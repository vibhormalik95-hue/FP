"""The response contract of the review routes for the page. Authored replies and test doubles only.

Each test pins one field or one outcome that the page reads: ``calls_attempted``,
``outcome_source``, the page-safe failure sentence, a rejected reply that stays
visible, ``plan_notes``, the limit of eight controls, a name collision, the
definition rejection and the launcher scenario ``conditions``. No test says
anything about a model.
"""
import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

from feedctrl.api import create_app
from feedctrl.controls import ParserOperationalError
from feedctrl.semantic_controls import TEXT_FIELDS
from feedctrl import indirect_grounding as ig

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests' / 'standins'))
import authored_replies  # noqa: E402  (test double)
import run_demo  # noqa: E402

IDENTITY = {'backend': 'test-double', 'model': 'authored', 'digest': 'not-live'}
SCOPE = list(range(1, 9))
LABELS = {1: {'first_level_category_name': 'Alpha', 'topic_tag': 'red, round'},
          2: {'first_level_category_name': 'Alpha', 'topic_tag': 'red'},
          3: {'first_level_category_name': 'Beta', 'topic_tag': 'blue, round'},
          4: {'first_level_category_name': 'Beta'},
          5: {'first_level_category_name': 'Gamma', 'topic_tag': 'green'},
          6: {'first_level_category_name': 'Gamma'},
          7: {'first_level_category_name': 'Delta'}}
TEXT = 'Fewer alpha things and more gamma, please.'


class Provider:
    """A stand-in for the configured adapter: ``action`` and ``evidence`` are set by each test."""

    def __init__(self):
        self.action = self.evidence = self.vocabulary = None
        self.calls = []

    def infer(self, payload, schema):
        stage = ('action' if 'needs_clarification' in schema['required'] else
                 'vocabulary' if 'controls' in schema['required'] else 'evidence')
        self.calls.append(stage)
        answer = getattr(self, stage)
        if isinstance(answer, Exception):
            raise answer
        return answer(payload) if callable(answer) else deepcopy(answer)

    def factory(self):
        return self.infer, deepcopy(IDENTITY)


@pytest.fixture
def served(tmp_path):
    path = tmp_path / 'source.csv'
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['video_id', *TEXT_FIELDS])
        writer.writeheader()
        for item in range(1, 37):
            writer.writerow({'video_id': item, 'caption': f'Description {item} of a clip', **LABELS.get(item, {})})
    provider = Provider()
    app = create_app(fixture=True, semantic_path=path, semantic_infer_factory=provider.factory,
                     allow_local_models=False)
    with TestClient(app) as client:
        yield client, provider, {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}


def describe(client, h, text='Remove the clips with description one.', label='Described', **body):
    return client.post('/api/semantic/preview', headers=h, json={
        'user_id': 1, 'text': text, 'label': label, 'candidate_ids': SCOPE,
        'backend': 'configured_model', 'action_source': 'model', **body})


def manual(client, h, category, label, operation='exclude', strength='none', **body):
    return client.post('/api/semantic/preview', headers=h, json={
        'user_id': 1, 'label': label, 'candidate_ids': body.pop('candidate_ids', SCOPE), 'backend': 'manual_category',
        'action_source': 'manual', 'category': category, 'operation': operation, 'strength': strength, **body})


def vocabulary(client, h, text=TEXT, **body):
    return client.post('/api/semantic/vocabulary/preview', headers=h,
                       json={'user_id': 1, 'text': text, 'candidate_ids': SCOPE, **body})


def apply(client, h, plan):
    reply = client.post('/api/semantic/apply', headers=h, json={'user_id': 1, 'plan_id': plan['plan_id']})
    assert reply.status_code == 200, reply.text
    return reply.json()


def groups(client, h):
    return client.get('/api/semantic/groups?user_id=1', headers=h).json()['groups']


def action(control='exclude/none', span='description one'):
    return {'needs_clarification': False, 'question': '', 'control': control, 'intent_span': span}


def evidence(*rows, status='propose', alternatives=()):
    return {'status': status, 'reason': 'authored reason', 'negation_resolved': True,
            'alternatives': list(alternatives),
            'evidence': [{'item_id': item, 'field': 'caption', 'quote': quote} for item, quote in rows]}


