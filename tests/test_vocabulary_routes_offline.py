"""The category and tag review routes, in process. Authored replies only.

A configured provider double returns replies that the tests write. That checks
the session discipline, the sealed groups, Apply and Undo. It is not evidence
about any model.
"""
from copy import deepcopy
import csv
import json

import pytest
from fastapi.testclient import TestClient

from feedctrl.api import create_app
from feedctrl.controls import ParserOperationalError
from feedctrl.semantic_controls import TEXT_FIELDS
from feedctrl import vocabulary_routes

IDENTITY = {'backend': 'test-double', 'model': 'authored', 'digest': 'not-live'}
SCOPE = list(range(1, 9))
TEXT = 'Fewer alpha things and more gamma, please.'
LABELS = {
    1: {'first_level_category_name': 'Alpha', 'topic_tag': 'red, round'},
    2: {'first_level_category_name': 'Alpha', 'topic_tag': 'red'},
    3: {'first_level_category_name': 'Beta', 'topic_tag': 'blue, round'},
    4: {'first_level_category_name': 'Beta'},
    5: {'first_level_category_name': 'Gamma', 'topic_tag': 'green'},
    6: {'first_level_category_name': 'Gamma'},
    7: {'first_level_category_name': 'Delta'},
}


class Provider:
    """A stand-in for the configured adapter. ``answer`` is set by each test."""

    def __init__(self):
        self.answer, self.payloads, self.hook = None, [], None

    def infer(self, payload, schema):
        self.payloads.append(deepcopy(payload))
        if self.hook:
            self.hook()
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer(payload) if callable(self.answer) else deepcopy(self.answer)

    def factory(self):
        return self.infer, deepcopy(IDENTITY)


def source(tmp_path, extra=None):
    path = tmp_path / 'source.csv'
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['video_id', *TEXT_FIELDS])
        writer.writeheader()
        for item in range(1, 37):
            writer.writerow({'video_id': item, 'caption': f'Description {item}',
                             **LABELS.get(item, {}), **(extra or {}).get(item, {})})
    return path


@pytest.fixture
def served(tmp_path):
    provider = Provider()
    app = create_app(fixture=True, semantic_path=source(tmp_path), semantic_infer_factory=provider.factory,
                     allow_local_models=False)
    with TestClient(app) as client:
        yield client, provider


def headers(client):
    return {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}


def pick(vocabulary, kind, value):
    found = next(t for t in vocabulary if t['kind'] == kind and t['value'] == value)
    return {'term_id': found['term_id'], 'value': found['value']}


def proposal(*controls, **changes):
    """A reply builder: each control is (choice, span, [(kind, value), ...])."""
    def build(payload):
        return {'status': 'propose', 'reason': 'authored reason', 'negation_resolved': True, 'alternatives': [],
                'controls': [{'control': choice, 'intent_span': span, 'relation': f'authored relation for {span}',
                              'terms': [pick(payload['vocabulary'], kind, value) for kind, value in terms]}
                             for choice, span, terms in controls], **changes}
    return build


ALPHA = ('exclude/none', 'alpha things', [('category', 'Alpha')])
GAMMA = ('boost/strong', 'more gamma', [('category', 'Gamma')])


def preview(client, h, text=TEXT, **body):
    return client.post('/api/semantic/vocabulary/preview', headers=h,
                       json={'user_id': 1, 'text': text, 'candidate_ids': SCOPE, **body})


def apply(client, h, plan):
    return client.post('/api/semantic/apply', headers=h, json={'user_id': 1, 'plan_id': plan['plan_id']})


def saved(client, h):
    return client.get('/api/semantic/groups?user_id=1', headers=h).json()


