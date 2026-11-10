import React, {useEffect, useRef, useState} from 'react';

export default function SyntheticDraftPanel({api,user,resetKey}) {
  const [open,setOpen]=useState(false),[saved,setSaved]=useState(null),[pending,setPending]=useState(null);
  const [brief,setBrief]=useState(''),[ack,setAck]=useState(false),[working,setWorking]=useState(false),[message,setMessage]=useState('');
  const generation=useRef(0);
  useEffect(()=>{const id=++generation.current;setSaved(null);setPending(null);setWorking(false);setMessage('');setAck(false);
    if(open&&user!==null)api(`synthetic/items?user_id=${user}`).then(r=>{if(id===generation.current)setSaved(r);})
      .catch(e=>{if(id===generation.current)setMessage(e.message);});
  },[user,resetKey,open]);
  async function run(work){const id=generation.current;setWorking(true);setMessage('');
    try{await work(id);}catch(e){if(id===generation.current)setMessage(e.message);}
    finally{if(id===generation.current)setWorking(false);}}
  function generate(){run(async id=>{setPending(null);const r=await api('synthetic/preview',{user_id:user,brief,synthetic_acknowledged:ack});
    if(id!==generation.current)return;if(r.ready)setPending(r);else setMessage(`${r.status||'error'}: ${r.reason||'No fictional draft admitted.'}`);});}
  function admit(){run(async id=>{const r=await api('synthetic/admit',{user_id:user,plan_id:pending.plan_id});
    if(id!==generation.current)return;setSaved(r);setPending(null);setMessage('Fictional metadata admitted only to the isolated synthetic feed.');});}
  function remove(item_id){run(async id=>{const r=await api('synthetic/remove',{user_id:user,item_id});
    if(id===generation.current){setSaved(r);setPending(null);setMessage('Synthetic item removed.');}});}
  function clear(){run(async id=>{const r=await api('synthetic/clear',{user_id:user});
    if(id===generation.current){setSaved(r);setPending(null);setMessage('Synthetic drafts cleared.');}});}
  function restore(){run(async id=>{const r=await api('synthetic/restore/preview',{user_id:user});
    if(id===generation.current){setPending(r);setAck(true);setMessage('Review the exact removed generated record. No new model call was made.');}});}
  const disabled=working||user===null;
  return <details open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>Experimental synthetic item drafts — fictional metadata only</summary>
    {open&&<section className="panel" aria-label="Synthetic item drafts">
      <h3>Create a fictional item and description</h3>
      <p className="help">Opt in to model-generated synthetic metadata. No real media, observed catalogue entry or verified fact is created. Drafts are temporary and isolated by session and user. They never enter original A–E, the observed catalogue, semantic source scopes or the trained scorer.</p>
      <label className="field-label" htmlFor="synthetic-brief">Fictional item brief</label>
      <textarea id="synthetic-brief" rows={3} maxLength={2000} value={brief} disabled={disabled}
        onChange={e=>{setBrief(e.target.value);setPending(null);}}/>
      <label><input type="checkbox" checked={ack} disabled={disabled} onChange={e=>{setAck(e.target.checked);setPending(null);}}/> I want fictional metadata, not a real video or observed item.</label>
      {saved?.generation_available===false?<p className="help">Fictional drafting is unavailable in this application.</p>:<p className="help">{saved?.generation_provider==='local' ? `Configured local model: ${saved?.configured_model||'Loading...'}.` : `Configured provider: ${saved?.generation_provider||'Loading...'}; model: ${saved?.configured_model||'configured model'}. Your brief and drafting instruction are sent to that provider; catalogue and history are not.`} One attempt per click; no automatic retry. Model wording can still be inappropriate; review before admission.</p>}
      <button className="primary" disabled={disabled||!saved||saved.generation_available===false||!ack||!brief.trim()} onClick={generate}>{working?'Generating...':'Generate fictional metadata draft'}</button>
      {message&&<p className="alert" role="status">{message}</p>}
      {pending&&<div className="saved-profile" aria-label="Fictional draft review">
        <h4>Review fictional metadata before admission</h4>
        {pending.replayed_removed_record&&<p className="help">Restoring the exact removed generated record; no new inference. Original model/prompt provenance is preserved.</p>}
        <strong>{pending.draft.title}</strong><p>{pending.draft.description}</p>
        <p className="help">Synthetic category: {pending.draft.category_label}. Origin: {pending.draft.origin}. No media asset.</p>
        <p className="help">Model: {pending.draft.provenance.model.model}; digest {pending.draft.provenance.model.digest}.</p>
        <p className="help">Prompt hash: {pending.draft.provenance.prompt_sha256}. Source-version hash: {pending.draft.source_version}. Approval expires after five minutes.</p>
        <p className="help">{pending.cold_start_policy}</p>
        <button className="primary" disabled={disabled||!ack} onClick={admit}>Approve fictional draft and admit to synthetic feed</button>
      </div>}
      <h4>Isolated synthetic metadata feed</h4>
      <p className="help">{saved?.feed.cold_start_policy||'Neutral score zero; admission order only. No trained relevance.'}</p>
      <p className="help">Eligible synthetic feed IDs: {saved?.feed.items.map(r=>r.item_id).join(', ')||'None'}. Only these records receive a diagnostic feed position.</p>
      <h4>Admitted synthetic records</h4>
      {saved?.items.length===0&&<p>No admitted synthetic items.</p>}
      {saved?.items.map(r=><article key={r.item_id} className="saved-profile">
        <strong>{r.title}</strong><p>{r.description}</p>
        <p className="help">SYNTHETIC / GENERATED — {r.item_id}; {r.category_label}; diagnostic score 0. No real media or trained relevance.</p>
        <p className="help">Model {r.provenance.model.model}, digest {r.provenance.model.digest}. Source version {r.source_version}.</p>
        {r.source_snapshot_changed&&<p role="status">Original source snapshot changed. This synthetic record is withheld from the diagnostic feed; remove or clear it.</p>}
        <button className="secondary" disabled={disabled} onClick={()=>remove(r.item_id)}>Remove synthetic item {r.item_id}</button>
      </article>)}
      <button className="secondary" disabled={disabled||!saved?.items.length} onClick={clear}>Clear synthetic items</button>
      <button className="secondary" disabled={disabled||!saved?.can_restore_removed} onClick={restore}>Review restoring last removed synthetic item</button>
      <p className="help">Admission/removal invalidates pending reviews. Global Reset this user also removes these session records. Existing saved observed-source groups and the observed taxonomy remain separate.</p>
    </section>}
  </details>;
}
