"""Trusted-code reference-free worker for AIREF E2. Application guard, not OS sandbox."""
from __future__ import annotations
import argparse,hashlib,json,os,platform,socket,sys,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
OPTIONS={'temperature':0,'seed':42,'num_ctx':4096,'num_predict':768,'num_thread':6}
SOURCE_PATHS={'scripts/ai_e2_inference_worker.py','feedctrl/__init__.py','feedctrl/controls.py','feedctrl/experiment2_controls.py'}
RELEASE_FIELDS={'study_id','status','frozen_utc','questions_sha256','model','options','worker_source_sha256','denied_probe_paths','reference_freeze_sha256','protocol_freeze_sha256','timeout_seconds'}
sys.path.insert(0,str(ROOT))
from feedctrl import controls as legacy
from feedctrl import experiment2_controls as controls

def now():return datetime.now(timezone.utc).isoformat()
def digest(b):return hashlib.sha256(b).hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
def norm(path):return os.path.normcase(os.path.abspath(os.fspath(path)))
def install_guard(roots):
    allowed=[norm(r) for r in roots]
    def permitted(path):
        if isinstance(path,int):return path in (0,1,2)
        if not isinstance(path,(str,bytes,os.PathLike)):return False
        p=norm(path)
        return any(p==r or p.startswith(r+os.sep) for r in allowed)
    def audit(event,args):
        if event=='open' and not permitted(args[0]):raise PermissionError('AIREF worker file-access boundary')
        if event in ('os.listdir','os.scandir','os.chdir','os.mkdir','os.remove','os.rmdir') and not permitted(args[0]):raise PermissionError('AIREF worker directory boundary')
        if event in ('os.rename','os.link','os.symlink') and any(not permitted(x) for x in args[:2]):raise PermissionError('AIREF worker path boundary')
        if event=='socket.connect' and (not isinstance(args[1],tuple) or args[1][:2]!=('127.0.0.1',11434)):raise PermissionError('AIREF worker network boundary')
        if event=='socket.getaddrinfo' and args[:2]!=('127.0.0.1',11434):raise PermissionError('AIREF worker DNS boundary')
        if event.startswith(('subprocess.','ctypes.','os.exec','os.spawn')) or event=='os.system':raise PermissionError('AIREF worker execution boundary')
    sys.addaudithook(audit)
    return {'allowed_roots':allowed,'mechanism':'CPython audit hook over trusted reference-free code; not an OS security sandbox'}
def packet(value):
    if set(value)!={'categories','questions'} or value['categories']!=[f'category_{i}' for i in range(31)]:raise ValueError('Invalid question-only envelope')
    rows=value['questions']
    if len(rows)!=100 or len({r['id'] for r in rows})!=100 or len({r['text'] for r in rows})!=100:raise ValueError('Expected 100 unique exact questions')
    if any(set(r)!={'id','text'} or not r['id'].startswith('q_') or not r['text'].strip() for r in rows):raise ValueError('Labels/classes must not enter inference')
    return value['categories'],rows
