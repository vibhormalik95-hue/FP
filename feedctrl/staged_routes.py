"""Session-bound definition approval followed by independently reviewed membership."""
from copy import deepcopy
import os
import secrets
import time
from typing import Literal

from fastapi import Header,HTTPException
from pydantic import BaseModel,ConfigDict,Field,StrictBool,field_validator
from feedctrl import induction_integration as ii
from feedctrl import staged_induction as staged
from feedctrl import evidence_audit
from feedctrl.indirect_grounding import _digest
from feedctrl.controls import ParserOperationalError
from feedctrl.semantic_controls import STRENGTH_WEIGHTS
from feedctrl.semantic_review import InductionPreview,scoped_index,seal_group

# The operator must start classification within the original review window.
# Once started, two bounded calls and cleanup have one fixed in-flight deadline;
# revision, nonce, source, inventory and sealed-record checks remain mandatory.
_DEFINITION_REVIEW_TTL_SECONDS = 300
_CLASSIFICATION_INFLIGHT_SECONDS = 2 * 600 + 30


def _within_review_window(created, now, *, inflight_deadline=None):
    if inflight_deadline is None:
        return now - created <= _DEFINITION_REVIEW_TTL_SECONDS
    return now <= inflight_deadline


class DefinitionApproval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_id:int=Field(ge=0)
    plan_id:str=Field(min_length=1,max_length=100)
    evidence_reviewed:StrictBool

    @field_validator('evidence_reviewed')
    @classmethod
    def affirmative(cls,value):
        if value is not True: raise ValueError('Explicit evidence review is required')
        return value

