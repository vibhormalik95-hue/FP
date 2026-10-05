"""Check recorded evidence receipts and execute pytest; not a fresh scientific/browser/LLM rerun."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='results/verification')
    parser.add_argument('--browser-evidence',default='results/verification/browser-acceptance.json')
    parser.add_argument('--llm-evidence',default='results/verification/llm-api.json')
    args=parser.parse_args()
    OUT=ROOT/args.output
    OUT.mkdir(parents=True,exist_ok=True)
    evidence={'checked_utc':datetime.now(timezone.utc).isoformat(),'checks':[],
              'execution_scope':{'executed_now':['pytest'],
                                 'recorded_evidence_only':['scientific results','browser acceptance','LLM API checks','fixture workflow'],
                                 'not_executed':['Windows acceptance','Google Colab acceptance','fresh training or inference']}}
    def record(name, ok, details):
        evidence['checks'].append({'name':name,'passed':bool(ok),'details':details})
    def read(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))
    try:
        data=read('data/processed.json')
        metadata=data['metadata']
        record('full_cohort',len(data['users'])==metadata['eligible_users']==865,
               {'users':len(data['users']),'items':len(data['items'])})
        data_hash=hashlib.sha256((ROOT/'data/processed.json').read_bytes()).hexdigest()
        record('data_fingerprint',data_hash==(ROOT/'data/processed.sha256').read_text(encoding='utf-8').split()[0],data_hash)
        for backend in ['rule','llm']:
            aggregate=read(f'results/{backend}/combined-summary.json')
            record(backend+'_cohort',aggregate['user_count']==865 and aggregate['seed_count']==3,
                   {'users':aggregate['user_count'],'seeds':aggregate['seed_count']})
            record(backend+'_explanation_invariance',aggregate['all_b_rank_invariant'],
                   'A and B ranking hashes match on every request')
            for seed in [42,43,44]:
                result=read(f'results/{backend}/seed_{seed}/summary.json')
                expected_status='rule_diagnostic' if backend=='rule' else 'executed_llm'
                record(f'{backend}_{seed}_execution',result['request_count']==1730 and result['evidence_status']==expected_status,
                       {k:result.get(k) for k in ['request_count','evidence_status','parse_operational_errors','unique_parse_count']})
        parser=read('results/parser_ollama_test/summary.json')
        record('actual_llm_parser_benchmark',parser['status']=='complete' and parser['completed_cases']==100,
               {k:parser.get(k) for k in ['correct','exact_accuracy','exact_accuracy_wilson_95','operational_errors','model']})
        stages=read('results/llm-stage-status.json')
        record('llm_workflow_stages',len(stages)==4 and all(stage['exit_code']==0 for stage in stages),stages)
        for filename in [args.browser_evidence,args.llm_evidence]:
            result=read(filename)
            receipt=ROOT/filename
            record(receipt.name,result['status']=='passed',{'status':result['status'],'checks':len(result.get('checks',[])),
                   'source':str(receipt.relative_to(ROOT)) if receipt.is_relative_to(ROOT) else str(receipt),
                   'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),'verification_mode':'recorded receipt; not executed by this script'})
        explanations=read('results/explanations.json')
        record('actual_explanation_sample',explanations['status']=='complete' and explanations['backend']=='ollama' and len(explanations['explanations'])==10,
               {'generated':len(explanations['explanations']),'scope':explanations['scope']})
        revision_path=ROOT/'results/audit_revision/analysis-v1.json'
        if revision_path.is_file():
            revision=read('results/audit_revision/analysis-v1.json')
            ni=revision['backends']['llm']['hr1_noninferiority_sensitivity']
            coherent=all(
                r['absolute_10_percentage_points']['statistical_criterion_passed']
                == (r['simultaneous_lower'] > -r['absolute_10_percentage_points']['margin_absolute'])
                and r['relative_10_percent_of_observed_reference']['statistical_criterion_passed']
                == (r['simultaneous_lower'] > -r['relative_10_percent_of_observed_reference']['margin_absolute'])
                and (not r['absolute_10_percentage_points']['margin_exceeds_baseline']
                     or not r['absolute_10_percentage_points']['informative_statistical_support'])
                for r in ni)
            record('revised_noninferiority_interpretation',len(ni)==3 and coherent,
                   {'source':'results/audit_revision/analysis-v1.json',
                    'scope':'Internal interpretation consistency; independent raw-row recomputation reported separately'})
            frozen=read('results/audit_revision/frozen-input-manifest.json')
            changed=[]
            for name,expected in frozen['files'].items():
                relative=Path(name).relative_to('cmp9500-recommender')
                actual=ROOT/relative
                if not actual.is_file() or hashlib.sha256(actual.read_bytes()).hexdigest()!=expected:
                    changed.append(str(relative))
            record('frozen_evidence_preservation',not changed,
                   {'files_checked':len(frozen['files']),'changed':changed})
            revision_smoke=read('results/audit_revision/verification/isolated-cli-smoke/pipeline_manifest.json')
            record('revised_isolated_fixture_workflow',revision_smoke['status']=='complete',
                   {'status':revision_smoke['status'],'stages':len(revision_smoke['steps']),
                    'mode':'recorded receipt from revised CLI execution'})
        junit=OUT/'pytest.xml'
        proc=subprocess.run([sys.executable,'-m','pytest','-q','--junitxml',str(junit)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (OUT/'pytest.txt').write_text(proc.stdout+proc.stderr,encoding='utf-8')
        totals={'tests':0,'failures':0,'errors':0,'skipped':0}
        if junit.exists():
            for suite in ET.parse(junit).getroot().iter('testsuite'):
                for key in totals: totals[key]+=int(suite.get(key,0))
        record('final_python_test_suite',proc.returncode==0,totals)
        smoke=read('results/smoke/final-run/pipeline_manifest.json')
        record('end_to_end_fixture_workflow',smoke['status']=='complete',{'status':smoke['status'],'stages':len(smoke['steps'])})
    except Exception as exc:
        record('verification_exception',False,f'{type(exc).__name__}: {exc}')
    evidence['technical_status']='passed' if evidence['checks'] and all(c['passed'] for c in evidence['checks']) else 'failed'
    evidence['academic_status']='Supervisor review, official BCIT template, student review and final presentation remain external requirements'
    evidence['interpretation']='Passing engineering checks does not establish the research hypotheses or useful recommendation quality'
    experiment2=ROOT/'results/experiment2/summary.json'
    if experiment2.is_file():
        e2=json.loads(experiment2.read_text(encoding='utf-8'))
        evidence['experiment2_status']=e2.get('status','unknown')
        evidence['scientific_completion']='complete' if e2.get('status')=='complete' else 'incomplete'
        evidence['interpretation']+='; the Experiment 2 completion status is separate from this engineering gate'
    path=OUT/'release-summary.json'
    path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence,indent=2))
    return 0 if evidence['technical_status']=='passed' else 1

if __name__=='__main__': raise SystemExit(main())
