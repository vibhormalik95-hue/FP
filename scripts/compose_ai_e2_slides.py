"""Audited AI-reference update of the existing BCIT PDF; honest PDF composition."""
from pathlib import Path
from io import BytesIO
import argparse,copy,json,re
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader,PdfWriter
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--inserts',type=Path,required=True);a=p.parse_args()
    def read(path):return json.loads(Path(path).read_text())
    if read(a.audit)['status']!='passed':raise ValueError('Independent audit required')
    m=read(a.study/'evaluation/manifest.json');s=read(a.study/'evaluation/ranking-summary.json');acc=read(a.study/'evaluation/parser-agreement-with-ai-reference.json');ag=read(a.study/'custody/agreement.json');rf=read(a.study/'custody/reference-freeze.json')
    if m['status']!='ai_reference_evaluation_completed':raise ValueError('Completed run required')
    x={c:s['descriptive'][c]['pooled'] for c in ('A','rule','llm','recency')};l=acc['ollama_compound'];r=acc['rule_compound']
    spec={
      1:('Current research position','Frozen E1 establishes bounded category enforcement.\nEquivalent commands yield identical canonical rankings.\n\nExposed practice remains a separate 73/100 diagnostic.\n\nThe new prospective AI-reference evaluation measures\nparser agreement and control with ranking-quality cost.','The finite synthetic bank and AI references do not establish human validity or general performance across LLMs.'),
      12:('Experiment Two under the AI revision','H1_AI: greater induced control success than both\nitem feedback and the unchanged rule parser.\n\nH2_AI: greater intended movement than item feedback.\n\nH3_AI: report HR@1 and NDCG@10 descriptively.\n\nAll claims concern this fixed system and AI references.','The user reports oral approval from Borna. No written or independently verified approval receipt is asserted.'),
      15:('Prospective design and separated roles','Protocol and source frozen before any fresh wording.\n\nVibhor: AI custodian controlling manifests and access.\nSeparate author: fresh requests from the seeded plan.\nTanishq and Khushi: separate AI annotation contexts.\n\nBoth label sets lock before comparison. Disputes use\na fresh AI adjudicator without predictions.','All AI roles inherit GPT-6.1-sol / xhigh. Shared model-family errors remain possible.'),
      16:('Fresh bank and reference provenance',f'100 selected requests, 25 in each of four classes.\n31 target category IDs covered by the fixed plan.\n\nScreened against 100 exposed and 48 development texts.\nNo duplicate or frozen close-paraphrase flags selected.\n\nInitial AI label agreement: {ag["full_command_exact_agreement_numerator"]}/100.\nCohen kappa: {ag["cohens_kappa"]:.4f}. Adjudicated disputes: {rf["adjudications"]}.','Lexical screening does not prove semantic or pretraining novelty. AI agreement is not human ground truth.'),
      17:('Prespecified analysis','User is the analysis unit. Average three seeds within\neach request/class, then equal eligible classes per user.\n\n5,000 paired user bootstrap samples, seed 2026.\nPratt one-sided Wilcoxon with joint BH over 11 tests.\n\nKeep failures, infeasibility and exclusions visible.\nReport control, HR@1 and NDCG@10 together.','Frozen prompts, validators, model digest, ranking inputs, seeds and metrics precede inference. No outcome tuning.'),
      18:('Fresh AI-reference evaluation results',f'Validated parser agreement: Llama {l["correct"]}/100; rules {r["correct"]}/100.\nLlama operational/validation failures: {l["operational_errors"]}, retained.\n\nInduced success: Llama {100*x["llm"]["induced_success"]:.2f}%; rules {100*x["rule"]["induced_success"]:.2f}%;\nitem feedback {100*x["A"]["induced_success"]:.2f}%.\nNDCG@10: Llama {x["llm"]["ndcg_at_10"]:.5f}; item feedback {x["A"]["ndcg_at_10"]:.5f}.\n\n{m["ranking_rows"]:,} ranking rows; {m["score_vectors"]:,} full score vectors.','These measured control and quality outcomes concern AI-authored synthetic requests, not independent human validation.'),
      19:('Contribution and limits',f'H1_AI: {"supported" if s["H1_passed"] else "not supported"}. H2_AI: {"supported" if s["H2_passed"] else "not supported"}.\nDecisions apply only to the prospective AI revision.\n\nTranslation, enforcement and quality remain observable.\nThe current bank and all recorded failures are auditable.\n\nHuman experience, naturalistic language and other\nLLM models require separate evidence.','The weak backbone, opaque categories and historical next-item proxy limit recommendation-quality interpretation.'),
      20:('Plan reconciliation','Verified now\nFrozen E1, exposed practice, revised AI-reference run,\nindependent audit and reviewed report artifacts.\n\nSeparate remaining scope\nFull E1 Windows replay and Colab remain unverified.\nHuman experience needs a separately designed study.\nHistorical score-hash discrepancy remains unresolved.','The 135-hour schedule is planned effort. No new student hours or meeting occurrence are inferred from agent/runtime activity.'),
      21:('Supervisor review','Review the measured AI-reference findings and limits.\n\nConfirm repository and complete-evidence access,\nfinal submission deadline and feedback timing.\n\nMain report: 6-8 pages including references.\nDetailed methods and audit evidence are separate.\n\nThe professor email remains an unsent local draft.','The earlier human-annotation protocol remains archived history and is not a prerequisite of this AI revision.'),
      26:('Backup evidence and execution route',f'288 frozen E1 hashes match after the new work.\n200 predictions committed before joining references.\n200 pre-call journals; {m["score_vectors"]:,} full score vectors.\n\nLocal llama3.1:8b / Q4_K_M, Ollama 0.34.0.\nModel digest and literal payloads are in methods evidence.\n\nSeparate reviewer checks saved outputs and calculations.','PDF composition retains original vector pages and uses revised Arial text pages. beamer.cls is absent; full Beamer rebuild unverified.')}
    practice=('Preserved exposed practice execution','Validated AI-reference agreement: Llama 73/100; rules 18/100.\nAll 24 Llama validation errors remain counted.\n\nInduced success: Llama 23.81%; rules 8.40%;\nitem feedback 3.92%.\nNDCG@10: Llama 0.02461; item feedback 0.03128.\n\n41,508 ranking rows; separate recount passed.','Original c6ebda0 practice run is intact and was not rerun. These exposed questions do not supply an unseen test.')
    original=PdfReader(ROOT/'deliverables/COMP9500-BCIT-Presentation.pdf');W,H=map(float,(original.pages[0].mediabox.width,original.pages[0].mediabox.height))
    pdfmetrics.registerFont(TTFont('ArialLocal','C:/Windows/Fonts/arial.ttf'));pdfmetrics.registerFont(TTFont('ArialLocalBold','C:/Windows/Fonts/arialbd.ttf'))
    logo=ROOT/'presentation-bcit/bcit_logo.png';c=canvas.Canvas(str(a.inserts),pagesize=(W,H))
    def lines(text,x,y,width,size=10,leading=14,bold=False,color='#192F34'):
        font='ArialLocalBold' if bold else 'ArialLocal';c.setFont(font,size);c.setFillColor(HexColor(color))
        for paragraph in text.split('\n'):
            for line in simpleSplit(paragraph,font,size,width) or ['']:c.drawString(x,y,line);y-=leading
        return y
    def frame(title,body,note):
        c.setFillColor(HexColor('#003C71'));c.rect(0,H-30,W,30,fill=1,stroke=0)
        lines(title,12,H-20,W-24,12,14,True,'#FFFFFF');bottom=lines(body,27,H-56,W-54)
        if bottom<=51:raise ValueError('Slide body overflow: '+title)
        lines(note,27,49,W-54,6.4,8,color='#6E6E6E');c.drawImage(str(logo),6,8,14,14,preserveAspectRatio=True,mask='auto')
        lines('COMP 9500 Natural language controls',30,12,W-80,5.5,7);c.showPage()
    c.drawImage(str(logo),W-48,H-53,30,30,preserveAspectRatio=True,mask='auto')
    lines('Natural-Language Controls for\nShort-Video Recommenders',27,175,W-54,19,23,True,'#003C71')
    lines('An offline study of controllability',27,121,W-54,11,14)
    lines('Vibhor Malik\nSupervisor review draft 14 October 2026\nCOMP 9500 M.Sc. Research Project\nBritish Columbia Institute of Technology\nSupervisor Borna Noureddin',27,92,W-54,8.2,12)
    lines('AI assistance was used for implementation, analysis and drafting.',27,22,W-54,6.4,8,color='#6E6E6E');c.showPage()
    indexes={0:0}
    for old_index,content in spec.items():indexes[old_index]=len(indexes);frame(*content)
    practice_index=len(indexes);frame(*practice);c.save()
    inserts=PdfReader(a.inserts);pages=[]
    for i,page in enumerate(original.pages):
        pages.append(copy.deepcopy(inserts.pages[indexes[i]] if i in indexes else page))
        if i==16:pages.append(copy.deepcopy(inserts.pages[practice_index]))
    assert len(pages)==29
    writer=PdfWriter()
    for i,page in enumerate(pages):
        if 0<i<23:
            stream=BytesIO();overlay=canvas.Canvas(stream,pagesize=(W,H));overlay.setFillColor(HexColor('#FFFFFF'));overlay.rect(W-55,5,52,15,fill=1,stroke=0)
            overlay.setFillColor(HexColor('#192F34'));overlay.setFont('ArialLocal',6);overlay.drawRightString(W-8,12,f'{i+1}/23');overlay.save();page.merge_page(PdfReader(stream).pages[0])
        writer.add_page(page)
    writer.add_metadata({'/Title':'COMP9500 prospective AI-reference evaluation review','/Author':'Vibhor Malik','/Subject':'PDF composition; source Beamer rebuild unverified; finite synthetic AI references'})
    with a.output.open('xb') as f:writer.write(f)
    # Keep a corresponding editable Beamer revision, without claiming it rebuilt.
    source=(ROOT/'presentation-bcit/main.tex').read_text();frames=list(re.finditer(r'\\begin\{frame\}(?:\[[^\]]*\])?(?:\{[^}]*\})?.*?\\end\{frame\}',source,re.S))
    if len(frames)!=29:raise ValueError('Unexpected Beamer frame inventory')
    def escape(text):
        for old,new in [('&',r'\&'),('%',r'\%'),('_',r'\_')]:text=text.replace(old,new)
        return text
    replacements={i+(i>16):content for i,content in spec.items()};replacements[17]=practice
    for index in sorted(replacements,reverse=True):
        title,body,note=replacements[index];replacement='\\begin{frame}{'+escape(title)+'}\n\\small\n'+'\n\n'.join(escape(part).replace('\n',r'\\'+'\n') for part in body.split('\n\n'))+'\n\\vfill\n\\tiny '+escape(note)+'\n\\end{frame}'
        match=frames[index];source=source[:match.start()]+replacement+source[match.end():]
    (ROOT/'presentation-bcit/ai-reference-main.tex').write_text(source,encoding='utf-8')
    record={'pages':29,'main_slides':23,'backup_slides':6,'replaced_original_indices':sorted(indexes),'inserted_practice_after_original_index':16,
      'route':'Original vector PDF pages retained; new Arial text composed with ReportLab/pypdf. Corresponding editable Beamer source retained but full rebuild unverified: local beamer.cls absent.',
      'slides':{str(k):v for k,v in spec.items()},'practice_slide':practice}
    (a.study/'audit/slide-composition-record.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in record.items() if k not in ('slides','practice_slide')}))
if __name__=='__main__':main()
