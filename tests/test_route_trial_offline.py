"""The route trial, offline.

scripts/route_trial.py sends the bundled requests of a scenario to the
application in process and records what the application made of each reply.
Here the replies are the hand-written rehearsal replies, either from the
scripted provider or from a stand-in server behind a model route. These tests
show that the tool reports outcomes, stops before a review, applies nothing
and keeps credentials out of its records. They are not evidence about a model.
"""
import getpass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from feedctrl import model_routes  # noqa: E402
import demo_scripted_replies  # noqa: E402
import quickstart  # noqa: E402
import relay_tools  # noqa: E402
import route_trial  # noqa: E402
import run_demo  # noqa: E402
from standins import common, openai_compatible_server  # noqa: E402
from standins.route_state import fresh_route_state  # noqa: E402,F401  (autouse)

KEY = 'sk-trial-0123456789abcdefSECRET'
MODEL = common.DEFAULT_MODEL
FOOD = [61001, 61002, 61003, 61009]
# case -> (outcome, model calls, selection: action and items of each control)
TAGS = {
    'vocabulary': ('review', 1, [['exclude', 'none', FOOD]]),
    'vocabulary:literal': ('review', 1, [['exclude', 'none', [61004, 61005]]]),
    'vocabulary:mixed': ('review', 1, [['boost', 'standard', [61007, 61008]], ['exclude', 'none', FOOD]]),
    'vocabulary:ambiguous': ('clarify', 1, None),
    'vocabulary:unsupported': ('unsupported', 1, None),
    'vocabulary:negated': ('clarify', 0, None),
    'vocabulary:no_match': ('no_match', 1, None),
    'configured_model': ('review', 2, [['exclude', 'none', [61004]]]),
    'synthetic': ('draft_ready', 1, None),
}


def run_trial(capsys, tmp_path, *arguments, name='trial'):
    """Run the tool as its command line does and return what it left behind."""
    out = tmp_path / name
    code = route_trial.main(['run', *arguments, '--out', str(out)])
    captured = capsys.readouterr()
    record = json.loads((out / 'trial.json').read_text(encoding='utf-8')) if (out / 'trial.json').is_file() else None
    return code, record, captured.out, captured.err, out


def route_file(tmp_path, config, name='model-route.json'):
    path = tmp_path / name
    model_routes.save_config(path, config)
    return str(path)


def by_case(record):
    return {result['case']: result for result in record['cases']}


def chat_requests(server):
    return [request for request in server.requests if request['path'] == '/v1/chat/completions']


def everything_written(folder):
    return b''.join(path.read_bytes() for path in sorted(Path(folder).rglob('*')) if path.is_file())


# --------------------------------------------------------------------------
# The rehearsal replies: each scenario, outcome classes, nothing applied
# --------------------------------------------------------------------------

def test_the_rehearsal_replies_give_every_request_of_the_tags_scenario_its_class(capsys, tmp_path):
    code, record, output, errors, out = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted')
    assert code == 0 and errors == '' and output.isascii()
    assert [result['case'] for result in record['cases']] == list(TAGS)   # the order of the scenario file
    for name, (outcome, calls, selection) in TAGS.items():
        result = by_case(record)[name]
        assert (result['outcome'], result['model_calls'], result['selection']) == (outcome, calls, selection), name
        assert result['state_after'] == {'read': True, 'applied_groups': 0, 'can_undo': False, 'feed_unchanged': True,
                                         'revision_unchanged': True, 'fictional_items': 0, 'nothing_applied': True}
        assert result['request_text'] == run_demo.scenario_requests('tags')[name]
        assert result['authored']['available'] and result['authored']['same_outcome']
    cases = by_case(record)
    # A review names what was chosen and through what; the application selected the items.
    (control,) = cases['vocabulary']['controls']
    assert [(term['kind'], term['value']) for term in control['terms']] == [('category', 'Cooking'), ('tag', 'street food')]
    assert control['intent_span'] == 'all the stuff that makes me hungry' and cases['vocabulary']['selected_item_ids'] == FOOD
    assert cases['configured_model']['controls'][0]['quotations'] == [
        {'item_id': 61004, 'field': 'caption', 'quote': 'between bites of a sandwich'}]
    # The application's own checks travel with the record, also for a request that it answers itself.
    assert len(cases['vocabulary']['checks']) == 16 and all(check['passed'] for check in cases['vocabulary']['checks'])
    assert [check['passed'] for check in cases['vocabulary:negated']['checks']] == [True, False]
    assert cases['vocabulary:negated']['raw_model_replies'] == [] and cases['configured_model']['checks'] is None
    assert len(cases['vocabulary:ambiguous']['clarification']['alternatives']) == 3
    assert cases['vocabulary']['raw_model_replies'][0]['status'] == 'propose'
    assert cases['synthetic']['draft']['is_synthetic'] is True
    assert cases['synthetic']['draft']['title'].endswith('(authored rehearsal)')
    assert record['totals'] == {'cases': 9, 'model_calls': 9, 'errors': 0, 'nothing_applied': True,
                                'state_changed': False, 'outcomes': {
                                    'review': 4, 'clarify': 2, 'unsupported': 1, 'no_match': 1, 'draft_ready': 1}}
    assert record['kind'] == route_trial.KIND and record['exit_code'] == 0 and record['scenario'] == 'tags'
    assert record['cases_chosen'] == list(TAGS) and record['interrupted'] is False
    assert record['source_fingerprint'] == run_demo.source_fingerprint()
    assert record['provider']['kind'] == 'scripted' and record['provider']['identity']['live_model'] is False
    assert record['statements'] == list(route_trial.STATEMENTS)
    text = (out / 'trial.md').read_text(encoding='utf-8')
    assert all(statement in text and statement in output for statement in route_trial.STATEMENTS)
    assert 'hand-written rehearsal replies. No model.' in text and 'this run is the rehearsal' in text
    assert 'nothing was applied' in text and '| vocabulary:mixed | categories and tags | 1 | review |' in text
    assert 'correct' not in output.lower().replace('not proof of a correct interpretation', '')
    assert sorted(path.name for path in out.iterdir()) == ['trial.json', 'trial.md']   # no route, so no call records