# ----------------------------------------------------------------- the description route

def test_the_description_route_applies_the_guard_before_its_first_call(served):
    client, provider, h = served
    provider.action, provider.evidence = action(span='the description one clips'), evidence((1, 'Description 1 '))
    body = describe(client, h, text='Do not hide the description one clips.').json()
    assert body['status'] == 'clarify' and provider.calls == []
    assert body['calls_attempted'] == 0 and body['outcome_source'] == 'application_check'
    assert body['checks'] == [{'check': ig.GUARD_CHECK, 'passed': False, 'detail': ig.GUARD_PATTERN_WORDS}]
    assert body['reason'] == ig.GUARD_REASON and body['model_calls'] == []


def test_a_ready_description_review_counts_its_calls_and_lists_its_checks(served):
    client, provider, h = served
    provider.action, provider.evidence = action(), evidence((1, 'Description 1 '))
    plan = describe(client, h).json()
    assert plan['ready'] and plan['calls_attempted'] == 2 and len(plan['model_calls']) == 2
    assert plan['call_attempts'] == [{'stage': 'interpretation', 'status': 'returned'},
                                     {'stage': 'evidence', 'status': 'returned'}]
    assert all(row['passed'] for row in plan['checks']) and plan['checks'][0]['check'] == ig.GUARD_CHECK
    assert plan['plan_notes'] == [] and 'outcome_source' not in plan


@pytest.mark.parametrize('stage', ['action', 'evidence'])
def test_a_failed_call_is_counted_and_its_text_stays_off_the_page(served, stage):
    client, provider, h = served
    provider.action, provider.evidence = action(), evidence((1, 'Description 1 '))
    setattr(provider, stage, ParserOperationalError('token=ghp_EXAMPLEnotARealToken0123 /home/alice/creds.json'))
    reply = describe(client, h)
    body = reply.json()
    text = json.dumps(body)
    assert 'ghp_' not in text and 'alice' not in text
    assert body['outcome_source'] == 'provider_failure' and body['ready'] is False
    assert body['reason'] == ('The call to the provider failed (ParserOperationalError). No usable reply came back. '
                              'The terminal of the server has the details.')
    if stage == 'action':
        # HTTP 502 as before; the body carries the fields of a result that is not ready.
        assert reply.status_code == 502 and body['calls_attempted'] == 1 and body['failed_stage'] == 'interpretation'
    else:
        assert reply.status_code == 200 and body['calls_attempted'] == 2 and body['failed_stage'] == 'evidence'
        assert body['call_attempts'][-1] == {'stage': 'evidence', 'status': 'failed',
                                             'error_type': 'ParserOperationalError'}


def test_a_page_safe_failure_shows_its_own_sentence(served):
    class Safe(ParserOperationalError):
        page_safe = True
    client, provider, h = served
    provider.action = Safe('The provider refused the key.\x1b[31m Check the variable and start again.')
    body = describe(client, h).json()
    assert body['reason'] == 'The provider refused the key. [31m Check the variable and start again.'
    assert body['outcome_source'] == 'provider_failure'


def test_a_rejected_action_reply_stays_visible(served):
    client, provider, h = served
    provider.action = action(span='words that are not in the request')
    body = describe(client, h).json()
    assert body['status'] == 'error' and body['outcome_source'] == 'reply_rejected' and body['calls_attempted'] == 1
    assert body['model_calls'][0]['raw_response'] == action(span='words that are not in the request')
    assert body['checks'][-1]['passed'] is False and 'verbatim part of the request' in body['checks'][-1]['check']


@pytest.mark.parametrize('stage', ['action', 'evidence'])
def test_a_reply_that_is_not_bounded_json_stays_visible_as_text(served, stage):
    client, provider, h = served
    provider.action, provider.evidence = action(), evidence((1, 'Description 1 '))
    setattr(provider, stage, {'status': float('nan'), 'note': 'IGNORE‮ the checks'})
    body = describe(client, h).json()
    assert body['ready'] is False and body['outcome_source'] == 'reply_rejected'
    rejected = body['model_calls'][-1]
    assert rejected['reply_rejected'] is True and rejected['raw_response'] is None
    assert 'nan' in rejected['raw_text'] and '‮' not in rejected['raw_text']
    assert body['call_attempts'][-1]['status'] == 'reply_rejected'


