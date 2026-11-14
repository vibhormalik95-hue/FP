"""Try the bundled requests of a scenario on a model route, without a browser.

    python scripts/route_trial.py run --scenario tags
        Use the model route of model-route.json (write it with
        "python scripts/quickstart.py setup").

    python scripts/route_trial.py run --scenario tags --provider scripted
        Use the hand-written rehearsal replies. No model.

    python scripts/route_trial.py cases --scenario tags
        List the cases of a scenario. Nothing is run.

    python scripts/route_trial.py compare runs/trial-a runs/trial-b
        Put two trials of the same scenario and the same source side by side.

The trial builds the application in this process exactly as
scripts/run_demo.py builds it, and sends each bundled request of the scenario
to the application's own API. It stops each case at the first point where a
person must review. It never approves, applies or admits anything, and it
reads the applied state back after each case to record that.

For each case it records what the application made of the model's reply: the
outcome class, the controls, the chosen terms or quotations, the selected
items, the application's own checks and the raw reply. Where a hand-written
rehearsal reply exists for the same request, it also records whether the
outcome and the selection are the same as with that reply. "The same" is not
"correct": the rehearsal reply is one authored answer, not a reference label.

This is a check of a model route on exposed development requests with invented
items. It is not an accuracy study. See docs/route-trial.md.

Exit code 0: no case ended in an error. 2: at least one case ended in an
error. 1: a usage or setup problem, or a trial that cannot be used as it is:
it was interrupted, or the applied state changed or could not be read (which
must not happen). Nothing here sends email, publishes or stores a credential.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / 'scripts')):
    if entry not in sys.path:
        sys.path.insert(0, entry)

KIND = 'route trial of the Feed Control Lab'
FORMAT = 1
STATEMENTS = (
    'The requests are exposed development requests of a bundled scenario with invented items.',
    'This is a check of a model route. It is not an accuracy study.',
    'An outcome that equals the authored rehearsal reply is not proof of a correct interpretation.',
    'Each case ran one time. Nothing was approved and nothing was applied.',
)
COMPARE_STATEMENTS = (
    STATEMENTS[0],
    'This puts two checks of a model route side by side. It is not an accuracy study.',
    'Equal outcomes in two trials are not proof of a correct interpretation. '
    'Different outcomes do not show which one is right.',
    'Each case ran one time in each trial. Nothing was approved and nothing was applied.',
    'Two routes can use different model settings, for example the output limit or the sampling. '
    'This table does not correct for that.',
)
# A request key of a scenario is "<method>" or "<method>:<case>". Each method
# is one way to make a request in the page. It has its own endpoint of the
# application and a largest number of model calls for one request.
METHODS = {
    'vocabulary': {'title': 'categories and tags', 'endpoint': '/api/semantic/vocabulary/preview', 'max_calls': 1},
    'configured_model': {'title': 'item descriptions', 'endpoint': '/api/semantic/preview', 'max_calls': 2},
    'staged': {'title': 'new category, first stage', 'endpoint': '/api/semantic/definition/preview', 'max_calls': 1},
    'synthetic': {'title': 'fictional item draft', 'endpoint': '/api/synthetic/preview', 'max_calls': 1},
}
# The application's own status words. Anything else is reported as an error of
# this tool, so that a new status is never shown under a wrong name.
OUTCOMES = ('review', 'clarify', 'no_match', 'unsupported', 'duplicate', 'definition_review', 'draft_ready', 'error')
OUTCOME_WORDS = {'definition_review': 'definition for review', 'draft_ready': 'draft ready', 'no_match': 'no match'}
SCOPE = 10  # the page offers the first ten items of the starting list as the evidence scope


# Requests that were interrupted with Ctrl+C while a model call still waited.
_IN_FLIGHT = []
_leave = os._exit  # replaced in the tests


class Stop(Exception):
    """A usage or setup problem. The text is for the terminal."""


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def one_line(value, limit=700):
    text = ' '.join(str(value).split())
    return text if len(text) <= limit else text[:limit - 3] + '...'


def ascii_text(value):
    """Text that every console can print; other characters become escapes."""
    return str(value).encode('ascii', 'backslashreplace').decode('ascii')


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def launcher():
    import run_demo
    return run_demo


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------

def scenario_cases(scenario):
    """The bundled requests of a scenario, in the order of the scenario file."""
    requests = launcher().scenario_requests(scenario)
    cases = []
    for key, text in requests.items():
        method = key.split(':', 1)[0]
        if method in METHODS:
            cases.append({'case': key, 'method': method, 'text': text})
    return cases, requests.get('label') or 'Route trial'


def select_cases(scenario, wanted):
    cases, label = scenario_cases(scenario)
    if not cases:
        raise Stop(f'The scenario "{scenario}" has no bundled request that this trial can run.')
    if wanted:
        names = [name.strip() for name in wanted.split(',') if name.strip()]
        known = {case['case'] for case in cases}
        unknown = [name for name in names if name not in known]
        if unknown or not names:
            raise Stop('Unknown case: ' + ', '.join(unknown or ['(none given)'])
                       + f'. Cases of the scenario "{scenario}": ' + ', '.join(case['case'] for case in cases) + '.')
        cases = [case for case in cases if case['case'] in names]
    return cases, label


def calls_needed(cases):
    return sum(METHODS[case['method']]['max_calls'] for case in cases)


# --------------------------------------------------------------------------
# The application, built as the launcher builds it
# --------------------------------------------------------------------------

def launcher_options(**values):
    """The options of scripts/run_demo.py that ``build_app`` reads."""
    base = dict(provider='manual', scenario=None, port=None, reviewed_config=None, report=None, relay_dir=None,
                declared_model=None, transport_note=None, relay_timeout=600, max_calls=None, route_file=None,
                record_dir=None)
    base.update(values)
    return argparse.Namespace(**base)


def build_application(provider, scenario, *, route_file=None, out=None):
    """Return ``(app, summary)`` from ``run_demo.build_app``; nothing is copied from it."""
    run_demo = launcher()
    if provider == 'scripted':
        options = launcher_options(provider='scripted', scenario=scenario)
    else:
        options = launcher_options(provider='route', scenario=scenario, route_file=str(route_file),
                                   record_dir=str(out / 'route-calls'), relay_dir=str(out / 'relay'))
    try:
        app, _, summary, _ = run_demo.build_app(options)
    except SystemExit as stopped:
        # The launcher reports a setup problem this way, with a text for a person.
        raise Stop(str(stopped.code) if stopped.code not in (None, 0) else 'The application could not be built.') from None
    app.state.source_fingerprint = run_demo.source_fingerprint()
    return app, summary


def client_class():
    """The in-process HTTP client of the web framework, or a plain message when it is not installed."""
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')  # a notice of the test client about its own HTTP library
            from fastapi.testclient import TestClient
    except ImportError as error:
        raise Stop('The trial needs the test tools of this project (' + one_line(error, 120) + '). '
                   'Run: python -m pip install -e ".[test]"') from None
    return TestClient


# --------------------------------------------------------------------------
# One case
# --------------------------------------------------------------------------

def request_body(case, user, candidate_ids, label):
    method, text = case['method'], case['text']
    if method == 'vocabulary':
        return {'user_id': user, 'text': text, 'candidate_ids': candidate_ids, 'mode': 'merge'}
    if method == 'configured_model':
        return {'user_id': user, 'text': text, 'label': label, 'candidate_ids': candidate_ids,
                'backend': 'configured_model', 'action_source': 'model', 'mode': 'merge'}
    if method == 'staged':
        # In the page the person chooses the action of a new category. The first
        # stage (the definition) does not use it; the trial declares "exclude".
        return {'user_id': user, 'objective': text, 'candidate_ids': candidate_ids,
                'operation': 'exclude', 'strength': 'none', 'mode': 'merge'}
    # The page asks the person to confirm that the draft is fictional metadata
    # before it calls a model. The trial gives that confirmation. It does not
    # admit the draft to any feed.
    return {'user_id': user, 'brief': text, 'synthetic_acknowledged': True}


def applied_state(client, headers, user):
    """What is applied for this session, or ``None`` when the application does not return it."""
    groups = client.get(f'/api/semantic/groups?user_id={user}', headers=headers)
    fictional = client.get(f'/api/synthetic/items?user_id={user}', headers=headers)
    if groups.status_code != 200 or fictional.status_code != 200:
        return None
    groups, fictional = groups.json(), fictional.json()
    return {'groups': groups['groups'], 'can_undo': groups['can_undo'], 'revision': groups['revision'],
            'feed': groups['feed'], 'fictional_items': fictional['items'], 'fictional_revision': fictional['revision']}


def state_record(before, after):
    """Compare the applied state after a case with the state before it."""
    if before is None or after is None:
        # Not read is not the same as unchanged: the trial then makes no statement.
        return {'read': False, 'nothing_applied': None}
    state = {'read': True, 'applied_groups': len(after['groups']), 'can_undo': after['can_undo'],
             'feed_unchanged': after['feed'] == before['feed'],
             'revision_unchanged': (after['revision'], after['fictional_revision'])
             == (before['revision'], before['fictional_revision']),
             'fictional_items': len(after['fictional_items'])}
    state['nothing_applied'] = (state['applied_groups'] == 0 and state['can_undo'] is False and state['feed_unchanged']
                                and state['revision_unchanged'] and state['fictional_items'] == 0)
    return state


def detail_text(body):
    detail = body.get('detail') if isinstance(body, dict) else body
    if isinstance(detail, list):  # a request that the application's input rules refused
        detail = '; '.join(one_line(part.get('msg', part) if isinstance(part, dict) else part, 200) for part in detail)
    return one_line(detail if detail not in (None, '') else 'The application gave no reason.')


def raw_replies(body):
    replies = []
    for call in body.get('model_calls') or []:
        if isinstance(call, dict):
            for name in ('raw_response', 'raw_output'):
                if name in call:
                    replies.append(deepcopy(call[name]))
    return replies


def read_review(method, body):
    """The controls of a review answer, in one shape for both request routes."""
    if method == 'vocabulary':
        return [{'label': control['label'], 'operation': control['operation'], 'strength': control['strength'],
                 'intent_span': control['intent_span'], 'relation': control['relation'],
                 'terms': [{'kind': term['kind'], 'level': term['level'], 'value': term['value'],
                            'item_ids': list(term['item_ids'])} for term in control['terms']],
                 'quotations': [], 'item_ids': sorted(control['item_ids'])}
                for control in body['vocabulary']['controls']]
    proposal = body['proposal']
    return [{'label': body['groups'][-1]['label'], 'operation': proposal['action']['operation'],
             'strength': proposal['action']['strength'], 'intent_span': proposal['action']['intent_span'],
             'relation': proposal['reason'], 'terms': [],
             'quotations': [{'item_id': row['item_id'], 'field': row['field'], 'quote': row['quote']}
                            for row in proposal['evidence']],
             'item_ids': sorted(proposal['item_ids'])}]


def read_answer(method, status_code, body):
    """Return the outcome class and what the application returned for it."""
    record = failed_record(None)
    if status_code != 200 or not isinstance(body, dict):
        record['reason'] = f'HTTP {status_code}: ' + detail_text(body)
        return record
    record['raw_model_replies'] = raw_replies(body)
    if method == 'vocabulary':
        record['checks'] = deepcopy((body.get('vocabulary') or {}).get('checks'))
    if method in ('vocabulary', 'configured_model') and body.get('ready') is True:
        record['outcome'] = 'review'
        record['controls'] = read_review(method, body)
        record['selected_item_ids'] = sorted({item for control in record['controls'] for item in control['item_ids']})
        return record
    if method == 'staged' and body.get('definition_ready') is True:
        proposal = body['definition']['proposal']
        record.update(outcome='definition_review', definition={name: deepcopy(proposal[name]) for name in
                                                               ('label', 'definition', 'rationale', 'evidence')})
        return record
    if method == 'synthetic' and body.get('ready') is True:
        draft = body['draft']
        record.update(outcome='draft_ready', draft={name: draft[name] for name in
                                                    ('title', 'description', 'category_label', 'origin', 'is_synthetic')})
        return record
    status = body.get('status')
    record['reason'] = one_line(body.get('reason') or 'The application gave no reason.')
    clarification = body.get('clarification')
    if isinstance(clarification, dict):
        record['clarification'] = {name: deepcopy(clarification[name]) for name in
                                   ('model_reason', 'alternatives', 'question', 'negation_resolved')
                                   if name in clarification}
        candidate = clarification.get('candidate')
        if isinstance(candidate, dict):  # a new category with competing meanings and one primary meaning
            record['clarification']['primary_label'] = candidate.get('label')
    if status in OUTCOMES and status not in ('review', 'definition_review', 'draft_ready'):
        record['outcome'] = status
    else:
        record['reason'] = (f'The application answered with the status "{one_line(status, 60)}", '
                            'which this trial does not know. ') + record['reason']
    return record


def selection_signature(record):
    """What a review selects: the action and the items of each control, in a fixed order."""
    if record['outcome'] != 'review':
        return None
    return sorted([control['operation'], control['strength'], list(control['item_ids'])]
                  for control in record['controls'])


def send(client, url, headers, body):
    """Send one request from a helper thread and wait for its answer.

    A model call can wait for a long time: a person carries a relay request, or
    a local model is slow. The application answers inside that wait, and the
    wait cannot be stopped from outside. With the request in a helper thread,
    Ctrl+C reaches this program at once, and the finished cases can be recorded.
    """
    box = {}

    def work():
        try:
            box['response'] = client.post(url, headers=headers, json=body)
        except BaseException as problem:  # handed to the caller below
            box['problem'] = problem

    thread = threading.Thread(target=work, daemon=True, name='route-trial-request')
    thread.start()
    try:
        while thread.is_alive():
            thread.join(0.2)
    except KeyboardInterrupt:
        _IN_FLIGHT.append(thread)
        raise
    if 'problem' in box:
        raise box['problem']
    return box['response']


def failed_record(reason):
    return {'outcome': 'error', 'reason': reason, 'controls': [], 'selected_item_ids': [], 'checks': None,
            'clarification': None, 'definition': None, 'draft': None, 'raw_model_replies': []}


def run_case(client, case, user, label, receipts):
    """One request in one new session, up to the first point where a person must review."""
    method = METHODS[case['method']]
    calls_before, started = len(receipts), time.monotonic()
    http_status, candidate_ids, before, after = None, [], None, None
    session = client.post('/api/session', json={})
    if session.status_code != 201:
        record = failed_record(f'The application did not open a session (HTTP {session.status_code}).')
    else:
        headers = {'X-Session-ID': session.json()['session_id']}
        before = applied_state(client, headers, user)
        if before is None:
            record = failed_record('The application did not return its applied state, so the request was not sent.')
        else:
            candidate_ids = list(before['feed']['baseline_items'][:SCOPE])
            started = time.monotonic()
            response = send(client, method['endpoint'], headers, request_body(case, user, candidate_ids, label))
            http_status = response.status_code
            try:
                answer = response.json()
            except ValueError:
                answer = {'detail': one_line(response.text, 300)}
            try:
                record = read_answer(case['method'], http_status, answer)
            except (KeyError, TypeError, IndexError) as problem:
                # The answer of the application did not have the fields that this tool reads.
                record = failed_record('This trial could not read the answer of the application '
                                       f'({type(problem).__name__}: {one_line(problem, 120)}).')
            after = applied_state(client, headers, user)
    seconds = round(time.monotonic() - started, 3)
    used = [deepcopy(receipt) for receipt in receipts[calls_before:]]
    return {'case': case['case'], 'method': case['method'], 'method_title': method['title'],
            'endpoint': method['endpoint'], 'calls_at_most': method['max_calls'], 'request_text': case['text'],
            'request_sha256': sha256_text(case['text']), 'candidate_ids': sorted(candidate_ids),
            'http_status': http_status, 'model_calls': len(used), 'seconds': seconds,
            **record, 'selection': selection_signature(record), 'state_after': state_record(before, after),
            'provider_receipts': used}


def run_cases(app, cases, label, *, say=None):
    """Return ``(results, interrupted)``. Ctrl+C keeps the cases that are finished."""
    receipts = app.state.provider_receipts
    receipts = receipts if isinstance(receipts, list) else []
    results, interrupted = [], False
    # An internal failure of the application becomes an HTTP 500 answer, and
    # that answer becomes the outcome "error" of its case. The client is not
    # used as a context: leaving one would wait for a call that is in flight.
    client = client_class()(app, raise_server_exceptions=False)
    try:
        user = client.get('/api/users').json()[0]['user_id']
        for number, case in enumerate(cases, 1):
            if say:
                say(f'case {number} of {len(cases)}: {case["case"]} ({METHODS[case["method"]]["title"]}) ...')
            result = run_case(client, case, user, label, receipts)
            results.append(result)
            if say:
                say(f'  -> {outcome_words(result["outcome"])}; model calls: {result["model_calls"]}; '
                    f'{result["seconds"]:.1f} s')
    except KeyboardInterrupt:
        interrupted = True
    return results, interrupted


def compare_with_authored(result, authored):
    """How a result relates to the run with the hand-written rehearsal reply."""
    if authored is None or authored['outcome'] == 'error':
        # The rehearsal provider refuses every request that it has no reply for.
        return {'available': False, 'reason': 'No hand-written rehearsal reply exists for this request.'}
    both_review = result['outcome'] == 'review' and authored['outcome'] == 'review'
    return {'available': True, 'outcome': authored['outcome'], 'model_calls': authored['model_calls'],
            'selection': authored['selection'], 'selected_item_ids': authored['selected_item_ids'],
            'same_outcome': result['outcome'] == authored['outcome'],
            # The action and the items of each control. Not applicable when either side selects nothing.
            'same_selection': result['selection'] == authored['selection'] if both_review else None}


# --------------------------------------------------------------------------
# Text for a person
# --------------------------------------------------------------------------

def outcome_words(outcome):
    return OUTCOME_WORDS.get(outcome, outcome)


def selection_words(result):
    if result['outcome'] == 'review':
        parts = []
        for control in result['controls']:
            action = control['operation'] + ('' if control['strength'] == 'none' else ' ' + control['strength'])
            if control['terms']:  # existing names; the application selected every item that carries one
                names = ', '.join(f'{term["kind"]} "{term["value"]}"' for term in control['terms'])
                parts.append(f'{action} through {names}: ' + ', '.join(str(item) for item in control['item_ids']))
            else:  # one exact quotation from the description of each item
                quoted = {row['item_id']: row['quote'] for row in control['quotations']}
                parts.append(f'{action}: ' + ', '.join(
                    f'{item} (quotation "{one_line(quoted[item], 70)}")' if item in quoted else str(item)
                    for item in control['item_ids']))
        return '; '.join(parts)
    if result['outcome'] == 'definition_review':
        return 'label "' + one_line(result['definition']['label'], 90) + '"'
    if result['outcome'] == 'draft_ready':
        return 'title "' + one_line(result['draft']['title'], 90) + '"'
    if result.get('clarification') and result['clarification'].get('alternatives'):
        return f'{len(result["clarification"]["alternatives"])} alternatives; ' + one_line(result['reason'], 160)
    return one_line(result['reason'] or '', 200)


def checks_words(result):
    checks = result['checks']
    if not checks:
        return 'no list'
    failed = [check['check'] for check in checks if not check['passed']]
    text = f'{len(checks) - len(failed)} of {len(checks)} passed'
    return text + ('; failed: ' + one_line('; '.join(failed), 160) if failed else '')


def authored_words(result, provider):
    authored = result['authored']
    if not authored['available']:
        return 'no rehearsal reply'
    if provider == 'scripted':
        return 'this run is the rehearsal'
    if not authored['same_outcome']:
        return f'no (rehearsal: {outcome_words(authored["outcome"])})'
    if authored['same_selection'] is None:
        return 'same outcome'
    return 'same outcome, same selection' if authored['same_selection'] else 'same outcome, other selection'


def ascii_table(headers, rows):
    rows = [[ascii_text(cell) for cell in row] for row in rows]
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]
    line = lambda cells: '  '.join(str(cell).ljust(width) for cell, width in zip(cells, widths)).rstrip()
    return '\n'.join([line(headers), line(['-' * width for width in widths]), *(line(row) for row in rows)])


def markdown_table(headers, rows):
    cell = lambda value: str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |',
                      *('| ' + ' | '.join(cell(value) for value in row) + ' |' for row in rows)])


def identity_lines(trial):
    provider, identity = trial['provider'], trial['provider']['identity']
    if provider['kind'] == 'scripted':
        lines = ['Provider: hand-written rehearsal replies. No model.']
    else:
        lines = [f'Provider: model route; backend {identity.get("backend")}; '
                 f'model {identity.get("model")} (the name that the route declares; the application cannot attest it)']
        lines += list(provider.get('route_description') or [])
    lines.append(f'Configuration digest: {identity.get("digest")}')
    return lines


def trial_rows(trial):
    kind = trial['provider']['kind']
    return [[result['case'], result['method_title'], result['model_calls'], outcome_words(result['outcome']),
             selection_words(result), checks_words(result), authored_words(result, kind), f'{result["seconds"]:.1f}']
            for result in trial['cases']]


TRIAL_HEADERS = ['Case', 'Method in the page', 'Model calls', 'Outcome', 'Selection or reason',
                 'Application checks', 'Same as the authored rehearsal reply', 'Seconds']


def error_lines(trial):
    lines = []
    for result in trial['cases']:
        if result['outcome'] == 'error':
            categories = sorted({str(receipt['error_category']) for receipt in result.get('provider_receipts') or []
                                 if isinstance(receipt, dict) and receipt.get('error_category')})
            lines.append(f'{result["case"]}: {result["reason"]}'
                         + (f' [route error: {", ".join(categories)}]' if categories else ''))
    return lines


def state_words(totals):
    if totals['nothing_applied']:
        return 'nothing was applied.'
    if totals['state_changed']:
        return '**THE STATE CHANGED. This is a defect; do not use this trial.**'
    return '**the state could not be read for every case, so this trial does not state that nothing was applied.**'


def trial_markdown(trial):
    totals = trial['totals']
    lines = [f'# Route trial: scenario `{trial["scenario"]}`', '',
             *('- ' + statement for statement in trial['statements']), '',
             f'- Started (UTC): {trial["started_utc"]}. Finished (UTC): {trial["finished_utc"]}.',
             f'- Source fingerprint: `{trial["source_fingerprint"]}`',
             *('- ' + line for line in identity_lines(trial)),
             f'- Cases: {totals["cases"]}. Model calls: {totals["model_calls"]}. Cases that ended in an error: {totals["errors"]}.',
             '- The applied state was read back after each case: ' + state_words(totals),
             *(['- **The trial was interrupted.** Only the finished cases are in this record.'] if trial.get('interrupted') else []),
             '', markdown_table(TRIAL_HEADERS, trial_rows(trial)), '']
    errors = error_lines(trial)
    if errors:
        lines += ['## Cases that ended in an error', '', *('- ' + line for line in errors), '']
    lines += ['## How to read the table', '',
              '- **Outcome** is the class that the application gave to the reply: a review for a person, a clarification, '
              'no match, unsupported, a definition for review, a draft, or an error. A clarification can be the right answer to a request.',
              '- **Selection** lists the action, the existing category or tag names or the quotations, and the items. '
              'The application selected the items; the model chose the names or quotations.',
              '- **Application checks** are mechanical. A passed check shows that names, identifiers and quotations exist in the item data. '
              'It does not show that the meaning is right.',
              '- **Same as the authored rehearsal reply** compares with one hand-written answer for the same request. '
              '"Same selection" means the same action and the same items in each control. It is not a correctness label.',
              '', 'The complete record, with every raw reply, is in `trial.json` in this folder.', '']
    return '\n'.join(lines)


def print_trial(trial, say):
    say('')
    if not trial['cases']:
        say('No case finished.')
        return
    say(ascii_table(['Case', 'Method in the page', 'Calls', 'Outcome', 'Same as authored rehearsal reply', 'Seconds'],
                    [[row[0], row[1], row[2], row[3], row[6], row[7]] for row in trial_rows(trial)]))
    say('')
    for result in trial['cases']:
        say(f'{result["case"]}: {selection_words(result)}')
        if result['checks']:
            say(f'  application checks: {checks_words(result)}')
    errors = error_lines(trial)
    if errors:
        say('')
        say('Cases that ended in an error (the text says what to do):')
        for line in errors:
            say('  ' + line)
    say('')
    for statement in trial['statements']:
        say(statement)


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def prepare_route(route_file, cases):
    """Read the route file and stop before any call when the trial cannot run."""
    from feedctrl import model_routes
    import getpass
    # ``(configuration, key)``. The key is only kept in memory.
    try:
        config = model_routes.load_config(route_file)
    except model_routes.RouteError as error:
        raise Stop(model_routes.ascii_text(error) + '\nRun "python scripts/quickstart.py setup" first, '
                                                    'or use --provider scripted for the rehearsal replies.') from None
    needed = calls_needed(cases)
    if config['max_calls'] < needed:
        raise Stop(f'The chosen cases ({len(cases)}) can need up to {needed} model calls. The route file allows '
                   f'{config["max_calls"]} calls for one run ("max_calls"). No call was made. '
                   'Raise "max_calls" in the route file (the relay route allows at most 10), '
                   'or run fewer cases with --cases.')
    try:
        key = model_routes.resolve_api_key(config, ask=getpass.getpass if sys.stdin.isatty() else None)
    except model_routes.RouteError as error:
        raise Stop(model_routes.ascii_text(error)) from None
    return config, key


def relay_lines(relay, timeout):
    tool = 'python scripts/relay_tools.py'
    return [f'Relay folder: {relay}',
            'For each request N, in a second window:',
            f'  {tool} show "{relay}" N request-N.txt',
            '  give the whole text of request-N.txt to the model in a new conversation',
            '  save the reply (the JSON object only) as answer-N.json',
            f'  {tool} check "{relay}" N answer-N.json',
            f'  {tool} deliver "{relay}" N answer-N.json',
            f'The trial waits for each reply as the app does (up to {timeout:g} s for each request).']


def run(args, out=print):
    run_demo = launcher()
    if args.scenario not in run_demo.SCENARIOS:
        raise Stop('Unknown scenario. Scenarios: ' + ', '.join(sorted(run_demo.SCENARIOS)) + '.')
    if args.provider == 'scripted' and args.route_file:
        raise Stop('Give --route-file or --provider scripted, not both.')
    provider = args.provider or 'route'
    cases, label = select_cases(args.scenario, args.cases)
    client_class()  # stop here, before anything is created, when the client is not installed
    del _IN_FLIGHT[:]
    started_utc = utc()
    folder = Path(args.out) if args.out else ROOT / 'runs' / f'trial-{args.scenario}-{time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())}'
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise Stop(f'{folder} exists and is not an empty folder. Give a new folder, so that no record is overwritten.')

    key, config, route_file, added_variable, clean = None, None, None, None, str
    if provider == 'route':
        from feedctrl import model_routes
        route_file = Path(args.route_file) if args.route_file else ROOT / 'model-route.json'
        config, key = prepare_route(route_file, cases)
        clean = model_routes.scrubber(key)
        name = model_routes.needs_api_key(config)
        if name and key and not (os.environ.get(name) or '').strip():
            # The key came from the hidden prompt. The launcher reads it from the
            # environment of this process; it is removed again below.
            os.environ[name] = key
            added_variable = name
    say = lambda text='': out(ascii_text(clean(text)))

    try:
        existed = folder.exists()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            app, summary = build_application(provider, args.scenario, route_file=route_file, out=folder)
        except Stop:
            if not existed and not any(folder.iterdir()):
                folder.rmdir()  # a trial that never started leaves no folder behind
            raise
        identity = deepcopy(summary.get('identity') or {})
        fingerprint = run_demo.source_fingerprint()
        say(f'Route trial of scenario "{args.scenario}": {len(cases)} case{"" if len(cases) == 1 else "s"}, '
            f'up to {calls_needed(cases)} model calls.')
        say(f'Source fingerprint: {fingerprint}')
        description = list(summary.get('route') or [])
        for line in (description if provider == 'route' else ['Provider: hand-written rehearsal replies. No model.']):
            say(line)
        if provider == 'route' and config['route'] == 'relay':
            for line in relay_lines(summary.get('relay_dir') or folder / 'relay', config['timeout_seconds']):
                say(line)
        say(f'Records: {folder}')
        say('Nothing is approved or applied. Each case stops where a person must review.')
        say('')

        results, interrupted = run_cases(app, cases, label, say=say)
        if provider == 'route':
            # The same cases with the hand-written rehearsal replies, in a second
            # application of the same source. It has no model and no allowance.
            baseline_app, _ = build_application('scripted', args.scenario)
            finished = [case for case in cases if case['case'] in {result['case'] for result in results}]
            baseline = {result['case']: result for result in run_cases(baseline_app, finished, label)[0]}
        else:
            baseline = {result['case']: result for result in results}
        for result in results:
            result['authored'] = compare_with_authored(result, baseline.get(result['case']))
    finally:
        if added_variable:
            os.environ.pop(added_variable, None)

    outcomes = {}
    for result in results:
        outcomes[result['outcome']] = outcomes.get(result['outcome'], 0) + 1
    states = [result['state_after']['nothing_applied'] for result in results]
    untouched, changed = all(state is True for state in states), any(state is False for state in states)
    errors = outcomes.get('error', 0)
    # 1: the trial cannot be used as it is. 2: a case ended in an error. 0: neither.
    exit_code = 1 if not untouched or interrupted else 2 if errors else 0
    trial = {'kind': KIND, 'format': FORMAT, 'statements': list(STATEMENTS), 'scenario': args.scenario,
             'started_utc': started_utc, 'finished_utc': utc(), 'source_fingerprint': fingerprint,
             'provider': {'kind': provider, 'identity': identity, 'route_description': description},
             'environment': {'python': platform.python_version(), 'system': f'{platform.system()} {platform.release()}'},
             'cases_chosen': [case['case'] for case in cases], 'interrupted': interrupted,
             'cases': results,
             'totals': {'cases': len(results), 'model_calls': sum(result['model_calls'] for result in results),
                        'errors': errors, 'outcomes': outcomes, 'nothing_applied': untouched, 'state_changed': changed},
             'exit_code': exit_code}
    # One more pass through the scrubber: no credential belongs in a record.
    text = clean(json.dumps(trial, indent=2, ensure_ascii=True, default=str))
    trial = json.loads(text)
    (folder / 'trial.json').write_text(text + '\n', encoding='utf-8', newline='\n')
    (folder / 'trial.md').write_text(clean(trial_markdown(trial)), encoding='utf-8', newline='\n')

    print_trial(trial, say)
    say('')
    say(f'Written: {folder / "trial.json"} and {folder / "trial.md"}')
    if changed:
        say('THE APPLIED STATE CHANGED DURING A CASE. This must not happen. Do not use this trial; report it.')
    elif not untouched:
        say('The applied state could not be read for every case. '
            'This trial does not state that nothing was applied.')
    elif interrupted:
        say(f'Interrupted after {len(results)} of {len(cases)} cases. The finished cases are recorded.')
    elif errors:
        say(f'{errors} of {len(results)} cases ended in an error.')
    else:
        say('No case ended in an error.')
    if any(thread.is_alive() for thread in _IN_FLIGHT):
        # The interrupted model call still waits in its helper thread, and
        # Python would wait for it at the end. The records are written, so the
        # program stops here without that wait.
        say('A model call was still waiting when the trial was interrupted. The program stops now.')
        sys.stdout.flush()
        sys.stderr.flush()
        _leave(exit_code)
    return exit_code


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------

def list_cases(args, out=print):
    run_demo = launcher()
    if args.scenario not in run_demo.SCENARIOS:
        raise Stop('Unknown scenario. Scenarios: ' + ', '.join(sorted(run_demo.SCENARIOS)) + '.')
    cases, _ = select_cases(args.scenario, None)
    out(ascii_text(ascii_table(['Case', 'Method in the page', 'Model calls at most', 'Request'],
                               [[case['case'], METHODS[case['method']]['title'], METHODS[case['method']]['max_calls'],
                                 one_line(case['text'], 110)] for case in cases])))
    out(f'All cases together can need up to {calls_needed(cases)} model calls.')
    return 0


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------

def load_trial(folder):
    path = Path(folder)
    path = path / 'trial.json' if path.is_dir() else path
    if not path.is_file():
        raise Stop(f'{folder} holds no trial.json. Give the folder of a finished trial.')
    try:
        trial = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeDecodeError):
        raise Stop(f'{path} is not valid JSON.') from None
    if not isinstance(trial, dict) or trial.get('kind') != KIND or not isinstance(trial.get('cases'), list):
        raise Stop(f'{path} is not the record of a route trial.')
    return trial


def comparison(first, second):
    if first['scenario'] != second['scenario']:
        raise Stop(f'The two trials ran different scenarios ("{first["scenario"]}" and "{second["scenario"]}"). '
                   'A comparison needs the same requests.')
    if first['source_fingerprint'] != second['source_fingerprint']:
        raise Stop('The two trials ran different source files (fingerprints '
                   f'{str(first["source_fingerprint"])[:12]}... and {str(second["source_fingerprint"])[:12]}...). '
                   'A comparison needs the same application, requests and items. Run both trials from the same files.')
    left = {result['case']: result for result in first['cases']}
    right = {result['case']: result for result in second['cases']}
    rows = []
    for case in [*left, *(name for name in right if name not in left)]:
        a, b = left.get(case), right.get(case)
        if a is None or b is None:
            same_outcome = same_selection = 'not run in both'
        else:
            same_outcome = 'yes' if a['outcome'] == b['outcome'] else 'no'
            both_review = a['outcome'] == 'review' and b['outcome'] == 'review'
            same_selection = ('yes' if a['selection'] == b['selection'] else 'no') if both_review else 'not applicable'
        cell = lambda result, read: 'not run' if result is None else read(result)
        rows.append([case, cell(a, lambda r: outcome_words(r['outcome'])), cell(b, lambda r: outcome_words(r['outcome'])),
                     same_outcome, same_selection,
                     cell(a, lambda r: f'{r["seconds"]:.1f}'), cell(b, lambda r: f'{r["seconds"]:.1f}')])
    return rows


def comparison_summary(rows):
    both = [row for row in rows if row[3] in ('yes', 'no')]
    reviews = [row for row in both if row[4] in ('yes', 'no')]
    return (f'Cases that both trials ran: {len(both)}. Same outcome: {sum(row[3] == "yes" for row in both)}. '
            f'Both gave a review: {len(reviews)}; same items and action in {sum(row[4] == "yes" for row in reviews)} of them.')


COMPARE_HEADERS = ['Case', 'Outcome A', 'Outcome B', 'Same outcome', 'Same items and action', 'Seconds A', 'Seconds B']


def compare(args, out=print):
    first, second = load_trial(args.first), load_trial(args.second)
    rows = comparison(first, second)
    target = Path(args.out) if args.out else None
    if target is not None and target.exists():
        raise Stop(f'{target} exists. Give a new file name, so that no record is overwritten.')
    header = [f'Scenario: {first["scenario"]}. Source fingerprint: {first["source_fingerprint"]}']
    for letter, folder, trial in (('A', args.first, first), ('B', args.second, second)):
        header.append(f'Trial {letter}: {folder} (started {trial["started_utc"]} UTC)')
        header += ['  ' + line for line in identity_lines(trial)]
    for line in header:
        out(ascii_text(line))
    out('')
    out(ascii_text(ascii_table(COMPARE_HEADERS, rows)))
    out('')
    out(comparison_summary(rows))
    out('"Same items and action" compares two reviews: the same action and the same items in each control.')
    for statement in COMPARE_STATEMENTS:
        out(statement)
    if target is not None:
        lines = [f'# Two route trials of scenario `{first["scenario"]}`', '',
                 *('- ' + statement for statement in COMPARE_STATEMENTS), '',
                 *('- ' + line.strip() if not line.startswith('  ') else '  - ' + line.strip() for line in header), '',
                 markdown_table(COMPARE_HEADERS, rows), '', comparison_summary(rows), '',
                 '"Same items and action" compares two reviews: the same action and the same items in each control. '
                 'It says nothing about which review is right.', '']
        target.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        out(ascii_text(f'Written: {target}'))
    return 0


# --------------------------------------------------------------------------

def main(argv=None, out=print):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    steps = parser.add_subparsers(dest='step', required=True)
    step = steps.add_parser('run', help='send the bundled requests of a scenario to the application through a provider')
    step.add_argument('--scenario', default='tags')
    step.add_argument('--route-file', help='the model route to use; default: model-route.json')
    step.add_argument('--provider', choices=('route', 'scripted'),
                      help='"scripted" uses the hand-written rehearsal replies instead of a model route')
    step.add_argument('--out', help='a new folder for the records; default: a new folder under runs/')
    step.add_argument('--cases', help='run only these cases, separated by commas')
    step.set_defaults(action=run)
    step = steps.add_parser('cases', help='list the cases of a scenario')
    step.add_argument('--scenario', default='tags')
    step.set_defaults(action=list_cases)
    step = steps.add_parser('compare', help='put two trials of the same scenario and source side by side')
    step.add_argument('first')
    step.add_argument('second')
    step.add_argument('--out', help='also write the comparison to this new Markdown file')
    step.set_defaults(action=compare)
    try:
        args = parser.parse_args(argv)
    except SystemExit as stopped:  # argparse printed its own message; usage problems are exit code 1
        return 0 if stopped.code == 0 else 1
    try:
        return args.action(args, out=out)
    except Stop as stopped:
        print(ascii_text(stopped), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
