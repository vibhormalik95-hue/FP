"""Post-freeze diagnostics; never tune hyperparameters on this test report."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl.data import load_data
from feedctrl.model import load_model
from scripts.output_safety import project_path, require_new_output


def assess(data, scorer):
    ids = [i['item_id'] for i in data['items']]
    first_hit = any_hit = 0
    predictions = Counter()
    for user in data['users']:
        scores = scorer(user['train'] + user['request_history'], ids)
        top = min(zip(ids, scores), key=lambda p: (-p[1], p[0]))[0]
        predictions[top] += 1
        first_hit += top == user['test'][0]
        any_hit += top in user['test']
    n = len(data['users'])
    return {'users': n, 'hr_at_1_next_positive': first_hit / n, 'hr_at_1_any_future_positive': any_hit / n,
            'next_positive_hits': first_hit, 'any_positive_hits': any_hit,
            'distinct_top1_items': len(predictions), 'largest_top1_prediction_share': max(predictions.values()) / n}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', default='data/processed.json')
    p.add_argument('--models', default='results/models')
    p.add_argument('--seeds', nargs='+', type=int, default=[42, 43, 44])
    p.add_argument('--output', default='results/reproduction-base-quality.json')
    a = p.parse_args()
    try:
        out = require_new_output(a.output, ROOT, directory=False)
    except ValueError as exc:
        p.error(str(exc))
    data_path = project_path(a.data, ROOT)
    data = load_data(data_path)
    popularity = Counter(i for u in data['users'] for i in u['train'])
    report = {'scope': 'Post-freeze descriptive backbone diagnosis; no tuning on these test outcomes',
              'data_sha256': hashlib.sha256(data_path.read_bytes()).hexdigest(),
              'relevance_definition': data['metadata']['positive_definition'],
              'denominator': 'all retained users; no seen-item exclusion; full fixed candidate catalogue',
              'popularity_train_only': assess(data, lambda history, ids: [popularity[i] for i in ids]),
              'sasrec': {}}
    for seed in a.seeds:
        model = load_model(project_path(a.models, ROOT) / f'seed_{seed}')
        report['sasrec'][str(seed)] = assess(data, model.score)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
