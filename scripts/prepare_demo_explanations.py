"""Prepare model-selected explanations for the declared A-E worked cases.

This prepares exposed prototype artifacts. It is not a language benchmark or
human-intent evaluation. Use a new Experiment2 output directory every time.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl.explanations import cached_explanation, generate_explanation, EXPLANATION_PROMPT
from scripts.output_safety import project_path, require_new_output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True)
    parser.add_argument('--reference-cache', required=True)
    parser.add_argument('--examples', default='deliverables/2026-10-27-feedback/demo-example-receipt.json')
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', default='llama3.1:8b')
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 180:
        parser.error('Use a timeout in (0, 180] seconds')
    output = require_new_output(args.output, ROOT, directory=True)
    if output.exists():
        parser.error('Output already exists; choose a new prototype directory')
    if not output.is_relative_to((ROOT / 'results/experiment2').resolve()):
        parser.error('Prototype output must be a new directory under results/experiment2')
    data_path = project_path(args.data, ROOT)
    reference_path = project_path(args.reference_cache, ROOT)
    examples_path = project_path(args.examples, ROOT)
    data = json.loads(data_path.read_text(encoding='utf-8'))
    examples = json.loads(examples_path.read_text(encoding='utf-8'))
    user_id = examples['user_id']
    user = next(u for u in data['users'] if u['user_id'] == user_id)
    history = user['train'] + user['request_history']
    categories = {i['item_id']: i['categories'] for i in data['items']}
    items = set(examples['baseline_history_only_top10'])
    for case in examples['conditions'].values():
        items.update(case['top10'])
    items.update(examples['mute_category_28_C']['top10'])
    items.update(examples['conflict_E_explicit_mute_profile_boost_category_1']['top10'])
    if not 1 <= len(items) <= 50 or not items <= categories.keys():
        parser.error('Worked cases must name at most fifty existing catalogue items')
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'user_id': user_id,
        'scope': 'Exposed worked-case prototype cache, not a new experiment or benchmark',
        'data_sha256': sha(data_path), 'examples_sha256': sha(examples_path),
        'reference_cache_sha256': sha(reference_path), 'model': args.model,
        'prompt_sha256': hashlib.sha256(EXPLANATION_PROMPT.encode()).hexdigest(),
        'item_ids': sorted(items), 'facts_split': 'Training plus request history only'}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    records, errors, reused = [], [], 0
    for item in sorted(items):
        try:
            record = cached_explanation(item, categories[item], history, categories, index_path=reference_path)
            if record['source'] == 'ollama_constrained_fact_selection':
                reused += 1
            else:
                record = generate_explanation(item, categories[item], history, categories, backend='ollama',
                    model=args.model, timeout=args.timeout, cache_dir=output / 'responses')
            records.append(record)
        except Exception as error:
            errors.append({'item_id': item, 'type': type(error).__name__, 'message': str(error)})
        result = {'user_id': user_id, 'explanations': records, 'errors': errors, 'status': 'in_progress',
                  'reused_records': reused, 'new_model_records': len(records)-reused}
        (output / 'index.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    result['status'] = 'partial' if errors else 'complete'
    result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (output / 'index.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    assert sha(reference_path) == manifest['reference_cache_sha256']
    print(json.dumps({k: result[k] for k in ('status','reused_records','new_model_records','errors')}))
    return 2 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