@pytest.mark.parametrize('scenario,case,outcome,calls', [
    ('hunger', 'configured_model', 'review', 2), ('category', 'staged', 'definition_review', 1)])
def test_the_two_older_scenarios_stop_at_their_first_review(capsys, tmp_path, scenario, case, outcome, calls):
    code, record, output, _, _ = run_trial(capsys, tmp_path, '--scenario', scenario, '--provider', 'scripted')
    (result,) = record['cases']
    assert code == 0 and (result['case'], result['outcome'], result['model_calls']) == (case, outcome, calls)
    assert result['state_after']['nothing_applied'] and record['totals']['nothing_applied']
    if scenario == 'hunger':
        assert result['selection'] == [['exclude', 'none', [81001, 81003, 81006]]]
        assert 'exclude: 81001 (quotation "prepares an edible tomato-and-pasta dinner")' in output
    else:
        # Only the definition is proposed. Classification needs a person's approval first, so it is not run.
        assert result['definition']['label'].endswith('(authored rehearsal)') and result['selection'] is None
        assert result['selected_item_ids'] == [] and 'definition for review' in output


def test_the_trial_sends_the_request_that_the_bundled_scenario_pins():
    # The same body that the page sends for the pinned request, with the scope in any order.
    for scenario, method in (('hunger', 'configured_model'), ('category', 'staged')):
        pinned = json.loads((run_demo.SCENARIOS[scenario] / 'app-preview.json').read_text(encoding='utf-8'))
        (case,), label = route_trial.scenario_cases(scenario)
        assert case['method'] == method
        assert route_trial.request_body(case, 1, pinned['candidate_ids'], label) == pinned


def test_cases_lists_the_cases_and_runs_nothing(capsys):
    assert route_trial.main(['cases', '--scenario', 'tags']) == 0
    output = capsys.readouterr().out
    assert all(name in output for name in TAGS) and 'up to 10 model calls' in output and output.isascii()
    assert route_trial.calls_needed(route_trial.scenario_cases('hunger')[0]) == 2
    assert route_trial.calls_needed(route_trial.scenario_cases('category')[0]) == 1


# --------------------------------------------------------------------------
# A model route (the model end is a stand-in server with the same replies)
# --------------------------------------------------------------------------

