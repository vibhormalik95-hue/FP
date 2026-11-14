"""Requests matched to existing category and tag terms. Authored replies only.

These tests check the application's part: the vocabulary, the checks on a
reply and the mechanical selection of members. A reply written for a test is
contract evidence. It is not evidence that a model maps requests correctly.
"""
from copy import deepcopy
import json

import pytest

from feedctrl.controls import ParserOperationalError
from feedctrl import indirect_grounding
from feedctrl import vocabulary_grounding as vg

MODEL = {'backend': 'test-double', 'model': 'authored', 'digest': 'not-live'}
REQUEST = 'Fewer alpha things and more gamma, please.'


def index():
    """Eight invented rows. Descriptions hold words that no label holds."""
    rows = {
        1: {'caption': 'SECRET-ONE', 'first_level_category_name': 'Alpha', 'second_level_category_name': 'Alpha minor',
            'topic_tag': 'red, round'},
        2: {'caption': 'SECRET-TWO', 'first_level_category_name': 'Alpha', 'topic_tag': '[red，#square]'},
        3: {'caption': 'SECRET-THREE', 'first_level_category_name': 'Beta', 'topic_tag': 'blue|round'},
        4: {'caption': 'SECRET-FOUR', 'first_level_category_name': 'Beta', 'third_level_category_name': 'Deep'},
        5: {'caption': 'SECRET-FIVE', 'first_level_category_name': 'Gamma', 'topic_tag': 'Gamma'},
        6: {'caption': 'SECRET-SIX', 'first_level_category_name': 'Gamma'},
        7: {'caption': 'SECRET-SEVEN', 'first_level_category_name': 'Delta'},
        8: {'caption': 'SECRET-EIGHT'},
    }
    return {'sha256': 'a' * 64, 'items': {item: {'fields': fields} for item, fields in rows.items()}}


def term(terms, kind, value):
    return next(t for t in terms if t['kind'] == kind and t['value'] == value)


def pick(terms, kind, value):
    found = term(terms, kind, value)
    return {'term_id': found['term_id'], 'value': found['value']}


def reply(controls, **changes):
    return {'status': 'propose', 'reason': 'authored reason', 'negation_resolved': True,
            'alternatives': [], 'controls': controls, **changes}


def control(terms, choice='exclude/none', span='alpha things', relation='authored relation'):
    return {'control': choice, 'intent_span': span, 'relation': relation, 'terms': terms}


def run(raw, request=REQUEST, source=None, **options):
    seen = []

    def infer(payload, schema):
        seen.append(deepcopy((payload, schema)))
        return raw(payload) if callable(raw) else deepcopy(raw)
    result = vg.propose_vocabulary(request, source or index(), infer, model_provenance=MODEL, **options)
    return result, seen


def failed(result):
    """The name of the one check that failed; every earlier check passed."""
    assert [c['passed'] for c in result['checks'][:-1]] == [True] * (len(result['checks']) - 1)
    assert result['checks'][-1]['passed'] is False and result['controls'] == []
    return result['checks'][-1]['check']


def test_tags_are_split_by_the_stated_rule_and_nothing_else():
    assert vg.split_tags('red, round') == ['red', 'round']
    assert vg.split_tags('[red，#square]') == ['red', 'square']
    assert vg.split_tags(' a ; b ；c|d ,, a ') == ['a', 'b', 'c', 'd']
    assert vg.split_tags('#  spaced out ') == ['spaced out']
    assert vg.split_tags('Street Food') == ['Street Food']  # case and inner spaces are kept
    assert vg.split_tags('[]') == [] and vg.split_tags('') == [] and vg.split_tags(None) == []
    assert vg.split_tags('[a') == ['[a']  # only a complete pair of brackets is removed


