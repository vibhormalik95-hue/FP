"""Grounded explanations from verified facts, optionally selected by an actual LLM.

The LLM selects a subset of fixed, verifiable statements. It cannot add free-form
causal claims. This is constrained fact selection, not explanation-faithfulness proof.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .controls import _request, ollama_provenance, ParserOperationalError

EXPLANATION_PROMPT = '''Select one to three useful verified statements to explain this recommendation card.
Return JSON matching the schema. Select only statements present in allowed_statements,
without changing any wording. Do not infer category topics, motives, causality, or future
behavior. A model score is an association used for ranking, not a causal explanation.
Prefer category membership and a matching historical observation when available.
'''


def verified_facts(item_id: int, categories: list[str], history: list[int], item_categories: dict[int,list[str]]) -> list[str]:
    facts=[f'This card represents item {item_id}.']
    for cat in sorted(set(categories)):
        facts.append(f'Item {item_id} is tagged {cat}; the category name is not available.')
        count=sum(cat in item_categories.get(i,[]) for i in history)
        if count:
            facts.append(f'{count} interactions in the visible history contain {cat}.')
    facts.append('The displayed order comes from model scores and any explicit controls currently applied.')
    return facts


def generate_explanation(item_id: int, categories: list[str], history: list[int], item_categories: dict[int,list[str]],
                         backend: str='template', base_url: str='http://127.0.0.1:11434',
                         model: str='llama3.1:8b', cache_dir: str | Path='results/explanation_cache',
                         timeout: float=180) -> dict:
    facts=verified_facts(item_id,categories,history,item_categories)
    signal_key=hashlib.sha256(json.dumps({'item_id':item_id,'facts':facts},sort_keys=True).encode()).hexdigest()
    if backend=='template':
        # Explicit fallback/comparator, not an LLM result.
        return {'item_id':item_id,'text':' '.join(facts[:min(3,len(facts))]),
                'statements':facts[:min(3,len(facts))],'allowed_statements':facts,
                'source':'verified_template','signal_key':signal_key}
    if backend!='ollama':
        raise ValueError('explanation backend must be template or ollama')
    provenance=ollama_provenance(base_url,model)
    schema={'type':'object','properties':{'item_id':{'type':'integer','enum':[item_id]},
             'statements':{'type':'array','items':{'type':'string','enum':facts},'minItems':1,'maxItems':3}},
             'required':['item_id','statements'],'additionalProperties':False}
    payload={'model':model,'messages':[{'role':'system','content':EXPLANATION_PROMPT},
             {'role':'user','content':json.dumps({'item_id':item_id,'allowed_statements':facts})}],
             'format':schema,'stream':False,'keep_alive':'15m',
             'options':{'temperature':0,'seed':42,'num_ctx':4096,'num_predict':256,'num_thread':4}}
    key=hashlib.sha256(json.dumps({'provenance':provenance,'payload':payload},sort_keys=True).encode()).hexdigest()
    target=Path(cache_dir)/f'{key}.json'
    if target.exists():
        cached=json.loads(target.read_text(encoding='utf-8'))
        if cached.get('key') != key:
            raise ParserOperationalError('Invalid explanation cache key')
        raw=cached['response']
    else:
        raw=_request(base_url,'/api/chat',payload,timeout)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({'key':key,'provenance':provenance,'payload':payload,'response':raw},indent=2),encoding='utf-8')
    try:
        obj=json.loads(raw['message']['content'])
    except (KeyError,TypeError,json.JSONDecodeError) as exc:
        raise ParserOperationalError('Invalid explanation JSON') from exc
    if (raw.get('done') is not True or raw.get('done_reason')=='length' or not isinstance(obj,dict)
        or set(obj)!={'item_id','statements'} or type(obj['item_id']) is not int or obj['item_id']!=item_id
        or not isinstance(obj['statements'],list) or not 1<=len(obj['statements'])<=3
        or any(not isinstance(s,str) or s not in facts for s in obj['statements'])):
        raise ParserOperationalError('Explanation failed grounding/schema validation')
    return {'item_id':item_id,'text':' '.join(dict.fromkeys(obj['statements'])),
            'statements':list(dict.fromkeys(obj['statements'])),'allowed_statements':facts,
            'source':'ollama_constrained_fact_selection','provenance':provenance,
            'cache_key':key,'signal_key':signal_key}


def cached_explanation(item_id: int, categories: list[str], history: list[int], item_categories: dict[int,list[str]],
                       index_path: str | Path='results/explanations.json') -> dict:
    fallback=generate_explanation(item_id,categories,history,item_categories)
    path=Path(index_path)
    if path.exists():
        index=json.loads(path.read_text(encoding='utf-8'))
        for record in index.get('explanations',[]):
            if record.get('signal_key')==fallback['signal_key'] and record.get('source')=='ollama_constrained_fact_selection':
                statements=record.get('statements')
                if (type(record.get('item_id')) is int and record['item_id']==item_id
                    and isinstance(statements,list) and 1<=len(statements)<=3
                    and all(isinstance(statement,str) and statement in fallback['allowed_statements'] for statement in statements)
                    and isinstance(record.get('provenance'),dict) and record['provenance'].get('digest')):
                    valid=list(dict.fromkeys(statements))
                    return {**record,'text':' '.join(valid),'statements':valid}
    return fallback
