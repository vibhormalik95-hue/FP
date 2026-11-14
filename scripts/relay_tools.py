"""Helpers for the relay provider of scripts/run_demo.py.

    python scripts/relay_tools.py show RELAY_DIR N OUT.txt
        Wait for request N and write it as the exact text to give a model:
        the instruction, the response schema, then the input as JSON.

    python scripts/relay_tools.py check RELAY_DIR N ANSWER.json
        Say whether the app would accept this answer file for request N.
        Nothing is delivered.

    python scripts/relay_tools.py deliver RELAY_DIR N ANSWER.json [--force]
        Give the model's answer file to the app, byte for byte, with an atomic
        rename so that the app never reads a partly written file.

The helpers copy bytes. They do not edit, trim or repair a reply. The answer
must be one JSON object with nothing around it, and it must match the schema of
the request. "deliver" first makes the same checks as "check" and refuses a
file that the app would reject. A refusal does not spend the call: copy the
model's reply again, without the text around the JSON object. If the model's
reply itself is not a valid answer, deliver it with --force. The app then
rejects it, and that rejection is the true result of the call.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def render(request):
    """The exact text for a model: instruction, schema sentence, then the input."""
    compact = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    # The same closing sentence that the personal CLI adapter adds in plain_json mode.
    return ('INSTRUCTIONS (verbatim from the application)\n\n' + request['system']
            + '\n\nReturn exactly one JSON object matching this schema. Do not use Markdown, prose, '
              'or additional text. Schema: ' + compact(request['schema'])
            + '\n\nINPUT (verbatim JSON from the application)\n\n' + compact(request['payload']) + '\n')


def wait_for_request(spool, ordinal, wait=600):
    request_path = spool / f'request-{ordinal:04d}.json'
    started = time.monotonic()
    while not request_path.exists():
        if time.monotonic() - started > wait:
            raise SystemExit(f'request {ordinal} did not appear within {wait} seconds')
        time.sleep(0.25)
    return json.loads(request_path.read_text(encoding='utf-8'))


def show(spool, ordinal, out, wait=600):
    request = wait_for_request(spool, ordinal, wait)
    text = render(request)
    with open(out, 'x', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    print(json.dumps({'ordinal': ordinal, 'request_sha256': request['request_sha256'],
                      'created_utc': request['created_utc'], 'text_file': str(out),
                      'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                      'required_fields': request['schema'].get('required')}, indent=2))


def problem(spool, ordinal, raw):
    """Return why the app would reject these bytes for request N, or None."""
    request_path = spool / f'request-{ordinal:04d}.json'
    if not request_path.is_file():
        return f'request {ordinal} does not exist in this relay folder'
    if not raw.strip():
        return 'the answer file is empty'
    if len(raw) > 1_000_000:
        return 'the answer file is larger than 1 MB'
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return ('the answer file is not UTF-8 text. Windows PowerShell 5.1 writes UTF-16 with ">": '
                'save the file with Notepad as UTF-8')
    try:
        answer = json.loads(text)
    except json.JSONDecodeError as error:
        return ('the answer file is not one JSON object with nothing around it '
                f'(line {error.lineno}, column {error.colno}: {error.msg}). '
                'Remove a Markdown fence or a sentence before or after the object')
    if not isinstance(answer, dict):
        return 'the answer is JSON but not an object'
    from jsonschema import Draft202012Validator
    schema = json.loads(request_path.read_text(encoding='utf-8'))['schema']
    errors = sorted(Draft202012Validator(schema).iter_errors(answer), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        where = '/'.join(str(part) for part in first.absolute_path) or '(top level)'
        return f'the answer does not match the schema of the request at {where}: {first.message[:200]}'
    return None


def check(spool, ordinal, answer):
    reason = problem(spool, ordinal, Path(answer).read_bytes())
    if reason:
        raise SystemExit('NOT ACCEPTABLE: ' + reason)
    print('OK: the app would accept this answer file as a transport reply')


def deliver(spool, ordinal, answer, force=False):
    raw = Path(answer).read_bytes()
    if not raw.strip():
        raise SystemExit('The answer file is empty')
    target = spool / f'response-{ordinal:04d}.json'
    if target.exists():
        raise SystemExit('A reply for this request was already delivered')
    reason = problem(spool, ordinal, raw)
    if reason and not force:
        raise SystemExit('NOT DELIVERED: ' + reason + '.\nThe call is not spent. Correct the copy and deliver again. '
                         'If this is exactly what the model returned, add --force to record that result.')
    incoming = spool / f'response-{ordinal:04d}.json.incoming'
    incoming.write_bytes(raw)
    os.replace(incoming, target)
    print(json.dumps({'ordinal': ordinal, 'answer_sha256': hashlib.sha256(raw).hexdigest(),
                      'answer_bytes': len(raw), **({'forced_despite': reason} if reason else {}),
                      'delivered_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}))


def main(argv):
    force = '--force' in argv
    argv = [value for value in argv if value != '--force']
    if len(argv) != 4 or argv[0] not in ('show', 'check', 'deliver') or not argv[2].isdigit():
        raise SystemExit(__doc__)
    if force and argv[0] != 'deliver':
        raise SystemExit('--force is for deliver only')
    spool = Path(argv[1])
    if not spool.is_dir():
        raise SystemExit('The relay folder does not exist')
    if argv[0] == 'deliver':
        deliver(spool, int(argv[2]), Path(argv[3]), force)
    else:
        (show if argv[0] == 'show' else check)(spool, int(argv[2]), Path(argv[3]))


if __name__ == '__main__':
    main(sys.argv[1:])
