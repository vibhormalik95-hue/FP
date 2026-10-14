"""Software-only fixtures. No real bank, human attestations or Ollama calls."""
import base64
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys
from unittest.mock import patch
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts import formal_e2_inference as worker

def packet():
    return {'categories':[f'category_{i}' for i in range(31)],'questions':[{'id':'SYNTHETIC_FIXTURE_A','text':'SOFTWARE TEST ONLY A'},{'id':'SYNTHETIC_FIXTURE_B','text':'SOFTWARE TEST ONLY B'}]}
def control(tmp_path):
    trust={'study_id':'SYNTHETIC_TEST_ONLY','custodian_identity':'synthetic fixture, not a participant','runner_sid':'S-1-5-21-0-0-0-99999','public_key_b64':None,'opening_ledger':str(tmp_path/'SYNTHETIC_LEDGER'),'private_inventory_sha256':'6'*64,'protected_roots':[str(tmp_path/'SYNTHETIC_PRIVATE')]}
    release={'study_id':trust['study_id'],'release_id':'SYNTHETIC_ONLY','custodian_identity':trust['custodian_identity'],'runner_sid':trust['runner_sid'],'trust_sha256':'0'*64,'full_freeze_sha256':'1'*64,'protocol_review_sha256':'2'*64,'private_inventory_sha256':'6'*64,'gate_status':'verified_human_attestations_and_full_freeze','created_utc':datetime.now(timezone.utc).isoformat(),'case_count':100,'questions_sha256':'3'*64,'source_sha256':{n:'4'*64 for n in worker.SOURCE_NAMES},'protected_files':{n:{'path':str(tmp_path/(n+'.SYNTHETIC')),'sha256':'5'*64} for n in worker.PROTECTED},'opening_ledger':str(tmp_path/'SYNTHETIC_LEDGER'),'model_provenance':deepcopy(worker.MODEL),'model_options':deepcopy(worker.OPTIONS)}
    return trust,release
@pytest.mark.parametrize('field',['gold','class','author_reference','predictions'])
def test_question_label_fields_rejected(field):
    p=packet();p['questions'][0][field]='POISONED SOFTWARE FIXTURE'
    with pytest.raises(ValueError,match='Only opaque ID'):worker.validate_questions(p,2)
def test_top_level_reference_field_rejected():
    p=packet();p['reference_labels']=[]
    with pytest.raises(ValueError,match='must not contain'):worker.validate_questions(p,2)
def test_exact_question_identity_and_order_retained():
    p=packet();cats,rows=worker.validate_questions(p,2);assert rows==p['questions'] and cats==p['categories']
@pytest.mark.parametrize('part',['id','text'])
def test_duplicates_rejected(part):
    p=packet();p['questions'][1][part]=p['questions'][0][part]
    with pytest.raises(ValueError,match='duplicate'):worker.validate_questions(p,2)
def test_unenrolled_custodian_cannot_release():
    with pytest.raises(ValueError,match='enrolled public key'):worker.verify_signature(b'SYNTHETIC',b'',dict.fromkeys(worker.TRUST_KEYS))
def test_signature_binds_exact_release_bytes():
    key=Ed25519PrivateKey.generate() # ephemeral software fixture, never enrolled as a study key
    trust=dict.fromkeys(worker.TRUST_KEYS);trust.update({'public_key_b64':base64.b64encode(key.public_key().public_bytes_raw()).decode(),'runner_sid':'SYNTHETIC','custodian_identity':'SYNTHETIC'})
    raw=b'SOFTWARE TEST ONLY';sig=key.sign(raw);worker.verify_signature(raw,sig,trust)
    with pytest.raises(Exception):worker.verify_signature(raw+b'changed',sig,trust)
@pytest.mark.parametrize('change',[{'gate_status':'pending'},{'case_count':99},{'runner_sid':'WRONG_OS_ACCOUNT'},{'model_options':{'temperature':1}},{'model_provenance':{'model':'llama3:latest'}},{'gold':[]}])
def test_release_gate_drift_rejected(tmp_path,change):
    t,r=control(tmp_path);r.update(change)
    with pytest.raises(ValueError):worker.validate_release(r,t,'0'*64,t['runner_sid'])
def test_metadata_allowlist_accepts_synthetic_control_only(tmp_path):
    t,r=control(tmp_path);worker.validate_release(r,t,'0'*64,t['runner_sid'])
def test_readable_reference_stops_before_reading_bytes(tmp_path):
    p=tmp_path/'SYNTHETIC_NOT_A_REFERENCE';p.write_text('SOFTWARE FIXTURE')
    with pytest.raises(ValueError,match='References accessible'):worker.require_denied_files({'author_bank':{'path':str(p)}})
def test_missing_reference_does_not_prove_isolation(tmp_path):
    with pytest.raises(ValueError,match='Missing/unverifiable'):worker.require_denied_files({'author_bank':{'path':str(tmp_path/'nonexistent')}})
def test_os_read_denial_is_required(tmp_path):
    with patch.object(Path,'open',side_effect=PermissionError('SYNTHETIC denial')):
        assert worker.require_denied_files({'author_bank':{'path':str(tmp_path/'fixture')}})=={'author_bank':'read denied before opening questions'}
def test_prediction_failures_remain_and_no_reference_is_needed(tmp_path):
    with patch.object(worker.parser,'parse_control',side_effect=RuntimeError('SYNTHETIC parser failure')) as parse:
        records=worker.collect_predictions(packet()['questions'],packet()['categories'],tmp_path)
    assert len(records)==4 and all(r['error'] and r['command']=={'operation':'clarify','directives':[]} for r in records)
    assert parse.call_count==4 and all('gold' not in r and 'class' not in r for r in records)
