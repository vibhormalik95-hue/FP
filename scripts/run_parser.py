"""Execute the frozen parser benchmark from the project root."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from feedctrl.parser_benchmark import run_parser_benchmark
from scripts.output_safety import project_path, require_new_output

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',default='data/parser_test.jsonl')
    p.add_argument('--output',default='results/reproduction-parser')
    p.add_argument('--backend',choices=['rule','ollama'],default='rule')
    p.add_argument('--model',default='llama3.1:8b')
    p.add_argument('--base-url',default='http://127.0.0.1:11434')
    p.add_argument('--cache-dir',help='New cache directory; default is OUTPUT/raw_llm_cache')
    p.add_argument('--timeout',type=float,default=180)
    p.add_argument('--num-thread',type=int,default=4)
    args=p.parse_args()
    try:
        output = require_new_output(args.output, ROOT, directory=True)
        cache = require_new_output(args.cache_dir or output/'raw_llm_cache', ROOT, directory=True)
    except ValueError as exc:
        p.error(str(exc))
    summary=run_parser_benchmark(project_path(args.data, ROOT),output,args.backend,model=args.model,base_url=args.base_url,
        cache_dir=cache,timeout=args.timeout,num_thread=args.num_thread)
    print(json.dumps(summary,indent=2))
    sys.exit(0 if summary['status']=='complete' else 2)