def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--expected-release-sha256',required=True)
    p.add_argument('--questions',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--opening',type=Path,required=True)
    a=p.parse_args()
    # This package contains only four parser/worker source files, metadata and questions.
    guard=install_guard([ROOT,Path(sys.base_prefix),Path(os.environ.get('SystemRoot',r'C:\Windows')),a.output.parent])
    release_bytes=a.release.read_bytes()
    if digest(release_bytes)!=a.expected_release_sha256:raise ValueError('Custodian release hash mismatch')
    release=json.loads(release_bytes)
    if set(release)!=RELEASE_FIELDS or set(release['worker_source_sha256'])!=SOURCE_PATHS:raise ValueError('Unexpected release schema/source paths')
    if release['timeout_seconds']!=600 or not sys.dont_write_bytecode:raise ValueError('Frozen timeout and -B bytecode policy required')
    if norm(a.release)!=norm(ROOT/'release.json') or norm(a.questions)!=norm(ROOT/'questions.json'):raise ValueError('Only bundle input paths permitted')
    if {f.relative_to(ROOT).as_posix() for f in ROOT.rglob('*') if f.is_file()}!=SOURCE_PATHS|{'release.json','questions.json'}:raise ValueError('Unexpected bundle file; caches forbidden')
    if release['status']!='frozen_before_inference' or release['study_id']!='AIREF-E2-20261014-v1':raise ValueError('Full AI-reference freeze required')
    if release['options']!=OPTIONS:raise ValueError('Frozen generation options differ from worker')
    if sys.version_info[:3]!=(3,14,0):raise ValueError('Frozen Python runtime mismatch')
    for name,expected in release['worker_source_sha256'].items():
        if digest((ROOT/name).read_bytes())!=expected:raise ValueError('Worker source changed')
    probes={}
    for label,path in release['denied_probe_paths'].items():
        try:
            with Path(path).open('rb'):pass
        except PermissionError:probes[label]='denied_without_reading_bytes'
        else:raise ValueError('Reference file accessible to inference: '+label)
    if a.output.exists():raise ValueError('Output must be new')
    provenance=legacy.ollama_provenance('http://127.0.0.1:11434','llama3.1:8b',10)
    if {k:provenance[k] for k in ('model','digest','ollama_version')}!=release['model']:raise ValueError('Frozen model/runtime mismatch')
    save(a.opening,{'opened_utc':now(),'release_sha256':digest(release_bytes),'questions_sha256':release['questions_sha256']})
    a.output.mkdir(parents=True);manifest={'started_utc':now(),'study_id':release['study_id'],'status':'started','scope':'predictions only; no reference access or scoring'}
    try:
        raw_questions=a.questions.read_bytes()
        if digest(raw_questions)!=release['questions_sha256']:raise ValueError('Question-only bytes changed')
        categories,rows=packet(json.loads(raw_questions))
        save(a.output/'protocol-before-inference.json',{'release':release,'guard':guard,'reference_read_probes':probes,'provenance':provenance,'prompt':controls.COMPOUND_PROMPT,'schema':controls.compound_schema(categories),'options':release['options'],'python':sys.version})
        outcomes=[]
        for backend in ('rule_compound','ollama_compound'):
            for n,row in enumerate(rows,1):
                start=time.monotonic();command={'operation':'clarify','directives':[]};result=None;error=None
                save(a.output/'attempts'/f'{backend}-{row["id"]}.json',{'id':row['id'],'backend':backend,'started_utc':now(),'policy':'one attempt; terminal prediction separate; interruption aborts this study version'})
                try:
                    kwargs={} if backend=='rule_compound' else {'model':'llama3.1:8b','base_url':'http://127.0.0.1:11434','timeout':600,'cache_dir':a.output/'raw_llm','seed':42,'num_thread':6}
                    result=controls.parse_control(row['text'],categories,backend=backend,**kwargs)
                    command={'operation':result['operation'],'directives':[{k:d[k] for k in ('operation','category','strength','floor','condition_category')} for d in result['directives']]}
                except Exception as exc:error=f'{type(exc).__name__}: {exc}'
                record={**row,'backend':backend,'command':command,'raw_result':result,'error':error,'completed_utc':now(),'wall_seconds':time.monotonic()-start}
                save(a.output/'predictions'/f'{backend}-{row["id"]}.json',record);outcomes.append(record)
                if n%10==0:print(json.dumps({'backend':backend,'completed':n,'errors_so_far':sum(bool(r['error']) for r in outcomes if r['backend']==backend)}),flush=True)
        if legacy.ollama_provenance('http://127.0.0.1:11434','llama3.1:8b',10)!=provenance:raise ValueError('Model/runtime drift')
        if len(outcomes)!=200 or len({(r['backend'],r['id']) for r in outcomes})!=200:raise ValueError('Incomplete terminal prediction coverage')
        save(a.output/'failures.json',[r for r in outcomes if r['error']])
        manifest.update({'status':'predictions_complete','prediction_count':len(outcomes),'raw_response_count':len(list((a.output/'raw_llm').glob('*.json'))),'failures':sum(bool(r['error']) for r in outcomes)})
    except Exception as exc:manifest.update({'status':'failed_or_incomplete','error':f'{type(exc).__name__}: {exc}'})
    finally:
        manifest.update({'completed_utc':now(),'files':{str(f.relative_to(a.output)):digest(f.read_bytes()) for f in sorted(a.output.rglob('*')) if f.is_file()}})
        save(a.output/'manifest.json',manifest)
    print(json.dumps(manifest|{'files':len(manifest['files'])}),flush=True)
    return 0 if manifest['status']=='predictions_complete' else 2
if __name__=='__main__':raise SystemExit(main())
