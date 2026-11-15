import React, {useEffect, useRef, useState} from 'react';
import ReviewBoard, {definitionEvidence} from './ReviewBoard.jsx';
import {actionWords, adoptText, changeRecord, exampleOptions, outcomeView, plural, REVIEW_MARGIN_SECONDS, REVIEW_SECONDS, scopeChoices, sourceWords, stageOfFailure, stageStates} from './reviewModel.js';

export {definitionEvidence};

// One workflow for every language control: request, interpretation, evidence,
// preview, apply, undo. The panel holds the request and the state. The review
// board shows each result in three blocks (what came back, application checks,
// your decision). `portal` and `reviewHost` let the page place the board in the
// wide results area; without them the board renders below the panel.

const METHODS = [
  // [value, name without its source, needs a provider, text after the source]
  ['manual_category', 'Existing category (manual, no model)', false, ''],
  ['vocabulary', 'My request, matched to existing categories and tags', true, ''],
  ['combined', 'My mixed request, matched to descriptions, categories and tags', true, ''],
  ['configured_model', 'My request, matched to item descriptions', true, ''],
  ['staged', 'A new category from my description', true, ', in stages'],
  ['ollama', 'My request, matched to item descriptions', true, ''],
  ['induction', 'A new category in one call (earlier method)', true, ''],
];
const METHOD_HELP = {
  manual_category: () => 'No model. You choose an existing category and an action. The application selects the items of that category in the evidence scope.',
  vocabulary: w => `One ${w.call}. ${w.The} gives the direction and strength of your request and chooses existing category and tag names. The application then selects the items that carry those names. One request can hold several preferences.`,
  combined: w => `One ${w.call} proposes up to four preferences using captions, cover text, categories and tags together. Review every selected item and quotation; Apply and Undo change the whole plan together. Nothing is silently applied.`,
  configured_model: w => `Two ${w.call}s at most. The first gives the direction and strength of your request. The second selects items and cites a quotation from each one. An unclear request or an invalid quotation applies nothing. There is no rule-based fallback.`,
  ollama: () => 'Two model calls at most, on the local model, with 90 seconds for each call. Call 1 reads the direction and strength. Call 2 selects items and cites a quotation from each one. An unclear request or an invalid quotation applies nothing. There is no rule-based fallback.',
  staged: w => `Three ${w.call}s at most. The first proposes a definition, and you review it. The second classifies every item in the scope. The third assesses the evidence without the classifications. Where the two disagree, the item gets no decision and is not selected. ${w.authored ? '' : 'The calls can use the same model, and both can be wrong. '}You choose the direction and strength below.`,
  induction: () => 'One model call proposes a name, a definition and a decision for every item in the scope. You choose the direction and strength below. The staged method gives a separate evidence assessment; this earlier method does not.',
};
const LIMITS = 'Limits: at most 8 applied controls; at most 4 controls in one request; a review is valid for five minutes; Undo goes back at most 10 changes.';

// Timers of the browser. Tests pass their own, so that no real clock runs there.
const browserTimers = {
  now: () => Date.now(),
  later: (work, wait) => { if (typeof window === 'undefined') return () => {}; const id = window.setTimeout(work, wait); return () => window.clearTimeout(id); },
  every: (work, wait) => { if (typeof window === 'undefined') return () => {}; const id = window.setInterval(work, wait); return () => window.clearInterval(id); },
};

