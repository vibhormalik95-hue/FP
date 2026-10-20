"""Auditable KuaiRec ingestion and explicitly synthetic integration fixtures.

Only small_matrix.csv and item_categories.csv from the official archive are used.
Engagement is an offline proxy (watch_ratio > 2), not an observed like signal.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import random
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA_URL = 'https://zenodo.org/records/18164998/files/KuaiRec.zip'
PUBLISHER_MD5 = '261550d472c48eff4990fb13c0e5bcf7'


def file_hash(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_data(path):
    with Path(path).open(encoding='utf-8') as f:
        data = json.load(f)
    validate_data(data)
    return data


def validate_data(data):
    if not isinstance(data, dict) or not all(k in data for k in ('metadata', 'items', 'users')):
        raise ValueError('Dataset must contain metadata, items and users')
    items = [x['item_id'] for x in data['items']]
    if not items or len(items) != len(set(items)) or not all(isinstance(i, int) for i in items):
        raise ValueError('Item IDs must be unique integers, with a nonempty catalogue')
    catalogue = set(items)
    for item in data['items']:
        if not item['categories'] or not all(isinstance(c, str) and c for c in item['categories']):
            raise ValueError('Every item needs nonempty category strings')
    users = [u['user_id'] for u in data['users']]
    if not users or len(users) != len(set(users)):
        raise ValueError('User IDs must be unique and nonempty')
    for u in data['users']:
        for key, minimum in [('train', 3), ('request_history', 2), ('test', 1)]:
            if len(u.get(key, [])) < minimum or not set(u[key]) <= catalogue:
                raise ValueError(f'Invalid {key} for user {u["user_id"]}')
    return True


def save_data(data, output):
    validate_data(data)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return output


def download_kuairec(destination, url=DATA_URL):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix('.part')
        request = urllib.request.Request(url, headers={'User-Agent': 'FeedCtrl-Research/1.0'})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as f:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                f.write(chunk)
        temporary.replace(destination)
    actual = file_hash(destination, 'md5')
    if url == DATA_URL and actual != PUBLISHER_MD5:
        raise ValueError(f'Official archive checksum mismatch: {actual}; remove invalid archive and retry')
    return {'url': url, 'sha256': file_hash(destination), 'md5': actual,
            'publisher_md5_verified': url == DATA_URL and actual == PUBLISHER_MD5,
            'bytes': destination.stat().st_size}


def _csv_member(archive, basename):
    matches = [n for n in archive.namelist() if n.rsplit('/', 1)[-1] == basename and not n.startswith('__MACOSX/')]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one {basename}, found {len(matches)}')
    return csv.DictReader(io.TextIOWrapper(archive.open(matches[0]), encoding='utf-8-sig'))


def preprocess_kuairec(archive_path, output, max_users=256, cohort_seed=42,
                       train_fraction=.70, history_fraction=.15, positive_threshold=2.0):
    """Global timestamp quantiles, then positive-only sequences; no test-derived requests.

    All original small-matrix events determine time boundaries. The candidate catalogue
    is fixed by positive events strictly before the training cutoff. Selection uses
    hash order of eligible user IDs, never ranking/control outcomes. A max_users of 0
    means all eligible users. Only selected users' train sequences fit the model.
    """
    import numpy as np
    if max_users < 0 or not 0 < train_fraction < 1 or not 0 < history_fraction < 1 - train_fraction:
        raise ValueError('Invalid cohort size or split fractions')
    if not math.isfinite(positive_threshold) or positive_threshold < 0:
        raise ValueError('Threshold must be finite and nonnegative')
    provenance = download_kuairec(archive_path)
    timestamps = []
    missing_timestamp_events = 0
    with zipfile.ZipFile(archive_path) as z:
        for r in _csv_member(z, 'small_matrix.csv'):
            if not r['timestamp'].strip():
                missing_timestamp_events += 1
                continue
            t = float(r['timestamp'])
            if not math.isfinite(t):
                raise ValueError('Nonfinite timestamp')
            timestamps.append(t)
    total_events = len(timestamps) + missing_timestamp_events
    cuts = np.quantile(np.array(timestamps, dtype=np.float64), [train_fraction, train_fraction + history_fraction])
    del timestamps
    train_cut, history_cut = map(float, cuts)
    sequences = defaultdict(lambda: {'train': [], 'request_history': [], 'test': []})
    train_catalogue = set()
    positive_events = 0
    with zipfile.ZipFile(archive_path) as z:
        categories = {}
        for r in _csv_member(z, 'item_categories.csv'):
            # The official feat column is a JSON list of integer category IDs.
            raw = json.loads(r['feat'])
            if not isinstance(raw, list) or not raw or not all(isinstance(c, int) for c in raw):
                raise ValueError('Malformed or empty official category list; no category names are invented')
            categories[int(r['video_id'])] = [f'category_{c}' for c in sorted(set(raw))]
        for row_index, r in enumerate(_csv_member(z, 'small_matrix.csv')):
            if not r['timestamp'].strip():
                continue
            watch = float(r['watch_ratio'])
            if not math.isfinite(watch):
                raise ValueError('Nonfinite watch ratio')
            if watch <= positive_threshold:
                continue
            positive_events += 1
            t, uid, iid = float(r['timestamp']), int(r['user_id']), int(r['video_id'])
            if iid not in categories:
                raise ValueError(f'Missing item metadata for {iid}')
            period = 'train' if t < train_cut else 'request_history' if t < history_cut else 'test'
            sequences[uid][period].append((t, row_index, iid))
            if period == 'train':
                train_catalogue.add(iid)
    eligible = []
    split_ranges = {}
    filtered_cold_events = 0
    for uid, parts in sequences.items():
        user = {'user_id': uid}
        for period, events in parts.items():
            filtered_cold_events += sum(i not in train_catalogue for _, _, i in events)
            filtered = sorted(e for e in events if e[2] in train_catalogue)
            user[period] = [i for _, _, i in filtered]
        if len(user['train']) >= 3 and len(user['request_history']) >= 2 and len(user['test']) >= 1:
            eligible.append(user)
    eligible.sort(key=lambda u: hashlib.sha256(f'{cohort_seed}:{u["user_id"]}'.encode()).hexdigest())
    selected = eligible[:max_users] if max_users else eligible
    for period in ('train', 'request_history', 'test'):
        times = [t for u in selected for t, _, i in sequences[u['user_id']][period] if i in train_catalogue]
        split_ranges[period] = {'min': min(times), 'max': max(times)} if times else {}
    metadata = {
        'schema_version': 1, 'kind': 'kuairec',
        'study_status': 'executed exploratory pilot; not a confirmatory result',
        'source': provenance,
        'source_repository': 'https://github.com/chongminggao/KuaiRec',
        'input_table': 'small_matrix.csv', 'total_source_events': total_events,
        'excluded_missing_timestamp_events': missing_timestamp_events,
        'missing_timestamp_policy': 'Rows lacking timestamp/time/date are excluded; chronology is not imputed',
        'positive_events_before_catalogue_filter': positive_events,
        'positive_definition': f'watch_ratio > {positive_threshold:g}; engagement proxy, not observed like',
        'global_split': {'train_fraction': train_fraction, 'request_history_fraction': history_fraction,
                         'train_end_exclusive': train_cut, 'history_end_exclusive': history_cut,
                         'boundary_rule': 'quantiles over nonmissing source timestamps; ties assigned to later split',
                         'observed_time_ranges': split_ranges},
        'candidate_policy': 'Full catalogue of items with at least one positive event before global training cutoff; repeats allowed',
        'categories': 'Opaque official feat IDs; no invented semantic names',
        'minimum_lengths': {'train': 3, 'request_history': 2, 'test': 1},
        'selection': f'sha256({cohort_seed}:user_id) ascending among eligible users',
        'cohort_seed': cohort_seed, 'max_users': max_users, 'eligible_users': len(eligible),
        'selected_users': len(selected), 'candidate_items': len(train_catalogue),
        'dropped_postcutoff_cold_item_events': filtered_cold_events,
        'request_information': 'train + request_history only; test never supplied to request generator',
        'training_information': 'train sequences of selected users only; request_history is inference context, not fitting data',
        'split_event_counts': {p: sum(len(u[p]) for u in selected) for p in ('train', 'request_history', 'test')},
    }
    data = {'metadata': metadata, 'items': [{'item_id': i, 'categories': categories[i]} for i in sorted(train_catalogue)],
            'users': sorted(selected, key=lambda u: u['user_id'])}
    save_data(data, output)
    return data


def make_fixture(n_users=12, n_items=60, seed=42):
    """Deterministic synthetic fixture, NEVER scientific evidence."""
    if n_users < 1 or n_items < 12:
        raise ValueError('Fixture requires >=1 users and >=12 items')
    rng = random.Random(seed)
    items = [{'item_id': i, 'categories': [f'category_{i % 6}']} for i in range(1, n_items + 1)]
    users = []
    for uid in range(1, n_users + 1):
        seq = [rng.randint(1, n_items) for _ in range(40)]
        users.append({'user_id': uid, 'train': seq[:28], 'request_history': seq[28:34], 'test': seq[34:]})
    return {'metadata': {'schema_version': 1, 'kind': 'synthetic_fixture', 'source': 'deterministic generated fixture',
                         'seed': seed, 'study_status': 'software verification only; not KuaiRec evidence'},
            'items': items, 'users': users}
