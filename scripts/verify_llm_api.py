"""Run three genuine Ollama-backed API mutations against the real dataset/model.

Requires a running local Ollama server with the configured model. Existing
model-digest-keyed response caches are permitted and explicitly reported. No
parser/model mocks, rule fallback, synthetic data, or successful-result fixtures
are used. Exit status is nonzero on any failed check.

Example (run after other CPU-heavy experiments have finished):
    python scripts/with_ollama.py -- python scripts/verify_llm_api.py
See `python scripts/with_ollama.py --help` for this project's wrapper syntax.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='data/processed.json')
    parser.add_argument('--model-dir', default='results/models/seed_42')
    parser.add_argument('--output', default='results/verification/llm-api.json')
    parser.add_argument('--ollama-model', default=os.environ.get('FEEDCTRL_OLLAMA_MODEL', 'llama3.1:8b'))
    args = parser.parse_args()
    data_path = Path(args.data).resolve()
    model_path = Path(args.model_dir).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = {
        'started_at': utc_now(), 'status': 'running', 'checks': [], 'calls': [],
        'scope': 'Real processed dataset and trained SASRec; actual FastAPI routes with three Ollama-backed mutations.',
        'cache_policy': 'Uses the real Ollama client and live model-digest provenance checks. Valid existing response caches are allowed; no mocks or rule fallback.',
        'parser_model_requested': args.ollama_model,
        'backend_calls_planned': 3,
    }

    def write_report():
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def check(name, passed, **details):
        report['checks'].append({'name': name, 'status': 'passed' if passed else 'failed', **details})
        write_report()
        if not passed:
            raise AssertionError(f'{name}: {details}')
        print(f'PASS {name}', flush=True)

    try:
        check('Required dataset and model files exist', data_path.is_file() and (model_path / 'model.pt').is_file())
        report['dataset_sha256'] = sha256(data_path)
        report['checkpoint_sha256'] = sha256(model_path / 'model.pt')
        os.environ['FEEDCTRL_DATA'] = str(data_path)
        os.environ['FEEDCTRL_MODEL'] = str(model_path)
        os.environ['FEEDCTRL_OLLAMA_MODEL'] = args.ollama_model

        # Import only after setting configuration, because feedctrl.api exports app.
        from fastapi.testclient import TestClient
        from feedctrl.api import create_app

        app = create_app(data_path=data_path, model_path=model_path)
        with TestClient(app) as client:
            status = client.get('/api/status').json()
            report['environment'] = status
            check('App loads real processed data and trained model',
                  status['data_mode'] == 'processed dataset' and status['model_mode'] == 'trained model')
            all_users = client.get('/api/users').json()
            user_id = all_users[0]['user_id']
            report['user_id'] = user_id
            first = client.post('/api/session', json={})
            second = client.post('/api/session', json={})
            check('Independent sessions created', first.status_code == 201 and second.status_code == 201)
            headers = {'X-Session-ID': first.json()['session_id']}
            other_headers = {'X-Session-ID': second.json()['session_id']}

            def get_feed(condition='E', supplied_headers=None, supplied_user=None):
                response = client.get('/api/feed', params={
                    'user_id': user_id if supplied_user is None else supplied_user,
                    'condition': condition,
                }, headers=headers if supplied_headers is None else supplied_headers)
                if response.status_code != 200:
                    raise AssertionError(f'Feed response {response.status_code}: {response.text}')
                return response.json()

            def ids(feed):
                return [item['item_id'] for item in feed['items']]

            baseline = get_feed('C')
            baseline_ids = ids(baseline)
            other_baseline = get_feed('E', other_headers)
            second_user = all_users[1]['user_id'] if len(all_users) > 1 else None
            second_user_baseline = get_feed('E', supplied_user=second_user) if second_user is not None else None
            neutral_text = baseline['profile_text']
            check('Initial profile contains only bounded grounded history context',
                  not baseline['profile'] and 'observed interaction history' in neutral_text
                  and len(neutral_text.split()) <= 200)

            # Choose a supported category whose fixed +0.25 boost has an observable
            # top-10 effect. This is API acceptance input selection, never test-label
            # selection or an empirical treatment-effect estimate.
            demo = app.state.demo
            user = demo.users[user_id]
            history = list(user['train']) + list(user['request_history'])
            catalog = sorted(demo.items)
            raw_scores = list(map(float, demo.model.score(history, catalog)))
            low, high = min(raw_scores), max(raw_scores)
            normalized = {i: ((s-low)/(high-low) if high > low else 0.0)
                          for i, s in zip(catalog, raw_scores)}
            expected_base = sorted(catalog, key=lambda i: (-normalized[i], i))[:10]
            check('API baseline matches the actual frozen scorer', baseline_ids == expected_base,
                  shown_item_ids=baseline_ids)
            selected = None
            for category in demo.categories:
                boosted_order = sorted(catalog, key=lambda i: (-(normalized[i] + (.25 if category in demo.items[i] else 0)), i))[:10]
                old_count = sum(category in demo.items[i] for i in baseline_ids)
                new_count = sum(category in demo.items[i] for i in boosted_order)
                if boosted_order != baseline_ids and new_count > old_count:
                    selected = (category, boosted_order, old_count, new_count)
                    break
            check('A category with observable boost response exists', selected is not None)
            category, expected_boost, before_exposure, after_exposure = selected
            report['target_category'] = category
            report['target_selection'] = 'First supported category whose fixed policy increases top-10 inclusion; uses frozen scores and item metadata only, never held-out labels.'

            cache_dir = Path(os.environ.get('FEEDCTRL_PARSER_CACHE', 'results/parser_cache'))

            def llm_call(endpoint, body, label):
                existing = {p.name for p in cache_dir.glob('*.json')}
                call_start = time.monotonic()
                response = client.post(endpoint, headers=headers, json={**body, 'user_id': user_id, 'backend': 'ollama'})
                created = sorted({p.name for p in cache_dir.glob('*.json')} - existing)
                try:
                    response_body = response.json()
                except ValueError:
                    response_body = {'non_json_response': response.text[:1000]}
                report['calls'].append({
                    'label': label, 'endpoint': endpoint, 'text': body['text'],
                    'http_status': response.status_code, 'response': response_body,
                    'wall_seconds': time.monotonic() - call_start,
                    'new_cache_files_during_call': created,
                    'cache_observation': 'No new file observed; existing validated response cache may have been used.' if not created else 'New response cache file(s) observed during this call.',
                })
                write_report()
                check(f'{label} completes through the actual Ollama API route', response.status_code == 200,
                      http_status=response.status_code, response=response_body)
                return response_body

            boost = llm_call('/api/control', {'text': f'Show me more {category}.'}, 'boost')
            command = boost.get('command', {})
            check('Boost is applied with Ollama provenance and exact intent',
                  boost.get('applied') is True and command.get('operation') == 'boost'
                  and command.get('category') == category and command.get('strength') == .25
                  and command.get('source', '').startswith('ollama:'))
            boosted = get_feed('C')
            check('Ollama boost changes the real ranking according to the fixed policy',
                  ids(boosted) == expected_boost and ids(boosted) != baseline_ids,
                  before_item_ids=baseline_ids, after_item_ids=ids(boosted),
                  target_count_before=before_exposure, target_count_after=after_exposure)

            mute = llm_call('/api/control', {'text': f'Mute {category}.'}, 'mute')
            command = mute.get('command', {})
            check('Mute is applied with Ollama provenance and exact intent',
                  mute.get('applied') is True and command.get('operation') == 'mute'
                  and command.get('category') == category and command.get('source', '').startswith('ollama:'))
            muted = get_feed('C')
            expected_mute = [i for i in sorted(catalog, key=lambda i: (-normalized[i], i)) if category not in demo.items[i]][:10]
            check('Ollama mute removes the target category without forbidden padding',
                  ids(muted) == expected_mute and all(category not in i['categories'] for i in muted['items']),
                  shown_item_ids=ids(muted), fill_rate=muted['fill_rate'])

            text = neutral_text + f'\nShow me more {category}.'
            check('Natural-language profile is at most 200 words', len(text.split()) <= 200,
                  words=len(text.split()))
            profile = llm_call('/api/profile/text', {'text': text}, 'profile')
            check('Profile ignores neutral history and applies only the explicit preference',
                  profile.get('applied') is True and profile.get('operation') == 'set'
                  and profile.get('profile') == {category: .25}
                  and profile.get('source', '').startswith('ollama:'))
            profile_feed = get_feed('D')
            check('Same-intent Ollama profile and control yield the same ranking',
                  ids(profile_feed) == ids(boosted) and profile_feed['profile_text'] == text,
                  profile_item_ids=ids(profile_feed))
            combined = get_feed('E')
            check('Existing mute command overrides conflicting profile boost in E',
                  ids(combined) == expected_mute)
            check('Actual LLM mutations remain isolated to their session',
                  get_feed('E', other_headers) == other_baseline)
            if second_user is not None:
                check('Actual LLM mutations remain isolated to their user',
                      get_feed('E', supplied_user=second_user) == second_user_baseline)
            reset = client.post('/api/reset', headers=headers, json={'user_id': user_id})
            restored = get_feed('E')
            check('Reset clears LLM controls and restores baseline',
                  reset.status_code == 200 and ids(restored) == baseline_ids
                  and not restored['profile'] and restored['command']['operation'] == 'clarify'
                  and restored['profile_text'] == neutral_text and restored['feedback_count'] == 0)
            check('Exactly three actual Ollama-backed API mutations were used', len(report['calls']) == 3)

        report['status'] = 'passed'
        report['finished_at'] = utc_now()
        report['wall_seconds'] = time.monotonic() - started
        write_report()
        print(json.dumps({'status': report['status'], 'checks': len(report['checks']), 'output': str(output)}, indent=2), flush=True)
        return 0
    except Exception as exc:
        report['status'] = 'failed'
        report['finished_at'] = utc_now()
        report['wall_seconds'] = time.monotonic() - started
        report['failure'] = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
        write_report()
        print(json.dumps({'status': 'failed', 'error': str(exc), 'output': str(output)}, indent=2), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