def test_vocabulary_is_deterministic_and_keeps_fields_apart():
    terms = vg.build_vocabulary(index())
    assert terms == vg.build_vocabulary(index())
    assert [t['term_id'] for t in terms] == [f'T{n:02d}' for n in range(1, len(terms) + 1)]
    assert [(t['kind'], t['level'], t['value']) for t in terms] == [
        ('category', 1, 'Alpha'), ('category', 1, 'Beta'), ('category', 1, 'Delta'), ('category', 1, 'Gamma'),
        ('category', 2, 'Alpha minor'), ('category', 3, 'Deep'),
        ('tag', None, 'blue'), ('tag', None, 'Gamma'), ('tag', None, 'red'), ('tag', None, 'round'),
        ('tag', None, 'square')]
    assert term(terms, 'category', 'Alpha')['item_ids'] == [1, 2]
    assert term(terms, 'tag', 'round')['item_ids'] == [1, 3]
    # The same value in two fields is two terms with their own members.
    assert term(terms, 'category', 'Gamma')['item_ids'] == [5, 6] and term(terms, 'tag', 'Gamma')['item_ids'] == [5]
    assert term(terms, 'tag', 'Gamma')['field'] == 'topic_tag'
    assert not any(8 in t['item_ids'] for t in terms)  # an item with no label is in no term


def test_identifiers_stay_ordered_beyond_ninety_nine_terms():
    source = index()
    source['items'][1]['fields']['topic_tag'] = ', '.join(f'tag{n:03d}' for n in range(120))
    terms = vg.build_vocabulary(source)
    assert len(terms[0]['term_id']) == 4 and [t['term_id'] for t in terms] == sorted(t['term_id'] for t in terms)


def test_the_model_receives_terms_and_no_description_or_item():
    result, seen = run(lambda payload: reply([control([pick(payload['vocabulary'], 'category', 'Alpha')])]))
    payload, schema = seen[0]
    assert set(payload) == {'system', 'request', 'scope_item_count', 'vocabulary'} and payload['request'] == REQUEST
    assert payload['scope_item_count'] == 8  # the model can see the size that the half-of-scope rule uses
    assert all(set(row) == {'term_id', 'kind', 'level', 'value', 'item_count'} for row in payload['vocabulary'])
    text = json.dumps(payload)
    assert 'SECRET' not in text and 'caption' not in text and 'item_ids' not in text
    assert schema == vg.SCHEMA and len(seen) == 1
    assert result['status'] == 'review'


def test_one_control_selects_exactly_the_items_that_carry_its_terms():
    result, _ = run(lambda payload: reply([control([pick(payload['vocabulary'], 'tag', 'round'),
                                                    pick(payload['vocabulary'], 'category', 'Delta')])]))
    assert result['status'] == 'review' and result['reason'] == 'authored reason' and result['requires_review']
    assert all(c['passed'] for c in result['checks']) and len(result['checks']) == 16
    assert result['call_attempted'] is True and 'outcome_source' not in result
    assert result['reply_reason'] == 'authored reason'
    (selected,) = result['controls']
    assert selected['action'] == {'operation': 'exclude', 'strength': 'none', 'intent_span': 'alpha things'}
    assert selected['item_ids'] == [1, 3, 7] and selected['relation'] == 'authored relation'
    # Custody: each quotation is the term value, present in that field of that item.
    source = index()
    assert [e['item_id'] for e in selected['evidence']] == [1, 3, 7]
    assert all(e['quote'] in source['items'][e['item_id']]['fields'][e['field']] for e in selected['evidence'])
    assert selected['evidence'][2] == {'item_id': 7, 'field': 'first_level_category_name', 'quote': 'Delta'}
    provenance = selected['provenance']
    assert provenance['action_sha256'] == indirect_grounding._digest(selected['action'])
    assert provenance['request_sha256'] == indirect_grounding._digest(REQUEST)
    assert provenance['catalogue_sha256'] == indirect_grounding._digest(indirect_grounding._catalogue(source))
    assert provenance['vocabulary_sha256'] == result['vocabulary']['sha256'] == indirect_grounding._digest(
        result['vocabulary']['terms'])
    assert provenance['source_sha256'] == 'a' * 64 and provenance['model'] == MODEL
    assert {'prompt_sha256', 'schema_sha256', 'response_sha256', 'candidate_count'} <= set(provenance)