def test_a_route_is_tried_on_the_same_requests_and_compared_with_the_rehearsal_reply(capsys, tmp_path):
    with openai_compatible_server.make_server(replies='scripted') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL})
        code, record, output, errors, out = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', path)
        sent = chat_requests(server)
    assert code == 0 and errors == '' and output.isascii()
    # Nine calls reached the route. The comparison run with the rehearsal replies made none.
    assert len(sent) == 9 and record['totals']['model_calls'] == 9
    for name, (outcome, calls, selection) in TAGS.items():
        result = by_case(record)[name]
        assert (result['outcome'], result['model_calls'], result['selection']) == (outcome, calls, selection), name
        assert result['authored'] == {'available': True, 'outcome': outcome, 'model_calls': calls,
                                      'selection': selection, 'selected_item_ids': result['selected_item_ids'],
                                      'same_outcome': True, 'same_selection': None if selection is None else True}
        assert result['state_after']['nothing_applied']
        assert [receipt['outcome'] for receipt in result['provider_receipts']] == ['parsed_transport_only'] * calls
    assert record['provider']['kind'] == 'route' and record['provider']['identity']['backend'] == 'openai-compatible-chat'
    assert record['provider']['route_description'][0] == 'Route: openai-compatible'
    assert record['provider']['identity']['route']['model'] == MODEL
    assert 'same outcome, same selection' in output and 'same as the authored' not in output.lower().replace(
        'same as authored rehearsal reply', '')
    # The route's own records of each call are in the trial folder.
    assert sorted(path.name for path in (out / 'route-calls').iterdir()) == [
        f'call-000{n}-{part}' for n in range(1, 10) for part in ('receipt.json', 'request.json', 'response.txt')]
    text = (out / 'trial.md').read_text(encoding='utf-8')
    assert 'Provider: model route; backend openai-compatible-chat' in text and 'cannot attest' in text
    assert 'Same as the authored rehearsal reply' in text and 'It is not a correctness label.' in text


def test_another_selection_than_the_rehearsal_reply_is_reported_as_other_not_as_wrong(capsys, tmp_path, monkeypatch):
    # A reply that passes every check but chooses one name only: the tag, not the category.
    original = demo_scripted_replies.lookup

    def narrower(payload, schema):
        reply = original(payload, schema)
        if payload.get('request') == run_demo.scenario_requests('tags')['vocabulary'] and reply and reply.get('controls'):
            reply = json.loads(json.dumps(reply))
            reply['controls'][0]['terms'] = [term for term in reply['controls'][0]['terms'] if term['value'] == 'street food']
        return reply

    with openai_compatible_server.make_server(replies='scripted') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL})
        monkeypatch.setattr(demo_scripted_replies, 'lookup', narrower)
        # The comparison run must use the unchanged rehearsal reply, as a real trial does.
        build = route_trial.build_application

        def build_with_original_rehearsal(provider, scenario, **options):
            if provider == 'scripted':
                monkeypatch.setattr(demo_scripted_replies, 'lookup', original)
            return build(provider, scenario, **options)

        monkeypatch.setattr(route_trial, 'build_application', build_with_original_rehearsal)
        code, record, output, _, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', path,
                                               '--cases', 'vocabulary')
    (result,) = record['cases']
    assert code == 0 and result['outcome'] == 'review' and result['selected_item_ids'] == [61003]
    assert result['authored']['same_outcome'] is True and result['authored']['same_selection'] is False
    assert result['authored']['selected_item_ids'] == FOOD
    assert 'same outcome, other selection' in output and 'wrong' not in output.lower()


@pytest.mark.parametrize('fault,category,words', [
    ('unauthorized', 'authentication', ('HTTP 401', 'api_key_env')),
    ('fenced', 'reply_not_json', ('Markdown code fence', 'structured-output setting')),
    ('truncated', 'reply_truncated', ('output limit', 'max_output_tokens'))])
def test_a_failing_route_gives_exit_code_2_and_a_line_that_says_what_to_do(capsys, tmp_path, fault, category, words):
    with openai_compatible_server.make_server(replies='scripted', fail=fault) as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL})
        code, record, output, _, out = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', path)
    cases = by_case(record)
    assert code == 2 and record['exit_code'] == 2 and output.isascii()
    # The request that the application answers itself needs no model, so it does not fail.
    assert cases['vocabulary:negated']['outcome'] == 'clarify' and cases['vocabulary:negated']['model_calls'] == 0
    failed = [result for result in record['cases'] if result['case'] != 'vocabulary:negated']
    assert all(result['outcome'] == 'error' and result['model_calls'] == 1 for result in failed)
    assert record['totals']['errors'] == 8 and record['totals']['nothing_applied']
    assert all(result['authored']['same_outcome'] is False for result in failed)
    # The description request stops at its first failed call: the second call is not made.
    assert cases['configured_model']['http_status'] == 502 and cases['vocabulary']['http_status'] == 200
    for result in failed:
        assert [receipt['error_category'] for receipt in result['provider_receipts']] == [category]
        assert all(word in result['reason'] for word in words), result['reason']
    assert 'Cases that ended in an error (the text says what to do):' in output
    assert f'[route error: {category}]' in output and '8 of 9 cases ended in an error.' in output
    text = (out / 'trial.md').read_text(encoding='utf-8')
    assert '## Cases that ended in an error' in text and all(word in text for word in words)


