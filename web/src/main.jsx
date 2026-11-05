import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import SteeringPanel from './SteeringPanel';
import SemanticPanel from './SemanticPanel';
import SyntheticDraftPanel from './SyntheticDraftPanel';

const conditions = {
  A: ['Item feedback', 'Direct feedback on individual items.'],
  B: ['Explanations', 'A + verified signal explanations. Rankings stay the same.'],
  C: ['Free text', 'Frozen scorer + your latest category instruction. Item feedback does not apply.'],
  D: ['Editable profile', 'Frozen scorer + your saved category preferences. Item feedback does not apply.'],
  E: ['All channels', 'Frozen scorer + explanation, instruction and profile. Latest instruction wins conflicts.'],
};

function App() {
  const [status, setStatus] = useState(null), [users, setUsers] = useState([]), [cats, setCats] = useState([]);
  const [user, setUser] = useState(null), [condition, setCondition] = useState('E');
  const [backend, setBackend] = useState('rule'), [feed, setFeed] = useState(null), [comparison, setComparison] = useState(null);
  const [control, setControl] = useState(''), [profileText, setProfileText] = useState('');
  const [topicText, setTopicText] = useState(''), [topicBackend, setTopicBackend] = useState('manual');
  const [topicOperation, setTopicOperation] = useState('boost'), [topicStrength, setTopicStrength] = useState('standard');
  const [topicResult, setTopicResult] = useState(null);
  const [reviewedFeed, setReviewedFeed] = useState(null), [steeringReset, setSteeringReset] = useState(0);
  const [busy, setBusy] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [showSignals, setShowSignals] = useState(true), [view, setView] = useState('feed');
  const token = useRef(null), requestId = useRef(0);

  async function api(path, body, method='POST') {
    const response = await fetch(`/api/${path}`, { method: body === undefined ? 'GET' : method,
      headers: { 'Content-Type': 'application/json', ...(token.current ? {'X-Session-ID': token.current} : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Check the input and try again.');
    return payload;
  }
  async function refresh(selectedUser=user, selectedCondition=condition, loadProfile=false) {
    const id = ++requestId.current;
    const [f, c] = await Promise.all([api(`feed?user_id=${selectedUser}&condition=${selectedCondition}`), api(`compare?user_id=${selectedUser}`)]);
    if (id === requestId.current) {setFeed(f); setComparison(c); if(loadProfile) setProfileText(f.profile_text);}
  }
  useEffect(() => { (async () => {
    try {
      const [s, u, c] = await Promise.all([api('status'), api('users'), api('categories')]);
      token.current = (await api('session', {})).session_id;
      setStatus(s); setUsers(u); setCats(c.categories); setUser(u[0].user_id);
      await refresh(u[0].user_id, 'E', true);
    } catch (e) {setError(e.message);} finally {setBusy(false);}
  })(); }, []);

  async function act(work, success, loadProfile=false) {
    setBusy(true); setError(''); setNotice(''); setTopicResult(null);
    try { const result = await work(); await refresh(user, condition, loadProfile); setNotice(typeof success === 'function' ? success(result) : success); }
    catch (e) {setError(e.message);} finally {setBusy(false);}
  }
  async function selectUser(value) {
    setReviewedFeed(null); setUser(Number(value)); setControl(''); setProfileText(''); setTopicResult(null); setNotice(''); setError(''); setBusy(true);
    try {await refresh(Number(value), condition, true);} catch (e) {setError(e.message);} finally {setBusy(false);}
  }
  async function selectCondition(value) {
    setCondition(value); setView('feed'); setTopicResult(null); setBusy(true); setError('');
    try {await refresh(user, value);} catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  async function previewTopic() {
    setBusy(true); setError(''); setNotice(''); setTopicResult(null);
    try {
      const result = await api('topic/preview', {user_id:user, text:topicText,
        backend:topicBackend, operation:topicOperation, strength:topicStrength,
        condition:condition === 'E' ? 'E' : 'C'});
      setTopicResult(result);
      setNotice(result.applied ? `Exploratory topic preview: ${result.candidate_matches} catalog items matched source text.` : result.message);
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  const shownFeed = view === 'steering' ? reviewedFeed : feed;
  const profile = feed?.profile || {};
  const profileWords = profileText.trim() ? profileText.trim().split(/\s+/).length : 0;
  const palette = ['#536c4a', '#986949', '#546d88', '#8e6381', '#ad944a', '#547e79'];
  const color = category => palette[Math.max(0, cats.indexOf(category)) % palette.length];

  return <div className="app-shell">
    <header className="header"><a href="#main" className="brand"><span className="brand-mark">f<span>↗</span></span><span>feed control<span className="brand-sub">RESEARCH LAB</span></span></a><div className="header-right"><span className="research-tag">COMP 9500 · OFFLINE PROTOTYPE</span><a href="/docs" target="_blank" rel="noreferrer">API reference ↗</a></div></header>
    <main id="main">
      <section className="intro"><div><p className="eyebrow">YOUR PREFERENCES, MADE VISIBLE</p><h1>A feed you can<br/><em>steer.</em></h1><p className="lede">Explore how explanations, natural-language instructions and an editable profile change a recommendation list.</p></div><div className="intro-note"><span className="big-number">05</span><span>conditions.<br/>One frozen scorer.<br/>Every control visible.</span></div></section>
      {status && <section className="status-strip" aria-label="Research environment"><span className={`status-chip ${status.data_mode === 'fixture' ? 'fixture' : ''}`}><i/>{status.data_mode === 'fixture' ? 'FIXTURE DATA' : 'PROCESSED DATASET'}</span><span>{status.model_mode}</span><span>{view === 'steering' ? 'Reviewed catalogue controls; model shown in the panel' : backend === 'rule' ? 'Rule parser · diagnostic only' : 'Ollama parser · actual request on submit'}</span><span>{status.items.toLocaleString()} items · {status.users.toLocaleString()} users</span></section>}
      <div className="disclosure">Metadata cards represent item IDs, not playable videos. Categories retain their original opaque IDs. This demonstrator makes no claim about human agency or satisfaction.</div>
      <div className="toolbar"><label className="user-select">Research user<select value={user ?? ''} onChange={e => selectUser(e.target.value)} disabled={busy || !users.length}>{users.map(u => <option key={u.user_id} value={u.user_id}>User {u.user_id} · {u.history_items} history items</option>)}</select></label><div className="view-tabs" aria-label="Display mode"><button className={view === 'feed' ? 'active' : ''} onClick={() => setView('feed')}>Explore feed</button><button className={view === 'compare' ? 'active' : ''} onClick={() => setView('compare')}>Compare A–E</button><button className={view === 'steering' ? 'active' : ''} disabled={!reviewedFeed} onClick={() => {setError(''); setNotice(''); setView('steering');}}>Reviewed topic feed</button></div><button className="text-button" disabled={busy || user === null} onClick={() => act(() => api('reset', {user_id:user}).then(r => {setSteeringReset(n=>n+1);return r;}), 'All controls and item feedback cleared for this user.', true)}>Reset this user ↺</button></div>
      {error && <div className="alert error" role="alert">{error}</div>}
      {notice && <div className="alert success" role="status">{notice}</div>}
      <div className="workspace">
        <aside className="controls">
          {view !== 'steering' && <>
          <section className="panel"><div className="section-heading"><span className="step">01</span><h2>Choose a condition</h2></div><div className="conditions">{Object.entries(conditions).map(([key, [label]]) => <button key={key} aria-pressed={condition === key} className={`condition ${condition === key ? 'selected' : ''}`} disabled={busy || user === null} onClick={() => selectCondition(key)}><b>{key}</b><span>{label}</span><span className="radio-dot"/></button>)}</div><p className="help">{conditions[condition][1]}</p></section>
          <section className="panel"><div className="section-heading"><span className="step">02</span><h2>Original category control</h2></div><label className="field-label" htmlFor="parser">Interpretation backend</label><select id="parser" value={backend} disabled={busy} onChange={e => {setBackend(e.target.value); setNotice('');}}><option value="rule">Rule parser (diagnostic)</option><option value="ollama">Ollama (local LLM)</option></select><p className="help">{backend === 'rule' ? 'Original A–E: one explicit existing category_N per instruction. This diagnostic parser is not an LLM.' : `Uses ${status?.ollama_model || 'the configured model'}. Original A–E accepts one explicit existing category_N. Backend errors are shown; no silent fallback.`}</p><form onSubmit={e => {e.preventDefault(); act(() => api('control', {user_id:user, text:control, backend}), r => r.applied ? `${r.command.operation} ${r.command.category || ''} applied via ${r.command.source}.` : 'Please clarify: name one existing category_N and ask for more, less, mute or reset. For named topics, use Reviewed topic feed.');}}><label className="field-label" htmlFor="control">What would you like to change?</label><textarea id="control" aria-describedby="control-shortcut" onKeyDown={e => {if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing) {e.preventDefault(); if (!busy && control.trim() && user !== null) e.currentTarget.form.requestSubmit();}}} maxLength={500} value={control} onChange={e => setControl(e.target.value)} placeholder={`Show me more ${cats[0] || 'category_0'}`} rows={3}/><div className="suggestions"><button type="button" onClick={() => setControl(`Show me more ${cats[0]}`)} disabled={!cats.length}>More {cats[0]}</button><button type="button" onClick={() => setControl(`Mute ${cats[1]}`)} disabled={cats.length < 2}>Mute {cats[1]}</button></div><button className="primary" disabled={busy || !control.trim() || user === null}>Apply instruction <span>↗</span></button></form><p className="help">Used by C and E. <span id="control-shortcut">Ctrl/Cmd+Enter applies the instruction.</span> One existing category_N per instruction; the latest replaces the previous one. Less/fewer means hard mute. New names and graded decreases belong in Reviewed topic feed.</p><button type="button" className="secondary" disabled={!reviewedFeed || busy} onClick={() => {setError(''); setNotice(''); setView('steering');}}>Use named topics and graded controls</button></section>
          <section className="panel"><div className="section-heading"><span className="step">03</span><h2>Your editable profile</h2></div><form onSubmit={e => {e.preventDefault(); act(() => api('profile/text', {user_id:user, text:profileText, backend}), r => r.applied ? `Profile saved via ${r.source}.` : 'Profile was ambiguous. State explicit category preferences and try again.');}}><label className="field-label" htmlFor="profile">History context + your current preferences</label><textarea id="profile" maxLength={2000} rows={4} value={profileText} onChange={e => setProfileText(e.target.value)} placeholder={`More ${cats[0] || 'category_0'}. Mute ${cats[1] || 'category_1'}.`}/><div className="word-count">{profileWords}/200 words · Used by D and E</div><button className="secondary" disabled={busy || !profileText.trim() || profileWords > 200 || user === null}>Save profile</button></form><div className="saved-profile"><span className="field-label">Parsed current preferences</span>{Object.keys(profile).length ? Object.entries(profile).map(([c,v]) => <div className="preference" key={c}><span><i style={{background:color(c)}}/>{c}</span><b>{v < 0 ? 'Muted' : `+${v.toFixed(2)}`}</b><button aria-label={`Remove ${c} preference`} disabled={busy} onClick={() => {const next={...profile}; delete next[c]; act(() => api('profile', {user_id:user,profile:next}, 'PUT'), `Removed ${c} from profile.`, true);}}>×</button></div>) : <p className="help">No saved category preferences.</p>}</div></section>
          </>}
          <div hidden={view !== 'steering'}><SteeringPanel api={api} user={user} resetKey={steeringReset} onFeed={setReviewedFeed} onApplied={() => setView('steering')}/></div>
          <div hidden={view !== 'steering'}><SemanticPanel api={api} user={user} resetKey={steeringReset} onFeed={setReviewedFeed}/></div>
            <div hidden={view !== 'steering'}><SyntheticDraftPanel api={api} user={user} resetKey={steeringReset}/></div>
          <details hidden={view === 'steering'}><summary>Earlier single-topic diagnostic</summary>
          <section className="panel" aria-label="Exploratory semantic topic control">
            <div className="section-heading"><span className="step">04</span><h2>Explore a new topic</h2></div>
            <p className="help">Optional source-text preview outside the frozen A-E study. It uses the official KuaiRec caption sidecar when configured. No new video or ground-truth category is created.</p>
            <p className="help">{status?.semantic_topic}</p>
            <form onSubmit={e => {e.preventDefault(); previewTopic();}}>
              <label className="field-label" htmlFor="topic-backend">Interpretation</label>
              <select id="topic-backend" value={topicBackend} disabled={busy} onChange={e => setTopicBackend(e.target.value)}>
                <option value="manual">Literal source-text topic (no LLM)</option>
                <option value="ollama">Local Ollama (real inference)</option>
              </select>
              {topicBackend === 'manual' && <><label className="field-label" htmlFor="topic-operation">Action</label>
                <select id="topic-operation" value={topicOperation} disabled={busy} onChange={e => setTopicOperation(e.target.value)}>
                  <option value="boost">Show more</option><option value="reduce">Show somewhat less</option>
                  <option value="exclude">Hide completely</option>
                </select>{topicOperation !== 'exclude' && <><label className="field-label" htmlFor="topic-strength">Strength</label>
                  <select id="topic-strength" value={topicStrength} disabled={busy} onChange={e => setTopicStrength(e.target.value)}>
                    <option value="light">A little (0.10)</option><option value="standard">Standard (0.25)</option>
                    <option value="strong">A lot (0.40)</option>
                  </select></>}</>}
              <label className="field-label" htmlFor="topic-text">{topicBackend === 'manual' ? 'Exact source-text topic' : 'Natural-language request'}</label>
              <textarea id="topic-text" maxLength={500} rows={3} value={topicText}
                onChange={e => setTopicText(e.target.value)}
                placeholder={topicBackend === 'manual' ? '美食' : 'Show me more cooking videos'}/>
              <button className="secondary" disabled={busy || !topicText.trim() || user === null || !status?.semantic_topic?.startsWith('Official')}>Preview topic feed</button>
            </form>
            {topicResult?.applied && <div className="saved-profile" role="status">
              <strong>{topicResult.command.operation} {topicResult.command.topic}</strong>
              <p className="help">{topicResult.command.source} | {topicResult.command.strength} strength ({topicResult.command.adjustment > 0 ? '+' : ''}{topicResult.command.adjustment.toFixed(2)}) | {topicResult.candidate_matches} catalog matches | {topicResult.top_k_match_count}/10 text matches shown | {topicResult.available_items} eligible items | {Math.round(topicResult.fill_rate*100)}% fill</p>
              {topicResult.command.rejected_terms?.length > 0 && <p className="help">Ignored unsupported model terms: {topicResult.command.rejected_terms.join(', ')}</p>}
              <p className="help">Top ten: {topicResult.items.map(item => `${item.item_id}${item.topic_text_match ? '*' : ''}`).join(', ')}</p>
              <p className="help">* matches supplied source text. This preview is not human relevance or A-E evaluation evidence.</p>
            </div>}
          </section>
          </details>
        </aside>
        <section className="results" aria-busy={busy}>
          <div className="results-header"><div><p className="eyebrow">{view === 'steering' ? 'REVIEWED CATALOGUE STEERING' : view !== 'compare' ? `CONDITION ${condition} · LIVE LOCAL PREVIEW` : 'WITHIN-SESSION COMPARISON'}</p><h2>{view === 'steering' ? 'Your reviewed topic feed' : view === 'feed' ? 'Your recommendation list' : 'One input. Five conditions.'}</h2></div>{view !== 'compare' && <label className="signal-toggle"><input type="checkbox" checked={showSignals} onChange={e => setShowSignals(e.target.checked)}/> Show signals</label>}</div>
          <div className="metrics"><div><b>{shownFeed?.items.length ?? ' - '}<small>/10</small></b><span>list fill</span></div><div><b>{Object.keys(shownFeed?.category_exposure || {}).length}</b><span>categories shown</span></div><div><b>{view === 'steering' ? reviewedFeed?.commands_count ?? 0 : feed?.feedback_count ?? 0}</b><span>{view === 'steering' ? 'topic controls' : 'item preferences'}</span></div></div>
          {view !== 'steering' && feed?.command?.category && <div className="active-instruction">Latest instruction: <strong>{feed.command.operation} {feed.command.category}</strong><span>{feed.command.source}</span></div>}
          {busy && !shownFeed && <div className="empty-state" role="status">Preparing your research session…</div>}
          {view !== 'compare' ? <><div className="feed-grid">{shownFeed?.items.map(item => <article className="item-card" key={item.item_id}><div className="item-art" style={{'--category-color':color(item.categories[0])}}><span className="rank">{String(item.rank).padStart(2,'0')}</span><div className="art-lines"><i/><i/><i/></div><span className="asset-type">ITEM METADATA</span><strong>{String(item.item_id).padStart(4,'0')}</strong></div><div className="item-body"><div className="item-title"><h3>Item {item.item_id}</h3><span>#{item.rank}</span></div><div className="category-pills">{item.categories.map(c => <span key={c}><i style={{background:color(c)}}/>{c}</span>)}</div>{showSignals && <div className="signals">{item.explanation.length > 0 && <span className="explanation-origin">{view === 'steering' ? 'Reviewed source-text policy' : item.explanation_source === 'ollama_constrained_fact_selection' ? 'Cached LLM · verified facts' : 'Verified template · no LLM'}</span>}{item.explanation.length ? item.explanation.map((s,i) => <p key={i}>{s}</p>) : <p>Explanations are available in B and E. Showing this panel does not change ranking.</p>}</div>}<div className="item-footer"><span>Base {item.base_score.toFixed(3)}</span><div style={{display:view === 'steering' ? 'none' : undefined}}><button disabled={busy} aria-label={`Like item ${item.item_id}`} title="Boost only this item" onClick={() => act(() => api('feedback', {user_id:user,item_id:item.item_id,direction:'like'}), `Positive item-only feedback saved for item ${item.item_id}; used in A and B.`)}>＋</button><button disabled={busy} aria-label={`Dislike item ${item.item_id}`} title="Remove only this item from A and B" onClick={() => act(() => api('feedback', {user_id:user,item_id:item.item_id,direction:'dislike'}), `Item ${item.item_id} excluded from A and B.`)}>−</button></div></div></div></article>)}</div>{shownFeed && !shownFeed.items.length && <div className="empty-state"><h3>No eligible items remain.</h3><p>Your mute preferences exclude the available catalog. Remove a preference or reset this user.</p></div>}</> : <div className="comparison"><p className="help">This is a preview of current inputs, not an experimental result. A and B must have identical item IDs. Exposure counts may overlap for multi-category items.</p><div className="comparison-scroll"><table><thead><tr><th>Condition</th><th>Top 10 item IDs</th><th>Category counts</th><th>Fill</th></tr></thead><tbody>{Object.entries(comparison || {}).map(([c,f]) => <tr key={c}><th><b>{c}</b>{conditions[c][0]}</th><td>{f.items.map(i => i.item_id).join(' · ') || 'Empty'}</td><td>{Object.entries(f.category_exposure).map(([cat,count]) => <span className="table-category" key={cat}><i style={{background:color(cat)}}/>{cat}: {count}</span>)}</td><td>{(100*f.fill_rate).toFixed(0)}%</td></tr>)}</tbody></table></div><div className="comparison-check">A/B rank invariance: <strong>{comparison && JSON.stringify(comparison.A.items.map(i=>i.item_id)) === JSON.stringify(comparison.B.items.map(i=>i.item_id)) ? 'verified in this preview' : 'not verified'}</strong></div></div>}
        </section>
      </div>
      <footer><span>Feed Control Lab · Research demonstrator</span><span>Session state is temporary and isolated by user. Reloading starts a fresh session.</span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
