"""Session-bound definition approval followed by independently reviewed membership."""
from copy import deepcopy
import os
import secrets
import time

from fastapi import Header,HTTPException
from pydantic import BaseModel,ConfigDict,Field,StrictBool,field_validator
from feedctrl import induction_integration as ii
from feedctrl import staged_induction as staged
from feedctrl.indirect_grounding import _digest
from feedctrl.controls import ParserOperationalError
from feedctrl.semantic_controls import STRENGTH_WEIGHTS
from feedctrl.semantic_review import InductionPreview,scoped_index,seal_group

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

def install_staged_routes(app,demo,state_for,review):
    def binding(pending):
        return _digest({k:pending[k] for k in ('id','created','revision','nonce','body','definition',
                                             'eligible_sha256','definition_model_calls')})

    def current(pending,state):
        if (not pending or pending.get('used') or time.monotonic()-pending['created']>300
                or state['semantic_revision']!=pending['revision']
                or state.get('semantic_preview_nonce')!=pending['nonce']):
            raise ValueError('Definition review expired, consumed or superseded')
        if pending.get('binding_sha256')!=binding(pending): raise ValueError('Definition review record changed')
        scope=scoped_index(demo.topic_index,pending['body']['candidate_ids'])
        inventory=ii.projected_inventory(scope,demo.items,state['semantic_groups'])
        if _digest(sorted(demo.items))!=pending['eligible_sha256']: raise ValueError('Eligible catalogue changed')
        staged.revalidate_definition(pending['definition'],pending['body']['objective'],scope,inventory)
        return scope,inventory

    @app.post('/api/semantic/definition/preview')
    def propose(body:InductionPreview,x_session_id:str|None=Header(default=None)):
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
            infer,model,calls=ii.make_induction_infer(os.getenv('FEEDCTRL_STEERING_MODEL','qwen2.5-coder:7b-instruct'),timeout=90)
            definition=staged.propose_definition(body.objective,scope,inventory,infer,model)
            if definition['status']!='definition_review':
                return {'definition_ready':False,'applied':False,**definition,'model_calls':deepcopy(calls)}
            with demo.lock:
                state=state_for(x_session_id,body.user_id)
                pending={'id':secrets.token_urlsafe(24),'created':time.monotonic(),'revision':revision,
                    'nonce':nonce,'body':body.model_dump(),'definition':deepcopy(definition),
                    'eligible_sha256':eligible,'definition_model_calls':deepcopy(calls),'used':False}
                pending['binding_sha256']=binding(pending)
                current(pending,state)
                state['semantic_definition_pending']=pending
                return {'definition_ready':True,'applied':False,'definition_plan_id':pending['id'],
                    'definition':deepcopy(definition),'scope_ids':sorted(scope['items']),
                    'model_calls':deepcopy(calls),'action_source':'manual'}
        except (ValueError,ParserOperationalError) as exc:
            return {'definition_ready':False,'applied':False,'status':'error','reason':str(exc),'model_calls':deepcopy(calls)}

    @app.post('/api/semantic/definition/classify')
    def classify(body:DefinitionApproval,x_session_id:str|None=Header(default=None)):
        calls=[]
        with demo.lock:
            state=state_for(x_session_id,body.user_id);pending=state.get('semantic_definition_pending')
            if not pending or pending['id']!=body.plan_id: raise HTTPException(409,'No matching definition review')
            try: scope,inventory=current(pending,state)
            except ValueError as exc: raise HTTPException(409,str(exc)) from exc
            owned=deepcopy(pending);pending['used']=True
        try:
            infer,model,calls=ii.make_induction_infer(owned['definition']['provenance']['model_id'],timeout=90)
            request=owned['body']
            envelope=staged.classify_definition(owned['definition'],request['objective'],scope,inventory,infer,model)
            if envelope['status']!='review':
                return {'ready':False,'applied':False,**envelope,'model_calls':deepcopy(calls)}
            with demo.lock:
                state=state_for(x_session_id,body.user_id)
                # Validate again with a separate unused copy: a consumed token cannot
                # start another call, while its in-flight result can still be checked.
                scope,inventory=current(owned,state)
                staged.revalidate_membership_envelope(envelope,request['objective'],scope,inventory)
                control=ii.category_as_control(envelope,request['objective'],scope,inventory,
                    request['operation'],request['strength'],model)
                control['induction'].update(definition_model_calls=owned['definition_model_calls'],model_calls=deepcopy(calls))
                group=seal_group(envelope['proposal']['label'],request['objective'],control,scope,demo.items)
                groups=([] if request['mode']=='replace' else deepcopy(state['semantic_groups']))+[group]
                if len(groups)>8: raise ValueError('At most eight active semantic groups')
                result=review(state,body.user_id,groups,proposal=control)
                state['semantic_pending']['induction_context']={
                    'candidate_ids':request['candidate_ids'],'inventory_sha256':_digest(inventory)}
                state['semantic_definition_pending']=None
                return {**result,'definition_approved':True,'induction':deepcopy(envelope),'model_calls':deepcopy(calls)}
        except (ValueError,ParserOperationalError) as exc:
            return {'ready':False,'applied':False,'status':'error','reason':str(exc),'model_calls':deepcopy(calls)}
