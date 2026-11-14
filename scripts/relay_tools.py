"""Two helpers for the relay provider of scripts/run_demo.py.

    python scripts/relay_tools.py show RELAY_DIR N OUT.txt
        Wait for request N and write it as the exact text to give a model:
        the instruction, the response schema, then the input as JSON.

    python scripts/relay_tools.py deliver RELAY_DIR N ANSWER.json
        Give the model's answer file to the app, byte for byte, with an atomic
        rename so that the app never reads a partly written file.

The helpers copy bytes. They do not edit, trim, repair or judge a reply. The
answer must be one JSON object with nothing around it; the app rejects anything
else and the call is then spent.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def show(spool, ordinal, out, wait=600):
    request_path = spool / f'request-{ordinal:04d}.json'
    started = time.monotonic()
    while not request_path.exists():
        if time.monotonic() - started > wait:
            raise SystemExit(f'request {ordinal} did not appear within {wait} seconds')
        time.sleep(0.25)
    request = json.loads(request_path.read_text(encoding='utf-8'))
    compact = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    # The same closing sentence that the personal CLI adapter adds in plain_json mode.
    text = ('INSTRUCTIONS (verbatim from the application)\n\n' + request['system']
            + '\n\nReturn exactly one JSON object matching this schema. Do not use Markdown, prose, '
              'or additional text. Schema: ' + compact(request['schema'])
            + '\n\nINPUT (verbatim JSON from the application)\n\n' + compact(request['payload']) + '\n')
    with open(out, 'x', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    print(json.dumps({'ordinal': ordinal, 'request_sha256': request['request_sha256'],
                      'created_utc': request['created_utc'], 'text_file': str(out),
                      'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                      'required_fields': request['schema'].get('required')}, indent=2))


def deliver(spool, ordinal, answer):
    raw = Path(answer).read_bytes()
    if not raw.strip():
        raise SystemExit('The answer file is empty')
    target = spool / f'response-{ordinal:04d}.json'
    if target.exists():
        raise SystemExit('A reply for this request was already delivered')
    incoming = spool / f'response-{ordinal:04d}.json.incoming'
    incoming.write_bytes(raw)
    os.replace(incoming, target)
    print(json.dumps({'ordinal': ordinal, 'answer_sha256': hashlib.sha256(raw).hexdigest(),
                      'answer_bytes': len(raw),
                      'delivered_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}))


def main(argv):
    if len(argv) != 4 or argv[0] not in ('show', 'deliver') or not argv[2].isdigit():
        raise SystemExit(__doc__)
    spool = Path(argv[1])
    if not spool.is_dir():
        raise SystemExit('The relay folder does not exist')
    (show if argv[0] == 'show' else deliver)(spool, int(argv[2]), Path(argv[3]))


if __name__ == '__main__':
    main(sys.argv[1:])