def test_two_preferences_give_two_controls_with_their_own_direction():
    result, _ = run(lambda payload: reply([
        control([pick(payload['vocabulary'], 'category', 'Alpha')], 'reduce/light', 'Fewer alpha things'),
        control([pick(payload['vocabulary'], 'category', 'Gamma')], 'boost/strong', 'more gamma')]))
    assert result['status'] == 'review'
    assert [c['action'] for c in result['controls']] == [
        {'operation': 'reduce', 'strength': 'light', 'intent_span': 'Fewer alpha things'},
        {'operation': 'boost', 'strength': 'strong', 'intent_span': 'more gamma'}]
    assert [c['item_ids'] for c in result['controls']] == [[1, 2], [5, 6]]
    assert result['controls'][0]['provenance']['action_sha256'] != result['controls'][1]['provenance']['action_sha256']


@pytest.mark.parametrize('build,status,check', [
    (lambda v: [control([{'term_id': 'T99', 'value': 'Alpha'}])],
     'error', 'Each selected term exists with exactly the supplied value'),
    (lambda v: [control([{'term_id': pick(v, 'category', 'Alpha')['term_id'], 'value': 'alpha'}])],
     'error', 'Each selected term exists with exactly the supplied value'),
    (lambda v: [control([pick(v, 'category', 'Alpha'), pick(v, 'category', 'Alpha')])],
     'error', 'No term is repeated in a control'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], 'exclude/none'),
                control([pick(v, 'category', 'Alpha')], 'boost/standard', 'more gamma')],
     'clarify', 'No term is used by more than one control'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], 'boost/light'),
                control([pick(v, 'category', 'Alpha')], 'boost/strong', 'more gamma')],
     'clarify', 'No term is used by more than one control'),
    (lambda v: [control([pick(v, 'category', 'Alpha')]), control([pick(v, 'category', 'Alpha')], span='more gamma')],
     'error', 'No term is used by more than one control'),
    (lambda v: [control([])], 'error', 'Each control selects at least one item'),
    (lambda v: [control([pick(v, 'category', 'Alpha'), pick(v, 'category', 'Beta'), pick(v, 'category', 'Delta')])],
     'clarify', 'No control selects more than half of the supplied items'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], span='ALPHA THINGS')],
     'error', 'Each intent span is a verbatim part of the request with at least one word'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], span=' ')],
     'error', 'Each intent span is a verbatim part of the request with at least one word'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], span=', ')],
     'error', 'Each intent span is a verbatim part of the request with at least one word'),
    # Two controls must cite different words: the same span, or one span inside the other, is refused.
    (lambda v: [control([pick(v, 'category', 'Alpha')]), control([pick(v, 'category', 'Gamma')], 'boost/light')],
     'error', 'The intent spans of different controls do not overlap'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], span='alpha things and more'),
                control([pick(v, 'category', 'Gamma')], 'boost/light', 'more gamma')],
     'error', 'The intent spans of different controls do not overlap'),
    # Different terms with the same members: two instructions for the same items are not settled silently.
    (lambda v: [control([pick(v, 'category', 'Alpha')], 'boost/strong', 'more gamma'),
                control([pick(v, 'tag', 'red')], 'exclude/none')],
     'clarify', 'No two controls give different instructions to the same items'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], 'boost/light', 'more gamma'),
                control([pick(v, 'tag', 'round')], 'boost/strong')],
     'clarify', 'No two controls give different instructions to the same items'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], 'exclude/strong')],
     'error', 'Each control value is one of the declared choices'),
    (lambda v: [control([pick(v, 'category', 'Alpha')], 'remove')],
     'error', 'Each control value is one of the declared choices'),
])
def test_each_application_check_stops_a_wrong_proposal(build, status, check):
    result, seen = run(lambda payload: reply(build(payload['vocabulary'])))
    assert result['status'] == status and failed(result) == check and len(seen) == 1
    assert 'clarification' not in result
    # A reply came back and an application check rejected it.
    assert result['outcome_source'] == 'reply_rejected' and result['call_attempted'] is True


def test_two_controls_with_the_same_instruction_may_share_items():
    # Removal of the same items through two terms is not a contradiction.
    result, _ = run(lambda payload: reply([control([pick(payload['vocabulary'], 'category', 'Alpha')]),
                                           control([pick(payload['vocabulary'], 'tag', 'red')], span='more gamma')]))
    assert result['status'] == 'review' and [c['item_ids'] for c in result['controls']] == [[1, 2], [1, 2]]