def test_an_invented_quotation_is_a_rejected_reply_with_its_failed_check(served):
    client, provider, h = served
    provider.action, provider.evidence = action(), evidence((1, 'words that are not in the description'))
    body = describe(client, h).json()
    assert body['status'] == 'error' and body['outcome_source'] == 'reply_rejected' and body['calls_attempted'] == 2
    failed = [row for row in body['checks'] if not row['passed']]
    assert len(failed) == 1 and failed[0]['check'].startswith('Every citation names one supplied item once')
    assert "'words that are not in the description'" in failed[0]['detail'] and 'item 1' in failed[0]['detail']
    assert len(body['model_calls']) == 2  # the rejected reply stays visible


def test_a_model_clarification_is_the_reply_s_own_report(served):
    client, provider, h = served
    provider.action = {'needs_clarification': True, 'question': 'Which clips?', 'control': 'exclude/none',
                       'intent_span': ''}
    body = describe(client, h).json()
    assert body['status'] == 'clarify' and body['outcome_source'] == 'model_report'
    assert body['reply_reason'] == 'Which clips?' and body['calls_attempted'] == 1


# ----------------------------------------------------------------- names and the limit

def test_a_name_collision_is_its_own_outcome_before_any_call(served):
    client, provider, h = served
    apply(client, h, manual(client, h, 'category_1', 'Mine').json())
    provider.action, provider.evidence = action(), evidence((1, 'Description 1 '))
    body = describe(client, h, label='mine ').json()
    assert body['status'] == 'label_collision' and body['outcome_source'] == 'application_check'
    assert body['calls_attempted'] == 0 and provider.calls == []
    assert body['reason'] == ('An applied control already has the name "mine". Nothing was applied. '
                              'Choose another name for this control, or remove the applied control first.')
    assert body['checks'] == [{'check': 'The name of the new control is not the name of an applied control',
                               'passed': False, 'detail': 'mine'}]
    # A manual control over another category with the same name collides too.
    other = manual(client, h, 'category_2', 'Mine').json()
    assert other['status'] == 'label_collision' and [g['label'] for g in groups(client, h)] == ['Mine']
    # The same manual control (same category and operation) is replaced by its new version.
    again = manual(client, h, 'category_1', 'Mine').json()
    assert again['ready'] and [g['label'] for g in again['groups']] == ['Mine']
    # Replace mode starts again, so the name is free.
    assert describe(client, h, label='Mine', mode='replace').json()['ready']


def test_a_category_and_tag_control_never_replaces_a_control_of_another_method_by_name(served):
    client, provider, h = served
    apply(client, h, manual(client, h, 'category_1', 'Remove: category "Alpha"').json())
    provider.vocabulary = lambda payload: {
        'status': 'propose', 'reason': 'r', 'negation_resolved': True, 'alternatives': [],
        'controls': [{'control': 'exclude/none', 'intent_span': 'alpha things', 'relation': 'rel',
                      'terms': [next({'term_id': t['term_id'], 'value': t['value']} for t in payload['vocabulary']
                                     if t['value'] == 'Alpha')]}]}
    plan = vocabulary(client, h).json()
    assert [g['label'] for g in plan['groups']] == ['Remove: category "Alpha"', 'Remove: category "Alpha" (2)']
    assert plan['groups'][0]['request'] == 'category_1'  # the manual control stays


