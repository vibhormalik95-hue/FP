import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { createRoot } from 'react-dom/client';
import './style.css';
import SteeringPanel from './SteeringPanel';
import SemanticPanel from './SemanticPanel';
import SyntheticDraftPanel from './SyntheticDraftPanel';
import { createApiClient } from './personalApi';
import { categoryIdsReadable, controlLines, plural } from './reviewModel.js';

const conditions = {
  A: ['Item feedback', 'Direct feedback on individual items.'],
  B: ['Explanations', 'A + explanation lines. Rankings stay the same.'],
  C: ['Free text', 'The same scorer + your latest category instruction. Item feedback does not apply.'],
  D: ['Editable profile', 'The same scorer + your saved category preferences. Item feedback does not apply.'],
  E: ['All channels', 'The same scorer + explanation, instruction and profile. Latest instruction wins conflicts.'],
};
const OPERATION_WORDS = {boost: 'show more', mute: 'mute', reset: 'reset of the instruction, the profile and the item feedback'};

// A server sentence about the parser, in words that say what to do.
function parserWords(message) {
  if (/^rule parser failed/.test(message)) return 'The rule parser did not understand the instruction. Name one existing category, for example "Show me more category_0" or "Mute category_1". Nothing changed.';
  if (/^rule profile parser failed/.test(message)) return 'The rule parser did not understand the profile. Write explicit category preferences, for example "More category_0. Mute category_1." The earlier profile is kept.';
  return message;
}