def test_existing_output_record_cannot_be_replaced(tmp_path):
    p=tmp_path/'SYNTHETIC.json';worker.new_json(p,{'old':'SYNTHETIC'})
    with pytest.raises(FileExistsError):worker.new_json(p,{'new':'SYNTHETIC'})

def main_fixture(tmp_path):
    trust,release=control(tmp_path);trustfile=tmp_path/'SYNTHETIC_TRUST.json';trustfile.write_text(json.dumps(trust))
    questions=tmp_path/'SYNTHETIC_QUESTIONS.json';questions.write_text(json.dumps(packet()))
    release['trust_sha256']=worker.sha(trustfile);release['questions_sha256']=worker.sha(questions)
    releasefile=tmp_path/'SYNTHETIC_RELEASE.json';releasefile.write_text(json.dumps(release))
    sig=tmp_path/'SYNTHETIC.sig';sig.write_bytes(b'SOFTWARE_FIXTURE_NOT_AN_AUTHORIZATION')
    argv=['fixture','--release',str(releasefile),'--signature',str(sig),'--questions',str(questions),'--output',str(tmp_path/'SYNTHETIC_OUTPUT')]
    return trust,release,trustfile,questions,argv

def main_mocks(tmp_path):
    trust,release,trustfile,questions,argv=main_fixture(tmp_path)
    stack=ExitStack()
    for target,value in [('require_protected_deployment',trustfile),('verify_signature',None),('current_sid',trust['runner_sid']),('require_denied_files',{}),('require_denied_trees',None)]:
        stack.enter_context(patch.object(worker,target,return_value=value))
    stack.enter_context(patch.object(worker,'sha',side_effect=lambda p:release['source_sha256'][str(Path(p).relative_to(worker.ROOT)).replace('\\','/')] if Path(p).is_relative_to(worker.ROOT) else hashlib.sha256(Path(p).read_bytes()).hexdigest()))
    stack.enter_context(patch.object(worker.legacy,'ollama_provenance',return_value=dict(worker.MODEL)))
    stack.enter_context(patch.object(sys,'argv',argv))
    return stack,release,questions

def test_unconfigured_candidate_never_reads_questions(tmp_path):
    *_,questions,argv=main_fixture(tmp_path)
    with patch.object(sys,'argv',argv),patch.object(Path,'read_bytes',side_effect=AssertionError('must not read any input')):
        with pytest.raises(ValueError,match='Candidate only'):worker.main()

def test_existing_opening_blocks_before_question_read(tmp_path):
    stack,r,q=main_mocks(tmp_path)
    ledger=Path(r['opening_ledger']);ledger.mkdir();(ledger/(r['study_id']+'.json')).write_text('SYNTHETIC PRIOR OPENING')
    original=Path.read_bytes
    def guarded(p):
        assert p!=q,'question reopened before rejecting ledger'
        return original(p)
    with stack,patch.object(Path,'read_bytes',guarded):
        with pytest.raises(FileExistsError):worker.main()

def test_startup_model_failure_does_not_open_questions(tmp_path):
    stack,r,q=main_mocks(tmp_path);original=Path.read_bytes
    def guarded(p):
        assert p!=q,'question read on failed startup'
        return original(p)
    with stack,patch.object(Path,'read_bytes',guarded),patch.object(worker.legacy,'ollama_provenance',side_effect=RuntimeError('SYNTHETIC unavailable')):
        with pytest.raises(RuntimeError,match='SYNTHETIC unavailable'):worker.main()
    assert not Path(r['opening_ledger']).exists()

def test_single_byte_read_after_opening_and_failure_manifest(tmp_path):
    stack,r,q=main_mocks(tmp_path);original=Path.read_bytes;reads=[]
    def guarded(p):
        if p==q:
            assert (Path(r['opening_ledger'])/(r['study_id']+'.json')).exists()
            reads.append(p);assert len(reads)==1
        return original(p)
    with stack,patch.object(Path,'read_bytes',guarded),patch.object(worker,'validate_questions',return_value=(packet()['categories'],packet()['questions'])),patch.object(worker,'collect_predictions',side_effect=RuntimeError('SYNTHETIC_STOP')):
        assert worker.main()==2
    assert len(reads)==1
    m=json.loads((tmp_path/'SYNTHETIC_OUTPUT/manifest.json').read_text());assert m['status']=='failed_or_incomplete' and 'SYNTHETIC_STOP' in m['error']

def test_actual_existing_parser_payload_options(tmp_path):
    raw={'done':True,'message':{'content':json.dumps({'operation':'clarify','directives':[]})}}
    with patch.object(worker.legacy,'ollama_provenance',return_value=dict(worker.MODEL)),patch.object(worker.legacy,'_request',return_value=raw) as request:
        worker.parser._llm_compound('SOFTWARE TEST ONLY',packet()['categories'],model='llama3.1:8b',timeout=600,cache_dir=tmp_path/'SYNTHETIC_CACHE',seed=42,num_thread=6)
    assert request.call_args.args[2]['options']==worker.OPTIONS

def test_protected_alias_paths_rejected(tmp_path):
    t,r=control(tmp_path);shared=next(iter(r['protected_files'].values()))
    r['protected_files']={n:shared for n in worker.PROTECTED}
    with pytest.raises(ValueError,match='distinct'):worker.validate_release(r,t,'0'*64,t['runner_sid'])
