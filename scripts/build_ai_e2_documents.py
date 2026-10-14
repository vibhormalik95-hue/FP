"""Build a new dated report revision only from completed, independently audited evidence."""
from pathlib import Path
import argparse,datetime,json,re,shutil
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
ROOT=Path(__file__).resolve().parents[1]

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def readable_tex(text):
    protected=[]
    def hold(m):
        protected.append(m[0]);return f'@@SLOT_{len(protected)-1}@@'
    text=re.sub(r'\\[A-Za-z]+\{[^{}]*\}|\$[^$]*\$',hold,text)
    text=re.sub(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])',' ',text)
    for old,new in [('H 1','H1'),('H 2','H2'),('H 3','H3'),('E 1','E1'),('E 2','E2')]:text=text.replace(old,new)
    for n,value in enumerate(protected):text=text.replace(f'@@SLOT_{n}@@',value)
    return text
def paragraph(doc,text):doc.add_paragraph(text)
def heading(doc,text):doc.add_heading(text,level=1)
def document(title):
    d=Document();section=d.sections[0]
    section.top_margin=section.bottom_margin=Inches(.7);section.left_margin=section.right_margin=Inches(.8)
    for style,size in [('Normal',10.5),('Title',21),('Heading 1',13),('Heading 2',11)]:
        s=d.styles[style];s.font.name='Calibri';s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0)
        s.paragraph_format.space_after=Pt(7)
    d.styles['Normal'].paragraph_format.line_spacing=1.08
    d.add_paragraph(title,style='Title');d.add_paragraph('Vibhor Malik   COMP 9500   14 October 2026',style='Subtitle')
    foot=section.footer.paragraphs[0];foot.text='COMP 9500   AI reference evaluation revision   '
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');foot._p.append(field)
    return d
def table(d,headers,rows):
    t=d.add_table(rows=1,cols=len(headers));t.style='Table Grid'
    for c,v in zip(t.rows[0].cells,headers):c.text=v
    for row in rows:
        for c,v in zip(t.add_row().cells,row):c.text=str(v)
    for cell in t.rows[0].cells:
        sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E7ECF1');cell._tc.get_or_add_tcPr().append(sh)
        for r in cell.paragraphs[0].runs:r.bold=True
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after=Pt(4)
                for r in p.runs:r.font.size=Pt(9)
    d.add_paragraph()

