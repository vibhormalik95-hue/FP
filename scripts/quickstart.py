"""One command for each step of the demonstration. Works the same on Windows, Linux and macOS.

    python scripts/quickstart.py check
        Print the source fingerprint and the versions that matter.

    python scripts/quickstart.py rehearse --scenario tags
        Serve the app with hand-written replies. No model. Use it to learn the screens.

    python scripts/quickstart.py setup
    python scripts/quickstart.py doctor
    python scripts/quickstart.py start --scenario tags
        Choose a model route (a program on this computer, a hosted API with your
        own key, a local model server, or the relay), confirm that it works, and
        serve the app with it. See docs/model-routes.md.

    python scripts/quickstart.py try --scenario tags
        Send the bundled requests of a scenario through the model route, with no
        browser, and print what the application made of each reply. Nothing is
        applied. See docs/route-trial.md.

    python scripts/quickstart.py live --scenario category --operator cli
    python scripts/quickstart.py live --scenario category --operator manual
        The earlier relay path. The app writes each request to a folder. With
        "cli" the Claude Code CLI on this computer answers it (see
        scripts/relay_claude_cli.py). With "manual" you carry each request to a
        model yourself, and the commands to use are printed.

Scenarios
    tags      existing categories and tags, a mixed request, requests that must
              change nothing, a request matched to descriptions, a fictional item
    category  a new category from natural language
    hunger    an indirect request matched to item descriptions
Each scenario also has the manual category control.

Open the printed address in a browser. The page opens on "Language controls".
Press Ctrl+C in this window to stop the server.

Nothing here sends email, publishes, or stores credentials.
"""
import argparse
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CALLS = {'category': 3, 'hunger': 2, 'tags': 10}
# The readiness test asks this computer only, so a proxy of the environment is never used for it.
_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def utc_stamp():
    """A folder-name stamp in UTC, the same clock as the call receipts."""
    return time.strftime('%Y%m%d-%H%M%SZ', time.gmtime())


