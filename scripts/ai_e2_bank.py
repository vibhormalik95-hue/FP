"""Custodian-only AI-reference bank preparation. No parser predictions or inference."""
from __future__ import annotations
import argparse,csv,difflib,hashlib,json,random,re
from pathlib import Path
from datetime import datetime,timezone

STUDY='AIREF-E2-20261014-v1'
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)
def normal(text):
    mapping={}
    def category(m):
        token=m[0].casefold()
        if token not in mapping:mapping[token]=f'C{len(mapping)}'
        return mapping[token]
    text=re.sub(r'\bcategory_\d+\b',category,text.casefold())
    return ' '.join(re.sub(r'[^\w]+',' ',text).split())
def similarity(a,b):
    a,b=normal(a),normal(b);aa=a.split();bb=b.split()
    ga=set(zip(aa,aa[1:]));gb=set(zip(bb,bb[1:]));union=ga|gb
    return {'sequence':difflib.SequenceMatcher(None,a,b,autojunk=False).ratio(),'bigram_jaccard':len(ga&gb)/len(union) if union else float(a==b)}
def close(s):return s['sequence']>=0.82 or s['bigram_jaccard']>=0.55
def plan(root):
    root=Path(root)
    if not (root/'protocol/protocol-freeze.json').exists():raise ValueError('Protocol freeze required before plan/case authoring')
    rng=random.Random(20261014);cats=[f'category_{i}' for i in range(31)];rng.shuffle(cats)
    grades=['slight_boost']*9+['strong_reduction']*8+['exclusion']*8;rng.shuffle(grades)
    slots=[]
    for n in range(100):
        label=('compound','graded','floor','conditional')[n//25];target=cats[n%31]
        second=rng.choice([c for c in cats if c!=target]) if label in ('compound','conditional') else None
        slots.append({'slot':n+1,'id':'q_'+hashlib.sha256(f'{STUDY}:slot:{n+1}'.encode()).hexdigest()[:12],
            'class':label,'target':target,'secondary':second,'subtype':grades[n-25] if label=='graded' else label})
    save(root/'custody/intent-plan.json',{'study_id':STUDY,'seed':20261014,'created_utc':now(),'slots':slots})
    save(root/'authoring/round-1-intent-plan.json',{'study_id':STUDY,'round':1,'slots':slots})
    print(json.dumps({'slots':len(slots),'targets':len({s['target'] for s in slots}),'plan_sha256':sha(root/'custody/intent-plan.json')}))
def screen(root,candidates,practice,dev,round_number):
    if not 1<=round_number<=5:raise ValueError('Round must be 1 through 5')
    root=Path(root);frozen=json.loads((root/'protocol/protocol-freeze.json').read_text())
    for source in (practice,dev):
        if frozen['input_sha256'].get(str(Path(source).resolve()))!=sha(source):raise ValueError('Frozen exclusion corpus mismatch')
    plan_data=json.loads((root/'custody/intent-plan.json').read_text())
    slots=plan_data['slots'];pool=json.loads(Path(candidates).read_text())
    if not isinstance(pool,list):raise ValueError('Candidate list required')
    lookup={r['id']:r for r in pool}
    if len(lookup)!=len(pool) or any(set(r)!={'id','candidates'} or len(r['candidates'])!=3 for r in pool):raise ValueError('Exactly three candidate texts per unique assigned ID')
    previous=root/'custody'/f'selection-round-{round_number-1}.json'
    selected=json.loads(previous.read_text())['selected'] if round_number>1 else []
    prior_ids={r['id'] for r in selected};unfilled=[s for s in slots if s['id'] not in prior_ids]
    if set(lookup)!={s['id'] for s in unfilled}:raise ValueError('Pool must match all and only unfilled slots')
    old=[r['text'] for r in csv.DictReader(Path(practice).open(encoding='utf-8-sig',newline=''))]
    development=[json.loads(line)['text'] for line in Path(dev).read_text().splitlines() if line.strip()]
    if len(old)!=100 or len(development)!=48:raise ValueError('Frozen exclusion counts must be 100 and 48')
    old += development
    audit=[]
    for s in unfilled:
        for ordinal,text in enumerate(lookup[s['id']]['candidates'],1):
            reasons=[]
            if not isinstance(text,str):reasons.append('not_text');text=str(text)
            if not 12<=len(text.split())<=45:reasons.append('word_count')
            refs=set(re.findall(r'\bcategory_\d+\b',text,flags=re.I));expected={s['target']}|({s['secondary']} if s['secondary'] else set())
            if refs!=expected:reasons.append('category_set')
            if any(c not in {f'category_{i}' for i in range(31)} for c in refs):reasons.append('unknown_category')
            if any(x in text for x in ('{','}','[',']')):reasons.append('schema_or_bracket_hint')
            if any(normal(text)==normal(o) for o in old):reasons.append('old_normalized_duplicate')
            scores=[similarity(text,o) for o in old]
            if any(close(v) for v in scores):reasons.append('old_close_paraphrase')
            if any(normal(text)==normal(o['text']) for o in selected if o['id']!=s['id']):reasons.append('fresh_normalized_duplicate')
            audit.append({'id':s['id'],'round':round_number,'ordinal':ordinal,'text':text,'reasons':sorted(set(reasons)),
                'max_old_sequence':max(v['sequence'] for v in scores),'max_old_bigram':max(v['bigram_jaccard'] for v in scores)})
            if not reasons and not any(r['id']==s['id'] for r in selected):
                selected.append({'id':s['id'],'text':text,'slot':s['slot'],'class':s['class'],'round':round_number,'ordinal':ordinal})
    ids={r['id'] for r in selected};missing=[s for s in slots if s['id'] not in ids]
    save(root/'custody'/f'screening-round-{round_number}.json',{'created_utc':now(),'candidate_file_sha256':sha(candidates),'practice_sha256':sha(practice),'dev_sha256':sha(dev),'audit':audit,'selected_count':len(selected),'missing_count':len(missing)})
    save(root/'custody'/f'selection-round-{round_number}.json',{'selected':sorted(selected,key=lambda r:r['slot']),'missing_ids':[s['id'] for s in missing]})
    if missing:
        if round_number>=5:raise ValueError('Generation limit reached; no threshold relaxation permitted')
        save(root/'authoring'/f'round-{round_number+1}-intent-plan.json',{'study_id':STUDY,'round':round_number+1,'slots':missing})
    else:
        questions=[{'id':r['id'],'text':r['text']} for r in sorted(selected,key=lambda r:r['slot'])]
        pairs=[]
        for i,a in enumerate(questions):
            for b in questions[i+1:]:
                sim=similarity(a['text'],b['text'])
                if close(sim):pairs.append({'a':a['id'],'b':b['id'],**sim})
        save(root/'custody/fresh-near-paraphrase-flags.json',{'flagged_pairs':pairs,'policy':'reported, not outcome-based exclusion'})
        save(root/'custody/questions-master.json',{'categories':[f'category_{i}' for i in range(31)],'questions':questions})
        for role,seed in [('tanishq',20261015),('khushi',20261016),('inference',20261017)]:
            copy=list(questions);random.Random(seed).shuffle(copy)
            path=root/f'annotations/{role}/questions.json' if role!='inference' else root/'inference/questions.json'
            save(path,{'categories':[f'category_{i}' for i in range(31)],'questions':copy})
        save(root/'custody/bank-lock.json',{'locked_utc':now(),'n':100,'category_coverage':sorted({c for q in questions for c in re.findall(r'\bcategory_\d+\b',q['text'])}),
            'question_master_sha256':sha(root/'custody/questions-master.json'),'intent_plan_sha256':sha(root/'custody/intent-plan.json'),'selected_round':round_number,
            'sheets':{role:sha(root/f'annotations/{role}/questions.json') for role in ('tanishq','khushi')},'inference_questions_sha256':sha(root/'inference/questions.json')})
    print(json.dumps({'selected':len(selected),'missing':len(missing),'round':round_number,'bank_locked':not missing}))
def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['plan','screen']);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--candidates',type=Path);p.add_argument('--practice',type=Path);p.add_argument('--dev',type=Path);p.add_argument('--round',type=int,default=1)
    a=p.parse_args()
    if a.stage=='plan':plan(a.root)
    else:screen(a.root,a.candidates,a.practice,a.dev,a.round)
if __name__=='__main__':main()
