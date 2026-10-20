"""Assemble reference-free release and final hash lock; no semantic case reads."""
import json,shutil,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.ai_e2_bank import save,sha
from scripts.ai_e2_inference_worker import SOURCE_PATHS,OPTIONS

def main():
    study=Path(sys.argv[1]);before=json.loads((study/'protocol/protocol-freeze.json').read_text())
    for name,digest in before['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Pre-authoring semantic/source baseline changed: '+name)
    for name,digest in before['input_sha256'].items():
        if sha(name)!=digest:raise ValueError('Pre-authoring ranking/screening input changed: '+name)
    ref=json.loads((study/'custody/reference-freeze.json').read_text())
    if ref['status']!='final_AI_references_frozen_before_inference' or ref['n']!=100 or ref['compatibility_status']!='all_100_final_canonical_labels_exactly_match_locked_subtype_and_target_roles':raise ValueError('Compatible final AI reference freeze required')
    fixed={'initial_lock':'initial-label-lock.json','comparison_lock':'comparison-lock.json','agreement':'agreement.json','disputes':'disputes.json'}
    for key,item in {**ref['source_hashes'],**ref['final_hashes']}.items():
        path=Path(item['path']) if 'path' in item else study/'custody'/fixed[key]
        if sha(path)!=item['sha256']:raise ValueError('Reference provenance byte commitment mismatch: '+key)
    if (study/'custody/references-aborted.json').exists():raise ValueError('Aborted references')
    bank=json.loads((study/'custody/bank-lock.json').read_text())
    if sha(study/'inference/questions.json')!=bank['inference_questions_sha256']:raise ValueError('Inference sheet differs from locked bank')
    if (study/'inference/opened.json').exists():raise ValueError('Study already opened; no refreeze or rerun')
    bundle=study/'inference/worker-bundle'
    if bundle.exists():raise ValueError('Bundle must be new')
    bundle.mkdir()
    for name in sorted(SOURCE_PATHS):
        dst=bundle/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dst)
    shutil.copy2(study/'inference/questions.json',bundle/'questions.json')
    timestamp=datetime.now(timezone.utc).isoformat()
    release={'study_id':before['study_id'],'status':'frozen_before_inference','frozen_utc':timestamp,
      'questions_sha256':sha(bundle/'questions.json'),'model':{k:before['ollama'][k] for k in ('model','digest','ollama_version')},
      'options':OPTIONS,'timeout_seconds':600,'worker_source_sha256':{name:sha(bundle/name) for name in sorted(SOURCE_PATHS)},
      'protocol_freeze_sha256':sha(study/'protocol/protocol-freeze.json'),'reference_freeze_sha256':sha(study/'custody/reference-freeze.json'),
      'denied_probe_paths':{'final_reference':str(study/'custody/final-cases.json'),'first_AI_labels':str(study/'annotations/tanishq/labels.json'),
          'second_AI_labels':str(study/'annotations/khushi/labels.json'),'intent_plan':str(study/'custody/intent-plan.json')}}
    save(bundle/'release.json',release)
    extra=['scripts/ai_e2_references.py','scripts/ai_e2_custody_restart.py','scripts/ai_e2_score.py','scripts/ai_e2_full_freeze.py','scripts/audit_ai_e2.py']
    paths=[ROOT/n for n in before['source_sha256']]+[Path(n) for n in before['input_sha256']]+[ROOT/n for n in extra]
    paths += [f for f in study.rglob('*') if f.is_file() and '__pycache__' not in f.parts]
    record={'study_id':before['study_id'],'status':'frozen_before_inference','frozen_utc':timestamp,
      'scope':'All initial/final AI reference and source/input evidence locked before any model parse; no claim of human gold.',
      'files':{str(f.resolve()):sha(f) for f in sorted(set(paths))},
      'immutable_pre_authoring_source_check':'passed all source and exclusion/ranking inputs unchanged',
      'late_wrappers':'Custody, release, independent audit and scoring IO wrappers finalized prospectively; original parser, ranking, metrics, prompts and thresholds unchanged.',
      'release_sha256':sha(bundle/'release.json'),'command':[sys.executable,*sys.argv]}
    save(study/'custody/full-freeze.json',record)
    print(json.dumps({'status':record['status'],'frozen_utc':timestamp,'files':len(record['files']),'full_freeze_sha256':sha(study/'custody/full-freeze.json'),'release_sha256':record['release_sha256']}))
if __name__=='__main__':main()