def test_spans_are_placed_without_overlap_also_when_a_span_occurs_twice():
    assert vg._separable('more a, more b', ['more', 'more'])
    assert not vg._separable('more a', ['more', 'more'])
    assert not vg._separable('abc', ['ab', 'bc']) and vg._separable('ab bc', ['ab', 'bc'])
    assert vg._separable('x', ['x'])


def test_several_exclusions_cannot_add_up_to_more_than_half_of_the_scope():
    def build(payload):
        v = payload['vocabulary']
        return reply([control([pick(v, 'category', 'Alpha')], span='alpha things'),
                      control([pick(v, 'category', 'Beta')], span='more gamma'),
                      control([pick(v, 'category', 'Delta')], span='Fewer')])
    result, _ = run(build)
    assert result['status'] == 'clarify'
    assert failed(result) == 'The removals of this request together remove at most half of the supplied items'
    assert result['outcome_source'] == 'reply_rejected'
    assert result['checks'][-1]['detail'] == '5 of 8 items'
    # The bound is on removal. An increase and an exclusion may together touch more than half.

    def mixed(payload):
        v = payload['vocabulary']
        return reply([control([pick(v, 'category', 'Alpha'), pick(v, 'category', 'Beta')], span='alpha things'),
                      control([pick(v, 'category', 'Gamma'), pick(v, 'category', 'Delta')], 'boost/light', 'more gamma')])
    result, _ = run(mixed)
    assert result['status'] == 'review' and [len(c['item_ids']) for c in result['controls']] == [4, 3]


def test_exactly_half_of_the_scope_is_still_accepted():
    result, _ = run(lambda payload: reply([control([pick(payload['vocabulary'], 'category', 'Alpha'),
                                                    pick(payload['vocabulary'], 'category', 'Beta')])]))
    assert result['status'] == 'review' and result['controls'][0]['item_ids'] == [1, 2, 3, 4]


@pytest.mark.parametrize('status', ['no_match', 'ambiguous', 'unsupported'])
def test_an_abstention_with_a_selection_is_an_error(status):
    result, _ = run(lambda payload: reply([control([pick(payload['vocabulary'], 'category', 'Alpha')])], status=status))
    assert result['status'] == 'error' and failed(result) == 'An abstention selects nothing'


def test_abstentions_keep_their_meaning_and_select_nothing():
    result, _ = run(reply([], status='no_match'))
    assert result['status'] == 'no_match' and result['reason'] == 'authored reason' and result['controls'] == []
    # The status and its reason are the reply's own report; the application did not test them.
    assert result['outcome_source'] == 'model_report' and result['reply_reason'] == 'authored reason'
    result, _ = run(reply([], status='unsupported'))
    assert result['status'] == 'unsupported' and result['reason'] == 'authored reason'
    assert result['outcome_source'] == 'model_report'
    result, _ = run(reply([], status='ambiguous', alternatives=['one reading', 'another reading']))
    assert result['status'] == 'clarify' and result['outcome_source'] == 'model_report'
    assert result['clarification'] == {
        'model_reason': 'authored reason', 'alternatives': ['one reading', 'another reading'],
        'negation_resolved': True,
        'question': 'Please state the intended target explicitly in your instruction.',
        'notice': 'These are unverified model interpretations. None was selected or applied.'}
    # A "no match" that still lists readings, or leaves a negation open, is a clarification.
    assert run(reply([], status='no_match', alternatives=['maybe this']))[0]['status'] == 'clarify'
    assert run(reply([], status='no_match', negation_resolved=False))[0]['status'] == 'clarify'
    assert all(c['passed'] for c in result['checks'])


@pytest.mark.parametrize('changes', [{'alternatives': ['a second reading']}, {'negation_resolved': False}])
def test_a_proposal_with_an_open_reading_is_a_clarification_that_keeps_the_readings(changes):
    result, _ = run(lambda payload: reply([control([pick(payload['vocabulary'], 'category', 'Alpha')])], **changes))
    assert result['status'] == 'clarify' and result['controls'] == []
    assert failed(result) == 'A proposal has no open negation and no competing interpretation'
    assert result['clarification']['alternatives'] == changes.get('alternatives', [])
    assert result['clarification']['negation_resolved'] is changes.get('negation_resolved', True)
    assert result['outcome_source'] == 'model_report'


