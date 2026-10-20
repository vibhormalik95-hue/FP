"""Independent stdlib recomputation from saved evidence, without project imports or inference."""
import argparse
from collections import defaultdict, Counter
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import statistics

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def fingerprint(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def canonical(x):
    return (x['operation'], sorted(tuple(d[k] for k in ('operation','category','strength','floor','condition_category')) for d in x['directives']))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    failures=[]
    def check(ok,message):
        if not ok: failures.append(message)
    manifest=read(a.run/'manifest.json')
    check(manifest['status']=='practice_diagnostic_completed','run incomplete')
    for name,digest in manifest['files'].items():
        check(hashlib.sha256((a.run/name).read_bytes()).hexdigest()==digest,'manifest mismatch '+name)
    policy=read(a.run/'protocol-before-inference.json')
    for name,digest in {**policy['source_sha256'],**policy['input_sha256']}.items():
        check(hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,'run source/input changed '+name)
    csvpath=next(a.run.glob('COMP9500-Worked-Practice-100-*.csv'))
    refs=list(csv.DictReader(csvpath.open(encoding='utf-8-sig',newline='')))
    cases={c['id']:c for c in read(a.run/'cases-from-exposed-reference.json')}
    check(len(refs)==len(cases)==100,'reference denominator')
    for r in refs:
        c=cases[r['annotation_id']]
        check(c['text']==r['text'] and canonical(c['gold'])==canonical({'operation':r['operation'],'directives':json.loads(r['directives_json'])}), 'reference changed '+c['id'])
        check(r['label_author']=='AI-generated worked example' and r['practice_status']=='NON_HELD_OUT_PRACTICE_ONLY','reference provenance')
    parses=[read(x) for x in (a.run/'parse_cache').glob('*.json')]
    check(len(parses)==200,'parser denominator')
    parser_report={}
    for backend in ('rule_compound','ollama_compound'):
        selected=[r for r in parses if r['backend']==backend]
        check(len({r['id'] for r in selected})==100,'unique parser IDs '+backend)
        report={'total':len(selected),'correct':sum(not r['error'] and canonical(r['command'])==canonical(cases[r['id']]['gold']) for r in selected),'operational_errors':sum(bool(r['error']) for r in selected)}
        parser_report[backend]=report
        original=read(a.run/'parser-agreement-with-ai-reference.json')[backend]
        check(all(report[k]==original[k] for k in report),'parser recount '+backend)
    raw=[read(x) for x in (a.run/'raw_llm').glob('*.json')]
    check(len(raw)==100,'raw response denominator')
    check(len(list((a.run/'attempts').glob('*.json')))==100,'attempt denominator')
    textcases={c['text']:c for c in cases.values()}
    raw_agreement=0
    for r in raw:
        check(r['provenance']['digest']==policy['digest'],'model digest drift')
        check(r['payload']['options']==policy['options'],'options drift')
        check(r['payload']['messages'][0]['content']==policy['prompt']+'\nSCHEMA: '+json.dumps(policy['schema'],sort_keys=True),'prompt drift')
        check(r['request_started_at']>=policy['committed_utc'],'inference preceded protocol')
        try:
            case=textcases[json.loads(r['payload']['messages'][1]['content'])['request']]
            raw_agreement+=canonical(json.loads(r['response']['message']['content']))==canonical(case['gold'])
        except (ValueError,KeyError,TypeError):
            pass
    data=read(a.data)
    cat={i['item_id']:set(i['categories']) for i in data['items']}
    users={u['user_id']:u for u in data['users']}
    requests={r['request_id']:r for r in read(a.run/'assigned-requests.json')}
    for req in requests.values():
        u=users[req['user_id']]
        support=set().union(*(cat[i] for i in u['train']+u['request_history']))
        eligible=sorted((c for c in cases.values() if c['class']==req['class'] and
            {v for d in c['gold']['directives'] for v in (d['category'],d['condition_category']) if v is not None}<=support),key=lambda c:c['id'])
        index=int.from_bytes(hashlib.sha256(f"2026:{req['user_id']}:{req['class']}".encode()).digest()[:8],'big')%len(eligible)
        check(req['case_id']==eligible[index]['id'] and req['eligible_case_count']==len(eligible),'request assignment '+req['request_id'])
        check(canonical(req['gold'])==canonical(cases[req['case_id']]['gold']),'assigned reference '+req['request_id'])
    rows=read(a.run/'ranking-rows.json')
    check(len(rows)==12*len(requests),'ranking denominator')
    check(len({(r['seed'],r['request_id'],r['condition']) for r in rows})==len(rows),'duplicate rows')
    expected_pairs={(s,c) for s in (42,43,44) for c in ('A','rule','llm','recency')}
    pairs=defaultdict(set)
    for row in rows:pairs[row['request_id']].add((row['seed'],row['condition']))
    check(all(v==expected_pairs for v in pairs.values()),'missing seed/condition pairs')
    vectors={}
    for f in (a.run/'score_vectors').glob('*.json'):
        v=read(f)
        u=users[v['user_id']]
        check(v['history_sha256']==fingerprint(u['train']+u['request_history']),'scoring history')
        check(v['score_sha256']==fingerprint(v['scores']),'score vector digest')
        scoremap=dict(zip(v['item_ids'],v['scores']))
        ranked=sorted(v['item_ids'],key=lambda i:(-scoremap[i],i))
        vectors[(v['seed'],v['user_id'])]=(v,ranked)
    aggregates=defaultdict(list)
    for row in rows:
        req=requests[row['request_id']]
        v,baseline=vectors[(row['seed'],row['user_id'])]
        check(row['score_sha256']==v['score_sha256'],'row scores')
        check(row['baseline_sha256']==fingerprint(baseline),'baseline ranking')
        top=row['top_10']; base=baseline[:10]; gold=req['gold']; ds=gold['directives']
        check(len(top)==len(set(top)) and set(top)<=set(cat),'invalid top 10')
        exposure=lambda items,pred:sum(1/math.log2(k+2) for k,i in enumerate(items) if pred(i))/sum(1/math.log2(k+2) for k in range(10))
        bands=[]; basebands=[]; moves=[]; floors=[]; counts={}; basecounts={}
        for d in ds:
            target=d['category']; cond=d['condition_category']
            pred=lambda i:target in cat[i] and (cond is None or cond in cat[i])
            other=lambda i:target in cat[i] and cond not in cat[i]
            n=sum(pred(i) for i in top); bn=sum(pred(i) for i in base)
            on=sum(other(i) for i in top) if cond else 0; bon=sum(other(i) for i in base) if cond else 0
            key=target if not cond else target+'&'+cond
            counts[key]=n; basecounts[key]=bn
            if cond: counts[target+'&!'+cond]=on; basecounts[target+'&!'+cond]=bon
            def band(n,other_n):
                if cond:return n>=2 and other_n<=bon
                if d['floor']==1:return 1<=n<=2
                if d['operation']=='exclude':return n==0
                if d['operation']=='reduce':return n<=1
                if len(ds)>1:return n>=2
                return 2<=n<=4 if d['strength']=='slight' else n>=2
            bands.append(band(n,on));basebands.append(band(bn,bon))
            move=exposure(top,pred)-exposure(base,pred)
            if cond:move-=max(0,exposure(top,other)-exposure(base,other))
            elif d['operation']!='boost':move=-move
            if d['floor']==1 and n<1:move=0
            moves.append(move); floors.append(d['floor']==1 and n<1)
        movement=min(moves) if moves else 0
        band_ok=bool(ds) and all(bands) and len(top)==10
        target=users[row['user_id']]['test'][0]
        expected={'counts':counts,'baseline_counts':basecounts,'full':len(top)==10,'band_satisfied':band_ok,'baseline_already_satisfies':bool(ds) and all(basebands),'floor_violation':any(floors),'fill_rate':len(top)/10,'intended_movement':movement,'induced_success':float(band_ok and movement>1e-12),'hr1':float(bool(top) and top[0]==target),'ndcg_at_10':1/math.log2(top.index(target)+2) if target in top else 0.0}
        for k,val in expected.items():
            check(math.isclose(row[k],val,rel_tol=1e-12,abs_tol=1e-12) if type(val) is float else row[k]==val,'metric '+k+' '+row['request_id'])
        for metric in ('induced_success','intended_movement','hr1','ndcg_at_10','band_satisfied','baseline_already_satisfies'):
            aggregates[(row['user_id'],row['class'],row['condition'],metric)].append(float(row[metric]))
    summary=read(a.run/'descriptive-ranking-summary.json')
    userclasses={k:statistics.mean(v) for k,v in aggregates.items()}
    pooled=defaultdict(list)
    for (uid,label,condition,metric),val in userclasses.items():pooled[(uid,condition,metric)].append(val)
    metrics={}
    for condition in ('A','rule','llm','recency'):
        metrics[condition]={}
        for metric in ('induced_success','intended_movement','hr1','ndcg_at_10','band_satisfied','baseline_already_satisfies'):
            val=statistics.mean(statistics.mean(v) for (uid,c,m),v in pooled.items() if c==condition and m==metric)
            metrics[condition][metric]=val
            check(math.isclose(val,summary['descriptive'][condition]['pooled'][metric],abs_tol=1e-12),'pooled aggregate '+condition+metric)
    report={'reviewed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'passed' if not failures else 'failed',
        'review_method':'Fresh Python process; independent stdlib metric and aggregation implementation; no feedctrl imports, inference, tuning or human adjudication.',
        'limitations':'Same AI agent performed this computational audit; no claim of a second human or blinded reviewer. Bootstrap intervals and signed-rank calculations are retained from the existing evaluator, not independently reimplemented here.',
        'scope':'Exposed practice against AI references only; original formal E2 remains pending.',
        'manifest_files_checked':len(manifest['files']),'parser_recount':parser_report,'raw_response_files':len(raw),
        'ranking_rows_checked':len(rows),'score_vectors_checked':len(vectors),'requests':len(requests),'users':len({r['user_id'] for r in rows}),
        'class_counts':dict(Counter(c['class'] for c in cases.values())),'independent_pooled_metrics':metrics,
        'parser_error_messages':dict(Counter(r['error'] for r in parses if r['error'])),
        'posthoc_raw_response_diagnostic':{'raw_reference_agreement_before_application_validation':raw_agreement,
            'denominator':100,'scope':'Post hoc failure explanation only; does not replace the fixed validated-parser score.'},
        'failures':failures}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
    return bool(failures)

if __name__=='__main__':raise SystemExit(main())
