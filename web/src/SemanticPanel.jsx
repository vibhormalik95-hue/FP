import React, {useEffect, useRef, useState} from 'react';
import ReviewBoard, {definitionEvidence} from './ReviewBoard.jsx';
import {actionWords, changeRecord, exampleOptions, stageStates} from './reviewModel.js';

export {definitionEvidence};

// One workflow for every language control: request, interpretation, evidence,
// preview, apply, undo. The panel holds the request and the state. The review
// board shows each result in three blocks (model output, application checks,
// your decision). `portal` and `reviewHost` let the page place the board in the
// wide results area; without them the board renders below the panel.

const METHOD_HELP = {
  manual_category: 'No model. You choose an existing category and an action. The application selects the items of that category.',
  vocabulary: 'One model call. The model reads the direction and strength from your request and chooses existing category and tag names. The application then selects the items that carry those names. One request can hold several preferences.',
  configured_model: 'Two model calls at most. Call 1 reads the direction and strength from your request. Call 2 selects items and cites a quotation from each one. An unclear request or an invalid quotation applies nothing. There is no rule-based fallback.',
  ollama: 'Two model calls at most, on the local model, with 90 seconds for each call. Call 1 reads the direction and strength. Call 2 selects items and cites a quotation from each one. An unclear request or an invalid quotation applies nothing. There is no rule-based fallback.',
  staged: 'Three model calls at most. Call 1 proposes a definition, and you review it. Call 2 classifies every item in the scope. Call 3 assesses the evidence without seeing the classifications. Where the two disagree, the item stays unknown. The calls can use the same model, and both can be wrong. You choose the direction and strength below.',
  induction: 'One model call proposes a label, a definition and a decision for every item in the scope. You choose the direction and strength below. The staged method gives a separate evidence assessment; this earlier method does not.',
};
const STATE_WORDS = {done: 'done', now: 'now', todo: 'not yet', skipped: 'not used'};