def test_a_proposal_without_a_control_matches_nothing():
    result, _ = run(reply([]))
    assert result['status'] == 'no_match' and failed(result) == 'A proposal selects at least one control'


@pytest.mark.parametrize('raw', [
    None, [], 'text', {},
    {k: v for k, v in reply([]).items() if k != 'alternatives'},
    {**reply([]), 'extra': 1},
    reply([], status='maybe'), reply([], status=None),
    reply([], reason=''), reply([], reason=' '), reply([], reason='x' * 2001), reply([], reason='bad\x00text'),
    reply([], reason='bad​text'), reply([], reason=5),
    reply([], negation_resolved=1), reply([], negation_resolved='true'),
    reply([], alternatives='one'), reply([], alternatives=['x'] * 7), reply([], alternatives=['']),
    reply([], alternatives=['x' * 301]), reply([], alternatives=[3]), reply([], alternatives=['line\nbreak']),
    reply([], alternatives=['zero\u200bwidth']), reply([], alternatives=['bidi\u202eturn']),
    reply('none'), reply([control([])] * 5), reply(['text']),
    reply([{'control': 'exclude/none', 'intent_span': 'alpha things', 'terms': []}]),
    reply([{**control([]), 'operation': 'exclude'}]),
    reply([control([], choice=7)]), reply([control([], span=None)]),
    reply([control([], relation='')]), reply([control([], relation='x' * 2001)]),
    reply([control('T01')]), reply([control([{'term_id': 'T01', 'value': 'Alpha'}] * 13)]),
    reply([control([{'term_id': 'T01'}])]), reply([control([{'term_id': 1, 'value': 'Alpha'}])]),
    reply([control([{'term_id': 'T01', 'value': 'Alpha', 'item_ids': [1]}])]),
])
def test_a_reply_without_the_declared_fields_and_bounds_is_rejected(raw):
    result, seen = run(raw)
    assert result['status'] == 'error' and result['controls'] == [] and len(seen) == 1
    if isinstance(raw, dict) and raw.get('alternatives') == ['lone\ud800surrogate']:
        assert failed(result) == 'The reply is bounded finite JSON'
    else:
        assert failed(result) == 'The reply has the declared fields and bounded values'
        assert result['checks'][-1]['detail']


@pytest.mark.parametrize('raw', [{'status': float('nan')}, {'status': {1, 2}}, {1: 'x'},
                                 reply([], alternatives=['lone\ud800surrogate'])])
def test_a_reply_that_is_not_bounded_json_is_rejected(raw):
    result, _ = run(raw)
    assert result['status'] == 'error' and result['reason'] == 'Response is not bounded finite JSON'
    assert 'response_sha256' not in result['provenance']
    assert result['outcome_source'] == 'reply_rejected' and failed(result) == 'The reply is bounded finite JSON'


@pytest.mark.parametrize('request_text', [
    'Do not hide the alpha things.', "Don't ever remove alpha things", 'never exclude gamma',
    'I want you not to boost it', 'Please do NOT really reduce the alpha things'])
def test_a_request_that_matches_the_negated_command_pattern_is_stopped_before_any_model_call(request_text):
    def infer(payload, schema):
        raise AssertionError('no call may be made')
    result = vg.propose_vocabulary(request_text, index(), infer, model_provenance=MODEL)
    assert result['status'] == 'clarify' and failed(result) == indirect_grounding.GUARD_CHECK
    # The check line says what a pattern can show; the reason says what the person can do.
    assert failed(result) == 'The request text does not match the negated-command pattern'
    assert result['checks'][-1]['detail'] == indirect_grounding.GUARD_PATTERN_WORDS
    assert result['reason'] == indirect_grounding.GUARD_REASON and 'positive instruction' in result['reason']
    assert result['outcome_source'] == 'application_check' and result['call_attempted'] is False
    assert 'response_sha256' not in result['provenance'] and 'reply_reason' not in result


def test_the_negation_guard_is_the_one_shared_pattern():
    assert vg.COMMAND_NEGATION is indirect_grounding.COMMAND_NEGATION
    assert not vg.COMMAND_NEGATION.search("I'm not hungry, remove all the stuff that makes me hungry.")


