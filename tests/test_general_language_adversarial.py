"""General-language adversarial contract tests over NEW synthetic catalogues.

Every model response in this file is an AUTHORED MOCK. These tests prove
mechanics and guards only (exact source custody, schema validation, abstention,
review gating, approval binding, deterministic apply). They do NOT measure or
prove model semantic accuracy, and they are not evaluation evidence.
No network, no Ollama, no provider: adapters are monkeypatched test doubles.
"""
from copy import deepcopy
import csv
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import feedctrl
from feedctrl import induction_integration as ii
from feedctrl import indirect_grounding as ig
from feedctrl import semantic_review as sr
from feedctrl.api import create_app
from feedctrl.semantic_controls import TEXT_FIELDS

PROVENANCE = {'backend': 'authored-mock', 'model': 'not-a-model', 'digest': 'no-weights'}
DEFAULT_CAPTION = 'Plain catalogue entry with no notable property.'

KITCHEN = {1: 'Wooden spoon set, oiled beech.', 2: 'Countertop blender with a roaring motor.',
           3: 'Silicone baking mat, reusable.', 4: 'Cast iron skillet, preseasoned.',
           5: 'Electric coffee grinder that shrieks at full speed.', 6: 'Glass storage jars with lids.',
           7: 'Manual pasta roller, quiet hand crank.', 8: 'Bamboo cutting board.'}
TRAVEL = {1: 'Packing cubes in three sizes.', 2: 'Collapsible water bottle.',
          3: 'Merino travel socks.', 4: 'Solar camp lantern that does not need batteries.',
          5: 'Neck pillow with memory foam.', 6: 'Clip-on headlamp that needs batteries.',
          7: 'Universal plug adapter.', 8: 'Quick-dry microfibre towel.'}
MUSIC = {1: 'Beginner violin lesson recorded in a quiet studio.', 2: 'Advanced cello masterclass with bowing drills.',
         3: 'Drum circle session in a city park.', 4: 'Ukulele strumming basics for new players.',
         5: 'Music theory worksheet on scales.', 6: 'Piano sight-reading practice.',
         7: 'Guitar chord changes for songwriters.', 8: 'Choir warm-up routine.'}