export default function SemanticPanel({api,user,resetKey,onFeed,scenarioRequests,categories,defaultOpen,portal,reviewHost}) {
  const [open,setOpen]=useState(Boolean(defaultOpen)),[saved,setSaved]=useState(null),[pending,setPending]=useState(null);
  const [text,setText]=useState(''),[typedLabel,setTypedLabel]=useState(null),[count,setCount]=useState(10);
  const [backend,setBackend]=useState('manual_category'),[category,setCategory]=useState('category_1');
  const [operation,setOperation]=useState('boost'),[strength,setStrength]=useState('standard'),[mode,setMode]=useState('merge');
  const [actionSource,setActionSource]=useState('ollama');
  const [definition,setDefinition]=useState(null),[evidenceReviewed,setEvidenceReviewed]=useState(false);
  const [working,setWorking]=useState(false),[message,setMessage]=useState('');
  const [clarification,setClarification]=useState(null);
  const [resolution,setResolution]=useState(null),[resolutionChoice,setResolutionChoice]=useState('');
  const [explicitTarget,setExplicitTarget]=useState(false),[target,setTarget]=useState(''),[targetConfirmed,setTargetConfirmed]=useState(false);
  const [targetSignature,setTargetSignature]=useState(null);
  // A result that proposes no change, a failed call, and the record of the last applied change.
  const [outcome,setOutcome]=useState(null),[failure,setFailure]=useState(''),[record,setRecord]=useState(null),[recordFresh,setRecordFresh]=useState(false);
  const [busyStage,setBusyStage]=useState(null),[terms,setTerms]=useState(null),[termsError,setTermsError]=useState('');
  // Until the person types a name, the control is named after what it does.
  const label=typedLabel!==null?typedLabel:backend==='manual_category'?`Manual: ${category}`:'My request';
  const setLabel=setTypedLabel;
  const currentTargetSignature=JSON.stringify([user,backend,text,target,count,operation,operation==='exclude'?'none':strength,mode]);
  const confirmedNow=targetConfirmed&&targetSignature===currentTargetSignature;
  // `generation` cancels a review that is in flight when an input changes. The first load of the
  // applied controls has its own counter, so that a default value set during the load does not discard it.
  const generation=useRef(0),activeRequest=useRef(null),termsRequest=useRef(0),loadRequest=useRef(0);
  const scopeKey=saved?saved.feed.baseline_items.slice(0,count).join(','):'';
  useEffect(()=>{++generation.current;const id=++loadRequest.current;activeRequest.current=null;setResolution(null);setResolutionChoice('');setSaved(null);setPending(null);setDefinition(null);setEvidenceReviewed(false);setClarification(null);
    setExplicitTarget(false);setTargetConfirmed(false);setMessage('');setWorking(false);setOutcome(null);setFailure('');setRecord(null);setRecordFresh(false);setBusyStage(null);
    if(open&&user!==null){setWorking(true);api(`semantic/groups?user_id=${user}`)
      .then(r=>{if(id===loadRequest.current){setSaved(r);onFeed(r.feed);}})
      .catch(e=>{if(id===loadRequest.current)setMessage(e.message);})
      .finally(()=>{if(id===loadRequest.current)setWorking(false);});}
  },[user,resetKey,open]);
  // Leave a method that this server does not offer. Never switch to a model method by itself.
  useEffect(()=>{if(!saved)return;
    const local=saved.local_models_allowed!==false,offered={manual_category:true,vocabulary:Boolean(saved.external_adapter_available),configured_model:Boolean(saved.external_adapter_available),
      staged:Boolean(saved.category_adapter_available)||local,induction:Boolean(saved.category_adapter_available)||local,ollama:local};
    if(!offered[backend]){setBackend('manual_category');setPending(null);}},[saved,backend]);
  useEffect(()=>{++generation.current;activeRequest.current=null;setWorking(false);setDefinition(null);setEvidenceReviewed(false);setClarification(null);setResolution(null);setResolutionChoice('');setRecordFresh(false);},[backend,text,label,count,operation,strength,mode,actionSource,category]);
  useEffect(()=>{setTargetConfirmed(false);setPending(null);},[backend,text,target,count,operation,strength,mode,explicitTarget]);
  useEffect(()=>{setOutcome(null);setFailure('');},[backend]);
  useEffect(()=>{if(Array.isArray(categories)&&categories.length&&!categories.includes(category))setCategory(categories[0]);},[categories,category]);
  // The existing categories and tags of the evidence scope. No model call.
  useEffect(()=>{const id=++termsRequest.current;setTerms(null);setTermsError('');
    if(!open||user===null||!scopeKey)return;
    api('semantic/vocabulary/terms',{user_id:user,candidate_ids:scopeKey.split(',').map(Number)})
      .then(r=>{if(id===termsRequest.current)setTerms(r);})
      .catch(e=>{if(id===termsRequest.current)setTermsError(e.message);});
  },[open,user,resetKey,scopeKey]);
  async function run(work,keepClarification=false,stage=null){
    if(activeRequest.current)return;
    const request=Symbol(),id=generation.current;activeRequest.current=request;setWorking(true);setMessage('');setFailure('');setBusyStage(stage);
    if(!keepClarification){setClarification(null);setResolution(null);setResolutionChoice('');}
    try{await work(id);}catch(e){if(id===generation.current){setMessage(e.message);setFailure(e.message);}}
    finally{if(activeRequest.current===request)activeRequest.current=null;if(id===generation.current)setWorking(false);}}
  async function load(id){const r=await api(`semantic/groups?user_id=${user}`);
    if(id===generation.current){setSaved(r);return r;}}
  function stopped(p,fallback){setOutcome({...p,method:backend,status:p.status||'clarify',request_text:text});
    setMessage(`${p.status||'clarify'}: ${p.reason||fallback}`);}
  function review(){run(async id=>{setPending(null);setDefinition(null);setEvidenceReviewed(false);setOutcome(null);const r=saved||await load(id);if(!r)return;
    const candidate_ids=r.feed.baseline_items.slice(0,count);
    const common={user_id:user,mode,operation,strength:operation==='exclude'?'none':strength,candidate_ids};
    const p=backend==='staged'?await api('semantic/definition/preview',{...common,objective:text}):
      backend==='induction'?await api('semantic/induction/preview',{...common,objective:text}):
      backend==='vocabulary'?await api('semantic/vocabulary/preview',{user_id:user,text,candidate_ids,mode}):
      await api('semantic/preview',{...common,text,label,backend,category,
        action_source:explicitTarget?'confirmed':backend==='configured_model'?'model':actionSource,
        ...(explicitTarget?{confirmed_target:target,target_confirmed:confirmedNow}:{})});
    if(id!==generation.current)return;
    if(p.definition_ready)setDefinition(p);else if(p.ready)setPending(p);
    else if(p.resolution_ready){setResolution(p);setResolutionChoice('');setClarification(p.clarification||null);setMessage(`${p.status||'clarify'}: ${p.reason||'Please clarify the request'}`);}
    else stopped(p,'Please clarify the request');},false,backend==='manual_category'?'Evidence':'Interpretation');}
  function resolveDefinition(choice){
    if(!resolution||!['review_primary','cancel'].includes(choice)||(choice==='review_primary'&&resolutionChoice!==choice))return;
    run(async id=>{const p=await api('semantic/definition/resolve',{
      user_id:user,plan_id:resolution.resolution_plan_id,choice});
      if(id!==generation.current)return;
      setResolution(null);setResolutionChoice('');setClarification(null);setEvidenceReviewed(false);
      if(p.definition_ready)setDefinition(p);
      else setMessage(p.status==='cancelled'?'Category clarification cancelled. Nothing was approved or applied.':`${p.status||'clarify'}: ${p.reason||'No definition was approved'}`);
    },true,'Interpretation');
  }
  function classify(){run(async id=>{const p=await api('semantic/definition/classify',{
    user_id:user,plan_id:definition.definition_plan_id,evidence_reviewed:evidenceReviewed});
    if(id!==generation.current)return;setDefinition(null);setEvidenceReviewed(false);
    if(p.ready)setPending(p);else stopped(p,'No membership was approved');},false,'Evidence');}
  function history(action){run(async id=>{setPending(null);setDefinition(null);setEvidenceReviewed(false);setOutcome(null);const p=await api('semantic/history/preview',{user_id:user,action});
    if(id!==generation.current)return;if(p.ready)setPending(p);else setMessage(p.reason);},false,'Undo');}
  function apply(){run(async id=>{const before=saved,plan=pending;const r=await api('semantic/apply',{user_id:user,plan_id:plan.plan_id});
    if(id!==generation.current)return;setSaved(r);setPending(null);onFeed(r.feed);setRecord(changeRecord(before,plan,r,new Date()));setRecordFresh(true);
    setMessage(plan.history_action==='undo'?'Undo applied. The earlier feed is restored.':plan.history_action==='clear'?'Every applied control is removed.':'Reviewed item set applied. The feed now shows the result.');},false,'Apply');}
  function discard(){if(activeRequest.current)return;setPending(null);setMessage('Review discarded. Nothing was applied.');}
  // An alternative becomes a new, explicit request by the person. Nothing is sent until they submit it.
  function adoptAlternative(value){if(typeof value!=='string'||!value.trim())return;
    if(backend==='vocabulary'){setText(value);setMessage('The alternative is now in the request box. Nothing was sent. Submit it when you are ready.');}
    else{setExplicitTarget(true);setTarget(value);setMessage('The alternative is now your stated target. Confirm it and choose the action. Nothing was sent.');}}
  function insertExample(option){setText(option.text);if(scenarioRequests?.label&&backend==='configured_model')setLabel(scenarioRequests.label);setPending(null);}
  const disabled=working||user===null;
  const local=saved?.local_models_allowed!==false,modelMethod=backend!=='manual_category';
  const category_method=['induction','staged'].includes(backend);
  const manualAction=backend==='manual_category'||category_method||explicitTarget||(backend==='ollama'&&actionSource==='manual');
  const examples=exampleOptions(scenarioRequests,backend);
  const external=backend==='vocabulary'||backend==='configured_model'||(category_method&&saved?.category_adapter_available);
  const variant=resolution?'resolution':definition?'definition':pending?'review':outcome?'outcome':failure?null:record?'changed':null;
  // A result without a change stays on the board while the person rewrites the request; the stage line then shows the first stage again.
  const outcomeNow=outcome&&(!modelMethod||outcome.request_text===text);
  const phase=working?'working':(resolution||definition||outcomeNow||(failure&&!pending))?'interpretation':pending?'preview':record&&recordFresh?(record.kind==='apply'?'applied':'undone'):'idle';
  const stages=stageStates({method:backend,phase,busyStage,historyAction:pending?.history_action||'none',stopped:Boolean(resolution||outcomeNow||failure)});
  const blocked=pending?.proposal?.target_confirmation&&(!explicitTarget||!confirmedNow)?'This review used a target that you stated. Keep the stated target and its confirmation unchanged to approve.':'';
  const context={terms:terms?.terms||pending?.vocabulary?.terms||null,
    categories:Object.fromEntries([...(saved?.feed.items||[]),...(pending?.feed.items||[])].map(item=>[item.item_id,item.categories])),
    descriptions:Object.fromEntries((saved?.feed.items||[]).map(item=>[item.item_id,item.source_text]))};
  const board=<ReviewBoard variant={variant} failure={failure} method={backend} pending={pending} current={saved} context={context} outcome={outcome}
    definition={definition} resolution={resolution} clarification={clarification} record={record}
    controls={{disabled,blocked,apply,discard,resolutionChoice,setResolutionChoice,resolveDefinition,evidenceReviewed,setEvidenceReviewed,classify,
      adoptAlternative:['vocabulary','configured_model','ollama'].includes(backend)?adoptAlternative:null,
      alternativeLabel:backend==='vocabulary'?'Use this as my new request':'Use this as my stated target'}}/>;
  const termLine=kind=>{const rows=(terms?.terms||[]).filter(kind);return rows.length?rows.map(t=>`${t.value} (${(t.item_ids||[]).length})`).join(', '):'none';};
  return <details open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>Language controls: change the feed with a reviewed request</summary>
    {open&&<section className="panel" aria-label="Language controls panel">
      <h3>One control, six stages</h3>
      <ol className="stage-line" aria-label="Stages of this control">{stages.map(s=><li key={s.name} data-state={s.state} aria-current={s.state==='now'?'step':undefined}>
        <span className="stage-name">{s.name}</span> <span className="stage-state">{STATE_WORDS[s.state]}{s.note?`: ${s.note}`:''}</span></li>)}</ol>
      <p className="help">A model can propose a change. The application checks the proposal. You review it. Nothing changes until you approve, and you can undo each change. A control is a named set of existing items with one action. It is not a new video and not a new dataset category. These controls are separate from the conditions A to E and from the earlier topic steering.</p>
      <h3>Request</h3>
      <label className="field-label" htmlFor="semantic-backend">Method</label>
      <select id="semantic-backend" disabled={disabled} value={backend} onChange={e=>{setBackend(e.target.value);setExplicitTarget(false);setTypedLabel(null);setPending(null);}}>
        <option value="manual_category">Existing category (manual, no model)</option>
        {saved?.external_adapter_available&&<option value="vocabulary">My request, matched to existing categories and tags (model)</option>}
        {saved?.external_adapter_available&&<option value="configured_model">My request, matched to item descriptions (model)</option>}
        {(saved?.category_adapter_available||local)&&<option value="staged">A new category from my description (model, in stages)</option>}
        {local&&<option value="ollama">My request, matched to item descriptions (local model {saved?.configured_model||'not loaded yet'})</option>}
        {(saved?.category_adapter_available||local)&&<option value="induction">A new category in one model call (earlier method)</option>}</select>
      <p className="help">{METHOD_HELP[backend]}</p>
      {external&&<p className="help">{backend==='vocabulary'?'The model provider receives your request and the category and tag names of the scope, with the number of items for each name. It does not receive the item descriptions.'
        :'The model provider receives your request and the item data of the evidence scope: descriptions, categories and tags.'} With some providers this data leaves this computer, and a call can cost money. Each review names the provider and the model.</p>}
      <label className="field-label" htmlFor="semantic-count">Evidence scope</label>
      <select id="semantic-count" disabled={disabled} value={count} onChange={e=>{setCount(Number(e.target.value));setPending(null);}}>
        <option value={6}>First 6 items of the starting list</option><option value={10}>First 10 items of the starting list</option></select>
      <p className="help">Items in the scope: {saved?.feed.baseline_items.slice(0,count).join(', ')||'Loading...'}. The application uses no other item, and it does not shorten the list silently. A request that is too large asks you for a smaller scope.</p>
      {backend==='vocabulary'&&<div aria-label="Existing categories and tags in the scope" className="vocabulary-terms">
        <span className="field-label">Existing categories and tags in the scope</span>
        {terms?<><p className="help">Categories: {termLine(t=>t.kind!=='tag'&&(t.level||1)===1)}.</p>
          <p className="help">Subcategories: {termLine(t=>t.kind!=='tag'&&(t.level||1)>1)}.</p>
          <p className="help">Tags: {termLine(t=>t.kind==='tag')}.</p>
          <p className="help">The number after each name is the number of items in the scope that carry it. {terms.note}</p></>
          :<p className="help">{termsError?`The list is not available from this server: ${termsError}`:'Loading...'}</p>}
      </div>}
      {backend==='manual_category'?<>
        <label className="field-label" htmlFor="semantic-category">Existing category</label>
        {Array.isArray(categories)&&categories.length?<select id="semantic-category" disabled={disabled} value={category} onChange={e=>{setCategory(e.target.value);setPending(null);}}>
          {categories.map(c=><option key={c} value={c}>{c}</option>)}</select>
          :<input id="semantic-category" disabled={disabled} value={category} onChange={e=>{setCategory(e.target.value);setPending(null);}}/>}
      </>:<>
        <label className="field-label" htmlFor="semantic-text">{category_method?'Describe the category that you want':'Your request'}</label>
        <textarea id="semantic-text" rows={3} maxLength={2000} disabled={disabled} value={text} onChange={e=>{setText(e.target.value);setPending(null);}}
          placeholder={category_method?'Say what the items of the new category have in common.':'Say what you want more of, less of, or none of. You do not need a category name.'}/>
        {scenarioRequests?.[backend]&&<button type="button" className="secondary" disabled={disabled} onClick={()=>insertExample(examples[0])}>Insert the bundled scenario request</button>}
        {examples.length>1&&<><label className="field-label" htmlFor="semantic-example">More bundled examples</label>
          <select id="semantic-example" disabled={disabled} value="" onChange={e=>{const option=examples.find(x=>x.key===e.target.value);if(option)insertExample(option);}}>
            <option value="">Choose an example to insert</option>{examples.map(x=><option key={x.key} value={x.key}>{x.name}</option>)}</select></>}
        {['configured_model','ollama'].includes(backend)&&<>
          <label><input type="checkbox" disabled={disabled} checked={explicitTarget} onChange={e=>setExplicitTarget(e.target.checked)}/> I will state the target meaning and the action myself.</label>
          {explicitTarget&&<>
            <label className="field-label" htmlFor="semantic-confirmed-target">Target meaning that I want filtered</label>
            <textarea id="semantic-confirmed-target" rows={3} maxLength={2000} disabled={disabled} value={target} onChange={e=>setTarget(e.target.value)}/>
            <p className="help">Use a rule that the supplied item data can show. This is your own interpretation. It is not automatic intent recognition and not proof of a personal reaction. The model only proposes related existing items, and you still review them.</p>
            <label><input type="checkbox" disabled={disabled||!target.trim()} checked={confirmedNow} onChange={e=>{setPending(null);setTargetConfirmed(e.target.checked);setTargetSignature(e.target.checked?currentTargetSignature:null);}}/> I confirm this target and the action below as my intended instruction.</label>
          </>}
          {backend==='ollama'&&!explicitTarget&&<><label className="field-label" htmlFor="semantic-action-source">Who chooses the direction and strength?</label>
          <select id="semantic-action-source" value={actionSource} disabled={disabled} onChange={e=>{setActionSource(e.target.value);setPending(null);}}>
            <option value="ollama">The model reads them from my request</option><option value="manual">I choose; the model only proposes related items</option></select></>}</>}
      </>}
      {manualAction&&<>
        <label className="field-label" htmlFor="semantic-operation">Action</label>
        <select id="semantic-operation" disabled={disabled} value={operation} onChange={e=>{setOperation(e.target.value);setPending(null);}}>
          <option value="boost">Show more (rank higher)</option><option value="reduce">Show less (rank lower, still in the feed)</option><option value="exclude">Remove from the feed</option></select>
        {operation!=='exclude'&&<><label className="field-label" htmlFor="semantic-strength">Strength of the change</label>
          <select id="semantic-strength" disabled={disabled} value={strength} onChange={e=>{setStrength(e.target.value);setPending(null);}}>
          <option value="light">Light 0.10</option><option value="standard">Standard 0.25</option><option value="strong">Strong 0.40</option></select></>}</>}
      {!category_method&&backend!=='vocabulary'&&<><label className="field-label" htmlFor="semantic-label">Name of this control</label>
        <input id="semantic-label" maxLength={80} disabled={disabled} value={label} onChange={e=>{setLabel(e.target.value);setPending(null);}}/></>}
      <label className="field-label" htmlFor="semantic-mode">How to combine with the applied controls</label>
      <select id="semantic-mode" disabled={disabled} value={mode} onChange={e=>{setMode(e.target.value);setPending(null);}}>
        <option value="merge">Add this control (a control with the same name is replaced)</option><option value="replace">Replace every applied control</option></select>
      <button className="primary" disabled={disabled||!saved||(!category_method&&backend!=='vocabulary'&&!label.trim())||(modelMethod&&!text.trim())||(explicitTarget&&(!target.trim()||!confirmedNow))} onClick={review}>
        {working?(modelMethod?'Waiting for the model...':'Working...'):backend==='staged'?'Propose a definition for review':backend==='manual_category'?'Show the proposed change':'Interpret my request'}</button>
      {message&&<p role="status" className="alert">{message}</p>}
      {(variant||failure)&&portal&&reviewHost&&<p className="help">The result is in the main area, above the feed.</p>}
      <h3>Applied controls</h3>
      {saved?(saved.groups.length?<ul className="applied-controls">{saved.groups.map(g=><li key={g.revision}><b>{g.label}</b>: {actionWords(g.proposal.action)}; {g.proposal.item_ids.length===1?'item':'items'} {g.proposal.item_ids.join(', ')}</li>)}</ul>
        :<p className="help">None.</p>):<p className="help">{working?'Loading...':'Not available.'}</p>}
      <p className="help">Applied controls last for this session only. They carry hashes of the source data. They are not new categories in the dataset.</p>
      {!saved&&message&&<p className="help">If the applied controls cannot be loaded, you can still review their removal for this user. Approval is required. The original category and topic preferences are preserved.</p>}
      <button className="secondary" disabled={disabled||!saved?.can_undo} onClick={()=>history('undo')}>Undo the last change (review first)</button>
      <button className="secondary" disabled={disabled||saved?.groups.length===0} onClick={()=>history('clear')}>Remove every applied control (review first)</button>
    </section>}
    {open&&(portal&&reviewHost?portal(board,reviewHost):board)}
  </details>;
}
