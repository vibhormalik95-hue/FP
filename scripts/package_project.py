"""Package portable source, recorded evidence and deliverables, excluding runtimes."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--status',choices=['in_progress','verified_release'],default='in_progress')
    p.add_argument('--gate',default='results/verification/release-summary.json',
                   help='Release evidence JSON, relative to project root unless absolute')
    args=p.parse_args()
    if args.status=='verified_release':
        gate=ROOT/args.gate
        if not gate.is_file() or json.loads(gate.read_text(encoding='utf-8')).get('technical_status')!='passed':
            p.error('verified_release requires a passed release-summary.json at --gate')
        if (ROOT/'results/experiment2').is_dir() and json.loads(gate.read_text(encoding='utf-8')).get('scientific_completion')!='complete':
            p.error('Experiment 2 is incomplete; use in_progress for an honest review package')
        for name in ['COMP9500-Research-Paper.pdf','COMP9500-Research-Presentation.pptx','COMP9500-135-Hour-Plan.docx']:
            if not (ROOT/'deliverables'/name).is_file():
                p.error('Missing final deliverable: '+name)
    output=Path(args.output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    blocked={'.venv','node_modules','__pycache__','.pytest_cache','.git','.codex-finalizer','.build','rendered','preview','previews','raw'}
    ignored_suffix={'.aux','.bbl','.blg','.log','.out','.toc','.pyc','.zip','.fdb_latexmk','.fls'}
    files=[]
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        relative=path.relative_to(ROOT)
        if any(part in blocked or part.startswith('.chart-data-') for part in relative.parts) or path.suffix in ignored_suffix: continue
        if '.egg-info' in str(relative) or path.name in ('package-manifest.json','processed-replay.json'): continue
        if relative.parts[0]=='slides' and (path.suffix=='.png' or any(part in {'build','output'} or part.startswith('build-') for part in relative.parts)): continue
        files.append((path,relative))
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'status':args.status,
        'excluded':'dependency runtimes, downloaded model weights, raw KuaiRec archive, temporary render/chart/LaTeX files',
        'files':[]}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path,relative in files:
            content=path.read_bytes()
            name=str(relative).replace('\\','/')
            manifest['files'].append({'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
            z.writestr('cmp9500-recommender/'+name,content)
        manifest_text=json.dumps(manifest,indent=2)
        z.writestr('cmp9500-recommender/package-manifest.json',manifest_text)
    (ROOT/'package-manifest.json').write_text(manifest_text,encoding='utf-8')
    with zipfile.ZipFile(output) as z:
        bad=z.testzip()
        if bad: raise RuntimeError(f'Archive CRC check failed: {bad}')
    print(json.dumps({'output':str(output),'files':len(files)+1,'bytes':output.stat().st_size,
                      'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'status':args.status}))

if __name__=='__main__': main()