@pytest.mark.parametrize('request_text', [
    "Don't show me the alpha things.", 'Never show me alpha things again.', 'Do not show gamma.'])
def test_do_not_show_is_a_plain_request_to_remove_and_reaches_the_model(request_text):
    assert not vg.COMMAND_NEGATION.search(request_text)
    result, seen = run(reply([], status='no_match'), request=request_text)
    assert len(seen) == 1 and result['status'] == 'no_match'
    assert next(c for c in result['checks'] if c['check'] == indirect_grounding.GUARD_CHECK)['passed'] is True


@pytest.mark.parametrize('request_text', [
    'Dont hide the alpha things.', 'Stop hiding the alpha things.', 'Keep the alpha things.',
    'You must not remove the alpha things.'])
def test_the_pattern_misses_other_wordings_and_the_docstring_of_the_limit_says_so(request_text):
    # Documented limit, not a claim: these negated commands are not found and reach the model.
    assert not vg.COMMAND_NEGATION.search(request_text)
    assert 'other wordings are not detected' in indirect_grounding.GUARD_PATTERN_WORDS


def test_a_negated_personal_state_reaches_the_model():
    result, seen = run(lambda payload: reply([control([pick(payload['vocabulary'], 'category', 'Alpha')],
                                                      span='hide the alpha things')]),
                       request='I am not in the mood, hide the alpha things.')
    assert result['status'] == 'review' and len(seen) == 1


def one_item(tags):
    return {'sha256': 'a' * 64, 'items': {1: {'fields': {'topic_tag': ', '.join(tags)}}, 2: {'fields': {}}}}


def size(source):
    return len(json.dumps(vg.model_view(vg.build_vocabulary(source)), ensure_ascii=False).encode('utf-8'))


def test_each_vocabulary_limit_can_be_reached_and_stops_the_request_without_a_call():
    def infer(payload, schema):
        raise AssertionError('no call may be made')
    # The term limit alone: short terms stay far below the byte limit.
    many = one_item(f't{n}' for n in range(vg.MAX_TERMS + 1))
    assert size(many) < vg.MAX_VOCABULARY_BYTES
    result = vg.propose_vocabulary(REQUEST, many, infer, model_provenance=MODEL)
    assert result['status'] == 'clarify' and failed(result) == 'The vocabulary fits the stated budget'
    assert result['checks'][-1]['detail'].startswith(f'{vg.MAX_TERMS + 1} terms of at most {vg.MAX_TERMS}; ')
    assert len(result['vocabulary']['terms']) == vg.MAX_TERMS + 1  # reported whole, never cut
    assert result['outcome_source'] == 'application_check' and result['call_attempted'] is False
    assert 'smaller scope' in result['reason']
    # The byte limit alone: fewer terms than the term limit, with long values.
    long = one_item('w' * 200 + str(n) for n in range(60))
    assert len(vg.build_vocabulary(long)) < vg.MAX_TERMS and size(long) > vg.MAX_VOCABULARY_BYTES
    result = vg.propose_vocabulary(REQUEST, long, infer, model_provenance=MODEL)
    assert result['status'] == 'clarify' and failed(result) == 'The vocabulary fits the stated budget'
    assert f'bytes of at most {vg.MAX_VOCABULARY_BYTES}' in result['checks'][-1]['detail']
    # Exactly at the term limit the request goes on to the model.
    result, seen = run(reply([], status='no_match'), source=one_item(f't{n}' for n in range(vg.MAX_TERMS)))
    assert len(seen) == 1 and result['checks'][0]['passed'] is True


def test_the_budget_counts_the_vocabulary_and_not_the_request_or_the_prompt():
    # The longest request that the route accepts, in four-byte characters, does not fail the vocabulary budget.
    result, seen = run(reply([], status='no_match'), request='\U0001F355' * 2000)
    assert len(seen) == 1 and result['status'] == 'no_match'
    assert result['checks'][0] == {'check': 'The vocabulary fits the stated budget', 'passed': True,
                                   'detail': f'11 terms of at most {vg.MAX_TERMS}; {size(index())} bytes of at most '
                                             f'{vg.MAX_VOCABULARY_BYTES}'}


