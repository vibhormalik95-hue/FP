import React, { useEffect, useRef, useState } from 'react';


// Language controls over the real KuaiRec feed. The model proposes; the server checks; the
// person reviews; Apply changes exactly the reviewed set; Undo restores the previous state.
// Nothing in this file knows any example request, label or item.

const KINDS = {feature: 'KuaiRec feature ID', category: 'KuaiRec category', tag: 'Topic tag', custom: 'New category (yours)'};
const ACTIONS = {boost: 'Show more', reduce: 'Show less', hide: 'Hide', only: 'Show only'};
const STRENGTHS = ['light', 'standard', 'strong'];
const PROVIDER_DEFAULTS = {
  mock: {model: 'mock-literal-v1', note: 'No AI. Literal word matching for tests; it cannot read indirect requests.'},
  openai: {model: 'gpt-5-mini', note: 'OpenAI API with your key. Leave the key empty to use OPENAI_API_KEY.'},
  anthropic: {model: 'claude-sonnet-5-5', note: 'Anthropic API with your key. Leave the key empty to use ANTHROPIC_API_KEY.'},
  ollama: {model: 'qwen2.5-coder:7b-instruct', note: 'A local model served by Ollama on this computer. No key.'},
  'claude-cli': {model: 'claude-sonnet-5-5', note: 'The Claude CLI signed in on this computer. Author\'s machine only.'},
};
const STAGES = {
  interpret: ['Sending the request and the label list to the model…', 'The model chooses existing labels…', 'The server checks every label and the quoted span…'],
  define: ['Sending the description and this user\'s top items to the model…', 'The model drafts a label and a definition…', 'The server checks every quotation…'],
  classify: ['Classifying every item in scope, ten per call, four calls at a time…', 'Each verdict needs an exact quotation…', 'A separate call checks each cited quotation without seeing the verdict…', 'The server keeps only matches whose quotation exists and passed the check…'],
  'new-items': ['Sending the new items and the existing labels to the model…', 'The model picks existing categories and tags…', 'The server drops any label that does not exist…'],
};

const fmtUsd = v => (typeof v === 'number' ? `USD ${v.toFixed(4)}` : 'cost n/a');