@pytest.mark.parametrize('method', ['manual', 'description', 'vocabulary'])
def test_the_limit_of_eight_controls_is_its_own_outcome(served, method):
    client, provider, h = served
    for number in range(8):
        apply(client, h, manual(client, h, f'category_{number % 6}', f'Control {number}',
                                operation='boost', strength='light').json())
    provider.action, provider.evidence = action(), evidence((1, 'Description 1 '))
    # A valid reply that adds one control: the category and tag method decides after the interpretation.
    provider.vocabulary = lambda payload: {
        'status': 'propose', 'reason': 'r', 'negation_resolved': True, 'alternatives': [],
        'controls': [{'control': 'exclude/none', 'intent_span': 'alpha things', 'relation': 'rel',
                      'terms': [next({'term_id': t['term_id'], 'value': t['value']} for t in payload['vocabulary']
                                     if t['value'] == 'Alpha')]}]}
    reply = {'manual': lambda: manual(client, h, 'category_0', 'Ninth'),
             'description': lambda: describe(client, h, label='Ninth'),
             'vocabulary': lambda: vocabulary(client, h)}[method]()
    body = reply.json()
    assert reply.status_code == 200 and body['status'] == 'limit' and body['ready'] is False
    assert body['outcome_source'] == 'application_check'
    if method == 'vocabulary':
        # This method decides after the interpretation: a reply can replace an applied control and then fits.
        assert body['calls_attempted'] == 1 and len(provider.calls) == 1
    else:
        assert body['calls_attempted'] == 0 and provider.calls == []
    assert body['reason'].startswith('At most 8 controls can be applied at one time. 8 stay applied')
    checks = body['vocabulary']['checks'] if method == 'vocabulary' else body['checks']
    assert checks[-1]['check'] == 'At most eight controls stay applied' and checks[-1]['passed'] is False
    assert len(groups(client, h)) == 8


# ----------------------------------------------------------------- plan notes

def test_plan_notes_name_contradictions_overlaps_and_a_broad_total(served):
    client, provider, h = served
    apply(client, h, manual(client, h, 'category_1', 'More one', operation='boost', strength='strong').json())
    plan = manual(client, h, 'category_1', 'Hide one').json()
    members = plan['groups'][0]['proposal']['item_ids']
    (note,) = plan['plan_notes']
    assert note['kind'] == 'conflict' and note['item_ids'] == members and note['controls'] == ['More one', 'Hide one']
    assert note['message'].startswith('The controls "More one" and "Hide one" both reach the items ')
    assert 'Removal takes priority, so the increase has no effect on them.' in note['message']
    assert groups(client, h)[0]['label'] == 'More one'  # display only: the preview changed nothing
    apply(client, h, plan)
    # Removals of several requests that together cover more than half of the catalogue get one note.
    first, second = list(range(1, 21)), list(range(17, 37))
    steps = [('category_2', first), ('category_3', first), ('category_1', second), ('category_2', second),
             ('category_3', second), ('category_4', first)]
    seen = []
    for number, (name, scope) in enumerate(steps):
        plan = manual(client, h, name, f'Hide {number}', candidate_ids=scope).json()
        assert plan['ready']  # a note never blocks
        removed = sorted({item for group in plan['groups'] if group['proposal']['action']['operation'] == 'exclude'
                          for item in group['proposal']['item_ids']})
        notes = [note for note in plan['plan_notes'] if note['kind'] == 'broad_total']
        assert bool(notes) == (len(removed) > 18), (number, removed)
        seen.append(len(removed))
        apply(client, h, plan)
    assert seen[0] <= 18 < seen[-1]
    assert notes[0]['item_ids'] == removed
    assert notes[0]['message'] == f'After this plan, {len(removed)} of the 36 items of the catalogue are removed.'


def test_a_review_states_the_scope_of_a_manual_control(served):
    client, provider, h = served
    plan = manual(client, h, 'category_1', 'Scoped').json()
    (effect,) = plan['scope_effects']
    assert effect['label'] == 'Scoped' and effect['in_scope_item_ids'] == plan['groups'][0]['proposal']['item_ids']
    assert effect['outside_scope_item_ids'] and not set(effect['outside_scope_item_ids']) & set(SCOPE)
    assert plan['calls_attempted'] == 0 and plan['model_calls'] == []


# ----------------------------------------------------------------- staged routes and the discard

def options(**values):
    base = dict(provider='route', scenario='category', port=None, reviewed_config=None, report=None,
                relay_dir=None, declared_model=None, transport_note=None, relay_timeout=600, max_calls=None)
    base.update(values)
    return argparse.Namespace(**base)


@pytest.fixture
def category(monkeypatch):
    authored_replies.install(monkeypatch, run_demo)
    app, _, _, _ = run_demo.build_app(options())
    with TestClient(app) as client:
        body = json.loads((run_demo.SCENARIOS['category'] / 'app-preview.json').read_text(encoding='utf-8'))
        yield client, {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}, body, app