def test_terms_are_listed_without_a_model_call(served):
    client, provider = served
    h = headers(client)
    reply = client.post('/api/semantic/vocabulary/terms', headers=h, json={'user_id': 1, 'candidate_ids': SCOPE})
    body = reply.json()
    assert reply.status_code == 200 and provider.payloads == []
    assert [(t['kind'], t['level'], t['value'], t['item_ids']) for t in body['terms']] == [
        ('category', 1, 'Alpha', [1, 2]), ('category', 1, 'Beta', [3, 4]), ('category', 1, 'Delta', [7]),
        ('category', 1, 'Gamma', [5, 6]), ('tag', None, 'blue', [3]), ('tag', None, 'green', [5]),
        ('tag', None, 'red', [1, 2]), ('tag', None, 'round', [1, 3])]
    assert all(set(t) == {'term_id', 'kind', 'level', 'field', 'value', 'item_ids'} for t in body['terms'])
    assert len(body['source_sha256']) == 64 and len(body['vocabulary_sha256']) == 64 and 'No model' in body['note']
    # A narrower scope gives its own terms and members.
    narrow = client.post('/api/semantic/vocabulary/terms', headers=h, json={'user_id': 1, 'candidate_ids': [2, 8]}).json()
    assert [(t['value'], t['item_ids']) for t in narrow['terms']] == [('Alpha', [2]), ('red', [2])]
    assert client.post('/api/semantic/vocabulary/terms', headers=h,
                       json={'user_id': 1, 'candidate_ids': [1, 999]}).status_code == 422
    assert client.post('/api/semantic/vocabulary/terms', headers=h,
                       json={'user_id': 1, 'candidate_ids': [1, 1]}).status_code == 422
    assert client.post('/api/semantic/vocabulary/terms', json={'user_id': 1, 'candidate_ids': SCOPE}).status_code == 401


def test_a_proposal_is_reviewed_applied_and_undone_without_touching_the_other_conditions(served):
    client, provider = served
    h = headers(client)
    before, compare = saved(client, h), client.get('/api/compare?user_id=1', headers=h).json()
    provider.answer = proposal(ALPHA)
    plan = preview(client, h).json()
    assert plan['ready'] and plan['applied'] is False and plan['history_action'] == 'none'
    assert plan['grounding'] == 'vocabulary' and plan['proposal'] is None
    assert plan['model_provenance'] == IDENTITY and len(plan['model_calls']) == 1
    assert set(plan['model_calls'][0]) == {'request_sha256', 'schema_sha256', 'response_sha256', 'raw_response'}
    (group,) = plan['groups']
    assert group['label'] == 'Remove: category "Alpha"' and group['request'] == TEXT and group['scope_ids'] == SCOPE
    sealed = group['proposal']
    assert sealed['status'] == 'review' and sealed['requires_review'] and sealed['action_source'] == 'model'
    assert sealed['grounding'] == 'vocabulary' and sealed['item_ids'] == [1, 2]
    assert sealed['action'] == {'operation': 'exclude', 'strength': 'none', 'intent_span': 'alpha things'}
    assert sealed['reason'] == 'authored relation for alpha things'
    assert sealed['evidence'] == [
        {'item_id': 1, 'field': 'first_level_category_name', 'quote': 'Alpha'},
        {'item_id': 2, 'field': 'first_level_category_name', 'quote': 'Alpha'}]
    assert sealed['vocabulary_terms'] == [{'term_id': 'T01', 'kind': 'category', 'level': 1,
                                           'field': 'first_level_category_name', 'value': 'Alpha'}]
    # The page data: what the model selected, what the application checked, what stays out and why.
    vocabulary = plan['vocabulary']
    assert set(vocabulary) == {'terms', 'controls', 'not_selected', 'checks'}
    assert vocabulary['controls'] == [{
        'label': 'Remove: category "Alpha"', 'operation': 'exclude', 'strength': 'none', 'intent_span': 'alpha things',
        'relation': 'authored relation for alpha things', 'item_ids': [1, 2], 'outside_scope_item_ids': [],
        'terms': [{'term_id': 'T01', 'kind': 'category', 'level': 1, 'field': 'first_level_category_name',
                   'value': 'Alpha', 'item_ids': [1, 2]}]}]
    assert [row['item_id'] for row in vocabulary['not_selected']] == [3, 4, 5, 6, 7, 8]
    assert vocabulary['not_selected'][0]['terms'] == [
        {'kind': 'category', 'level': 1, 'value': 'Beta'}, {'kind': 'tag', 'level': None, 'value': 'blue'},
        {'kind': 'tag', 'level': None, 'value': 'round'}]
    assert vocabulary['not_selected'][-1] == {'item_id': 8, 'terms': []}  # no label: nothing can select it
    assert all(c['passed'] for c in vocabulary['checks']) and len(vocabulary['checks']) == 16
    # The response contract of the page: one call begun, the reply's own reason, no notes for one control.
    assert plan['calls_attempted'] == 1 and plan['call_attempts'] == [{'stage': 'interpretation', 'status': 'returned'}]
    assert 'outcome_source' not in plan and plan['reply_reason'] == 'authored reason' and plan['plan_notes'] == []
    assert plan['scope_effects'] == [{'label': 'Remove: category "Alpha"', 'in_scope_item_ids': [1, 2],
                                      'outside_scope_item_ids': [],
                                      'message': 'This control selects 2 of the 8 items in the scope.'}]
    assert [row['item_id'] for row in plan['scope_items']] == SCOPE
    assert [(row['item_id'], row['field'], row['quote'], row['supplied_field_text'], row['quote_present'])
            for row in plan['evidence_context']] == [
        (1, 'first_level_category_name', 'Alpha', 'Alpha', True),
        (2, 'first_level_category_name', 'Alpha', 'Alpha', True)]
    # The model saw terms only.
    assert set(provider.payloads[0]) == {'system', 'request', 'scope_item_count', 'vocabulary'}
    assert 'Description' not in str(provider.payloads[0])
    # A preview changes nothing.
    assert saved(client, h) == before
    applied = apply(client, h, plan).json()
    assert applied['applied'] and [g['label'] for g in applied['groups']] == ['Remove: category "Alpha"']
    assert applied['feed']['available_items'] == before['feed']['available_items'] - 2
    assert not {1, 2} & {item['item_id'] for item in applied['feed']['items']}
    assert client.get('/api/compare?user_id=1', headers=h).json() == compare
    assert apply(client, h, plan).status_code == 409  # a plan is used once
    undo = client.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'undo'}).json()
    assert undo['ready'] and undo['history_action'] == 'undo'
    restored = apply(client, h, undo).json()
    assert restored['feed'] == before['feed'] and restored['groups'] == []