def test_a_small_allowance_stops_the_trial_before_any_call(capsys, tmp_path):
    with openai_compatible_server.make_server(replies='scripted') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL,
                                     'max_calls': 3})
        code, record, output, errors, out = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', path)
        assert code == 1 and record is None and not out.exists() and server.requests == []
        assert 'can need up to 10 model calls' in errors and 'allows 3 calls' in errors and 'No call was made' in errors
        assert '--cases' in errors and 'max_calls' in errors and errors.isascii()
        # Fewer cases fit the same allowance. The description request counts as two calls.
        code, record, _, _, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', path,
                                          '--cases', 'vocabulary:literal,configured_model', name='fits')
        assert code == 0 and [result['case'] for result in record['cases']] == ['vocabulary:literal', 'configured_model']
        assert len(chat_requests(server)) == 3
        code, _, _, errors, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', path,
                                          '--cases', 'vocabulary,vocabulary:mixed,configured_model', name='too-many')
        assert code == 1 and 'can need up to 4 model calls' in errors and len(chat_requests(server)) == 3


def test_the_relay_route_prints_its_commands_and_waits_for_each_reply(capsys, tmp_path):
    out = tmp_path / 'trial'
    path = route_file(tmp_path, {'route': 'relay', 'declared_model': 'stand-in: a test loop, not a model',
                                 'transport_note': 'a thread writes the hand-written rehearsal reply', 'timeout_seconds': 30})
    problems = []

    def operator():
        # What a person does by hand: read request N, save an answer file, deliver it with the relay tool.
        try:
            for number in (1, 2):
                request = relay_tools.wait_for_request(out / 'relay', number, wait=20)
                reply = demo_scripted_replies.lookup({'system': request['system'], **request['payload']}, request['schema'])
                answer = tmp_path / f'answer-{number}.json'
                answer.write_text(json.dumps(reply), encoding='utf-8')
                relay_tools.deliver(out / 'relay', number, answer)
        except BaseException as problem:  # shown by the assertion below instead of a silent wait
            problems.append(repr(problem))

    worker = threading.Thread(target=operator, daemon=True)
    worker.start()
    code = route_trial.main(['run', '--scenario', 'hunger', '--route-file', path, '--out', str(out)])
    worker.join(timeout=5)
    output = capsys.readouterr().out
    record = json.loads((out / 'trial.json').read_text(encoding='utf-8'))
    (result,) = record['cases']
    assert problems == [] and code == 0
    assert (result['outcome'], result['model_calls'], result['authored']['same_selection']) == ('review', 2, True)
    assert record['provider']['identity']['backend'] == 'operator-relay-file-queue'
    assert f'Relay folder: {out / "relay"}' in output and 'relay_tools.py deliver' in output
    assert 'The trial waits for each reply as the app does (up to 30 s for each request).' in output
    assert output.index('relay_tools.py deliver') < output.index('case 1 of 1')   # the commands come before the wait
    assert sorted(path.name for path in (out / 'relay').iterdir()) == [
        f'{kind}-000{n}.json' for kind in ('receipt', 'request', 'response') for n in (1, 2)]
    assert not (out / 'route-calls').exists()


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------

def test_no_credential_reaches_any_output_even_when_the_provider_repeats_it(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv('TRIAL_TEST_KEY', KEY)
    with openai_compatible_server.make_server(replies='scripted', fail='echo_key') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL,
                                     'api_key_env': 'TRIAL_TEST_KEY'})
        code, record, output, errors, out = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', path)
        sent = chat_requests(server)
    # The key did travel to the endpoint, in the header only, and the endpoint did repeat it.
    assert code == 2 and sent and all(request['headers']['authorization'] == 'Bearer ' + KEY for request in sent)
    assert by_case(record)['vocabulary']['outcome'] == 'error'
    assert 'TRIAL_TEST_KEY' in output                      # the name of the variable is not a secret
    written = everything_written(out)
    assert len(written) > 10000 and KEY.encode() not in written and KEY[8:].encode() not in written
    assert KEY not in output + errors and KEY not in Path(path).read_text(encoding='utf-8')
    assert os.environ['TRIAL_TEST_KEY'] == KEY             # a variable that the person set is left alone


