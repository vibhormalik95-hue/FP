import React, {useEffect, useRef, useState} from 'react';

export default function SteeringPanel({api, user, resetKey, onFeed, onApplied}) {
  const [saved,setSaved]=useState(null), [text,setText]=useState(''), [mode,setMode]=useState('merge');
  const [backend,setBackend]=useState('ollama'), [manual,setManual]=useState([]);
  const [topic,setTopic]=useState(''), [operation,setOperation]=useState('boost'), [strength,setStrength]=useState('standard');
  const [pending,setPending]=useState(null), [question,setQuestion]=useState(''), [error,setError]=useState('');
  const [working,setWorking]=useState(false);
  const [modelName,setModelName]=useState('configured local model');
  const [clarification,setClarification]=useState(null);
  const generation=useRef(0);
  useEffect(()=>{
    const id=++generation.current; setWorking(false);setPending(null);setQuestion('');setClarification(null);setError('');setManual([]);setText('');setSaved(null);
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
    const r=await api('steering/preview',{user_id:user,backend,mode,
      ...(backend==='manual'?{actions:manual}:{text})});
    if(id!==generation.current)return;
    if(r.ready)setPending(r);else {setQuestion(r.question||'Please clarify the requested subjects.');setClarification(r.clarification||null);}
  });}
  function apply(){run(async id=>{
    const r=await api('steering/apply',{user_id:user,plan_id:pending.plan_id});
    if(id!==generation.current)return;
    setSaved(r);setPending(null);setText(r.text);onFeed(r.feed);onApplied();
  });}
  function remove(subject){run(async id=>{
    const r=await api('steering/remove',{user_id:user,topic:subject});
    if(id!==generation.current)return;
    setSaved(r);setPending(null);setText(r.text);onFeed(r.feed);
  });}
  const disabled=working||user===null;
  return <section className="panel" aria-label="Reviewed catalogue steering">
    <div className="section-heading"><span className="step">04</span><h2>Talk to the local feed</h2></div>
    <p className="help">Compose several topic preferences, review their source subjects, then apply. This controls the local saved-model catalogue, with no YouTube connection. Original A-E results remain separate.</p>
    <label className="field-label" htmlFor="steering-backend">Interpretation method</label>
    <select id="steering-backend" value={backend} disabled={disabled} onChange={e=>{setBackend(e.target.value);setPending(null);}}>
      <option value="ollama">{modelName}: natural language</option><option value="manual">Manual: exact source subjects</option>
    </select>
    <label className="field-label" htmlFor="steering-mode">Update scope</label>
    <select id="steering-mode" value={mode} disabled={disabled} onChange={e=>{
      setMode(e.target.value);setPending(null);if(e.target.value==='replace')setText(saved?.text||text);
    }}><option value="merge">Add or change an instruction</option><option value="replace">Replace editable topic profile</option></select>
    {backend==='ollama'?<><label className="field-label" htmlFor="steering-text">Your instruction or editable profile</label>
      <textarea id="steering-text" rows={4} maxLength={2000} value={text} disabled={disabled}
        onChange={e=>{setText(e.target.value);setPending(null);}}
        placeholder="A lot more Qingdao, slightly less gaming, and hide cooking completely."/>
      <p className="help">The model extracts directions and strengths, then grounds subjects through literal source text, translation or a disclosed real catalogue label. Ambiguity asks for clarification. No silent rule fallback.</p></>:<>
      <label className="field-label" htmlFor="steering-manual-topic">Exact catalogue phrase</label>
      <input id="steering-manual-topic" value={topic} maxLength={32} disabled={disabled} onChange={e=>setTopic(e.target.value)}/>
      <label className="field-label" htmlFor="steering-operation">Manual direction</label>
      <select id="steering-operation" value={operation} disabled={disabled} onChange={e=>setOperation(e.target.value)}>
        <option value="boost">Increase</option><option value="reduce">Decrease, still eligible</option><option value="exclude">Exclude completely</option>
      </select>
      {operation!=='exclude'&&<><label className="field-label" htmlFor="steering-strength">Manual strength</label>
        <select id="steering-strength" value={strength} disabled={disabled} onChange={e=>setStrength(e.target.value)}>
          <option value="light">A little (0.10)</option><option value="standard">Standard (0.25)</option><option value="strong">A lot (0.40)</option>
        </select></>}
      <button className="secondary" disabled={disabled||topic.trim().length<2||manual.length>=8} onClick={()=>{
        setManual([...manual,{topic:topic.trim(),operation,strength:operation==='exclude'?'none':strength}]);setTopic('');setPending(null);
      }}>Add manual control</button>
      {manual.map((c,i)=><p className="help" key={i}>{c.operation} {c.topic} ({c.strength}) <button disabled={disabled} aria-label={`Remove draft control ${i+1}`} onClick={()=>{setManual(manual.filter((_,j)=>j!==i));setPending(null);}}>Remove</button></p>)}
    </>}
    <button className="primary" disabled={disabled||(backend==='manual'?!manual.length:!text.trim())} onClick={review}>
      {working?'Working locally...':'Review proposed changes'}</button>
    {error&&<p role="alert" className="alert error">{error}</p>}
    {question&&<p role="status" className="alert">Clarification needed: {question} Active preferences were kept.</p>}
    {clarification&&text.toLowerCase().includes(clarification.requested_topic.toLowerCase())&&<button className="secondary" disabled={disabled}
      onClick={()=>{const start=text.toLowerCase().indexOf(clarification.requested_topic.toLowerCase());
        setText(text.slice(0,start)+clarification.suggested_topic+text.slice(start+clarification.requested_topic.length));
        setQuestion('Source phrase inserted. Review the complete request again; nothing is applied.');setClarification(null);setPending(null);}}>
      Use exact source phrase {clarification.suggested_topic} and review again</button>}
    {pending&&<div className="saved-profile" role="status"><h3>Review before applying</h3>
      {pending.commands.map(c=><div className="steering-review" key={c.topic}>
        <strong>{c.operation} {c.topic} ({c.strength}, {c.adjustment>0?'+':''}{c.adjustment.toFixed(2)})</strong>
        <p className="help">Requested subject: {c.requested_topic}; {c.grounding_method}; {c.candidate_matches} source matches.</p>
        <p className="help">{c.source}</p>
        <p className="help">Example item IDs: {c.match_evidence.map(x=>x.item_id).join(', ')}</p>
      </div>)}
      {pending.preview.topic_exposure.map(c=><p className="help" key={c.topic}>{c.topic}: {c.baseline_top_k_match_count}/10 before; {c.top_k_match_count}/10 proposed.</p>)}
      <p className="help">Proposed top ten: {pending.preview.items.map(x=>x.item_id).join(', ')}. {Math.round(pending.preview.fill_rate*100)}% fill; {pending.preview.available_items} eligible.</p>
      <p className="help">Check the subjects yourself. Source matching and a changed order do not prove human relevance. Hard exclusions win overlapping controls.</p>
      <button className="primary" disabled={disabled} onClick={apply}>Apply reviewed changes</button>
    </div>}
    <div className="saved-profile"><h3>Saved topic profile</h3>
      {saved?.commands?.length?saved.commands.map(c=><div className="preference" key={c.topic}>
        <span>{c.operation} {c.topic} ({c.strength})</span><button disabled={disabled} aria-label={`Remove saved topic ${c.topic}`} onClick={()=>remove(c.topic)}>Remove</button>
      </div>):<p className="help">No saved topic controls.</p>}
      <p className="help">Saved within this session and research user. Reset this user clears these controls. Reloading starts a fresh session.</p>
    </div>
  </section>;
}