function FeedCard({item, mark}) {
  return <article className={`lab-card ${mark || ''}`} data-item={item.item_id}>
    <div className="lab-card-head"><b>#{item.rank}</b><span>Item {item.item_id}{item.origin === 'added' ? ' · added by you' : ''}</span><em>{item.score.toFixed(3)}{Math.abs(item.score - item.base_score) > 1e-9 ? ` (base ${item.base_score.toFixed(3)})` : ''}</em></div>
    <p className="lab-gloss lab-gloss-main">{[item.title, item.caption !== item.title && item.caption].filter(Boolean).join(' · ') || '(no text in KuaiRec)'}</p>
    <div className="lab-pills">{item.kuairec_categories.map(c => <span key={c}>{c}</span>)}{item.tags.slice(0, 4).map(t => <span key={t} className="tag">#{t}</span>)}</div>
    {item.controls.length > 0 && <p className="lab-ctl">{[...new Set(item.controls.map(c => { const m = c.match(/^(Show more|Show less|Hide|Show only)[^:]*:[^']*'([^']+)'/); return m ? `${{'Show more': '↑', 'Show less': '↓', 'Hide': '×', 'Show only': '='}[m[1]]} ${m[2]}` : c; }))].join('  ')}</p>}
  </article>;
}

function FeedColumn({state, preview, side, setSide}) {
  const showing = preview ? (side === 'before' ? preview.before : preview.after) : state?.feed;
  const changes = preview?.changes;
  const mark = id => !preview || side === 'before' ? (changes && side === 'before' && changes.left.includes(id) ? 'left' : '')
    : changes.entered.includes(id) ? 'entered' : changes.moved_up.includes(id) ? 'up' : changes.moved_down.includes(id) ? 'down' : '';
  return <aside className="lab-feed" aria-label="Feed">
    <div className="lab-feed-head">
      <div><p className="eyebrow">{preview ? 'PREVIEW · NOT APPLIED' : 'CURRENT FEED · TRAINED SASREC RANKING'}</p>
        <h2>{preview ? (side === 'before' ? 'Feed before' : 'Feed after Apply') : 'Top ten for this user'}</h2></div>
      {preview && <div className="view-tabs" role="group" aria-label="Before or after"><button className={side === 'before' ? 'active' : ''} onClick={() => setSide('before')}>Before</button><button className={side === 'after' ? 'active' : ''} onClick={() => setSide('after')}>After</button></div>}
    </div>
    {showing && <p className="help lab-count">{showing.eligible} of {showing.catalogue} eligible{changes ? ` · ${changes.entered.length} enter, ${changes.left.length} leave the top ten` : ''}</p>}
    <div className="lab-feed-list">{showing?.items.map(item => <FeedCard key={item.item_id} item={item} mark={mark(item.item_id)}/>)}</div>
    {showing && !showing.items.length && <div className="empty-state">No eligible items remain.</div>}
  </aside>;
}

function Checks({checks}) {
  if (!checks?.length) return null;
  const ok = checks.filter(c => c.ok).length;
  return <details className="lab-checks-box"><summary className={ok === checks.length ? 'ok' : 'bad'}>{ok === checks.length ? '✓' : '✗'} {ok} of {checks.length} checks passed</summary>
    <ul className="lab-checks">{checks.map((c, i) => <li key={i} className={c.ok ? 'ok' : 'bad'}>{c.ok ? '✓' : '✗'} {c.check}</li>)}</ul></details>;
}

function Calls({calls}) {
  if (!calls?.length) return null;
  const total = calls.reduce((s, c) => s + (c.cost_usd || 0), 0);
  return <details className="lab-calls"><summary>{calls.length} model call(s) · {fmtUsd(total)} · {calls.map(c => c.latency_s).filter(Boolean).reduce((a, b) => a + b, 0).toFixed(1)} s total</summary>
    <table><thead><tr><th>Task</th><th>Provider · model</th><th>Seconds</th><th>Tokens in/out</th><th>Cost</th></tr></thead>
      <tbody>{calls.map((c, i) => <tr key={i}><td>{c.task}</td><td>{c.provider} · {c.served_by || c.model}</td><td>{c.latency_s ?? '-'}</td><td>{c.input_tokens ?? '-'} / {c.output_tokens ?? '-'}</td><td>{c.error ? `error: ${c.error}` : fmtUsd(c.cost_usd)}</td></tr>)}</tbody></table></details>;
}

function EvidenceRows({preview}) {
  if (preview.kind === 'interpret') return <div className="lab-evidence">{preview.evidence.map((e, i) => <div key={i} className="lab-ev"><b>{ACTIONS[e.action] || e.action}{e.strength && ['boost', 'reduce'].includes(e.action) ? ` (${e.strength})` : ''}</b> for “{e.intent_span}”<p>{e.relation}</p></div>)}</div>;
  if (preview.kind === 'new-category') return <div className="lab-table-wrap"><table className="lab-table"><thead><tr><th>Item</th><th>Text (KuaiRec, English)</th><th>Verdict</th><th>Quotation</th><th>Evidence check</th><th>Selected</th></tr></thead><tbody>
    {preview.evidence.map(r => <tr key={r.item_id} className={r.selected ? 'sel' : ''}><td>{r.item_id}</td><td>{r.title || r.caption || '(no text)'}</td><td>{r.verdict}</td><td>{r.quote ? <><q>{r.quote}</q> <small>{r.field}{r.quote_verified ? ' · found' : ' · NOT FOUND'}</small></> : '-'}<small className="lab-reason">{r.reason}</small></td><td>{r.assessment ? (r.assessment.supports ? 'supports' : 'does not support') : '-'}<small className="lab-reason">{r.assessment?.reason}</small></td><td>{r.selected ? 'yes' : 'no'}</td></tr>)}</tbody></table></div>;
  if (preview.kind === 'new-items') return <div className="lab-evidence">{preview.evidence.map(e => <div key={e.item_id} className="lab-ev"><b>{e.title}</b> → categories: {e.categories.length ? e.categories.map(c => <code key={c}>{c}</code>) : 'none'}; tags: {e.tags.length ? e.tags.map(t => <code key={t}>#{t}</code>) : 'none'}<p>{e.category_reason}</p>{e.new_categories.map(n => <p key={n.label}>New category <b>{n.label}</b>: {n.verdict}{n.quote ? <> · <q>{n.quote}</q></> : ''} · {n.selected ? 'selected' : 'not selected'}</p>)}</div>)}</div>;
  return null;
}

function Review({preview, onApply, onDiscard, busy}) {
  return <section className="lab-review" aria-label="Review" data-role="review">
    <p className="eyebrow">REVIEW · {preview.kind.toUpperCase()}</p>
    <h3>{preview.summary}</h3>
    <div className="lab-blocks">
      <div><h4>1 · What came back</h4>
        {preview.proposal?.status && <p>Model status: <b>{preview.proposal.status}</b>{preview.proposal.reason ? ` · ${preview.proposal.reason}` : ''}</p>}
        <EvidenceRows preview={preview}/>
        {preview.controls.length > 0 && <><h4>Controls that Apply would add</h4><ul className="lab-controls">{preview.controls.map(c => <li key={c.id}>{c.text}</li>)}</ul></>}

      </div>
      <div><h4>2 · What the application checked</h4><Checks checks={preview.checks}/>{preview.notes.map((n, i) => <p key={i} className="help">{n}</p>)}<Calls calls={preview.calls}/></div>
      <div><h4>3 · Your decision</h4>
        <p className="help">Eligible videos: {preview.changes.eligible_before} → {preview.changes.eligible_after}.</p>

        <div className="lab-buttons"><button className="primary" data-role="apply" disabled={busy || !preview.applicable} onClick={onApply}>Apply <span>↗</span></button><button className="secondary" data-role="discard" disabled={busy} onClick={onDiscard}>Discard</button></div>
        {!preview.applicable && <p className="help">Nothing to apply: the proposal changed nothing after the checks.</p>}
      </div>
    </div>
  </section>;
}

function ProviderBar({status, api, onChange}) {
  const current = status?.provider;
  const [kind, setKind] = useState(current?.provider || 'mock');
  const [model, setModel] = useState(current?.model || PROVIDER_DEFAULTS.mock.model);
  const [key, setKey] = useState(''), [baseUrl, setBaseUrl] = useState(''), [effort, setEffort] = useState('low'), [msg, setMsg] = useState('');
  useEffect(() => { if (current) { setKind(current.provider); setModel(current.model || ''); } }, [current?.provider, current?.model]);
  const choose = k => { setKind(k); setModel(PROVIDER_DEFAULTS[k].model); setMsg(''); };
  async function save(e) {
    e.preventDefault(); setMsg('');
    try { await api('lab/provider', {kind, model, effort, api_key: key || undefined, base_url: baseUrl || undefined}); setKey(''); setMsg('Provider set. The key is held in the server\'s memory only.'); onChange(); }
    catch (err) { setMsg(err.message); }
  }
  const keyed = kind === 'openai' || kind === 'anthropic';
  return <form className="lab-provider" onSubmit={save} autoComplete="off" data-role="provider">
    <label>Model provider<select value={kind} onChange={e => choose(e.target.value)} data-role="provider-kind">{Object.entries(status?.providers || {}).map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
    <label>Model<input value={model} onChange={e => setModel(e.target.value)} spellCheck={false} data-role="provider-model"/></label>
    {keyed && <label>API key<input type="password" value={key} onChange={e => setKey(e.target.value)} placeholder={status?.env_keys?.[kind] ? 'empty = use the environment variable' : 'paste your key'} autoComplete="new-password" spellCheck={false} data-role="api-key"/></label>}
    {(kind === 'ollama' || kind === 'openai') && <label>Base URL<input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder={kind === 'ollama' ? 'http://127.0.0.1:11434/v1' : 'https://api.openai.com/v1'} spellCheck={false}/></label>}
    {(kind === 'openai' || kind === 'anthropic' || kind === 'claude-cli') && <label>Reasoning effort<select value={effort} onChange={e => setEffort(e.target.value)} data-role="provider-effort">{(kind === 'openai' ? ['minimal', 'low', 'medium', 'high'] : ['low', 'medium', 'high']).map(x => <option key={x} value={x}>{x}{x === 'low' ? ' (measured)' : ''}</option>)}</select></label>}
    <button className="secondary" data-role="provider-save">Use this provider</button>
    <p className="help">Now: <b>{current?.label} · {current?.model}{current?.effort ? ` · effort ${current.effort}` : ''}</b> · spent {fmtUsd(current?.spent_usd)}.{msg && <> {msg}</>}</p>
  </form>;
}

function LabelPicker({api, user, kind, value, onPick}) {
  const [q, setQ] = useState(''), [labels, setLabels] = useState([]);
  useEffect(() => { let live = true; api(`lab/labels?user_id=${user}&kind=${kind}&q=${encodeURIComponent(q)}&limit=60`).then(r => live && setLabels(r.labels)).catch(() => {}); return () => { live = false; }; }, [kind, q, user]);
  return <div className="lab-picker"><input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter labels" data-role="label-filter"/>
    <select size={7} value={value} onChange={e => onPick(e.target.value)} data-role="label-list">{labels.map(l => <option key={l.term_id} value={l.value} onClick={() => onPick(l.value)}>{l.value} · {l.item_count} items</option>)}</select></div>;
}

export function LabView({api, user, status, onStatus}) {
  const [tab, setTab] = useState('manual'), [state, setState] = useState(null), [preview, setPreview] = useState(null);
  const [side, setSide] = useState('after'), [busy, setBusy] = useState(false), [error, setError] = useState(''), [stage, setStage] = useState(null);
  const [auto, setAuto] = useState(false);
  const [kind, setKind] = useState('category'), [values, setValues] = useState([]), value = values[values.length - 1] || '', setValue = v => setValues(v ? [v] : []), addValue = v => setValues(vs => vs.includes(v) ? vs : [...vs, v]), [action, setAction] = useState('hide'), [strength, setStrength] = useState('standard');
  const [request, setRequest] = useState(''), [description, setDescription] = useState(''), [definition, setDefinition] = useState(null);
  const [catAction, setCatAction] = useState('only'), [scope, setScope] = useState(40);
  const SCOPES = [10, 20, 40, 80, 120, 200];
  const [newItems, setNewItems] = useState([{title: '', description: ''}]);
  const timer = useRef(null);

  const refresh = () => api(`lab/state?user_id=${user}`).then(setState).catch(e => setError(e.message));
  useEffect(() => { if (user !== null) { setPreview(null); setDefinition(null); refresh(); } }, [user]);
  useEffect(() => () => clearInterval(timer.current), []);

  async function run(task, fn, after) {
    setBusy(true); setError(''); const started = Date.now(); const lines = STAGES[task] || [];
    setStage(lines.length ? {text: lines[0], s: 0} : null);
    clearInterval(timer.current);
    if (lines.length) timer.current = setInterval(() => { const s = Math.round((Date.now() - started) / 1000); setStage({text: lines[Math.min(Math.floor(s / 6), lines.length - 1)], s}); }, 1000);
    try { const r = await fn(); after(r); window.labDone = (window.labDone || 0) + 1; } catch (e) { setError(e.message); window.labLastError = e.message; window.labDone = (window.labDone || 0) + 1; } finally { clearInterval(timer.current); setStage(null); setBusy(false); onStatus(); }
  }
  const showPreview = async p => { window.labLastPreview = {id: p.preview_id, kind: p.kind, changes: p.changes, calls: p.calls, controls: p.controls.map(c => c.text), notes: p.notes, applicable: p.applicable, selected: (p.evidence || []).filter(r => r.selected).length, rows: (p.evidence || []).length}; setPreview(p); setSide('after'); if (auto && p.applicable) await apply(p); };
  async function apply(p = preview) { await run('apply', () => api('lab/apply', {user_id: user, preview_id: p.preview_id}), s => { setState(s); setPreview(null); setValues([]); }); }
  const undo = () => run('undo', () => api('lab/undo', {user_id: user}), s => { setState(s); setPreview(null); });
  const reset = () => run('reset', () => api('lab/reset', {user_id: user}), s => { setState(s); setPreview(null); setDefinition(null); });

  const tabs = [['manual', '1 · Choose a category'], ['interpret', '2 · Say it your way'], ['category', '3 · New category'], ['items', '4 · New items']];
  return <div className="lab">
    <ProviderBar status={status} api={api} onChange={onStatus}/>
    <div className="lab-grid">
      <section className="lab-main">
        <div className="lab-tabs" role="tablist">{tabs.map(([k, label]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'active' : ''} onClick={() => { setTab(k); setError(''); }} data-tab={k}>{label}</button>)}
          <label className="lab-auto"><input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} data-role="auto-apply"/> Auto-apply</label></div>

        {tab === 'manual' && <form className="panel" onSubmit={e => { e.preventDefault(); run('manual', () => api('lab/manual', {user_id: user, kind, value, values, action, strength}), showPreview); }}>
          <p className="help">Pick a label and an action. No model.</p>
          <div className="lab-row"><label>Label type<select value={kind} onChange={e => { setKind(e.target.value); setValue(''); }} data-role="manual-kind">{Object.entries(KINDS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            <label>Action<select value={action} onChange={e => setAction(e.target.value)} data-role="manual-action">{Object.entries(ACTIONS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            {['boost', 'reduce'].includes(action) && <label>Strength<select value={strength} onChange={e => setStrength(e.target.value)} data-role="lab-strength">{STRENGTHS.map(s => <option key={s}>{s}</option>)}</select></label>}</div>
          <LabelPicker api={api} user={user} kind={kind} value={value} onPick={addValue}/>
          {values.length > 0 && <div className="lab-picked" data-role="picked">{values.map(v => <span key={v}>{v} <button type="button" aria-label={`Remove ${v}`} onClick={() => setValues(values.filter(x => x !== v))}>×</button></span>)}</div>}
          <button className="primary" disabled={busy || !values.length} data-role="manual-preview">Preview <span>↗</span></button></form>}

        {tab === 'interpret' && <form className="panel" onSubmit={e => { e.preventDefault(); run('interpret', () => api('lab/interpret', {user_id: user, request}), showPreview); }}>
          <p className="help">Say what you want. No category name needed.</p>
          <textarea value={request} onChange={e => setRequest(e.target.value)} rows={3} maxLength={1000} placeholder="Your request" data-role="request"/>
          <button className="primary" disabled={busy || !request.trim()} data-role="interpret-preview">Interpret and preview <span>↗</span></button></form>}

        {tab === 'category' && <div className="panel">
          <form onSubmit={e => { e.preventDefault(); run('define', () => api('lab/define', {user_id: user, description, scope_size: scope}), d => { window.labLastDefinition = {label: d.label, status: d.status, evidence: d.evidence.length, calls: d.calls}; setDefinition(d); }); }}>
            <p className="help">Describe a category KuaiRec does not have.</p>
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} maxLength={1000} placeholder="Describe the new category" data-role="category-description"/>
            <label className="lab-inline">Scope: this user's top <select value={scope} onChange={e => setScope(Number(e.target.value))} data-role="scope">{SCOPES.map(n => <option key={n} value={n}>{n}</option>)}</select> items</label>
            <button className="primary" disabled={busy || !description.trim()} data-role="define">Propose a definition <span>↗</span></button></form>
          {definition && <form className="lab-definition" data-role="definition" onSubmit={e => { e.preventDefault(); run('classify', () => api('lab/classify', {user_id: user, label: definition.label, definition: definition.definition, action: catAction, scope_size: scope}), showPreview); }}>
            <p className="eyebrow">STEP 1 RESULT · REVIEW THE DEFINITION</p>
            <p>Model status: <b>{definition.status}</b>{definition.duplicate ? ' · this label already exists' : ''}</p>
            {definition.alternatives?.length > 0 && <p className="help">Competing readings: {definition.alternatives.join('; ')}</p>}
            <label>Label<input value={definition.label} onChange={e => setDefinition({...definition, label: e.target.value})} data-role="definition-label"/></label>
            <label>Definition<textarea rows={4} value={definition.definition} onChange={e => setDefinition({...definition, definition: e.target.value})} data-role="definition-text"/></label>
            <p className="help">{definition.rationale}</p>
            <ul className="lab-checks">{definition.evidence.map((ev, i) => <li key={i} className={ev.quote_verified ? 'ok' : 'bad'}>{ev.quote_verified ? '✓' : '✗'} item {ev.item_id}: <q>{ev.quote}</q> ({ev.field}) · {ev.reason}</li>)}</ul>
            <Calls calls={definition.calls}/>
            <label>When applied<select value={catAction} onChange={e => setCatAction(e.target.value)} data-role="category-action">{Object.entries(ACTIONS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            <button className="primary" disabled={busy || definition.status !== 'propose' || !definition.label || !definition.definition} data-role="classify">Approve the definition and classify <span>↗</span></button></form>}
        </div>}

        {tab === 'items' && <form className="panel" onSubmit={e => { e.preventDefault(); run('new-items', () => api('lab/new-items', {user_id: user, items: newItems}), showPreview); }}>
          <p className="help">Add videos that are not in KuaiRec.</p>
          {newItems.map((it, i) => <div key={i} className="lab-newitem"><input value={it.title} onChange={e => setNewItems(newItems.map((x, j) => j === i ? {...x, title: e.target.value} : x))} placeholder="Title" data-role={`new-title-${i}`}/><textarea rows={2} value={it.description} onChange={e => setNewItems(newItems.map((x, j) => j === i ? {...x, description: e.target.value} : x))} placeholder="Description" data-role={`new-description-${i}`}/></div>)}
          <div className="lab-buttons"><button type="button" className="secondary" disabled={newItems.length >= 10} onClick={() => setNewItems([...newItems, {title: '', description: ''}])} data-role="add-row">Add another item</button>
            <button className="primary" disabled={busy || !newItems.some(x => x.title.trim() && x.description.trim())} data-role="new-items-preview">Classify and preview <span>↗</span></button></div></form>}

        {stage && <div className="lab-stage" role="status" data-role="stage">{stage.text} <b>{stage.s}s</b></div>}
        {error && <div className="alert error" role="alert" data-role="error">{error}</div>}
        {preview && <Review preview={preview} busy={busy} onApply={() => apply()} onDiscard={() => setPreview(null)}/>}

        <section className="panel lab-applied" data-role="applied"><h4>Applied now</h4>
          {state?.controls.length ? <ul className="lab-controls">{state.controls.map(c => <li key={c.id}>{c.text}</li>)}</ul> : <p className="help">No control is applied. The feed is the trained recommender's ranking.</p>}
          {state && Object.values(state.custom).map(c => <p key={c.label} className="help"><b>{c.label}</b>: {c.members.length} member(s). {c.definition}</p>)}
          {state?.added.length > 0 && <p className="help">Added items: {state.added.map(a => `${a.item_id} ${a.title}`).join(' · ')}</p>}
          <div className="lab-buttons"><button className="secondary" disabled={busy || !state?.can_undo} onClick={undo} data-role="undo">Undo the last change</button><button className="text-button" disabled={busy} onClick={reset} data-role="lab-reset">Reset this user</button></div>
        </section>
      </section>
      <FeedColumn state={state} preview={preview} side={side} setSide={setSide}/>
    </div>
  </div>;
}

function Table({table}) {
  return <div className="lab-table-wrap"><h4>{table.title}</h4><table className="lab-table"><thead><tr>{table.columns.map(c => <th key={c}>{c}</th>)}</tr></thead>
    <tbody>{table.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(4)) : String(v ?? '')}</td>)}</tr>)}</tbody></table>{table.note && <p className="help">{table.note}</p>}</div>;
}

export function ResultsView({api}) {
  const [data, setData] = useState(null), [error, setError] = useState('');
  useEffect(() => { api('lab/results').then(setData).catch(e => setError(e.message)); }, []);
  if (error) return <div className="alert error">{error}</div>;
  if (!data) return <p className="help">Loading the result files…</p>;
  if (!data.runs.length) return <div className="empty-state">No measured results yet. They appear here after <code>scripts/lab_eval.py</code> writes a run under docs/evidence/{data.folder}/.</div>;
  return <div className="lab-results" data-role="results">{data.runs.map(run => <section key={run.run} className="panel"><p className="eyebrow">RUN {run.run}</p><h3>{run.title || 'Measured results'}</h3>
    {run.text_label && <p className="lab-text-label" data-role="text-label"><b>{run.text_label}</b></p>}
    {run.status_note && <p className="help">{run.status_note}</p>}
    {(run.tables || []).map((t, i) => <Table key={i} table={t}/>)}</section>)}</div>;
}
