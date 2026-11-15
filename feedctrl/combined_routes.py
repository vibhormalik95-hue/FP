"""Atomic, session-bound review of mixed preferences grounded in item metadata."""
from copy import deepcopy
import secrets
from fastapi import Header, HTTPException
from feedctrl import combined_grounding as grounding
from feedctrl.indirect_grounding import (APPLICATION_CHECK, PROVIDER_FAILURE, REPLY_REJECTED,
    _catalogue, _digest, _response_snapshot, clean_page_text, failure_sentence, rejected_call)
from feedctrl.semantic_review import (MAX_GROUPS, printable_request, scoped_index, seal_group,
    scope_effect, limit_reason)
from feedctrl.vocabulary_routes import VocabularyPreview, ACTION_WORDS


def install_combined_routes(app,demo,state_for,review,*,configured_infer,provider_available,scope_guard=None,scope_identity=None):
    @app.post('/api/semantic/combined/preview')
    def preview(body:VocabularyPreview,x_session_id:str|None=Header(default=None)):
        if not provider_available:
            raise HTTPException(503,'No configured provider; no model call was attempted')
        calls,attempts,provenance=[],[],None
        preview_scope=None
        try:
            with demo.lock:
                state=state_for(x_session_id,body.user_id)
                revision,nonce=state['semantic_revision'],secrets.token_urlsafe(16)
                state['semantic_preview_nonce']=nonce
                state['semantic_pending']=None
                existing=deepcopy(state['semantic_groups'])
                if scope_guard is not None:
                    if getattr(scope_guard,'flow_mode',None)!='combined-v1':
                        scope_guard.reject_scope()
                        raise HTTPException(409,'Combined preview scope unavailable')
                    def preview_is_current():
                        current=state_for(x_session_id,body.user_id)
                        current_index=scoped_index(demo.topic_index,body.candidate_ids)
                        return (current['semantic_revision']==revision and current.get('semantic_preview_nonce')==nonce
                            and current_index['sha256']==scope_guard.source_sha256
                            and _digest(_catalogue(current_index))==scope_guard.catalogue_sha256)
                    binding={'mode':'combined-v1','request':body.text,
                        'source_sha256':demo.topic_index['sha256'],
                        'candidate_ids':tuple(sorted(body.candidate_ids)),
                        'model':scope_identity.get('model') if isinstance(scope_identity,dict) else None}
                    try:
                        preview_scope=scope_guard.open_preview_scope(state_lock=demo.lock,validate=preview_is_current,
                            identity=(x_session_id,body.user_id,nonce),binding=binding)
                    except ValueError as exc:
                        raise HTTPException(409,'Combined preview scope unavailable') from exc
                try: index=scoped_index(demo.topic_index,body.candidate_ids)
                except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        except BaseException:
            if preview_scope is not None:preview_scope.close()
            elif scope_guard is not None:scope_guard.reject_scope()
            raise
        def stopped(status,reason,source,checks=None):
            return {'ready':False,'applied':False,'grounding':'combined','status':status,'reason':reason,
                'outcome_source':source,'failed_stage':'interpretation','checks':checks or [],
                'model_calls':deepcopy(calls),'model_provenance':deepcopy(provenance),
                'calls_attempted':len(attempts),'call_attempts':deepcopy(attempts)}
        try:
            try:
                infer,provenance=configured_infer()
                if scope_guard is not None:
                    if preview_scope is None or infer is not scope_guard or provenance.get('model')!=scope_guard.model:
                        raise ValueError('Combined provider identity mismatch')
                    infer=preview_scope
            except Exception as exc:
                return stopped('error',failure_sentence(exc),PROVIDER_FAILURE)
            def tracked(payload,schema):
                attempt={'stage':'interpretation','status':'started'}
                attempts.append(attempt)
                try: raw=infer(deepcopy(payload),deepcopy(schema))
                except Exception as exc:
                    attempt.update(status='failed',error_type=type(exc).__name__)
                    raise
                try: bounded=_response_snapshot(raw)
                except (TypeError,ValueError,RecursionError):
                    attempt['status']='reply_rejected'
                    calls.append(rejected_call(payload,schema,raw))
                    return raw
                attempt['status']='returned'
                calls.append({'request_sha256':_digest(payload),'schema_sha256':_digest(schema),
                    'response_sha256':_digest(bounded),'raw_response':deepcopy(bounded)})
                return bounded
            try:
                proposal=grounding.propose_combined(body.text,index,tracked,model_provenance=provenance)
                if proposal['status']!='review':
                    return stopped(proposal['status'],proposal['reason'],proposal['outcome_source'],proposal['checks'])
                # Same-request refresh replaces only this method's exact request and scope.
                kept=[] if body.mode=='replace' else [g for g in existing if not (
                    g['proposal'].get('grounding')=='combined' and g['request']==body.text and
                    g['scope_ids']==sorted(index['items']))]
                if len(kept)+len(proposal['controls'])>MAX_GROUPS:
                    return stopped('limit',limit_reason(len(kept),len(proposal['controls'])),APPLICATION_CHECK,proposal['checks'])
                taken={g['label'].casefold() for g in kept}
                groups=[]
                for c in proposal['controls']:
                    label=clean_page_text(f'{ACTION_WORDS[c["action"]["operation"]]}: {c["action"]["intent_span"]}',70)
                    base,n=label,2
                    while label.casefold() in taken:
                        label=f'{base} ({n})';n+=1
                    taken.add(label.casefold())
                    sealed={'status':'review','requires_review':True,'reason':c['relation'],
                        'action':deepcopy(c['action']),'item_ids':list(c['item_ids']),
                        'evidence':deepcopy(c['evidence']),'provenance':deepcopy(c['provenance']),
                        'action_source':'model','grounding':'combined','checks':deepcopy(proposal['checks'])}
                    groups.append(seal_group(label,body.text,sealed,index,demo.items))
                with demo.lock:
                    state=state_for(x_session_id,body.user_id)
                    if state['semantic_revision']!=revision or state.get('semantic_preview_nonce')!=nonce:
                        raise HTTPException(409,'Preferences changed during inference; review again')
                    result=review(state,body.user_id,kept+groups,proposals=[g['proposal'] for g in groups])
                    return {**result,'grounding':'combined','checks':proposal['checks'],
                        'reply_reason':proposal['reason'],'model_calls':deepcopy(calls),
                        'model_provenance':deepcopy(provenance),'calls_attempted':len(attempts),
                        'call_attempts':deepcopy(attempts),
                        'scope_effects':[scope_effect(g['label'],g['proposal']['item_ids'],[],len(index['items'])) for g in groups]}
            except ValueError as exc:
                return stopped('error',clean_page_text(exc),REPLY_REJECTED if attempts else APPLICATION_CHECK)
        finally:
            if preview_scope is not None:preview_scope.close()
