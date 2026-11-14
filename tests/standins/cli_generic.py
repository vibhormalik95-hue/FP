"""A stand-in for any program that reads a prompt on standard input. It is not a model.

    python tests/standins/cli_generic.py [--replies scripted|echo-ok] [--fail FAULT]

It writes the hand-written rehearsal reply for the request to standard output.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--replies', choices=('scripted', 'echo-ok'), default='scripted')
    parser.add_argument('--fail', choices=('exit_code', 'slow', 'not_utf8', *common.REPLY_FAULTS))
    parser.add_argument('--delay', type=float, default=30.0)
    args = parser.parse_args(argv)
    prompt = sys.stdin.buffer.read().decode('utf-8')
    if args.fail == 'slow':
        time.sleep(args.delay)
    if args.fail == 'exit_code':
        sys.stderr.write('stand-in failure: boom\n')
        return 7
    if args.fail == 'not_utf8':
        sys.stdout.buffer.write(b'\xff\xfe{"ok": true}')
        return 0
    try:
        payload, schema = common.from_prompt(prompt)
    except ValueError:
        sys.stderr.write(common.NOTE + ': the input does not have the form that the routes send\n')
        return 2
    reply = common.reply_for(payload, schema, args.replies)
    if reply is None:
        sys.stderr.write(common.NO_REPLY + '\n')
        return 3
    sys.stdout.write(common.faulty(json.dumps(reply, ensure_ascii=False), args.fail))
    return 0


if __name__ == '__main__':
    sys.exit(main())