def test_a_definition_can_be_rejected_explicitly(category):
    client, h, body, app = category
    definition = client.post('/api/semantic/definition/preview', headers=h, json=body).json()
    assert definition['definition_ready'] and definition['calls_attempted'] == 1
    plan = definition['definition_plan_id']
    assert client.post('/api/semantic/definition/discard', headers=h,
                       json={'user_id': 1, 'plan_id': 'another'}).status_code == 409
    other = {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}
    assert client.post('/api/semantic/definition/discard', headers=other,
                       json={'user_id': 1, 'plan_id': plan}).status_code == 409
    discarded = client.post('/api/semantic/definition/discard', headers=h, json={'user_id': 1, 'plan_id': plan})
    assert discarded.status_code == 200 and discarded.json()['status'] == 'discarded'
    assert discarded.json()['applied'] is False and len(app.state.provider_receipts) == 1  # no call
    # The rejected definition cannot be classified and cannot be rejected again.
    assert client.post('/api/semantic/definition/classify', headers=h,
                       json={'user_id': 1, 'plan_id': plan, 'evidence_reviewed': True}).status_code == 409
    assert client.post('/api/semantic/definition/discard', headers=h,
                       json={'user_id': 1, 'plan_id': plan}).status_code == 409
    assert client.get('/api/semantic/groups?user_id=1', headers=h).json()['groups'] == []


def test_the_staged_routes_count_their_calls(category):
    client, h, body, _ = category
    definition = client.post('/api/semantic/definition/preview', headers=h, json=body).json()
    review = client.post('/api/semantic/definition/classify', headers=h, json={
        'user_id': 1, 'plan_id': definition['definition_plan_id'], 'evidence_reviewed': True}).json()
    assert review['ready'] and review['calls_attempted'] == 2 and 'plan_notes' in review
    refused = client.post('/api/semantic/definition/preview', headers=h,
                          json={**body, 'objective': body['objective'] + ' Please.'}).json()
    assert refused['status'] == 'error' and refused['outcome_source'] == 'provider_failure'
    assert refused['calls_attempted'] == 1 and refused['reason'].startswith('Test double: no fixed reply')


def test_a_proposed_name_that_exists_is_its_own_outcome():
    from feedctrl import staged_routes
    calls = [{'status': 'returned_json', 'raw_response': {'label': 'K1‮'}}]
    reason, checks = staged_routes.duplicate_name(calls)
    assert reason.startswith('The proposed name "K1" is already the name of a category or an applied control')
    assert checks == [{'check': staged_routes.NAME_CHECK, 'passed': False, 'detail': 'K1'}]


# ----------------------------------------------------------------- the launcher scenario "conditions"

@pytest.mark.parametrize('provider', ['relay', 'route', 'personal-cli'])
def test_the_conditions_scenario_refuses_every_provider_but_manual(provider):
    with pytest.raises(SystemExit, match='Start it with --provider manual'):
        run_demo.build_app(options(provider=provider, scenario='conditions'))


def test_the_conditions_scenario_serves_the_fixture_for_the_rule_parser(monkeypatch):
    monkeypatch.setenv('FEEDCTRL_CAPTION_SIDECAR', str(ROOT / 'scenarios' / 'categories-and-tags' / 'metadata.csv'))
    app, port, summary, _ = run_demo.build_app(options(provider='manual', scenario='conditions'))
    assert summary['scenario'] == 'conditions' and summary['provider'] == 'manual'
    import os
    assert os.environ['FEEDCTRL_CAPTION_SIDECAR'].endswith('metadata.csv')  # restored after the build
    with TestClient(app) as client:
        status = client.get('/api/status').json()
        assert status['scenario'] == 'conditions' and status['scenario_requests'] == {}
        assert status['provider'] is None and status['items'] == 36 and status['caption_data'] is None
        assert client.get('/api/categories').json()['categories'] == [f'category_{n}' for n in range(6)]
        assert len(client.get('/api/users').json()) == 3
        h = {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}
        before = client.get('/api/compare?user_id=1', headers=h).json()
        # The rule parser reads category_N: the instruction applies, and C, D and E can differ from A.
        reply = client.post('/api/control', headers=h, json={'user_id': 1, 'text': 'Show more category_3',
                                                               'backend': 'rule'})
        assert reply.status_code == 200 and reply.json()['applied'] is True
        assert reply.json()['command']['category'] == 'category_3'
        assert client.get('/api/compare?user_id=1', headers=h).json() != before
        profile = client.post('/api/profile/text', headers=h, json={'user_id': 1, 'backend': 'rule',
                                                                    'text': 'I like category_2.'})
        assert profile.status_code == 200, profile.text
        # No language controls: no caption data is loaded.
        assert client.post('/api/semantic/vocabulary/terms', headers=h,
                           json={'user_id': 1, 'candidate_ids': [1, 2]}).status_code == 503


