import React, {useEffect, useRef, useState} from 'react';

export default function SemanticPanel({api,user,resetKey,onFeed}) {
  const [open,setOpen]=useState(false),[saved,setSaved]=useState(null),[pending,setPending]=useState(null);
  const [text,setText]=useState(''),[label,setLabel]=useState('My semantic group'),[count,setCount]=useState(10);
  const [backend,setBackend]=useState('ollama'),[category,setCategory]=useState('category_1');
  const [operation,setOperation]=useState('boost'),[strength,setStrength]=useState('standard'),[mode,setMode]=useState('merge');
  const [actionSource,setActionSource]=useState('ollama');
  const [definition,setDefinition]=useState(null),[evidenceReviewed,setEvidenceReviewed]=useState(false);
  const [working,setWorking]=useState(false),[message,setMessage]=useState('');
  const generation=useRef(0);
  useEffect(()=>{const id=++generation.current;setSaved(null);setPending(null);setDefinition(null);setEvidenceReviewed(false);setMessage('');setWorking(false);
    if(open&&user!==null){setWorking(true);api(`semantic/groups?user_id=${user}`)
      .then(r=>{if(id===generation.current)setSaved(r);})
      .catch(e=>{if(id===generation.current)setMessage(e.message);})
      .finally(()=>{if(id===generation.current)setWorking(false);});}
  },[user,resetKey,open]);
  useEffect(()=>{setDefinition(null);setEvidenceReviewed(false);},[backend,text,count,operation,strength,mode]);
  async function run(work){const id=generation.current;setWorking(true);setMessage('');
    try{await work(id);}catch(e){if(id===generation.current)setMessage(e.message);}
    finally{if(id===generation.current)setWorking(false);}}
  async function load(id){const r=await api(`semantic/groups?user_id=${user}`);
    if(id===generation.current){setSaved(r);return r;}}
  function review(){run(async id=>{setPending(null);setDefinition(null);setEvidenceReviewed(false);const r=saved||await load(id);if(!r)return;
    const common={user_id:user,mode,operation,strength:operation==='exclude'?'none':strength,
      candidate_ids:r.feed.baseline_items.slice(0,count)};
    const p=backend==='staged'?await api('semantic/definition/preview',{...common,objective:text}):
      backend==='induction'?await api('semantic/induction/preview',{...common,objective:text}):
      await api('semantic/preview',{...common,text,label,backend,category,action_source:actionSource});
    if(id!==generation.current)return;
    if(p.definition_ready)setDefinition(p);else if(p.ready)setPending(p);else setMessage(`${p.status||'clarify'}: ${p.reason||'Please clarify the request'}`);});}
  function classify(){run(async id=>{const p=await api('semantic/definition/classify',{
    user_id:user,plan_id:definition.definition_plan_id,evidence_reviewed:evidenceReviewed});
    if(id!==generation.current)return;setDefinition(null);setEvidenceReviewed(false);
    if(p.ready)setPending(p);else setMessage(`${p.status||'clarify'}: ${p.reason||'No membership was approved'}`);});}
  function history(action){run(async id=>{setPending(null);setDefinition(null);setEvidenceReviewed(false);const p=await api('semantic/history/preview',{user_id:user,action});
    if(id!==generation.current)return;if(p.ready)setPending(p);else setMessage(p.reason);});}
  function apply(){run(async id=>{const r=await api('semantic/apply',{user_id:user,plan_id:pending.plan_id});
    if(id!==generation.current)return;setSaved(r);setPending(null);onFeed(r.feed);setMessage('Reviewed item set applied to the separate semantic feed.');});}
  const disabled=working||user===null;
  return <details open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>Experimental semantic groups: indirect intent over supplied items</summary>
    {open&&<section className="panel" aria-label="Reviewed semantic groups">
      <h3>Create and review a named semantic item set</h3>
      <p className="help">The local model can propose a nonliteral relationship from real source text. Only the displayed baseline items are assessed. This is a new user-defined group over existing videos, not a new video or an official dataset category. Original A-E and literal topic preferences stay separate.</p>
      <label className="field-label" htmlFor="semantic-backend">Method</label>
      <select id="semantic-backend" disabled={disabled} value={backend} onChange={e=>{setBackend(e.target.value);setPending(null);}}>
        <option value="ollama">{saved?.configured_model||'Configured local model'}: semantic proposal</option>
        <option value="staged">Local LLM: review definition, then classify all supplied items</option>
        <option value="induction">Local LLM: propose a new category definition and membership</option>
        <option value="manual_category">Manual: exact original category baseline</option></select>
      {!['induction','staged'].includes(backend)&&<><label className="field-label" htmlFor="semantic-label">Name this group</label>
      <input id="semantic-label" maxLength={80} disabled={disabled} value={label} onChange={e=>{setLabel(e.target.value);setPending(null);}}/></>}
      <label className="field-label" htmlFor="semantic-count">Evidence scope</label>
      <select id="semantic-count" disabled={disabled} value={count} onChange={e=>{setCount(Number(e.target.value));setPending(null);}}>
        <option value={6}>First 6 baseline items</option><option value={10}>First 10 baseline items</option></select>
      <p className="help">Supplied item IDs: {saved?.feed.baseline_items.slice(0,count).join(', ')||'Loading...'}. No hidden retrieval or silent truncation. An oversized evidence payload asks for a narrower scope.</p>
      {backend!=='manual_category'?<><label className="field-label" htmlFor="semantic-text">{['induction','staged'].includes(backend)?'Category discovery objective':'One current instruction'}</label>
        <textarea id="semantic-text" rows={3} maxLength={2000} disabled={disabled} value={text} onChange={e=>{setText(e.target.value);setPending(null);}}
          placeholder="Describe what you want more, less or none of; indirect meaning is allowed."/>
        {backend==='staged'?<p className="help">First review a model-proposed definition. After approval, one call classifies all supplied items and a separate call assesses the evidence without seeing those decisions. Disagreements become unknown. Three calls at most, each bounded to 90 seconds plus identity checks. This may use the same model and does not verify semantic truth: both passes can agree on a wrong set. Review every final membership before applying. You choose direction and strength below.</p>:backend==='induction'?<p className="help">One local model call proposes a label, definition and match/not_match/unknown decision for every supplied item. You choose the control below. Evidence and inventory budgets may block a request; no silent truncation. Review is required; no new videos are created.</p>:<>
        <p className="help">Two real model calls at most: action interpretation and evidence selection, each limited to 90 seconds plus identity checks. Ambiguity or invalid evidence applies nothing. No rule fallback.</p>
        <label className="field-label" htmlFor="semantic-action-source">Who chooses direction and strength?</label>
        <select id="semantic-action-source" value={actionSource} disabled={disabled} onChange={e=>{setActionSource(e.target.value);setPending(null);}}>
          <option value="ollama">The model interprets my instruction</option><option value="manual">I choose; the model only proposes related items</option></select></>}
      </>:<>
        <label className="field-label" htmlFor="semantic-category">Existing category ID</label>
        <input id="semantic-category" disabled={disabled} value={category} onChange={e=>{setCategory(e.target.value);setPending(null);}}/>
      </>}
      {(backend==='manual_category'||backend==='induction'||backend==='staged'||actionSource==='manual')&&<>
        <label className="field-label" htmlFor="semantic-operation">Manual action</label>
        <select id="semantic-operation" disabled={disabled} value={operation} onChange={e=>{setOperation(e.target.value);setPending(null);}}>
          <option value="boost">Increase</option><option value="reduce">Decrease, still eligible</option><option value="exclude">Exclude</option></select>
        {operation!=='exclude'&&<select aria-label="Semantic manual strength" disabled={disabled} value={strength} onChange={e=>{setStrength(e.target.value);setPending(null);}}>
          <option value="light">Light 0.10</option><option value="standard">Standard 0.25</option><option value="strong">Strong 0.40</option></select>}</>}
      <label className="field-label" htmlFor="semantic-mode">Semantic profile update</label>
      <select id="semantic-mode" disabled={disabled} value={mode} onChange={e=>{setMode(e.target.value);setPending(null);}}>
        <option value="merge">Add or replace this named group</option><option value="replace">Replace semantic group profile</option></select>
      <button className="primary" disabled={disabled||!saved||(!['induction','staged'].includes(backend)&&!label.trim())||(backend!=='manual_category'&&!text.trim())} onClick={review}>
        {working?'Working locally...':backend==='staged'?'Propose a definition for review':'Review semantic proposal'}</button>
      {message&&<p role="status" className="alert">{message}</p>}
      {definition&&<div className="saved-profile" aria-label="Category definition review">
        <h4>Stage 1: review the whole definition</h4>
        <strong>{definition.definition.proposal.label}</strong>
        <p>{definition.definition.proposal.definition}</p>
        {definition.definition.source_constraints&&<p className="help">Literal witness requirements: {definition.definition.source_constraints.terms.join(', ')||'No digit-bearing terms'}. Every positive must contain these terms in supplied metadata. This conservative text constraint may withhold equivalent wording, unit conversions or ranges; presence does not establish truth.</p>}
        <p className="help">Objective: {definition.definition.objective}</p>
        <p className="help">Model rationale: {definition.definition.proposal.rationale}</p>
        {definition.definition.proposal.evidence.map((e,n)=><p className="help" key={n}>Item {e.item_id}, {e.field}: "{e.quote}". {e.reason}</p>)}
        <p className="help">{definition.definition.provenance.model_id}; digest {definition.definition.provenance.model_revision}. Assessed scope: {definition.scope_ids.join(', ')}. No membership or feed change is approved yet.</p>
        <p className="help">Reject a definition with unsupported properties, credentials or ratings, even if the quotation exists. Change the objective to start again. Approval expires after five minutes.</p>
        <label><input type="checkbox" checked={evidenceReviewed} disabled={disabled} onChange={e=>setEvidenceReviewed(e.target.checked)}/> I reviewed whether the source evidence supports the entire definition.</label>
        <button className="primary" disabled={disabled||!evidenceReviewed} onClick={classify}>Approve definition and classify supplied items</button>
      </div>}
      {pending&&<div className="saved-profile"><h4>Review the meaning and evidence yourself</h4>
        {pending.groups.map(g=><div key={g.label} className="steering-review">
          <strong>{g.label}: {g.proposal.action.operation} ({g.proposal.action.strength})</strong>
          <p className="help">Original request: {g.request}</p><p className="help">Model relationship: {g.proposal.reason}</p>
          {g.proposal.induction&&<div><p className="help">Generated definition: {g.proposal.induction.validated_category.definition}</p>
            <p className="help">Unknown items: {g.proposal.induction.validated_category.unknown_ids.join(', ')||'None'}. Novelty is checked only against the supplied inventory.</p>
            {g.proposal.induction.envelope.evidence_audit&&<div>
              <p className="help">Separate evidence assessment: {g.proposal.induction.envelope.evidence_audit.assessment.model.model_id}; digest {g.proposal.induction.envelope.evidence_audit.assessment.model.model_revision}. Blinded to primary decisions, possibly the same model. Agreement is not independent proof; unsupported properties can still be proposed incorrectly.</p>
              {g.proposal.induction.envelope.evidence_audit.assessment.assessments.map(a=><p className="help" key={a.item_id}>Item {a.item_id} evidence assessment: {a.assessment}; {a.field||'no field'}; "{a.quote}". {a.reason}</p>)}
              <p className="help">Withheld as unknown after assessment disagreement: {g.proposal.induction.envelope.evidence_audit.withheld.filter(r=>!r.missing_literal_terms?.length).map(r=>r.item_id).join(', ')||'None'}.</p>
              <p className="help">Withheld as unknown because required literal terms are absent: {g.proposal.induction.envelope.evidence_audit.withheld.filter(r=>r.missing_literal_terms?.length).map(r=>`Item ${r.item_id}: ${r.missing_literal_terms.join(', ')}`).join('; ')||'None'}. A primary unknown or negative is never upgraded to positive.</p>
              <p className="help">Required literal witnesses: {g.proposal.induction.envelope.evidence_audit.literal_constraints.terms.join(', ')||'No digit-bearing terms'}. Missing witnesses also remain unknown. A present term may still be negated, quoted or unrelated; this is not semantic truth verification.</p>
            </div>}
            {g.proposal.induction.envelope.normalizations?.map(e=><p className="help" key={e.item_id}>Item {e.item_id}: uncited unknown field "{e.original_field}" omitted from canonical evidence. The verdict remains unknown; raw model output is retained.</p>)}
            {g.proposal.induction.envelope.field_evidence.map(e=><p className="help" key={e.item_id}>Item {e.item_id}: {e.verdict}; {e.field||'no field'}; "{e.evidence_quote}". {e.reason}</p>)}
            <p className="help">Overlaps: {g.proposal.induction.envelope.overlaps.map(o=>`${o.category_id}: ${o.member_ids.join(',')}`).join('; ')||'None in supplied inventory'}</p>
          </div>}
          <p className="help">Direction and strength: {g.proposal.action_source==='manual'?'Explicitly selected by you; not model action accuracy':g.proposal.provenance.model.backend==='manual_category'?'Manual category baseline':'Interpreted by the model'}.</p>
          <p className="help">Selected existing IDs: {g.proposal.item_ids.join(', ')}; assessed scope: {g.scope_ids.join(', ')}</p>
          {g.proposal.evidence.map(e=><p className="help" key={e.item_id}>Item {e.item_id}, {e.field}: “{e.quote}”</p>)}
          <p className="help">{g.proposal.provenance.model.backend} / {g.proposal.provenance.model.model}; digest {g.proposal.provenance.model.digest}</p>
        </div>)}
        {pending.feed.group_exposure.map(g=><p key={g.label} className="help">{g.label}: {g.before}/10 baseline; {g.after}/10 proposed.</p>)}
        <p className="help">Proposed IDs: {pending.feed.items.map(i=>i.item_id).join(', ')}; {pending.feed.available_items} eligible. An exact quote proves source existence, not semantic relevance. Model meaning may be wrong; do not approve it if inappropriate.</p>
        <button className="primary" disabled={disabled} onClick={apply}>Approve this exact item set and apply</button>
      </div>}
      <p className="help">Saved semantic groups: {saved?(saved.groups.map(g=>g.label).join(', ')||'None'):(working?'Loading...':'Unavailable')}. These are temporary session records with source hashes, not new source taxonomy labels.</p>
      {!saved&&message&&<p className="help">If saved groups cannot be loaded, you can still review clearing semantic groups for this user. Approval is required; original category and topic preferences are preserved.</p>}
      <button className="secondary" disabled={disabled||!saved?.can_undo} onClick={()=>history('undo')}>Review semantic undo</button>
      <button className="secondary" disabled={disabled||saved?.groups.length===0} onClick={()=>history('clear')}>Review clearing semantic groups</button>
    </section>}
  </details>;
}
