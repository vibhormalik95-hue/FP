"""Carry relay requests to the Claude Code CLI on this computer.

    python scripts/relay_claude_cli.py RELAY_DIR --calls 3
        [--model claude-fable-5-2] [--effort max] [--claude PATH]
        [--timeout 600] [--max-budget-usd 2] [--allow-other-models]

Start the app first with "--provider relay --relay-dir RELAY_DIR". Then start
this script in a second window. For each request it runs the CLI one time in
print mode, with the request text on standard input. It checks that the reply
is one JSON object that matches the schema of the request, and delivers the
reply unchanged. A new category needs --calls 3. An indirect request needs
--calls 2.

What this script is. It is an operator of the relay: it does by program what
a person does with "relay_tools.py show" and "relay_tools.py deliver". It is
not the reviewed Claude Code CLI connection ("--provider personal-cli"): it
has no reviewed configuration, no check of the executable, and no process
containment. You are responsible for the CLI on your computer, for the
account that it is signed in to, and for the usage that it causes.

What it never does. It never calls the CLI a second time for the same
request. It never edits a reply. If a call fails, or the reply is not an
acceptable answer, it stops and leaves the request open. You can then answer
that request by hand with relay_tools.py, or stop the app.

It writes cli-call-000N.json for each call: times, exit code, flags, hashes,
the token usage and the model names that the CLI reported. It stores no
request text there. A reply that was not delivered is kept as
cli-reply-000N.not-delivered.txt.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relay_tools  # noqa: E402

# The same environment names that the reviewed adapter passes on. No API key is passed.
ENV_ALLOW = ('SYSTEMROOT', 'WINDIR', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH',
             'HOME', 'PATH', 'PATHEXT', 'COMSPEC', 'TEMP', 'TMP', 'TMPDIR')
ENV_SET = {'CLAUDE_CODE_MAX_RETRIES': '0', 'CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES': '0',
           'CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK': '1', 'CLAUDE_CODE_MAX_OUTPUT_TOKENS': '16384',
           'DISABLE_AUTOUPDATER': '1', 'CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK': '1'}
APPEND = 'Reply with exactly one JSON object and nothing else. Do not use a code fence. Do not use tools.'


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def cli_arguments(executable, model, effort, budget):
    """Flags for one print-mode call. The request text goes to standard input, never into a flag."""
    flags = ['-p', '--safe-mode']
    if Path(executable).suffix.lower() not in ('.cmd', '.bat'):
        # An empty argument is not reliable through a Windows command shim.
        flags += ['--tools', '']
    flags += ['--disallowedTools', 'mcp__*', '--no-chrome', '--no-session-persistence',
              '--permission-mode', 'dontAsk', '--max-turns', '1', '--model', model, '--effort', effort,
              '--max-budget-usd', str(budget), '--output-format', 'json', '--append-system-prompt', APPEND]
    return flags


def strict_result_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON constant')
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError('nonfinite JSON number')
        return parsed
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float)


def failure_output_summary(stdout, stderr):
    """Retain bounded structural evidence, never arbitrary diagnostic text.

    Output may contain prompts, credentials, or private model text. Store only
    lengths/digests and recognized terminal fields. This is evidence, not an
    acceptance decision or an automatic retry classification.
    """
    summary = {}
    for name, raw in (('stdout', stdout), ('stderr', stderr)):
        if raw is None:
            summary[name] = {'available': False}
            continue
        if isinstance(raw, str):
            raw = raw.encode('utf-8', 'replace')
        item = {'available': True, 'bytes': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest()}
        summary[name] = item
        if len(raw) > 65536:
            item['json_status'] = 'over_limit'
            continue
        try:
            envelope = strict_result_json(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError, RecursionError):
            item['json_status'] = 'invalid'
            continue
        if not isinstance(envelope, dict):
            item['json_status'] = 'not_object'
            continue
        item['json_status'] = 'object'
        terminal = {}
        choices = {
            'type': ('result',),
            'subtype': ('success', 'error_during_execution', 'error_max_turns',
                        'error_max_budget_usd', 'error_max_structured_output_retries'),
            'stop_reason': ('end_turn', 'refusal', 'max_tokens', 'tool_use',
                            'stop_sequence', 'pause_turn'),
        }
        for key, allowed in choices.items():
            if key in envelope:
                value = envelope[key]
                terminal[key] = value if isinstance(value, str) and value in allowed else 'unrecognized'
        if type(envelope.get('is_error')) is bool:
            terminal['is_error'] = envelope['is_error']
        turns = envelope.get('num_turns')
        if type(turns) is int and 0 <= turns <= 1000000:
            terminal['num_turns'] = turns
        item['terminal'] = terminal
    return summary


def terminal_result_problem(envelope):
    """The local one-turn operator only delivers an explicit normal completion."""
    if (envelope.get('type') != 'result' or envelope.get('subtype') != 'success'
            or envelope.get('is_error') is not False):
        return 'the CLI did not report a successful result'
    if envelope.get('stop_reason') != 'end_turn':
        return 'the CLI did not report a supported normal stop reason'
    if type(envelope.get('num_turns')) is not int or envelope['num_turns'] != 1:
        return 'the CLI did not report exactly one turn'
    return None


def claim_attempt(spool, ordinal, request_sha256):
    """An immutable exclusive claim survives all failures and process exits."""
    marker = spool / f'cli-attempt-{ordinal:04d}.json'
    for existing in (spool / f'cli-call-{ordinal:04d}.json',
                     spool / f'response-{ordinal:04d}.json'):
        if existing.exists():
            raise SystemExit(f'Request {ordinal} already has a receipt or response; no CLI call was made.')
    try:
        with marker.open('x', encoding='utf-8') as handle:
            json.dump({'ordinal': ordinal, 'request_sha256': request_sha256,
                       'claimed_utc': utc()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise SystemExit(f'Request {ordinal} was previously claimed; no CLI call was made.')


def one_call(spool, ordinal, executable, args):
    request = relay_tools.wait_for_request(spool, ordinal, args.wait)
    text = relay_tools.render(request).encode('utf-8')
    flags = cli_arguments(executable, args.model, args.effort, args.max_budget_usd)
    env = {name: os.environ[name] for name in ENV_ALLOW if name in os.environ}
    env.update(ENV_SET)
    record = {'ordinal': ordinal, 'request_sha256': request['request_sha256'], 'started_utc': utc(),
              'cli': Path(executable).name, 'flags': flags, 'stdin_sha256': hashlib.sha256(text).hexdigest(),
              'requested_model': args.model, 'requested_effort': args.effort, 'delivered': False}
    record_path = spool / f'cli-call-{ordinal:04d}.json'

    def finish(reason=None, reply=None):
        record.update(finished_utc=utc(), seconds=round(time.monotonic() - started, 1), not_delivered_because=reason)
        record_path.write_text(json.dumps(record, indent=2), encoding='utf-8')
        if reason:
            if reply is not None:
                (spool / f'cli-reply-{ordinal:04d}.not-delivered.txt').write_bytes(reply)
            raise SystemExit(f'Request {ordinal} was NOT delivered: {reason}.\n'
                             'The request is still open. Answer it by hand with relay_tools.py, or stop the app.')

    claim_attempt(spool, ordinal, request['request_sha256'])
    print(f'[{utc()}] request {ordinal}: calling the CLI (limit {args.timeout} s) ...', flush=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='relay-cli-') as workdir:
        try:
            done = subprocess.run([executable, *flags], input=text, capture_output=True,
                                  timeout=args.timeout, cwd=workdir, env=env)
        except subprocess.TimeoutExpired as error:
            record['failure_output'] = failure_output_summary(error.stdout, error.stderr)
            finish(f'the CLI did not finish within {args.timeout} s')
        except OSError as error:
            finish(f'the CLI could not be started ({error.__class__.__name__})')
    record.update(exit_code=done.returncode, stdout_sha256=hashlib.sha256(done.stdout).hexdigest(),
                  stdout_bytes=len(done.stdout))
    if done.returncode != 0:
        record['failure_output'] = failure_output_summary(done.stdout, done.stderr)
        finish(f'the CLI ended with exit code {done.returncode}; see bounded failure_output in the receipt')
    try:
        envelope = strict_result_json(done.stdout.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        finish('the CLI output was not one JSON result', done.stdout)
    if not isinstance(envelope, dict):
        finish('the CLI output was not a JSON result object', done.stdout)
    usage = envelope.get('usage') if isinstance(envelope.get('usage'), dict) else {}
    models = sorted(envelope['modelUsage']) if isinstance(envelope.get('modelUsage'), dict) else []
    record.update(result={key: envelope.get(key) for key in ('type', 'subtype', 'is_error', 'num_turns', 'stop_reason',
                                                             'duration_ms', 'total_cost_usd')},
                  usage={key: value for key, value in usage.items() if type(value) is int},
                  reported_models=models)
    reply = envelope.get('result')
    reply_bytes = reply.encode('utf-8') if isinstance(reply, str) else None
    terminal_problem = terminal_result_problem(envelope)
    if terminal_problem:
        finish(terminal_problem, reply_bytes)
    if reply_bytes is None:
        finish('the CLI result holds no text')
    if models != [args.model] and not args.allow_other_models:
        finish(f'the CLI reported the models {models}, not only {args.model} (use --allow-other-models to accept)', reply_bytes)
    reason = relay_tools.problem(spool, ordinal, reply_bytes)
    if reason:
        finish(reason, reply_bytes)
    answer = spool / f'cli-answer-{ordinal:04d}.json'
    answer.write_bytes(reply_bytes)
    relay_tools.deliver(spool, ordinal, answer)
    record.update(delivered=True, answer_sha256=hashlib.sha256(reply_bytes).hexdigest())
    finish()
    print(f'[{utc()}] request {ordinal}: delivered after {record["seconds"]} s; models reported: {models}', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('relay_dir')
    parser.add_argument('--calls', type=int, required=True, help='3 for a new category, 2 for an indirect request')
    parser.add_argument('--model', default='claude-fable-5-2')
    parser.add_argument('--effort', default='max', choices=('low', 'medium', 'high', 'max'))
    parser.add_argument('--claude', help='path of the Claude Code CLI; default: "claude" on PATH')
    parser.add_argument('--timeout', type=float, default=600, help='seconds for one CLI call')
    parser.add_argument('--wait', type=float, default=3600, help='seconds to wait for the next request')
    parser.add_argument('--max-budget-usd', type=float, default=2.0, help='the CLI\'s own estimate limit for one call')
    parser.add_argument('--allow-other-models', action='store_true')
    args = parser.parse_args(argv)
    spool = Path(args.relay_dir)
    if not spool.is_dir():
        raise SystemExit('The relay folder does not exist. Start the app with --provider relay first.')
    if not 1 <= args.calls <= 3:
        raise SystemExit('--calls must be 1, 2 or 3')
    executable = args.claude or shutil.which('claude')
    if not executable or not Path(executable).is_file():
        raise SystemExit('The Claude Code CLI was not found. Give its full path with --claude.')
    print(f'Operator for {spool}: {args.calls} request(s), model {args.model}, effort {args.effort}.')
    print('One CLI call for each request. No retry. Press Ctrl+C to stop.', flush=True)
    for ordinal in range(1, args.calls + 1):
        if (spool / f'response-{ordinal:04d}.json').exists():
            print(f'request {ordinal}: a reply was already delivered; skipped')
            continue
        print(f'[{utc()}] waiting for request {ordinal} ...', flush=True)
        one_call(spool, ordinal, str(executable), args)
    print('All requests were delivered. Do the reviews in the page.')


if __name__ == '__main__':
    main()
