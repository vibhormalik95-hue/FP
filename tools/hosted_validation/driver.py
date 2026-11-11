"""Inert unless explicitly invoked with reviewed execution configuration.
Direct application endpoints, no HTTP client/server; operator reviews are explicit.
"""
import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
import sys
import tempfile

EXPECTED_MODEL = 'claude-fable-5-2'
IDENTITY_BASIS = {
    'kind': 'official_documentation', 'expected_model_id': EXPECTED_MODEL,
    'requested_effort': 'max', 'minimum_cli_version': '2.1.321',
    'prior_runtime_observed': False, 'runtime_availability': 'unknown',
    'references': ['https://platform.claude.com/docs/en/models/fable-5-2/overview',
                   'https://code.claude.com/docs/en/model-config#work-with-fable'],
}

CAPS = {'category': 3, 'indirect': 2}
INPUT_MANIFEST_SHA256 = 'b524eb6ff4814140308f0708d5efc9ea201fb1431749297f8274c93b826c57d3'
SCENARIO_DIRS = {'category':'01-category-discovery', 'indirect':'02-hunger-continuation'}
GATES = ('runtime_authorized', 'data_authorized', 'subscription_and_usage_authorized',
         'executable_reviewed', 'managed_runtime_reviewed', 'process_containment_reviewed')
BOUNDS = {'max_output_tokens': 4096, 'max_request_bytes': 20000,
          'max_response_bytes': 1000000, 'timeout': 90}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def validate(config, source):
    require(config['scenario'] in CAPS, 'Unknown scenario')
    require(config['driver_sha256'] == digest(__file__), 'Driver differs from reviewed invocation')
    require(config['max_calls'] == CAPS[config['scenario']] and type(config['max_calls']) is int, 'Exact scenario cap required')
    require(config['output_mode'] == 'plain_json', 'Plain JSON only')
    require(all(config.get(g) is True for g in GATES), 'Six explicit reviewed assertions required')
    require(config['reviewed_cli_version'] == '2.1.321', 'Reviewed version differs')
    require(config['model'] == EXPECTED_MODEL and config['effort'] == 'max', 'Exact requested Fable model and max effort required')
    require(json.dumps(config.get('identity_basis'),sort_keys=True) == json.dumps(IDENTITY_BASIS,sort_keys=True), 'Explicit documented, unobserved identity basis required')
    for key, maximum in BOUNDS.items():
        value = config[key]
        require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= maximum, 'Invalid or raised bound: '+key)
    for name in ('authorization', 'model_identity', 'native_containment', 'managed_runtime'):
        receipt = config['review_receipts'][name]
        require(digest(receipt['path']) == receipt['sha256'], 'Review receipt changed: '+name)
    identity_receipt = config['review_receipts']['model_identity']
    require(json.dumps(json.loads(Path(identity_receipt['path']).read_text(encoding='utf-8')),sort_keys=True) == json.dumps(IDENTITY_BASIS,sort_keys=True), 'Identity receipt does not match documented target')
    require(bool(config['reviewer_reference'].strip()), 'Reviewer reference required')
    require(set(config['source_sha256']) == {str(p.relative_to(source)).replace('\\','/') for p in (source/'feedctrl').glob('*.py')}, 'Complete application Python manifest required')
    for relative in config['source_sha256']:
        require(digest(source / relative) == config['source_sha256'][relative], 'Reviewed source changed: '+relative)
    require(digest(config['executable']) == config['executable_sha256'], 'Executable changed')
    require(Path(config['workdir']).is_dir(), 'Isolated workdir missing')
    # These are supplied assertions and hash bindings, never proof that approval occurred.