def test_a_key_from_the_hidden_prompt_is_used_and_then_removed_from_the_environment(capsys, tmp_path, monkeypatch):
    monkeypatch.delenv('TRIAL_TEST_KEY', raising=False)
    asked = []
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True, raising=False)
    monkeypatch.setattr(getpass, 'getpass', lambda prompt='': asked.append(prompt) or KEY)
    with openai_compatible_server.make_server(replies='scripted') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL,
                                     'api_key_env': 'TRIAL_TEST_KEY'})
        code, _, output, errors, out = run_trial(capsys, tmp_path, '--scenario', 'hunger', '--route-file', path)
        sent = chat_requests(server)
    assert code == 0 and len(asked) == 1 and 'TRIAL_TEST_KEY' in asked[0]   # one prompt, not one for each step
    assert [request['headers']['authorization'] for request in sent] == ['Bearer ' + KEY] * 2
    assert 'TRIAL_TEST_KEY' not in os.environ
    assert KEY.encode() not in everything_written(out) and KEY not in output + errors


def test_a_missing_key_or_route_file_stops_before_any_call(capsys, tmp_path, monkeypatch):
    monkeypatch.delenv('TRIAL_TEST_KEY', raising=False)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False, raising=False)
    with openai_compatible_server.make_server(replies='scripted') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL,
                                     'api_key_env': 'TRIAL_TEST_KEY'})
        code, record, _, errors, out = run_trial(capsys, tmp_path, '--scenario', 'hunger', '--route-file', path)
        assert code == 1 and record is None and not out.exists() and server.requests == []
        assert 'TRIAL_TEST_KEY is not set' in errors
    code, _, _, errors, out = run_trial(capsys, tmp_path, '--scenario', 'hunger', '--route-file', str(tmp_path / 'none.json'))
    assert code == 1 and not out.exists()
    assert 'does not exist' in errors and 'quickstart.py setup' in errors and '--provider scripted' in errors


# --------------------------------------------------------------------------
# Usage problems and the invariant
# --------------------------------------------------------------------------

def test_usage_problems_are_exit_code_1_with_a_plain_message(capsys, tmp_path):
    code, _, _, errors, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted', '--cases', 'mixed')
    assert code == 1 and 'Unknown case: mixed' in errors and 'vocabulary:mixed' in errors
    code, _, _, errors, _ = run_trial(capsys, tmp_path, '--scenario', 'not-a-scenario', '--provider', 'scripted')
    assert code == 1 and 'Unknown scenario' in errors and 'tags' in errors
    code, _, _, errors, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted',
                                      '--route-file', 'model-route.json')
    assert code == 1 and 'not both' in errors
    used = tmp_path / 'used'
    used.mkdir()
    (used / 'old.txt').write_text('x', encoding='utf-8')
    code, _, _, errors, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted', name='used')
    assert code == 1 and 'not an empty folder' in errors and sorted(path.name for path in used.iterdir()) == ['old.txt']
    assert route_trial.main(['run', '--no-such-option']) == 1 and route_trial.main(['compare', 'one']) == 1
    capsys.readouterr()
    assert route_trial.main(['--help']) == 0 and 'run' in capsys.readouterr().out


def test_a_changed_applied_state_is_reported_as_a_defect_with_exit_code_1(capsys, tmp_path, monkeypatch):
    # The application does not change its state on a preview. If it ever did, the trial must say so loudly.
    read, reads = route_trial.applied_state, []

    def changed_after_the_request(client, headers, user):
        state = read(client, headers, user)
        reads.append(1)
        return {**state, 'groups': [{'label': 'applied by a defect'}]} if len(reads) % 2 == 0 else state

    monkeypatch.setattr(route_trial, 'applied_state', changed_after_the_request)
    code, record, output, _, out = run_trial(capsys, tmp_path, '--scenario', 'hunger', '--provider', 'scripted')
    assert code == 1 and record['exit_code'] == 1 and record['totals']['nothing_applied'] is False
    assert record['totals']['state_changed'] is True and record['cases'][0]['state_after']['applied_groups'] == 1
    assert 'THE APPLIED STATE CHANGED DURING A CASE' in output
    assert 'THE STATE CHANGED' in (out / 'trial.md').read_text(encoding='utf-8')


def test_a_state_that_cannot_be_read_back_is_not_reported_as_unchanged(capsys, tmp_path, monkeypatch):
    read, reads = route_trial.applied_state, []

    def unreadable_after_the_request(client, headers, user):
        reads.append(1)
        return None if len(reads) % 2 == 0 else read(client, headers, user)

    monkeypatch.setattr(route_trial, 'applied_state', unreadable_after_the_request)
    code, record, output, _, out = run_trial(capsys, tmp_path, '--scenario', 'hunger', '--provider', 'scripted')
    (result,) = record['cases']
    assert code == 1 and result['outcome'] == 'review' and result['state_after'] == {'read': False, 'nothing_applied': None}
    assert record['totals']['nothing_applied'] is False and record['totals']['state_changed'] is False
    assert 'could not be read for every case' in output and 'THE APPLIED STATE CHANGED' not in output
    assert 'does not state that nothing was applied' in (out / 'trial.md').read_text(encoding='utf-8')
    # Not readable before the request: the request is not sent at all.
    monkeypatch.setattr(route_trial, 'applied_state', lambda client, headers, user: None)
    code, record, _, _, _ = run_trial(capsys, tmp_path, '--scenario', 'hunger', '--provider', 'scripted', name='second')
    (result,) = record['cases']
    assert code == 1 and result['outcome'] == 'error' and result['model_calls'] == 0 and result['http_status'] is None
    assert 'the request was not sent' in result['reason']