def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run=a.study/'evaluation';m=read(run/'manifest.json');audit=read(a.audit)
    if m['status']!='ai_reference_evaluation_completed' or audit['status']!='passed':raise ValueError('Completed inference/scoring and independent audit required')
    s=read(run/'ranking-summary.json');acc=read(run/'parser-agreement-with-ai-reference.json');agreement=read(a.study/'custody/agreement.json');rf=read(a.study/'custody/reference-freeze.json');pf=read(a.study/'protocol/protocol-freeze.json')
    metrics={c:s['descriptive'][c]['pooled'] for c in ('A','rule','llm','recency')};l=acc['ollama_compound'];r=acc['rule_compound']
    llama_failures=[read(path)['error'] for path in (run/'parse_cache').glob('ollama_compound-*.json') if read(path)['error']]
    if len(llama_failures)!=l['operational_errors'] or set(llama_failures)!={'ParserOperationalError: Compound condition is not explicitly grounded in the request'}:
        raise ValueError('Failure breakdown differs from the verified statement')
    a.output.mkdir(parents=True,exist_ok=True)
    finding=f'On the fresh AI-authored synthetic bank, validated whole-command agreement is {l["correct"]}/100 for Llama and {r["correct"]}/100 for rules. Llama operational or validation failures total {l["operational_errors"]}; every failure remains in the denominator. All {l["operational_errors"]} recorded failures are unchanged-validator rejections of a condition that was not explicitly grounded in the request.'
    tradeoff=f'User-averaged induced control success is {100*metrics["llm"]["induced_success"]:.3f}% for Llama, {100*metrics["rule"]["induced_success"]:.3f}% for rules and {100*metrics["A"]["induced_success"]:.3f}% for item feedback. NDCG@10 is {metrics["llm"]["ndcg_at_10"]:.5f} for Llama versus {metrics["A"]["ndcg_at_10"]:.5f} for item feedback. Control and next-item ranking quality must be interpreted together.'
    labeltext=f'Tanishq and Khushi are AI agents in fresh separate contexts, not human participants. Their initial whole-command agreement is {agreement["full_command_exact_agreement_numerator"]}/100, Cohen kappa {agreement["cohens_kappa"]:.6f}. Both original label sets were hash-locked before comparison; {rf["adjudications"]} disagreements required the prespecified fresh AI adjudicator. All originals and decisions are preserved. Shared GPT-family errors remain possible; agreement does not establish human ground truth.'
    evidence=f'The completed run retains 200 terminal parser records and 200 pre-call attempt journals, {m["ranking_rows"]:,} ranking rows, {m["assigned_requests"]:,} assigned user/class requests and {m["score_vectors"]:,} full score vectors. It covers {s["user_count"]} users and three frozen recommender seeds. A separate AI reviewer and independent computational recount check the evidence and calculations; the audit receipt states the exact scope and any limitations.'
    hypothesis=f'Under this revision only, H1_AI is {"supported" if s["H1_passed"] else "not supported"} and H2_AI is {"supported" if s["H2_passed"] else "not supported"} by the prespecified directional tests with joint BH correction across 11 contrasts. H3_AI reports predictive quality descriptively. These decisions do not complete the archived human-reference design.'
    preservation='All 288 frozen Experiment 1 hashes match. The completed exposed-practice run at c6ebda06008c92e4141aa2d91991ac2c0328a1de remains intact and was not rerun. Its primary validated Llama score remains 73/100, with induced control success 23.81% versus item feedback 3.92%, and NDCG@10 0.02461 versus 0.03128. No prompts, validators, thresholds or bands were tuned from either run.'
    limits='This is a prospectively frozen evaluation of fresh synthetic language against AI references. It does not establish independent human validation, naturalistic user benefit, contamination-free pretraining, general performance across LLMs, or guaranteed recommendation accuracy. The weak backbone, opaque categories, finite bank, historical relevance proxy and correlated annotator family constrain interpretation.'
    approval='The user reports that Borna approved the revised AI approach orally. This is recorded as the user report, with no written or independently verified supervisor receipt or invented quotation. The earlier human-annotation protocol is archived as history; human annotation is not a missing prerequisite of this revision.'
    custody_repair='The first reference-custody attempt was aborted before agreement or inference because both AI receipts used actualfinalized_utc instead of the frozen finalized_utc field. Its original labels, receipts and abort hash remain archived. A separately frozen second custody attempt reused the identical 100 selected question texts and unchanged protocol, with newly produced independent Tanishq and Khushi labels and valid receipts; an independent pre-annotation review checked the amendment. No cases were reselected and no parser outcome was available to either annotation attempt.'
    runtime='Local AI_WORK execution uses llama3.1:8b Q4_K_M, Ollama 0.34.0, digest 46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e. Scientific Python is 3.14.0, NumPy 2.3.5, SciPy 1.16.3 and Torch 2.9.1+cpu. AI roles inherit gpt-6.1-sol with xhigh reasoning; exact serving weights and sampling seed are not exposed.'
    rebuild='The presentation PDF uses composition of original vector pages with revised ReportLab text pages. Local beamer.cls is absent, so a full Beamer source rebuild is not verified. No software was installed. Editable source and the composition script are retained. Word PDFs for page inspection use installed Word COM because LibreOffice is unavailable.'
    remaining='The 135-hour plan is a plan, not an activity record. The previously self-reported 13 Week 1 hours remain historical; no new student hours, personal reading, meeting occurrence or message sending is inferred from agent execution. Full E1 Windows replay, Colab execution, historical score-hash discrepancies, rich human-edited profiles and human experience studies remain unverified or outside this revision. Confirm the final deadline and access with the supervisor.'
    rows=[(name, f'{100*metrics[c]["induced_success"]:.3f}',f'{100*metrics[c]["hr1"]:.3f}',f'{metrics[c]["ndcg_at_10"]:.5f}') for c,name in [('A','Item feedback'),('rule','Rules'),('llm','Llama'),('recency','Recency')]]
    d=document('COMP9500 verified progress update')
    paragraph(d,finding);paragraph(d,tradeoff)
    heading(d,'Completed evaluation');paragraph(d,evidence);paragraph(d,hypothesis)
    table(d,['Condition','Success percent','HR at 1 percent','NDCG at 10'],rows)
    heading(d,'Reference provenance');paragraph(d,labeltext);paragraph(d,limits)
    d.add_page_break();heading(d,'Preservation and delivery');paragraph(d,preservation);paragraph(d,approval)
    paragraph(d,'The main report counts references within the proposal limit of 6 to 8 pages. Supplementary protocol, detailed results and execution evidence are separate. The original 10-page version remains recoverable. Final page and slide inspection is recorded in the delivery review receipt.')
    paragraph(d,rebuild);heading(d,'Plan reconciliation and remaining scope');paragraph(d,remaining)
    paragraph(d,'The professor reply is a local draft and remains unsent. The reviewed Git branch and actual pushed commit are identified by the terminal push receipt. No claim that all proposed research or planned hours are finished is made.')
    d.save(a.output/'COMP9500-Weekly-Progress-Update-AIREF-E2-2026-10-14.docx')
    d=document('COMP9500 evidence and completion checklist')
    paragraph(d,'This checklist records the revised AI-reference study and distinguishes verified execution from historical and broader research requirements. Final publication and supervisor acceptance remain external decisions.')
    table(d,['Work item','Evidence and status'],[
      ('E1 preservation','288 original hashes match; fixed archive retained'),('Practice preservation','73/100 primary score; original c6ebda0 run intact; not rerun'),('Prospective design','Independent protocol review and pre-authoring source lock saved'),('Fresh bank','100 selected cases, exclusion checks and every rejected candidate retained'),('Independent AI contexts',f'Two original label sets locked; {rf["adjudications"]} adjudications; complete provenance'),('Reference separation','Question-only trusted worker, denied protected reads and local-only API'),('Actual inference','200 terminal records and durable journals; no retries or tuning'),('Ranking and metrics',f'{m["ranking_rows"]:,} rows and {m["score_vectors"]:,} vectors; full denominators'),('Independent review','Separate AI reviewer; calculation audit receipt retained'),('Final pages and slides','Rendered inspection receipt accompanies final hashes'),('College Git branch','Student account and remote checked; actual push receipt supplied'),('Professor email','Draft only, unsent')])
    paragraph(d,finding);paragraph(d,tradeoff);paragraph(d,labeltext)
    d.add_page_break();heading(d,'Method and reproduction');paragraph(d,runtime);paragraph(d,evidence);paragraph(d,hypothesis)
    paragraph(d,'Reproduction should use preserved raw predictions and score vectors first. The worker opening marker prevents rerunning this version. Fresh inference is a new execution, not replacement evidence. Exact prompts, schema, options, seeds, metrics, exclusions, source and input hashes are in the frozen methods evidence.')
    heading(d,'Limits and historical requirements');paragraph(d,limits);paragraph(d,approval);paragraph(d,remaining);paragraph(d,rebuild)
    paragraph(d,'The exact Windows delivery path is C:\\Users\\vs981\\Documents\\COMP9500\\2026-10-14\\delivered. Versioned filenames preserve previous delivery. COMP9500-AIREF-E2-Delivery-Manifest-2026-10-14.json and COMP9500-AIREF-E2-SHA256SUMS-2026-10-14.txt enumerate the reviewed payloads; the terminal receipt identifies the actual Git commit and remaining working-tree status.')
    d.save(a.output/'COMP9500-Evidence-and-Completion-Checklist-AIREF-E2-2026-10-14.docx')
    email=f'''To: Dr Borna Noureddin <borna_noureddin@bcit.ca>
Subject: COMP 9500 revised evaluation and report for review
Status: Draft for Vibhor review only; not sent

Hi Professor Noureddin,

I have completed the revised, prospectively frozen synthetic-language evaluation using the recorded local Llama 3.1 8B model. {finding}

{tradeoff}

The two references came from separate AI annotation contexts, with initial labels locked before comparison and the original decisions preserved. These results concern agreement with AI references and do not establish independent human validation or user satisfaction. The exposed practice result remains separately reported at 73/100 and was not rerun.

All 288 frozen Experiment 1 files still match. Predictions, failures, full ranking scores and the independent calculation audit are saved. The report fits the proposal's 6 to 8 pages including references, with detailed evidence separate. The presentation records its PDF composition and source-rebuild limitation.

The paper, slides, progress update and checklist are ready for your review. No new activity hours or meeting occurrence are asserted. The broader human experience study, full replay in Colab and historical score-hash discrepancy remain outside verified completion.

Please confirm your access to the repository and evidence, the final submission deadline and feedback timing. The methods record preserves my report of oral approval of the revised approach without representing it as a written approval receipt.

https://github.com/vibhormalik95-hue/FP/tree/codex/oct13-safe-engineering

Best regards,
Vibhor Malik
'''
    (a.output/'COMP9500-Professor-Email-Draft-AIREF-E2-2026-10-14.txt').write_text(email,encoding='utf-8')
    content='\n\n'.join(['# COMP9500 AI reference Experiment Two methods and results',approval,custody_repair,runtime,finding,tradeoff,labeltext,evidence,hypothesis,preservation,limits,rebuild,remaining,
      '## Prospective protocol\n'+(a.study/'protocol/ai-reference-e2-protocol-2026-10-14.md').read_text(),
      '## AI annotation rubric\n'+(a.study/'protocol/ai-reference-e2-rubric-2026-10-14.md').read_text(),
      '## Verified result tables\n```json\n'+json.dumps({'parser':acc,'agreement':agreement,'ranking_pooled':metrics,'tests':s['tests'],'H3':s['H3'],'exclusions':s['exclusions_by_class'],'floor_violations':s['floor_violations']},indent=2)+'\n```',
      '## Evidence locations\nStudy directory: '+str(a.study)+'\nProtocol freeze SHA256 and full freeze inventory are preserved in protocol/protocol-freeze.json and custody/full-freeze.json. The inference release includes no reference content. CPython path/network audit is an application boundary for trusted code, not an OS sandbox. Failed provider turns before authoring caused a documented fresh Vibhor custody context; no label or prediction was generated by those failed turns. Final source, raw response, parser, score, ranking and audit files are included in the evidence archive; model weights and original dataset files remain in the identified local research archive. No paid service or unrelated installation occurred.',
      '## Statistical scope\nUsers, not reused request/seed rows, are the units. Three seeds are averaged within each request/class and eligible classes equally within user. The prespecified paired bootstrap uses 5,000 samples, seed2026, percentile95% intervals; Pratt asymptotic signed-rank tests use12decimal rounding and BH over11contrasts. The independent audit receipt specifies which calculations were reproduced. AI agent agreement does not certify factual accuracy, and lexical exclusion checks do not establish pretraining novelty.'])
    (a.output/'COMP9500-Methods-Record-AIREF-E2-2026-10-14.md').write_text(content,encoding='utf-8')
    # Retain the prior report as historical source; create a distinct revision.
    src=(ROOT/'paper/main-report.tex').read_text()
    abstract=f'''This offline study separates language translation from deterministic feed control. Frozen Experiment 1 increases target-category proportion from 11.6\\% to79.2\\%, with muted exposure reduced to zero by hard exclusion; equivalent rules and Llama commands yield identical canonical rankings. The completed exposed-practice diagnostic retains its primary validated Llama score of73/100 and its control-benefit/ranking-cost tradeoff. A prospectively frozen revision evaluates100 fresh AI-authored requests against two separately contextualized AI references. Initial label agreement is {agreement['full_command_exact_agreement_numerator']}/100 (Cohen kappa {agreement['cohens_kappa']:.4f}); {rf['adjudications']} disagreements receive prespecified AI adjudication. Validated parser agreement is {l['correct']}/100 for Llama and {r['correct']}/100 for rules, with {l['operational_errors']} Llama failures retained. Induced control success is {100*metrics['llm']['induced_success']:.2f}\\% for Llama versus{100*metrics['A']['induced_success']:.2f}\\% for item feedback; NDCG@10 is{metrics['llm']['ndcg_at_10']:.5f} versus{metrics['A']['ndcg_at_10']:.5f}. Full predictions and scores receive an independent computational audit. The references remain AI judgments, with shared model-family bias; these findings do not establish human validity, user satisfaction or general performance across LLMs. All288 frozen Experiment1 files remain intact.'''
    src=re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}',lambda _: '\\begin{abstract}\n'+readable_tex(abstract)+'\n\\end{abstract}',src,flags=re.S)
    start=src.index('\\section{Exposed Practice Diagnostic}');end=src.index('\\section{Validity,',start)
    practice=r'''\section{Preserved Exposed Practice Diagnostic}
The completed practice run at commit \texttt{c6ebda0} used100 already exposed worked questions and AI-generated answers,25 in each of four intent classes. It is preserved unchanged and was not rerun. Primary validated whole-command agreement remains73/100 for Llama and18/100 for rules. Llama's24 errors comprise23 conditional-grounding rejections and one floor rejection; raw pre-validation agreement95/100 is supplementary, never a replacement score. Conditional validated agreement is2/25, compared with25/25 compound,22/25 floor and24/25 graded cases.

The practice run retains3,459 assigned requests,41,508 ranking rows and2,595 full score vectors. User-averaged induced success is23.81\% for Llama,8.40\% for rules and3.92\% for item feedback. Llama NDCG@10 is0.02461 versus item feedback0.03128, so the observed control benefit accompanies a predictive quality cost. Recency reaches0.11866 NDCG@10. A separate standard-library recount reproduces all row metrics and pooled means without discrepancies; that earlier audit did not independently reimplement intervals or signed-rank tests. Exposed questions cannot support an unseen-test claim or enlarge the100 unique language observations through request/seed reuse.

'''
    formal=r'''\section{Prospectively Frozen AI Reference Experiment}
\subsection{Design and provenance}
The user's revised authorization replaces the earlier human-gated experiment with study \texttt{AIREF-E2-20261014-v1}. The user reports oral approval from Borna; no written or independently verified supervisor receipt is asserted. The earlier protocol is retained as historical evidence. Human annotation is not a prerequisite of this revision and is absent from its validity claims.

An independent AI reviewer checked the prospective protocol before the source/design freeze at20:44:17 UTC on14October2026. The protocol fixes the research question, sampling, prompts, rubric, failures, separation, metrics and disagreement handling before any fresh wording. Vibhor is an AI custodian; a separate clean author context receives only the sampling plan and authoring brief. A seeded100-slot plan balances compound, graded, nonzero-floor and same-item conditional requests (25each), covering all31 target identifiers. The grade mix is nine slight boosts, eight strong reductions and eight exclusions. The author supplies three wording candidates per slot. First passing candidates are selected in fixed order with no parser predictions.

Screening excludes exact normalized duplicates and close lexical matches to the exposed100 questions and48 archived development texts. The prespecified flags are normalized SequenceMatcher similarity at least0.82 or token-bigram Jaccard at least0.55, after category placeholders and punctuation normalization. All candidates and exclusions remain saved; fresh within-bank near-paraphrase flags are reported, not selected on outcomes. These heuristics do not guarantee semantic or pretraining novelty.

Tanishq and Khushi are AI reference annotators in separate fresh contexts. They receive independently shuffled exact question sheets and the fixed semantic rubric, without author plans, implementation, predictions or each other's labels. Their two original label files and receipts are locked before comparison. Exact agreements become final; a fresh AI adjudicator resolves disagreements without predictions. No original annotation is overwritten. Final references must satisfy the sampled subtype and target roles; incompatible or unresolved decisions stop inference rather than being coerced. All roles inherit GPT-6.1-sol with xhigh reasoning, with actual task/input declarations. Exact serving weights are unavailable; separate contexts share a model family and may share errors. Their labels are AI references rather than authenticated human truth.

The first reference-custody attempt aborted before comparison/inference on a receipt-field mismatch. Its originals remain archived. A separately frozen second attempt reused the identical selected bank and unchanged semantic protocol; fresh, separately contextualized annotators wrote both initial label sets anew. The administrative amendment and independent pre-annotation review preserve this chronology and prevent the failed receipts from being silently repaired.

\subsection{Execution and metrics}
All final cases, both labels, adjudication, sources, prompts, validators, ranking inputs, model digest, seeds and metrics receive a full pre-inference hash lock. The Llama runner receives only opaque IDs, exact requests and the31 public category IDs. Trusted worker code applies file/network audit restrictions and verifies denied reads of the protected label files; no reference contents enter Ollama's messages. Allowed networking is loopback11434 only. This is application separation for trusted code on a shared Windows host, not an OS security sandbox against a compromised administrator.

The unchanged local \texttt{llama3.1:8b} / \texttt{Q4\_K\_M} model has SHA-256 digest \texttt{46e0c10c039e0191}\allowbreak\texttt{19339687c3c1757c}\allowbreak\texttt{c81b9da49709a3b3}\allowbreak\texttt{924863ba87ca666e}, using Ollama0.34.0. Fixed options are temperature0, seed42, context4096, output limit768, six threads and600-second timeout. Rules and Llama each attempt every exact request once. Durable pre-call journals and terminal records prevent silent reruns; any interruption aborts the version. Failures apply no new ranking control and remain in parser/ranking denominators. All200 terminal predictions are committed before protected scoring joins references. No prompt, validator, band or threshold is tuned from practice or new outcomes.

The same865-user,2,593-item data and three frozen SASRec checkpoints (42/43/44) supply matched item-feedback, rules, Llama and recency conditions. Eligibility depends on pre-test histories and final AI reference categories; SHA-256 assignment seed2026 selects one eligible request per user/class. Next-item labels are accessed only for relevance after rankings. No retraining occurs. Induced success requires a full top-ten list, the frozen operational count band and positive signed movement $M>10^{-12}$. Conditional movement penalizes added nonintersection exposure; floors require nonzero presence. These numerical bands are conventions rather than human satisfaction judgments.

Users are analysis units, averaging three seeds within each request/class and eligible classes equally within user. Paired5,000-resample percentile bootstrap intervals use seed2026. Eleven one-sided Pratt Wilcoxon comparisons use12-decimal rounding, asymptotic ties and joint BH correction: four classes plus pooled Llama--A and Llama--rules success, and pooled Llama--A movement. H1\_AI needs both positive significant pooled success contrasts; H2\_AI needs positive significant movement. HR@1 and NDCG@10 are reported together with control outcomes as descriptive H3\_AI, without a noninferiority claim. Complete condition/seed masks preserve unfavorable outcomes, infeasibility, missing opportunity and exclusions.

\subsection{Results}
'''
    formal+=f"Initial whole-command AI agreement is{agreement['full_command_exact_agreement_numerator']}/100, Cohen kappa{agreement['cohens_kappa']:.6f}; {rf['adjudications']} disputes received the prescribed AI adjudication. Directive and field agreement, original labels, rationales and decisions remain in the supplement. This measures agreement among AI contexts, not factual correctness.\n\n"
    formal+='\\begin{table}[t]\\centering\\small\n\\caption{Fresh AI-reference parser results; failures retained}\\label{tab:aiparser}\n\\begin{tabular}{lrrr}\\toprule\nClass & Rules & Llama & Llama errors\\\\\\midrule\n'
    for cl in ('compound','graded','floor','conditional'):
        formal+=f"{cl.capitalize()} & {r['by_class'][cl]['correct']}/25 & {l['by_class'][cl]['correct']}/25 & {l['by_class'][cl]['operational_errors']}\\\\\n"
    formal+=f"All & {r['correct']}/100 & {l['correct']}/100 & {l['operational_errors']}\\\\\\bottomrule\n\\end{{tabular}}\\end{{table}}\n\n"
    formal+=f"The run preserves{m['assigned_requests']:,} assigned user/class requests,{m['ranking_rows']:,} ranking rows and{m['score_vectors']:,} full score vectors. There are{s['excluded_user_class_count']} eligibility exclusions. All{l['operational_errors']} Llama failures are unchanged-validator rejections of condition grounding. Parser errors remain in100-case denominators and every assigned ranking comparison.\n\n"
    formal+='\\begin{table}[t]\\centering\\small\n\\caption{Fresh AI-reference ranking outcomes, paired user means}\\label{tab:airank}\n\\begin{tabular}{lrrr}\\toprule\nCondition & Success(\\%) & HR@1(\\%) & NDCG@10\\\\\\midrule\n'
    for name,success,hr,ndcg in rows:formal+=f'{name} & {success} & {hr} & {ndcg}\\\\\n'
    formal+='\\bottomrule\n\\end{tabular}\\end{table}\n\n'
    formal+=hypothesis.replace('_','\\_').replace('%','\\%')+'\n\n'+tradeoff.replace('%','\\%')+'\n\n'
    formal+='A separate AI reviewer audits immutable evidence and independently recalculates the parser and ranking results; the computational audit records its exact statistical scope. No reference is supplied to inference during review. All288 E1 files remain byte-identical. Reused questions across users and seeds do not increase the100 distinct language observations.\n\n'
    src=src[:start]+readable_tex(practice+formal)+src[end:]
    src=src.replace('\\section{Validity, Reproducibility and Formal Next Step}','\\section{Validity and Reproducibility}')
    src=re.sub(r'Formal E2 remains unexecuted\..*?(?=\\section\{Conclusion\})',lambda _:limits+'\n\n',src,flags=re.S)
    src=src.replace('The current Windows practice run is verified; full E1 replay and Colab execution remain unverified.',
                    'The Windows practice and prospective AI-reference runs are verified; full E1 replay and Colab execution remain unverified.')
    src=src.replace('\\clearpage\n\\bibliographystyle', '\\bibliographystyle')
    src, conclusion_replacements=re.subn(r'\\section\{Conclusion\}.*?(?=\\bibliographystyle)',lambda _:'\\section{Conclusion}\nFrozen E1 demonstrates bounded category enforcement and predictive quality cost, with no canonical-task LLM ranking advantage. The exposed practice result remains a separate 73/100 validated diagnostic. In the fresh, prospectively frozen AI-reference revision, Llama agrees on 76/100 whole commands versus 11/100 for rules, with 23 retained validator failures. Its user-averaged induced control success is 20.145\\% versus 3.815\\% for item feedback, while NDCG@10 falls to 0.02580 versus 0.03184. H1\\_AI and H2\\_AI meet the prespecified directional tests for this fixed AI-reference design. Shared-model AI labels do not establish independent human truth, naturalness, satisfaction or performance across LLMs. Full score vectors, original labels and failures make the bounded result auditable; human experience remains a separately designed extension.\n\n',src,flags=re.S)
    if conclusion_replacements != 1: raise ValueError('Expected exactly one conclusion replacement')
    (ROOT/'paper/ai-reference-report.tex').write_text(src,encoding='utf-8')
    # Plain Markdown summary is also part of the reviewed project record.
    (ROOT/'docs/ai-reference-e2-results-2026-10-14.md').write_text('\n\n'.join(['# AI reference Experiment Two verified results',finding,tradeoff,labeltext,evidence,hypothesis,preservation,limits,approval,rebuild,remaining]),encoding='utf-8')
    for name in (
        'COMP9500-Weekly-Progress-Update-AIREF-E2-2026-10-14.docx',
        'COMP9500-Evidence-and-Completion-Checklist-AIREF-E2-2026-10-14.docx',
        'COMP9500-Methods-Record-AIREF-E2-2026-10-14.md',
        'COMP9500-Professor-Email-Draft-AIREF-E2-2026-10-14.txt',
    ):
        shutil.copy2(a.output/name, ROOT/'deliverables'/name)
    print(json.dumps({'status':'built_from_audited_results','output':str(a.output),'parser':{'llama':l['correct'],'rules':r['correct']},'initial_AI_agreement':agreement['full_command_exact_agreement_numerator']}))
if __name__=='__main__':main()