def write_catalogue(tmp_path, captions, extra=None, name='catalogue.csv'):
    """Synthetic 36-row sidecar matching the fixture item IDs; never a frozen fixture."""
    path = tmp_path / name
    with path.open('w', encoding='utf8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['video_id', *TEXT_FIELDS])
        writer.writeheader()
        for i in range(1, 37):
            row = {'video_id': i, 'caption': captions.get(i, DEFAULT_CAPTION)}
            row.update((extra or {}).get(i, {}))
            writer.writerow(row)
    return path


def session(c):
    return {'X-Session-ID': c.post('/api/session', json={}).json()['session_id']}


def snapshot(c, h, user=1):
    """Observable state: saved groups (with their semantic feed) and the A-E feeds."""
    return {'groups': c.get(f'/api/semantic/groups?user_id={user}', headers=h).json(),
            'feed': c.get(f'/api/feed?user_id={user}', headers=h).json(),
            'compare': c.get(f'/api/compare?user_id={user}', headers=h).json()}


def pending(c, h, user=1):
    return c.app.state.demo.user_state(h['X-Session-ID'], user).get('semantic_pending')


class Mock:
    """Authored two-stage response double: action parse, then evidence grounding."""

    def __init__(self, action=None, grounding=None):
        self.action, self.grounding, self.calls = action, grounding, []

    def __call__(self, payload, schema):
        if 'needs_clarification' in schema['required']:
            self.calls.append(('action', deepcopy(payload)))
            return self.action(payload) if callable(self.action) else deepcopy(self.action)
        self.calls.append(('grounding', deepcopy(payload)))
        return self.grounding(payload) if callable(self.grounding) else deepcopy(self.grounding)

    def stages(self):
        return [s for s, _ in self.calls]


def action(control, span, clarify=False, question=''):
    return {'needs_clarification': clarify, 'question': question, 'control': control, 'intent_span': span}


def grounding(evidence, status='propose', resolved=True, alternatives=(), reason='Authored mock relation.'):
    return {'status': status, 'reason': reason, 'negation_resolved': resolved,
            'alternatives': list(alternatives), 'evidence': evidence}


def ev(item_id, quote, field='caption'):
    return {'item_id': item_id, 'field': field, 'quote': quote}


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    clients = []

    def build(captions, mock, extra=None):
        path = write_catalogue(tmp_path, captions, extra)
        monkeypatch.setattr(sr, 'make_local_ollama_infer', lambda *a, **k: (mock, deepcopy(PROVENANCE)))
        client = TestClient(create_app(fixture=True, semantic_path=path))
        client.__enter__()
        clients.append(client)
        return client
    yield build
    for client in clients:
        client.__exit__(None, None, None)


def preview(c, h, text, user=1, **kw):
    body = {'user_id': user, 'text': text, 'label': kw.pop('label', 'Reviewed set'),
            'candidate_ids': kw.pop('candidate_ids', list(range(1, 9))), **kw}
    return c.post('/api/semantic/preview', headers=h, json=body)


def apply(c, h, plan_id, user=1):
    return c.post('/api/semantic/apply', headers=h, json={'user_id': user, 'plan_id': plan_id})


def assert_not_ready_and_unchanged(c, h, response, before):
    body = response.json()
    assert response.status_code == 200
    assert body['ready'] is False and body['applied'] is False and 'plan_id' not in body
    assert pending(c, h) is None
    assert snapshot(c, h) == before
    return body


# 1. Paraphrase / nonliteral request across domains -------------------------------------
PARAPHRASES = [
    pytest.param(KITCHEN, 'My early mornings should stay calm, so drop the noisy appliances.',
                 'the noisy appliances', [ev(2, 'roaring motor'), ev(5, 'shrieks at full speed')], id='kitchen-noise'),
    pytest.param(TRAVEL, 'Spare me anything I would have to keep recharging or feeding cells.',
                 'anything I would have to keep recharging or feeding cells', [ev(6, 'needs batteries')], id='travel-power'),
    pytest.param(MUSIC, 'I already own a bow; skip whatever would put it to use.',
                 'whatever would put it to use', [ev(1, 'violin lesson'), ev(2, 'bowing drills')], id='music-bow'),
]


@pytest.mark.parametrize('captions,text,span,evidence', PARAPHRASES)
def test_nonliteral_paraphrase_reaches_review_and_apply_excludes_exact_ids(make_client, captions, text, span, evidence):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy.

    A request with no literal catalogue/category words reaches Review; nothing is
    applied until /api/semantic/apply; afterwards exactly the approved IDs leave the
    eligible set and every other item keeps its unchanged base score.
    """
    mock = Mock(action('exclude/none', span), grounding(evidence))
    c = make_client(captions, mock)
    h = session(c)
    before = snapshot(c, h)
    p = preview(c, h, text).json()
    approved = sorted(e['item_id'] for e in evidence)
    assert p['ready'] is True and p['applied'] is False and p['proposal']['status'] == 'review'
    assert p['proposal']['item_ids'] == approved and p['proposal']['evidence'] == evidence
    assert mock.stages() == ['action', 'grounding']
    grounding_payload = mock.calls[1][1]
    assert grounding_payload['request'] == text  # original request preserved verbatim
    assert [r['item_id'] for r in grounding_payload['catalogue']] == list(range(1, 9))
    assert p['groups'][0]['request'] == text
    assert snapshot(c, h) == before  # preview wrote nothing
    result = apply(c, h, p['plan_id'])
    assert result.status_code == 200 and result.json()['applied'] is True
    after = snapshot(c, h)
    assert after['compare'] == before['compare'] and after['feed'] == before['feed']  # A-E isolation
    feed = after['groups']['feed']
    assert feed['available_items'] == 36 - len(approved)
    assert [g['proposal']['item_ids'] for g in after['groups']['groups']] == [approved]
    shown = {i['item_id'] for i in feed['items']}
    assert not shown & set(approved)
    assert all(i['score'] == i['base_score'] for i in feed['items'])  # untouched non-members


# 2. Real but contradictory quote: quote existence != entailment -----------------------
def contradictory_setup(make_client):
    mock = Mock(action('exclude/none', 'gear that needs batteries'),
                grounding([ev(4, 'need batteries'), ev(6, 'needs batteries')]))
    return make_client(TRAVEL, mock), mock


def test_contradictory_exact_quote_passes_custody_but_never_auto_applies(make_client):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy.

    Item 4 says 'does not need batteries'; the mock cites the exact substring
    'need batteries'. Exact-quote custody is NOT semantic verification, so this
    CAN reach Review. The guard is that a human sees the evidence and nothing is
    applied or changed before explicit approval.
    """
    c, mock = contradictory_setup(make_client)
    h = session(c)
    before = snapshot(c, h)
    response = preview(c, h, 'Hide gear that needs batteries')
    p = response.json()
    assert response.status_code == 200 and p['ready'] is True and p['applied'] is False
    assert p['proposal']['item_ids'] == [4, 6]
    assert {'item_id': 4, 'field': 'caption', 'quote': 'need batteries'} in p['proposal']['evidence']
    assert p['groups'][0]['proposal']['evidence'] == p['proposal']['evidence']
    assert p['proposal']['requires_review'] is True
    assert 'quotes are not relevance proof' in p['note']
    assert snapshot(c, h) == before  # groups, semantic feed and A-E feed unchanged
    assert pending(c, h)['id'] == p['plan_id']  # only a pending token exists


def test_contradictory_quote_review_payload_exposes_cited_source_context(make_client):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy.

    Regression for the review-context gap found by the adversarial pass: the
    review payload must carry the full cited supplied field so a human can see
    that the exact quote ("need batteries") is contradicted by its context
    ("does not need batteries"). The context is display-only: it is not sealed
    into the group, it does not change approval, and no semantic check is claimed.
    """
    c, _ = contradictory_setup(make_client)
    h = session(c)
    before = snapshot(c, h)
    p = preview(c, h, 'Hide gear that needs batteries').json()
    assert p['ready'] is True and p['applied'] is False
    rows = {r['item_id']: r for r in p['evidence_context']}
    assert rows[4]['supplied_field_text'] == TRAVEL[4]
    assert rows[4]['quote_present'] is True and rows[4]['truncated'] is False
    assert 'not performed' in rows[4]['semantic_check']
    assert all('evidence_context' not in json.dumps(g) for g in p['groups'])  # not sealed
    assert snapshot(c, h) == before


# 3. Negation / scope ------------------------------------------------------------------
@pytest.mark.parametrize('text,span', [
    ("Don't remove anything about violin lessons", 'violin lessons'),
    ('Do not hide the cello masterclass', 'the cello masterclass'),
    ('never exclude choir warm-ups', 'choir warm-ups'),
    ('Please do NOT really boost drum circles', 'drum circles'),
    ('don’t   show piano drills less', 'piano drills'),
])
def test_command_negation_guard_clarifies_before_grounding(make_client, text, span):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy.

    Even when the action mock wrongly returns a positive exclude, the lexical
    command-negation guard returns clarify before any grounding call.
    """
    mock = Mock(action('exclude/none', span), grounding([ev(1, 'violin lesson')]))
    c = make_client(MUSIC, mock)
    h = session(c)
    before = snapshot(c, h)
    body = assert_not_ready_and_unchanged(c, h, preview(c, h, text), before)
    assert body['status'] == 'clarify' and 'negation' in body['reason'].lower()
    assert body['item_ids'] == [] and mock.stages() == ['action']


@pytest.mark.parametrize('text,span', [
    ('Dont remove the violin lessons', 'the violin lessons'),
    ('Keep the violin lessons', 'the violin lessons'),
])
def test_negation_guard_is_lexical_only_so_missed_phrasings_rely_on_review(make_client, text, span):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy.

    Documents ACTUAL behaviour: the guard is a conservative English regex. An
    unapostrophised "Dont" or a "Keep" phrasing is not caught; if a (mock) model
    misreads it as exclude, the proposal reaches Review. Mandatory human approval
    is then the only backstop; nothing is applied without /api/semantic/apply.
    """
    mock = Mock(action('exclude/none', span), grounding([ev(1, 'violin lesson')]))
    c = make_client(MUSIC, mock)
    h = session(c)
    before = snapshot(c, h)
    p = preview(c, h, text).json()
    assert mock.stages() == ['action', 'grounding']
    assert p['ready'] is True and p['applied'] is False
    assert snapshot(c, h) == before


@pytest.mark.parametrize('selected,expected', [((1, 2, 3, 4, 5), 'clarify'), ((1, 2, 3, 4), 'review')])
def test_broad_scope_over_half_of_assessed_items_clarifies(make_client, selected, expected):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy.

    Selecting more than half of the 8 assessed items clarifies with no plan;
    exactly half is the inclusive boundary and still reaches Review.
    """
    captions = {i: f'Travel accessory, lightweight model {chr(64 + i)}.' for i in range(1, 9)}
    mock = Mock(action('reduce/standard', 'lightweight things'),
                grounding([ev(i, 'lightweight') for i in selected]))
    c = make_client(captions, mock)
    h = session(c)
    before = snapshot(c, h)
    response = preview(c, h, 'Show fewer lightweight things')
    if expected == 'clarify':
        body = assert_not_ready_and_unchanged(c, h, response, before)
        assert body['status'] == 'clarify' and 'half' in body['reason']
    else:
        assert response.json()['ready'] is True and snapshot(c, h) == before


# 4. Absent concept / no match ---------------------------------------------------------
@pytest.mark.parametrize('raw,status', [
    (grounding([], status='no_match'), 'no_match'),
    (grounding([], status='propose'), 'no_match'),
    (grounding([ev(2, 'roaring motor')], status='no_match'), 'error'),
])
def test_absent_concept_never_reaches_review(make_client, raw, status):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    mock = Mock(action('exclude/none', 'submarine parts'), raw)
    c = make_client(KITCHEN, mock)
    h = session(c)
    before = snapshot(c, h)
    body = assert_not_ready_and_unchanged(c, h, preview(c, h, 'Remove submarine parts'), before)
    assert body['status'] == status and body['item_ids'] == []


# 5. Malformed / adversarial model output fails closed ---------------------------------
def deep(n):
    value = 'x'
    for _ in range(n):
        value = [value]
    return value


GOOD = [ev(2, 'roaring motor')]
BAD_GROUNDING = {
    'invented-id': grounding([ev(999, 'roaring motor')]),
    'real-id-outside-scope': grounding([ev(20, 'Plain')]),
    'string-id': grounding([{'item_id': '2', 'field': 'caption', 'quote': 'roaring motor'}]),
    'bool-id': grounding([{'item_id': True, 'field': 'caption', 'quote': 'Wooden'}]),
    'duplicate-id': grounding([ev(2, 'roaring motor'), ev(2, 'Countertop blender')]),
    'quote-absent': grounding([ev(2, 'whisper-quiet motor')]),
    'quote-case-changed': grounding([ev(2, 'ROARING MOTOR')]),
    'quote-in-other-field': grounding([ev(2, 'small appliance', field='caption')]),
    'wrong-field-for-quote': grounding([ev(2, 'roaring motor', field='topic_tag')]),
    'unsupported-field': grounding([ev(2, 'roaring motor', field='description')]),
    'whitespace-quote': grounding([ev(2, '   ')]),
    'extra-evidence-key': grounding([{**GOOD[0], 'score': 1}]),
    'extra-top-key': {**grounding(GOOD), 'apply_now': True},
    'missing-key': {k: v for k, v in grounding(GOOD).items() if k != 'negation_resolved'},
    'bad-status': grounding(GOOD, status='apply'),
    'nan-reason': grounding(GOOD, reason=float('nan')),
    'inf-in-evidence': grounding([{'item_id': 2, 'field': 'caption', 'quote': 'roaring motor'}, float('inf')]),
    'deep-json': grounding(GOOD, alternatives=[deep(80)]),
    'oversized-text': grounding(GOOD, reason='z' * 2_000_001),
    'non-string-key': {**grounding(GOOD), 1: 'x'},
    'non-json-object': {**grounding(GOOD), 'alternatives': {'a', 'b'}},
    'format-char-reason': grounding(GOOD, reason='ok‮disguised'),
}


@pytest.mark.parametrize('name', sorted(BAD_GROUNDING))
def test_malformed_grounding_output_fails_closed(make_client, name):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    mock = Mock(action('exclude/none', 'loud gadgets'), BAD_GROUNDING[name])
    extra = {2: {'topic_tag': 'small appliance'}}
    c = make_client(KITCHEN, mock, extra)
    h = session(c)
    before = snapshot(c, h)
    body = assert_not_ready_and_unchanged(c, h, preview(c, h, 'Cut the loud gadgets'), before)
    assert body['status'] == 'error' and body.get('item_ids', []) == []


BAD_ACTION = {
    'span-not-in-request': action('exclude/none', 'blenders and grinders'),
    'invalid-enum-pair': action('exclude/strong', 'loud gadgets'),
    'split-fields': {**action('exclude/none', 'loud gadgets'), 'operation': 'exclude'},
    'empty-span': action('boost/light', '  '),
    'non-bool-flag': {**action('exclude/none', 'loud gadgets'), 'needs_clarification': 'false'},
    'nan-question': {**action('exclude/none', 'loud gadgets'), 'question': float('nan')},
    'deep-json': {**action('exclude/none', 'loud gadgets'), 'question': deep(80)},
}


@pytest.mark.parametrize('name', sorted(BAD_ACTION))
def test_malformed_action_output_fails_closed_before_grounding(make_client, name):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    mock = Mock(BAD_ACTION[name], grounding(GOOD))
    c = make_client(KITCHEN, mock)
    h = session(c)
    before = snapshot(c, h)
    body = assert_not_ready_and_unchanged(c, h, preview(c, h, 'Cut the loud gadgets'), before)
    assert body['status'] == 'error' and mock.stages() == ['action']


# 6. Ambiguity -> clarification --------------------------------------------------------
def test_ambiguous_request_surfaces_action_clarification_without_grounding(make_client):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    question = 'Do you mean lessons for beginners or lessons about strings?'
    mock = Mock(action('boost/light', 'the easy string stuff', clarify=True, question=question), grounding(GOOD))
    c = make_client(MUSIC, mock)
    h = session(c)
    before = snapshot(c, h)
    body = assert_not_ready_and_unchanged(c, h, preview(c, h, 'More of the easy string stuff, or less, whatever'), before)
    assert body['status'] == 'clarify' and body['reason'] == question and mock.stages() == ['action']


@pytest.mark.parametrize('raw', [
    grounding([], status='ambiguous', alternatives=['bowed instruments', 'plucked instruments']),
    grounding([ev(1, 'violin lesson')], alternatives=['bowed instruments', 'plucked instruments']),
    grounding([ev(1, 'violin lesson')], resolved=False),
], ids=['ambiguous-status', 'propose-with-alternatives', 'negation-unresolved'])
def test_grounding_ambiguity_clarifies_and_preserves_unselected_alternatives(make_client, raw):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    mock = Mock(action('boost/standard', 'string lessons'), raw)
    c = make_client(MUSIC, mock)
    h = session(c)
    before = snapshot(c, h)
    body = assert_not_ready_and_unchanged(c, h, preview(c, h, 'More string lessons please'), before)
    assert body['status'] == 'clarify' and body['item_ids'] == []
    assert body['clarification']['alternatives'] == raw['alternatives']
    assert 'None was selected or applied' in body['clarification']['notice']


# 7. Approval invalidation -------------------------------------------------------------
def kitchen_ready(make_client):
    mock = Mock(action('exclude/none', 'the noisy appliances'), grounding([ev(2, 'roaring motor')]))
    return make_client(KITCHEN, mock)


@pytest.mark.parametrize('scenario', ['other-session', 'other-user', 'superseded', 'replayed',
                                      'after-reset', 'after-history-preview', 'expired', 'forged-id'])
def test_plan_binding_rejects_cross_session_user_stale_and_replayed_apply(make_client, scenario):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    c = kitchen_ready(make_client)
    h = session(c)
    text = 'Drop the noisy appliances'
    p = preview(c, h, text).json()
    assert p['ready'] is True
    target_h, target_user, plan = h, 1, p['plan_id']
    if scenario == 'other-session':
        target_h = session(c)
    elif scenario == 'other-user':
        target_user = 2
    elif scenario == 'superseded':
        assert preview(c, h, text).json()['ready'] is True
    elif scenario == 'replayed':
        assert apply(c, h, plan).status_code == 200
    elif scenario == 'after-reset':
        assert c.post('/api/reset', headers=h, json={'user_id': 1}).json() == {'reset': True}
    elif scenario == 'after-history-preview':
        assert c.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'clear'}).json()['ready']
    elif scenario == 'expired':
        pending(c, h)['created'] -= 301
    else:
        plan = plan[:-1] + ('A' if plan[-1] != 'A' else 'B')
    before = snapshot(c, target_h, target_user)
    response = apply(c, target_h, plan, target_user)
    assert response.status_code == 409
    assert snapshot(c, target_h, target_user) == before
    if scenario != 'replayed':
        assert snapshot(c, h)['groups']['groups'] == []


