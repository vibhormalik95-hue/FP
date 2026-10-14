"""Read-only local runtime and frozen-E1 receipt. No installs or model inference."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
p.add_argument('--archive', type=Path, required=True)
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
receipt = {'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'computer': os.environ.get('COMPUTERNAME'), 'user': os.environ.get('USERNAME'),
           'platform': platform.platform(), 'python_executable': sys.executable,
           'project_root': str(root), 'archive_root': str(args.archive), 'commands': [], 'api': {}}
commands = [
    ['git', 'status', '--short', '--branch'], ['git', 'remote', '-v'],
    ['git', 'rev-parse', 'HEAD'], ['git', 'branch', '--show-current'],
    ['git', 'ls-remote', 'origin', 'refs/heads/main', 'refs/heads/codex/oct13-safe-engineering'],
    ['gh', 'api', 'user', '--jq', '{login: .login, id: .id, email: .email}'],
    ['ollama', '--version'], ['ollama', 'list'], ['ollama', 'ps'],
    ['powershell', '-NoProfile', '-Command', 'Get-Process *ollama* | Select-Object Id,ProcessName,Path | ConvertTo-Json'],
    [sys.executable, str(root / 'scripts/verify_frozen_e1.py'), str(args.archive)],
]
for command in commands:
    start = dt.datetime.now(dt.timezone.utc).isoformat()
    r = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
    receipt['commands'].append({'argv': command, 'started_utc': start, 'exit_code': r.returncode,
                                'stdout': r.stdout, 'stderr': r.stderr})
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for endpoint in ('version', 'tags', 'ps'):
    url = 'http://127.0.0.1:11434/api/' + endpoint
    try:
        with opener.open(url, timeout=10) as response:
            raw = response.read()
            receipt['api'][endpoint] = {'url': url, 'http_status': response.status,
                'body': json.loads(raw), 'body_sha256': hashlib.sha256(raw).hexdigest()}
    except Exception as e:
        receipt['api'][endpoint] = {'url': url, 'error': repr(e)}
receipt['completed_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open('x', encoding='utf-8') as stream:
    json.dump(receipt, stream, indent=2)
print(json.dumps({'receipt': str(args.output), 'computer': receipt['computer'],
    'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
    'command_exit_codes': [r['exit_code'] for r in receipt['commands']],
    'api_statuses': {k: v.get('http_status', v.get('error')) for k,v in receipt['api'].items()}}))
