"""Pre-authoring source/protocol lock; hashes existing evidence without inference."""
import hashlib,importlib.metadata,json,os,platform,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.verify_frozen_e1 import verify
from feedctrl.controls import ollama_provenance
from scripts.ai_e2_bank import save,sha

def main():
    study=Path(sys.argv[1]);archive=Path(sys.argv[2])
    review=study/'audit/protocol-review-before-authoring.json'
    if not review.exists():raise ValueError('Independent protocol review required')
    # Reviewer status is inspected independently by coordinator before invocation.
    if (study/'protocol/protocol-freeze.json').exists():raise ValueError('Already frozen')
    sources=['docs/ai-reference-e2-protocol-2026-10-14.md','docs/ai-reference-e2-rubric-2026-10-14.md','docs/ai-reference-e2-role-prompts-2026-10-14.json',
      'scripts/ai_e2_bank.py','scripts/ai_e2_inference_worker.py','scripts/test_ai_e2_boundary.py','scripts/ai_e2_protocol_freeze.py',
      'feedctrl/__init__.py','feedctrl/controls.py','feedctrl/experiment2_controls.py','feedctrl/experiment2_evaluation.py','feedctrl/evaluation.py','feedctrl/model.py']
    inputs=[ROOT/'deliverables/COMP9500-Worked-Practice-100-2026-10-11.csv',archive/'results/experiment2/language-v2/dev.jsonl',archive/'data/processed.json']
    inputs += [archive/f'results/models/seed_{s}/{n}' for s in (42,43,44) for n in ('model.pt','metadata.json')]
    before=verify(archive,archive/'results/audit_revision/frozen-input-manifest.json')
    if before['status']!='passed':raise ValueError('E1 preservation failed')
    save(study/'audit/e1-before-authoring.json',before)
    boundary=subprocess.run([sys.executable,str(ROOT/'scripts/test_ai_e2_boundary.py')],capture_output=True,text=True,check=True)
    save(study/'audit/no-case-boundary-preflight.json',json.loads(boundary.stdout))
    provenance=ollama_provenance('http://127.0.0.1:11434','llama3.1:8b',10)
    if provenance['digest']!='46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e' or provenance['ollama_version']!='0.34.0':raise ValueError('Model identity changed')
    snapshot=study/'protocol/source';snapshot.mkdir()
    for name in sources:
        target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for name in sources[:3]:shutil.copy2(ROOT/name,study/'protocol'/Path(name).name)
    prompts=json.loads((ROOT/sources[2]).read_text())
    author_brief={'study_id':'AIREF-E2-20261014-v1','role_prompt':prompts['author'],
      'intent_definitions':{'compound':'Moderately increase target; moderately reduce secondary independently.','slight_boost':'Slightly increase target.','strong_reduction':'Strongly reduce target without requiring total exclusion.','exclusion':'Exclude target completely.','floor':'Reduce target moderately but retain at least one item.','conditional':'Moderately increase target only on individual items also carrying secondary; do not change other items.'},
      'output_format':[{'id':'exact assigned opaque ID','candidates':['first natural text','second natural text','third natural text']}],
      'context_separation':'Read this brief and assigned round plan only. No references, software, old questions or predictions.'}
    save(study/'authoring/authoring-brief.json',author_brief)
    old=Path(r'C:\Users\vs981\Documents\COMP9500\2026-10-14\evaluation-llama31-practice-01\manifest.json')
    if sha(old)!='ab5ee56a139e39e55dc8913534456ad535b1c28123e98e0ca2c242f899f68595':raise ValueError('Practice evidence manifest changed')
    record={'study_id':'AIREF-E2-20261014-v1','status':'protocol_frozen_before_authoring','frozen_utc':datetime.now(timezone.utc).isoformat(),
      'computer':os.environ['COMPUTERNAME'],'python_executable':sys.executable,'python':sys.version,'platform':platform.platform(),
      'packages':{n:importlib.metadata.version(n) for n in ('numpy','scipy','torch','httpx')},'ollama':provenance,
      'source_sha256':{name:sha(ROOT/name) for name in sources},'input_sha256':{str(p):sha(p) for p in inputs},
      'independent_protocol_review_sha256':sha(review),'boundary_preflight_sha256':sha(study/'audit/no-case-boundary-preflight.json'),
      'agent_model_identity_sha256':sha(study/'audit/agent-model-identity-before-authoring.json'),
      'author_brief_sha256':sha(study/'authoring/authoring-brief.json'),'practice_manifest_sha256':sha(old),
      'e1':before,'existing_practice_commit':'c6ebda06008c92e4141aa2d91991ac2c0328a1de',
      'approval':'User reports Borna approved revised AI approach; not independently verified or written receipt.',
      'command':[sys.executable,*sys.argv]}
    save(study/'protocol/protocol-freeze.json',record)
    print(json.dumps({'status':record['status'],'utc':record['frozen_utc'],'protocol_freeze_sha256':sha(study/'protocol/protocol-freeze.json'),'e1':before}))
if __name__=='__main__':main()
