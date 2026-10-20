"""Protected scoring after immutable reference-free predictions; no parser calls."""
from __future__ import annotations
import argparse,hashlib,json,shutil,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from feedctrl import experiment2_evaluation as ev
from scripts.verify_frozen_e1 import verify

def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
    out=a.study/'evaluation';pred=a.study/'inference/run-01';release_path=a.study/'inference/worker-bundle/release.json'
    if out.exists():raise ValueError('New scoring output required')
    release=ev.read_json(release_path)
    # Verify the completed inventory before any reference file is opened.
    manifest=ev.read_json(pred/'manifest.json')
    if manifest['status']!='predictions_complete' or manifest['prediction_count']!=200:raise ValueError('200 committed terminal predictions required')
    for name,digest in manifest['files'].items():
        if ev.sha256_file(pred/name)!=digest:raise ValueError('Prediction evidence changed: '+name)
    q=ev.read_json(a.study/'inference/questions.json')['questions'];ids={r['id'] for r in q};texts={r['id']:r['text'] for r in q}
    outcomes=[ev.read_json(f) for f in sorted((pred/'predictions').glob('*.json'))]
    expected={(b,i) for b in ('rule_compound','ollama_compound') for i in ids}
    if len(outcomes)!=200 or {(r['backend'],r['id']) for r in outcomes}!=expected:raise ValueError('Prediction coverage')
    attempts=[ev.read_json(f) for f in sorted((pred/'attempts').glob('*.json'))]
    if len(attempts)!=200 or {(r['backend'],r['id']) for r in attempts}!=expected or any(r['text']!=texts[r['id']] for r in outcomes):raise ValueError('Attempt/text coverage')
    required={f'{folder}/{b}-{i}.json' for b,i in expected for folder in ('attempts','predictions')}
    if not required<={name.replace('\\','/') for name in manifest['files']}:raise ValueError('Prediction inventory lacks required evidence')
    out.mkdir();start=time.monotonic()
    status={'study_id':release['study_id'],'status':'started','started_utc':ev.utc_now(),'prediction_manifest_sha256':ev.sha256_file(pred/'manifest.json'),'scope':'AI-reference synthetic evaluation; not independent human validation'}
    ev.write_new_json(out/'predictions-committed-before-reference-join.json',status)
    try:
        before=verify(a.archive,a.archive/'results/audit_revision/frozen-input-manifest.json');ev.write_new_json(out/'e1-before.json',before)
        if before['status']!='passed':raise ValueError('E1 changed')
        # Final freeze pins every protected source/input; references enter only here.
        full=ev.read_json(a.study/'custody/full-freeze.json')
        for name,digest in full['files'].items():
            if ev.sha256_file(Path(name))!=digest:raise ValueError('Frozen evidence changed: '+name)
        cases=ev.read_json(a.study/'custody/final-cases.json');ev.validate_ranking_cases(cases)
        if {c['id'] for c in cases}!=ids or any(c['text']!=texts[c['id']] for c in cases):raise ValueError('Reference question mismatch')
        ev.write_new_json(out/'cases-with-final-ai-reference.json',cases)
        for r in outcomes:r['class']=next(c['class'] for c in cases if c['id']==r['id'])
        for r in outcomes:ev.write_new_json(out/'parse_cache'/f'{r["backend"]}-{r["id"]}.json',r)
        accuracy=ev.summarize_parser(outcomes,cases);ev.write_new_json(out/'parser-agreement-with-ai-reference.json',accuracy)
        ev.write_new_json(out/'parser-failures.json',[r for r in outcomes if r['error'] or ev.canonical(r['command'])!=ev.canonical(next(c['gold'] for c in cases if c['id']==r['id']))])
        print(json.dumps({'checkpoint':'parser_scored_after_prediction_commit','summary':accuracy}),flush=True)
        data=ev.read_json(a.archive/'data/processed.json');from feedctrl.model import load_model
        history_users={ev.fingerprint(u['train']+u['request_history']):u['user_id'] for u in data['users']}
        class RecordingModel:
            def __init__(self,seed):
                self.seed=seed;self.model=load_model(a.archive/f'results/models/seed_{seed}');self.metadata=self.model.metadata
            def score(self,history,item_ids):
                values=[float(v) for v in self.model.score(history,item_ids)];hh=ev.fingerprint(history);uid=history_users[hh]
                ev.write_new_json(out/'score_vectors'/f'{self.seed}-{uid}.json',{'seed':self.seed,'user_id':uid,'history_sha256':hh,'item_ids':item_ids,'scores':values,'score_sha256':ev.fingerprint(values)})
                return values
        models={seed:RecordingModel(seed) for seed in ev.SEEDS}
        rows,summary,requests,exclusions=ev.run_rankings(data,cases,outcomes,models,n_bootstrap=5000)
        summary.update({'study_id':release['study_id'],'reference_provenance':'Two separately contextualized AI annotations, locked before comparison; preserved AI adjudication if needed. Shared GPT family, no human ground truth.',
          'hypothesis_scope':'H1/H2 below are H1_AI/H2_AI in this prospective revision only; archived human-reference study not completed.'})
        ev.write_new_json(out/'ranking-rows.json',rows);ev.write_new_json(out/'assigned-requests.json',requests);ev.write_new_json(out/'excluded-user-classes.json',exclusions)
        ev.write_new_json(out/'ranking-summary.json',summary)
        after=verify(a.archive,a.archive/'results/audit_revision/frozen-input-manifest.json');ev.write_new_json(out/'e1-after.json',after)
        if after!=before:raise ValueError('E1 changed during scoring')
        for name,digest in full['files'].items():
            if ev.sha256_file(Path(name))!=digest:raise ValueError('Frozen source/input changed during scoring')
        status.update({'status':'ai_reference_evaluation_completed','parser':accuracy,'ranking_rows':len(rows),'assigned_requests':len(requests),'score_vectors':len(list((out/'score_vectors').glob('*.json')))})
    except Exception as exc:
        status.update({'status':'failed_or_incomplete','error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()});print(status['traceback'],file=sys.stderr)
    status.update({'completed_utc':ev.utc_now(),'wall_seconds':time.monotonic()-start,'files':{str(f.relative_to(out)):ev.sha256_file(f) for f in sorted(out.rglob('*')) if f.is_file()}})
    ev.write_new_json(out/'manifest.json',status)
    print(json.dumps(status|{'files':len(status['files'])}),flush=True)
    return 0 if status['status']=='ai_reference_evaluation_completed' else 2
if __name__=='__main__':raise SystemExit(main())