# ----------------------------------------------------------------- texts of an invented scenario (ui m16, M13, N3)

def test_an_invented_scenario_is_not_called_the_official_sidecar_and_an_empty_history_reads_well(monkeypatch):
    authored_replies.install(monkeypatch, run_demo)
    app, _, _, _ = run_demo.build_app(options(scenario='tags'))
    with TestClient(app) as client:
        status = client.get('/api/status').json()
        assert status['semantic_topic'] == 'Caption sidecar loaded; origin not verified; exploratory preview only'
        assert 'Official' not in status['semantic_topic'] and status['semantic_topic_available'] is True
        assert status['caption_data'] == 'invented scenario file' and status['scenario'] == 'tags'
        h = {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}
        text = client.get('/api/feed?user_id=1&condition=D', headers=h).json()['profile_text']
        assert text == 'My observed interaction history contains no items. No category preference is stated yet.'


def test_a_review_lists_the_category_and_the_labels_of_each_scope_item(served):
    client, provider, h = served
    plan = manual(client, h, 'category_1', 'Scoped').json()
    first = plan['scope_items'][0]
    assert first['item_id'] == 1 and first['categories'] == ['category_1']
    assert first['labels'] == [{'kind': 'category', 'level': 1, 'value': 'Alpha'},
                               {'kind': 'tag', 'level': None, 'value': 'red'},
                               {'kind': 'tag', 'level': None, 'value': 'round'}]


@pytest.mark.parametrize('backend', ['manual_category', 'None', ' not_applicable '])
def test_a_draft_provider_cannot_carry_a_name_that_means_no_model(backend):
    from feedctrl import synthetic_drafts
    assert synthetic_drafts._declared_backend(backend) is False
    assert synthetic_drafts._declared_backend('openai-compatible') is True


def test_the_description_route_checks_its_evidence_budget_before_the_first_call(tmp_path):
    path = tmp_path / 'long.csv'
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['video_id', *TEXT_FIELDS])
        writer.writeheader()
        for item in range(1, 37):
            writer.writerow({'video_id': item, 'caption': f'Clip {item} ' + 'word ' * 120})
    provider = Provider()
    provider.action = action(span='clip one')
    app = create_app(fixture=True, semantic_path=path, semantic_infer_factory=provider.factory,
                     allow_local_models=False)
    with TestClient(app) as client:
        h = {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}
        body = client.post('/api/semantic/preview', headers=h, json={
            'user_id': 1, 'text': 'Remove clip one.', 'label': 'L', 'candidate_ids': list(range(1, 21)),
            'backend': 'configured_model', 'action_source': 'model'}).json()
        assert body['status'] == 'clarify' and body['outcome_source'] == 'application_check'
        assert body['calls_attempted'] == 0 and provider.calls == []
        assert body['checks'][-1]['check'] == ig.BUDGET_CHECK and body['checks'][-1]['passed'] is False
        # A smaller scope fits: the same check passes and the calls are made.
        provider.evidence = evidence((1, 'Clip 1 '))
        body = client.post('/api/semantic/preview', headers=h, json={
            'user_id': 1, 'text': 'Remove clip one.', 'label': 'L', 'candidate_ids': [1, 2, 3, 4],
            'backend': 'configured_model', 'action_source': 'model'}).json()
        assert body['ready'] and provider.calls == ['action', 'evidence']
        assert [row['check'] for row in body['checks']][:2] == [ig.GUARD_CHECK, ig.BUDGET_CHECK]
