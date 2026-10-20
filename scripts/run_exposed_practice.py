"""Separate exposed-practice diagnostic; reuses E2 components without changing them.

This is not the gated reserved study and cannot supply human annotations or H1/H2 evidence.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl import controls as legacy
from feedctrl import experiment2_controls as controls
from feedctrl import experiment2_evaluation as evaluation
from scripts.verify_frozen_e1 import verify

MODEL = 'llama3.1:8b'
DIGEST = '46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e'
OPTIONS = {'temperature': 0, 'seed': 42, 'num_ctx': 4096, 'num_predict': 768, 'num_thread': 6}

def save(path, value):
    evaluation.write_new_json(path, value)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists():
        raise ValueError('Output must be genuinely new; no overwrite or automatic retry')
    out.mkdir(parents=True)
    start = time.monotonic()
    status = {'started_utc': evaluation.utc_now(), 'scope': 'EXPOSED_PRACTICE_DIAGNOSTIC',
        'original_reserved_E2': 'not_run', 'H1': 'not_assessed', 'H2': 'not_assessed',
        'formal_H3': 'not_run', 'ranking_status': 'not_run', 'student_hours': 'not_recorded_by_this_run'}
    exit_code = 0
    try:
        before = verify(a.archive, a.archive / 'results/audit_revision/frozen-input-manifest.json')
        save(out / 'e1-before.json', before)
        if before['status'] != 'passed':
            raise ValueError('Frozen E1 mismatch')
        data_path = a.archive / 'data/processed.json'
        data = evaluation.read_json(data_path)
        categories = sorted({c for i in data['items'] for c in i['categories']}, key=evaluation.category_key)
        source = ROOT / 'deliverables/COMP9500-Worked-Practice-100-2026-10-11.csv'
        rows = list(csv.DictReader(source.open(encoding='utf-8-sig', newline='')))
        if len(rows) != 100 or len({r['annotation_id'] for r in rows}) != 100:
            raise ValueError('Expected 100 unique exposed practice questions')
        cases = []
        for r in rows:
            if r['practice_status'] != 'NON_HELD_OUT_PRACTICE_ONLY' or r['label_author'] != 'AI-generated worked example':
                raise ValueError('Reference provenance or practice status changed')
            gold = {'operation': r['operation'], 'directives': json.loads(r['directives_json'])}
            controls.validate_command(gold, categories)
            directives = gold['directives']
            label = ('compound' if len(directives) == 2 else 'conditional' if directives[0]['condition_category']
                     else 'floor' if directives[0]['floor'] == 1 else 'graded')
            cases.append({'id': r['annotation_id'], 'text': r['text'], 'class': label, 'gold': gold})
        evaluation.validate_ranking_cases(cases)
        provenance = legacy.ollama_provenance('http://127.0.0.1:11434', MODEL, 10)
        if provenance['digest'] != DIGEST or provenance['ollama_version'] != '0.34.0':
            raise ValueError('Prospectively selected runtime changed')
        sources = [Path(__file__), ROOT/'feedctrl/experiment2_controls.py', ROOT/'feedctrl/experiment2_evaluation.py',
                   ROOT/'feedctrl/controls.py', ROOT/'feedctrl/evaluation.py', ROOT/'feedctrl/model.py']
        inputs = [data_path, source, a.archive/'results/experiment2/parser-freeze-v2.json']
        inputs += [a.archive/f'results/models/seed_{s}/{n}' for s in evaluation.SEEDS for n in ('model.pt','metadata.json')]
        policy = {'committed_utc': evaluation.utc_now(), 'scope': status['scope'],
            'prospective_revision': 'Use the original Llama 3.1 8B digest and unchanged E2 prompt/schema with local Ollama 0.34.0 (historical runtime 0.34.4). Evaluate exposed practice against supplied AI reference labels, not the gated reserved study. Original protocol and receipt unchanged.',
            'reference_labels': 'AI-generated worked examples copied verbatim from the delivered CSV; not human or independent gold.',
            'label_timestamp_caveat': 'Original ai_generated_at_utc strings are preserved as supplied human-readable local-time strings, not independently authenticated timestamps.',
            'exposure': 'All 100 questions and reference answers were exposed before this run. No unseen-test, human IAA, or generalization claim.',
            'class_assignment': 'Derived from reference shape: two directives compound; otherwise condition conditional; otherwise floor=1 floor; otherwise graded.',
            'provenance': provenance, 'model': MODEL, 'digest': DIGEST, 'options': OPTIONS, 'timeout_seconds': 600,
            'prompt': controls.COMPOUND_PROMPT, 'schema': controls.compound_schema(categories),
            'parse_policy': 'Once per question/backend in CSV order; no retries, tuning, response repair, discarded failures, or rule substitution. Existing strict validation and grounding.',
            'ranking_policy': 'Existing assign_requests/run_rankings unchanged; frozen checkpoint seeds 42/43/44, request seed 2026; full catalogue; top 10; all four comparator conditions; error fallback recorded.',
            'metrics': 'Exact structured agreement with AI reference by class and pooled; operational failures in full denominator. Ranking induced success, intended movement, band satisfaction, HR@1, NDCG@10, floor violations; user means across seeds and 5000 user bootstrap resamples. Descriptive diagnostic only.',
            'source_sha256': {str(s): evaluation.sha256_file(s) for s in sources},
            'input_sha256': {str(s): evaluation.sha256_file(s) for s in inputs},
            'python': sys.version, 'packages': {n:importlib.metadata.version(n) for n in ('numpy','scipy','torch','httpx')},
            'command': [sys.executable, *sys.argv],
            'api_documentation_checked': ['https://docs.ollama.com/api/chat','https://docs.ollama.com/capabilities/structured-outputs']}
        save(out/'protocol-before-inference.json', policy)
        save(out/'cases-from-exposed-reference.json', cases)
        (out/'source_snapshot').mkdir()
        for i,s in enumerate(sources):
            shutil.copy2(s, out/'source_snapshot'/f'{i:02d}-{s.name}')
        shutil.copy2(source, out/source.name)
        print(json.dumps({'checkpoint':'protocol_saved_before_inference','model':MODEL,'digest':DIGEST,'cases':len(cases)}), flush=True)
        counter = 0
        def parser(text, cats, backend, **kwargs):
            nonlocal counter
            if backend == 'rule_compound':
                return controls.parse_control(text, cats, backend=backend)
            counter += 1
            evidence = {'started_utc':evaluation.utc_now(),'error':None}
            try:
                return controls.parse_control(text,cats,backend='ollama_compound',
                    model=MODEL,base_url='http://127.0.0.1:11434',timeout=600,
                    cache_dir=out/'raw_llm',seed=42,num_thread=6)
            except Exception as e:
                evidence['error'] = f'{type(e).__name__}: {e}'
                raise
            finally:
                evidence['completed_utc'] = evaluation.utc_now()
                save(out/'attempts'/f'{counter:03d}.json',evidence)
                if counter % 10 == 0 or counter == 1:
                    print(json.dumps({'checkpoint':'llm_attempts','count':counter,'latest_error':evidence['error']}),flush=True)
        outcomes = evaluation.parse_cases(cases,categories,out,{},parser=parser)
        accuracy = evaluation.summarize_parser(outcomes,cases)
        save(out/'parser-agreement-with-ai-reference.json',accuracy)
        save(out/'parser-failures.json',[r for r in outcomes if r['error'] or evaluation.canonical(r['command']) != evaluation.canonical(next(c['gold'] for c in cases if c['id']==r['id']))])
        print(json.dumps({'checkpoint':'parser_complete','agreement':accuracy}),flush=True)
        from feedctrl.model import load_model
        history_users = {evaluation.fingerprint(u['train']+u['request_history']): u['user_id'] for u in data['users']}
        class RecordingModel:
            def __init__(self, seed):
                self.seed = seed
                self.model = load_model(a.archive/f'results/models/seed_{seed}')
                self.metadata = self.model.metadata
            def score(self, history, item_ids):
                values = [float(v) for v in self.model.score(history,item_ids)]
                history_hash = evaluation.fingerprint(history)
                uid = history_users[history_hash]
                save(out/'score_vectors'/f'{self.seed}-{uid}.json', {
                    'seed':self.seed,'user_id':uid,'history_sha256':history_hash,
                    'item_ids':item_ids,'scores':values,'score_sha256':evaluation.fingerprint(values)})
                return values
        models = {seed: RecordingModel(seed) for seed in evaluation.SEEDS}
        print(json.dumps({'checkpoint':'ranking_started','checkpoint_seeds':list(models)}),flush=True)
        rankings, summary, requests, exclusions = evaluation.run_rankings(data,cases,outcomes,models,n_bootstrap=5000)
        save(out/'ranking-rows.json',rankings)
        save(out/'assigned-requests.json',requests)
        save(out/'excluded-user-classes.json',exclusions)
        # Preserve calculated contrasts but prevent their reuse as formal study decisions.
        summary['scope'] = status['scope']
        summary['reference_provenance'] = policy['reference_labels']
        summary['algorithmic_threshold_flags_not_formal_hypotheses'] = {k:summary.pop(k) for k in ('H1_passed','H2_passed','H1_status','H2_status') if k in summary}
        summary.update({'H1_status':'not_assessed','H2_status':'not_assessed','original_reserved_E2':'not_run'})
        save(out/'descriptive-ranking-summary.json',summary)
        status.update({'status':'practice_diagnostic_completed','ranking_status':'practice_only_completed',
            'parser_outcomes':len(outcomes),'ranking_rows':len(rankings),'assigned_requests':len(requests),'parser_agreement':accuracy})
        print(json.dumps({'checkpoint':'ranking_complete','rows':len(rankings),'requests':len(requests)}),flush=True)
        after = verify(a.archive,a.archive/'results/audit_revision/frozen-input-manifest.json')
        save(out/'e1-after.json',after)
        if after != before:
            raise ValueError('Frozen E1 verification changed')
        post = legacy.ollama_provenance('http://127.0.0.1:11434',MODEL,10)
        if post != provenance:
            raise ValueError('Runtime identity changed during execution')
        save(out/'runtime-after.json',post)
        changed = [str(s) for s in sources+inputs if evaluation.sha256_file(s) != {**policy['source_sha256'],**policy['input_sha256']}[str(s)]]
        if changed:
            raise ValueError(f'Frozen run input or source changed: {changed}')
    except Exception as e:
        exit_code = 1
        status.update({'status':'failed_or_incomplete','error':f'{type(e).__name__}: {e}','traceback':traceback.format_exc()})
        print(status['traceback'],file=sys.stderr,flush=True)
    status.update({'completed_utc':evaluation.utc_now(),'wall_seconds':time.monotonic()-start,'exit_code':exit_code})
    status['files'] = {str(f.relative_to(out)):evaluation.sha256_file(f) for f in sorted(out.rglob('*')) if f.is_file()}
    save(out/'manifest.json',status)
    print(json.dumps(status|{'files':f'{len(status["files"])} hashed files'}),flush=True)
    return exit_code

if __name__ == '__main__':
    raise SystemExit(main())
