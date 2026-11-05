"""Explicit development smoke in a NEW local session; never a held-out study.

Usage: python scripts/smoke_semantic_groups.py --output PRIVATE_JSON
The default declared scope is source-selected, not query retrieval or unbiased.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8774')
    parser.add_argument('--scope', default='deliverables/2026-11-05-semantic-review/development-scope.json')
    parser.add_argument('--text', default='I am not hungry. Hide anything that makes me hungry.')
    parser.add_argument('--output', required=True)
    parser.add_argument('--manual-action', action='store_true', help='Declared grounding-only ablation, never an automatic fallback')
    args = parser.parse_args()
    if not args.base.startswith('http://127.0.0.1:'):
        raise ValueError('Only the explicit local prototype is supported')
    receipt = {'kind': 'source-selected development smoke, not semantic accuracy evaluation',
        'started_utc': datetime.now(timezone.utc).isoformat(), 'base': args.base,
        'scope': json.loads(Path(args.scope).read_text(encoding='utf-8')), 'text': args.text}
    token = None
    def call(path, body=None):
        request = urllib.request.Request(args.base + '/api/' + path,
            data=json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None,
            headers={'Content-Type': 'application/json', **({'X-Session-ID': token} if token else {})})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=195) as response:
                return {'http': response.status, 'seconds': time.monotonic() - start, 'body': json.load(response)}
        except urllib.error.HTTPError as error:
            return {'http': error.code, 'seconds': time.monotonic() - start, 'body': json.load(error)}
    try:
        receipt['status'] = call('status')
        session = call('session', {})
        token = session['body']['session_id']  # private credential excluded from the receipt
        receipt['ae_before'] = call('compare?user_id=14')
        receipt['neutral'] = call('semantic/groups?user_id=14')
        receipt['preview'] = call('semantic/preview', {'user_id': 14, 'label': 'Appetite-related development group',
            'candidate_ids': receipt['scope']['ids'], 'text': args.text, 'backend': 'ollama',
            'action_source': 'manual' if args.manual_action else 'ollama',
            'operation': 'exclude', 'strength': 'none'})
        receipt['action_source'] = 'manual' if args.manual_action else 'ollama'
        proposal = receipt['preview']['body']
        if receipt['preview']['http'] == 200 and proposal.get('ready'):
            receipt['apply'] = call('semantic/apply', {'user_id': 14, 'plan_id': proposal['plan_id']})
            undo = call('semantic/history/preview', {'user_id': 14, 'action': 'undo'})
            receipt['undo_preview'] = undo
            if undo['http'] == 200 and undo['body'].get('ready'):
                receipt['undo_apply'] = call('semantic/apply', {'user_id': 14, 'plan_id': undo['body']['plan_id']})
        receipt['ae_after'] = call('compare?user_id=14')
        receipt['ae_unchanged'] = receipt['ae_before']['body'] == receipt['ae_after']['body']
    except Exception as error:
        receipt['exception'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        receipt['ended_utc'] = datetime.now(timezone.utc).isoformat()
        Path(args.output).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        p = receipt.get('preview', {})
        print(json.dumps({'output': args.output, 'http': p.get('http'), 'seconds': p.get('seconds'),
            'ready': p.get('body', {}).get('ready'), 'status': p.get('body', {}).get('status'),
            'reason': p.get('body', {}).get('reason'), 'exception': receipt.get('exception'),
            'ae_unchanged': receipt.get('ae_unchanged')}, ensure_ascii=True))


if __name__ == '__main__':
    main()