def load_inputs(root, scenario):
    root=Path(root).resolve()
    require(digest(root/'MANIFEST.json')==INPUT_MANIFEST_SHA256,'Input manifest differs from reviewed package')
    manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    for name,expected in manifest.items():
        path=root/name
        require(path.resolve().is_relative_to(root) and path.is_file(),'Invalid input path')
        require(digest(path)==expected['sha256'] and path.stat().st_size==expected['bytes'],'Input drift: '+name)
    folder=root/SCENARIO_DIRS[scenario]
    body=json.loads((folder/'app-preview.json').read_text(encoding='utf-8'))
    rows=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    data=json.loads((folder/'app-data.json').read_text(encoding='utf-8'))
    ids=sorted(row['item_id'] for row in rows)
    require(ids==sorted(body['candidate_ids'])==sorted(row['item_id'] for row in data['items']),'Scope mismatch')
    require(data['metadata']['is_fixture'] is True,'Synthetic data required')
    return {'folder':folder,'body':body,'rows':rows,'data':data,
            'first':json.loads((folder/'first-model-input.json').read_text(encoding='utf-8')),
            'review_notes':(folder/'REVIEW-NOTES.md').read_text(encoding='utf-8'),
            'hashes':{name:expected['sha256'] for name,expected in manifest.items() if name.startswith(SCENARIO_DIRS[scenario]+'/')}}

def capturing_runner(runner, bundle, report, checkpoint):
    """Retain bounded exact logical CLI inputs before execution, no environment/argv secrets."""
    from feedctrl.model_adapters import _json
    def wrapped(argv, input_bytes, env, cwd, timeout, maximum):
        system=argv[argv.index('--system-prompt')+1]
        if not report['model_inputs']:
            first=bundle['first'];payload=first['payload']
            expected_system=payload['system']+('\n\nReturn exactly one JSON object matching this schema. '
                'Do not use Markdown, prose, or additional text. Schema: '+_json(first['schema']).decode('utf8'))
            require(input_bytes==_json({k:v for k,v in payload.items() if k!='system'}) and system==expected_system,
                    'First logical payload/schema differs from frozen input; no runner call')
        entry={'ordinal':len(report['model_inputs'])+1,'stdin_utf8':input_bytes.decode('utf8'),
               'stdin_sha256':hashlib.sha256(input_bytes).hexdigest(),
               'rendered_system_prompt':system,'rendered_system_sha256':hashlib.sha256(system.encode()).hexdigest(),
               'status':'prepared_before_runner'}
        report['model_inputs'].append(entry);checkpoint()
        try:
            result=runner(argv,input_bytes,env,cwd,timeout,maximum)
        except BaseException:
            entry['status']='runner_raised'
            try:checkpoint()
            except Exception:entry['post_error_checkpoint_failed']=True
            raise  # Preserve CleanupUncertain as the adapter's direct cause.
        entry['status']='runner_returned';checkpoint();return result
    return wrapped

def build(config, source, bundle, runner, report, checkpoint=lambda:None):
    from feedctrl.claude_personal_app import create_claude_personal_app
    from feedctrl.model_adapters import HostedRunBudget
    budget=HostedRunBudget(CAPS[config['scenario']])
    kwargs={k:config[k] for k in (*GATES,*BOUNDS,'executable','workdir','model','effort',
                 'estimated_per_invocation_usd','output_mode','reviewed_cli_version')}
    app=create_claude_personal_app(operator_token=config['operator_token'],
        allowed_origin='http://127.0.0.1:8765',fixture=False,
        data_path=bundle['folder']/'app-data.json',semantic_path=bundle['folder']/'metadata.csv',
        run_budget=budget,process_runner=capturing_runner(runner,bundle,report,checkpoint),**kwargs)
    return app,budget

