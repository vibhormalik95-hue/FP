"""New mechanics receipt. Replays retained replies; never calls a model or edits old evidence."""
from copy import deepcopy
from pathlib import Path
import datetime, hashlib, json, subprocess, sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OLD = HERE / 'replay-inputs'
BASE = '71234a15f26e73f30bfc8918a201ce5ef5cdcd81'
sys.path.insert(0, str(REPO))
from fastapi.testclient import TestClient
from feedctrl.api import create_app
from feedctrl.synthetic_drafts import source_version

def canon(v): return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def save(name, v):
    # New output only; never overwrite the historical delivered receipt.
    with (Path.cwd() / name).open('xb') as f: f.write(canon(v))

class Replay:
    def __init__(self): self.calls = []
    def __call__(self, payload, schema):
        for n in (1, 2):
            req = json.loads((OLD / f'call-{n}.request.json').read_bytes())
            if canon(payload) == canon(req['payload']) and canon(schema) == canon(req['response_schema']):
                raw = (OLD / f'call-{n}.terminal.json').read_bytes()
                self.calls.append({'retained_stage': n, 'terminal_sha256': sha(raw), 'new_generation': False})
                return deepcopy(json.loads(raw)['parsed'])
        raise ValueError('Replay accepts only the exact retained payload/schema; no inference or repair')

def make_app():
    replay = Replay()
    provenance = {'backend': 'retained-reply-replay', 'model': 'Retained Opus 5.5 Medium UI reply; no fresh model call',
                  'digest': '912aeb961c1d237aacf300d3bf13019f9aa4abdf44ae5432802dba2747aaeb8d', 'digest_kind': 'prior_protocol_sha256_not_weights'}
    app = create_app(data_path=OLD/'data.json', model_path=HERE/'NO-TRAINED-MODEL', semantic_path=OLD/'source.csv',
                     semantic_infer_factory=lambda: (replay, deepcopy(provenance)))
    app.state.demo.topic_index['source'] = 'synthetic://comp-claude-copy-indirect-dev-20261105/desk-tools'
    app.state.demo.initial_profile = lambda user: 'Wholly invented desk-tool metadata and diagnostic history. No real media or trained relevance.'
    app.state.delivery_replay = replay
    return app

def run():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO).decode().strip()
    subprocess.check_call(['git','diff','--exit-code',BASE,'HEAD','--','feedctrl','web/src'],cwd=REPO)
    subprocess.check_call(['git','diff','--exit-code','HEAD','--','feedctrl','web/src'],cwd=REPO)
    app = make_app(); demo = app.state.demo; receipts = []
    with TestClient(app) as c:
        headers = {'X-Session-ID': c.post('/api/session', json={}).json()['session_id']}
        def call(method, path, body=None):
            r = c.request(method, path, headers=headers, json=body)
            receipts.append({'method': method, 'path': path, 'request': body, 'status': r.status_code, 'response': r.json()})
            assert r.status_code == 200, r.text
            return r
        def snap():
            return {'semantic': call('GET','/api/semantic/groups?user_id=1').json(),
                    'ae': call('GET','/api/compare?user_id=1').json(),
                    'literal': call('GET','/api/steering?user_id=1').json(),
                    'source': deepcopy(demo.topic_index), 'source_version': source_version(demo),
                    'categories': deepcopy(demo.categories), 'items': deepcopy(demo.items)}
        baseline = snap()
        p = call('POST','/api/semantic/preview', {'user_id':1,'text':'Hide desk tools that would tie me to a wall socket.',
            'label':'Wall-tethered desk tools','candidate_ids':[71001,71002,71003,71004,71005,71006,71007,71008],
            'backend':'configured_model','action_source':'model','mode':'replace'}).json()
        assert p['ready'] and not p['applied']
        assert p['groups'][0]['proposal']['item_ids'] == [71001,71003,71006]
        preview = snap(); assert preview == baseline
        call('POST','/api/semantic/apply', {'user_id':1,'plan_id':p['plan_id']})
        active = snap()
        assert len(active['semantic']['groups']) == 1 and active['semantic']['feed']['available_items'] == 5
        call('POST','/api/reset', {'user_id':1})
        reset = snap()
        assert reset['semantic']['groups'] == [] and reset['semantic']['feed']['available_items'] == 8
        assert not reset['semantic']['can_undo']
        for key in ('ae','source','source_version','categories','items'): assert reset[key] == baseline[key], key
        for key in baseline['literal']:
            if key != 'revision': assert reset['literal'][key] == baseline['literal'][key], key
        state = demo.user_state(headers['X-Session-ID'], 1)
        assert not state['semantic_history'] and state['semantic_pending'] is None and state['semantic_definition_pending'] is None
        stale = c.post('/api/semantic/apply', headers=headers, json={'user_id':1,'plan_id':p['plan_id']})
        assert stale.status_code == 409
        receipts.append({'path':'/api/semantic/apply','stage':'stale_after_reset','status':stale.status_code,'response':stale.json()})
        assert snap() == reset
    result = {'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source_commit':head,'application_source_base':BASE,
        'kind':'offline retained-output replay through actual FastAPI TestClient routes; not browser evidence or new model accuracy',
        'actual_generation_calls':0,'replayed_adapter_calls':app.state.delivery_replay.calls,
        'eligible_sequence':[8,5,8], 'active_group_reset':True,'stale_plan_after_reset_http':409,
        'ae_source_categories_items_preserved':True,
        'snapshots':{'baseline':baseline,'preview':preview,'active':active,'reset':reset},'http_receipts':receipts}
    save('ACTIVE-GROUP-RESET.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('snapshots','http_receipts','replayed_adapter_calls')}))

if __name__ == '__main__': run()