class DefinitionResolution(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_id:int=Field(ge=0)
    plan_id:str=Field(min_length=1,max_length=100)
    choice:Literal['review_primary','cancel']


def install_staged_routes(app,demo,state_for,review,*,evidence_context,category_provider=None):
    if category_provider is None:
        from feedctrl.category_provider import CategoryProvider
        category_provider = CategoryProvider()
    def binding(pending):
        return _digest({k:pending[k] for k in ('id','created','revision','nonce','body','definition',
                                             'eligible_sha256','definition_model_calls','session_id')})

    def current(pending,state,session_id,user_id,*,clarification=False,inflight_deadline=None):
        if (not pending or pending.get('used') or pending['session_id']!=session_id
                or pending['body']['user_id']!=user_id
                or not _within_review_window(pending['created'],time.monotonic(),inflight_deadline=inflight_deadline)
                or state['semantic_revision']!=pending['revision']
                or state.get('semantic_preview_nonce')!=pending['nonce']):
            raise ValueError('Definition review expired, consumed or superseded')
        if pending.get('binding_sha256')!=binding(pending): raise ValueError('Definition review record changed')
        scope=scoped_index(demo.topic_index,pending['body']['candidate_ids'])
        inventory=ii.projected_inventory(scope,demo.items,state['semantic_groups'])
        if _digest(sorted(demo.items))!=pending['eligible_sha256']: raise ValueError('Eligible catalogue changed')
        validate=staged.revalidate_clarification if clarification else staged.revalidate_definition
        validate(pending['definition'],pending['body']['objective'],scope,inventory)
        return scope,inventory

    @app.post('/api/semantic/definition/preview')
    def propose(body:InductionPreview,x_session_id:str|None=Header(default=None)):
        try:
            category_provider.require_available()
        except ParserOperationalError as exc:
            raise HTTPException(503,str(exc)) from exc
        if (body.strength!='none' if body.operation=='exclude' else body.strength not in STRENGTH_WEIGHTS):
            raise HTTPException(422,'Invalid operation/strength')
        calls=[]
        with demo.lock:
            state=state_for(x_session_id,body.user_id)
            nonce=secrets.token_urlsafe(16);revision=state['semantic_revision']
            state.update(semantic_preview_nonce=nonce,semantic_pending=None,semantic_definition_pending=None)
            try:
                scope=scoped_index(demo.topic_index,body.candidate_ids)
                inventory=ii.projected_inventory(scope,demo.items,state['semantic_groups'])
            except ValueError as exc: raise HTTPException(422,str(exc)) from exc
            eligible=_digest(sorted(demo.items))
        try:
            infer,model,calls=category_provider.stage('definition',os.getenv('FEEDCTRL_STEERING_MODEL','qwen2.5-coder:7b-instruct'))
            definition=staged.propose_definition(body.objective,scope,inventory,infer,model)
            resolvable=definition['status']=='clarify' and bool(definition.get('clarification',{}).get('candidate'))
            if definition['status']!='definition_review' and not resolvable:
                return {'definition_ready':False,'applied':False,**definition,'model_calls':deepcopy(calls)}
            with demo.lock:
                state=state_for(x_session_id,body.user_id)
                pending={'id':secrets.token_urlsafe(24),'created':time.monotonic(),'revision':revision,
                    'nonce':nonce,'session_id':x_session_id,'body':body.model_dump(),'definition':deepcopy(definition),
                    'eligible_sha256':eligible,'definition_model_calls':deepcopy(calls),'used':False}
                pending['binding_sha256']=binding(pending)
                scope,inventory=current(pending,state,x_session_id,body.user_id,clarification=resolvable)
                state['semantic_definition_pending']=pending
                if resolvable:
                    return {'definition_ready':False,'resolution_ready':True,'resolution_plan_id':pending['id'],
                        'applied':False,**deepcopy(definition),'model_calls':deepcopy(calls),
                        'scope_ids':sorted(scope['items']),
                        'evidence_context':evidence_context(definition['clarification']['candidate'],scope)}
                return {'definition_ready':True,'applied':False,'definition_plan_id':pending['id'],
                    'definition':deepcopy(definition),'scope_ids':sorted(scope['items']),
                    'evidence_context':evidence_context(definition['proposal'],scope),
                    'model_calls':deepcopy(calls),'action_source':'manual'}
        except (ValueError,ParserOperationalError) as exc:
            return {'definition_ready':False,'applied':False,'status':'error','reason':str(exc),'model_calls':deepcopy(calls)}

    @app.post('/api/semantic/definition/resolve')
    def resolve(body:DefinitionResolution,x_session_id:str|None=Header(default=None)):
        # No provider lookup or inference: the client supplies only a bounded choice.
        with demo.lock:
            state=state_for(x_session_id,body.user_id);pending=state.get('semantic_definition_pending')
            if not pending or pending['id']!=body.plan_id:
                raise HTTPException(409,'No matching definition clarification')
            try:
                scope,inventory=current(pending,state,x_session_id,body.user_id,clarification=True)
                if body.choice=='cancel':
                    pending['used']=True
                    state['semantic_definition_pending']=None
                    return {'definition_ready':False,'resolution_ready':False,'applied':False,'status':'cancelled'}
                definition=staged.resolve_primary(pending['definition'],pending['body']['objective'],scope,inventory,
                    user_id=body.user_id,resolved_at=time.time())
                # Replace the single-use clarification with a distinct ordinary review token.
                next_pending={**deepcopy(pending),'id':secrets.token_urlsafe(24),'created':time.monotonic(),
                    'definition':definition,'used':False}
                next_pending['binding_sha256']=binding(next_pending)
                current(next_pending,state,x_session_id,body.user_id)
                pending['used']=True
                state['semantic_definition_pending']=next_pending
                return {'definition_ready':True,'resolution_ready':False,'applied':False,
                    'definition_plan_id':next_pending['id'],'definition':deepcopy(definition),
                    'scope_ids':sorted(scope['items']),'model_calls':deepcopy(next_pending['definition_model_calls']),
                    'action_source':'manual','evidence_context':evidence_context(definition['proposal'],scope)}
            except ValueError as exc: raise HTTPException(409,str(exc)) from exc

    @app.post('/api/semantic/definition/classify')
    def classify(body:DefinitionApproval,x_session_id:str|None=Header(default=None)):
        try:
            category_provider.require_available()
        except ParserOperationalError as exc:
            raise HTTPException(503,str(exc)) from exc
        calls=[];audit_calls=[]
        with demo.lock:
            state=state_for(x_session_id,body.user_id);pending=state.get('semantic_definition_pending')
            if not pending or pending['id']!=body.plan_id: raise HTTPException(409,'No matching definition review')
            try: scope,inventory=current(pending,state,x_session_id,body.user_id)
            except ValueError as exc: raise HTTPException(409,str(exc)) from exc
            owned=deepcopy(pending);pending['used']=True
            inflight_deadline=time.monotonic()+_CLASSIFICATION_INFLIGHT_SECONDS
        try:
            infer,model,calls=category_provider.stage('membership',owned['definition']['provenance']['model_id'],
                expected=owned['definition']['provenance'])
            request=owned['body']
            envelope=staged.classify_definition(owned['definition'],request['objective'],scope,inventory,infer,model)
            if envelope['status']!='review':
                return {'ready':False,'applied':False,**envelope,'model_calls':deepcopy(calls)}
            with demo.lock:
                current(owned,state_for(x_session_id,body.user_id),x_session_id,body.user_id,inflight_deadline=inflight_deadline)
            audit_infer,audit_model,audit_calls=category_provider.stage('evidence_audit',model['model_id'],expected=model)
            if audit_model!=model:raise ValueError('Model identity changed before evidence assessment')
            envelope=evidence_audit.audit_membership_envelope(envelope,request['objective'],scope,inventory,audit_infer,audit_model)
            if envelope['status']!='review':
                return {'ready':False,'applied':False,**envelope,'model_calls':deepcopy(calls),
                    'evidence_audit_model_calls':deepcopy(audit_calls)}
            with demo.lock:
                state=state_for(x_session_id,body.user_id)
                # Validate again with a separate unused copy: a consumed token cannot
                # start another call, while its in-flight result can still be checked.
                scope,inventory=current(owned,state,x_session_id,body.user_id,inflight_deadline=inflight_deadline)
                staged.revalidate_membership_envelope(envelope,request['objective'],scope,inventory)
                control=ii.category_as_control(envelope,request['objective'],scope,inventory,
                    request['operation'],request['strength'],model)
                control['induction'].update(definition_model_calls=owned['definition_model_calls'],model_calls=deepcopy(calls),
                    evidence_audit_model_calls=deepcopy(audit_calls))
                group=seal_group(envelope['proposal']['label'],request['objective'],control,scope,demo.items)
                groups=([] if request['mode']=='replace' else deepcopy(state['semantic_groups']))+[group]
                if len(groups)>8: raise ValueError('At most eight active semantic groups')
                result=review(state,body.user_id,groups,proposal=control)
                state['semantic_pending']['induction_context']={
                    'candidate_ids':request['candidate_ids'],'inventory_sha256':_digest(inventory)}
                state['semantic_definition_pending']=None
                return {**result,'definition_approved':True,'induction':deepcopy(envelope),'model_calls':deepcopy(calls),
                    'evidence_audit_model_calls':deepcopy(audit_calls)}
        except (ValueError,ParserOperationalError) as exc:
            return {'ready':False,'applied':False,'status':'error','reason':str(exc),'model_calls':deepcopy(calls),
                'evidence_audit_model_calls':deepcopy(audit_calls)}