def test_an_interrupted_trial_keeps_the_finished_cases(capsys, tmp_path, monkeypatch):
    run_one, seen = route_trial.run_case, []

    def interrupt_at_the_third(client, case, user, label, receipts):
        seen.append(case['case'])
        if len(seen) == 3:
            raise KeyboardInterrupt
        return run_one(client, case, user, label, receipts)

    monkeypatch.setattr(route_trial, 'run_case', interrupt_at_the_third)
    code, record, output, _, out = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted')
    assert code == 1 and record['interrupted'] is True and record['exit_code'] == 1
    assert [result['case'] for result in record['cases']] == ['vocabulary', 'vocabulary:literal']
    assert record['cases_chosen'] == list(TAGS) and record['totals']['nothing_applied'] is True
    assert 'Interrupted after 2 of 9 cases. The finished cases are recorded.' in output
    assert 'The trial was interrupted.' in (out / 'trial.md').read_text(encoding='utf-8')


def test_ctrl_c_during_a_waiting_model_call_records_the_finished_cases_and_stops(capsys, tmp_path, monkeypatch):
    # A relay request that nobody answers. Ctrl+C must not wait for it.
    path = route_file(tmp_path, {'route': 'relay', 'declared_model': 'nobody answers in this test',
                                 'transport_note': 'no reply is delivered', 'timeout_seconds': 60})
    left = []
    monkeypatch.setattr(route_trial, '_leave', left.append)
    out = tmp_path / 'trial'

    def press_ctrl_c_when_the_request_waits():
        # Only when the request file exists is the trial inside its wait, where Ctrl+C is expected.
        for _ in range(1000):   # up to 50 s on a slow or busy computer
            if (out / 'relay' / 'request-0001.json').is_file():
                time.sleep(0.3)
                signal.raise_signal(signal.SIGINT)
                return
            time.sleep(0.05)

    started = time.monotonic()
    threading.Thread(target=press_ctrl_c_when_the_request_waits, daemon=True).start()
    try:
        code = route_trial.main(['run', '--scenario', 'tags', '--route-file', path, '--out', str(out),
                                 '--cases', 'vocabulary:negated,vocabulary:no_match'])
    except KeyboardInterrupt:
        pytest.fail('the interrupt escaped the trial')
    waited = time.monotonic() - started
    output = capsys.readouterr().out
    record = json.loads((out / 'trial.json').read_text(encoding='utf-8'))
    assert code == 1 and waited < 45                              # well before the relay gives up at 60 s
    assert model_routes.stop_requested()                          # the waiting model call was told to end
    for thread in route_trial._IN_FLIGHT:
        thread.join(2)
    assert not any(thread.is_alive() for thread in route_trial._IN_FLIGHT)
    assert record['interrupted'] is True and record['cases_chosen'] == ['vocabulary:negated', 'vocabulary:no_match']
    assert [(result['case'], result['outcome']) for result in record['cases']] == [('vocabulary:negated', 'clarify')]
    assert 'Interrupted after 1 of 2 cases. The finished cases are recorded.' in output
    # The stop usually ends the wait before the records are written; then no forced end is needed.
    assert left == [] or (left == [1] and 'A model call was still waiting when the trial was interrupted.' in output)
    assert (out / 'relay' / 'request-0001.json').is_file()        # the open request stays on disk for the record
    for thread in route_trial._IN_FLIGHT:                         # let the abandoned call end before the next test
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in route_trial._IN_FLIGHT)


def test_an_answer_with_other_fields_than_expected_is_an_error_of_its_case(capsys, tmp_path, monkeypatch):
    # A review answer without the fields that the trial reads: the tool and the application do not match.
    monkeypatch.setattr(route_trial, 'read_review', lambda method, body: body['no_such_field'])
    code, record, _, _, _ = run_trial(capsys, tmp_path, '--scenario', 'hunger', '--provider', 'scripted')
    (result,) = record['cases']
    assert code == 2 and result['outcome'] == 'error' and 'could not read the answer' in result['reason']
    assert 'KeyError' in result['reason'] and result['state_after']['nothing_applied'] is True