# 8. Staged new category: definition review, then classification ----------------------
OBJECTIVE = 'Find lessons for instruments played with a bow.'


def staged_mock(monkeypatch, memberships=None, definition=None):
    stages = []

    def default_definition(payload):
        caption = next(r for r in payload['catalogue'] if r['item_id'] == 1)['fields']['caption']
        assert caption == MUSIC[1]
        return {'status': 'propose', 'label': 'Bowed instrument lessons',
                'definition': 'Lessons whose caption names a bowed string instrument or bowing.',
                'rationale': 'Authored mock definition.', 'alternatives': [],
                'evidence': [{'item_id': 1, 'field': 'caption', 'quote': 'violin lesson', 'reason': 'Authored mock.'}]}

    def default_memberships(payload):
        rows = []
        for r in payload['catalogue']:
            iid = r['item_id']
            if iid in (1, 2):
                rows.append({'item_id': iid, 'verdict': 'match', 'field': 'caption',
                             'evidence_quote': r['fields']['caption'], 'reason': 'Authored mock.'})
            elif iid == 4:
                rows.append({'item_id': iid, 'verdict': 'unknown', 'field': '', 'evidence_quote': '',
                             'reason': 'Authored mock: ukulele bowing not stated.'})
            else:
                rows.append({'item_id': iid, 'verdict': 'not_match', 'field': 'caption',
                             'evidence_quote': r['fields']['caption'], 'reason': 'Authored mock.'})
        return {'memberships': rows}

    def audit(payload):
        out = []
        for r in payload['catalogue']:
            iid = r['item_id']
            kind = 'supported' if iid in (1, 2) else 'not_stated' if iid == 4 else 'contradicted'
            cited = kind != 'not_stated'
            out.append({'item_id': iid, 'assessment': kind, 'field': 'caption' if cited else '',
                        'quote': r['fields']['caption'] if cited else '', 'reason': 'Authored mock.'})
        return {'assessments': out}

    def make(*args, **kwargs):
        local = []

        def infer(payload, schema):
            stage = ('definition' if 'evidence' in schema['required'] else
                     'audit' if 'assessments' in schema['required'] else 'membership')
            stages.append(stage)
            fn = {'definition': definition or default_definition,
                  'membership': memberships or default_memberships, 'audit': audit}[stage]
            raw = fn(deepcopy(payload))
            local.append({'raw_http_response': deepcopy(raw)})
            return raw
        return infer, {'backend': 'authored-mock', 'model_id': 'mock', 'model_revision': 'none'}, local
    monkeypatch.setattr(ii, 'make_induction_infer', make)
    return stages


