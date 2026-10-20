"""Run an auditable experiment workflow with explicit backend and failure status."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.output_safety import project_path, require_new_output


def configure_paths(args):
    """Allocate new data/models within the run unless explicitly reading frozen inputs."""
    if len(set(args.seeds)) != len(args.seeds):
        raise ValueError('Seeds must be unique; duplicate seeds would overwrite a checkpoint')
    output = args.output or ('results/fixture/run' if args.fixture else 'results/reproduction')
    out = require_new_output(output, ROOT, directory=True)
    default_data = ('data/fixture.json' if args.fixture else 'data/processed.json') if args.skip_data else out / 'data/processed.json'
    default_models = ('results/fixture/models' if args.fixture else 'results/models') if args.skip_train else out / 'models'
    data = project_path(args.data or default_data, ROOT)
    models = project_path(args.models or default_models, ROOT)
    if not args.skip_data:
        require_new_output(data, ROOT, directory=False)
    elif not data.is_file():
        raise ValueError(f'--skip-data requires an existing input file: {data}')
    if not args.skip_train:
        require_new_output(models, ROOT, directory=True)
    elif not all((models / f'seed_{seed}' / 'model.pt').is_file() for seed in args.seeds):
        raise ValueError(f'--skip-train requires existing checkpoints for all requested seeds: {models}')
    if (data == out or models == out or data == models or data.is_relative_to(models)
            or out.is_relative_to(models) or out.is_relative_to(data) or models.is_relative_to(data)):
        raise ValueError('Use distinct output, data, and model paths; data must not be inside the model directory')
    args.output, args.data, args.models = str(out), str(data), str(models)
    return out

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['rule','ollama'], default='ollama')
    p.add_argument('--fixture', action='store_true', help='Synthetic software smoke test, not research evidence')
    p.add_argument('--output')
    p.add_argument('--data')
    p.add_argument('--max-users', type=int, default=0)
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--seeds', type=int, nargs='+', default=[42,43,44])
    p.add_argument('--device', default='cpu')
    p.add_argument('--skip-data', action='store_true')
    p.add_argument('--skip-train', action='store_true')
    p.add_argument('--models')
    p.add_argument('--skip-tests', action='store_true')
    p.add_argument('--skip-parser', action='store_true')
    p.add_argument('--ollama-url', default='http://127.0.0.1:11434')
    p.add_argument('--ollama-model', default='llama3.1:8b')
    p.add_argument('--timeout', type=float, default=300)
    p.add_argument('--num-thread', type=int, default=6)
    p.add_argument('--skip-explanations', action='store_true')
    args = p.parse_args()
    os.chdir(ROOT)
    try:
        out = configure_paths(args)
    except ValueError as exc:
        p.error(str(exc))
    out.mkdir(parents=True,exist_ok=True)
    manifest={'started_utc':datetime.now(timezone.utc).isoformat(),'status':'running',
              'configuration':vars(args),'platform':platform.platform(),'python':sys.version,
              'steps':[],'claim':'synthetic software fixture' if args.fixture else 'real dataset experiment'}
    target = out/'pipeline_manifest.json'
    def save():
        target.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    def run(name, command):
        entry={'stage':name,'command':command,'started_utc':datetime.now(timezone.utc).isoformat()}
        manifest['steps'].append(entry);save()
        print('Running',name,flush=True)
        start=time.monotonic()
        environment = dict(os.environ, FEEDCTRL_PARSER_CACHE=str(out/'raw_llm_cache'))
        with (out/f'{name}.log').open('w',encoding='utf-8') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,env=environment)
        entry.update(exit_code=result.returncode,elapsed_seconds=time.monotonic()-start);save()
        if result.returncode:
            raise RuntimeError(f'{name} failed with exit {result.returncode}; see {out/name}.log')
    try:
        if args.backend=='ollama':
            from feedctrl.controls import ollama_provenance
            manifest['ollama']=ollama_provenance(args.ollama_url,args.ollama_model)
        if not args.skip_tests:
            run('tests',[sys.executable,'-m','pytest','-q'])
        if not args.skip_data:
            command=[sys.executable,'scripts/fetch_data.py','--output',args.data,'--max-users',str(args.max_users)]
            if args.fixture: command.append('--fixture')
            run('data',command)
        data_bytes=Path(args.data).read_bytes()
        data=json.loads(data_bytes)
        real=data['metadata'].get('kind')=='kuairec'
        if args.fixture==real:
            raise RuntimeError('Dataset kind does not match --fixture mode; use a separate data/output path')
        manifest['data_sha256']=hashlib.sha256(data_bytes).hexdigest()
        manifest['data_metadata']=data['metadata'];save()
        if not args.skip_train:
            run('training',[sys.executable,'scripts/train.py','--data',args.data,'--output',args.models,
                '--epochs',str(args.epochs),'--device',args.device,'--seeds',*[str(s) for s in args.seeds]])
        if not args.skip_parser:
            run('parser',[sys.executable,'scripts/run_parser.py','--backend',args.backend,'--output',str(out/'parser'),
                '--model',args.ollama_model,'--base-url',args.ollama_url,'--timeout',str(args.timeout),
                '--num-thread',str(args.num_thread),'--cache-dir',str(out/'raw_llm_cache')])
        run('evaluation_matrix',[sys.executable,'scripts/evaluate_matrix.py','--data',args.data,
            '--models',args.models,'--output',str(out/'evaluation'),'--backend',args.backend,
            '--seeds',*[str(s) for s in args.seeds],'--ollama-url',args.ollama_url,
            '--ollama-model',args.ollama_model,'--timeout',str(args.timeout),'--num-thread',str(args.num_thread)])
        if not args.skip_explanations:
            run('explanations',[sys.executable,'scripts/generate_explanations.py','--data',args.data,
                '--model-dir',str(Path(args.models)/f'seed_{args.seeds[0]}'),
                '--backend','ollama' if args.backend=='ollama' else 'template','--count','10',
                '--output',str(out/'explanations.json'),'--ollama-model',args.ollama_model,
                '--base-url',args.ollama_url,'--timeout',str(args.timeout)])
        manifest['status']='complete'
    except Exception as exc:
        manifest['status']='failed';manifest['error']=f'{type(exc).__name__}: {exc}'
        print(manifest['error'],file=sys.stderr)
    finally:
        manifest['finished_utc']=datetime.now(timezone.utc).isoformat();save()
    print(target)
    return 0 if manifest['status']=='complete' else 1

if __name__=='__main__':
    raise SystemExit(main())
