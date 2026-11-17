"""Explicit one/two-call personal CLI binding; import never invokes a provider."""
from pathlib import Path
from . import bootstrap
from .flow_guard import FlowGuard

class _ModelPinnedRunner:
    """Reject a changed model before reserving or starting a transport."""
    def __init__(self,runner,model):self.runner=runner;self.model=model
    def __call__(self,argv,*args):
        if type(argv) is not list or argv.count('--model')!=1:
            raise ValueError('model_binding_mismatch')
        index=argv.index('--model')
        if index+1>=len(argv) or argv[index+1]!=self.model:
            raise ValueError('model_binding_mismatch')
        return self.runner(argv,*args)

_APPROVALS=frozenset(('runtime_authorized','data_authorized','subscription_and_usage_authorized',
                      'executable_reviewed','managed_runtime_reviewed','process_containment_reviewed'))

def construct(*, enable_live=False, context, marker, allowed_origin,
              model, effort, estimated_per_invocation_usd, output_mode, reviewed_cli_version,
              approvals, reviewed_files, max_calls=1, request=None, catalogue_sha256=None,
              flow_mode=None, source_sha256=None, candidate_ids=None,
              timeout=300, max_request_bytes=20000, max_response_bytes=1000000,
              fixture=False, data_path=None, semantic_path=None):
    """Construct after explicit review; never starts a listener or invokes a model."""
    if enable_live is not True or type(context) is not dict or type(approvals) is not dict:
        raise ValueError('explicit_review_required')
    if set(context) != {'context_file','context_sha256','cli','workdir','home'}:
        raise ValueError('explicit_context_required')
    if set(approvals) != _APPROVALS or any(v is not True for v in approvals.values()):
        raise ValueError('separate_reviews_required')
    if type(max_calls) is not int or max_calls not in (1,2):raise ValueError('invalid_call_budget')
    if type(reviewed_files) is not dict or not reviewed_files:raise ValueError('reviewed_inputs_required')
    if type(fixture) is not bool or (fixture and data_path is not None):raise ValueError('ambiguous_fixture')
    required={str(Path(p)) for p in (data_path,semantic_path) if p is not None}
    if not required or set(reviewed_files)!=required:raise ValueError('input_pin_scope_mismatch')
    if flow_mode=='combined-v1' and (max_calls!=1 or semantic_path is None or reviewed_files[str(Path(semantic_path))]!=source_sha256):
        raise ValueError('combined_source_binding_mismatch')
    qualification=bootstrap._load()
    for name,digest in reviewed_files.items():
        if not qualification._hash_string(digest) or qualification._digest(Path(name))!=digest:
            raise ValueError('input_identity_mismatch')
    runner,observations=bootstrap.bind_once(marker=marker,enable_live=True,max_calls=max_calls,**context)
    reviewed=qualification._load_context(context['context_file'],context['context_sha256'])
    if flow_mode=='combined-v1':runner=_ModelPinnedRunner(runner,model)
    from feedctrl.claude_personal_app import create_claude_personal_app
    from feedctrl.model_adapters import HostedRunBudget
    def wrap(infer):
        return FlowGuard(infer,max_calls=max_calls,request=request,catalogue_sha256=catalogue_sha256,
                         files=reviewed_files,file_digest=qualification._digest,mode=flow_mode,
                         source_sha256=source_sha256,candidate_ids=candidate_ids,model=model,scope_timeout=timeout)
    app=create_claude_personal_app(allowed_origin=allowed_origin,
        data_path=data_path,semantic_path=semantic_path,fixture=fixture,infer_wrapper=wrap,
        executable=str(context['cli']),workdir=str(context['workdir']),model=model,effort=effort,
        run_budget=HostedRunBudget(max_calls),estimated_per_invocation_usd=estimated_per_invocation_usd,
        output_mode=output_mode,reviewed_cli_version=reviewed_cli_version,
        max_output_tokens=int(reviewed['max_output_tokens']),timeout=timeout,
        max_request_bytes=max_request_bytes,max_response_bytes=max_response_bytes,
        runtime_mode='reviewed_hooks',reviewed_hooks_context_sha256=context['context_sha256'],
        process_runner=runner,**approvals)
    return app,observations
