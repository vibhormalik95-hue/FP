"""Post-hoc baseline and artifact checks; never fits models or changes frozen evidence.

Run from any directory with this project's Python environment. Outputs are separate
from the original experiment. Recent popularity pools later pre-test observations;
its comparison with train-fitted SASRec is descriptive, not an information-matched
test of model quality. All rankings retain the original full candidate catalogue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feedctrl.data import load_data
from feedctrl.explanations import EXPLANATION_PROMPT, verified_facts
from feedctrl.model import load_model


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rank_candidates(ids, scores):
    """Stable tie-break by item ID, independently of catalogue input order."""
    if len(ids) != len(scores) or len(ids) != len(set(ids)):
        raise ValueError('Scores must match unique candidates')
    if not all(math.isfinite(score) for score in scores):
        raise ValueError('Scores must be finite')
    return [item for item, score in sorted(zip(ids, scores), key=lambda pair: (-pair[1], pair[0]))]


def popularity_scores(data, period, ids):
    if period not in ('train', 'request_history'):
        raise ValueError('Popularity may use only pre-test periods')
    counts = Counter(item for user in data['users'] for item in user[period])
    return [counts[item] for item in ids]


def assess(data, scorer, k=10):
    ids = sorted(item['item_id'] for item in data['items'])
    if not 1 <= k <= len(ids):
        raise ValueError('Invalid K for catalogue')
    hits1 = hitsk = 0
    discounted = []
    top1 = Counter()
    topk_seen = 0
    rankings_digest = hashlib.sha256()
    for user in sorted(data['users'], key=lambda row: row['user_id']):
        history = user['train'] + user['request_history']
        ranking = rank_candidates(ids, scorer(history, ids))
        top = ranking[:k]
        target = user['test'][0]
        hits1 += top[0] == target
        hitsk += target in top
        discounted.append(1 / math.log2(top.index(target) + 2) if target in top else 0.0)
        top1[top[0]] += 1
        topk_seen += len(set(top) & set(history))
        rankings_digest.update(json.dumps([user['user_id'], top], separators=(',', ':')).encode() + b'\n')
    n = len(data['users'])
    return {'users': n, 'hr1': hits1 / n, 'hr10': hitsk / n,
            'ndcg10': math.fsum(discounted) / n, 'hits1': hits1, 'hits10': hitsk,
            'distinct_top1_items': len(top1), 'largest_top1_prediction_share': max(top1.values()) / n,
            'mean_seen_items_in_top10': topk_seen / n,
            'user_top10_sha256': rankings_digest.hexdigest()}


def uniform_expectation(candidate_count, k=10):
    if not 1 <= k <= candidate_count:
        raise ValueError('Invalid K for catalogue')
    return {'hr1': 1 / candidate_count, 'hr10': k / candidate_count,
            'ndcg10': math.fsum(1 / math.log2(rank + 1) for rank in range(1, k + 1)) / candidate_count,
            'method': 'Exact expectation under uniform random permutations without replacement; no sampled run',
            'relevance': 'One relevant item: the first retained test positive'}


def sequence_checks(data):
    return {
        'users_with_repeated_train_items': sum(len(u['train']) != len(set(u['train'])) for u in data['users']),
        'users_with_repeated_visible_history_items': sum(
            len(u['train'] + u['request_history']) != len(set(u['train'] + u['request_history']))
            for u in data['users']),
        'users_with_first_test_item_seen_in_visible_history': sum(
            u['test'][0] in set(u['train'] + u['request_history']) for u in data['users']),
        'users_with_any_test_item_seen_in_visible_history': sum(
            bool(set(u['test']) & set(u['train'] + u['request_history'])) for u in data['users']),
        'interpretation': 'These are properties of the retained positive-event dataset, not all source viewing events. '
                          'The frozen full-catalogue policy permits seen-item recommendations even when targets are unseen.'}


def explanation_checks(data, path, input_hashes):
    index = json.loads(path.read_text(encoding='utf-8'))
    user = next(u for u in data['users'] if u['user_id'] == index['user_id'])
    history = user['train'] + user['request_history']
    categories = {item['item_id']: item['categories'] for item in data['items']}
    if index['prompt_sha256'] != hashlib.sha256(EXPLANATION_PROMPT.encode()).hexdigest():
        raise ValueError('Explanation prompt provenance mismatch')
    records = []
    for record in index['explanations']:
        item = record['item_id']
        facts = verified_facts(item, categories[item], history, categories)
        signal = hashlib.sha256(json.dumps({'item_id': item, 'facts': facts}, sort_keys=True).encode()).hexdigest()
        cache_path = path.parent / 'explanation_cache' / (record['cache_key'] + '.json')
        input_hashes[cache_path] = sha256(cache_path)
        cache = json.loads(cache_path.read_text(encoding='utf-8'))
        cache_key = hashlib.sha256(json.dumps({'provenance': cache['provenance'], 'payload': cache['payload']},
                                             sort_keys=True).encode()).hexdigest()
        response = json.loads(cache['response']['message']['content'])
        if (record['source'] != 'ollama_constrained_fact_selection' or facts != record['allowed_statements']
                or signal != record['signal_key'] or record['cache_key'] != cache_key
                or cache['key'] != cache_key or cache['provenance'] != record['provenance']
                or list(dict.fromkeys(response['statements'])) != record['statements']):
            raise ValueError(f'Explanation provenance mismatch for item {item}')
        records.append({'item_id': item, 'matches_first_three_facts': record['statements'] == facts[:3],
                        'matches_template_text': record['text'] == ' '.join(facts[:3]),
                        'cache_sha256': input_hashes[cache_path]})
    return {'user_id': user['user_id'], 'records': len(records),
            'matches_first_three_facts': sum(r['matches_first_three_facts'] for r in records),
            'matches_template_text': sum(r['matches_template_text'] for r in records), 'items': records,
            'interpretation': 'Observed equality for this ten-card cache, not a fresh LLM run, broad equivalence claim, '
                              'or evidence that the recorded LLM executions did not occur.'}


def markdown(report):
    lines = ['# Supplemental baseline and artifact audit', '',
             'Post-hoc descriptive analysis of unchanged frozen data and checkpoints. No training, parser inference, '
             'request regeneration, candidate changes, or hyperparameter selection was performed.', '',
             '| Method | HR@1 | HR@10 | NDCG@10 |', '|---|---:|---:|---:|']
    rows = [('Training-window popularity', report['popularity_train_only']),
            ('Request-history-window popularity', report['popularity_request_history_only']),
            ('Uniform random (exact expectation)', report['uniform_random_expectation'])]
    rows.extend((f'SASRec seed {seed}', metrics) for seed, metrics in report['sasrec'].items())
    for name, metrics in rows:
        lines.append(f"| {name} | {metrics['hr1']:.8f} | {metrics['hr10']:.8f} | {metrics['ndcg10']:.8f} |")
    lines.extend(['', report['information_access_caveat'], '',
                  'Every method uses the same full catalogue and first retained test positive per user. '
                  'Scores are unmodified baseline scores, without A’s item-feedback adjustment. '
                  'Ties resolve by ascending item ID. Random values are mathematical expectations, not observations.', '',
                  f"Sequence checks: {report['sequence_checks']['users_with_repeated_train_items']} users have repeated "
                  'training positives; '
                  f"{report['sequence_checks']['users_with_repeated_visible_history_items']} have repeated visible-history "
                  'positives; '
                  f"{report['sequence_checks']['users_with_any_test_item_seen_in_visible_history']} have any retained test "
                  'positive already in their visible positive history. This does not describe all source viewing events.', '',
                  f"All {report['explanation_checks']['records']} explanation records were checked against their archived "
                  f"responses and recomputed facts; {report['explanation_checks']['matches_first_three_facts']} select exactly "
                  'the template’s first three facts. No LLM benefit is observed for those examples.', '',
                  'Dataset, checkpoint, training-sequence, archived metric, and explanation-cache provenance was checked. '
                  'Input file hashes remained unchanged. Full values, cutoffs, environment and hashes are in `baselines.json`.', '',
                  'Reproduce: `python scripts/benchmark_revision.py` using the project environment. This loads the saved '
                  'checkpoints and writes only the supplemental JSON and this Markdown report.', ''])
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/processed.json')
    parser.add_argument('--models', type=Path, default=ROOT / 'results/models')
    parser.add_argument('--recorded-baseline', type=Path, default=ROOT / 'results/base-quality.json')
    parser.add_argument('--explanations', type=Path, default=ROOT / 'results/explanations.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/audit_revision/baselines.json')
    args = parser.parse_args(argv)
    data = load_data(args.data)
    prior = json.loads(args.recorded_baseline.read_text(encoding='utf-8'))
    input_hashes = {p: sha256(p) for p in (args.data, args.recorded_baseline, args.explanations)}
    if input_hashes[args.data] != prior['data_sha256']:
        raise ValueError('Dataset differs from recorded baseline provenance')
    train_payload = [{'user_id': u['user_id'], 'train': u['train']} for u in data['users']]
    train_hash = hashlib.sha256(json.dumps(train_payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    report = {'schema_version': 1, 'analysis_status': 'post-hoc descriptive supplement; frozen inputs unchanged',
              'users': len(data['users']), 'candidate_items': len(data['items']), 'k': 10,
              'relevance': 'First retained test positive per user; one relevant item; IDCG@10 = 1',
              'candidate_policy': data['metadata']['candidate_policy'],
              'global_split': data['metadata']['global_split'],
              'information_access_caveat': 'SASRec weights were fitted only on training-window interactions, but '
                  'inference uses each user\'s own training plus request history. Recent popularity pools all retained '
                  'users\' later request-history-window interactions. Both precede the test cutoff; the recency and '
                  'pooled information differ. This is a post-hoc descriptive baseline, not a controlled, '
                  'information-matched comparison or evidence of model-class superiority.',
              'data_sha256': input_hashes[args.data], 'train_sequence_sha256': train_hash,
              'uniform_random_expectation': uniform_expectation(len(data['items'])), 'sasrec': {},
              'checkpoint_provenance': {}, 'sequence_checks': sequence_checks(data)}
    for period, label in [('train', 'popularity_train_only'), ('request_history', 'popularity_request_history_only')]:
        counts = dict(zip([i['item_id'] for i in data['items']],
                          popularity_scores(data, period, [i['item_id'] for i in data['items']])))
        report[label] = assess(data, lambda history, ids: [counts[i] for i in ids])
    if report['popularity_train_only']['hr1'] != prior['popularity_train_only']['hr_at_1_next_positive']:
        raise ValueError('Training popularity does not reproduce archived metric')
    for seed in (42, 43, 44):
        directory = args.models / f'seed_{seed}'
        for path in (directory / 'model.pt', directory / 'metadata.json'):
            input_hashes[path] = sha256(path)
        metadata = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
        if (metadata['train_sequence_sha256'] != train_hash or metadata['seed'] != seed
                or metadata['checkpoint_sha256'] != input_hashes[directory / 'model.pt']):
            raise ValueError(f'Checkpoint provenance mismatch for seed {seed}')
        model = load_model(directory)
        if set(model.mapping) != {item['item_id'] for item in data['items']}:
            raise ValueError('Checkpoint candidate mapping differs')
        metrics = assess(data, model.score)
        recorded = prior['sasrec'][str(seed)]
        if (metrics['hr1'] != recorded['hr_at_1_next_positive']
                or metrics['distinct_top1_items'] != recorded['distinct_top1_items']
                or metrics['largest_top1_prediction_share'] != recorded['largest_top1_prediction_share']):
            raise ValueError(f'Checkpoint replay does not reproduce archived HR@1/top1 concentration for seed {seed}')
        report['sasrec'][str(seed)] = metrics
        report['checkpoint_provenance'][str(seed)] = {
            'sha256': input_hashes[directory / 'model.pt'], 'training_torch_version': metadata['torch_version'],
            'training_scope': metadata['training_scope'], 'recorded_hr1_reproduced': True}
        print(f'Seed {seed}: HR1={metrics["hr1"]:.8f}; HR10={metrics["hr10"]:.8f}; NDCG10={metrics["ndcg10"]:.8f}', flush=True)
    report['explanation_checks'] = explanation_checks(data, args.explanations, input_hashes)
    import torch
    report['execution_environment'] = {'python': platform.python_version(), 'torch': torch.__version__,
                                       'platform': platform.platform(), 'device': 'cpu', 'threads': torch.get_num_threads()}
    report['inputs_unchanged'] = all(sha256(path) == digest for path, digest in input_hashes.items())
    if not report['inputs_unchanged']:
        raise ValueError('An input changed during the audit')
    report['input_sha256'] = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): v
                              for p, v in input_hashes.items()}
    report['analysis_script_sha256'] = sha256(Path(__file__))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    args.output.with_suffix('.md').write_text(markdown(report), encoding='utf-8')
    print(f'Wrote {args.output}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