def test_a_scope_without_a_category_or_a_tag_makes_no_call():
    def infer(payload, schema):
        raise AssertionError('no call may be made')
    empty = {'sha256': 'a' * 64, 'items': {1: {'fields': {'caption': 'x'}}, 2: {'fields': {}}}}
    result = vg.propose_vocabulary(REQUEST, empty, infer, model_provenance=MODEL)
    assert result['status'] == 'no_match' and failed(result) == 'The scope has at least one category or tag'
    assert result['outcome_source'] == 'application_check' and result['call_attempted'] is False
    assert 'No model was called' in result['reason']


def test_a_failed_call_is_reported_and_never_retried():
    calls = []

    def operational(payload, schema):
        calls.append(1)
        raise ParserOperationalError('The endpoint refused the key. Check the variable and start again.')
    result = vg.propose_vocabulary(REQUEST, index(), operational, model_provenance=MODEL)
    assert result['status'] == 'error' and len(calls) == 1
    # A call was begun and failed. The text of an ordinary operational error can
    # hold provider or program text, so the page gets type names only.
    assert result['outcome_source'] == 'provider_failure' and result['call_attempted'] is True
    assert result['reason'].startswith('The call to the provider failed (ParserOperationalError).')
    assert 'refused the key' not in result['reason'] and 'reply_reason' not in result

    def unexpected(payload, schema):
        raise KeyError('internal detail that is not written for an operator')
    result = vg.propose_vocabulary(REQUEST, index(), unexpected, model_provenance=MODEL)
    assert result['status'] == 'error' and result['reason'].startswith('The call to the provider failed (KeyError).')
    assert 'internal detail' not in result['reason']


class PageSafe(ParserOperationalError):
    page_safe = True


def test_only_a_page_safe_failure_shows_its_own_sentence_bounded_and_without_control_characters():
    def refused(payload, schema):
        raise PageSafe('The endpoint refused the key.\x1b[2K Check the variable\u202e and start again. ' + 'x' * 2000)
    result = vg.propose_vocabulary(REQUEST, index(), refused, model_provenance=MODEL)
    assert result['status'] == 'error' and result['outcome_source'] == 'provider_failure'
    assert result['reason'].startswith('The endpoint refused the key. [2K Check the variable and start again. xxx')
    assert len(result['reason']) == 600 and '\x1b' not in result['reason'] and '\u202e' not in result['reason']

    def chained(payload, schema):
        try:
            raise TimeoutError('provider text that must stay off the page')
        except TimeoutError as cause:
            raise ParserOperationalError('more provider text') from cause
    result = vg.propose_vocabulary(REQUEST, index(), chained, model_provenance=MODEL)
    assert result['reason'].startswith('The call to the provider failed (ParserOperationalError, caused by TimeoutError).')
    assert 'provider text' not in result['reason']


def test_a_sealed_control_is_recomputed_from_its_terms():
    result, _ = run(lambda payload: reply([control([pick(payload['vocabulary'], 'tag', 'round'),
                                                    pick(payload['vocabulary'], 'category', 'Delta')])]))
    (selected,) = result['controls']
    sealed = {'item_ids': selected['item_ids'], 'evidence': selected['evidence'],
              'vocabulary_terms': [{k: t[k] for k in ('term_id', 'kind', 'level', 'field', 'value')}
                                   for t in selected['terms']]}
    vg.revalidate_control(sealed, index())  # unchanged: accepted
    for change in ({'item_ids': [1, 3, 7, 8]}, {'item_ids': [1, 3]},
                   {'evidence': selected['evidence'][:2]},
                   {'evidence': [*selected['evidence'][:2], {'item_id': 7, 'field': 'topic_tag', 'quote': 'round'}]},
                   {'evidence': [{**selected['evidence'][0], 'field': 'first_level_category_name', 'quote': 'Alpha'}, *selected['evidence'][1:]]},
                   {'evidence': [*selected['evidence'], {'item_id': 1, 'field': 'topic_tag', 'quote': 'red'}]},
                   {'vocabulary_terms': []},
                   {'vocabulary_terms': [{**sealed['vocabulary_terms'][0], 'value': 'absent'}]},
                   {'vocabulary_terms': [{**sealed['vocabulary_terms'][0], 'kind': 'category'}]}):
        with pytest.raises(ValueError):
            vg.revalidate_control({**sealed, **change}, index())
    # A changed source: the term lost one of its items.
    moved = index()
    moved['items'][3]['fields']['topic_tag'] = 'blue'
    with pytest.raises(ValueError, match='differ from the members of its terms'):
        vg.revalidate_control(sealed, moved)


