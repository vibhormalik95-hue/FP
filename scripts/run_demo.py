"""Serve the Feed Control Lab on this computer for the three-control demonstration.

Examples (run from the repository root):

    python scripts/run_demo.py --scenario category --provider manual
    python scripts/run_demo.py --scenario category --provider scripted
    python scripts/run_demo.py --scenario hunger --provider relay \
        --relay-dir runs/relay-01 --declared-model claude-fable-5-2 \
        --transport-note "replies pasted by hand from a Claude chat"
    python scripts/run_demo.py --provider personal-cli --reviewed-config my-config.json \
        --report runs/category-report.json

Providers
    manual        No model. Only the manual category control is offered.
    scripted      Hand-written replies for the bundled requests. Not a model.
    relay         An operator carries each request to a model and saves the reply.
    personal-cli  The signed-in Claude Code CLI on Windows, through the reviewed
                  configuration that the validation driver already checks.

The server binds to 127.0.0.1 only. Local models and the trained recommender stay
disabled; the bundled scenarios use eight invented descriptions and a labelled
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
}
# The reviewed driver names the indirect-request scenario "indirect".
DRIVER_SCENARIO = {'category': 'category', 'indirect': 'hunger'}
# Calls needed by one complete pass: definition + membership + evidence
# assessment for a new category; action + grounding for an indirect request.
# A failed stage ends its flow, so a spare call would not be used.
CALLS = {'category': 3, 'hunger': 2}
PERSONAL_PORT = 8765  # the origin the reviewed driver declares for the personal app


def scenario_paths(name):
    folder = SCENARIOS[name]
    data, sidecar = folder / 'app-data.json', folder / 'metadata.csv'
    if not data.is_file() or not sidecar.is_file():
        raise SystemExit(f'Scenario files are missing under {folder}')
    return data, sidecar


def scenario_requests(name):
    """The exact bundled request text, offered in the page so it is not retyped."""
    body = json.loads((SCENARIOS[name] / 'app-preview.json').read_text(encoding='utf-8'))
    if name == 'category':
        return {'staged': body['objective']}
    return {'configured_model': body['text'], 'label': body['label']}


def source_fingerprint(root=None):
    """One SHA-256 over the files that decide what the served app does.

    It covers the application package, the built interface, this launcher, the
    authored rehearsal replies and the bundled scenario inputs. A run receipt
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
             root / 'scripts' / 'run_demo.py', root / 'scripts' / 'demo_scripted_replies.py']
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


def build_app(args):
    """Return ``(app, port, summary, finish)`` for the selected provider."""
    sys.path.insert(0, str(ROOT))
    if args.provider == 'personal-cli':
        return build_personal_cli_app(args)

    from feedctrl.api import create_app
    from feedctrl import demo_providers

    scenario = args.scenario or 'category'
    port = args.port or PERSONAL_PORT
    data, sidecar = scenario_paths(scenario)
    factories = {}
    summary = {'scenario': scenario, 'provider': args.provider}
    if args.provider == 'scripted':
        sys.path.insert(0, str(ROOT / 'scripts'))
        import demo_scripted_replies
        infer, identity, receipts = demo_providers.scripted_provider(
            demo_scripted_replies.lookup, demo_scripted_replies.TABLE)
    elif args.provider == 'relay':
        if not args.relay_dir or not args.declared_model or not args.transport_note:
            raise SystemExit('relay needs --relay-dir, --declared-model and --transport-note')
        spool = Path(args.relay_dir)
        spool.mkdir(parents=True, exist_ok=True)
        infer, identity, receipts = demo_providers.relay_provider(
            spool, declared_model=args.declared_model, transport_note=args.transport_note,
            max_calls=args.max_calls or CALLS[scenario], timeout=args.relay_timeout)
        summary['relay_dir'] = str(spool.resolve())
    else:
        infer = identity = receipts = None
    if infer is not None:
        semantic, category = demo_providers.bind_factories(infer, identity)
        factories = {'semantic_infer_factory': semantic, 'category_infer_factory': category}
        summary['identity'] = identity
    app = create_app(data_path=data, semantic_path=sidecar, fixture=False,
                     allow_local_models=False, allow_local_recommender=False, **factories)
    app.state.provider_receipts = receipts
    app.state.scenario_requests = scenario_requests(scenario)
    return app, port, summary, lambda: None


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
    if not args.reviewed_config or not args.report:
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
               'note': 'Enter the operator token from the reviewed configuration to unlock the page.'}

    def finish():
        report['status'] = 'server_stopped'
        checkpoint()

    return app, PERSONAL_PORT, summary, finish


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--scenario', choices=sorted(SCENARIOS))
    parser.add_argument('--provider', choices=('manual', 'scripted', 'relay', 'personal-cli'),
                        default='manual')
    parser.add_argument('--port', type=int)
    parser.add_argument('--relay-dir')
    parser.add_argument('--declared-model')
    parser.add_argument('--transport-note')
    parser.add_argument('--relay-timeout', type=float, default=600)
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--reviewed-config')
    parser.add_argument('--report')
    parser.add_argument('--fingerprint', action='store_true', help='print the source fingerprint and exit')
    args = parser.parse_args(argv)
    if args.fingerprint:
        print(source_fingerprint())
        return
    if args.port is not None and not 1024 <= args.port <= 65535:
        raise SystemExit('Choose a port between 1024 and 65535')
    require_built_interface()

    app, port, summary, finish = build_app(args)
    app.state.source_fingerprint = summary['source_fingerprint'] = source_fingerprint()
    import uvicorn
    print(json.dumps({'serving': f'http://127.0.0.1:{port}', **summary}, indent=2, default=str), flush=True)
    try:
        uvicorn.run(app, host='127.0.0.1', port=port, proxy_headers=False, server_header=False,
                    log_level='warning')
    finally:
        finish()


if __name__ == '__main__':
    main()