@pytest.fixture
def music_client(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, 'make_local_ollama_infer', lambda *a, **k: pytest.fail('No grounding call expected'))
    with TestClient(create_app(fixture=True, semantic_path=write_catalogue(tmp_path, MUSIC))) as c:
        yield c


def define(c, h, **kw):
    return c.post('/api/semantic/definition/preview', headers=h, json={
        'user_id': 1, 'candidate_ids': list(range(1, 9)), 'objective': OBJECTIVE,
        'operation': 'exclude', 'strength': 'none', **kw})


def classify(c, h, plan_id, **kw):
    return c.post('/api/semantic/definition/classify', headers=h,
                  json={'user_id': 1, 'plan_id': plan_id, **kw})


def test_staged_new_category_keeps_unknowns_eligible_after_apply(music_client, monkeypatch):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    c = music_client
    stages = staged_mock(monkeypatch)
    h = session(c)
    before = snapshot(c, h)
    d = define(c, h).json()
    assert d['definition_ready'] is True and d['applied'] is False and stages == ['definition']
    assert snapshot(c, h) == before
    m = classify(c, h, d['definition_plan_id'], evidence_reviewed=True).json()
    assert m['ready'] is True and m['applied'] is False and m['definition_approved'] is True
    assert stages == ['definition', 'membership', 'audit']
    assert m['groups'][0]['proposal']['item_ids'] == [1, 2]
    assert m['induction']['unknown_ids'] == [4]
    assert snapshot(c, h) == before
    result = apply(c, h, m['plan_id']).json()
    assert result['applied'] is True
    assert result['feed']['available_items'] == 34  # only the two matches removed; unknown 4 stays eligible
    assert 4 not in result['groups'][0]['proposal']['item_ids']
    assert classify(c, h, d['definition_plan_id'], evidence_reviewed=True).status_code == 409