export default function SemanticPanel({api,user,resetKey,onFeed,onActive,onUnavailable,scenarioRequests,categories=[],defaultOpen,portal,reviewHost,provider,dataNote,timers=browserTimers}) {
  const [open,setOpen]=useState(Boolean(defaultOpen)),[saved,setSaved]=useState(null),[pending,setPending]=useState(null);
  const [text,setText]=useState(''),[typedLabel,setTypedLabel]=useState(null),[count,setCount]=useState(10);
  const [backend,setBackend]=useState('manual_category'),[category,setCategory]=useState('');
  const [operation,setOperation]=useState('boost'),[strength,setStrength]=useState('standard'),[mode,setMode]=useState('merge');
  const [actionSource,setActionSource]=useState('ollama');
  const [definition,setDefinition]=useState(null),[evidenceReviewed,setEvidenceReviewed]=useState(false);
  const [working,setWorking]=useState(false),[message,setMessage]=useState('');
  const [clarification,setClarification]=useState(null);
  const [resolution,setResolution]=useState(null),[resolutionChoice,setResolutionChoice]=useState('');
  const [explicitTarget,setExplicitTarget]=useState(false),[target,setTarget]=useState(''),[targetConfirmed,setTargetConfirmed]=useState(false);
  const [targetSignature,setTargetSignature]=useState(null);
  // A result that proposes no change, a failed request, and the record of the last applied change.
  const [outcome,setOutcome]=useState(null),[failure,setFailure]=useState(null),[record,setRecord]=useState(null),[recordFresh,setRecordFresh]=useState(false);
  const [busyStage,setBusyStage]=useState(null),[busyCall,setBusyCall]=useState(false),[stoppedStage,setStoppedStage]=useState(null),[terms,setTerms]=useState(null),[termsError,setTermsError]=useState('');
  // The time at which the open review ends, whether it has ended, the seconds of a running call, and a counter that moves focus to a new result.
  const [deadline,setDeadline]=useState(null),[expired,setExpired]=useState(false),[elapsed,setElapsed]=useState(0),[focusKey,setFocusKey]=useState(0);
  // A field that changed outside the view of the person: bring it into view after the next render.
  const [fieldFocus,setFieldFocus]=useState(null);
  // Until the person types a name, the control is named after what it does.
  const label=typedLabel!==null?typedLabel:backend==='manual_category'?`Manual: ${category}`:'My request';
  const setLabel=setTypedLabel;
  const currentTargetSignature=JSON.stringify([user,backend,text,target,count,operation,operation==='exclude'?'none':strength,mode]);
  const confirmedNow=targetConfirmed&&targetSignature===currentTargetSignature;
  // `generation` cancels a review that is in flight when an input changes. The first load of the
  // applied controls has its own counter, so that a default value set during the load does not discard it.
  const generation=useRef(0),activeRequest=useRef(null),termsRequest=useRef(0),loadRequest=useRef(0);
  // `notice` is a message that the next change of an input shows in place of the plain "changed" message.
  const reviewOpen=useRef(false),mounted=useRef(false),notice=useRef(null);
  reviewOpen.current=Boolean(pending||definition||resolution);
  const authored=provider?.live_model===false,words=sourceWords(authored);
  const choices=scopeChoices(saved?saved.feed.baseline_items.length:10);
  const local=saved?.local_models_allowed!==false,modelMethod=backend!=='manual_category';
  // Authored replies exist for the complete bundled scope only.
  const scope=authored&&modelMethod?10:count;
  const scopeKey=saved?saved.feed.baseline_items.slice(0,scope).join(','):'';
  function clearReview(){setPending(null);setDefinition(null);setEvidenceReviewed(false);setResolution(null);setResolutionChoice('');setClarification(null);setDeadline(null);setExpired(false);}
  useEffect(()=>{++generation.current;const id=++loadRequest.current;activeRequest.current=null;clearReview();setSaved(null);
    setExplicitTarget(false);setTargetConfirmed(false);setMessage('');setWorking(false);setOutcome(null);setFailure(null);setRecord(null);setRecordFresh(false);setBusyStage(null);setStoppedStage(null);
    if(open&&user!==null){setWorking(true);api(`semantic/groups?user_id=${user}`)
      .then(r=>{if(id===loadRequest.current){setSaved(r);onFeed(r.feed,r.groups);}})
      .catch(e=>{if(id===loadRequest.current){setMessage(e.message);if(onUnavailable)onUnavailable(e.message);}})
      .finally(()=>{if(id===loadRequest.current)setWorking(false);});}
  },[user,resetKey,open]);
  // Which methods this server offers. With no provider at all the model methods stay visible, disabled, with the reason.
  const offered=saved?{manual_category:true,vocabulary:Boolean(saved.external_adapter_available),combined:Boolean(saved.external_adapter_available)&&!authored,configured_model:Boolean(saved.external_adapter_available),
    staged:Boolean(saved.category_adapter_available)||local,induction:(Boolean(saved.category_adapter_available)||local)&&!authored,ollama:local}:{manual_category:true};
  const noProvider=Boolean(saved)&&!saved.external_adapter_available&&!saved.category_adapter_available&&!local;
  // Leave a method that this server does not offer. Never switch to a model method by itself.
  useEffect(()=>{if(saved&&!offered[backend])setBackend('manual_category');},[saved,backend]);
  // A change of any input ends an open review, because the review belonged to the earlier input. It also removes the earlier message.
  const inputKey=JSON.stringify([backend,text,label,count,operation,strength,mode,actionSource,category,target,explicitTarget]);
  useEffect(()=>{if(!mounted.current){mounted.current=true;return;}
    ++generation.current;activeRequest.current=null;setWorking(false);const had=reviewOpen.current;clearReview();setFailure(null);setRecordFresh(false);setStoppedStage(null);
    setMessage(notice.current||(had?'You changed the request. The review was discarded. Nothing was applied.':''));notice.current=null;},[inputKey]);
  useEffect(()=>{setTargetConfirmed(false);},[backend,text,target,count,operation,strength,mode,explicitTarget]);
  useEffect(()=>{setOutcome(null);},[backend]);
  useEffect(()=>{if(category&&!categories.includes(category))setCategory('');},[categories,category]);
  // The existing categories and tags of the evidence scope. No model call.
  useEffect(()=>{const id=++termsRequest.current;setTerms(null);setTermsError('');
    if(!open||user===null||!scopeKey)return;
    api('semantic/vocabulary/terms',{user_id:user,candidate_ids:scopeKey.split(',').map(Number)})
      .then(r=>{if(id===termsRequest.current)setTerms(r);})
      .catch(e=>{if(id===termsRequest.current)setTermsError(e.message);});
  },[open,user,resetKey,scopeKey]);
  // The seconds of a running call, so that a long wait is visible.
  useEffect(()=>{setElapsed(0);if(!working)return;const started=timers.now();
    return timers.every(()=>setElapsed(Math.floor((timers.now()-started)/1000)),1000);},[working]);
  // The server accepts a review for five minutes. The page marks the review as expired a little earlier.
  useEffect(()=>{if(deadline===null)return;const wait=deadline-timers.now();
    if(wait<=0){setExpired(true);return;}return timers.later(()=>setExpired(true),wait);},[deadline]);
  // After each result, bring the result into view and move focus to its heading.
  useEffect(()=>{if(!focusKey||typeof document==='undefined')return;
    const board=document.getElementById('review-board'),title=document.getElementById('review-heading');
    if(board&&board.scrollIntoView)board.scrollIntoView({block:'start'});
    if(title&&title.focus)title.focus({preventScroll:true});},[focusKey]);
  useEffect(()=>{if(!fieldFocus||typeof document==='undefined')return;const field=document.getElementById(fieldFocus);
    if(field){if(field.scrollIntoView)field.scrollIntoView({block:'center'});if(field.focus)field.focus({preventScroll:true});}setFieldFocus(null);},[fieldFocus]);
  // The server states how long it accepts a review (`review_window_seconds`); the page ends a little earlier.
  const arm=answer=>{const seconds=Number.isFinite(answer?.review_window_seconds)&&answer.review_window_seconds>REVIEW_MARGIN_SECONDS?answer.review_window_seconds:REVIEW_SECONDS;
    setDeadline(timers.now()+(seconds-REVIEW_MARGIN_SECONDS)*1000);setExpired(false);};
  const shown=()=>setFocusKey(n=>n+1);
  function fail(e,stage){
    const kind=e?.kind==='session'||e?.kind==='network'?e.kind:undefined;
    setFailure({message:e.message,kind,request_text:modelMethod?text:undefined});setStoppedStage(stage);
    setMessage(kind==='session'?'The session has ended. Reload the page.':kind==='network'?'The page cannot reach the server.':'The request failed. Nothing was applied. See the message in the result.');shown();}
  // `call` is true when the step can call the provider: only then the page shows the waiting time and "Stop waiting".
  async function run(work,keepClarification=false,stage=null,call=false){
    if(activeRequest.current)return;
    const request=Symbol(),id=generation.current;activeRequest.current=request;setWorking(true);setMessage('');setFailure(null);setBusyStage(stage);setBusyCall(call);setStoppedStage(null);
    if(onActive)onActive();
    if(!keepClarification){setClarification(null);setResolution(null);setResolutionChoice('');}
    // An error answer that carries a structured result (outcome_source) is a result without a change, not a crash.
    try{await work(id);}catch(e){if(id===generation.current){if(e?.payload?.outcome_source)stopped(e.payload,stage);else fail(e,stage);}}
    finally{if(activeRequest.current===request)activeRequest.current=null;if(id===generation.current)setWorking(false);}}
  // The person stops waiting. The call can still finish on the server; this page discards its result.
  function stopWaiting(){if(!activeRequest.current)return;++generation.current;activeRequest.current=null;setWorking(false);
    setMessage(`You stopped waiting. The ${words.call} can still finish on the server. This page discards its result. Nothing was applied.`);}
  async function load(id){const r=await api(`semantic/groups?user_id=${user}`);
    if(id===generation.current){setSaved(r);return r;}}
  // A result without a proposal. `stage` is the stage in which the request ended.
  function stopped(p,stage,lost){const result={...p,method:backend,status:p.status||'clarify',request_text:backend==='manual_category'?`category ${category}`:text,lost:lost||(p.definition_consumed?'The definition that you approved is used up. To try again, press "Propose a definition for review" again.':undefined)};
    setOutcome(result);setStoppedStage(p.failed_stage?stageOfFailure(p.failed_stage,stage||'Interpretation'):stage);setMessage(`${outcomeView(result,words).heading}. Nothing was applied. See the result.`);shown();}
  // The server no longer accepts a review: it is older than five minutes, or a newer request replaced it.
  function expiredNow(stage,reason){clearReview();setOutcome({page:'expired',status:'expired',reason,method:backend,request_text:modelMethod?text:undefined});setStoppedStage(stage);
    setMessage('The review has expired. Nothing was applied.');shown();}
  const isExpiry=e=>/expired|superseded|No matching/i.test(e?.message||'')&&!e?.kind;
  function review(){if(backend==='manual_category'&&!categories.includes(category))return;run(async id=>{clearReview();setOutcome(null);const r=saved||await load(id);if(!r)return;
    const candidate_ids=r.feed.baseline_items.slice(0,scope);
    const common={user_id:user,mode,operation,strength:operation==='exclude'?'none':strength,candidate_ids};
    const p=backend==='staged'?await api('semantic/definition/preview',{...common,objective:text}):
      backend==='induction'?await api('semantic/induction/preview',{...common,objective:text}):
      backend==='combined'?await api('semantic/combined/preview',{user_id:user,text,candidate_ids,mode}):
      backend==='vocabulary'?await api('semantic/vocabulary/preview',{user_id:user,text,candidate_ids,mode}):
      await api('semantic/preview',{...common,text,label,backend,category,
        action_source:explicitTarget?'confirmed':backend==='configured_model'?'model':actionSource,
        ...(explicitTarget?{confirmed_target:target,target_confirmed:confirmedNow}:{})});
    if(id!==generation.current)return;
    if(p.definition_ready){setDefinition(p);arm(p);setMessage('The proposed definition is ready for your review. Nothing is classified or applied.');shown();}
    else if(p.ready){setPending(p);arm(p);setMessage('The review is ready. Nothing is applied yet.');shown();}
    else if(p.resolution_ready){setResolution(p);setResolutionChoice('');setClarification(p.clarification||null);arm(p);
      setMessage('The reply names more than one meaning. Choose in the result. Nothing is approved or applied.');shown();}
    // A second call of the description method belongs to the evidence stage.
    else stopped(p,backend==='manual_category'?'Evidence':(p.calls_attempted>=2||p.action)?'Evidence':'Interpretation');},false,backend==='manual_category'?'Evidence':'Interpretation',backend!=='manual_category');}
  function resolveDefinition(choice){
    if(!resolution||!['review_primary','cancel'].includes(choice)||(choice==='review_primary'&&resolutionChoice!==choice))return;
    run(async id=>{let p;
      try{p=await api('semantic/definition/resolve',{user_id:user,plan_id:resolution.resolution_plan_id,choice});}
      catch(e){if(id===generation.current&&isExpiry(e)){expiredNow('Interpretation',e.message);return;}throw e;}
      if(id!==generation.current)return;
      clearReview();
      if(p.definition_ready){setDefinition(p);arm(p);setMessage('The definition is ready for your review. Nothing is classified or applied.');shown();}
      else if(p.status==='cancelled')setMessage('Category clarification cancelled. Nothing was approved or applied.');
      else stopped(p,'Interpretation');
    },true,'Interpretation');
  }
  function classify(){run(async id=>{let p;
    try{p=await api('semantic/definition/classify',{user_id:user,plan_id:definition.definition_plan_id,evidence_reviewed:evidenceReviewed});}
    catch(e){if(id===generation.current&&isExpiry(e)){expiredNow('Interpretation',e.message);return;}throw e;}
    if(id!==generation.current)return;clearReview();
    if(p.ready){setPending(p);arm(p);setMessage('The review is ready. Nothing is applied yet.');shown();}
    // The approved definition is single use: after a stop here it must be proposed again.
    else stopped(p,'Evidence','The definition that you approved is used up. To try again, press "Propose a definition for review" again.');},false,'Evidence',true);}
  // An explicit rejection of the definition under review. The server forgets the proposal.
  function rejectDefinition(){if(!definition)return;run(async id=>{
    try{await api('semantic/definition/discard',{user_id:user,plan_id:definition.definition_plan_id});}
    catch(e){if(e?.kind)throw e;/* a server without this route, or a review that has already ended: the page forgets the proposal in both cases */}
    if(id!==generation.current)return;clearReview();setMessage('You rejected the definition. Nothing was classified or applied. Change your description to get another definition.');},false,'Interpretation');}
  function history(action){run(async id=>{clearReview();setOutcome(null);const p=await api('semantic/history/preview',{user_id:user,action});
    if(id!==generation.current)return;if(p.ready){setPending(p);arm(p);setMessage(action==='undo'?'The undo review is ready. Nothing is changed yet.':'The review of the removal is ready. Nothing is changed yet.');shown();}
    else setMessage(p.reason||'No earlier state exists.');},false,action==='undo'?'Undo':'Preview');}
  function apply(){run(async id=>{const before=saved,plan=pending;let r;
    try{r=await api('semantic/apply',{user_id:user,plan_id:plan.plan_id});}
    catch(e){if(id===generation.current&&isExpiry(e)){expiredNow(plan.history_action==='undo'?'Undo':'Preview',e.message);return;}throw e;}
    if(id!==generation.current)return;setSaved(r);clearReview();setOutcome(null);onFeed(r.feed,r.groups);setRecord(changeRecord(before,plan,r,new Date(timers.now())));setRecordFresh(true);
    setMessage(plan.history_action==='undo'?'The undo is applied. The earlier feed is restored.':plan.history_action==='clear'?'Every applied control is removed.':'The approved change is applied. The feed shows the result.');shown();},false,'Apply');}
  function discard(){if(activeRequest.current)return;const late=expired;clearReview();setFailure(null);setRecordFresh(false);
    setMessage(late?'The expired review is closed. Nothing was applied.':'Review discarded. Nothing was applied.');}
  // A meaning that the reply named becomes part of the person's own request. Nothing is sent until the person submits it.
  function adoptAlternative(value){if(typeof value!=='string'||!value.trim())return;
    if(backend==='vocabulary'){notice.current='The meaning is added to your request in the panel. Nothing was sent. Submit it when you are ready.';setText(adoptText(text,value));}
    else{notice.current='The meaning is now your stated target in the panel. Confirm it and choose the action. Nothing was sent.';setExplicitTarget(true);setTarget(value);}
    setFieldFocus(backend==='vocabulary'?'semantic-text':'semantic-confirmed-target');}
  function insertExample(option){setText(option.text);if(scenarioRequests?.label&&backend==='configured_model')setLabel(scenarioRequests.label);}
  const disabled=working||user===null;
  const category_method=['induction','staged'].includes(backend);
  const manualAction=backend==='manual_category'||category_method||explicitTarget||(backend==='ollama'&&actionSource==='manual');
  const examples=exampleOptions(scenarioRequests,backend);
  const external=!authored&&(backend==='vocabulary'||backend==='combined'||backend==='configured_model'||(category_method&&saved?.category_adapter_available));
  const variant=resolution?'resolution':definition?'definition':pending?'review':outcome?'outcome':failure?null:record?'changed':null;
  // A result without a change stays on the board while the person rewrites the request; the stage line then shows the first stage again.
  const outcomeNow=outcome&&(outcome.method!==backend?false:!modelMethod||outcome.request_text===text||outcome.page==='expired');
  const history_action=pending?.history_action||'none';
  // A review that the server refused as too old is an expired result, not a plain stop.
  const expiredResult=Boolean(outcomeNow&&outcome?.page==='expired');
  const phase=working?'working':expired&&(pending||definition||resolution)?'expired':(resolution||definition)?'interpretation':pending?'preview'
    :expiredResult?'expired':(outcomeNow||failure)?'stopped':record&&recordFresh?(record.kind==='apply'?'applied':record.kind==='undo'?'undone':'cleared'):'idle';
  const stages=stageStates({method:backend,phase,stage:phase==='working'?busyStage:phase==='expired'?(pending?(history_action==='undo'?'Undo':'Preview'):(definition||resolution)?'Interpretation':stoppedStage):stoppedStage,
    historyAction:history_action,needsInput:Boolean(resolution),canUndo:Boolean(saved?.can_undo)});
  const blocked=pending?.proposal?.target_confirmation&&(!explicitTarget||!confirmedNow)?'This review used a target that you stated. Keep the stated target and its confirmation unchanged to approve.':'';
  const first=saved?.feed.baseline_items||[];
  const context={terms:terms?.terms||pending?.vocabulary?.terms||null,outside:first.slice(scope),
    categories:Object.fromEntries([...(saved?.feed.items||[]),...(pending?.feed.items||[])].map(item=>[item.item_id,item.categories])),
    descriptions:Object.fromEntries((saved?.feed.items||[]).map(item=>[item.item_id,item.source_text]))};
  const deadlineText=deadline===null?'':new Date(deadline).toLocaleTimeString();
  const board=<ReviewBoard variant={variant} failure={failure} method={backend} pending={pending} current={saved} context={context} outcome={outcome}
    definition={definition} resolution={resolution} clarification={clarification} record={record} recordFresh={recordFresh}
    words={words} expired={expired} deadlineText={deadlineText} dataNote={dataNote}
    controls={{disabled,blocked,apply,discard,undo:()=>history('undo'),canUndo:Boolean(saved?.can_undo),resolutionChoice,setResolutionChoice,resolveDefinition,evidenceReviewed,setEvidenceReviewed,classify,rejectDefinition,
      // With authored replies an adopted meaning has no authored reply, so the control would lead to a refusal.
      adoptAlternative:!authored&&['vocabulary','configured_model','ollama'].includes(backend)?adoptAlternative:null,
      alternativeLabel:backend==='vocabulary'?'Add this meaning to my request':'Use this as my stated target'}}/>;
  const termLine=kind=>{const rows=(terms?.terms||[]).filter(kind);return rows.length?rows.map(t=>`${t.value} (${(t.item_ids||[]).length})`).join(', '):'none';};
  const methodName=([value,name,needs,tail])=>!needs?name:value==='ollama'?`${name} (local model ${saved?.configured_model||'not loaded yet'})`
    :value==='induction'?name:`${name}${tail} (${!offered[value]&&noProvider?'needs a model provider':words.suffix})`;
  const waitText=busyCall?`${words.waiting}: ${elapsed} s`:'Working...';
  return <details open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>Change the feed with a reviewed request</summary>
    {open&&<section className="panel" aria-label="Language controls panel" aria-busy={working?'true':'false'}>
      <h3>One control, six stages</h3>
      <ol className="stage-line" aria-label="Stages of this control">{stages.map(s=><li key={s.name} data-state={s.state} aria-current={s.state==='now'?'step':undefined}>
        <span className="stage-name">{s.name}</span> <span className="stage-state">{s.text}</span></li>)}</ol>
      <p className="help">{noProvider?'This server has no model provider. You can choose an existing category by hand.':authored?'This server answers with hand-written replies for the bundled examples. It has no model.':'A model can propose a change.'} The application checks each proposal. You review it. Nothing changes until you approve, and you can undo each change. A control is a named set of existing items with one action. It is not a new video and not a new dataset category. These controls are separate from the conditions A to E and from the earlier topic tool.</p>
      <h3>Request</h3>
      <fieldset id="semantic-backend" className="methods" data-value={backend} disabled={disabled} onChange={e=>{if(!METHODS.some(m=>m[0]===e.target?.value))return;setBackend(e.target.value);setExplicitTarget(false);setTypedLabel(null);}}>
        <legend className="field-label">Method</legend>
        {METHODS.filter(m=>offered[m[0]]||(noProvider&&['vocabulary','combined','configured_model','staged'].includes(m[0]))).map(m=><label key={m[0]} className="method">
          <input type="radio" name="semantic-method" value={m[0]} checked={backend===m[0]} disabled={!offered[m[0]]} onChange={()=>{}}/> {methodName(m)}</label>)}
      </fieldset>
      {noProvider&&<p className="help" data-role="no-provider">This server was started without a model provider. Only the manual category control is available. To use the language methods, start the server with a model route: <code>python scripts/quickstart.py setup</code>, then <code>python scripts/quickstart.py start</code>. To see the screens with hand-written replies: <code>python scripts/quickstart.py rehearse</code>.</p>}
      <p className="help">{METHOD_HELP[backend](words)}</p>
      {external&&<p className="help">{backend==='vocabulary'?'The model provider receives your request and the category and tag names of the scope, with the number of items for each name. It does not receive the item descriptions.'
        :category_method?'The model provider receives your description, the item data of the evidence scope (descriptions, categories and tags), and the names and item IDs of the controls that are applied.'
        :'The model provider receives your request and the item data of the evidence scope: descriptions, categories and tags.'} With some providers this data leaves this computer, and a call can cost money. Each review names the provider and the model.</p>}
      {authored&&modelMethod&&<p className="help">No data leaves this computer. The server looks up a hand-written reply for the exact bundled request.</p>}
      <label className="field-label" htmlFor="semantic-count">Evidence scope</label>
      <select id="semantic-count" disabled={disabled||(authored&&modelMethod)} value={choices.some(choice=>choice.value===scope)?scope:10} onChange={e=>setCount(Number(e.target.value))}>
        {choices.map(choice=><option key={choice.value} value={choice.value}>{choice.name}</option>)}</select>
      <p className="help">Items in the scope: {saved?.feed.baseline_items.slice(0,scope).join(', ')||'Loading...'}. The application uses no other item, and it does not shorten the list silently. {authored&&modelMethod?'The hand-written replies exist for this complete scope only.':'A request that is too large asks you for a smaller scope.'}</p>
      {backend==='vocabulary'&&<div role="group" aria-label="Existing categories and tags in the scope" className="vocabulary-terms">
        <span className="field-label">Existing categories and tags in the scope</span>
        {terms?<><p className="help">Categories: {termLine(t=>t.kind!=='tag'&&(t.level||1)===1)}.</p>
          <p className="help">Subcategories: {termLine(t=>t.kind!=='tag'&&(t.level||1)>1)}.</p>
          <p className="help">Tags: {termLine(t=>t.kind==='tag')}.</p>
          <p className="help">The number after each name is the number of items in the scope that carry it. {terms.note}</p></>
          :<p className="help">{termsError?`The list is not available from this server: ${termsError}`:'Loading...'}</p>}
      </div>}
      {backend==='manual_category'?<>
        <label className="field-label" htmlFor="semantic-category">Existing category</label>
        <select id="semantic-category" disabled={disabled||!categories.length} value={categories.includes(category)?category:''} onChange={e=>setCategory(e.target.value)}>
          <option value="">Choose an existing category</option>
          {categories.map(c=><option key={c} value={c}>{c}</option>)}
        </select>
      </>:<>
        <label className="field-label" htmlFor="semantic-text">{category_method?'Describe the category that you want':'Your request'}</label>
        <textarea id="semantic-text" rows={3} maxLength={2000} disabled={disabled} value={text} onChange={e=>setText(e.target.value)}
          placeholder={category_method?'Say what the items of the new category have in common.':'Say what you want more of, less of, or none of. You do not need a category name.'}/>
        {scenarioRequests?.[backend]&&<button type="button" className="secondary" disabled={disabled} onClick={()=>insertExample(examples[0])}>Insert the bundled scenario request</button>}
        {examples.length>1&&<><label className="field-label" htmlFor="semantic-example">More bundled examples</label>
          <select id="semantic-example" disabled={disabled} value="" onChange={e=>{const option=examples.find(x=>x.key===e.target.value);if(option)insertExample(option);}}>
            <option value="">Choose an example to insert</option>{examples.map(x=><option key={x.key} value={x.key}>{x.name}</option>)}</select></>}
        {['configured_model','ollama'].includes(backend)&&!authored&&<>
          <label><input type="checkbox" disabled={disabled} checked={explicitTarget} onChange={e=>setExplicitTarget(e.target.checked)}/> I will state the target meaning and the action myself.</label>
          {explicitTarget&&<>
            <label className="field-label" htmlFor="semantic-confirmed-target">Target meaning that I want filtered</label>
            <textarea id="semantic-confirmed-target" rows={3} maxLength={2000} disabled={disabled} value={target} onChange={e=>setTarget(e.target.value)}/>
            <p className="help">Use a rule that the item data can show. This is your own interpretation. It is not automatic recognition of intent and not proof of a personal reaction. The model only proposes related existing items, and you still review them.</p>
            <label><input type="checkbox" disabled={disabled||!target.trim()} checked={confirmedNow} onChange={e=>{if(reviewOpen.current){clearReview();setMessage('You changed the confirmation. The review was discarded. Nothing was applied.');}setTargetConfirmed(e.target.checked);setTargetSignature(e.target.checked?currentTargetSignature:null);}}/> I confirm this target and the action below as my intended instruction.</label>
          </>}
          {backend==='ollama'&&!explicitTarget&&<><label className="field-label" htmlFor="semantic-action-source">Who chooses the direction and strength?</label>
          <select id="semantic-action-source" value={actionSource} disabled={disabled} onChange={e=>setActionSource(e.target.value)}>
            <option value="ollama">The model reads them from my request</option><option value="manual">I choose; the model only proposes related items</option></select></>}</>}
      </>}
      {manualAction&&<>
        <label className="field-label" htmlFor="semantic-operation">Action</label>
        <select id="semantic-operation" disabled={disabled} value={operation} onChange={e=>setOperation(e.target.value)}>
          <option value="boost">Show more (raise the score)</option><option value="reduce">Show less (lower the score, still in the feed)</option><option value="exclude">Remove from the feed</option></select>
        {operation!=='exclude'&&<><label className="field-label" htmlFor="semantic-strength">Strength of the change</label>
          <select id="semantic-strength" disabled={disabled} value={strength} onChange={e=>setStrength(e.target.value)}>
          <option value="light">Light 0.10</option><option value="standard">Standard 0.25</option><option value="strong">Strong 0.40</option></select></>}</>}
      {!category_method&&!['vocabulary','combined'].includes(backend)&&<><label className="field-label" htmlFor="semantic-label">Name of this control</label>
        <input id="semantic-label" maxLength={80} disabled={disabled} value={label} onChange={e=>setLabel(e.target.value)}/></>}
      <label className="field-label" htmlFor="semantic-mode">How to combine with the applied controls</label>
      <select id="semantic-mode" disabled={disabled} value={mode} onChange={e=>setMode(e.target.value)}>
        <option value="merge">Add to the applied controls</option><option value="replace">Replace every applied control</option></select>
      <p className="help">"Add" keeps the applied controls. A control with the same name is replaced.</p>
      <button className="primary" disabled={disabled||!saved||(!modelMethod&&!categories.includes(category))||(!category_method&&!['vocabulary','combined'].includes(backend)&&!label.trim())||(modelMethod&&!text.trim())||(explicitTarget&&(!target.trim()||!confirmedNow))} onClick={review}>
        {working?waitText:backend==='staged'?'Propose a definition for review':backend==='manual_category'?'Show the proposed change':'Interpret my request'}</button>
      {working&&busyCall&&<button type="button" className="secondary" onClick={stopWaiting}>Stop waiting</button>}
      {working&&busyCall&&<p className="help">{authored?'The server reads a hand-written reply.':'A call can take minutes. "Stop waiting" does not stop the call on the server. It only discards the result on this page.'}</p>}
      {/* One live region that is always present, so that a screen reader announces each new message. */}
      <p role="status" aria-live="polite" className={message?'alert':'status-empty'}>{message}</p>
      {(variant||failure)&&<p className="help" data-role="result-place">{portal&&reviewHost?'The result is in the main area, above the feed.':'The result is below this panel.'}</p>}
      <h3>Applied controls</h3>
      {saved?(saved.groups.length?<ul className="applied-controls">{saved.groups.map(g=><li key={g.revision}><b>{g.label}</b>: {actionWords(g.proposal.action)}; {g.proposal.item_ids.length===1?'item':'items'} {g.proposal.item_ids.join(', ')}</li>)}</ul>
        :<p className="help">None.</p>):<p className="help">{working?'Loading...':'Not available.'}</p>}
      <p className="help">{saved&&saved.groups.length?plural(saved.groups.length,'control')+' applied. ':''}Applied controls last for this session only. A reload of the page starts a new session without them. They are not new categories in the dataset.</p>
      <p className="help">{LIMITS}</p>
      {!saved&&message&&<p className="help">If the applied controls cannot be loaded, you can still review their removal for this user. Approval is required. The original category and topic preferences are preserved.</p>}
      <button className="secondary" disabled={disabled||!saved?.can_undo} onClick={()=>history('undo')}>Undo the last change (review first)</button>
      <button className="secondary" disabled={disabled||saved?.groups.length===0} onClick={()=>history('clear')}>Remove every applied control (review first)</button>
    </section>}
    {open&&(portal&&reviewHost?portal(board,reviewHost):board)}
  </details>;
}

