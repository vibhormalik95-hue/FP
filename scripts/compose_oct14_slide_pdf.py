"""Revise the existing BCIT PDF without installing missing Beamer dependencies.

Keep unaffected source pages as vector PDF. New text uses installed Windows Arial.
The current editable Beamer source is retained separately; this is a PDF composition.
"""
from io import BytesIO
from pathlib import Path
import argparse
import copy
import json
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader, PdfWriter

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,required=True)
p.add_argument('--inserts',type=Path,required=True)
a=p.parse_args()
pdfmetrics.registerFont(TTFont('ArialLocal','C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialLocalBold','C:/Windows/Fonts/arialbd.ttf'))
original=PdfReader(ROOT/'deliverables/COMP9500-BCIT-Presentation.pdf')
W,H=map(float,(original.pages[0].mediabox.width,original.pages[0].mediabox.height))
logo=ROOT/'presentation-bcit/bcit_logo.png'
c=canvas.Canvas(str(a.inserts),pagesize=(W,H))
c.setTitle('BCIT slide updates verified October 14 2026')
c.setAuthor('Vibhor Malik with disclosed AI assistance')
def lines(text,x,y,width,size=10,leading=15,bold=False,color='#192F34'):
    c.setFillColor(HexColor(color));c.setFont('ArialLocalBold' if bold else 'ArialLocal',size)
    for paragraph in text.split('\n'):
        for line in simpleSplit(paragraph,'ArialLocalBold' if bold else 'ArialLocal',size,width) or ['']:
            c.drawString(x,y,line);y-=leading
    return y
def frame(title,body,note):
    c.setFillColor(HexColor('#003C71'));c.rect(0,H-30,W,30,fill=1,stroke=0)
    lines(title,12,H-20,W-24,size=12,leading=14,bold=True,color='#FFFFFF')
    bottom=lines(body,27,H-56,W-54,size=10,leading=14)
    assert bottom>51,(title,bottom)
    lines(note,27,49,W-54,size=6.4,leading=8,color='#6E6E6E')
    c.drawImage(str(logo),6,8,width=14,height=14,preserveAspectRatio=True,mask='auto')
    lines('COMP 9500: Natural-language controls',30,12,W-80,size=5.5)
    c.showPage()
c.drawImage(str(logo),W-48,H-53,width=30,height=30,preserveAspectRatio=True,mask='auto')
lines('Natural-Language Controls for\nShort-Video Recommenders',27,175,W-54,size=19,leading=23,bold=True,color='#003C71')
lines('An offline study of controllability',27,121,W-54,size=11)
lines('Vibhor Malik\nSupervisor review draft: 14 October 2026\nCOMP 9500, M.Sc. Research Project\nBritish Columbia Institute of Technology\nSupervisor: Borna Noureddin',27,92,W-54,size=8.2,leading=12)
lines('AI assistance was used for implementation, analysis and drafting.',27,22,W-54,size=6.4,leading=8,color='#6E6E6E')
c.showPage()
frame('Formal evaluation procedure',
    '1. Preserve the original bank and September 29 commitment.\n\n2. Agree a replacement unseen bank and annotation route.\n\n3. Obtain independent labels, agreement and blinded adjudication.\n\n4. Complete the full freeze and verify model provenance.\n\n5. Execute once; report parser results before ranking.',
    'The current 100 worked questions and AI answers are exposed practice. Formal E2 remains pending.')
frame('Development evidence and bank exposure',
    'Development v1: rules 48/48; Llama 24/48.\nTen Llama operational errors were retained.\n\nDevelopment v2: rules 48/48; Llama 48/48.\nPrompt and wording changed during development.\n\nThe original 100 questions are now exposed practice.\nNo unseen-test or formal H1/H2 result is claimed.',
    'Archived September 29 development evidence is preserved. Equal development scores establish no LLM advantage.')
frame('Exposed practice execution on October 14',
    'AI reference agreement: Llama 73/100; rules 18/100.\nLlama validation rejections: 24/100, retained.\n\nInduced control success: Llama 23.81%; rules 8.40%;\nitem feedback 3.92%.\nNDCG@10: Llama 0.02461; item feedback 0.03128.\n\n41,508 ranking rows; 865 users; three frozen seeds.',
    'Exposed AI references, not unseen human gold. Fixed Llama 3.1 8B / Ollama 0.34.0; no tuning. Metric recount passed.')