def test_item_labels_are_the_values_that_the_vocabulary_reads():
    fields = index()['items'][1]['fields']
    assert vg.item_labels(fields) == [
        {'kind': 'category', 'level': 1, 'value': 'Alpha'}, {'kind': 'category', 'level': 2, 'value': 'Alpha minor'},
        {'kind': 'tag', 'level': None, 'value': 'red'}, {'kind': 'tag', 'level': None, 'value': 'round'}]
    assert vg.item_labels({'caption': 'no label'}) == []


def test_the_caller_keeps_its_own_data():
    source, supplied = index(), deepcopy(MODEL)

    def infer(payload, schema):
        payload['vocabulary'].clear()
        schema.clear()
        return reply([], status='no_match')
    before = deepcopy(source)
    result = vg.propose_vocabulary(REQUEST, source, infer, model_provenance=supplied)
    assert source == before and supplied == MODEL and len(result['vocabulary']['terms']) == 11
    assert vg.SCHEMA['required'] == ['status', 'reason', 'negation_resolved', 'alternatives', 'controls']


@pytest.mark.parametrize('arguments', [
    {'request': ''}, {'request': '   '}, {'request': 'x' * 2001}, {'request': None},
    {'model_provenance': {'backend': 'b', 'model': 'm'}}, {'model_provenance': {'backend': '', 'model': 'm', 'digest': 'd'}},
    {'max_fraction': 0}, {'max_fraction': .6}, {'max_fraction': True},
])
def test_invalid_arguments_are_refused_before_any_call(arguments):
    def infer(payload, schema):
        raise AssertionError('no call may be made')
    options = {'request': REQUEST, 'model_provenance': MODEL, **arguments}
    with pytest.raises(ValueError):
        vg.propose_vocabulary(options.pop('request'), index(), infer, **options)


def test_the_schema_uses_the_shared_control_choices_and_the_prompt_names_no_scenario():
    from feedctrl.semantic_review import ACTION_CHOICES
    assert vg.SCHEMA['properties']['controls']['items']['properties']['control']['enum'] == list(ACTION_CHOICES)
    assert vg.SCHEMA['properties']['controls']['maxItems'] == vg.MAX_CONTROLS == 4
    lowered = vg.PROMPT.casefold()
    assert not any(word in lowered for word in ('hungry', 'hunger', 'food', 'cooking', 'repair'))
    assert 'unsupported' in lowered and 'ambiguous' in lowered and 'no_match' in lowered
    # The prompt names the rules that the application enforces on the model's side of the contract.
    assert 'more than half of the supplied items' in lowered and 'scope_item_count' in lowered
    assert 'without control or format characters' in lowered


def test_no_prompt_of_the_language_routes_holds_a_word_of_a_bundled_example():
    import re
    from feedctrl import semantic_review, staged_induction, evidence_audit, synthetic_drafts
    prompts = {'vocabulary': vg.PROMPT, 'description': indirect_grounding.PROMPT,
               'action': semantic_review.ACTION_PROMPT, 'definition': staged_induction.DEFINITION_PROMPT,
               'membership': staged_induction.MEMBERSHIP_PROMPT, 'draft': synthetic_drafts.PROMPT}
    prompts.update({f'audit:{name}': value for name, value in vars(evidence_audit).items()
                    if name.endswith('PROMPT') and isinstance(value, str)})
    words = re.compile(r'hungr|hunger|\bfood\b|cooking|sandwich|bicycle|\bkite\b|eating|astronom|street food', re.I)
    assert {name: words.findall(text) for name, text in prompts.items() if words.search(text)} == {}
    # The sentence that an earlier revision left without a verb is whole again.
    assert 'Respect qualifiers, intersections and exclusions in the intent.' in indirect_grounding.PROMPT
