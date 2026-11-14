import React, {useEffect, useRef, useState} from 'react';

// Fictional items: a title, a description and a category name for an item that
// does not exist. They stay in their own list. One name for one thing: "fictional item".
export default function SyntheticDraftPanel({api,user,resetKey,scenarioRequests,provider}) {
  const [open,setOpen]=useState(false),[saved,setSaved]=useState(null),[pending,setPending]=useState(null);
  const [brief,setBrief]=useState(''),[ack,setAck]=useState(false),[working,setWorking]=useState(false),[message,setMessage]=useState('');
  const generation=useRef(0);
  const authored=provider?.live_model===false;
  useEffect(()=>{const id=++generation.current;setSaved(null);setPending(null);setWorking(false);setMessage('');setAck(false);
    if(open&&user!==null)api(`synthetic/items?user_id=${user}`).then(r=>{if(id===generation.current)setSaved(r);})
      .catch(e=>{if(id===generation.current)setMessage(e.message);});
  },[user,resetKey,open]);
  async function run(work){const id=generation.current;setWorking(true);setMessage('');
    try{await work(id);}catch(e){if(id===generation.current)setMessage(e.message);}
    finally{if(id===generation.current)setWorking(false);}}
  function generate(){run(async id=>{setPending(null);const r=await api('synthetic/preview',{user_id:user,brief,synthetic_acknowledged:ack});
    if(id!==generation.current)return;if(r.ready)setPending(r);else setMessage(`No draft was written. ${r.reason||'No reason was given.'}`);});}
  function admit(){run(async id=>{const r=await api('synthetic/admit',{user_id:user,plan_id:pending.plan_id});
    if(id!==generation.current)return;setSaved(r);setPending(null);setMessage('The fictional item is added to the list of fictional items. The feed and the catalogue are unchanged.');});}
  function remove(item_id){run(async id=>{const r=await api('synthetic/remove',{user_id:user,item_id});
    if(id===generation.current){setSaved(r);setPending(null);setMessage('The fictional item is removed.');}});}
  function clear(){run(async id=>{const r=await api('synthetic/clear',{user_id:user});
    if(id===generation.current){setSaved(r);setPending(null);setMessage('Every fictional item is removed.');}});}
  function restore(){run(async id=>{const r=await api('synthetic/restore/preview',{user_id:user});
    if(id===generation.current){setPending(r);setAck(true);setMessage('Review the removed fictional item. No new call was made.');}});}
  const disabled=working||user===null;
  const source=model=>authored?`Reply: written by hand for the example brief. No model wrote it.${model?.digest?` Hash of the reply table: ${String(model.digest).slice(0,12)}.`:''}`
    :`Model, as the server settings name it: ${model?.model||'not named'}.${model?.digest?` Settings hash ${String(model.digest).slice(0,12)} (it identifies the settings, not the model).`:''}`;
  const origin=authored?'authored reply (fictional)':'written by the model (fictional)';
  return <details open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>Fictional items: drafts in a separate list</summary>
    {open&&<section className="panel" aria-label="Fictional items">
      <h3>Draft a fictional item</h3>
      <p className="help">{authored?'A hand-written reply gives a title, a description and a category name for an item that does not exist. No model writes it.':saved?.generation_available===false?'With a model provider, a model writes a title, a description and a category name for an item that does not exist.':'A model writes a title, a description and a category name for an item that does not exist.'} Nothing real is created: no media, no item of the catalogue and no verified fact. A fictional item lasts for this session only. It never enters the conditions A to E, the catalogue, the evidence scope of a language control or the trained scorer.</p>
      <label className="field-label" htmlFor="synthetic-brief">Describe the fictional item</label>
      <textarea id="synthetic-brief" rows={3} maxLength={2000} value={brief} disabled={disabled}
        onChange={e=>{setBrief(e.target.value);setPending(null);}}/>
      {typeof scenarioRequests?.synthetic==='string'&&<button type="button" className="secondary" disabled={disabled} onClick={()=>{setBrief(scenarioRequests.synthetic);setPending(null);}}>Insert the example description</button>}
      <label><input type="checkbox" checked={ack} disabled={disabled} onChange={e=>{setAck(e.target.checked);setPending(null);}}/> I want a fictional item, not a real video or an item of the catalogue.</label>
      {saved?.generation_available===false?<p className="help" data-role="no-draft-provider">No model provider is configured, so no draft can be written.</p>
        :<p className="help">{authored?'The server looks up a hand-written reply for the exact example brief. No data leaves this computer.'
          :saved?.generation_provider==='local'?`Configured local model: ${saved?.configured_model||'Loading...'}.`
          :`Configured provider: ${saved?.generation_provider||'Loading...'}; model, as the settings name it: ${saved?.configured_model||'not named'}. The provider receives your description and the drafting instruction. It does not receive the catalogue or the history.`} One attempt for each click. No automatic second attempt.{authored?'':' The words of a model can be wrong or not suitable. Review them before you add the item.'}</p>}
      <button className="primary" disabled={disabled||!saved||saved.generation_available===false||!ack||!brief.trim()} onClick={generate}>{working?'Working...':'Write a fictional draft'}</button>
      <p role="status" aria-live="polite" className={message?'alert':'status-empty'}>{message}</p>
      {pending&&<div className="saved-profile" aria-label="Fictional draft review">
        <h4>Review the fictional item before you add it</h4>
        {pending.replayed_removed_record&&<p className="help">This is the removed fictional item, unchanged. No new call was made. Its original record is kept.</p>}
        <strong>{pending.draft.title}</strong><p>{pending.draft.description}</p>
        <p className="help">Category name of the fictional item: {pending.draft.category_label}. Origin: {origin}. No media.</p>
        <p className="help">{source(pending.draft.provenance.model)}</p>
        <p className="help">Prompt hash: {String(pending.draft.provenance.prompt_sha256).slice(0,12)}. Source version: {String(pending.draft.source_version).slice(0,12)}. Approve within five minutes.</p>
        <p className="help">Fictional items have no score. The list shows them in the order in which you added them.</p>
        <button className="primary" disabled={disabled||!ack} onClick={admit}>Approve and add to the list of fictional items</button>
      </div>}
      <h4>List of fictional items</h4>
      <p className="help">Fictional items have no score. The list shows them in the order in which you added them.</p>
      <p className="help">Fictional items in the list: {saved?.feed.items.map(r=>r.item_id).join(', ')||'none'}.</p>
      <h4>Fictional items that you added</h4>
      {saved?.items.length===0&&<p className="help">None.</p>}
      {saved?.items.map(r=><article key={r.item_id} className="saved-profile">
        <strong>{r.title}</strong><p>{r.description}</p>
        <p className="help">Fictional item {r.item_id}. Category name: {r.category_label}. No score and no media.</p>
        <p className="help">{source(r.provenance.model)} Source version: {String(r.source_version).slice(0,12)}.</p>
        {r.source_snapshot_changed&&<p role="status">The source data changed after this item was added. The item is not shown in the list. Remove it.</p>}
        <button className="secondary" disabled={disabled} onClick={()=>remove(r.item_id)}>Remove fictional item {r.item_id}</button>
      </article>)}
      <button className="secondary" disabled={disabled||!saved?.items.length} onClick={clear}>Remove every fictional item</button>
      <button className="secondary" disabled={disabled||!saved?.can_restore_removed} onClick={restore}>Review the return of the last removed fictional item</button>
      <p className="help">When you add or remove a fictional item, an open review of a language control ends. "Reset this user" removes the fictional items too. Fictional items never enter the feed or the categories of the catalogue.</p>
    </section>}
  </details>;
}
