"""Offline category/tag evidence contract. Authored inference, not model accuracy."""
import csv
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl.api import create_app
from feedctrl import semantic_review as sr
from feedctrl.semantic_controls import TEXT_FIELDS

@pytest.mark.parametrize('field', ['topic_tag', 'first_level_category_name'])
@pytest.mark.parametrize('forgery', [None, 'caption', 'quote', 'other_item'])
def test_existing_metadata_without_descriptions(tmp_path, monkeypatch, field, forgery):
    path = tmp_path / 'metadata.csv'
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['video_id', *TEXT_FIELDS])
        writer.writeheader()
        for i in range(1, 37):
            writer.writerow({'video_id': i, field: 'Food' if i in (3, 4) else 'Cycling'})
    # Inspect the complete fixture feed, not only its default top ten.
    rank_groups = sr.rank_groups
    monkeypatch.setattr(sr, 'rank_groups', lambda *a, **kw: rank_groups(*a, limit=36, **kw))
    calls = []
    def infer(payload, schema):
        calls.append(payload)
        if 'needs_clarification' in schema['required']:
            return {'needs_clarification': False, 'question': '', 'control': 'exclude/none', 'intent_span': 'makes me hungry'}
        return {'status': 'propose', 'reason': 'Authored contract test, not model inference',
                'negation_resolved': True, 'alternatives': [],
                'evidence': [{'item_id': 1 if forgery == 'other_item' and i == 3 else i, 'field': 'caption' if forgery == 'caption' else field, 'quote': 'Pizza' if forgery == 'quote' else 'Food'} for i in (3, 4)]}
    monkeypatch.setattr(sr, 'make_local_ollama_infer', lambda *a, **kw: (infer, {'backend': 'test-double', 'model': 'none', 'digest': 'not-live'}))
    with TestClient(create_app(fixture=True, semantic_path=path)) as c:
        h = {'X-Session-ID': c.post('/api/session', json={}).json()['session_id']}
        baseline = c.get('/api/semantic/groups?user_id=1', headers=h).json()['feed']
        before = c.get('/api/compare?user_id=1', headers=h).json()
        state = c.app.state.demo.user_state(h['X-Session-ID'], 1)
        assert all('caption' not in x['fields'] and 'manual_cover_text' not in x['fields'] for x in c.app.state.demo.topic_index['items'].values())
        p = c.post('/api/semantic/preview', headers=h, json={'user_id': 1, 'text': 'Hide what makes me hungry', 'label': 'Appetite cues', 'candidate_ids': list(range(1,9))}).json()
        assert len(calls) == 2
        assert state['semantic_groups'] == []
        assert p['applied'] is False
        assert c.get('/api/semantic/groups?user_id=1', headers=h).json()['feed'] == baseline
        assert c.get('/api/compare?user_id=1', headers=h).json() == before
        if forgery:
            assert p['status'] == 'error'
            assert p['reason'] == 'Evidence contains unknown/duplicate IDs or unsupported quotations'
            assert state['semantic_pending'] is None
            assert not p['ready']
            assert state['semantic_history'] == []
            return
        assert p['ready'], p
        assert p['groups'][0]['proposal']['item_ids'] == [3,4]
        applied = c.post('/api/semantic/apply', headers=h, json={'user_id': 1, 'plan_id': p['plan_id']}).json()
        assert applied['applied'] and applied['feed']['available_items'] == 34
        assert {x['item_id'] for x in applied['feed']['items']} == set(range(1, 37)) - {3, 4}
        assert applied['feed'] == p['feed']
        undo = c.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'undo'}).json()
        assert len(state['semantic_groups']) == 1
        assert c.get('/api/semantic/groups?user_id=1', headers=h).json()['feed'] == applied['feed']
        restored = c.post('/api/semantic/apply', headers=h, json={'user_id': 1, 'plan_id': undo['plan_id']}).json()
        assert restored['applied'] and restored['feed']['available_items'] == 36
        assert restored['feed'] == baseline
        assert state['semantic_groups'] == []
        assert c.get('/api/compare?user_id=1', headers=h).json() == before

