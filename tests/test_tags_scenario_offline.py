"""Scenario "tags" with fixed test replies (a test double). No model, no listener.

The scenario holds ten invented items with categories and tags. These tests
check the application behaviour for each bundled request: the class of the
result, that a preview changes nothing, that Apply uses exactly the reviewed
members and that Undo restores the identical feed. They say nothing about how
a model maps a request. The fixed replies live in tests/standins/authored_replies.py;
no launcher has hand-written replies.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests' / 'standins'))
import authored_replies  # noqa: E402  (test double)
import run_demo  # noqa: E402

IDS = list(range(61001, 61011))
FOLDER = ROOT / 'scenarios' / 'categories-and-tags'


def options(**values):
    base = dict(provider='route', scenario='tags', port=None, reviewed_config=None, report=None,
                relay_dir=None, declared_model=None, transport_note=None, relay_timeout=600, max_calls=None)
    base.update(values)
    return argparse.Namespace(**base)


@pytest.fixture
def served(monkeypatch):
    authored_replies.install(monkeypatch, run_demo)
    app, _, summary, _ = run_demo.build_app(options())
    assert summary['scenario'] == 'tags' and summary['identity']['live_model'] is False
    with TestClient(app) as client:
        headers = {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}
        yield client, headers, app


def requests():
    return run_demo.scenario_requests('tags')


def saved(client, headers):
    return client.get('/api/semantic/groups?user_id=1', headers=headers).json()


def match(client, headers, key, **body):
    return client.post('/api/semantic/vocabulary/preview', headers=headers,
                       json={'user_id': 1, 'text': requests()[key], 'candidate_ids': IDS, **body}).json()


def apply(client, headers, plan):
    return client.post('/api/semantic/apply', headers=headers, json={'user_id': 1, 'plan_id': plan['plan_id']}).json()


def undo(client, headers):
    plan = client.post('/api/semantic/history/preview', headers=headers, json={'user_id': 1, 'action': 'undo'}).json()
    assert plan['ready'] and plan['history_action'] == 'undo'
    return apply(client, headers, plan)


def calls(app):
    return len(app.state.provider_receipts)


def test_the_scenario_files_agree_with_each_other():
    data = json.loads((FOLDER / 'app-data.json').read_text(encoding='utf-8'))
    assert data['metadata']['is_fixture'] is True and data['metadata']['kind'] == 'synthetic_fixture'
    assert [item['item_id'] for item in data['items']] == IDS and len(data['users']) == 1
    with (FOLDER / 'metadata.csv').open(encoding='utf-8', newline='') as handle:
        rows = {int(row['video_id']): row for row in csv.DictReader(handle)}
    assert sorted(rows) == IDS
    for item in data['items']:
        first = rows[item['item_id']]['first_level_category_name']
        assert item['categories'] == ([first] if first else [])
    assert data['items'][-1]['categories'] == [] and not rows[61010]['topic_tag']
    # The labels and the descriptions disagree in the places that the scenario needs.
    assert all('food' not in rows[item]['caption'].lower() and rows[item]['first_level_category_name'] == 'Cooking'
               for item in (61001, 61002, 61009))
    assert rows[61003]['first_level_category_name'] == 'Travel' and 'street food' in rows[61003]['topic_tag']
    assert 'sandwich' in rows[61004]['caption'] and rows[61004]['first_level_category_name'] == 'Repair'
    bundled = json.loads((FOLDER / 'requests.json').read_text(encoding='utf-8'))
    assert bundled['requests'] == requests()
    # Every bundled vocabulary request has an authored reply, except the one the guard answers.
    for key, text in requests().items():
        if key.startswith('vocabulary') and key != 'vocabulary:negated':
            assert text in authored_replies._TAGS_REPLIES, key
    assert all(text.isascii() for text in requests().values())


def test_status_names_the_scenario_requests_and_the_authored_provider(served):
    client, headers, _ = served
    status = client.get('/api/status').json()
    assert status['items'] == 10 and status['data_mode'] == 'fixture' and status['categories'] == 4
    assert status['provider'] == {'backend': authored_replies.BACKEND,
                                  'model': authored_replies.MODEL, 'live_model': False}
    assert status['scenario_requests'] == requests()
    assert sorted(key for key in requests() if ':' not in key) == ['configured_model', 'label', 'synthetic', 'vocabulary']
    groups = saved(client, headers)
    assert groups['external_adapter_available'] and sorted(groups['feed']['baseline_items']) == IDS


def test_the_two_older_scenarios_keep_their_requests():
    assert set(run_demo.scenario_requests('category')) == {'staged'}
    assert set(run_demo.scenario_requests('hunger')) == {'configured_model', 'label'}
    assert run_demo.CALLS == {'category': 3, 'hunger': 2, 'tags': 10}


def test_the_vocabulary_of_the_ten_items(served):
    client, headers, app = served
    body = client.post('/api/semantic/vocabulary/terms', headers=headers,
                       json={'user_id': 1, 'candidate_ids': IDS}).json()
    assert [[t['kind'], t['level'], t['value'], len(t['item_ids'])] for t in body['terms']] \
        == authored_replies._TAGS_VOCABULARY
    assert not any(61010 in t['item_ids'] for t in body['terms']) and calls(app) == 0


def test_the_indirect_request_selects_by_labels_and_is_applied_and_undone(served):
    client, headers, app = served
    before = saved(client, headers)
    plan = match(client, headers, 'vocabulary')
    assert plan['ready'] and plan['applied'] is False and calls(app) == 1
    (control,) = plan['vocabulary']['controls']
    assert control['label'] == 'Remove: category "Cooking", tag "street food"' and control['operation'] == 'exclude'
    assert control['intent_span'] == 'all the stuff that makes me hungry'
    assert [(t['kind'], t['value'], t['item_ids']) for t in control['terms']] == [
        ('category', 'Cooking', [61001, 61002, 61009]), ('tag', 'street food', [61003])]
    assert control['item_ids'] == [61001, 61002, 61003, 61009]
    assert control['relation'].startswith('Authored rehearsal reply')
    # No description was needed: the three Cooking items say nothing about food.
    assert all('food' not in (row['source_text'] or '').lower()
               for row in plan['scope_items'] if row['item_id'] in (61001, 61002, 61009))
    # The item that mentions food only in its description stays, and the reason is visible.
    kept = {row['item_id']: row['terms'] for row in plan['vocabulary']['not_selected']}
    assert sorted(kept) == [61004, 61005, 61006, 61007, 61008, 61010]
    assert [t['value'] for t in kept[61004]] == ['Repair', 'Bicycle repair', 'bicycle', 'tools']
    assert kept[61010] == []
    assert saved(client, headers) == before  # the preview changed nothing
    applied = apply(client, headers, plan)
    assert applied['feed']['available_items'] == 6
    assert sorted(item['item_id'] for item in applied['feed']['items']) == [61004, 61005, 61006, 61007, 61008, 61010]
    restored = undo(client, headers)
    assert restored['feed'] == before['feed'] and restored['groups'] == [] and calls(app) == 1


def test_the_literal_request_names_an_existing_category(served):
    client, headers, _ = served
    plan = match(client, headers, 'vocabulary:literal')
    assert plan['ready'] and [g['label'] for g in plan['groups']] == ['Remove: category "Repair"']
    assert plan['groups'][0]['proposal']['item_ids'] == [61004, 61005]
    assert plan['groups'][0]['proposal']['action']['intent_span'] == 'the Repair category'
    # The manual category control selects the same members with no model.
    manual = client.post('/api/semantic/preview', headers=headers, json={
        'user_id': 1, 'label': 'Manual', 'candidate_ids': IDS, 'backend': 'manual_category',
        'action_source': 'manual', 'category': 'Repair', 'operation': 'exclude', 'strength': 'none'}).json()
    assert manual['ready'] and manual['groups'][0]['proposal']['item_ids'] == [61004, 61005]
    assert manual['model_calls'] == []


def test_the_mixed_request_gives_two_groups_and_both_effects(served):
    client, headers, app = served
    before = saved(client, headers)
    plan = match(client, headers, 'vocabulary:mixed')
    assert plan['ready'] and calls(app) == 1
    assert [(c['label'], c['operation'], c['strength'], c['intent_span'], c['item_ids'])
            for c in plan['vocabulary']['controls']] == [
        ('Show more: category "Music"', 'boost', 'standard', 'more music videos', [61007, 61008]),
        ('Remove: category "Cooking", tag "street food"', 'exclude', 'none', 'anything about food', [61001, 61002, 61003, 61009])]
    assert [row['item_id'] for row in plan['vocabulary']['not_selected']] == [61004, 61005, 61006, 61010]
    assert saved(client, headers) == before
    rank = lambda items: {item['item_id']: item['rank'] for item in items}
    feed = apply(client, headers, plan)['feed']
    shown = {item['item_id']: item for item in feed['items']}
    assert sorted(shown) == [61004, 61005, 61006, 61007, 61008, 61010]
    # The increase is visible: both music items change position in the first ten (vocab F3, ui M9).
    start, after = rank(before['feed']['items']), rank(feed['items'])
    assert (start[61007], start[61008]) == (4, 5) and (after[61007], after[61008]) == (2, 4)
    assert [item['item_id'] for item in feed['items']] == [61004, 61007, 61005, 61008, 61006, 61010]
    assert all(abs(shown[item]['score'] - shown[item]['base_score'] - 0.25) < 1e-9 for item in (61007, 61008))
    assert all(abs(shown[item]['score'] - shown[item]['base_score']) < 1e-9 for item in (61004, 61005, 61006, 61010))
    assert undo(client, headers)['feed'] == before['feed']


@pytest.mark.parametrize('key,status,provider_calls', [
    ('vocabulary:ambiguous', 'clarify', 1), ('vocabulary:unsupported', 'unsupported', 1),
    ('vocabulary:no_match', 'no_match', 1), ('vocabulary:negated', 'clarify', 0)])
def test_requests_that_cannot_be_applied_change_nothing(served, key, status, provider_calls):
    client, headers, app = served
    before = saved(client, headers)
    body = match(client, headers, key)
    assert body['ready'] is False and body['status'] == status and calls(app) == provider_calls
    assert len(body['model_calls']) == provider_calls and 'plan_id' not in body
    if key == 'vocabulary:ambiguous':
        assert len(body['clarification']['alternatives']) == 3
        assert body['clarification']['model_reason'].startswith('Authored rehearsal reply')
    if key == 'vocabulary:negated':
        assert body['reason'].startswith('The request matches the negated-command pattern')
        assert body['reason'] == __import__('feedctrl.indirect_grounding', fromlist=['GUARD_REASON']).GUARD_REASON
        assert body['outcome_source'] == 'application_check'
    else:
        assert body['outcome_source'] == 'model_report' and body['reply_reason'].startswith('Authored rehearsal reply')
    assert body['calls_attempted'] == provider_calls
    if status in ('unsupported', 'no_match'):
        assert body['reason'].startswith('Authored rehearsal reply')
    assert saved(client, headers) == before
    assert client.post('/api/semantic/apply', headers=headers,
                       json={'user_id': 1, 'plan_id': 'none'}).status_code == 409


def test_a_provider_failure_for_a_request_or_a_scope_is_reported_and_page_safe(served):
    client, headers, _ = served
    other = client.post('/api/semantic/vocabulary/preview', headers=headers, json={
        'user_id': 1, 'text': 'Hide the Repair category, please.', 'candidate_ids': IDS}).json()
    # One page-safe sentence that says what to do; a call was begun and no usable reply came back.
    assert other['ready'] is False and other['status'] == 'error' and other['reason'].startswith('Test double: no fixed reply')
    assert other['outcome_source'] == 'provider_failure' and other['calls_attempted'] == 1
    narrow = client.post('/api/semantic/vocabulary/preview', headers=headers, json={
        'user_id': 1, 'text': requests()['vocabulary:literal'], 'candidate_ids': IDS[:6]}).json()
    assert narrow['ready'] is False and narrow['status'] == 'error' and narrow['reason'].startswith('Test double: no fixed reply')


def test_the_description_request_uses_the_separate_route_and_finds_what_labels_do_not(served):
    client, headers, app = served
    before = saved(client, headers)
    plan = client.post('/api/semantic/preview', headers=headers, json={
        'user_id': 1, 'text': requests()['configured_model'], 'label': requests()['label'],
        'candidate_ids': IDS, 'backend': 'configured_model', 'action_source': 'model', 'mode': 'merge'}).json()
    assert plan['ready'] and calls(app) == 2
    (group,) = plan['groups']
    assert group['label'] == 'Reviewed description request' and group['proposal']['item_ids'] == [61004]
    assert group['proposal']['evidence'] == [
        {'item_id': 61004, 'field': 'caption', 'quote': 'between bites of a sandwich'}]
    assert group['proposal']['action'] == {'operation': 'exclude', 'strength': 'none',
                                           'intent_span': 'the videos where someone is eating'}
    assert apply(client, headers, plan)['feed']['available_items'] == 9
    assert undo(client, headers)['feed'] == before['feed']


def test_a_label_match_and_a_description_match_can_be_active_together(served):
    client, headers, _ = served
    before = saved(client, headers)
    apply(client, headers, match(client, headers, 'vocabulary'))
    plan = client.post('/api/semantic/preview', headers=headers, json={
        'user_id': 1, 'text': requests()['configured_model'], 'label': requests()['label'],
        'candidate_ids': IDS, 'backend': 'configured_model', 'action_source': 'model', 'mode': 'merge'}).json()
    assert [g['label'] for g in plan['groups']] == ['Remove: category "Cooking", tag "street food"', 'Reviewed description request']
    assert apply(client, headers, plan)['feed']['available_items'] == 5
    assert undo(client, headers)['feed']['available_items'] == 6
    assert undo(client, headers)['feed'] == before['feed']


def test_the_item_without_a_label_works_in_every_view(served):
    client, headers, _ = served
    for path in ('/api/feed?user_id=1&condition=E', '/api/compare?user_id=1', '/api/steering?user_id=1',
                 '/api/semantic/groups?user_id=1', '/api/synthetic/items?user_id=1'):
        assert client.get(path, headers=headers).status_code == 200, path
    assert client.get('/api/categories').json()['categories'] == ['Cooking', 'Music', 'Repair', 'Travel']
    feed = client.get('/api/feed?user_id=1&condition=E', headers=headers).json()
    card = next(item for item in feed['items'] if item['item_id'] == 61010)
    assert card['categories'] == []
    semantic = next(item for item in saved(client, headers)['feed']['items'] if item['item_id'] == 61010)
    assert semantic['categories'] == [] and semantic['source_text'].startswith('Untitled clip')
    # A manual control on a category never selects it, and it has no category of its own to choose.
    for category in ('Cooking', 'Music', 'Repair', 'Travel'):
        manual = client.post('/api/semantic/preview', headers=headers, json={
            'user_id': 1, 'label': 'Manual', 'candidate_ids': IDS, 'backend': 'manual_category',
            'action_source': 'manual', 'category': category, 'operation': 'exclude', 'strength': 'none'}).json()
        assert manual['ready'] and 61010 not in manual['groups'][0]['proposal']['item_ids']
    # A scope of the unlabelled item and one other item has only the other item's terms.
    terms = client.post('/api/semantic/vocabulary/terms', headers=headers,
                        json={'user_id': 1, 'candidate_ids': [61008, 61010]}).json()['terms']
    assert [t['value'] for t in terms] == ['Music', 'Live sessions', 'live', 'piano']
    assert all(t['item_ids'] == [61008] for t in terms)


def test_the_fictional_brief_is_drafted_reviewed_admitted_and_removed(served):
    client, headers, app = served
    before, compare = saved(client, headers), client.get('/api/compare?user_id=1', headers=headers).json()
    state = client.get('/api/synthetic/items?user_id=1', headers=headers).json()
    assert state['generation_available'] and state['generation_provider'] == authored_replies.BACKEND
    assert state['configured_model'] == authored_replies.MODEL and state['items'] == []
    draft = client.post('/api/synthetic/preview', headers=headers, json={
        'user_id': 1, 'brief': requests()['synthetic'], 'synthetic_acknowledged': True}).json()
    assert draft['ready'] and draft['admitted'] is False and calls(app) == 1
    record = draft['draft']
    assert record['title'].endswith('(authored rehearsal)') and record['category_label'].endswith('(authored rehearsal)')
    assert record['description'].startswith('Authored rehearsal reply') and record['is_synthetic'] is True
    assert record['origin'] == 'model_generated_synthetic' and record['media_asset'] is None
    assert record['provenance']['model']['backend'] == authored_replies.BACKEND
    assert client.get('/api/synthetic/items?user_id=1', headers=headers).json()['items'] == []  # a draft adds nothing
    admitted = client.post('/api/synthetic/admit', headers=headers,
                           json={'user_id': 1, 'plan_id': draft['plan_id']}).json()
    assert [item['item_id'] for item in admitted['items']] == [record['item_id']]
    assert admitted['feed']['isolated_from_observed_catalogue'] and admitted['feed']['uses_trained_scorer'] is False
    # The fictional item is in its own feed only: the catalogue feeds do not change.
    assert saved(client, headers)['feed'] == before['feed']
    assert client.get('/api/compare?user_id=1', headers=headers).json() == compare
    removed = client.post('/api/synthetic/remove', headers=headers,
                          json={'user_id': 1, 'item_id': record['item_id']}).json()
    assert removed['items'] == [] and calls(app) == 1
    other = client.post('/api/synthetic/preview', headers=headers, json={
        'user_id': 1, 'brief': 'Another fictional brief.', 'synthetic_acknowledged': True}).json()
    assert other['ready'] is False and other['reason'].startswith('Test double: no fixed reply')
    assert other['outcome_source'] == 'provider_failure' and other['calls_attempted'] == 1


def test_the_manual_provider_offers_the_terms_and_no_match(tmp_path):
    app, _, summary, _ = run_demo.build_app(options(provider='manual'))
    assert summary == {'scenario': 'tags', 'provider': 'manual'}
    with TestClient(app) as client:
        headers = {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}
        assert client.get('/api/status').json()['provider'] is None
        assert client.post('/api/semantic/vocabulary/terms', headers=headers,
                           json={'user_id': 1, 'candidate_ids': IDS}).status_code == 200
        assert client.post('/api/semantic/vocabulary/preview', headers=headers, json={
            'user_id': 1, 'text': requests()['vocabulary'], 'candidate_ids': IDS}).status_code == 503
        state = client.get('/api/synthetic/items?user_id=1', headers=headers).json()
        assert state['generation_available'] is False


def test_the_relay_provider_serves_the_scenario_with_its_larger_allowance(tmp_path):
    app, _, summary, _ = run_demo.build_app(options(
        provider='relay', relay_dir=str(tmp_path / 'relay'), declared_model='declared by a test',
        transport_note='no reply is delivered in this test'))
    assert summary['scenario'] == 'tags' and summary['identity']['max_calls'] == 10
    with TestClient(app) as client:
        status = client.get('/api/status').json()
        assert status['provider']['backend'] == 'operator-relay-file-queue'
        assert status['scenario_requests'] == requests()


def test_a_relayed_reply_to_the_vocabulary_request_is_checked_against_its_schema(tmp_path):
    """The relay writes the exact request and validates the delivered file. No model is involved here."""
    import os
    import threading
    import time
    from feedctrl import vocabulary_grounding
    spool = tmp_path / 'relay'
    app, _, _, _ = run_demo.build_app(options(
        provider='relay', relay_dir=str(spool), declared_model='declared by a test',
        transport_note='the test delivers a hand-written reply file', relay_timeout=5))
    with TestClient(app) as client:
        headers = {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}
        result = {}
        worker = threading.Thread(target=lambda: result.update(body=match(client, headers, 'vocabulary:mixed')))
        worker.start()
        request_path, deadline = spool / 'request-0001.json', time.monotonic() + 20
        while not request_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        request = json.loads(request_path.read_text(encoding='utf-8'))
        assert request['system'] == vocabulary_grounding.PROMPT and request['schema'] == vocabulary_grounding.SCHEMA
        assert set(request['payload']) == {'request', 'scope_item_count', 'vocabulary'}
        assert 'Episode' not in json.dumps(request['payload'])  # no description leaves the application
        reply = authored_replies.lookup(request['payload'], request['schema'])
        partial = spool / 'answer.partial'
        partial.write_text(json.dumps(reply), encoding='utf-8')
        os.replace(partial, spool / 'response-0001.json')
        worker.join(20)
        body = result['body']
        assert body['ready'] and [g['label'] for g in body['groups']] == ['Show more: category "Music"', 'Remove: category "Cooking", tag "street food"']
        assert body['model_provenance']['backend'] == 'operator-relay-file-queue'
        receipt = json.loads((spool / 'receipt-0001.json').read_text(encoding='utf-8'))
        assert receipt['outcome'] == 'parsed_transport_only'


def test_the_fingerprint_covers_the_scenario_folder(tmp_path):
    import shutil
    copy = tmp_path / 'copy'
    for folder in ('feedctrl', 'web/dist', 'tools/hosted_validation_current/inputs', 'scenarios'):
        shutil.copytree(ROOT / folder, copy / folder)
    (copy / 'scripts').mkdir()
    shutil.copy(ROOT / 'scripts' / 'run_demo.py', copy / 'scripts' / 'run_demo.py')
    first = run_demo.source_fingerprint(copy)
    assert first == run_demo.source_fingerprint()
    with open(copy / 'scenarios' / 'categories-and-tags' / 'metadata.csv', 'ab') as handle:
        handle.write(b'\n')
    assert run_demo.source_fingerprint(copy) != first