def test_a_defect_in_a_provider_is_an_error_of_its_case_not_a_crash(capsys, tmp_path, monkeypatch):
    def broken(payload, schema):
        raise RuntimeError('defect in a provider')

    monkeypatch.setattr(demo_scripted_replies, 'lookup', broken)
    code, record, output, _, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted',
                                           '--cases', 'vocabulary,vocabulary:negated')
    cases = by_case(record)
    assert code == 2 and cases['vocabulary']['outcome'] == 'error' and cases['vocabulary']['state_after']['nothing_applied']
    assert cases['vocabulary:negated']['outcome'] == 'clarify'
    # With no working rehearsal reply there is nothing to compare with, and the record says so.
    assert cases['vocabulary']['authored'] == {'available': False,
                                               'reason': 'No hand-written rehearsal reply exists for this request.'}
    assert 'no rehearsal reply' in output


def test_a_defect_in_the_application_is_an_error_of_its_case_not_a_crash(capsys, tmp_path, monkeypatch):
    from feedctrl import vocabulary_grounding

    def broken(index):
        raise RuntimeError('defect in the application')

    # The application answers HTTP 500 for an exception that it does not expect.
    monkeypatch.setattr(vocabulary_grounding, 'build_vocabulary', broken)
    code, record, output, _, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted',
                                           '--cases', 'vocabulary,configured_model')
    cases = by_case(record)
    assert code == 2 and record['totals']['errors'] == 1 and record['totals']['nothing_applied']
    assert cases['vocabulary']['outcome'] == 'error' and cases['vocabulary']['http_status'] == 500
    assert cases['vocabulary']['reason'].startswith('HTTP 500: ') and cases['vocabulary']['model_calls'] == 0
    assert cases['configured_model']['outcome'] == 'review'          # the next case still runs, in its own session
    assert '1 of 2 cases ended in an error.' in output


def test_text_for_the_terminal_is_ascii_and_a_long_reason_is_kept_in_the_record():
    table = route_trial.ascii_table(['Case', 'Outcome'], [['café — résumé', '美食']])
    assert table.isascii() and '\\xe9' in table and '\\u7f8e' in table
    assert route_trial.markdown_table(['A'], [['x | y\nz']]) == '| A |\n| --- |\n| x \\| y z |'
    assert route_trial.one_line('a\n  b\tc') == 'a b c' and len(route_trial.one_line('x' * 900)) == 700


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------

def test_compare_puts_two_trials_side_by_side_and_refuses_what_cannot_be_compared(capsys, tmp_path):
    _, first, _, _, a = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted', name='a')
    with openai_compatible_server.make_server(replies='scripted') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL})
        run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', path, name='b')
    b = tmp_path / 'b'
    report = tmp_path / 'side-by-side.md'
    assert route_trial.main(['compare', str(a), str(b), '--out', str(report)]) == 0
    output = capsys.readouterr().out
    assert output.isascii() and 'Trial A: ' + str(a) in output and 'backend openai-compatible-chat' in output
    assert ('Cases that both trials ran: 9. Same outcome: 9. Both gave a review: 4; '
            'same items and action in 4 of them.') in output
    assert all(statement in output for statement in route_trial.COMPARE_STATEMENTS)
    rows = {line.split()[0]: line.split() for line in output.splitlines() if line.split() and line.split()[0] in TAGS}
    assert set(rows) == set(TAGS)
    assert rows['vocabulary:mixed'][1:5] == ['review', 'review', 'yes', 'yes']
    assert ' '.join(rows['vocabulary:ambiguous'][1:6]) == 'clarify clarify yes not applicable'
    text = report.read_text(encoding='utf-8')
    assert '| vocabulary | review | review | yes | yes |' in text and 'It says nothing about which review is right.' in text
    assert route_trial.main(['compare', str(a), str(b), '--out', str(report)]) == 1    # never overwrite
    assert 'exists' in capsys.readouterr().err
    assert route_trial.main(['compare', str(a / 'trial.json'), str(b)]) == 0            # the file itself is accepted too
    capsys.readouterr()

    # A different scenario: other requests.
    run_trial(capsys, tmp_path, '--scenario', 'hunger', '--provider', 'scripted', name='hunger')
    assert route_trial.main(['compare', str(a), str(tmp_path / 'hunger')]) == 1
    assert 'different scenarios ("tags" and "hunger")' in capsys.readouterr().err
    # A different source: other application, requests or items.
    other = tmp_path / 'other-source'
    other.mkdir()
    changed = dict(first, source_fingerprint='0' * 64)
    (other / 'trial.json').write_text(json.dumps(changed), encoding='utf-8')
    assert route_trial.main(['compare', str(a), str(other)]) == 1
    errors = capsys.readouterr().err
    assert 'different source files' in errors and '000000000000...' in errors and 'same files' in errors
    # Not a trial at all.
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert route_trial.main(['compare', str(a), str(empty)]) == 1 and 'holds no trial.json' in capsys.readouterr().err
    (empty / 'trial.json').write_text('{"kind": "something else"}', encoding='utf-8')
    assert route_trial.main(['compare', str(a), str(empty)]) == 1 and 'not the record of a route trial' in capsys.readouterr().err
    (empty / 'trial.json').write_text('{not json', encoding='utf-8')
    assert route_trial.main(['compare', str(a), str(empty)]) == 1 and 'not valid JSON' in capsys.readouterr().err


