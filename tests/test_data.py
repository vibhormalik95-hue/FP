import hashlib
import json
import zipfile
import pytest
from feedctrl.data import make_fixture, save_data, load_data, validate_data, file_hash


def test_fixture_is_deterministic_and_labeled():
    assert make_fixture() == make_fixture()
    assert make_fixture()['metadata']['kind'] == 'synthetic_fixture'
    assert validate_data(make_fixture())


def test_roundtrip_and_hash(tmp_path):
    data = make_fixture()
    p = save_data(data, tmp_path / 'data.json')
    assert load_data(p) == data
    assert file_hash(p) == hashlib.sha256(p.read_bytes()).hexdigest()


def test_invalid_catalogue_rejected():
    data = make_fixture()
    data['users'][0]['test'].append(100000)
    with pytest.raises(ValueError):
        validate_data(data)


def test_preprocessing_ties_and_missing_dates(tmp_path, monkeypatch):
    import feedctrl.data as mod
    archive = tmp_path / 'mock.zip'
    rows = ['user_id,video_id,timestamp,watch_ratio']
    # Every user has train/history/test records under globally shared timestamps.
    for user in range(3):
        for t in range(20):
            rows.append(f'{user},{t % 4},{t},3')
    rows.append('0,1,,3')
    rows.append('0,999,19,3') # future-only item must never enter candidates
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('data/small_matrix.csv', '\n'.join(rows))
        z.writestr('data/item_categories.csv', 'video_id,feat\n0,"[1]"\n1,"[1]"\n2,"[2]"\n3,"[2]"\n999,"[9]"\n')
    monkeypatch.setattr(mod, 'download_kuairec', lambda path: {'sha256': 'test-source'})
    data = mod.preprocess_kuairec(archive, tmp_path / 'processed.json', max_users=0)
    meta = data['metadata']
    assert meta['excluded_missing_timestamp_events'] == 1
    assert meta['candidate_items'] == 4
    assert meta['dropped_postcutoff_cold_item_events'] == 1
    ranges = meta['global_split']['observed_time_ranges']
    assert ranges['train']['max'] < ranges['request_history']['min']
    assert ranges['request_history']['max'] < ranges['test']['min']
