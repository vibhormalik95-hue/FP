"""Run a command with a temporary local Ollama server in this network namespace.

Examples:
 python scripts/with_ollama.py -- python scripts/run_parser.py --backend ollama
 python scripts/with_ollama.py --pull -- python scripts/run_parser.py --backend ollama
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',default=shutil.which('ollama') or '/tmp/ollama-runtime/bin/ollama')
    parser.add_argument('--models',default=os.environ.get('OLLAMA_MODELS',''))
    parser.add_argument('--model',default='llama3.1:8b')
    parser.add_argument('--pull',action='store_true')
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command and args.command[0]=='--' else args.command
    if not command:
        parser.error('a command is required after --')
    if not Path(args.binary).is_file():
        parser.error('Ollama binary not found; install Ollama first (docs/LLM_RUNTIME.md)')
    env={**os.environ,'OLLAMA_HOST':'127.0.0.1:11434','OLLAMA_NO_CLOUD':'true',
         'OLLAMA_NUM_PARALLEL':'1','OLLAMA_MAX_LOADED_MODELS':'1'}
    if args.models:
        env['OLLAMA_MODELS']=str(Path(args.models).resolve())
    (ROOT/'results').mkdir(exist_ok=True)
    log_path=ROOT/'results/ollama_server.log'
    with log_path.open('a',encoding='utf-8') as log:
        server=subprocess.Popen([args.binary,'serve'],env=env,stdout=log,stderr=log)
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(150):
                if server.poll() is not None:
                    raise RuntimeError(f'Ollama server exited; inspect {log_path}. Quit an existing server first.')
                try:
                    with opener.open('http://127.0.0.1:11434/api/version',timeout=1) as response:
                        print('Ollama ready:',response.read().decode(),flush=True)
                    break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError('Ollama did not become ready within 30 seconds')
            if args.pull:
                subprocess.run([args.binary,'pull',args.model],env=env,check=True)
            return subprocess.run(command,env=env).returncode
        finally:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill();server.wait(timeout=5)

if __name__=='__main__':
    raise SystemExit(main())