def test_two_preferences_become_two_groups_with_both_effects(served):
    client, provider = served
    h = headers(client)
    before = saved(client, h)
    provider.answer = proposal(ALPHA, GAMMA)
    plan = preview(client, h).json()
    assert plan['ready'] and [g['label'] for g in plan['groups']] == ['Remove: category "Alpha"',
                                                                      'Show more: category "Gamma"']
    assert [c['item_ids'] for c in plan['vocabulary']['controls']] == [[1, 2], [5, 6]]
    assert [row['item_id'] for row in plan['vocabulary']['not_selected']] == [3, 4, 7, 8]
    assert sorted(row['item_id'] for row in plan['evidence_context']) == [1, 2, 5, 6]
    assert len(provider.payloads) == 1 and saved(client, h) == before
    feed = apply(client, h, plan).json()['feed']
    shown = {item['item_id']: item for item in feed['items']}
    assert not {1, 2} & set(shown) and feed['available_items'] == before['feed']['available_items'] - 2
    assert {5, 6} <= set(shown)  # a strong increase brings both members into the list
    assert all(abs(shown[item]['score'] - shown[item]['base_score'] - 0.40) < 1e-9 for item in (5, 6))
    assert all(abs(item['score'] - item['base_score']) < 1e-9 for key, item in shown.items() if key not in (5, 6))
    undo = client.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'undo'}).json()
    assert apply(client, h, undo).json()['feed'] == before['feed']


def test_merge_replaces_the_same_name_and_keeps_others_and_replace_starts_again(served):
    client, provider = served
    h = headers(client)
    provider.answer = proposal(ALPHA)
    apply(client, h, preview(client, h).json())
    provider.answer = proposal(GAMMA)
    plan = preview(client, h).json()
    assert [g['label'] for g in plan['groups']] == ['Remove: category "Alpha"', 'Show more: category "Gamma"']
    apply(client, h, plan)
    # The same operation and terms again: the earlier control is replaced, not doubled. The latest strength wins.
    provider.answer = proposal(('boost/light', 'more gamma', [('category', 'Gamma')]))
    plan = preview(client, h).json()
    assert [g['label'] for g in plan['groups']] == ['Remove: category "Alpha"', 'Show more: category "Gamma"']
    assert plan['groups'][1]['proposal']['action']['strength'] == 'light'
    apply(client, h, plan)
    provider.answer = proposal(('reduce/standard', 'Fewer alpha things', [('tag', 'round')]))
    plan = preview(client, h, mode='replace').json()
    assert [g['label'] for g in plan['groups']] == ['Show less: tag "round"']
    assert [g['label'] for g in apply(client, h, plan).json()['groups']] == ['Show less: tag "round"']


