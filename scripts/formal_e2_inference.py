"""Reference-free E2 inference worker. Run only in the approved restricted OS account.

Custodian verifies human gates/full freeze elsewhere and signs a metadata-only release.
This worker never imports the evaluator, reads labels/data or calculates accuracy.
Existing E2 parser, prompt, validation and model calls are reused unchanged.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from feedctrl import controls as legacy
from feedctrl import experiment2_controls as parser

MODEL={'model':'llama3.1:8b','digest':'46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e','ollama_version':'0.34.0'}
OPTIONS={'temperature':0,'seed':42,'num_ctx':4096,'num_predict':768,'num_thread':6}
SOURCE_NAMES={'scripts/formal_e2_inference.py','feedctrl/__init__.py','feedctrl/controls.py','feedctrl/experiment2_controls.py'}
PROTECTED={'author_bank','independent_annotations','adjudication','agreement_record','annotation_commit','ranking_data'}
DEPLOYMENT=Path(r'C:\ProgramData\COMP9500\FormalE2\inference')
TRUST_KEYS={'study_id','custodian_identity','runner_sid','public_key_b64','opening_ledger','private_inventory_sha256','protected_roots'}
RELEASE_KEYS={'study_id','release_id','custodian_identity','runner_sid','trust_sha256','full_freeze_sha256','protocol_review_sha256','private_inventory_sha256','gate_status','created_utc','case_count','questions_sha256','source_sha256','protected_files','opening_ledger','model_provenance','model_options'}
def now():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def new_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
def current_sid():
    r=subprocess.run([r'C:\Windows\System32\whoami.exe','/user','/fo','csv','/nh'],capture_output=True,text=True,check=True)
    matches=re.findall(r'S-1-\d+(?:-\d+)+',r.stdout)
    if len(matches)!=1:raise ValueError('Cannot establish the actual Windows runner SID')
    return matches[0]
def require_protected_deployment():
    if ROOT!=DEPLOYMENT:raise ValueError('Candidate only: deploy through the custodian-controlled read-only launcher before formal use')
    # Custodian-controlled anchor, not a caller-selected public key.
    trust_path=DEPLOYMENT/'trusted-custodian.json'
    try:
        with trust_path.open('r+b'):pass
    except PermissionError:pass
    else:raise ValueError('Runner can modify its trust enrollment')
    try:
        with tempfile.TemporaryFile(dir=DEPLOYMENT):pass
    except PermissionError:pass
    else:raise ValueError('Runner can create/replace files in the deployment directory')
    return trust_path
def verify_signature(raw,signature,trust):
    # The real custodian supplies/enrolls this key. No study key is generated here.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if set(trust)!=TRUST_KEYS:raise ValueError('Trust enrollment schema mismatch')
    if not trust.get('public_key_b64') or not trust.get('runner_sid') or not trust.get('custodian_identity'):
        raise ValueError('Named custodian, enrolled public key and restricted runner SID are required')
    key=Ed25519PublicKey.from_public_bytes(base64.b64decode(trust['public_key_b64'],validate=True))
    key.verify(signature,raw)
def validate_release(release,trust,trust_hash,sid):
    if set(release)!=RELEASE_KEYS:raise ValueError('Release must contain only the approved metadata fields')
    if release['gate_status']!='verified_human_attestations_and_full_freeze':raise ValueError('Full human gate and freeze release required')
    for field in ('study_id','custodian_identity','runner_sid','opening_ledger','private_inventory_sha256'):
        if not trust.get(field) or release[field]!=trust[field]:raise ValueError('Trust/release identity mismatch: '+field)
    if release['runner_sid']!=sid:raise ValueError('Wrong OS identity; directories alone do not isolate references')
    if release['trust_sha256']!=trust_hash:raise ValueError('Trust enrollment changed')
    for field in ('full_freeze_sha256','protocol_review_sha256','questions_sha256','trust_sha256','private_inventory_sha256'):
        if not re.fullmatch('[0-9a-f]{64}',release[field]):raise ValueError('Invalid bound hash: '+field)
    for field in ('study_id','release_id'):
        if not re.fullmatch('[A-Za-z0-9_-]{1,80}',release[field]):raise ValueError('Unsafe study/release identifier')
    stamp=datetime.fromisoformat(release['created_utc'])
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('Invalid actual release time')
    if release['case_count']!=100:raise ValueError('This candidate preserves the original 100-case design; revise prospectively for another size')
    if release['model_provenance']!=MODEL or release['model_options']!=OPTIONS:raise ValueError('Model/runtime/options differ from candidate lock')
    if set(release['source_sha256'])!=SOURCE_NAMES:raise ValueError('Incorrect worker source inventory')
    if set(release['protected_files'])!=PROTECTED:raise ValueError('All label-bearing and held-out data files must be protected')
    paths=[]
    for identity in release['protected_files'].values():
        if set(identity)!={'path','sha256'} or not re.fullmatch('[0-9a-f]{64}',identity['sha256']):raise ValueError('Custodian-signed private inventory required')
        paths.append(str(Path(identity['path'])).casefold())
    if len(set(paths))!=len(paths):raise ValueError('Protected artifact paths must be distinct')
    if not Path(release['opening_ledger']).is_absolute():raise ValueError('Opening ledger must be an absolute frozen path')
def require_denied_trees(roots):
    if not isinstance(roots,list) or not roots:raise ValueError('Protected private tree inventory is required')
    for name in roots:
        if not Path(name).is_absolute():raise ValueError('Private tree must be absolute')
        try:
            with os.scandir(name):pass # No names or contents are read.
        except PermissionError:pass
        except OSError as error:raise ValueError('Private tree boundary unverifiable') from error
        else:raise ValueError('Private reference tree is enumerable by runner')
def require_denied_files(files):
    evidence={}
    for label,identity in files.items():
        path=Path(identity['path'])
        if not path.is_absolute() or str(path).startswith('\\\\'):raise ValueError('Protected files must be actual local absolute paths')
        try:
            # Probe read permission without reading a single reference byte.
            with path.open('rb'):pass
        except PermissionError:evidence[label]='read denied before opening questions'
        except OSError as error:raise ValueError('Missing/unverifiable protected file: '+label) from error
        else:raise ValueError('References accessible to runner: '+label)
    return evidence
def validate_questions(packet,expected_count=100):
    if set(packet)!={'categories','questions'}:raise ValueError('Question packet must not contain references or class labels')
    cats=packet['categories']
    if cats!=[f'category_{i}' for i in range(31)]:raise ValueError('Unexpected frozen public category vocabulary')
    rows=packet['questions']
    if len(rows)!=expected_count:raise ValueError('Question count mismatch')
    ids=set();texts=set()
    for row in rows:
        if set(row)!={'id','text'}:raise ValueError('Only opaque ID and exact text may reach inference')
        if not re.fullmatch('[A-Za-z0-9_-]{1,80}',row['id']) or row['id'] in ids:raise ValueError('Unsafe/duplicate question ID')
        if not isinstance(row['text'],str) or not row['text'].strip() or row['text'] in texts:raise ValueError('Empty/duplicate exact wording')
        ids.add(row['id']);texts.add(row['text'])
    return cats,rows
def collect_predictions(rows,categories,out):
    records=[]
    for backend in ('rule_compound','ollama_compound'):
        for index,row in enumerate(rows,1):
            start=time.monotonic();command={'operation':'clarify','directives':[]};raw=None;error=None
            try:
                kwargs={} if backend=='rule_compound' else {'model':MODEL['model'],'base_url':'http://127.0.0.1:11434','timeout':600,'cache_dir':out/'raw_llm','seed':42,'num_thread':6}
                raw=parser.parse_control(row['text'],categories,backend=backend,**kwargs)
                command={'operation':raw['operation'],'directives':[{k:d[k] for k in ('operation','category','strength','floor','condition_category')} for d in raw['directives']]}
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
            record={**row,'backend':backend,'command':command,'raw_result':raw,'error':error,'completed_utc':now(),'wall_seconds':time.monotonic()-start}
            new_json(out/'predictions'/f'{backend}-{row["id"]}.json',record);records.append(record)
            if index%10==0:print(json.dumps({'backend':backend,'attempts':index}),flush=True)
    return records
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('release','signature','questions','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();trust_path=require_protected_deployment()
    if sys.version_info[:3]!=(3,14,0):raise ValueError('Candidate requires the recorded Python 3.14.0 runtime')
    trust_raw=trust_path.read_bytes();trust=json.loads(trust_raw);release_raw=a.release.read_bytes()
    verify_signature(release_raw,a.signature.read_bytes(),trust)
    release=json.loads(release_raw);validate_release(release,trust,hashlib.sha256(trust_raw).hexdigest(),current_sid())
    for name,digest in release['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Worker source changed: '+name)
    boundary=require_denied_files(release['protected_files'])
    require_denied_trees(trust['protected_roots'])
    provenance=legacy.ollama_provenance('http://127.0.0.1:11434',MODEL['model'],10)
    if {k:provenance[k] for k in MODEL}!=MODEL:raise ValueError('Installed model/runtime differs from frozen identity')
    if a.output.exists():raise ValueError('Output must be genuinely new')
    opening=Path(release['opening_ledger'])/(release['study_id']+'.json')
    new_json(opening,{'opened_utc':now(),'release_sha256':hashlib.sha256(release_raw).hexdigest(),'questions_sha256':release['questions_sha256'],'output':str(a.output.resolve())})
    a.output.mkdir(parents=True);status={'started_utc':now(),'status':'started','scope':'reference-free inference; accuracy and ranking require protected scoring later'}
    try:
        # Claim opening before reading cases; hash and parse exactly the same bytes once.
        question_bytes=a.questions.read_bytes()
        if hashlib.sha256(question_bytes).hexdigest()!=release['questions_sha256']:raise ValueError('Question-only package hash changed')
        categories,rows=validate_questions(json.loads(question_bytes))
        new_json(a.output/'protocol-before-inference.json',{'release':release,'boundary':boundary,'prompt':parser.COMPOUND_PROMPT,'schema':parser.compound_schema(categories),'provenance':provenance,'options':OPTIONS,'python':sys.version,'source_sha256':release['source_sha256']})
        records=collect_predictions(rows,categories,a.output)
        post=legacy.ollama_provenance('http://127.0.0.1:11434',MODEL['model'],10)
        if post!=provenance:raise ValueError('Runtime changed during inference')
        new_json(a.output/'failures.json',[r for r in records if r['error']])
        status.update({'status':'predictions_complete_pending_protected_scoring','outcomes':len(records),'parser_failures':sum(bool(r['error']) for r in records),'formal_hypotheses':'not_assessed_by_worker'})
    except Exception as exc:
        status.update({'status':'failed_or_incomplete','error':f'{type(exc).__name__}: {exc}'})
    finally:
        status.update({'completed_utc':now(),'files':{str(f.relative_to(a.output)):sha(f) for f in sorted(a.output.rglob('*')) if f.is_file()}})
        new_json(a.output/'manifest.json',status)
    print(json.dumps(status|{'files':len(status['files'])}),flush=True)
    return 0 if status['status']=='predictions_complete_pending_protected_scoring' else 2
if __name__=='__main__':raise SystemExit(main())
