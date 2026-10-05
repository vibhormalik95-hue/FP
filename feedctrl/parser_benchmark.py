"""Run the preauthored synthetic control-language benchmark without silent fallback."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import time
from .controls import (parse_control, ollama_provenance, ParserOperationalError,
                       CONTROL_PROMPT, PROFILE_PROMPT, PROMPT_VERSION)


def _wilson(successes: int,total: int) -> list[float] | None:
    if not total:
        return None
    z=1.959963984540054
    p=successes/total
    den=1+z*z/total
    center=(p+z*z/(2*total))/den
    radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [max(0,center-radius),min(1,center+radius)]


def run_parser_benchmark(data_path: str | Path, output_dir: str | Path, backend: str='rule', **kwargs) -> dict:
    data_path,output_dir=Path(data_path),Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    raw=data_path.read_bytes()
    cases=[json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    if not cases or len({c['case_id'] for c in cases}) != len(cases) or len({c['text'] for c in cases}) != len(cases):
        raise ValueError('benchmark requires nonempty unique IDs and texts')
    summary={'backend':backend,'status':'running','cases':len(cases),'data_sha256':hashlib.sha256(raw).hexdigest(),
             'prompt_version':PROMPT_VERSION,'prompt_sha256':hashlib.sha256(CONTROL_PROMPT.encode()).hexdigest(),
             'benchmark_type':'synthetic, single-author gold labels; not human user research',
             'created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    if backend=='ollama':
        try:
            summary['model']=ollama_provenance(kwargs.get('base_url','http://127.0.0.1:11434'),kwargs.get('model','llama3.1:8b'))
        except ParserOperationalError as exc:
            summary.update(status='blocked',blocker=str(exc),completed_cases=0)
            (output_dir/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
            return summary
    rows=[]
    start=time.monotonic()
    with (output_dir/'predictions.jsonl').open('w',encoding='utf-8') as out:
        for case in cases:
            row={**case,'prediction':None,'correct':False,'operation_correct':False,'error':None}
            case_start=time.monotonic()
            try:
                row['prediction']=parse_control(case['text'],case['categories'],backend,**kwargs)
                prediction=row['prediction']
                row['operation_correct']=prediction['operation']==case['expected']['operation']
                row['correct']=all(prediction[k]==case['expected'][k] for k in ('operation','category','strength'))
            except ParserOperationalError as exc:
                row['error']=str(exc)
            row['elapsed_seconds']=time.monotonic()-case_start
            rows.append(row)
            out.write(json.dumps(row)+'\n');out.flush()
            print(f'parser {backend}: {len(rows)}/{len(cases)} {case["case_id"]} correct={row["correct"]}',flush=True)
    correct=sum(r['correct'] for r in rows)
    operations=['boost','mute','reset','clarify']
    f1s=[]
    per_operation={}
    for op in operations:
        tp=sum(r['prediction'] is not None and r['prediction']['operation']==op and r['expected']['operation']==op for r in rows)
        fp=sum(r['prediction'] is not None and r['prediction']['operation']==op and r['expected']['operation']!=op for r in rows)
        fn=sum((r['prediction'] is None or r['prediction']['operation']!=op) and r['expected']['operation']==op for r in rows)
        f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0
        f1s.append(f1)
        per_operation[op]={'tp':tp,'fp':fp,'fn':fn,'f1':f1}
    per_group={}
    for group in sorted({r['group'] for r in rows}):
        subset=[r for r in rows if r['group']==group]
        per_group[group]={'cases':len(subset),'correct':sum(r['correct'] for r in subset),
                          'exact_accuracy':sum(r['correct'] for r in subset)/len(subset)}
    summary.update(status='complete',completed_cases=len(rows),correct=correct,exact_accuracy=correct/len(rows),
        operation_accuracy=sum(r['operation_correct'] for r in rows)/len(rows),
        exact_accuracy_wilson_95=_wilson(correct,len(rows)),operation_macro_f1=sum(f1s)/len(f1s),
        operational_errors=sum(r['error'] is not None for r in rows),per_operation=per_operation,
        per_group=per_group,elapsed_seconds=time.monotonic()-start)
    (output_dir/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary
