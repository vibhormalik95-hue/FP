"""Verify packaged bytes and open the real-model app from a fresh extraction.

Run using an environment with this project's Python dependencies installed.
This verifies relocation on the current operating system, not Windows or Colab.
It never invokes Ollama, modifies the source package, or downloads dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


APP_CHECK = r'''
import json
from pathlib import Path
import feedctrl
from fastapi.testclient import TestClient
from feedctrl.api import app

root = Path.cwd().resolve()
assert Path(feedctrl.__file__).resolve().is_relative_to(root), "Import escaped extracted package"
with TestClient(app) as client:
    status = client.get('/api/status').json()
    assert status['data_mode'] == 'processed dataset', status
    assert status['model_mode'] == 'trained model', status
    users = client.get('/api/users').json()
    assert len(users) == 865
    session = client.post('/api/session', json={})
    assert session.status_code == 201
    headers = {'X-Session-ID': session.json()['session_id']}
    params = {'user_id': users[0]['user_id'], 'condition': 'E'}
    response = client.get('/api/feed', params=params, headers=headers)
    assert response.status_code == 200, response.text
    feed = response.json()
    assert len(feed['items']) == 10
    category = feed['items'][0]['categories'][0]
    response = client.post('/api/control', headers=headers,
        json={'user_id': users[0]['user_id'], 'text': 'Mute '+category+'.', 'backend': 'rule'})
    assert response.status_code == 200 and response.json()['applied'], response.text
    muted = client.get('/api/feed', params=params, headers=headers).json()
    assert len(muted['items']) == 10
    assert all(category not in card['categories'] for card in muted['items'])
    page = client.get('/')
    assert page.status_code == 200 and '<div id="root"></div>' in page.text
print(json.dumps({'status': 'passed', 'users': len(users), 'mode': status,
                  'source_imported_from_extraction': True,
                  'checks': ['real data', 'real checkpoint', 'frontend', 'session', 'feed', 'rule mute']}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    args = parser.parse_args()
    archive = Path(args.archive).resolve()
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('Archive CRC check failed')
        prefix = 'cmp9500-recommender/'
        manifest_name = prefix + 'package-manifest.json'
        manifest = json.loads(bundle.read(manifest_name))
        expected = {prefix + row['path'] for row in manifest['files']} | {manifest_name}
        if set(bundle.namelist()) != expected or len(bundle.namelist()) != len(expected):
            raise ValueError('Manifest and archive entries differ')
        for row in manifest['files']:
            name = prefix + row['path']
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Unsafe archive path')
            content = bundle.read(name)
            if len(content) != row['bytes'] or hashlib.sha256(content).hexdigest() != row['sha256']:
                raise ValueError('Manifest fingerprint mismatch: ' + name)
        with tempfile.TemporaryDirectory(prefix='cmp9500-release-') as scratch:
            bundle.extractall(scratch)
            extracted = Path(scratch) / 'cmp9500-recommender'
            result = subprocess.run([sys.executable, '-c', APP_CHECK], cwd=extracted,
                                    capture_output=True, text=True, timeout=180)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            application = json.loads(result.stdout.strip().splitlines()[-1])
    print(json.dumps({'status': 'passed', 'archive': str(archive),
                      'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                      'manifest_files_verified': len(manifest['files']),
                      'extracted_application': application}, indent=2))


if __name__ == '__main__':
    main()