frame('Current completion limits',
    'Experiment 1: complete and frozen; 288 hashes match.\n\nPractice diagnostic: parsing and ranking completed.\nA separate metric recount found no discrepancies.\n\nFormal E2: replacement bank and human evidence pending.\nH1/H2 unassessed; formal H3 has not run.\n\nWindows practice verified; full E1 replay and Colab unverified.',
    'Formal study requires genuinely independent annotation, agreement and blinded adjudication.')
frame('Backup: evidence and responsible authorship',
    'Frozen E1: preserved data, checkpoints, prompts and outcomes.\nAll 288 manifest hashes still match.\n\nPractice: exact inputs, AI-reference provenance, raw responses,\nfull scores, ranking metrics and failures are saved.\n\nValidated parser score: 73/100, with all 24 errors retained.\nControl benefit and NDCG cost are reported together.\n\nHuman annotation and the fresh formal bank remain pending.',
    'Personal reading, independent annotation and activity hours are recorded only when actually completed.')
frame('Current research position',
    'Experiment 1: category enforcement under a fixed policy.\nNo LLM ranking advantage on canonical templates.\n\nExposed practice: better Llama control success,\nwith lower NDCG@10 than item feedback.\n\nFormal unseen E2: replacement bank and eligible\nindependent annotation remain pending.',
    'No unseen language-generalization, recommendation-accuracy gain or human-experience benefit is established.')
frame('Contribution and publication direction',
    'Supported contribution\nAn inspectable pipeline separates translation from enforcement.\nFrozen E1 establishes bounded enforcement and quality cost.\nPractice records a control benefit alongside NDCG cost.\n\nWork needed for a stronger paper\nApprove a fresh bank and valid annotation route prospectively.\nComplete the full freeze before one formal evaluation.\nHuman experience needs a separately approved extension.',
    'The exposed practice result is descriptive; formal H1/H2/H3 remain outstanding.')
frame('Supervisor discussion',
    '1. Decide the prospective amendment and approval record.\n\n2. Agree fresh-bank provenance, access and annotators.\n\n3. Resolve the original non-inferiority margin wording.\n\n4. Confirm final date and repository/evidence access.\n\nThe main report is within 6-8 pages including references;\nthe extended report and audit evidence are separate.',
    'Practice parsing/ranking is verified. No unseen bank, eligible human labels or formal E2 completion is claimed.')
c.save()
inserts=PdfReader(a.inserts)
pages=[]
for i,page in enumerate(original.pages):
    replacement={0:0,1:6,15:1,16:2,18:4,19:7,21:8,26:5}.get(i)
    pages.append(copy.deepcopy(inserts.pages[replacement] if replacement is not None else page))
    if i==16:pages.append(copy.deepcopy(inserts.pages[3]))
assert len(pages)==29
writer=PdfWriter()
for i,page in enumerate(pages):
    if 0<i<23:
        overlay=BytesIO();o=canvas.Canvas(overlay,pagesize=(W,H))
        o.setFillColor(HexColor('#FFFFFF'));o.rect(W-55,5,52,15,fill=1,stroke=0)
        o.setFillColor(HexColor('#192F34'));o.setFont('ArialLocal',6)
        o.drawRightString(W-8,12,f'{i+1}/23');o.save()
        page.merge_page(PdfReader(overlay).pages[0])
    writer.add_page(page)
writer.add_metadata({'/Title':'COMP9500 BCIT presentation verified October 14 2026',
    '/Author':'Vibhor Malik with disclosed AI assistance',
    '/Subject':'Exposed-practice diagnostic; formal E2 pending; PDF composition retains unchanged original slides'})
with a.output.open('wb') as f:writer.write(f)
print(json.dumps({'output':str(a.output),'pages':len(pages),'main_slides':23,'backup_slides':6,
    'method':'Original vector PDF pages retained; 8 pages replaced and 1 inserted using native PDF text; Arial on revised slides.',
    'source_rebuild_blocker':'Local beamer.cls absent; bundled presentation PDF export missing #standard-fonts/Helvetica. No installation performed.'}))
