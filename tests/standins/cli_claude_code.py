"""A stand-in for the Claude Code CLI in print mode. It is not a model and not the CLI.

It prints the same kind of JSON result object that the CLI documentation
describes for ``claude -p --output-format json``. It answers with the
hand-written rehearsal replies. A route starts it through a small launcher file
(``common.write_launcher``), because a route starts a program by its path.

Behaviour is set through environment variables, which the route must name in
"pass_environment": STANDIN_REPLIES (scripted or echo-ok), STANDIN_FAIL (one
fault name), STANDIN_UNKNOWN (an option to refuse as unknown), STANDIN_LOG (a
file that receives the arguments, the names of the environment variables and
the process number), STANDIN_REPORT_MODEL (the model name that the result
reports in place of the requested one).
"""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

VALUE_FLAGS = ('--output-format', '--model', '--max-turns', '--permission-mode', '--tools', '--disallowedTools',
               '--effort', '--max-budget-usd', '--json-schema', '--append-system-prompt', '--system-prompt', '--settings')
PLAIN_FLAGS = ('-p', '--print', '--safe-mode', '--no-session-persistence', '--no-chrome', '--bare', '--verbose')
FAULTS = ('not_signed_in', 'max_turns', 'budget', 'exit_code', 'no_envelope', 'other_model', 'extra_model',
          'fallback_model', 'no_model_usage', 'slow', 'no_structured', 'duplicate_structured', 'nan_structured',
          'duplicate_envelope', 'warning_line', 'usage_limit', 'overloaded_with_sign_in_words', *common.REPLY_FAULTS)
# Result texts of a failed call. They are stand-in texts in the style of the CLI, not quotations.
USAGE_LIMIT = "You've hit your usage limit. Your limit resets 3pm. Wait, or sign in to another account."
OVERLOADED = 'API Error: 529 {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}'


def parse(argv):
    """Return ``(options, positional)`` or raise ``ValueError`` with the unknown option."""
    options, positional, index = {}, [], 0
    unknown = os.environ.get('STANDIN_UNKNOWN')
    while index < len(argv):
        part = argv[index]
        if part == unknown or (part.startswith('-') and part not in VALUE_FLAGS and part not in PLAIN_FLAGS):
            raise ValueError(part)
        if part in VALUE_FLAGS:
            options[part] = argv[index + 1] if index + 1 < len(argv) else ''
            index += 2
        elif part in PLAIN_FLAGS:
            options[part] = True
            index += 1
        else:
            positional.append(part)
            index += 1
    return options, positional


def main(argv):
    fail = os.environ.get('STANDIN_FAIL') or None
    log = os.environ.get('STANDIN_LOG')
    if log:
        with open(log, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps({'argv': argv, 'environment_names': sorted(os.environ), 'cwd': os.getcwd(),
                                     'cwd_entries': sorted(os.listdir('.')), 'pid': os.getpid(),
                                     'started': time.time()}) + '\n')
    if argv[:1] in (['--version'], ['-v']):
        print('0.0.0 (stand-in for the Claude Code CLI; not a model)')
        return 0
    if argv[:2] == ['auth', 'status']:
        signed_in = fail != 'not_signed_in'
        print(json.dumps({'loggedIn': signed_in, 'authMethod': 'stand-in' if signed_in else 'none'}))
        return 0 if signed_in else 1
    try:
        options, _ = parse(argv)
    except ValueError as unknown:
        sys.stderr.write(f"error: unknown option '{unknown}'\n")
        return 1
    if '-p' not in options and '--print' not in options:
        sys.stderr.write(common.NOTE + ': only print mode (-p) is implemented\n')
        return 2
    prompt = sys.stdin.buffer.read().decode('utf-8')
    model = os.environ.get('STANDIN_REPORT_MODEL') or options.get('--model', common.DEFAULT_MODEL)
    if fail == 'slow':
        time.sleep(float(os.environ.get('STANDIN_DELAY', '30')))
    if fail == 'exit_code':
        sys.stderr.write('stand-in failure: boom\n')
        return 7
    if fail == 'no_envelope':
        print('plain text, not a result object')
        return 0
    envelope = {'type': 'result', 'subtype': 'success', 'is_error': False, 'num_turns': 1, 'stop_reason': 'end_turn',
                'duration_ms': 1, 'session_id': 'stand-in-not-a-model', 'total_cost_usd': 0.0,
                'usage': {'input_tokens': len(prompt) // 4, 'output_tokens': 1},
                'modelUsage': {model: {'inputTokens': len(prompt) // 4, 'outputTokens': 1, 'costUSD': 0.0}}}
    if fail == 'not_signed_in':
        envelope.update(is_error=True, result='Not logged in. Please run /login')
        print(json.dumps(envelope))
        return 1
    if fail in ('usage_limit', 'overloaded_with_sign_in_words'):
        if fail == 'overloaded_with_sign_in_words':
            sys.stderr.write('[debug] OAuth token refreshed; not logged in to the browser extension\n')
        envelope.update(is_error=True, subtype='success', result=USAGE_LIMIT if fail == 'usage_limit' else OVERLOADED)
        print(json.dumps(envelope))
        return 1
    if fail in ('max_turns', 'budget'):
        envelope.update(is_error=True, subtype='error_max_turns' if fail == 'max_turns' else 'error_max_budget_usd')
        print(json.dumps(envelope))
        return 1
    try:
        payload, schema = common.from_prompt(prompt)
    except ValueError:
        envelope.update(is_error=True, result=common.NOTE + ': the input does not have the form that the routes send')
        print(json.dumps(envelope))
        return 1
    reply = common.reply_for(payload, schema, os.environ.get('STANDIN_REPLIES', 'scripted'))
    if reply is None:
        envelope.update(is_error=True, result=common.NO_REPLY)
        print(json.dumps(envelope))
        return 1
    envelope['result'] = common.faulty(json.dumps(reply, ensure_ascii=False), fail)
    if '--json-schema' in options and fail != 'no_structured':
        envelope['structured_output'] = {'unexpected': True} if fail == 'wrong_schema' else reply
    if fail == 'warning_line':
        print('Warning: a newer version of this stand-in is available.')
    if fail in ('duplicate_structured', 'nan_structured', 'duplicate_envelope'):
        text = json.dumps(envelope)
        if fail == 'duplicate_structured':     # the structured output repeats a key: the last one is true
            text = text[:-1] + ', "structured_output": {"ok": false, "ok": true}}'
        elif fail == 'nan_structured':
            text = text[:-1] + ', "structured_output": {"ok": true, "n": NaN}}'
        else:                                  # two "result" fields
            text = text[:-1] + ', "result": "{\\"ok\\": false}"}'
        print(text)
        return 0
    if fail == 'other_model':
        envelope['modelUsage'] = {'another-model': {}}
    elif fail == 'extra_model':
        envelope['modelUsage']['a-small-helper-model'] = {}
    elif fail == 'fallback_model':   # another model wrote most of the answer
        envelope['modelUsage'][model]['outputTokens'] = 3
        envelope['modelUsage']['claude-fallback-model'] = {'inputTokens': 10, 'outputTokens': 1300, 'costUSD': 0.0}
    elif fail == 'no_model_usage':
        del envelope['modelUsage']
    print(json.dumps(envelope))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