function App({client, personal, onLock}) {
  const [status, setStatus] = useState(null), [users, setUsers] = useState([]), [cats, setCats] = useState([]);
  const [user, setUser] = useState(null), [condition, setCondition] = useState('E');
  const [backend, setBackend] = useState('rule'), [feed, setFeed] = useState(null), [comparison, setComparison] = useState(null);
  const [control, setControl] = useState(''), [profileText, setProfileText] = useState('');
  const [topicText, setTopicText] = useState(''), [topicBackend, setTopicBackend] = useState('manual');
  const [topicOperation, setTopicOperation] = useState('boost'), [topicStrength, setTopicStrength] = useState('standard');
  const [topicResult, setTopicResult] = useState(null);
  // The language view has two tools with separate state: the language controls and the
  // earlier topic tool. The feed of the tool that was used last is shown.
  const [semanticFeed, setSemanticFeed] = useState(null), [semanticGroups, setSemanticGroups] = useState([]), [steeringFeed, setSteeringFeed] = useState(null);
  const [feedTool, setFeedTool] = useState('semantic'), [steeringReset, setSteeringReset] = useState(0);
  const [reviewHost, setReviewHost] = useState(null), [languageMissing, setLanguageMissing] = useState('');
  const [busy, setBusy] = useState(true), [confirmReset, setConfirmReset] = useState(false), [lost, setLost] = useState('');
  // Each message stands next to the control that caused it: the instruction, the profile, the topic preview, or the page.
  const [messages, setMessages] = useState({});
  const [showSignals, setShowSignals] = useState(true), [view, setView] = useState('feed');
  const token = useRef(null), requestId = useRef(0);
  const say = (where, kind, text) => setMessages(all => ({...all, [where]: text ? {kind, text} : null}));

  async function api(path, body, method='POST') {
    try { return await client.request(path, body, method, token.current); }
    catch (error) {
      // The browser gives a TypeError when no answer came back at all.
      if (error instanceof TypeError) {
        setLost('network');
        throw Object.assign(new Error('The page cannot reach the server. Check that the server runs, then reload the page. A server that was started again has no applied controls.'), {kind: 'network'});
      }
      if (/^Session expired/.test(error.message || '')) {
        setLost('session');
        throw Object.assign(new Error('The session has ended. The server was started again, or the session expired. The controls that this page shows are no longer on the server. Reload the page to start a new session.'), {kind: 'session'});
      }
      throw error;
    }
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
      // A bundled scenario is served for the language controls: open that view first.
      if (s.scenario_requests) setView('steering');
      await refresh(u[0].user_id, 'E', true);
    } catch (e) {say('page', 'error', e.message);} finally {setBusy(false);}
  })(); }, []);
  // Without item descriptions the language controls cannot work: go back to the conditions and say why.
  useEffect(() => { if (languageMissing && view === 'steering') setView('feed'); }, [languageMissing, view]);

  async function act(work, success, loadProfile=false, where='page') {
    setBusy(true); setMessages({}); setTopicResult(null);
    try { const result = await work(); await refresh(user, condition, loadProfile); say(where, 'notice', typeof success === 'function' ? success(result) : success); }
    catch (e) {say(where, 'error', parserWords(e.message));} finally {setBusy(false);}
  }
  async function selectUser(value) {
    setSemanticFeed(null); setSemanticGroups([]); setSteeringFeed(null); setFeedTool('semantic'); setUser(Number(value)); setControl(''); setProfileText(''); setTopicResult(null); setMessages({}); setBusy(true);
    try {await refresh(Number(value), condition, true);} catch (e) {say('page', 'error', e.message);} finally {setBusy(false);}
  }
  async function selectCondition(value) {
    setCondition(value); setView('feed'); setTopicResult(null); setBusy(true); setMessages({});
    try {await refresh(user, value);} catch(e) {say('page', 'error', e.message);} finally {setBusy(false);}
  }
  async function previewTopic() {
    setBusy(true); setMessages({}); setTopicResult(null);
    try {
      const result = await api('topic/preview', {user_id:user, text:topicText,
        backend:topicBackend, operation:topicOperation, strength:topicStrength,
        condition:condition === 'E' ? 'E' : 'C'});
      setTopicResult(result);
      say('topic', 'notice', result.applied ? `Topic preview: ${plural(result.candidate_matches, 'item')} of the catalogue matched the text.` : result.message);
    } catch(e) {say('topic', 'error', e.message);} finally {setBusy(false);}
  }
  function resetUser() {
    setConfirmReset(false);
    act(() => api('reset', {user_id:user}).then(r => {setSteeringReset(n=>n+1);return r;}), 'Every control and all item feedback of this user is removed.', true);
  }
  const inline = where => messages[where] ? <p className={`alert inline ${messages[where].kind === 'error' ? 'error' : 'success'}`} role={messages[where].kind === 'error' ? 'alert' : 'status'}>{messages[where].text}</p> : null;
  const reviewedFeed = feedTool === 'steering' ? steeringFeed : semanticFeed;
  const languageReady = Boolean(semanticFeed || steeringFeed);
  const shownFeed = view === 'steering' ? reviewedFeed : feed;
  // What the served data is, in plain words. A bundled scenario has invented items.
  const dataKind = !status ? null : status.data_mode !== 'fixture' ? 'dataset' : status.source === 'deterministic fixture' ? 'fixture' : 'scenario';
  const diagnostic = status ? status.model_mode !== 'trained model' : false;
  const authored = status?.provider?.live_model === false, noProvider = Boolean(status) && !status.provider && status.local_models_allowed === false;
  // The original conditions C, D and E read category IDs of the form category_<number> only.
  const idsReadable = categoryIdsReadable(cats);
  const scorerWords = !status ? '' : diagnostic ? 'deterministic diagnostic scorer (a fixed formula, not the trained recommender)' : 'trained recommender';
  const disclosure = dataKind === 'scenario'
    ? 'The items of this scenario are invented for the demonstration. Each card shows an item ID and an invented description, not a playable video. The category and tag names are part of the invented data. The scores come from the scorer that the line above names. This demonstrator makes no claim about human agency or satisfaction.'
    : dataKind === 'fixture'
    ? 'The items are a built-in fixture, not the research dataset. Each card shows an item ID, not a playable video. The category names are placeholders. This demonstrator makes no claim about human agency or satisfaction.'
    : 'Each card shows an item ID of the processed dataset, not a playable video. Categories keep their original opaque IDs. This demonstrator makes no claim about human agency or satisfaction.';
  const dataNote = dataKind === 'scenario' ? `Data of this review: invented items of a bundled scenario. Scores: ${diagnostic ? 'the diagnostic scorer, a fixed formula' : 'the trained recommender'}.`
    : dataKind === 'fixture' ? 'Data of this review: the built-in fixture, not the research dataset.' : '';
  const viewIntro = view === 'steering'
    ? (noProvider ? 'Language controls. This server has no model provider, so only the manual category control works here. You choose an existing category, review the change and approve it. A deterministic filter applies exactly the set that you approved, and you can undo each change.'
      : `Language controls. ${authored ? 'A hand-written reply stands in for a model here.' : 'A model proposes a change from your words.'} The application checks the proposal, and you review it. A deterministic filter then applies exactly the set that you approved, in the same way as for a category that you choose by hand. A proposal does not change the feed, and you can undo each change.`)
      + ' Use this view to see how the controls behave. It does not measure accuracy or satisfaction.'
    : view === 'compare'
    ? 'Compare A to E. The first ten items of each condition for the same user and the same inputs. This is a preview of the current inputs, not an experimental result.'
    : 'Original study (A to E). The five conditions of the original proposal: item feedback (A), explanations (B), a free-text category instruction (C), an editable profile (D) and all channels (E). In C and E a parser reads one category instruction. In D and E it reads the profile, which can hold several categories. A fixed policy applies the result to the scores of the scorer that the status line names. The language model does not rank items. The view "Language controls" adds reviewed controls: a model proposes, the application checks, and you approve.';
  const profile = feed?.profile || {};
  const profileWords = profileText.trim() ? profileText.trim().split(/\s+/).length : 0;
  const palette = ['#536c4a', '#986949', '#546d88', '#8e6381', '#ad944a', '#547e79'];
  const color = category => palette[Math.max(0, cats.indexOf(category)) % palette.length];
  const language = view === 'steering', semanticTool = language && feedTool !== 'steering';
  const namedCategories = <p className="help" data-role="conditions-unavailable">The original conditions read category IDs of the form category_N. This data has named categories ({cats.slice(0, 4).join(', ')}{cats.length > 4 ? ', ...' : ''}), so the instruction and the profile are not available here, and C, D and E show the start list. To try C, D and E, start the built-in fixture: <code>python scripts/quickstart.py rehearse --scenario conditions</code></p>;
  const scoreLine = item => {
    if (!semanticTool || typeof item.score !== 'number') return `Base score ${item.base_score.toFixed(3)}${diagnostic ? ' (diagnostic formula)' : ''}`;
    const delta = item.score - item.base_score;
    return `Score ${item.score.toFixed(3)}${Math.abs(delta) > 1e-9 ? ` (base ${item.base_score.toFixed(3)} ${delta > 0 ? '+' : '-'} ${Math.abs(delta).toFixed(2)})` : ''}${diagnostic ? ' · diagnostic formula' : ''}`;
  };
  const cardLines = item => semanticTool ? controlLines(semanticGroups, item.item_id) : item.explanation;

  return <div className="app-shell">
    <header className="header"><a href="#main" className="brand"><span className="brand-mark">f<span>↗</span></span><span>feed control<span className="brand-sub">RESEARCH LAB</span></span></a><div className="header-right"><span className="research-tag">COMP 9500 · OFFLINE PROTOTYPE</span>{personal && <button type="button" className="text-button" onClick={onLock}>Lock session</button>}</div></header>
    <main id="main">
      {language
        ? <section className="intro compact"><div><p className="eyebrow">LANGUAGE CONTROLS</p><h1>Say what you want. Review it. Apply it. Undo it.</h1></div></section>
        : <section className="intro"><div><p className="eyebrow">YOUR PREFERENCES, MADE VISIBLE</p><h1>A feed you can <br/><em>steer.</em></h1><p className="lede">Explore how explanations, natural-language instructions and an editable profile change a recommendation list.</p></div><div className="intro-note"><span className="big-number">05</span><span>conditions.<br/>One scorer.<br/>Every control visible.</span></div></section>}
      {status && <section className="status-strip" aria-label="Research environment"><span className={`status-chip ${status.data_mode === 'fixture' ? 'fixture' : ''}`}><i/>{status.data_mode === 'fixture' ? 'FIXTURE DATA' : 'PROCESSED DATASET'}{dataKind === 'scenario' ? ' · INVENTED ITEMS' : ''}</span>
        <span>{scorerWords}</span><span>{language ? 'Language controls · each review names the provider and the model' : backend === 'rule' ? 'Rule parser · diagnostic only' : 'Ollama parser · actual request on submit'}</span><span>{plural(status.items, 'item')} · {plural(status.users, 'user')}</span>
        {status.provider ? <span className={`status-chip ${authored ? 'fixture' : ''}`} data-role="provider"><i/>{authored ? 'AUTHORED REPLIES · NO MODEL' : `PROVIDER · ${status.provider.backend} · ${status.provider.model}`}</span> : status.local_models_allowed === false && <span data-role="provider">No model provider · manual controls only</span>}</section>}
      <p className="disclosure">{disclosure}</p>
      {lost && <div className="alert error" role="alert">{lost === 'network' ? 'The page cannot reach the server. Check that the server runs, then reload the page. A server that was started again has no applied controls.' : 'The session has ended. The server was started again, or the session expired. The controls that this page shows are no longer on the server.'} <button type="button" className="text-button" onClick={() => window.location.reload()}>Reload the page</button></div>}
      <div className="toolbar"><label className="user-select">Research user<select value={user ?? ''} onChange={e => selectUser(e.target.value)} disabled={busy || !users.length}>{users.map(u => <option key={u.user_id} value={u.user_id}>User {u.user_id} · {plural(u.history_items, 'history item')}</option>)}</select></label><div className="view-tabs" role="group" aria-label="View"><button aria-pressed={view === 'feed'} className={view === 'feed' ? 'active' : ''} onClick={() => setView('feed')}>Original study (A to E)</button><button aria-pressed={view === 'compare'} className={view === 'compare' ? 'active' : ''} onClick={() => setView('compare')}>Compare A to E</button><button aria-pressed={language} className={language ? 'active' : ''} disabled={!languageReady} onClick={() => {setMessages({}); setView('steering');}}>Language controls</button></div>
        {confirmReset ? <span className="confirm-reset" role="group" aria-label="Confirm the reset"><span>Remove every control and all feedback of this user? You cannot undo this.</span> <button type="button" className="text-button" onClick={resetUser}>Yes, remove everything</button> <button type="button" className="text-button" onClick={() => setConfirmReset(false)}>Keep everything</button></span>
          : <button type="button" className="text-button" disabled={busy || user === null} onClick={() => setConfirmReset(true)}>Reset this user ↺</button>}</div>
      {languageMissing && <p className="help tab-note" data-role="language-unavailable">The view "Language controls" is not available here: no item descriptions are loaded, so there is nothing to match a request with. To use it, start a bundled scenario, for example <code>python scripts/quickstart.py rehearse --scenario tags</code>.</p>}
      <p className="view-intro" aria-label="About this view">{viewIntro}</p>
      <div className={`workspace ${language ? 'language' : ''}`}>
        <aside className="controls">
          {!language && <>
          <section className="panel"><div className="section-heading"><span className="step">01</span><h2>Choose a condition</h2></div><div className="conditions">{Object.entries(conditions).map(([key, [label]]) => <button key={key} aria-pressed={condition === key} className={`condition ${condition === key ? 'selected' : ''}`} disabled={busy || user === null} onClick={() => selectCondition(key)}><b>{key}</b><span>{label}</span><span className="radio-dot"/></button>)}</div><p className="help">{conditions[condition][1]}</p></section>
          <section className="panel" aria-label="Original category control"><div className="section-heading"><span className="step">02</span><h2>Original category control</h2></div>
            {!idsReadable && cats.length > 0 ? namedCategories : <>
            <label className="field-label" htmlFor="parser">Interpretation backend</label><select id="parser" value={backend} disabled={busy} onChange={e => {setBackend(e.target.value); say('control', null);}}><option value="rule">Rule parser (diagnostic)</option>{status?.local_models_allowed!==false&&<option value="ollama">Ollama (local LLM)</option>}</select><p className="help">{backend === 'rule' ? 'Original A to E: one existing category_N in each instruction. This diagnostic parser is not an LLM.' : `Uses ${status?.ollama_model || 'the configured model'}. Original A to E accepts one existing category_N. Backend errors are shown; no silent fallback.`}</p>
            <form onSubmit={e => {e.preventDefault(); act(() => api('control', {user_id:user, text:control, backend}), r => r.applied ? `Applied: ${OPERATION_WORDS[r.command.operation] || r.command.operation}${r.command.category ? ' ' + r.command.category : ''} (${r.command.source === 'rule' ? 'rule parser' : r.command.source}).` : 'Nothing was applied. Name one existing category_N and ask for more, less, mute or reset. For named subjects, use the view "Language controls".', false, 'control');}}><label className="field-label" htmlFor="control">What would you like to change?</label><textarea id="control" aria-describedby="control-shortcut" onKeyDown={e => {if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing) {e.preventDefault(); if (!busy && control.trim() && user !== null) e.currentTarget.form.requestSubmit();}}} maxLength={500} value={control} onChange={e => setControl(e.target.value)} placeholder={`Show me more ${cats[0] || 'category_0'}`} rows={3}/><div className="suggestions"><button type="button" onClick={() => setControl(`Show me more ${cats[0]}`)} disabled={!cats.length}>More {cats[0]}</button><button type="button" onClick={() => setControl(`Mute ${cats[1]}`)} disabled={cats.length < 2}>Mute {cats[1]}</button></div><button className="primary" disabled={busy || !control.trim() || user === null}>Apply instruction <span>↗</span></button></form>
            {inline('control')}
            <p className="help">Used by C and E. <span id="control-shortcut">Ctrl/Cmd+Enter applies the instruction.</span> One existing category_N in each instruction; the latest replaces the earlier one. Less or fewer means a hard mute. New names and graded decreases belong in the view "Language controls".</p></>}
            <button type="button" className="secondary" disabled={!languageReady || busy} onClick={() => {setMessages({}); setView('steering');}}>Open the language controls</button></section>
          <section className="panel" aria-label="Editable profile"><div className="section-heading"><span className="step">03</span><h2>Your editable profile</h2></div>
            {!idsReadable && cats.length > 0 ? <p className="help">Not available on this data, for the reason in panel 02.</p> : <>
            <form onSubmit={e => {e.preventDefault(); act(() => api('profile/text', {user_id:user, text:profileText, backend}), r => r.applied ? `Profile saved (${r.source === 'rule' ? 'rule parser' : r.source}).` : 'The profile was not clear. State explicit category preferences and try again. Nothing changed.', false, 'profile');}}><label className="field-label" htmlFor="profile">History context + your current preferences</label><textarea id="profile" maxLength={2000} rows={4} value={profileText} onChange={e => setProfileText(e.target.value)} placeholder={`More ${cats[0] || 'category_0'}. Mute ${cats[1] || 'category_1'}.`}/><div className="word-count">{profileWords}/200 words · Used by D and E</div><button className="secondary" disabled={busy || !profileText.trim() || profileWords > 200 || user === null}>Save profile</button></form>
            {inline('profile')}
            <div className="saved-profile"><span className="field-label">Parsed current preferences</span>{Object.keys(profile).length ? Object.entries(profile).map(([c,v]) => <div className="preference" key={c}><span><i style={{background:color(c)}}/>{c}</span><b>{v < 0 ? 'Muted' : `+${v.toFixed(2)}`}</b><button aria-label={`Remove ${c} preference`} disabled={busy} onClick={() => {const next={...profile}; delete next[c]; act(() => api('profile', {user_id:user,profile:next}, 'PUT'), `Removed ${c} from the profile.`, true, 'profile');}}>×</button></div>) : <p className="help">No saved category preferences.</p>}</div></>}</section>
          </>}
          <div hidden={!language}>
            <h2 className="aside-title">Language controls</h2>
            <SemanticPanel api={api} user={user} resetKey={steeringReset} defaultOpen categories={cats} scenarioRequests={status?.scenario_requests} provider={status?.provider} dataNote={dataNote}
              onFeed={(f, groups) => {setSemanticFeed(f); setSemanticGroups(groups || []); setFeedTool('semantic');}} onActive={() => setFeedTool('semantic')} onUnavailable={setLanguageMissing}
              portal={createPortal} reviewHost={language ? reviewHost : null}/>
          </div>
          <div hidden={!language}>
            <h2 className="aside-title">Fictional items (separate list)</h2>
            <SyntheticDraftPanel api={api} user={user} resetKey={steeringReset} scenarioRequests={status?.scenario_requests} provider={status?.provider}/>
          </div>
          <div hidden={!language}>
            <h2 className="aside-title">Earlier topic tool (exact phrases)</h2>
            <details><summary>Open the earlier topic tool</summary>
              <p className="help">This earlier tool matches exact phrases in the item text. Its language interpretation works with a local Ollama model only; without a local model it accepts phrases that you type. It keeps its own controls and its own feed, separate from the language controls above.</p>
              <SteeringPanel allowLocalModels={status?.local_models_allowed!==false} api={api} user={user} resetKey={steeringReset} onFeed={setSteeringFeed} onApplied={() => {setFeedTool('steering'); setView('steering');}}/>
            </details>
          </div>
          <details hidden={language}><summary>Earlier single-topic preview</summary>
          <section className="panel" aria-label="Exploratory semantic topic control">
            <div className="section-heading"><span className="step">04</span><h2>Explore a new topic</h2></div>
            <p className="help">An optional preview by exact text, outside the conditions A to E. It reads the item descriptions that the server loaded{dataKind === 'dataset' ? ' (the KuaiRec caption file)' : dataKind === 'scenario' ? ' (the invented descriptions of this scenario)' : ''}. No new video and no new category is created.</p>
            <p className="help">{languageMissing ? 'No item descriptions are loaded, so this preview is not available.' : 'Item descriptions are loaded. This is a preview only.'}</p>
            <form onSubmit={e => {e.preventDefault(); previewTopic();}}>
              <label className="field-label" htmlFor="topic-backend">Interpretation</label>
              <select id="topic-backend" value={topicBackend} disabled={busy} onChange={e => setTopicBackend(e.target.value)}>
                <option value="manual">Exact text (no model)</option>
                {status?.local_models_allowed!==false&&<option value="ollama">Local Ollama (real inference)</option>}
              </select>
              {topicBackend === 'manual' && <><label className="field-label" htmlFor="topic-operation">Action</label>
                <select id="topic-operation" value={topicOperation} disabled={busy} onChange={e => setTopicOperation(e.target.value)}>
                  <option value="boost">Show more</option><option value="reduce">Show less, still in the feed</option>
                  <option value="exclude">Remove from the feed</option>
                </select>{topicOperation !== 'exclude' && <><label className="field-label" htmlFor="topic-strength">Strength</label>
                  <select id="topic-strength" value={topicStrength} disabled={busy} onChange={e => setTopicStrength(e.target.value)}>
                    <option value="light">Light 0.10</option><option value="standard">Standard 0.25</option>
                    <option value="strong">Strong 0.40</option>
                  </select></>}</>}
              <label className="field-label" htmlFor="topic-text">{topicBackend === 'manual' ? 'Exact text to look for' : 'Natural-language request'}</label>
              <textarea id="topic-text" maxLength={500} rows={3} value={topicText}
                onChange={e => setTopicText(e.target.value)}
                placeholder={topicBackend === 'manual' ? (dataKind === 'dataset' ? '美食' : 'a word of an item description') : 'Show me more cooking videos'}/>
              <button className="secondary" disabled={busy || !topicText.trim() || user === null || Boolean(languageMissing) || !languageReady}>Preview topic feed</button>
            </form>
            {inline('topic')}
            {topicResult?.applied && <div className="saved-profile" role="status">
              <strong>{topicResult.command.operation === 'exclude' ? 'Remove' : topicResult.command.operation === 'boost' ? 'Show more' : 'Show less'}: {topicResult.command.topic}</strong>
              <p className="help">{topicResult.command.operation === 'exclude' ? 'removal' : `score ${topicResult.command.adjustment > 0 ? '+' : ''}${topicResult.command.adjustment.toFixed(2)}`} | {plural(topicResult.candidate_matches, 'item')} of the catalogue matched | {topicResult.top_k_match_count} of the first ten match | {plural(topicResult.available_items, 'eligible item')}</p>
              {topicResult.command.rejected_terms?.length > 0 && <p className="help">Search words of the model that were not used: {topicResult.command.rejected_terms.join(', ')}</p>}
              <p className="help">First ten: {topicResult.items.map(item => `${item.item_id}${item.topic_text_match ? '*' : ''}`).join(', ')}</p>
              <p className="help">* the item text holds the words. This preview is not a relevance judgement and not evidence of the A to E study.</p>
            </div>}
          </section>
          </details>
        </aside>
        <section className="results" aria-busy={busy}>
          <div className="results-header"><div><p className="eyebrow">{language ? (feedTool === 'steering' ? 'EARLIER TOPIC TOOL · ITS OWN FEED' : `LANGUAGE CONTROLS · APPLIED FEED${dataKind === 'scenario' ? ' · INVENTED ITEMS' : ''}${diagnostic ? ' · DIAGNOSTIC SCORER' : ''}`) : view !== 'compare' ? `CONDITION ${condition} · LIVE LOCAL PREVIEW` : 'WITHIN-SESSION COMPARISON'}</p><h2>{language ? (feedTool === 'steering' ? 'The feed of the earlier topic tool' : 'The feed with your applied controls') : view === 'feed' ? 'Your recommendation list' : 'One input. Five conditions.'}</h2></div>{view !== 'compare' && <label className="signal-toggle"><input type="checkbox" checked={showSignals} onChange={e => setShowSignals(e.target.checked)}/> Show signals</label>}</div>
          {inline('page')}
          {language && feedTool === 'steering' && semanticFeed && <p className="help">The cards show the feed of the earlier topic tool. <button type="button" className="text-button" onClick={() => setFeedTool('semantic')}>Show the feed of the language controls</button></p>}
          {language && <div ref={setReviewHost} className="review-host"/>}
          {view !== 'compare' && <div className="metrics"><div><b>{shownFeed?.items.length ?? ' - '}<small>/10</small></b><span>list fill</span></div><div><b>{Object.keys(shownFeed?.category_exposure || {}).length}</b><span>{Object.keys(shownFeed?.category_exposure || {}).length === 1 ? 'category shown' : 'categories shown'}</span></div><div><b>{language ? reviewedFeed?.commands_count ?? 0 : feed?.feedback_count ?? 0}</b><span>{language ? ((reviewedFeed?.commands_count ?? 0) === 1 ? 'applied control' : 'applied controls') : ((feed?.feedback_count ?? 0) === 1 ? 'item preference' : 'item preferences')}</span></div></div>}
          {!language && feed?.command?.category && <div className="active-instruction">Latest instruction: <strong>{OPERATION_WORDS[feed.command.operation] || feed.command.operation} {feed.command.category}</strong><span>{feed.command.source === 'rule' ? 'rule parser' : feed.command.source}</span></div>}
          {busy && !shownFeed && <div className="empty-state" role="status">Preparing your research session…</div>}
          {!language && view === 'feed' && showSignals && dataKind === 'scenario' && ['B', 'E'].includes(condition) && <p className="help" data-role="template-note">The explanation lines are templates that were written for the research dataset, where categories are opaque IDs and a trained model gives the scores. On this invented scenario they are not exact: the category names are known here, and the scores come from the diagnostic scorer.</p>}
          {view !== 'compare' ? <><div className="feed-grid">{shownFeed?.items.map(item => { const lines = cardLines(item) || []; return <article className="item-card" key={item.item_id}><div className="item-art" style={{'--category-color':color(item.categories[0])}}><span className="rank">{String(item.rank).padStart(2,'0')}</span><div className="art-lines"><i/><i/><i/></div><span className="asset-type">ITEM METADATA</span><strong>{String(item.item_id).padStart(4,'0')}</strong></div><div className="item-body"><div className="item-title"><h3>Item {item.item_id}</h3><span>#{item.rank}</span></div><div className="category-pills">{item.categories.map(c => <span key={c}><i style={{background:color(c)}}/>{c}</span>)}</div>{language && item.source_text && <p className="item-source">{item.source_text}</p>}{showSignals && <div className="signals">{lines.length > 0 && <span className="explanation-origin">{language ? (feedTool === 'steering' ? 'Earlier topic tool' : 'Applied language control') : item.explanation_source === 'ollama_constrained_fact_selection' ? 'Cached LLM selection of template facts' : 'Template text · no LLM'}</span>}{lines.length ? lines.map((s,i) => <p key={i}>{s}</p>) : <p>{language ? 'No applied control changes this item.' : 'Explanations are available in B and E. Showing this panel does not change ranking.'}</p>}</div>}<div className="item-footer"><span>{scoreLine(item)}</span><div style={{display:language ? 'none' : undefined}}><button disabled={busy} aria-label={`Like item ${item.item_id}`} title="Boost only this item" onClick={() => act(() => api('feedback', {user_id:user,item_id:item.item_id,direction:'like'}), `Positive feedback saved for item ${item.item_id} only. A and B use it.`)}>＋</button><button disabled={busy} aria-label={`Dislike item ${item.item_id}`} title="Remove only this item from A and B" onClick={() => act(() => api('feedback', {user_id:user,item_id:item.item_id,direction:'dislike'}), `Item ${item.item_id} is removed from A and B.`)}>−</button></div></div></div></article>; })}</div>{shownFeed && !shownFeed.items.length && <div className="empty-state"><h3>No eligible items remain.</h3><p>{language ? 'The applied controls remove every item. Undo the last change, or remove the applied controls.' : 'Your mute preferences remove every item. Remove a preference or reset this user.'}</p></div>}</> : <div className="comparison"><p className="help">This is a preview of current inputs, not an experimental result. A and B must have identical item IDs. Exposure counts may overlap for multi-category items.</p><div className="comparison-scroll" tabIndex={0} role="region" aria-label="Comparison of the five conditions. It can scroll sideways."><table><thead><tr><th scope="col">Condition</th><th scope="col">First 10 item IDs</th><th scope="col">Category counts</th><th scope="col">Fill</th></tr></thead><tbody>{Object.entries(comparison || {}).map(([c,f]) => <tr key={c}><th scope="row"><b>{c}</b>{conditions[c][0]}</th><td>{f.items.map(i => i.item_id).join(' · ') || 'Empty'}</td><td>{Object.entries(f.category_exposure).map(([cat,count]) => <span className="table-category" key={cat}><i style={{background:color(cat)}}/>{cat}: {count}</span>)}</td><td>{(100*f.fill_rate).toFixed(0)}%</td></tr>)}</tbody></table></div><p className="help narrow-only">The table is wider than the screen. Move it sideways.</p><div className="comparison-check">A and B have the same item IDs in the same order: <strong>{comparison && JSON.stringify(comparison.A.items.map(i=>i.item_id)) === JSON.stringify(comparison.B.items.map(i=>i.item_id)) ? 'yes, in this preview' : 'no'}</strong></div></div>}
        </section>
      </div>
      <footer><span>Feed Control Lab · Research demonstrator</span><span>Session state is temporary. A reload of the page starts a new session without the applied controls.</span></footer>
    </main>
  </div>;
}

function PersonalEntry() {
  const personal = document.documentElement.dataset.personalAuth === 'required';
  const [client] = useState(() => createApiClient({personal}));
  const [unlocked, setUnlocked] = useState(!personal);
  const [draft, setDraft] = useState('');
  const [checking, setChecking] = useState(false);
  const [authError, setAuthError] = useState('');
  async function submit(event) {
    event.preventDefault();
    if (!draft || checking) return;
    setChecking(true); setAuthError('');
    const ok = await client.unlock(draft);
    setDraft(''); setChecking(false);
    if (ok) setUnlocked(true); else setAuthError('Could not unlock this personal session. Check the token and try again.');
  }
  function lock() {client.lock(); setDraft(''); setAuthError(''); setUnlocked(false);}
  if (unlocked) return <App client={client} personal={personal} onLock={lock}/>;
  return <main className="personal-entry"><section className="panel" aria-labelledby="personal-title">
    <p className="eyebrow">PERSONAL LOOPBACK SESSION</p><h1 id="personal-title">Unlock the research app</h1>
    <p className="help">Enter the operator token supplied for this local session. It stays in this page’s memory and is cleared when you lock or reload.</p>
    <form onSubmit={submit} autoComplete="off"><label className="field-label" htmlFor="personal-token">Operator token</label>
      <input id="personal-token" type="password" autoComplete="off" spellCheck={false} value={draft}
        onChange={e => setDraft(e.target.value)} disabled={checking} />
      <button type="submit" className="primary" disabled={checking || !draft}>{checking ? 'Checking…' : 'Unlock'}</button>
    </form>{authError && <p role="alert" className="alert error">{authError}</p>}
  </section></main>;
}

createRoot(document.getElementById('root')).render(<PersonalEntry/>);
