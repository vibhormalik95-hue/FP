import React, {useEffect, useRef, useState} from 'react';

// Plain words for the stored values of the earlier topic tool.
const ACTION={boost:'Show more',reduce:'Show less, still in the feed',exclude:'Remove from the feed'};
const SOURCE={manual_structured:'You typed this phrase.',literal_source_phrase:'The phrase is in the item text.'};
const sentence=text=>{const value=String(text||'').trim();return value&&!/[.!?]$/.test(value)?value+'.':value;};
const phrase=c=>`${ACTION[c.operation]||c.operation}: "${c.topic}"${c.operation==='exclude'?'':` (${c.strength}${typeof c.adjustment==='number'?`, ${c.adjustment>0?'+':''}${c.adjustment.toFixed(2)}`:''})`}`;

export default function SteeringPanel({api, user, resetKey, onFeed, onApplied, allowLocalModels=true}) {
  const [saved,setSaved]=useState(null), [text,setText]=useState(''), [mode,setMode]=useState('merge');
  const [backend,setBackend]=useState('ollama'), [manual,setManual]=useState([]);
  const [topic,setTopic]=useState(''), [operation,setOperation]=useState('boost'), [strength,setStrength]=useState('standard');
  const [pending,setPending]=useState(null), [question,setQuestion]=useState(''), [error,setError]=useState('');
  const [working,setWorking]=useState(false);
  const [modelName,setModelName]=useState('configured local model');
  const [clarification,setClarification]=useState(null);
  const [subjectBindings,setSubjectBindings]=useState([]);
  const generation=useRef(0);
  useEffect(()=>{if(!allowLocalModels&&backend==='ollama'){setBackend('manual');setPending(null);}},[allowLocalModels,backend]);
  useEffect(()=>{
    const id=++generation.current; setWorking(false);setPending(null);setQuestion('');setClarification(null);setSubjectBindings([]);setError('');setManual([]);setText('');setSaved(null);
    if(user===null)return;
    api(`steering?user_id=${user}`).then(r=>{if(id===generation.current){setSaved(r);setModelName(r.configured_model);onFeed(r.feed);}})
      .catch(e=>{if(id===generation.current)setError(e.message);});
  },[user,resetKey]);
  async function run(action) {
    const id=generation.current;setWorking(true);setError('');setQuestion('');setClarification(null);
    try {await action(id);}catch(e){if(id===generation.current)setError(e.message);}
    finally{if(id===generation.current)setWorking(false);}
  }
  function review(){run(async id=>{
    setPending(null);
    const r=await api('steering/preview',{user_id:user,backend,mode,bindings:subjectBindings,
      ...(backend==='manual'?{actions:manual}:{text})});
    if(id!==generation.current)return;
    if(r.ready)setPending(r);else {setQuestion(r.question||'Please clarify the requested subjects.');setClarification(r.clarification||null);}
  });}
  function apply(){run(async id=>{
    const r=await api('steering/apply',{user_id:user,plan_id:pending.plan_id});
    if(id!==generation.current)return;
    setSaved(r);setPending(null);setSubjectBindings([]);setText(r.text);onFeed(r.feed);onApplied();
  });}
  function remove(subject){run(async id=>{
    const r=await api('steering/remove',{user_id:user,topic:subject});
    if(id!==generation.current)return;
    setSaved(r);setPending(null);setText(r.text);onFeed(r.feed);
  });}
  function history(action){run(async id=>{
    setPending(null);
    const r=await api('steering/history/preview',{user_id:user,action});
    if(id!==generation.current)return;
    if(r.ready)setPending(r);else setQuestion(r.question);
  });}
  function chooseSource(sourceTopic){
    const requested=clarification.requested_topic;
    const next=[...subjectBindings.filter(x=>x.requested_topic.toLowerCase()!==requested.toLowerCase()),
      {requested_topic:requested,source_topic:sourceTopic}];
    if(next.length>8){setQuestion('Remove a confirmed scope choice before adding another.');return;}
    setSubjectBindings(next);
    const start=text.toLowerCase().indexOf(requested.toLowerCase());
    if(start>=0)setText(text.slice(0,start)+sourceTopic+text.slice(start+requested.length));
    setQuestion('Source scope confirmed for this request. Review again; nothing is applied.');
    setClarification(null);setPending(null);
  }
  const disabled=working||user===null;
  return <section className="panel" aria-label="Earlier topic tool">
    <h3>Exact phrases</h3>
    <p className="help">Type exact phrases, review the matching items, then apply. The tool changes only its own feed. It is separate from the conditions A to E and from the language controls.</p>
    <label className="field-label" htmlFor="steering-backend">How the phrases are found</label>
    <select id="steering-backend" value={backend} disabled={disabled} onChange={e=>{setBackend(e.target.value);setPending(null);}}>
      {allowLocalModels&&<option value="ollama">Local model {modelName}: your own words</option>}<option value="manual">Exact phrases that you type (no model)</option>
    </select>
    <label className="field-label" htmlFor="steering-mode">How to combine with the applied phrases</label>
    <select id="steering-mode" value={mode} disabled={disabled} onChange={e=>{
      setMode(e.target.value);setPending(null);if(e.target.value==='replace')setText(saved?.text||text);
    }}><option value="merge">Add or change a phrase</option><option value="replace">Replace every phrase</option></select>
    {backend==='ollama'?<><label className="field-label" htmlFor="steering-text">Your instruction or editable profile</label>
      <textarea id="steering-text" rows={4} maxLength={2000} value={text} disabled={disabled}
        onChange={e=>{setText(e.target.value);setPending(null);}}
        placeholder="A lot more Qingdao, slightly less gaming, and hide cooking completely."/>
      <p className="help">The model reads your applied phrases for a follow-up request. You can call the last applied phrase "that"; otherwise name it. You review each action, strength and phrase before it applies. There is no rule-based fallback.</p></>:<>
      <label className="field-label" htmlFor="steering-manual-topic">Exact phrase in the item text</label>
      <input id="steering-manual-topic" value={topic} maxLength={32} disabled={disabled} onChange={e=>setTopic(e.target.value)}/>
      <label className="field-label" htmlFor="steering-operation">Action</label>
      <select id="steering-operation" value={operation} disabled={disabled} onChange={e=>setOperation(e.target.value)}>
        <option value="boost">Show more</option><option value="reduce">Show less, still in the feed</option><option value="exclude">Remove from the feed</option>
      </select>
      {operation!=='exclude'&&<><label className="field-label" htmlFor="steering-strength">Strength of the change</label>
        <select id="steering-strength" value={strength} disabled={disabled} onChange={e=>setStrength(e.target.value)}>
          <option value="light">Light 0.10</option><option value="standard">Standard 0.25</option><option value="strong">Strong 0.40</option>
        </select></>}
      <button className="secondary" disabled={disabled||topic.trim().length<2||manual.length>=8} onClick={()=>{
        setManual([...manual,{topic:topic.trim(),operation,strength:operation==='exclude'?'none':strength}]);setTopic('');setPending(null);
      }}>Add this phrase</button>
      {manual.map((c,i)=><p className="help" key={i}>{phrase(c)} <button className="text-button" disabled={disabled} aria-label={`Remove the phrase ${c.topic} from the request`} onClick={()=>{setManual(manual.filter((_,j)=>j!==i));setPending(null);}}>Remove</button></p>)}
    </>}
    <button className="primary" disabled={disabled||(backend==='manual'?!manual.length:!text.trim())} onClick={review}>
      {working?'Working...':'Review the change'}</button>
    {error&&<p role="alert" className="alert error">{error}</p>}
    {question&&<p role="status" className="alert">The tool needs a clearer request. {sentence(question)} Nothing was changed.</p>}
    {clarification&&<button className="secondary" disabled={disabled} onClick={()=>chooseSource(clarification.suggested_topic)}>
      Use the exact phrase "{clarification.suggested_topic}" and review again</button>}
    {clarification?.literal_topic&&clarification.literal_topic!==clarification.suggested_topic&&<button className="secondary" disabled={disabled}
      onClick={()=>chooseSource(clarification.literal_topic)}>Keep the phrase "{clarification.literal_topic}" as you wrote it</button>}
    {subjectBindings.map((b,i)=><p className="help" key={b.requested_topic}>Confirmed phrase: "{b.requested_topic}" means "{b.source_topic}". <button className="text-button" disabled={disabled}
      onClick={()=>{setSubjectBindings(subjectBindings.filter((_,j)=>j!==i));setPending(null);}}>Forget this choice</button></p>)}
    {pending&&<div className="saved-profile" role="status"><h4>Review the change before you apply it</h4>
      {pending.interpretation?.history_action&&pending.interpretation.history_action!=='none'
        ?<p className="help">{pending.interpretation.history_action==='undo'?'You asked to undo the last change of the phrases.':'You asked to remove every phrase.'}</p>
        :<p className="help">Requested: {pending.interpretation?.commands?.map(phrase).join('; ')}.</p>}
      <p className="help">After approval the tool has {pending.commands.length===1?'1 phrase':`${pending.commands.length} phrases`}.</p>
      {pending.commands.map(c=><div className="steering-review" key={c.topic}>
        <strong>{phrase(c)}</strong>
        <p className="help">Requested phrase: "{c.requested_topic}". {SOURCE[c.grounding_method]||`Method: ${c.grounding_method}.`} Items whose text holds it: {c.candidate_matches}.</p>
        {c.source&&<p className="help">{SOURCE[c.source]||`Source: ${c.source}.`}</p>}
        <p className="help">Examples of these items: {c.match_evidence.map(x=>x.item_id).join(', ')||'none'}.</p>
      </div>)}
      {pending.preview.topic_exposure.map(c=><p className="help" key={c.topic}>"{c.topic}": {c.baseline_top_k_match_count} of the first ten now; {c.top_k_match_count} after approval.</p>)}
      <p className="help">First ten after approval: {pending.preview.items.map(x=>x.item_id).join(', ')}. Eligible items: {pending.preview.available_items}.</p>
      <p className="help">Check the phrases yourself. A matching phrase and a changed order do not show that an item fits. A removal takes priority over a rank change.</p>
      <button className="primary" disabled={disabled} onClick={apply}>Approve and apply</button>
    </div>}
    <div className="saved-profile"><h4>Applied phrases</h4>
      {allowLocalModels&&<p className="help">{saved?.focus?`A follow-up request refers to: ${saved.focus}.`:'No phrase is the clear subject of a follow-up request. Name the phrase.'}</p>}
      {saved?.commands?.length?saved.commands.map(c=><div className="preference" key={c.topic}>
        <span>{phrase(c)}</span><button disabled={disabled} aria-label={`Remove the applied phrase ${c.topic}`} onClick={()=>remove(c.topic)}>×</button>
      </div>):<p className="help">None.</p>}
      <button className="secondary" disabled={disabled||!saved?.can_undo} onClick={()=>history('undo')}>Undo the last phrase change (review first)</button>
      <button className="secondary" disabled={disabled||!saved?.commands?.length} onClick={()=>history('clear')}>Remove every phrase (review first)</button>
      <p className="help">Undo goes back at most 10 changes. "Reset this user" removes every phrase and the undo history. A reload of the page starts a new session.</p>
    </div>
  </section>;
}
