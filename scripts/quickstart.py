"""One command for each step of the demonstration. Works the same on Windows, Linux and macOS.

    python scripts/quickstart.py check
        Print the source fingerprint and the versions that matter.

    python scripts/quickstart.py rehearse --scenario category
        Serve the app with hand-written replies. No model. Use it to learn the screens.

    python scripts/quickstart.py live --scenario category --operator cli
        Serve the app with the relay provider, and answer each request with the
        Claude Code CLI on this computer (see scripts/relay_claude_cli.py).

    python scripts/quickstart.py live --scenario category --operator manual
        Serve the app with the relay provider. You carry each request to a model
        yourself. The commands to use are printed.

Scenarios: "category" (manual control and a new category from natural language)
and "hunger" (manual control and an indirect request). Open the printed address
in a browser, choose "Reviewed topic feed", then open "Experimental semantic
groups". Press Ctrl+C in this window to stop the server.

Each live start uses a new relay folder under runs/. Nothing here sends email,
publishes, or stores credentials.
"""
import argparse
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CALLS = {'category': 3, 'hunger': 2}


def run_demo(*arguments):
    return subprocess.Popen([sys.executable, str(ROOT / 'scripts' / 'run_demo.py'), *arguments], cwd=str(ROOT))


def wait_until_served(port, server, seconds=40):
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        if server.poll() is not None:
            raise SystemExit('The server stopped. Read its message above.')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise SystemExit(f'The server did not answer on port {port} within {seconds} s')


def keep_serving(server):
    print('\nThe server keeps running. Finish in the browser, then press Ctrl+C here.', flush=True)
    try:
        server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if server.poll() is None:
            server.terminate()


def check(_):
    sys.path.insert(0, str(ROOT / 'scripts'))
    import run_demo as launcher
    print('source fingerprint:', launcher.source_fingerprint())
    print('python:', platform.python_version(), '| system:', platform.system(), platform.release())
    from importlib import metadata
    for name in ('fastapi', 'uvicorn', 'pydantic', 'numpy', 'scipy', 'jsonschema'):
        try:
            print(f'{name}: {metadata.version(name)}')
        except metadata.PackageNotFoundError:
            print(f'{name}: MISSING. Run: python -m pip install -e ".[test]"')
    launcher.require_built_interface()
    print('built interface: present')


def rehearse(args):
    print(f'Rehearsal with hand-written replies (no model). Open http://127.0.0.1:{args.port}', flush=True)
    server = run_demo('--scenario', args.scenario, '--provider', 'scripted', '--port', str(args.port))
    keep_serving(server)


def live(args):
    relay = ROOT / 'runs' / f'relay-{args.scenario}-{time.strftime("%Y%m%d-%H%M%S")}'
    calls = CALLS[args.scenario]
    if args.operator == 'cli':
        note = 'automatic operator: the Claude Code CLI on this computer, one print-mode call for each request'
    else:
        note = 'an operator carries each request to the model by hand and returns the reply unchanged'
    server = run_demo('--scenario', args.scenario, '--provider', 'relay', '--port', str(args.port),
                      '--relay-dir', str(relay), '--declared-model', f'{args.model} (declared by the operator)',
                      '--transport-note', note, '--relay-timeout', '1800')
    try:
        wait_until_served(args.port, server)
        print(f'\nOpen http://127.0.0.1:{args.port}   relay folder: {relay}', flush=True)
        if args.operator == 'manual':
            tool = f'python scripts/relay_tools.py'
            print(f'\nFor each request N (1 to {calls}), in a second window:\n'
                  f'  {tool} show "{relay}" N request-N.txt\n'
                  f'  give the whole text of request-N.txt to the model in a new conversation\n'
                  f'  save the reply (the JSON object only) as answer-N.json\n'
                  f'  {tool} check "{relay}" N answer-N.json\n'
                  f'  {tool} deliver "{relay}" N answer-N.json', flush=True)
        else:
            sys.path.insert(0, str(ROOT / 'scripts'))
            import relay_claude_cli
            operator = [str(relay), '--calls', str(calls), '--model', args.model, '--effort', args.effort]
            if args.claude:
                operator += ['--claude', args.claude]
            if args.allow_other_models:
                operator.append('--allow-other-models')
            try:
                relay_claude_cli.main(operator)
            except SystemExit as stopped:
                if stopped.code not in (None, 0):
                    print(f'\n{stopped.code}', flush=True)
        keep_serving(server)
    finally:
        if server.poll() is None:
            server.terminate()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    steps = parser.add_subparsers(dest='step', required=True)
    steps.add_parser('check').set_defaults(run=check)
    for name, function in (('rehearse', rehearse), ('live', live)):
        step = steps.add_parser(name)
        step.add_argument('--scenario', choices=sorted(CALLS), default='category')
        step.add_argument('--port', type=int, default=8765)
        step.set_defaults(run=function)
        if name == 'live':
            step.add_argument('--operator', choices=('cli', 'manual'), required=True)
            step.add_argument('--model', default='claude-fable-5-2')
            step.add_argument('--effort', default='max', choices=('low', 'medium', 'high', 'max'))
            step.add_argument('--claude', help='path of the Claude Code CLI; default: "claude" on PATH')
            step.add_argument('--allow-other-models', action='store_true')
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
