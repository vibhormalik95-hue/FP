"""Generate a bounded cache of grounded explanations; exit nonzero on partial failure."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from feedctrl.explanations import generate_explanation,EXPLANATION_PROMPT
from feedctrl.controls import ParserOperationalError
from feedctrl.model import load_model
from scripts.output_safety import project_path, require_new_output


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--data',default='data/processed.json')
    p.add_argument('--model-dir',default='results/models/seed_42')
    p.add_argument('--output',default='results/reproduction-explanations/explanations.json')
    p.add_argument('--cache-dir',help='New cache directory; default is alongside OUTPUT in explanation_cache')
    p.add_argument('--count',type=int,default=10)
    p.add_argument('--backend',choices=['template','ollama'],default='ollama')
    p.add_argument('--ollama-model',default='llama3.1:8b')
    p.add_argument('--base-url','--ollama-base-url',dest='base_url',default='http://127.0.0.1:11434')
    p.add_argument('--timeout',type=float,default=180)
    args=p.parse_args(argv)
    if args.count < 1:
        p.error('--count must be positive')
    if not 0 < args.timeout <= 600:
        p.error('--timeout must be in (0, 600] seconds')
    try:
        output_path=require_new_output(args.output, ROOT, directory=False)
        cache=require_new_output(args.cache_dir or output_path.parent/'explanation_cache', ROOT, directory=True)
    except ValueError as exc:
        p.error(str(exc))
    output_path.parent.mkdir(parents=True,exist_ok=True)
    data=json.loads(project_path(args.data, ROOT).read_text(encoding='utf-8'))
    predictor=load_model(project_path(args.model_dir, ROOT))
    categories={i['item_id']:i['categories'] for i in data['items']}
    ids=sorted(categories)
    user=data['users'][0]
    history=user['train']+user['request_history']
    scores=predictor.score(history,ids)
    order=sorted(zip(ids,scores),key=lambda row:(-row[1],row[0]))
    output={'user_id':user['user_id'],'backend':args.backend,'scope':'First user, top baseline items; limited cache coverage',
            'prompt_sha256':hashlib.sha256(EXPLANATION_PROMPT.encode()).hexdigest(),'explanations':[],'errors':[]}
    for item_id,_ in order[:args.count]:
        try:
            record=generate_explanation(item_id,categories[item_id],history,categories,
                backend=args.backend,model=args.ollama_model,base_url=args.base_url,timeout=args.timeout,cache_dir=cache)
            output['explanations'].append(record)
        except ParserOperationalError as exc:
            output['errors'].append({'item_id':item_id,'error':str(exc)})
        output_path.write_text(json.dumps(output,indent=2),encoding='utf-8')
        print('explanation',item_id,len(output['explanations']),flush=True)
    output['status']='complete' if not output['errors'] else 'partial'
    output_path.write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps({'status':output['status'],'generated':len(output['explanations']),'errors':output['errors']},indent=2))
    return 0 if output['status']=='complete' else 2


if __name__=='__main__':
    raise SystemExit(main())