def new_report(scenario,bundle):
    return {'status':'prepared','scenario':scenario,'steps':[],'operator_decisions':[],'model_inputs':[],
        'source_evidence':{'input_manifest_sha256':INPUT_MANIFEST_SHA256,'files':bundle['hashes'],
            'exact_app_request':bundle['body'],'all_scoped_metadata':bundle['rows'],
            'operator_only_facts_unknowns_and_review_notes':bundle['review_notes']},
        'semantic_evidence':{'judgment':'Not automatically scored; no fixed target set or gold category.',
            'indirect_limit':'Selected evidence is not a complete tri-state classification; unselected does not mean negative.',
            'historical_hunger_failure':'Unchanged; this would be a separate exposed continuation.'},
        'mechanics':{'applied':False,'undo_applied':False},
        'limitations':'Invented metadata and diagnostic scores; no general accuracy, utility, held-out comparison or real-media claim.'}

def run(app, scenario, review, report, bundle):
    from feedctrl.semantic_review import SemanticPreview,SemanticApply,SemanticHistory,InductionPreview
    from feedctrl.staged_routes import DefinitionApproval
    def endpoint(path):return next(r.endpoint for r in app.routes if getattr(r,'path',None)==path)
    session=endpoint('/api/session')()['session_id']
    user=bundle['body']['user_id']
    def call(path,body):
        from fastapi import HTTPException
        try:result=endpoint(path)(body,session)
        except HTTPException as exc:
            report['steps'].append({'path':path,'http_status':exc.status_code,'error_type':type(exc).__name__,'detail':str(exc.detail)})
            report['semantic_evidence']['operational_failure']={'http_status':exc.status_code,'error_type':type(exc).__name__}
            raise
        report['steps'].append({'path':path,'result':result});return result
    def saved():return endpoint('/api/semantic/groups')(user,session)
    original=saved()['feed'];report['mechanics']['baseline_available']=original['available_items']
    def unchanged():require(saved()['feed']==original and saved()['groups']==[],'Unapplied result mutated original state')
    def decision(label,value):
        context={'actual_proposal':value,'all_scoped_metadata':bundle['rows'],
                 'operator_only_facts_unknowns_and_review_notes':bundle['review_notes']}
        approved=review(label,context) is True
        report['operator_decisions'].append({'action':label,'approved':approved})
        if not approved:
            report['status']='operator_declined_no_apply';unchanged()
        return approved
    def terminal(value):
        report['status']='terminal_without_apply'
        report['semantic_evidence']['terminal_result']=value
        unchanged()
    if scenario=='category':
        definition=call('/api/semantic/definition/preview',InductionPreview(**bundle['body']))
        report['semantic_evidence']['definition_result']=definition
        if definition.get('definition_ready') is not True:return terminal(definition)
        unchanged()
        if not decision('review exact new definition and all supplied facts/unknowns before classification',definition):return
        proposal=call('/api/semantic/definition/classify',DefinitionApproval(user_id=user,
                      plan_id=definition['definition_plan_id'],evidence_reviewed=True))
    else:
        proposal=call('/api/semantic/preview',SemanticPreview(**bundle['body']))
    report['semantic_evidence']['proposal_result']=proposal
    if proposal.get('ready') is not True:return terminal(proposal)
    unchanged();require(proposal.get('applied') is False,'Unexpected automatic Apply')
    control=proposal['proposal'];selected=control['item_ids'];scope=bundle['body']['candidate_ids']
    report['semantic_evidence']['observed_selection']=[{'item_id':i,'selected':i in selected,
          'nonselection_is_not_a_negative_disposition':True} for i in scope]
    report['semantic_evidence']['returned_action']=control['action']
    if control['action']['operation']!='exclude' or control['action']['strength']!='none':
        report['status']='unsupported_action_preserved_no_apply';return
    if not decision('review every scoped item, missing facts, actual action and evidence before Apply',proposal):return
    applied=call('/api/semantic/apply',SemanticApply(user_id=user,plan_id=proposal['plan_id']))
    report['mechanics'].update(applied=True,selected_ids=selected,after_apply_available=applied['feed']['available_items'])
    require(applied['feed']['available_items']==original['available_items']-len(set(selected)), 'Actual exclusion count mismatch')
    undo=call('/api/semantic/history/preview',SemanticHistory(user_id=user,action='undo'))
    require(undo.get('ready') is True,'Undo unavailable')
    # Undo has its own explicit application review; declining leaves the applied state visible.
    approved=review('undo reviewed control',{'actual_proposal':undo,'all_scoped_metadata':bundle['rows'],
                    'operator_only_facts_unknowns_and_review_notes':bundle['review_notes']}) is True
    report['operator_decisions'].append({'action':'undo reviewed control','approved':approved})
    if not approved:
        report['status']='operator_declined_undo_control_still_applied';return
    undone=call('/api/semantic/apply',SemanticApply(user_id=user,plan_id=undo['plan_id']))
    report['mechanics'].update(undo_applied=True,after_undo_available=undone['feed']['available_items'])
    require(undone['feed']==original,'Undo did not restore exact baseline')
    report['status']='completed_reviewed_mechanics_semantics_not_automatically_scored'