def require_free_port(port):
    """Stop with one clear line when another server uses the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'Port {port} on 127.0.0.1 is in use. Stop the other server, '
                             'or choose another port with --port.') from None


def run_demo(*arguments, env=None):
    return subprocess.Popen([sys.executable, str(ROOT / 'scripts' / 'run_demo.py'), *arguments], cwd=str(ROOT), env=env)


def wait_until_served(port, server, seconds=40):
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        if server.poll() is not None:
            raise SystemExit('The server stopped. Read its message above.')
        try:
            with _LOCAL.open(f'http://127.0.0.1:{port}/', timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise SystemExit(f'The server did not answer on port {port} within {seconds} s')


def stop_server(server, patience=15):
    """End the server: first ask, then wait, then force.

    The server ends its running model calls when it is asked to stop. A forced
    end cannot do that, so it comes last. On Windows the first step is a forced
    end already, because Python has no gentler signal for another process there;
    Ctrl+C in the terminal reaches the server itself and stops it gently.
    """
    if server.poll() is not None:
        return server.returncode
    for ask, wait in ((lambda: server.send_signal(signal.SIGINT) if sys.platform != 'win32' else server.terminate(), patience),
                      (server.terminate, 5), (server.kill, 5)):
        try:
            ask()
            return server.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            continue
        except OSError:
            break
    return server.poll()


def keep_serving(server, patience=15):
    """Wait for the server. Return its exit code, or 0 after Ctrl+C."""
    print('\nThe server keeps running. Finish in the browser, then press Ctrl+C here.', flush=True)
    try:
        return server.wait()
    except KeyboardInterrupt:
        # Ctrl+C in a terminal goes to the server as well. It ends its model
        # calls and stops by itself; a forced end follows only when it does not.
        print('\nStopping the server ...', flush=True)
        try:
            server.wait(timeout=patience)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            stop_server(server, patience=5)
        return 0


def serve_until_stopped(server):
    """Leave with the exit code of a server that ended by itself with an error."""
    code = keep_serving(server)
    if code not in (None, 0):
        raise SystemExit(code)


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
    require_free_port(args.port)
    server = run_demo('--scenario', args.scenario, '--provider', 'scripted', '--port', str(args.port))
    try:
        wait_until_served(args.port, server)
        print(f'Rehearsal with hand-written replies (no model). Open http://127.0.0.1:{args.port}', flush=True)
        serve_until_stopped(server)
    finally:
        stop_server(server)


def live(args):
    require_free_port(args.port)
    relay = ROOT / 'runs' / f'relay-{args.scenario}-{utc_stamp()}'
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
            tool = 'python scripts/relay_tools.py'
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
        serve_until_stopped(server)
    finally:
        stop_server(server)


ROUTE_TOOL = {'setup': 'setup', 'doctor': 'check'}  # these steps are commands of scripts/model_route.py


def start(args):
    """Serve the app with the model route of the route file."""
    import getpass
    import os
    sys.path.insert(0, str(ROOT))
    from feedctrl import model_routes
    # The server runs in the repository folder. A path that is relative to the
    # folder of the user would name another file there, so each path is made
    # absolute here.
    route_file = Path(args.route_file).expanduser().resolve()
    try:
        config = model_routes.load_config(route_file)
    except model_routes.RouteError as error:
        raise SystemExit(model_routes.ascii_text(error) + '\nRun "python scripts/quickstart.py setup" first.') from None
    try:
        # A hidden prompt cannot be answered in the server process, so the key is
        # read here and handed to the server in its environment only.
        key = model_routes.resolve_api_key(config, ask=getpass.getpass if sys.stdin.isatty() else None)
    except model_routes.RouteError as error:
        raise SystemExit(model_routes.ascii_text(error)) from None
    require_free_port(args.port)
    print('Route file: ' + model_routes.ascii_text(route_file))
    for line in model_routes.describe(config):
        print(line)
    arguments = ['--scenario', args.scenario, '--provider', 'route', '--route-file', str(route_file),
                 '--port', str(args.port)]
    if args.record_dir:
        none = args.record_dir.strip().lower() == 'none'
        arguments += ['--record-dir', 'none' if none else str(Path(args.record_dir).expanduser().resolve())]
    relay = None
    if config['route'] == 'relay':
        relay = ROOT / 'runs' / f'relay-{args.scenario}-{utc_stamp()}'
        arguments += ['--relay-dir', str(relay)]
    name = model_routes.needs_api_key(config)
    server = run_demo(*arguments, env={**os.environ, name: key} if name else None)
    try:
        wait_until_served(args.port, server)
        print(f'\nOpen http://127.0.0.1:{args.port}', flush=True)
        if relay is not None:
            tool = 'python scripts/relay_tools.py'
            print(f'\nRelay folder: {relay}\nFor each request N, in a second window:\n'
                  f'  {tool} show "{relay}" N request-N.txt\n'
                  f'  give the whole text of request-N.txt to the model in a new conversation\n'
                  f'  save the reply (the JSON object only) as answer-N.json\n'
                  f'  {tool} check "{relay}" N answer-N.json\n'
                  f'  {tool} deliver "{relay}" N answer-N.json', flush=True)
        serve_until_stopped(server)
    finally:
        stop_server(server)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] and argv[0] in ROUTE_TOOL:
        # Their options belong to the route tool, so they are handed on unchanged.
        sys.path.insert(0, str(ROOT / 'scripts'))
        import model_route
        raise SystemExit(model_route.main([ROUTE_TOOL[argv[0]], *argv[1:]]))
    if argv[:1] == ['try']:
        # The same for the route trial: "try" is "python scripts/route_trial.py run".
        sys.path.insert(0, str(ROOT / 'scripts'))
        import route_trial
        raise SystemExit(route_trial.main(['run', *argv[1:]]))
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    steps = parser.add_subparsers(dest='step', required=True)
    steps.add_parser('check').set_defaults(run=check)
    sys.path.insert(0, str(ROOT / 'scripts'))
    import run_demo as launcher
    scenarios = sorted(launcher.SCENARIOS)
    for name, function in (('rehearse', rehearse), ('live', live)):
        step = steps.add_parser(name)
        if name == 'rehearse':
            step.add_argument('--scenario', choices=scenarios, default='tags' if 'tags' in scenarios else 'category')
        else:
            # The relay operator waits for a fixed number of requests, so this
            # older path serves the two scenarios with one complete flow each.
            step.add_argument('--scenario', choices=('category', 'hunger'), default='category')
        step.add_argument('--port', type=int, default=8765)
        step.set_defaults(run=function)
        if name == 'live':
            step.add_argument('--operator', choices=('cli', 'manual'), required=True)
            step.add_argument('--model', default='claude-fable-5-2')
            step.add_argument('--effort', default='max', choices=('low', 'medium', 'high', 'max'))
            step.add_argument('--claude', help='path of the Claude Code CLI; default: "claude" on PATH')
            step.add_argument('--allow-other-models', action='store_true')
    for name, command in ROUTE_TOOL.items():   # listed for --help; handled above
        steps.add_parser(name, help=f'the same as "python scripts/model_route.py {command}"')
    steps.add_parser('try', help='the same as "python scripts/route_trial.py run"')
    step = steps.add_parser('start')
    step.add_argument('--scenario', choices=scenarios, default='tags' if 'tags' in scenarios else 'category')
    step.add_argument('--port', type=int, default=8765)
    step.add_argument('--route-file', default=str(ROOT / 'model-route.json'))
    step.add_argument('--record-dir', help='a new folder for the call records, or "none"; default: a new folder under runs/')
    step.set_defaults(run=start)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