@pytest.mark.parametrize('approval', [{}, {'evidence_reviewed': False}, {'evidence_reviewed': 'true'},
                                      {'evidence_reviewed': 1}, {'evidence_reviewed': None}])
def test_definition_review_cannot_be_skipped(music_client, monkeypatch, approval):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    c = music_client
    stages = staged_mock(monkeypatch)
    h = session(c)
    d = define(c, h).json()
    before = snapshot(c, h)
    assert classify(c, h, d['definition_plan_id'], **approval).status_code == 422
    assert stages == ['definition'] and pending(c, h) is None and snapshot(c, h) == before
    # A definition token is never an apply token.
    assert apply(c, h, d['definition_plan_id']).status_code == 409
    assert snapshot(c, h) == before


def test_staged_classification_with_invented_member_fails_closed(music_client, monkeypatch):
    """Authored mock; proves mechanics/guards only, not model semantic accuracy."""
    def invented(payload):
        rows = [{'item_id': r['item_id'], 'verdict': 'unknown', 'field': '', 'evidence_quote': '',
                 'reason': 'Authored mock.'} for r in payload['catalogue']]
        rows[0]['item_id'] = 999
        return {'memberships': rows}
    c = music_client
    staged_mock(monkeypatch, memberships=invented)
    h = session(c)
    d = define(c, h).json()
    before = snapshot(c, h)
    m = classify(c, h, d['definition_plan_id'], evidence_reviewed=True).json()
    assert m['ready'] is False and m['status'] == 'error' and 'plan_id' not in m
    assert pending(c, h) is None and snapshot(c, h) == before


# 9. Source-level guard: no hunger-specific routing -----------------------------------
def test_no_hunger_specific_routing_in_package_source():
    """Static check; proves absence of hunger-keyed code paths, not model behaviour.

    The only occurrence of 'hungr' is an illustrative example inside the
    grounding PROMPT string (negated personal state). No regex, branch or
    keyword table in feedctrl routes on it.
    """
    root = Path(feedctrl.__file__).parent
    hits = [(p.name, n, line) for p in sorted(root.glob('*.py'))
            for n, line in enumerate(p.read_text(encoding='utf8').splitlines(), 1)
            if re.search(r'hungr|appetit', line, re.I)]
    assert [(name, '(not hungry)' in line) for name, _, line in hits] == [('indirect_grounding.py', True)]
    assert 'not hungry' in ig.PROMPT
    code_without_prompt = (root / 'indirect_grounding.py').read_text(encoding='utf8').replace(ig.PROMPT, '')
    assert not re.search(r'hungr', code_without_prompt, re.I)
