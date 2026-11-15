"""Inference sequencing and preview-lifetime binding; no provider call on import."""
from copy import deepcopy
import hashlib
import json
import math
import time
from pathlib import Path
from threading import Lock

class FlowGuardError(ValueError):
    pass

def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()

class _PreviewScope:
    def __init__(self,guard,state_lock,validate,identity,deadline=None):
        self._guard=guard;self._state_lock=state_lock;self._validate=validate;self._identity=identity;self._deadline=deadline;self._closed=False
    def __call__(self,payload,schema):
        return self._guard._scoped_call(self,payload,schema)
    def close(self):
        self._guard._close_scope(self)

class FlowGuard:
    def __init__(self, inner, *, max_calls, request, catalogue_sha256, files, file_digest, mode=None, source_sha256=None, candidate_ids=None, model=None, scope_timeout=None):
        if not callable(inner) or type(max_calls) is not int or max_calls not in (1,2):
            raise FlowGuardError('invalid_flow')
        if mode is None:mode='indirect-v1' if max_calls==2 else 'single-v1'
        if mode not in ('single-v1','indirect-v1','combined-v1') or (mode=='indirect-v1' and max_calls!=2) or (mode!='indirect-v1' and max_calls!=1):
            raise FlowGuardError('invalid_flow_mode')
        if mode in ('indirect-v1','combined-v1') and (type(request) is not str or not request.strip() or
                type(catalogue_sha256) is not str or len(catalogue_sha256)!=64 or
                any(c not in '0123456789abcdef' for c in catalogue_sha256)):
            raise FlowGuardError('scoped_request_required')
        if mode=='combined-v1' and (type(source_sha256) is not str or len(source_sha256)!=64 or
                any(c not in '0123456789abcdef' for c in source_sha256) or
                type(candidate_ids) not in (list,tuple) or not 2<=len(candidate_ids)<=20 or
                any(type(i) is not int for i in candidate_ids) or len(set(candidate_ids))!=len(candidate_ids) or
                type(model) is not str or not model or type(scope_timeout) not in (int,float) or
                not math.isfinite(scope_timeout) or not 0<scope_timeout<=600):
            raise FlowGuardError('combined_binding_required')
        if type(files) is not dict or not files or not callable(file_digest):
            raise FlowGuardError('input_pins_required')
        self.inner=inner;self.maximum=max_calls;self.request=request;self.catalogue_sha256=catalogue_sha256
        self.files=dict(files);self.file_digest=file_digest;self.count=0;self.failed=False;self.action=None;self.lock=Lock()
        self.flow_mode=mode;self.source_sha256=source_sha256;self.candidate_ids=tuple(sorted(candidate_ids)) if mode=='combined-v1' else None;self.model=model
        self.scope_timeout=scope_timeout;self._clock=time.monotonic
        self.is_guarded_inference=True;self.requires_preview_scope=(mode!='single-v1');self._claimed=False;self._active=None;self._inflight=False
    def open_preview_scope(self, *, state_lock, validate, identity, binding=None):
        """Claim one opaque session/user/nonce while its application state is locked."""
        if (not self.requires_preview_scope or not callable(validate) or type(identity) is not tuple or len(identity)!=3
            or not isinstance(identity[0],str) or not identity[0] or type(identity[1]) is not int
            or not isinstance(identity[2],str) or not identity[2]):
            raise FlowGuardError('invalid_preview_scope')
        with state_lock:
            with self.lock:
                if self._claimed or self.failed or self.count:raise FlowGuardError('scope_unavailable')
                self._claimed=True
                try:
                    if self.flow_mode=='combined-v1':
                        expected={'mode':'combined-v1','request':self.request,'source_sha256':self.source_sha256,
                                  'candidate_ids':self.candidate_ids,'model':self.model}
                        if binding != expected:raise FlowGuardError('combined_scope_mismatch')
                    elif binding is not None:raise FlowGuardError('unexpected_scope_binding')
                    if validate() is not True:raise FlowGuardError('preview_expired')
                    deadline=self._clock()+self.scope_timeout if self.flow_mode=='combined-v1' else None
                    scope=_PreviewScope(self,state_lock,validate,identity,deadline);self._active=scope
                    return scope
                except BaseException:
                    self.failed=True
                    raise
    def reject_scope(self):
        with self.lock:
            self._claimed=True;self.failed=True
            if self._active is not None:self._active._closed=True
    def _close_scope(self,scope):
        with self.lock:
            if scope is self._active:
                scope._closed=True;self.failed=True
    def _validate_payload(self,payload,schema):
        for path,expected in self.files.items():
            if self.file_digest(Path(path)) != expected:raise FlowGuardError('input_changed')
        if self.flow_mode == 'combined-v1':
            from feedctrl.combined_grounding import SCHEMA,PROMPT
            if (type(payload) is not dict or set(payload)!={'system','request','catalogue'}
                or payload['system']!=PROMPT or payload['request']!=self.request or schema!=SCHEMA
                or _digest(payload['catalogue'])!=self.catalogue_sha256
                or tuple(sorted(row['item_id'] for row in payload['catalogue']))!=self.candidate_ids):
                raise FlowGuardError('unexpected_combined_request')
        elif self.flow_mode == 'indirect-v1':
            from feedctrl.semantic_review import ACTION_SCHEMA,ACTION_PROMPT
            from feedctrl.indirect_grounding import SCHEMA,PROMPT
            if self.count == 0:
                if payload != {'system':ACTION_PROMPT,'request':self.request} or schema != ACTION_SCHEMA:
                    raise FlowGuardError('unexpected_action_request')
            elif (type(payload) is not dict or set(payload) != {'system','request','action','catalogue'}
                  or payload['system'] != PROMPT or payload['request'] != self.request
                  or payload['action'] != self.action or schema != SCHEMA
                  or _digest(payload['catalogue']) != self.catalogue_sha256):
                raise FlowGuardError('unexpected_grounding_request')
    def _invoke_reserved(self,payload,schema,scope):
        try:
            response=self.inner(payload,schema)
            with self.lock:
                self._inflight=False
                if scope is not None and scope._closed:
                    self.failed=True;raise FlowGuardError('scope_closed')
                if self.flow_mode == 'indirect-v1' and self.count == 1:
                    from feedctrl.semantic_review import interpret_action
                    self.action,_ = interpret_action(self.request,lambda _payload,_schema:deepcopy(response))
                    if self.action is None:self.failed=True
                return response
        except BaseException:
            with self.lock:
                self._inflight=False;self.failed=True
            raise
    def _scoped_call(self,scope,payload,schema):
        # Lock order is always application state, then guard. Reservation while
        # both are held is the dispatch linearization point; neither remains held
        # across the provider call. A later supersession cannot revoke that call.
        with scope._state_lock:
            with self.lock:
                try:
                    if (scope is not self._active or scope._closed or self.failed or self._inflight
                        or self.count>=self.maximum or (scope._deadline is not None and self._clock()>scope._deadline)
                        or scope._validate() is not True):
                        raise FlowGuardError('scope_unavailable')
                    self._validate_payload(payload,schema)
                    self.count+=1;self._inflight=True
                except BaseException:
                    self.failed=True
                    raise
        return self._invoke_reserved(payload,schema,scope)
    def __call__(self,payload,schema):
        if self.requires_preview_scope:
            with self.lock:self.failed=True
            raise FlowGuardError('preview_scope_required')
        with self.lock:
            try:
                if self.failed or self._inflight or self.count>=self.maximum:raise FlowGuardError('flow_consumed')
                self._validate_payload(payload,schema);self.count+=1;self._inflight=True
            except BaseException:
                self.failed=True
                raise
        return self._invoke_reserved(payload,schema,None)