def test_a_newer_review_or_a_changed_profile_withholds_an_older_result(served):
    client, provider = served
    h = headers(client)
    provider.answer = proposal(ALPHA)
    first = preview(client, h).json()
    second = preview(client, h).json()
    assert apply(client, h, first).status_code == 409  # replaced by the newer review
    assert apply(client, h, second).status_code == 200
    # A reset while the model is working: the late result is not installed.
    provider.hook = lambda: client.post('/api/reset', headers=h, json={'user_id': 1})
    late = preview(client, h)
    assert late.status_code == 409 and saved(client, h)['groups'] == []


@pytest.mark.parametrize('answer,status,calls,source', [
    ({'status': 'ambiguous', 'reason': 'two readings', 'negation_resolved': True,
      'alternatives': ['reading one', 'reading two'], 'controls': []}, 'clarify', 1, 'model_report'),
    ({'status': 'unsupported', 'reason': 'a quota', 'negation_resolved': True, 'alternatives': [], 'controls': []},
     'unsupported', 1, 'model_report'),
    ({'status': 'no_match', 'reason': 'nothing relates', 'negation_resolved': True, 'alternatives': [],
      'controls': []}, 'no_match', 1, 'model_report'),
    ({'status': 'propose'}, 'error', 1, 'reply_rejected'),
    (ParserOperationalError('The provider is not reachable. Start it and try again.'), 'error', 0, 'provider_failure'),
])
def test_a_result_that_is_not_ready_installs_no_plan_and_shows_the_checks(served, answer, status, calls, source):
    client, provider = served
    h = headers(client)
    before = saved(client, h)
    provider.answer = answer
    body = preview(client, h).json()
    assert body['ready'] is False and body['applied'] is False and body['status'] == status
    assert body['grounding'] == 'vocabulary' and 'plan_id' not in body and 'groups' not in body
    assert len(body['vocabulary']['terms']) == 8 and body['vocabulary']['checks']
    assert len(body['model_calls']) == calls and body['model_provenance'] == IDENTITY
    assert ('clarification' in body) == (status == 'clarify')
    if status == 'clarify':
        assert body['clarification']['alternatives'] == ['reading one', 'reading two']
    # One call was begun in every case, also the one that raised and left no reply (vocab F1).
    assert body['calls_attempted'] == 1 and body['outcome_source'] == source
    if isinstance(answer, Exception):
        # An ordinary operational error can hold provider text: the page gets type names only (vocab F2).
        assert body['reason'] == ('The call to the provider failed (ParserOperationalError). No usable reply '
                                  'came back. The terminal of the server has the details.')
        assert body['call_attempts'] == [{'stage': 'interpretation', 'status': 'failed',
                                          'error_type': 'ParserOperationalError'}]
    assert saved(client, h) == before
    assert client.post('/api/semantic/apply', headers=h, json={'user_id': 1, 'plan_id': 'none'}).status_code == 409


def test_a_negated_command_is_clarified_without_a_call(served):
    client, provider = served
    h = headers(client)
    body = preview(client, h, text='Do not hide the alpha things.').json()
    assert body['status'] == 'clarify' and body['model_calls'] == [] and provider.payloads == []
    assert body['calls_attempted'] == 0 and body['outcome_source'] == 'application_check'
    # The check line states only what a pattern can show (vocab F5).
    assert body['vocabulary']['checks'][-1] == {
        'check': 'The request text does not match the negated-command pattern', 'passed': False,
        'detail': "do not, don't, never or not to, followed by hide, exclude, remove, reduce or boost; "
                  'one English pattern, checked before any model call; other wordings are not detected'}