def test_compare_marks_a_case_that_one_trial_did_not_run_and_two_different_selections(capsys, tmp_path):
    _, first, _, _, a = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted', name='a')
    _, _, _, _, part = run_trial(capsys, tmp_path, '--scenario', 'tags', '--provider', 'scripted',
                                 '--cases', 'vocabulary,vocabulary:ambiguous', name='part')
    # The second trial chose one name only for the same request, and gave another class to the second one.
    changed = json.loads((part / 'trial.json').read_text(encoding='utf-8'))
    changed['cases'][0]['selection'] = [['exclude', 'none', [61003]]]
    changed['cases'][1]['outcome'] = 'no_match'
    (part / 'trial.json').write_text(json.dumps(changed), encoding='utf-8')
    rows = {row[0]: row[1:] for row in route_trial.comparison(first, changed)}
    assert rows['vocabulary'][:4] == ['review', 'review', 'yes', 'no']
    assert rows['vocabulary:ambiguous'][:4] == ['clarify', 'no match', 'no', 'not applicable']
    # The fifth column is the seconds of the first trial: a measured time, so only its form is fixed.
    assert rows['synthetic'][:4] + rows['synthetic'][5:] == ['draft ready', 'not run', 'not run in both',
                                                             'not run in both', 'not run']
    assert float(rows['synthetic'][4]) >= 0
    assert route_trial.comparison_summary(route_trial.comparison(first, changed)) == (
        'Cases that both trials ran: 2. Same outcome: 1. Both gave a review: 1; same items and action in 0 of them.')
    assert route_trial.main(['compare', str(a), str(part)]) == 0 and 'not run' in capsys.readouterr().out


# --------------------------------------------------------------------------
# The command lines
# --------------------------------------------------------------------------

def test_quickstart_try_is_the_run_step_of_the_trial(capsys, tmp_path):
    out = tmp_path / 'from-quickstart'
    with pytest.raises(SystemExit) as stopped:
        quickstart.main(['try', '--scenario', 'hunger', '--provider', 'scripted', '--out', str(out)])
    assert stopped.value.code == 0 and json.loads((out / 'trial.json').read_text())['scenario'] == 'hunger'
    assert 'No case ended in an error.' in capsys.readouterr().out
    with pytest.raises(SystemExit) as stopped:
        quickstart.main(['try', '--scenario', 'tags', '--provider', 'scripted', '--cases', 'nothing'])
    assert stopped.value.code == 1
    assert 'try' in quickstart.__doc__ and 'docs/route-trial.md' in quickstart.__doc__


def test_the_script_runs_from_a_plain_command_line_with_the_documented_exit_codes(tmp_path):
    script = [sys.executable, str(ROOT / 'scripts' / 'route_trial.py')]
    started = time.monotonic()
    done = subprocess.run([*script, 'run', '--scenario', 'hunger', '--provider', 'scripted', '--out', str(tmp_path / 'cli')],
                          capture_output=True, text=True, cwd=str(tmp_path), timeout=120)
    assert done.returncode == 0 and done.stderr == '' and done.stdout.isascii(), done.stderr
    assert 'No case ended in an error.' in done.stdout and (tmp_path / 'cli' / 'trial.md').is_file()
    # It ran the files of this tree, from another working folder.
    record = json.loads((tmp_path / 'cli' / 'trial.json').read_text(encoding='utf-8'))
    assert record['source_fingerprint'] == run_demo.source_fingerprint()
    wrong = subprocess.run([*script, 'run', '--scenario', 'hunger', '--provider', 'scripted', '--cases', 'x'],
                           capture_output=True, text=True, cwd=str(tmp_path), timeout=120)
    assert wrong.returncode == 1 and 'Unknown case: x' in wrong.stderr and wrong.stdout == ''
    assert time.monotonic() - started < 120