def operator_review(label,value):
    print(json.dumps(value,indent=2)); print('Review:',label)
    return input('Type APPROVE to continue: ') == 'APPROVE'

USAGE_FIELDS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
MODEL_USAGE_FIELDS = ('inputTokens', 'outputTokens', 'cacheReadInputTokens',
                      'cacheCreationInputTokens', 'webSearchRequests', 'contextWindow', 'maxOutputTokens')

def numeric_usage(value, fields, include_cost=False):
    """Export known counters only, never provider-added strings or nested objects."""
    if not isinstance(value, dict): return {}
    out = {k: value[k] for k in fields if type(value.get(k)) is int and 0 <= value[k] <= 2**53-1}
    cost = value.get('costUSD')
    if include_cost and type(cost) in (int,float) and 0 <= cost <= 1000000 and math.isfinite(cost):
        out['costUSD'] = cost
    return out

def receipt_projection(receipts, config):
    """Bounded export schema for adapter receipts, not blanket content anonymization."""
    require(isinstance(receipts,list) and len(receipts) <= 3, 'Unexpected receipt count')
    model = config['model']
    require(isinstance(model,str) and re.fullmatch(r'claude-[a-zA-Z0-9.-]{1,120}',model), 'Invalid reviewed model')
    result=[]
    for receipt in receipts:
        require(isinstance(receipt,dict), 'Invalid receipt')
        out={}
        for key in ('request_sha256','schema_sha256','response_sha256'):
            value=receipt.get(key)
            if isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value): out[key]=value
        for key in ('logical_call_id','exit_code'):
            value=receipt.get(key)
            if type(value) is int and 0 <= value <= 2**32-1: out[key]=value
        for key in ('started_unix','elapsed_seconds','estimated_cost_usd'):
            value=receipt.get(key)
            if type(value) in (int,float) and 0 <= value <= 2**53-1 and math.isfinite(value): out[key]=value
        for key,allowed in {
            'outcome':('started','error','parsed_transport_only'),
            'output_mode':('plain_json',),
            'representation':('logical_invocation_reservation',),
        }.items():
            if receipt.get(key) in allowed: out[key]=receipt[key]
        # Re-project the adapter's closed evidence instead of trusting nested data.
        if receipt.get('failure_reason') in ('malformed_envelope', 'invalid_envelope_type',
                'incomplete_success', 'model_identity_validation_failed',
                'invalid_metadata', 'invalid_output'):
            out['failure_reason'] = receipt['failure_reason']
        status = receipt.get('cli_status')
        if isinstance(status, dict):
            safe = {}
            for key, allowed in {
                'type': ('result',),
                'subtype': ('success', 'error_during_execution', 'error_max_turns',
                            'error_max_budget_usd', 'error_max_structured_output_retries'),
                'stop_reason': ('end_turn', 'max_tokens', 'stop_sequence', 'tool_use',
                                'pause_turn', 'refusal'),
            }.items():
                if status.get(key) in allowed: safe[key] = status[key]
            if type(status.get('is_error')) is bool: safe['is_error'] = status['is_error']
            if type(status.get('num_turns')) is int and 0 <= status['num_turns'] <= 2**53-1:
                safe['num_turns'] = status['num_turns']
            out['cli_status'] = safe
        if 'error_type' in receipt:
            value=receipt['error_type']
            out['error_type']=value if value in ('ValueError','TimeoutError','OSError','CleanupUncertain','ParserOperationalError','ValidationError','WindowsRunnerError') else 'OtherError'
        if receipt.get('reported_model') == model: out['reported_model']=model
        if 'reported_usage' in receipt:
            out['reported_usage']=numeric_usage(receipt['reported_usage'],USAGE_FIELDS)
        model_usage=receipt.get('reported_model_usage')
        if isinstance(model_usage,dict) and model in model_usage:
            out['reported_model_usage']={model:numeric_usage(model_usage[model],MODEL_USAGE_FIELDS,True)}
        if 'estimated_cost_usd' in out: out['estimated_cost_note']='CLI estimate, not billing proof'
        result.append(out)
    return result

