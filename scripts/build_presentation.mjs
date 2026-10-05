import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const workspaceDir = process.env.CMP_PROJECT_ROOT || '/workspace/scratch/f5758fa874dd/cmp9500-recommender';
const TMP_DIR = path.join(workspaceDir, 'slides/build-experiment2');
const SKILL_DIR = '/root/.codex/skills/builtins/presentations';
const RUNTIME_PYTHON = process.env.CODEX_PRIMARY_RUNTIME_PYTHON;
const RUNTIME_NODE = process.env.CODEX_PRIMARY_RUNTIME_NODE;
const RUNTIME_NODE_MODULES = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
const RUNTIME_BIN_DIR = path.join(process.env.CODEX_PRIMARY_RUNTIME, 'dependencies/bin/override');
Object.assign(process.env, {RUNTIME_NODE, RUNTIME_NODE_MODULES, RUNTIME_PYTHON, RUNTIME_BIN_DIR});
for (const p of [workspaceDir, RUNTIME_PYTHON, RUNTIME_NODE, RUNTIME_NODE_MODULES, RUNTIME_BIN_DIR]) {
  if (!path.isAbsolute(p || '')) throw Error('Required absolute runtime/task path missing');
  await fs.access(p);
}
const {resolvePresentationFont, applyPresentationChartFont, finalizePresentation} = await import(pathToFileURL(path.join(SKILL_DIR,'container_tools/artifact_tool_utils.mjs')).href);
const font = resolvePresentationFont({fontFamily:'Arial'});
const presentation = Presentation.create({slideSize:{width:1280,height:720}});
const C={navy:'#142A43',ink:'#18212B',muted:'#526274',blue:'#255B88',teal:'#1E786B',light:'#E8EEF3',white:'#FFFFFF'};
let evidence={};
try { evidence=JSON.parse(await fs.readFile(path.join(workspaceDir,'slides/evidence.json'),'utf8')); } catch {}
if(process.env.CMP_FINAL_PPTX && (!evidence.parser || !evidence.aggregate || evidence.aggregate_backend!=='ollama')) throw Error('Final deck requires checked parser and actual LLM aggregate evidence');
const data=JSON.parse(await fs.readFile(path.join(workspaceDir,'data/processed.json'),'utf8'));
const dm=data.metadata;
const n=(v)=>Number(v).toLocaleString('en-CA');
const pct=(v,d=1)=>`${(v*100).toFixed(d)}%`;
const dec=(v,d=4)=>Number(v).toFixed(d);
const tableSlides=[], chartSlides=[];
function text(slide,content,x,y,w,h,size=28,bold=false,color=C.ink){
 const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 s.text=content;s.text.style={typeface:font,fontSize:size,bold,color,autoFit:'none'};return s;
}
function slide(title,notes){
 const s=presentation.slides.add();s.background.fill=C.white;
 text(s,title,64,42,1152,106,44,true,C.navy);
 text(s,String(presentation.slides.items.length),1148,677,68,25,18,false,C.muted);
 s.speakerNotes.textFrame.setText(notes);return s;
}
function prose(s,paras,top=188){paras.forEach((p,i)=>text(s,p,70,top+i*135,1110,114,29,false,C.ink));}
function table(s,values,widths,top=172,height=415,size=25){
 tableSlides.push(presentation.slides.items.length);
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:64,top,width:1152,height,columnWidths:widths,values});
 t.borders.assign({fill:'#D5DFE7',width:0.6});
 for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
  const cell=t.getCell(r,c);cell.fill=r===0?C.navy:(r%2?C.white:'#F4F7FA');
  cell.text.style={typeface:font,fontSize:size,color:r===0?C.white:C.ink,bold:r===0};
 }
 t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({margins:{left:12,right:12,top:9,bottom:9},anchor:'center'});
 return t;
}
function foot(s,txt){text(s,txt,70,615,1110,55,22,false,C.muted);}
function chart(s,categories,series,title){
 chartSlides.push(presentation.slides.items.length);
 const ch=s.charts.add('bar',{position:{left:65,top:165,width:1140,height:425},categories,series:series.map(x=>({...x,values:x.values.map(v=>Number(v.toFixed(6))),valuesFormatCode:'0.0%'})),barOptions:{direction:'column',grouping:'clustered',gapWidth:75},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:22,typeface:font,fill:C.ink}},xAxis:{textStyle:{fontSize:23,typeface:font,fill:C.ink}},yAxis:{min:0,max:1,numberFormatCode:'0%',textStyle:{fontSize:20,typeface:font,fill:C.muted},majorGridlines:{fill:'#D5DFE7',width:0.5}},dataLabels:{showValue:true,position:'outEnd',textStyle:{fontSize:22,typeface:font,fill:C.ink}},chartFill:C.white,plotAreaFill:C.white});
 applyPresentationChartFont(ch,{fontFamily:font});return ch;
}
// 1
{
 const s=presentation.slides.add();s.background.fill=C.white;
 text(s,'LLM-Mediated Natural Language Controls\nfor Short-Video Recommender Systems',65,92,1150,205,56,true,C.navy);
 text(s,'An Offline Study of Controllability',69,325,1120,65,36,false,C.ink);
 text(s,'Vibhor Malik\nM.Sc. in Applied Computing, BCIT\nSupervisor: Borna Noureddin',70,466,1100,133,28,false,C.muted);
 text(s,'Research review. Proposal approval remains pending.',70,651,1050,28,21,false,C.muted);
 s.speakerNotes.textFrame.setText('Timing: 45 seconds. Introduce the exact submitted-proposal title and the project question. This presentation accompanies the COMP 9500 research artifact and manuscript. Explain that the system translates written category preferences into commands around a fixed sequential recommender. The study separates whether a model understands a command from whether a ranking policy applies it. This is a review deck in a provisional academic design because the official BCIT presentation template has not been supplied. Transfer the content to that template before the assessed presentation. Do not describe this design as the official BCIT template. AI agents wrote code, executed preprocessing, training, LLM evaluation and analysis, and drafted the manuscript and slides. The supplied proposal form has no signatures, no research path selection and no approval selection. The completed artifact remains subject to supervisor scope acceptance. The student should acknowledge assistance according to course policy and be able to explain the work. The main talk is planned for approximately 24 minutes, followed by the course\'s 10–15 minutes of questions.');
}
// 2
{
 const s=slide('Explicit control over a recommendation feed','Timing: 75 seconds. Begin with the difference between feedback on one item and an instruction about a category. A thumbs-down action can mean many things: disliking the video, its creator, its topic or its presentation. A written request can express a broader instruction, but it introduces a translation problem. Mozilla\'s 2022 audit motivated interest in stronger control. Its 22,722 volunteers and less-than-half prevention result are historical platform evidence, not present-day measurements or the performance of this artifact. The project does not recreate YouTube or TikTok. It uses a documented short-video dataset to study a narrow computational question. Make the role of explanations distinct: they can expose a signal but cannot change an offline ranking when no user acts on them. Source: https://www.mozillafoundation.org/en/research/library/user-controls/report/');
 text(s,'“Show me more category_12”',72,187,1100,85,42,true,C.blue);
 prose(s,['An item reaction and a category request convey different information.','A language interface must identify the intended change and apply it consistently.'],318);
 foot(s,'Opaque category labels preserve the dataset’s actual metadata.');
}
// 3
{
 const s=slide('Research question','Timing: 75 seconds. Read the question and then explain its two measurable components. The parser must return the correct operation and category. Once the command is valid, the ranking policy must alter exposure consistently. The study also measures next-item prediction as a limited quality indicator. These components prevent a hard filter\'s expected success from being attributed entirely to an LLM. Explain the scope clearly: requests are synthetic assignments drawn from prior history, not observed human wishes. No human participants react to the interface. The benchmark therefore cannot measure satisfaction, agency or usability. The contribution is a reproducible applied system with explicit information boundaries and recorded failures. Source: project manuscript, Sections I and III.');
 text(s,'How reliably can a local language model\ncompile category controls?',72,184,1100,136,42,true,C.navy);
 text(s,'What changes in exposure and next-item accuracy\nfollow from those controls?',72,362,1100,136,38,false,C.ink);
 foot(s,'Offline evaluation with synthetic requests and a frozen recommender');
}
// 4
{
 const s=slide('Research context','Timing: 75 seconds. This is a focused review rather than a claim to exhaust the field. Niu combines conversational control and explanation in a short-video interface. Ramos demonstrates editable natural-language profiles. Lu learns controllable LLM recommendation using SASRec-derived supervision, so it should not be described as merely training category weights inside SASRec. Dai uses learned control tokens for reranking and recognizes compliance–utility trade-offs. Fabbri\'s 2026 integrated short-video system further narrows any novelty claim. Our contribution is a controlled, reproducible evaluation around a shared policy, not the first multi-channel interface. The proposal\'s incomplete Shu 2024 citation could not be verified and is excluded. Zhou, Dai and Joachims 2024 is a separately verified related profile paper. Sources: https://commons.clarku.edu/faculty_computer_sciences/242/ ; https://aclanthology.org/2024.acl-long.753/ ; https://aclanthology.org/2024.acl-long.443/ ; https://arxiv.org/abs/2511.17913 ; https://doi.org/10.1016/j.ijhcs.2026.103811');
 table(s,[['Work','Relevant mechanism'],['Niu et al., 2025','Conversational short-video control and explanations'],['Ramos et al., 2024','Editable natural-language profiles'],['Lu et al., 2024','LLM alignment for category control'],['Dai et al., 2025','Learned control tokens for reranking'],['Fabbri et al., 2026','Transparent, controllable short-video interface']],[345,807],168,421,25);
 foot(s,'Contribution: a reproducible comparison under one control policy');
}
// 5
{
 const s=slide('KuaiRec study cohort','Timing: 75 seconds. Distinguish source-wide counts from the filtered study. The official small matrix contains 1,411 users and 3,327 videos, but missing timestamps, positive-feedback filtering and temporal eligibility reduce the experimental cohort. The prepared file has '+n(dm.selected_users)+' users and '+n(dm.candidate_items)+' candidates. Watch ratio greater than 2 is an engagement proxy. KuaiRec does not contain observed like labels. Excluding missing times avoids invented chronology. Restricting items to pre-cutoff positive observations prevents future-only catalog items from entering the candidate set. Eligibility requires at least three training, two request-history and one final evaluation event. All eligible users are included in the main study. Describe the limitation: results generalize to this active, filtered cohort under this threshold, not every platform user. The candidate policy retains seen items, but the processed cohort contains no repeated training items and no test positives previously seen in train plus request history. This is a policy choice, not evidence of observed repeat engagement. Post-cutoff item filtering excludes 43,708 positive events and retains 16,374 request-history and test events. Source: data/processed.json metadata and https://github.com/chongminggao/KuaiRec');
 table(s,[['Study quantity','Observed count'],['Eligible users',n(dm.selected_users)],['Candidate videos',n(dm.candidate_items)],['Training positive events',n(dm.split_event_counts.train)],['Request-history positive events',n(dm.split_event_counts.request_history)],['Evaluation positive events',n(dm.split_event_counts.test)]],[800,352],170,411,27);
 foot(s,'Positive event: watch ratio > 2.0. The candidate set retains previously seen items.');
}
// 6
{
 const s=slide('Chronological separation','Timing: 75 seconds. Explain the three windows and why the middle window exists. Shared timestamp boundaries apply across users, avoiding a model that learns another user\'s future interactions. The first window fits model parameters. The next window can inform the current user context and request construction without being used for gradients. The last window supplies the first eligible next-item label. A request never uses that final label. The nominal 70/15/15 split refers to all dated source events. It does not imply the same percentages after filtering to watch ratio greater than 2. Request categories are assigned reproducibly from earlier category support, instead of being selected from held-out category shifts. Mutating the final test labels should leave generated requests and pre-evaluation scores unchanged. Source: feedctrl/data.py and feedctrl/evaluation.py. Background: https://arxiv.org/abs/2010.11060');
 table(s,[['Window','Permitted use','Excluded use'],['First 70% of dated events','Fit recommender parameters','Future labels'],['Next 15%','Construct requests and inference history','Gradient updates'],['Final 15%','Score held-out next item','Choose request or prompt']],[375,398,379],190,299,28);
 foot(s,'A separate request window prevents outcome-derived control requests.');
}
// 7
{
 const s=slide('Working research prototype','Timing: 75 seconds. This is an actual screenshot of the local prototype using prepared KuaiRec data and a trained checkpoint. Point to the five conditions, the free-text control and the metadata recommendation cards. The screenshot captures user 14 in condition E using a trained SASRec checkpoint and the rule-parser diagnostic. All ten baseline cards display cached LLM verified facts from the historical explanation cache. This screenshot run did not execute fresh LLM calls. Actual Llama experiments are reported separately. The app lets a user choose a condition, change category preferences, edit a profile and inspect the recommendation list. FastAPI applies bounded schema validation and the shared policy. The interface represents item metadata rather than playable original videos. On a live demo, show a mute, inspect the target category, then reset and confirm the original order returns. Software acceptance checks include state isolation and label visibility. The screenshot provides evidence of implementation, not proof of human usability. Source image: results/audit_revision/verification/app-presentation.png, captured from the local application.');
 s.images.add({blob:await fs.readFile(path.join(workspaceDir,'results/audit_revision/verification/app-presentation.png')),contentType:'image/png',alt:'Actual Feed Control prototype with condition selector, command input and recommendation metadata cards',fit:'contain',position:{left:208,top:152,width:864,height:450}});
 foot(s,'Actual application. Rule-parser diagnostic with previously cached LLM explanations.');
}
// 8
{
 const s=slide('Frozen recommender configuration','Timing: 75 seconds. Explain that the network is a compact, independently implemented SASRec-style backbone rather than an exact reproduction claim. Item and positional embeddings feed causal attention. Training uses a sampled logistic objective, one negative per valid timestep and only training information for negative exclusion. The 20 fixed epochs and three seeds were chosen before examining test outcomes, after a small setup run showed affordable runtime. Do not call fixed epochs convergence. All conditions within each seed share the same checkpoint and candidate scores. The goal is to compare control paths under a fixed base, not to establish a new best recommender. Source: results/main-run-design.json and results/models metadata. SASRec: https://arxiv.org/abs/1808.09781');
 table(s,[['Setting','Value'],['Hidden dimension / attention blocks','32 / 2'],['Attention heads / context length','1 / 50 items'],['Dropout / learning rate','0.2 / 0.001'],['Epochs / batch size','20 / 64'],['Training seeds','42, 43, 44']],[740,412],174,415,28);
 foot(s,'Fixed before outcome analysis. No convergence or state-of-the-art claim.');
}
// 9
{
 const s=slide('Five matched configurations','Timing: 75 seconds. Explain every condition explicitly. A boosts or removes a single recent historical item in the requested category. B adds displayed explanation text to A. C parses a free-text command. D parses equivalent preference wording into a profile. E combines text, profile and explanations with a same-category overwrite rule, so duplicated instructions do not double the effect. The item baseline has lower information granularity than a category request, which limits attribution of gains to the LLM. These are five matched configurations, not the eight combinations of a complete three-factor experiment. B must equal A because nobody responds to an explanation in this offline study. C, D and E can also match whenever they compile the same command. That equality establishes consistency, not equal usability. Main ranking experiments use verified policy-template explanations. A separate demonstration generated ten actual Llama fact selections for one user’s baseline items, with no recorded errors and all selected statements inside the verified allowed set. Every one of these ten outputs exactly matches the first three facts selected by the deterministic template. This demonstrates no observed benefit from LLM fact selection in the ten-item sample, and does not imply fresh generation for every card. Source: feedctrl/evaluation.py, feedctrl/controls.py and results/explanations.json.');
 table(s,[['Condition','Mechanism'],['A','Simulated feedback on one historical item'],['B','A with grounded explanation text'],['C','Parsed free-text category command'],['D','Parsed editable preference profile'],['E','Text, profile and explanations combined']],[240,912],170,410,28);
 foot(s,'All 10 cached LLM explanations equal the first three template facts.');
}
// 10
{
 const s=slide('Shared command semantics','Timing: 75 seconds. Use the displayed request as an illustrative schema example, not a claim about a particular observed user. The parser returns an operation, a valid category identifier and a strength. A boost adds 0.25 to normalized scores of matching items. A mute removes all matching items and never pads the feed with forbidden videos. The same intent receives the same ranking policy whether it arrives through a message or profile. A new explicit instruction for the same category takes precedence in the combined ranking; the saved profile remains unchanged for the profile-only condition. Different categories can coexist. The intended policy requests clarification for unsupported or ambiguous text; the measured parser does not always comply. Operational failures remain errors. State reset and cross-user isolation need functional tests beyond one-turn ranking. Source: feedctrl/controls.py.');
 text(s,'Request',70,180,1080,42,28,true,C.muted);
 text(s,'Show more category_12',70,232,1080,80,40,true,C.navy);
 text(s,'Validated command',70,365,1080,42,28,true,C.muted);
 text(s,'operation: boost\ncategory: category_12\nstrength: 0.25',70,419,1080,146,31,false,C.ink);
 foot(s,'Equivalent text and profile intent use the same score adjustment.');
}
// 11
{
 const s=slide('Evaluation measures','Timing: 75 seconds. TCP and TCER use the same count over ten slots but the desired direction changes by request type. A multi-tag item counts at most once for the target category. Fill rate is essential because an empty list trivially has zero forbidden exposure. Conditional exposure over the returned list is also stored. HR at one checks the first eligible held-out positive item, rather than any future item. This is a narrow predictive metric and the historical label was generated before the synthetic command existed. Parser exact-match accuracy checks the full intended command, including operation, category and strength, and operational errors remain in its denominator. Each metric answers a different question, so no single score certifies overall usefulness. Source: feedctrl/evaluation.py, parser rubric and https://aclanthology.org/2024.acl-long.443/');
 table(s,[['Measure','Meaning'],['TCP@10','Target-category items / 10 after a boost'],['TCER@10','Target-category items / 10 after a mute'],['Fill rate','Returned items / 10'],['HR@1','First recommendation equals next held-out item'],['Parser accuracy','Correct full command / all test cases']],[330,822],172,414,26);
}
// 12
{
 const s=slide('Verification and uncertainty','Timing: 75 seconds. The unit of inference is the user. Requests and training seeds repeat within users and are averaged before paired analysis. Bootstrap resampling preserves those clusters. Six primary comparisons cover C, D and E against A for positive and negative exposure. Wilcoxon uses Pratt zero handling with a tie-aware approximation, and Benjamini–Hochberg adjustments accompany the exploratory p-values. The system also records an exchangeability-dependent sign-flip sensitivity check. A/B equality is a code assertion, not a hypothesis test. The proposal says within 10% without specifying absolute or relative units. The original analysis used absolute 0.10. The audit supplement reports both readings, with the same pooled users, requests, seeds and Bonferroni rule. Neither interpretation has documented supervisor approval. Never interpret nonsignificance as proof of equal quality. Software tests cover specific failure modes; they do not validate genuine user intentions. Sources: feedctrl/evaluation.py; https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html ; https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html');
 table(s,[['Check','Evidence sought'],['Information isolation','Test-label changes leave requests unchanged'],['Policy correctness','Mute safety, stable order and reset behavior'],['Matched comparisons','Same users, candidates and frozen scores'],['Uncertainty','Paired user analysis, with dependencies disclosed']],[420,732],184,342,27);
 foot(s,'Requests and seeds do not increase the number of independent users.');
}
// 13
{
 const p=evidence.parser;
 const s=slide('Local-model parser results','Timing: 75 seconds. The frozen 100-case suite yields 79 correct full commands, below the prespecified 85% point-estimate target and above the proposal’s 70% degradation floor, with a 95% Wilson interval of 70.0% to 85.8%. All 70 supported boost, mute and reset cases are correct, but only 9 of 30 required clarification cases are correct. Seven errors are grounding-validation rejections and 14 are valid but incorrect commands. These are not seven network outages. Separate this final suite from the development examples. Shared templates and synthetic labels restrict generalization. Caching repeated evaluation requests can reduce compute but does not create new language evidence. A target point estimate of 85% is distinct from a confidence lower bound of 85%. Review failures by type, especially ambiguous negation, unsupported multiple requests and unknown categories. Ambiguous cases score 7/20 and adversarial cases 2/10. The 85% target appears in Objective 3 and Expected Outcomes of the supplied proposal, which also declares parser accuracy below 70% as degraded control channels. This observed 79% clears that point-estimate floor without meeting the target. Do not replace failed local calls with a rule answer. All measured values on this slide come from the saved parser benchmark and its case-level log. The interrupted run resumed using 96 recorded case outputs and four remaining calls; cached evaluation time must not be interpreted as inference latency. Sources: results/parser_ollama_test/summary.json and its predictions; interrupted records are retained separately.');
 if(p){table(s,[['Measure','Measured result'],['Correct / test cases',`${p.correct} / ${p.total}`],['Exact-match accuracy',pct(p.accuracy)],['95% Wilson interval',`${pct(p.ci[0])} to ${pct(p.ci[1])}`],['Supported commands','70 / 70'],['Ambiguous / adversarial cases','7 / 20 and 2 / 10']],[695,457],174,414,27);foot(s,p.note||`85% target ${p.accuracy>=.85?'met':'not met'}. Frozen synthetic test suite; development cases excluded.`);}
 else prose(s,['The local-model test is running.','Only saved, checked outcomes will populate this slide.','Rule-parser results remain a separate diagnostic.']);
}
// 14
{
 const a=evidence.aggregate;
 const s=slide('Category exposure after control','Timing: 75 seconds. Explain the direction of each series before reading values: boosts seek higher target exposure, mutes seek lower target exposure. The bars summarize the same user cohort with training seeds averaged within each user. C, D and E technically support the proposal hypothesis of higher TCP and lower TCER versus A under Wilcoxon with Benjamini–Hochberg adjustment. This should be interpreted as evidence of policy enforcement. The hard mute structurally removes target exposure for correctly parsed requests, while a positive category bonus favors the requested category by design. The rule parser produces identical results, so this does not establish an LLM advantage. Statistical significance itself is data dependent, rather than mathematically guaranteed by the policy. Their uncertainty belongs to paired differences and appears in the manuscript. A and B are expected to match exactly. C, D and E match exactly, as do the separately executed rule counterparts; the shared enforcement policy explains that result. All 120 unique canonical inputs from four templates compile correctly: 60 text commands and 60 equivalent profile statements, covering 30 categories per operation and 31 distinct categories across operations in each channel. This narrow template result does not contradict the broader 79/100 parser result. Zero mute exposure follows from a correctly parsed hard filter and should not be described as a newly learned intelligent capability. Fill rate must accompany exposure to rule out an empty-feed shortcut. This figure uses the actual Llama run. All lists remain fully filled. The positive paired change is 67.607 percentage points with 95% user-bootstrap interval 65.788 to 69.438, while the negative change is minus 6.112 points with interval minus 7.056 to minus 5.241. Source: the exact saved aggregate identified in slides/evidence.json.');
 if(a){chart(s,['A','B','C','D','E'],[{name:'Positive request: TCP@10',values:['A','B','C','D','E'].map(c=>a.descriptive[c].boost.target_proportion),fill:C.blue},{name:'Negative request: TCER@10',values:['A','B','C','D','E'].map(c=>a.descriptive[c].mute.target_proportion),fill:C.teal}]);foot(s,'Full lists. Primary hypothesis supported within this policy. Rules yield identical rankings.');}
 else prose(s,['Main evaluation results are pending verification.','The final chart will show positive and negative requests separately.','Every condition will use the same candidate scores.']);
}
// 15
{
 const b=evidence.baselines;
 if(!b) throw Error('Audit baseline evidence is required');
 const s=slide('Simple baselines expose weak prediction','Timing: 85 seconds. All rows use the same 865 users, 2,593 candidates and first eligible test positive. Uniform random is an analytic expectation, not a sampled run. Train-window popularity uses only training positives. Recent popularity pools all users’ request-window positives, which supplies newer item-level aggregate information than the frozen SASRec parameters. SASRec receives request-history items as inference context but does not update its item parameters from those events. Therefore recent popularity is a diagnostic with different information access, not a fully matched architecture comparison. Its strong result motivates a future development cycle. Do not retune on these exposed test labels. Frozen SASRec seeds predict only zero, three and four correct top items. Their dominant item reaches 73.9% to 96.2% of users. The boost condition lowers NDCG@10 from 0.03012 to 0.01637, about 45.7%. The paired difference and interval are reported as post hoc supplementary analysis in the paper. This evaluates historical next-item recovery after a synthetic control, rather than actual satisfaction. Sources: results/audit_revision/baselines.json, results/base-quality.json and results/audit_revision/analysis-v1.json.');
 table(s,[['Reference','HR@1','NDCG@10'],...b.rows.map(r=>[r.label,pct(r.hr1,3),dec(r.ndcg_at_10,5)])],[625,250,277],172,370,26);
 text(s,'Boost NDCG@10: 0.03012 to 0.01637 (45.7% lower)',70,559,1120,40,27,false,C.ink);
 foot(s,'Recent popularity uses newer aggregate information. All rows share test labels and candidates.');
}
// 16
{
 const ni=evidence.analysis_revision.noninferiority;
 const s=slide('The 10% margin changes the conclusion','Timing: 85 seconds. This is an analysis-only sensitivity report on the frozen outputs. The proposal leaves within 10% ambiguous. The original analysis chose an absolute 0.10 HR@1 margin. The paired statistic pools boost and mute within each of 865 users and averages the three seeds. Its baseline is 0.002504816955684 in proportion units, or 0.25048%. Ten percent of that baseline is 0.000250481695568. The simultaneous lower bound for C, D or E versus A is -0.000770712909441 under the original three-comparison Bonferroni rule. It exceeds -0.10 but falls below -0.000250481695568. Absolute non-inferiority therefore passes mechanically, while relative non-inferiority is not supported. Failure to establish relative non-inferiority is not proof of inferiority. The pooled analysis baseline differs from the boost-only 0.231% value in the external audit. Using the boost-only baseline to set a pooled margin mixes estimands. The absolute margin dwarfs this baseline and even allows loss of all correct hits. This sensitivity holds the observed A baseline fixed to derive the relative margin. It is not a fully ratio-based NI analysis or a prospectively justified margin. Supervisor agreement on a meaningful margin remains required before making a quality-preservation claim. Source: results/audit_revision/analysis-v1.json.');
 text(s,`Pooled A baseline: ${pct(ni.baseline_hr1,5)} HR@1`,70,168,1120,50,30,true,C.navy);
 table(s,[['Reading of “within 10%”','Margin (proportion)','Result for C / D / E'],['Absolute proportion','0.100000','Mechanical pass'],['Relative to pooled A','0.00025048','Not supported']],[530,250,372],253,242,26);
 text(s,'Bonferroni-adjusted lower bound: −0.00077071',70,532,1120,46,28,false,C.ink);
 foot(s,'Bounds use proportion units. The absolute pass does not establish useful quality preservation.');
}
// 17
{
 const s=slide('Experiment 1: concrete conclusion','Timing: 85 seconds. Read the five findings in order. Enforcement is supplied by the policy: hard exclusion guarantees zero target exposure, while the observed boost increase follows the fixed score adjustment and is not a universal strict-increase guarantee. Parser performance clears the 70% floor but misses the 85% target. Broader language is author-generated synthetic language, not spontaneous user speech. All ten explanations equal the template. Quality decreases on boosts and the absolute NI margin is uninformative. The recency comparison is descriptive and uses pooled recent history. Sources: results/audit_revision/analysis-v1.json and baselines.json, results/parser_ollama_test/summary.json and results/explanations.json.');
 table(s,[['Finding','Observed evidence'],['Policy enforcement','TCP 11.6% to 79.2%; TCER 6.1% to 0. Built into policy.'],['Language parsing','120/120 templated; 79/100 broader; 2/10 adversarial.'],['Explanations','10/10 equal the template. No observed LLM advantage.'],['Quality cost','Boost NDCG down 45.7%; NI check uninformative.'],['Weak backbone','HR@1 0.0 to 0.46% versus recency popularity 8.0%.']],[300,852],165,432,24);
 foot(s,'Mechanical control works. LLM advantage, naturalness and useful quality preservation are unestablished.');
}
// 18
{
 const s=slide('Experiment 2: richer intent in one interaction','Timing: 75 seconds. Prospective protocol, not results. H1 compares LLM intent satisfaction with both one item reaction and an extended rule parser. H2 compares intended-direction rank movement per interaction with one thumb. H3 describes paired quality changes without NI. Primary satisfaction requires a top-ten band plus strictly positive intended movement. Already satisfied and impossible requests are flagged and retained. Both parsers use the same ranker. Source: docs/experiment2-protocol.md.');
 table(s,[['Intent class','Example meaning'],['Two categories','More X and less Y'],['Graded','A bit more X, much less X, or none of X'],['Nonzero floor','Less X, while keeping at least one'],['Conditional scope','Boost X only when the item also has Y']],[365,787],183,352,27);
 foot(s,'One interaction each. Same ranker. The rule comparator tests whether the LLM adds value.');
}
// 19
{
 const s=slide('Experiment 2: reserved evaluation pending','Timing: 75 seconds. Forty-eight development and one hundred reserved cases span all 31 opaque categories. The student must independently annotate the test text without first-author gold or model output. No AI pass substitutes and no agreement number is invented. Frozen parser hashes precede test opening. Parser accuracy must be reported before rankings. The three seeds are averaged within user; eleven hypotheses receive BH correction. Windows and Colab execution remain unverified. Supervisor approval, official template and the Experiment 1 NI margin reading remain external decisions. Source: docs/experiment2-protocol.md and results/experiment2/summary.json.');
 table(s,[['Question','Current evidence status'],['H1: intent satisfaction','Not assessed. Reserved test has not run.'],['H2: movement per interaction','Not assessed. Reserved test has not run.'],['H3: quality cost','Descriptive analysis pending. No NI claim.'],['Student annotation','Pending. Inter-annotator agreement unavailable.']],[470,682],178,359,26);
 foot(s,'A clean negative result will be reported. Software tests cannot substitute for the reserved experiment.');
}
// 18
{
 const s=slide('Discussion','Timing: Q&A, 10–15 minutes after the main presentation. The main talk targets approximately 24 minutes. Likely questions: Why use watch ratio greater than 2? Explain the operational threshold, lack of explicit likes and need for sensitivity analysis. Why retain seen candidates? Explain the frozen candidate policy and disclose that the derived positive cohort has no observed repeat items. Why do explanation rankings match? Nobody acts on the text in offline evaluation. Why might C, D and E match? They share validated commands and deduplicated enforcement. What does a perfect mute mean? It confirms filtering when the correct target is known. How do you avoid leakage? Global time boundaries, separate request history and invariance tests. Why does non-inferiority need caution? The absolute reading passes mechanically, while the relative reading is not supported under the original simultaneous confidence rule. What remains before assessment? Student verification, signed scope acceptance and research path confirmation, supervisor methodological agreement, official slide template and actual presentation. Refer to saved artifacts for exact values and acknowledge limits rather than speculate.');
 text(s,'Language parsing, control policy\nand recommendation utility',72,200,1100,165,46,true,C.navy);
 text(s,'Which evidence should guide the next iteration?',72,438,1100,100,34,false,C.ink);
 foot(s,'Code, raw outcomes, manuscript and reproducibility instructions accompany this deck.');
}
await fs.mkdir(TMP_DIR,{recursive:true});
const candidatePath=path.join(TMP_DIR,'candidate.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
await fs.writeFile(path.join(TMP_DIR,'slides.inspect.ndjson'),(await presentation.inspect({kind:'slide,textbox,table,chart,notes',maxChars:500000})).ndjson);
for(let i=0;i<presentation.slides.items.length;i++){
 const s=presentation.slides.items[i];
 const preview=await presentation.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(TMP_DIR,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await preview.arrayBuffer()));
}
const finalPath=process.env.CMP_FINAL_PPTX || process.env.CMP_DRAFT_PPTX || path.join(workspaceDir,'slides/output/audit-revision-review.pptx');
await fs.mkdir(path.dirname(finalPath),{recursive:true});
const result=await finalizePresentation({
 workspaceDir,candidatePath,finalPath,pythonExecutable:RUNTIME_PYTHON,
 integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...tableSlides.flatMap(v=>['--require-native-table-slide',String(v)])],
 explicitTotalSlideCount:20,requiredNativeTableOwnerSlides:tableSlides,requiredNativeChartOwnerSlides:chartSlides,
 materializeLiteralChartWorkbooks:true,
 fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
 receiptPath:process.env.CMP_PRESENTATION_RECEIPT || path.join(TMP_DIR,`${path.basename(finalPath)}.validation.json`)
});
console.log(JSON.stringify({finalPath,slideCount:presentation.slides.items.length,tableSlides,chartSlides,result}));
