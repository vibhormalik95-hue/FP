"""Serve the Feed Control Lab on this computer for the language-control demonstration.

Examples (run from the repository root):

    python scripts/run_demo.py --scenario tags --provider route --route-file model-route.json
    python scripts/run_demo.py --scenario category --provider manual
    python scripts/run_demo.py --scenario hunger --provider relay \
        --relay-dir runs/relay-01 --declared-model claude-fable-5-2 \
        --transport-note "replies pasted by hand from a Claude chat"
    python scripts/run_demo.py --provider personal-cli --reviewed-config my-config.json \
        --report runs/category-report.json
    python scripts/run_demo.py --scenario hunger --provider route --route-file model-route.json

Providers
    manual        No model. Only the manual category control is offered.
    relay         An operator carries each request to a model and saves the reply.
    personal-cli  The signed-in Claude Code CLI on Windows, through the reviewed
                  configuration that the validation driver already checks.
    route         A model route from a route file: a program on this computer, a
                  hosted API with your own key, a local model server, or the relay.
                  Write the file with "python scripts/model_route.py setup".
                  See docs/model-routes.md.

There is no provider with hand-written replies. To try the screens of a
language-control workflow with no key and no model, use Feed Control Studio
(run-studio.cmd) and its mock provider; see docs/studio-guide.md.

Scenarios
    tags      Ten invented items with categories and tags: the manual control, a
              request matched to existing categories and tags, a mixed request,
              requests that must not change the feed, a request matched to item
              descriptions, and a fictional-item draft.
    category  Eight invented items: the manual control and a new category.
    hunger    Eight invented items: the manual control and an indirect request
              matched to item descriptions.
    conditions  The five original conditions A to E on the built-in fixture (36
              items with the categories category_0 to category_5, three users)
              and the rule parser. No language controls. Use --provider manual.

The server binds to 127.0.0.1 only. Local models and the trained recommender stay
disabled; the bundled scenarios use invented item descriptions and a labelled
diagnostic scorer. Nothing here sends email, publishes or stores credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'tools' / 'hosted_validation_current' / 'inputs'
SCENARIOS = {
    'category': INPUTS / '01-category-discovery',
    'hunger': INPUTS / '02-hunger-continuation',
    # Existing categories and tags; not bound to the reviewed driver's input pins.
    'tags': ROOT / 'scenarios' / 'categories-and-tags',
}
# A scenario without a folder: the built-in fixture of the application. Its
# categories have the form category_N, which the rule parser of the original
# conditions A to E reads. The bundled scenarios above have named categories,
# so the instruction and the profile of C, D and E cannot be tried on them.
FIXTURE_SCENARIOS = {
    'conditions': 'The five original conditions A to E on the built-in fixture: 36 items, category_0 to '
                  'category_5, three users, the rule parser. No caption data, so no language controls.',
}
# The reviewed driver names the indirect-request scenario "indirect".
DRIVER_SCENARIO = {'category': 'category', 'indirect': 'hunger'}
# Calls needed by one complete pass: definition + membership + evidence
# assessment for a new category; action + grounding for an indirect request.
# A failed stage ends its flow, so a spare call would not be used. The tags
# scenario bundles several one-call requests, a two-call description request
# and a fictional-item brief, so it gets the largest relay allowance.
CALLS = {'category': 3, 'hunger': 2, 'tags': 10}
PERSONAL_PORT = 8765  # the origin the reviewed driver declares for the personal app


def scenario_paths(name):
    folder = SCENARIOS[name]
    data, sidecar = folder / 'app-data.json', folder / 'metadata.csv'
    if not data.is_file() or not sidecar.is_file():
        raise SystemExit(f'Scenario files are missing under {folder}')
    return data, sidecar


def scenario_requests(name):
    """The exact bundled request text, offered in the page so it is not retyped.

    A scenario with ``requests.json`` supplies a flat mapping. Key ``<method>``
    is the main request of a method and ``<method>:<case>`` is a further example.
    """
    bundled = SCENARIOS[name] / 'requests.json'
    if bundled.is_file():
        requests = json.loads(bundled.read_text(encoding='utf-8'))['requests']
        if not isinstance(requests, dict) or not all(isinstance(text, str) for text in requests.values()):
            raise SystemExit(f'{bundled} must hold a flat mapping of request texts')
        return dict(requests)
    body = json.loads((SCENARIOS[name] / 'app-preview.json').read_text(encoding='utf-8'))
    if name == 'category':
        return {'staged': body['objective']}
    return {'configured_model': body['text'], 'label': body['label']}


def source_fingerprint(root=None):
    """One SHA-256 over the files that decide what the served app does.

    It covers the application package, the built interface, this launcher and
    the bundled scenario inputs (the pinned validation inputs and the
    ``scenarios`` folder). A run receipt
    that records it can be matched to an exact source tree without Git. Print
    it with ``python scripts/run_demo.py --fingerprint``.

    The value is the same on Windows, Linux and macOS for the same tree. Files
    are ordered by the parts of their relative path, compared as case-sensitive
    text. CRLF line endings in Python files count as LF, because Git on Windows
    can convert them on checkout. Every other file is hashed as bytes on disk.
    """
    root = ROOT if root is None else Path(root)
    inputs = root / 'tools' / 'hosted_validation_current' / 'inputs'
    files = [*(root / 'feedctrl').glob('*.py'), *(root / 'web' / 'dist').rglob('*'), *inputs.rglob('*'),
             *(root / 'scenarios').rglob('*'),
             root / 'scripts' / 'run_demo.py']
    digest = hashlib.sha256()
    for parts, path in sorted((path.relative_to(root).parts, path) for path in files if path.is_file()):
        data = path.read_bytes()
        if path.suffix == '.py':
            data = data.replace(b'\r\n', b'\n')
        digest.update('/'.join(parts).encode('utf-8') + b'\0')
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def require_built_interface():
    """Fail before any provider work if the page or a file it loads is missing."""
    index = ROOT / 'web' / 'dist' / 'index.html'
    if not index.is_file():
        raise SystemExit('The built interface is missing: run "npm ci" and "npm run build" in web/')
    for asset in re.findall(r'(?:src|href)="/(assets/[^"]+)"', index.read_text(encoding='utf-8')):
        if not (ROOT / 'web' / 'dist' / asset).is_file():
            raise SystemExit(f'The built interface is incomplete: web/dist/{asset} is missing. '
                             'Run "npm ci" and "npm run build" in web/')


def require_free_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError as exc:
            raise SystemExit(f'Port {port} on 127.0.0.1 is in use; stop the other server first') from exc


def build_route_provider(args, scenario, summary):
    """Return ``(infer, identity, receipts)`` for the route that a route file selects.

    The key of a hosted route comes from the environment variable that the file
    names, or from a hidden prompt at a terminal. It is never printed or stored.
    Each call is recorded in a new folder under runs/ (the exact request body
    and the raw reply, no header), unless --record-dir none is given.
    """
    import getpass
    import time
    from feedctrl import model_routes
    # UTC, the clock of the call receipts.
    stamp = time.strftime('%Y%m%d-%H%M%SZ', time.gmtime())
    relay_only = [option for option, value in (('--declared-model', args.declared_model),
                                               ('--transport-note', args.transport_note),
                                               ('--relay-timeout', getattr(args, 'relay_timeout_given', None)))
                  if value is not None]
    if relay_only:
        raise SystemExit(', '.join(relay_only) + ' belong to --provider relay. With a route file, put the same '
                         'settings in the file ("declared_model", "transport_note", "timeout_seconds").')
    record_option = getattr(args, 'record_dir', None)
    try:
        config = model_routes.load_config(getattr(args, 'route_file', None) or ROOT / model_routes.DEFAULT_FILE)
        if args.max_calls is not None:
            # The option can set the allowance of this run; the limits of the route kind still hold.
            config = model_routes.validate_config({**config, 'max_calls': args.max_calls})
        key = model_routes.resolve_api_key(config, ask=getpass.getpass if sys.stdin.isatty() else None)
        relay_dir = record_dir = None
        if config['route'] == 'relay':
            relay_dir = Path(args.relay_dir) if args.relay_dir else ROOT / 'runs' / f'relay-{scenario}-{stamp}'
            summary['relay_dir'] = str(relay_dir.resolve())
        elif record_option is None or record_option.strip().lower() != 'none':
            record_dir = Path(record_option or ROOT / 'runs' / f'route-{scenario}-{stamp}')
            summary['record_dir'] = str(record_dir.resolve())
        provider = model_routes.build_route(config, api_key=key, record_dir=record_dir, relay_dir=relay_dir,
                                            log=lambda line: print(line, flush=True))
    except model_routes.RouteError as error:
        raise SystemExit(model_routes.ascii_text(error)) from None
    summary['route'] = model_routes.describe(config)
    return provider


def build_fixture_app(args, scenario):
    """Serve the built-in fixture for the original conditions A to E. No model provider."""
    if args.provider != 'manual':
        raise SystemExit(f'The scenario "{scenario}" has no language controls and no model provider: '
                         f'{FIXTURE_SCENARIOS[scenario]} Start it with --provider manual.')
    import os
    from feedctrl.api import create_app
    # The fixture has no caption data. A sidecar path in the environment belongs
    # to another data set, so it is ignored while the application is built.
    saved = os.environ.pop('FEEDCTRL_CAPTION_SIDECAR', None)
    try:
        app = create_app(fixture=True, allow_local_models=False, allow_local_recommender=False)
    finally:
        if saved is not None:
            os.environ['FEEDCTRL_CAPTION_SIDECAR'] = saved
    app.state.provider_receipts = None
    app.state.scenario_requests = {}
    app.state.scenario_name = scenario
    summary = {'scenario': scenario, 'provider': 'manual', 'note': FIXTURE_SCENARIOS[scenario]}
    return app, args.port or PERSONAL_PORT, summary, lambda: None


def build_app(args):
    """Return ``(app, port, summary, finish)`` for the selected provider."""
    sys.path.insert(0, str(ROOT))
    # First: the fixture scenario refuses every provider but manual, also personal-cli.
    if args.scenario in FIXTURE_SCENARIOS:
        return build_fixture_app(args, args.scenario)
    if args.provider == 'personal-cli':
        return build_personal_cli_app(args)

    from feedctrl.api import create_app
    from feedctrl import demo_providers

    scenario = args.scenario or 'category'
    port = args.port or PERSONAL_PORT
    data, sidecar = scenario_paths(scenario)
    factories = {}
    summary = {'scenario': scenario, 'provider': args.provider}
    if args.provider == 'relay':
        if not args.relay_dir or not args.declared_model or not args.transport_note:
            raise SystemExit('relay needs --relay-dir, --declared-model and --transport-note')
        spool = Path(args.relay_dir)
        spool.mkdir(parents=True, exist_ok=True)
        infer, identity, receipts = demo_providers.relay_provider(
            spool, declared_model=args.declared_model, transport_note=args.transport_note,
            max_calls=args.max_calls or CALLS[scenario], timeout=args.relay_timeout)
        summary['relay_dir'] = str(spool.resolve())
    elif args.provider == 'route':
        infer, identity, receipts = build_route_provider(args, scenario, summary)
    else:
        infer = identity = receipts = None
    if infer is not None:
        semantic, category = demo_providers.bind_factories(infer, identity)
        # The fictional-item draft uses the same callable and the same allowance.
        factories = {'semantic_infer_factory': semantic, 'category_infer_factory': category,
                     'synthetic_infer_factory': semantic}
        summary['identity'] = identity
    app = create_app(data_path=data, semantic_path=sidecar, fixture=False,
                     allow_local_models=False, allow_local_recommender=False, **factories)
    app.state.provider_receipts = receipts
    app.state.scenario_requests = scenario_requests(scenario)
    app.state.scenario_name = scenario
    return app, port, summary, lambda: None


RETIRED_PERSONAL_CLI = ('personal-cli is retired: it served the token-gated personal app through the frozen '
                        'driver in tools/hosted_validation_current. Use the Studio instead: '
                        'python -m studio --provider claude-cli  (or run-studio.cmd with your own API key).')


def build_personal_cli_app(args):
    """Serve the exact app object that the reviewed validation driver builds.

    All checks stay in ``tools/hosted_validation_current/driver.py``: the six
    explicit assertions, the pinned source and inputs, the executable hash and
    the call allowance. This function adds only an HTTP listener on the origin
    that the driver already declares, so the same run can be reviewed in a
    browser. Reviews, Apply and Undo happen in the page; the report written
    here holds the provider facts (exact inputs, receipts, attempts) and says so.
    A configuration file is marked as used and is refused a second time.
    """
    raise SystemExit(RETIRED_PERSONAL_CLI)
    if not args.reviewed_config or not args.report:  # pragma: no cover - kept for the record of past runs
        raise SystemExit('personal-cli needs --reviewed-config and --report')
    if args.port not in (None, PERSONAL_PORT):
        raise SystemExit(f'personal-cli always serves on port {PERSONAL_PORT}, the origin the reviewed driver declares')
    driver_path = ROOT / 'tools' / 'hosted_validation_current' / 'driver.py'
    spec = importlib.util.spec_from_file_location('reviewed_driver', driver_path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)

    config_path, report_path = Path(args.reviewed_config), Path(args.report)
    config = json.loads(config_path.read_text(encoding='utf-8'))
    driver.validate(config, ROOT)
    driver.require(config.get('input_manifest_sha256') == driver.INPUT_MANIFEST_SHA256,
                   'Reviewed input pin required')
    scenario = DRIVER_SCENARIO[config['scenario']]
    if args.scenario not in (None, scenario):
        raise SystemExit(f'--scenario {args.scenario} does not match the reviewed configuration ({scenario})')
    bundle = driver.load_inputs(INPUTS, config['scenario'])
    driver.require(not report_path.exists(), 'Report already exists; no rerun or overwrite')
    # Everything that can fail for a local reason is checked before the
    # configuration is marked as used.
    import uvicorn  # noqa: F401
    require_free_port(PERSONAL_PORT)
    marker = Path(str(config_path.resolve()) + '.consumed')
    with marker.open('x', encoding='utf-8') as handle:
        handle.write(driver.digest(config_path))

    from feedctrl.windows_job_runner import run_windows_job
    report = driver.new_report(config['scenario'], bundle)
    served_note = 'Not recorded here: the run was served to a browser. See the browser receipt.'
    report.update(config_sha256=driver.digest(config_path), identity_basis=config['identity_basis'],
                  status='served_to_browser', steps=served_note, operator_decisions=served_note,
                  mechanics={'recorded_here': False, 'note': served_note},
                  evidence_kind='served application; provider facts only; reviews, Apply and Undo are in the browser receipt')
    holder = {}

    def checkpoint():
        if 'app' in holder:
            report['receipts'] = holder['app'].state.hosted_model_receipts
            report['attempted'] = holder['budget'].attempted
        report_path.write_text(json.dumps(driver.redact(report, config), indent=2), encoding='utf-8')

    built, budget = driver.build(config, ROOT, bundle, run_windows_job, report, checkpoint)
    built.state.scenario_requests = scenario_requests(scenario)
    holder.update(app=built, budget=budget)
    checkpoint()

    async def app(scope, receive, send):
        # Save the provider facts after every API call, so the last receipt on
        # disk is final even if the server is stopped abruptly.
        try:
            await built(scope, receive, send)
        finally:
            if scope.get('type') == 'http' and scope.get('path', '').startswith('/api/semantic'):
                checkpoint()

    app.state = built.state
    summary = {'scenario': scenario, 'provider': 'personal-cli',
               'model': config['model'], 'max_calls': budget.max_calls,
               'report': str(report_path.resolve()),
               'note': 'Open the page on 127.0.0.1; it serves only loopback requests.'}

    def finish():
        report['status'] = 'server_stopped'
        checkpoint()

    return app, PERSONAL_PORT, summary, finish


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--scenario', choices=sorted([*SCENARIOS, *FIXTURE_SCENARIOS]))
    parser.add_argument('--provider', choices=('manual', 'relay', 'personal-cli', 'route'),
                        default='manual')
    parser.add_argument('--route-file', help='with --provider route; default: model-route.json')
    parser.add_argument('--record-dir', help='with --provider route: a new folder for the call records, or "none"')
    parser.add_argument('--port', type=int)
    parser.add_argument('--relay-dir')
    parser.add_argument('--declared-model')
    parser.add_argument('--transport-note')
    parser.add_argument('--relay-timeout', type=float)
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--reviewed-config')
    parser.add_argument('--report')
    parser.add_argument('--fingerprint', action='store_true', help='print the source fingerprint and exit')
    args = parser.parse_args(argv)
    # The relay provider waits 600 s by default; a route file has its own setting.
    args.relay_timeout_given, args.relay_timeout = args.relay_timeout, 600 if args.relay_timeout is None else args.relay_timeout
    if args.fingerprint:
        print(source_fingerprint())
        return
    if args.port is not None and not 1024 <= args.port <= 65535:
        raise SystemExit('Choose a port between 1024 and 65535')
    require_built_interface()

    app, port, summary, finish = build_app(args)
    app.state.source_fingerprint = summary['source_fingerprint'] = source_fingerprint()
    print(json.dumps({'serving': f'http://127.0.0.1:{port}', **summary}, indent=2, default=str), flush=True)
    try:
        serve(app, port)
    finally:
        finish()


# Seconds that the server waits for open requests after a stop signal. A stop
# ends every running model call first, so a request ends within about a second.
GRACEFUL_SECONDS = 10


def serve(app, port):
    """Serve until Ctrl+C or a stop signal (SIGINT, SIGTERM; Ctrl+Break on Windows).

    The signal sets the stop flag of the model routes. A route then refuses
    every new call, and a watcher ends the running calls: it closes an HTTP
    connection, and it ends a program with the programs that it started. Then
    the server waits at most ``GRACEFUL_SECONDS`` for open requests. A second
    Ctrl+C ends the wait at once.
    """
    import contextlib
    import signal
    import threading
    import uvicorn
    from feedctrl import model_routes

    class StoppingServer(uvicorn.Server):
        def handle_exit(self, sig, frame):
            model_routes.request_stop()   # only a flag: safe in a signal handler
            super().handle_exit(sig, frame)

        @contextlib.contextmanager
        def capture_signals(self):
            # As uvicorn does, but the signal is not raised again after the
            # stop, so that the report of a run is closed and the exit code is 0.
            if threading.current_thread() is not threading.main_thread():
                yield
                return
            names = [signal.SIGINT, signal.SIGTERM] + ([signal.SIGBREAK] if hasattr(signal, 'SIGBREAK') else [])
            original = {name: signal.signal(name, self.handle_exit) for name in names}
            try:
                yield
            finally:
                for name, handler in original.items():
                    signal.signal(name, handler)

    config = uvicorn.Config(app, host='127.0.0.1', port=port, proxy_headers=False, server_header=False,
                            log_level='warning', timeout_graceful_shutdown=GRACEFUL_SECONDS)
    try:
        StoppingServer(config).run()
    except KeyboardInterrupt:
        pass
    finally:
        model_routes.request_stop()
        model_routes.cancel_running('stop')


if __name__ == '__main__':
    main()