def redact(value, config):
    # Named sensitive fields and exact configured paths only. Free-text model output
    # is not comprehensively anonymized and must be reviewed before sharing.
    if isinstance(value, dict):
        out={}
        for k,v in value.items():
            if k=='receipts': out[k]=receipt_projection(v,config)
            elif k=='reported_usage': out[k]=numeric_usage(v,USAGE_FIELDS)
            elif k=='reported_model_usage':
                model=config['model']
                out[k]={model:numeric_usage(v[model],MODEL_USAGE_FIELDS,True)} if isinstance(v,dict) and model in v else {}
            elif any(x in k.lower() for x in ('account','email','token','executable','workdir','session_id')) and k not in USAGE_FIELDS:
                out[k]='[redacted]'
            else: out[k]=redact(v,config)
        return out
    if isinstance(value,list): return [redact(v,config) for v in value]
    if isinstance(value,str):
        for key in ('executable','workdir','operator_token'):
            value=value.replace(config[key],'[redacted]')
    return value

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed-config',required=True)
    parser.add_argument('--source',required=True);parser.add_argument('--report',required=True)
    parser.add_argument('--inputs',default=str(Path(__file__).parent/'inputs'))
    args=parser.parse_args();source=Path(args.source).resolve()
    config=json.loads(Path(args.reviewed_config).read_text(encoding='utf-8'));validate(config,source)
    require(config.get('input_manifest_sha256')==INPUT_MANIFEST_SHA256,'Reviewed input pin required')
    bundle=load_inputs(args.inputs,config['scenario'])
    require(not Path(args.report).exists(),'Report already exists; no rerun/overwrite')
    marker=Path(str(Path(args.reviewed_config).resolve())+'.consumed')
    with marker.open('x', encoding='utf-8') as handle:handle.write(digest(args.reviewed_config))
    sys.path.insert(0,str(source))
    from feedctrl.windows_job_runner import run_windows_job
    report=new_report(config['scenario'],bundle)
    report.update(config_sha256=digest(args.reviewed_config),identity_basis=config['identity_basis'],
                  evidence_kind='actual hosted application run only if actual receipts confirm')
    app=None;budget=None
    def checkpoint():
        if app is not None:report['receipts']=app.state.hosted_model_receipts
        if budget is not None:report['attempted']=budget.attempted
        Path(args.report).write_text(json.dumps(redact(report,config),indent=2), encoding='utf-8')
    try:
        app,budget=build(config,source,bundle,run_windows_job,report,checkpoint)
        run(app,config['scenario'],operator_review,report,bundle)
        require(budget.attempted<=CAPS[config['scenario']],'Scenario attempt cap exceeded')
        if report['mechanics']['applied']:require(budget.attempted==CAPS[config['scenario']],'Incomplete inference before Apply')
    except BaseException as exc:
        report['status']='stopped';report['error_type']=type(exc).__name__;raise
    finally:checkpoint()

if __name__=='__main__':main()
