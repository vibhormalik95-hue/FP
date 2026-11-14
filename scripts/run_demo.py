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
                  configuration that the guarded validation driver already checks.

The server binds to 127.0.0.1 only. Local models and the trained recommender stay
disabled; the bundled scenarios use eight invented descriptions and a labelled
diagnostic scorer. Nothing here sends email, publishes or stores credentials.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'tools' / 'hosted_validation_current' / 'inputs'
SCENARIOS = {
    'category': INPUTS / '01-category-discovery',
    'hunger': INPUTS / '02-hunger-continuation',
}
# Calls needed by one complete pass: definition + membership + evidence
# assessment for a new category; action + grounding for an indirect request.
CALLS = {'category': 3, 'hunger': 2}


def scenario_paths(name):
    folder = SCENARIOS[name]
    data, sidecar = folder / 'app-data.json', folder / 'metadata.csv'
    if not data.is_file() or not sidecar.is_file():
        raise SystemExit(f'Scenario files are missing under {folder}')
    return data, sidecar


def build_app(args):
    """Return ``(app, port, summary)`` for the selected provider."""
    sys.path.insert(0, str(ROOT))
    if args.provider == 'personal-cli':
        return build_personal_cli_app(args)

    from feedctrl.api import create_app
    from feedctrl import demo_providers

    data, sidecar = scenario_paths(args.scenario)
    factories = {}
    summary = {'scenario': args.scenario, 'provider': args.provider}
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
            max_calls=args.max_calls or CALLS[args.scenario], timeout=args.relay_timeout)
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
    return app, args.port, summary


def build_personal_cli_app(args):
    """Serve the exact app object that the reviewed validation driver builds.

    All checks stay in ``tools/hosted_validation_current/driver.py``: the six
    explicit assertions, the pinned source and inputs, the executable hash and
    the call allowance. This function adds only an HTTP listener on the origin
    that the driver already declares, so the same run can be reviewed in a
    browser. The driver's consumed marker prevents a configuration being reused.
    """
    if not args.reviewed_config or not args.report:
        raise SystemExit('personal-cli needs --reviewed-config and --report')
    driver_path = ROOT / 'tools' / 'hosted_validation_current' / 'driver.py'
    spec = importlib.util.spec_from_file_location('reviewed_driver', driver_path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)

    config_path, report_path = Path(args.reviewed_config), Path(args.report)
    config = json.loads(config_path.read_text(encoding='utf-8'))
    driver.validate(config, ROOT)
    driver.require(config.get('input_manifest_sha256') == driver.INPUT_MANIFEST_SHA256,
                   'Reviewed input pin required')
    bundle = driver.load_inputs(INPUTS, config['scenario'])
    driver.require(not report_path.exists(), 'Report already exists; no rerun or overwrite')
    marker = Path(str(config_path.resolve()) + '.consumed')
    with marker.open('x', encoding='utf-8') as handle:
        handle.write(driver.digest(config_path))

    from feedctrl.windows_job_runner import run_windows_job
    report = driver.new_report(config['scenario'], bundle)
    report.update(config_sha256=driver.digest(config_path), identity_basis=config['identity_basis'],
                  evidence_kind='served application; reviews made in the browser by the operator')
    holder = {}

    def checkpoint():
        if 'app' in holder:
            report['receipts'] = holder['app'].state.hosted_model_receipts
            report['attempted'] = holder['budget'].attempted
        report_path.write_text(json.dumps(driver.redact(report, config), indent=2), encoding='utf-8')

    app, budget = driver.build(config, ROOT, bundle, run_windows_job, report, checkpoint)
    holder.update(app=app, budget=budget)
    checkpoint()
    summary = {'scenario': config['scenario'], 'provider': 'personal-cli',
               'model': config['model'], 'max_calls': budget.max_calls,
               'report': str(report_path.resolve()),
               'note': 'Enter the operator token from the reviewed configuration to unlock the page.'}
    return app, 8765, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--scenario', choices=sorted(SCENARIOS), default='category')
    parser.add_argument('--provider', choices=('manual', 'scripted', 'relay', 'personal-cli'),
                        default='manual')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--relay-dir')
    parser.add_argument('--declared-model')
    parser.add_argument('--transport-note')
    parser.add_argument('--relay-timeout', type=float, default=600)
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--reviewed-config')
    parser.add_argument('--report')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        raise SystemExit('Choose a port between 1024 and 65535')
    if not (ROOT / 'web' / 'dist' / 'index.html').is_file():
        raise SystemExit('The built interface is missing: run "npm ci" and "npm run build" in web/')

    app, port, summary = build_app(args)
    import uvicorn
    print(json.dumps({'serving': f'http://127.0.0.1:{port}', **summary}, indent=2, default=str), flush=True)
    uvicorn.run(app, host='127.0.0.1', port=port, proxy_headers=False, server_header=False,
                log_level='warning')


if __name__ == '__main__':
    main()