def test_a_changed_term_value_is_refused_and_named_in_the_checks(served):
    client, provider = served
    h = headers(client)

    def altered(payload):
        reply = proposal(ALPHA)(payload)
        reply['controls'][0]['terms'][0]['value'] = 'Alphas'
        return reply
    provider.answer = altered
    body = preview(client, h).json()
    assert body['status'] == 'error' and body['vocabulary']['checks'][-1]['passed'] is False
    assert body['vocabulary']['checks'][-1]['check'] == 'Each selected term exists with exactly the supplied value'
    assert "'Alphas'" in body['vocabulary']['checks'][-1]['detail']


def test_at_most_eight_groups_stay_active(served):
    client, provider = served
    h = headers(client)
    for number, (kind, value) in enumerate([('category', 'Alpha'), ('category', 'Beta'), ('category', 'Delta'),
                                            ('category', 'Gamma'), ('tag', 'blue'), ('tag', 'green'),
                                            ('tag', 'red'), ('tag', 'round')]):
        provider.answer = proposal(('reduce/light', 'alpha things', [(kind, value)]))
        assert apply(client, h, preview(client, h).json()).status_code == 200, number
    provider.answer = proposal(('boost/light', 'more gamma', [('category', 'Gamma')]))
    calls = len(provider.payloads)
    body = preview(client, h).json()
    # Its own outcome with a plain sentence, before any call, and no control list (vocab F14, ui m21).
    assert body['ready'] is False and body['status'] == 'limit' and body['outcome_source'] == 'application_check'
    assert body['reason'] == ('At most 8 controls can be applied at one time. 8 stay applied and this request '
                              'adds 1. Remove a control first, or choose to replace the applied controls.')
    assert body['calls_attempted'] == 0 and len(provider.payloads) == calls and 'controls' not in body['vocabulary']
    assert body['vocabulary']['checks'][-1] == {'check': 'At most eight controls stay applied', 'passed': False,
                                                'detail': '8 stay applied; this request adds 1'}
    assert len(saved(client, h)['groups']) == 8
    # The same operation over the same terms replaces a control, so it fits; the limit counts after replacement.
    provider.answer = proposal(('boost/strong', 'more gamma', [('category', 'Gamma')]))
    body = preview(client, h).json()
    assert body['status'] == 'limit' and body['calls_attempted'] == 0  # eight applied: no call is spent
    # Replace mode starts again, so the same reply fits.
    body = preview(client, h, mode='replace').json()
    assert body['ready'] and len(body['groups']) == 1


def test_requests_are_validated_and_need_a_session(served):
    client, provider = served
    h = headers(client)
    provider.answer = proposal(ALPHA)
    assert preview(client, h, text='').status_code == 422
    assert preview(client, h, text='x' * 2001).status_code == 422
    assert preview(client, h, mode='append').status_code == 422
    assert preview(client, h, label='not a field of this route').status_code == 422
    assert client.post('/api/semantic/vocabulary/preview', headers=h,
                       json={'user_id': 1, 'text': TEXT, 'candidate_ids': [1]}).status_code == 422
    assert client.post('/api/semantic/vocabulary/preview', headers=h,
                       json={'user_id': 1, 'text': TEXT, 'candidate_ids': [1, 999]}).status_code == 422
    assert client.post('/api/semantic/vocabulary/preview',
                       json={'user_id': 1, 'text': TEXT, 'candidate_ids': SCOPE}).status_code == 401
    assert provider.payloads == []


def test_without_a_provider_the_match_is_unavailable_and_terms_still_work(tmp_path):
    with TestClient(create_app(fixture=True, semantic_path=source(tmp_path), allow_local_models=False)) as client:
        h = headers(client)
        reply = preview(client, h)
        assert reply.status_code == 503 and 'No model provider' in reply.json()['detail']
        assert client.post('/api/semantic/vocabulary/terms', headers=h,
                           json={'user_id': 1, 'candidate_ids': SCOPE}).status_code == 200


