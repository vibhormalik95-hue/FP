"""Data-free formal E2 preparation. No bank authoring, annotation or model inference."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.verify_frozen_e1 import verify
from feedctrl.controls import ollama_provenance
from feedctrl import experiment2_controls as controls
from feedctrl import experiment2_evaluation as evaluation

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for n in ('output','archive','practice','old-delivery'):cli.add_argument('--'+n,type=Path,required=True)
    a=cli.parse_args();out=a.output.resolve()
    if out.exists():raise ValueError('Preparation output must be genuinely new')
    out.mkdir(parents=True)
    record={'created_utc':datetime.now(timezone.utc).isoformat(),'client_date':'2026-10-14','client_timezone':'America/Vancouver','scope':'preparation only; no bank, labels, final freeze or inference','status':'preparation_started'}
    try:
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        assert branch=='codex/oct13-safe-engineering'
        subprocess.run(['git','merge-base','--is-ancestor','c6ebda06008c92e4141aa2d91991ac2c0328a1de','HEAD'],cwd=ROOT,check=True)
        record.update({'repository_head_before_preparation_commit':head,'branch':branch,'preserved_practice_commit':'c6ebda06008c92e4141aa2d91991ac2c0328a1de'})
        before=verify(a.archive,a.archive/'results/audit_revision/frozen-input-manifest.json');assert before['status']=='passed'
        save(out/'audit/e1-before.json',before)
        manifest_path=a.practice/'manifest.json'
        assert sha(manifest_path)=='ab5ee56a139e39e55dc8913534456ad535b1c28123e98e0ca2c242f899f68595'
        manifest=json.loads(manifest_path.read_text())
        for relative,digest in manifest['files'].items():
            target=(a.practice/relative).resolve()
            assert target.is_relative_to(a.practice.resolve()) and sha(target)==digest
        # Validate the prior delivery by byte hashes only; do not read practice wording/labels.
        old_inventory=json.loads((a.old_delivery.parent/'audit/delivery-directory-verification.json').read_text())
        assert all(sha(a.old_delivery/name)==v['sha256'] for name,v in old_inventory['files'].items())
        save(out/'audit/prior-practice-preservation.json',{'status':'passed','run_manifest_sha256':sha(manifest_path),'run_files_matched':len(manifest['files']),'prior_delivery_files_matched':len(old_inventory['files']),'scope':'streamed hashes only; no practice/model rerun'})
        provenance=ollama_provenance('http://127.0.0.1:11434','llama3.1:8b',10)
        assert provenance['digest']=='46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e' and provenance['ollama_version']=='0.34.0'
        packages={n:importlib.metadata.version(n) for n in ('numpy','scipy','torch','httpx','cryptography','pytest')}
        assert sys.version_info[:3]==(3,14,0)
        names=['feedctrl/__init__.py','feedctrl/controls.py','feedctrl/experiment2_controls.py','feedctrl/experiment2_evaluation.py','feedctrl/evaluation.py','feedctrl/model.py','scripts/run_experiment2.py','scripts/formal_e2_inference.py','scripts/prepare_formal_e2.py','scripts/verify_frozen_e1.py','docs/formal-e2-prospective-amendment.md','docs/experiment2-protocol.md','docs/experiment2-annotation-rubric.md']
        source_hashes={name:sha(ROOT/name) for name in names}
        for name in names:
            target=out/'source-candidate'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        worker_names=['scripts/formal_e2_inference.py','feedctrl/__init__.py','feedctrl/controls.py','feedctrl/experiment2_controls.py']
        for name in worker_names:
            target=out/'runner-candidate'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        save(out/'runner-candidate/trusted-custodian.TEMPLATE.json',{'study_id':None,'custodian_identity':None,'runner_sid':None,'public_key_b64':None,'opening_ledger':None,'private_inventory_sha256':None,'protected_roots':None})
        cats=[f'category_{i}' for i in range(31)]
        inputs=[a.archive/'data/processed.json']+[a.archive/f'results/models/seed_{seed}/{name}' for seed in (42,43,44) for name in ('model.pt','metadata.json')]
        lock={'status':'pre_exposure_candidate_lock_not_final_freeze','locked_utc':datetime.now(timezone.utc).isoformat(),'bank_bound_commitment':'not_created_no_fresh_bank','human_evidence':'not_created','role_configuration':'pending named custodian/eligibility decisions','python_executable':sys.executable,'python':sys.version,'packages':packages,'model_provenance':provenance,'literal_prompt':controls.COMPOUND_PROMPT,'schema':controls.compound_schema(cats),'categories':cats,'options':{'temperature':0,'seed':42,'num_ctx':4096,'num_predict':768,'num_thread':6,'timeout_seconds':600},'source_sha256':source_hashes,'ranking_inputs_sha256':{str(f):sha(f) for f in inputs},'inherited_analysis_candidate':{'bank_size':100,'classes':4,'per_class':25,'approval_of_remaining_design_fields':'not_inferred','checkpoint_seeds':[42,43,44],'request_seed':2026,'k':10,'bootstrap_resamples':5000,'BH_family_size':11,'induced_success_movement_threshold':1e-12,'prompt_validators_bands_ranking':'unchanged source; no outcome tuning'},'boundary':'Runner package has no references, ranking data or evaluator. Actual restricted OS SID, denied-read checks, real custodian key and signed release remain unconfigured. No claim of enforced isolation yet.'}
        save(out/'pre-exposure-source-runtime-lock.json',lock)
        approval={'recorded_utc':datetime.now(timezone.utc).isoformat(),'source':'user report in this chat','type':'user_reported_oral_supervisor_approval','reported_supervisor':'Borna Noureddin','reported_scope':'specific fresh-bank and annotation amendment','reported_statement':'I report that Borna has approved the specific fresh-bank and annotation amendment orally.','supervisor_approval_event_time':None,'written_receipt_seen':False,'independently_verified':False,'meaning':'Records the report accurately; does not invent custody, participants, choices, signatures, labels or approval date.'}
        save(out/'user-reported-oral-approval.json',approval)
        save(out/'templates/role-and-exposure-decision.TEMPLATE.json',{'template_only':True,'custodian_identity':None,'author_identity_and_AI_role':None,'independent_annotator_identity':None,'eligibility_and_prior_exposure':None,'adjudicator_identity':None,'reference_origin_decision':None,'bank_size_and_coverage_decision':None,'IAA_rule_and_consequence':None,'approval_report_source':'user-reported oral approval; not independently verified','attestations':None})
        csv=out/'templates/independent-pass.EMPTY.csv';csv.write_text('annotation_id,text,operation,directives_json,annotator,timestamp_utc\n',encoding='utf-8')
        after=verify(a.archive,a.archive/'results/audit_revision/frozen-input-manifest.json');assert after==before
        save(out/'audit/e1-after.json',after)
        record.update({'status':'prepared_pending_custodian_and_design_decisions','model_available':True,'model_inference_requests':0,'new_cases':0,'new_labels':0,'source_files_snapshotted':len(names),'practice_manifest_entries_preserved':len(manifest['files']),'frozen_e1_matched':after['matched'],'next_decision':'Name the fresh-bank custodian who will establish access, eligibility and reference-origin decisions before authoring.'})
    except Exception as error:
        record.update({'status':'failed_or_partial','error':f'{type(error).__name__}: {error}'})
    finally:
        record['completed_utc']=datetime.now(timezone.utc).isoformat();record['files']={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
        save(out/'preparation-receipt.json',record)
    print(json.dumps(record|{'files':len(record['files'])}))
    return 0 if record['status']=='prepared_pending_custodian_and_design_decisions' else 2
if __name__=='__main__':raise SystemExit(main())