def test_a_provider_that_cannot_start_is_an_operational_failure(tmp_path):
    def broken():
        raise ParserOperationalError('The route file names a program that is not installed.')
    app = create_app(fixture=True, semantic_path=source(tmp_path), semantic_infer_factory=broken,
                     allow_local_models=False)
    with TestClient(app) as client:
        h = headers(client)
        reply = preview(client, h)
        body = reply.json()
        # HTTP 502 as before. The text of an ordinary operational error stays off the page (vocab F2);
        # the body carries the fields of every other answer that is not ready.
        assert reply.status_code == 502 and 'not installed' not in json.dumps(body)
        assert body['detail'].startswith('Category and tag match failed (ParserOperationalError); no preferences changed:')
        assert body['outcome_source'] == 'provider_failure' and body['calls_attempted'] == 0
        assert body['status'] == 'error' and body['ready'] is False and len(body['vocabulary']['terms']) == 8
        assert saved(client, h)['groups'] == []


def test_a_provider_without_an_identity_is_refused_and_the_terms_are_still_shown(tmp_path):
    called = []

    def infer(payload, schema):
        called.append(1)
        return {}
    app = create_app(fixture=True, semantic_path=source(tmp_path), allow_local_models=False,
                     semantic_infer_factory=lambda: (infer, {'backend': 'unnamed'}))
    with TestClient(app) as client:
        h = headers(client)
        body = preview(client, h).json()
        assert body['ready'] is False and body['status'] == 'error' and 'provenance' in body['reason']
        assert len(body['vocabulary']['terms']) == 8 and body['vocabulary']['checks'] == []
        assert body['model_calls'] == [] and body['model_provenance'] is None and called == []


def control_of(operation, *terms, strength='none'):
    return {'action': {'operation': operation, 'strength': strength},
            'terms': [{'term_id': identifier, 'kind': kind, 'field': 'topic_tag' if kind == 'tag' else
                       'first_level_category_name', 'value': value} for identifier, kind, value in terms]}


def test_group_names_are_printable_bounded_and_distinct():
    taken = set()
    assert vocabulary_routes.control_label(control_of('exclude', ('T01', 'category', 'Alpha'),
                                                      ('T09', 'tag', 'red')), taken) \
        == 'Remove: category "Alpha", tag "red"'
    assert vocabulary_routes.control_label(control_of('boost', ('T01', 'category', 'Alpha')), taken) \
        == 'Show more: category "Alpha"'
    assert vocabulary_routes.control_label(control_of('reduce', ('T01', 'category', 'Alpha')), taken) \
        == 'Show less: category "Alpha"'
    # A second control that would get the same name gets a number.
    assert vocabulary_routes.control_label(control_of('boost', ('T01', 'category', 'Alpha')), taken) \
        == 'Show more: category "Alpha" (2)'
    # The kind and the case are part of the name: a tag and a category with one value differ.
    assert vocabulary_routes.control_label(control_of('boost', ('T05', 'tag', 'Alpha')), taken) \
        == 'Show more: tag "Alpha"'
    # A long name is cut and marked with a short hash of its terms, so two long names differ.
    long = vocabulary_routes.control_label(control_of('exclude', ('T02', 'tag', 'w' * 200 + 'a')), taken)
    other = vocabulary_routes.control_label(control_of('exclude', ('T02', 'tag', 'w' * 200 + 'b')), taken)
    assert len(long) <= 80 and len(other) <= 80 and long != other and long[:60] == other[:60]
    assert long.endswith(']') and '... [' in long
    again = vocabulary_routes.control_label(control_of('exclude', ('T02', 'tag', 'w' * 200 + 'a')), taken)
    assert len(again) <= 80 and again.endswith(' (2)') and again != long
    # A catalogue value with a format character is not put into a name.
    hidden = vocabulary_routes.control_label(control_of('exclude', ('T03', 'tag', 'zero\u200bwidth')), taken)
    assert hidden == 'Remove: terms T03'


def test_a_catalogue_value_with_a_format_character_still_gives_a_usable_group(tmp_path):
    provider = Provider()
    path = source(tmp_path, {7: {'first_level_category_name': 'Del​ta'}})
    app = create_app(fixture=True, semantic_path=path, semantic_infer_factory=provider.factory,
                     allow_local_models=False)
    with TestClient(app) as client:
        h = headers(client)
        provider.answer = proposal(('exclude/none', 'alpha things', [('category', 'Del​ta')]))
        plan = preview(client, h).json()
        assert plan['ready'] and plan['groups'][0]['label'] == 'Remove: terms T03'
        assert plan['groups'][0]['proposal']['item_ids'] == [7]
        assert apply(client, h, plan).status_code == 200
