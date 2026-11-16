import {callSummary, changeSentence, money, providerLine, seconds, validNewItems, verdictLabel} from './logic.js';

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
let state = null, preview = null, titles = {}, lastFlash = [];

async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
  const res = await fetch(path, {method, headers: {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await res.json().catch(() => ({error: `HTTP ${res.status}`}));
  if (!res.ok) throw new Error(data.error || data.detail?.[0]?.msg || `HTTP ${res.status}`);
  return data;
}

async function busy(text, fn) {
  $('busy-text').textContent = text; $('busy').hidden = false;
  document.querySelectorAll('button').forEach(b => b.dataset.wasDisabled = b.disabled ? '1' : '');
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  try { return await fn(); }
  finally {
    $('busy').hidden = true;
    document.querySelectorAll('button').forEach(b => b.disabled = b.dataset.wasDisabled === '1');
    renderUndo();
  }
}

// ---------------------------------------------------------------- state & feed
async function refresh() {
  state = await api('/api/state');
  titles = Object.fromEntries(state.items.map(i => [i.id, i.title]));
  render();
}

function render() {
  $('provider-line').textContent = providerLine(state.provider);
  $('spend').textContent = money(state.spend_usd);
  const f = state.feed;
  $('feed-count').textContent = `(top ${f.top.length} of ${f.eligible} eligible · ${f.catalogue} in catalogue)`;
  $('feed').innerHTML = f.top.map(r => `<li class="${lastFlash.includes(r.id) ? 'flash' : ''}" data-id="${esc(r.id)}">
      ${esc(r.title)}${r.origin === 'added' ? '<span class="badge new">NEW</span>' : ''}
      <div class="cat">${esc(r.category)} · score ${r.score.toFixed(2)} · ${esc(r.id)}</div></li>`).join('');
  $('controls').innerHTML = state.controls.length
    ? state.controls.map(c => `<li>${esc(c.text)} <span class="muted">(${esc(c.source)})</span></li>`).join('')
    : '<li class="muted">None yet</li>';
  renderUndo();
  fillManualValues();
}

function renderUndo() { if (state) $('undo-btn').disabled = !state.can_undo; }

// ---------------------------------------------------------------- provider
function setupProvider() {
  const p = state.provider;
  if (!p.cli_enabled) $('provider-kind').querySelector('option[value="claude-cli"]').remove();
  $('provider-kind').value = p.provider;
  syncProviderForm();
  $('provider-kind').addEventListener('change', syncProviderForm);
  $('save-provider').addEventListener('click', saveProvider);
}

function syncProviderForm() {
  const kind = $('provider-kind').value, p = state.provider;
  const models = p.models[kind] || [];
  $('model-list').innerHTML = models.map(m => `<option value="${esc(m)}">`).join('');
  $('model-select').value = kind === p.provider ? p.model : (models[0] || '');
  $('base-url-row').hidden = kind !== 'openai';
  const needsKey = kind === 'anthropic' || kind === 'openai';
  $('api-key').disabled = !needsKey;
  $('api-key').placeholder = !needsKey ? 'No key needed' : (p.env_keys[kind] ? 'Optional: a key is set in the environment' : 'Paste your key here');
  $('effort-select').disabled = !(kind === 'anthropic' || kind === 'claude-cli');
}

async function saveProvider() {
  const msg = $('provider-msg'); msg.className = 'msg'; msg.textContent = '';
  const body = {kind: $('provider-kind').value, model: $('model-select').value.trim(),
    effort: $('effort-select').value, base_url: $('base-url').value.trim() || null, api_key: $('api-key').value || null};
  try {
    await busy('Saving model settings…', () => api('/api/provider', body));
    $('api-key').value = '';   // the key now lives only in the server's memory
    msg.className = 'msg ok';
    msg.textContent = `Ready: ${body.kind === 'mock' ? 'mock provider (no AI)' : body.model}. The key was not saved to disk.`;
    await refresh();
  } catch (e) { msg.className = 'msg err'; msg.textContent = e.message; }
}

// ---------------------------------------------------------------- tabs & forms
function setupTabs() {
  document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === t));
    document.querySelectorAll('.panel').forEach(p => p.hidden = p.id !== `panel-${t.dataset.tab}`);
  }));
}

function fillManualValues() {
  const kind = $('manual-kind').value, current = $('manual-value').value;
  const values = kind === 'category' ? Object.entries(state.categories)
    : kind === 'tag' ? Object.entries(state.tags) : state.custom.map(c => [c.label, c.members.length]);
  $('manual-value').innerHTML = values.map(([v, n]) => `<option value="${esc(v)}">${esc(v)} (${n})</option>`).join('');
  if (values.some(([v]) => v === current)) $('manual-value').value = current;
}

function addItemRow(title = '', description = '') {
  const n = $('item-rows').children.length;
  const div = document.createElement('div');
  div.className = 'item-row';
  div.innerHTML = `<label for="item-title-${n}">Video ${n + 1} title</label><input id="item-title-${n}" autocomplete="off">
    <label for="item-desc-${n}">Video ${n + 1} description</label><textarea id="item-desc-${n}" rows="2"></textarea>`;
  $('item-rows').appendChild(div);
  $(`item-title-${n}`).value = title; $(`item-desc-${n}`).value = description;
}

// ---------------------------------------------------------------- previews
async function runPreview(label, fn) {
  try {
    preview = await busy(label, fn);
    window.studioLastPreview = preview;   // read-only copy for automated tests and the demo recorder
    renderReview();
    if ($('auto-apply').checked && preview.applicable) await applyPreview(true);
  } catch (e) { showError(e.message); }
}

function showError(text) {
  preview = null;
  $('review-empty').hidden = true; $('review-body').hidden = false; $('review-actions').hidden = true;
  $('review-body').innerHTML = `<p class="err-box">${esc(text)}</p>`;
}

function stageBox(title, body) { return `<div class="stage"><span class="stage-title">${esc(title)}</span>${body}</div>`; }

function callsBox(calls) {
  if (!calls.length) return stageBox('Model calls', 'None. This control does not use a model.');
  const s = callSummary(calls);
  const rows = calls.map(c => `<tr><td>${esc(c.task)}</td><td>${esc(c.model || '')}</td><td>${seconds(c.latency_s)}</td>
    <td>${c.input_tokens ?? ''} / ${c.output_tokens ?? ''}</td><td>${money(c.cost_usd)}</td><td>${c.error ? esc(c.error) : 'ok'}</td></tr>`).join('');
  return stageBox(`Model calls: ${s.count} (${s.stages}) · ${money(s.cost)}`,
    `<table><tr><th>Stage</th><th>Model</th><th>Time</th><th>Tokens in/out</th><th>Cost</th><th>Result</th></tr>${rows}</table>`);
}

function checksBox(checks) {
  if (!checks.length) return '';
  return stageBox('Application checks', `<ul class="checks">${checks.map(c => `<li class="${c.ok ? '' : 'fail'}">${esc(c.check)}</li>`).join('')}</ul>`);
}

function evidenceBox(p) {
  if (p.kind === 'interpret' && p.evidence.length) {
    return stageBox('What the model proposed', `<table><tr><th>Words in your request</th><th>Action</th><th>Labels chosen</th><th>Why</th></tr>${
      p.evidence.map(e => `<tr><td class="q">“${esc(e.intent_span)}”</td><td>${esc(e.action)}${e.action === 'boost' || e.action === 'reduce' ? ' (' + esc(e.strength) + ')' : ''}</td>
        <td>${esc((e.labels || []).join(', '))}</td><td>${esc(e.relation)}</td></tr>`).join('')}</table>`);
  }
  if (p.kind === 'new-category') {
    const row = r => `<tr class="${r.selected ? 'sel' : ''}"><td>${esc(r.title)} <span class="muted">${esc(r.item_id)}</span></td>
        <td>${esc(verdictLabel(r))}</td><td class="q">${r.quote ? '“' + esc(r.quote) + '” <span class="muted">(' + esc(r.field) + (r.quote_verified ? ', found' : ', NOT found') + ')</span>' : ''}</td>
        <td>${esc(r.reason)}</td><td>${r.assessment ? (r.assessment.supports ? '✓ ' : '✗ ') + esc(r.assessment.reason) : ''}</td></tr>`;
    const head = '<tr><th>Video</th><th>Verdict</th><th>Quoted evidence</th><th>Classifier reason</th><th>Independent check</th></tr>';
    const matched = p.evidence.filter(r => r.verdict === 'match').sort((a, b) => b.selected - a.selected);
    const rest = p.evidence.filter(r => r.verdict !== 'match');
    const nm = rest.filter(r => r.verdict === 'not_match').length;
    return stageBox(`Definition: ${p.proposal.label}`, `<p>${esc(p.proposal.definition)}</p>
      <table id="match-table">${head}${matched.map(row).join('') || '<tr><td colspan="5">No video matched.</td></tr>'}</table>
      <details id="other-rows"><summary>The other ${rest.length} videos (${nm} not match, ${rest.length - nm} unknown) — click to see each verdict</summary>
      <table>${head}${rest.map(row).join('')}</table></details>`);
  }
  if (p.kind === 'new-items') {
    return stageBox('How the model classified the new videos', `<table><tr><th>New video</th><th>Category</th><th>Tags</th><th>Your categories</th><th>Why</th></tr>${
      p.evidence.map(e => `<tr><td>${esc(e.title)} <span class="muted">${esc(e.item_id)}</span></td><td>${esc(e.category)}</td><td>${esc(e.tags.join(', '))}</td>
        <td>${e.new_categories.map(n => `${esc(n.label)}: <b>${esc(n.verdict)}</b>${n.quote ? ' “' + esc(n.quote) + '”' : ''}`).join('<br>')}</td>
        <td>${esc(e.category_reason)}</td></tr>`).join('')}</table>`);
  }
  return '';
}

function beforeAfter(p) {
  const ch = p.changes, b = p.feed_before.top, a = p.feed_after.top;
  const name = id => esc(titles[id] || p.new_items.find(i => i.id === id)?.title || id);
  const affected = p.affected.map(x => `<li>${esc(x.control)} → <b>${x.count}</b> item(s)${x.count ? ': ' + x.item_ids.map(name).join(', ') : ''}</li>`).join('');
  return stageBox('Effect on your feed (not applied yet)', `<p class="counts">${esc(changeSentence(ch))}</p>
    ${affected ? `<ul>${affected}</ul>` : ''}
    <div class="ba"><div><b>Before</b><ol>${b.map(r => `<li class="${ch.left.includes(r.id) ? 'out' : ''}">${esc(r.title)}</li>`).join('')}</ol></div>
    <div><b>After</b><ol>${a.map(r => `<li class="${ch.entered.includes(r.id) ? 'in' : ''}">${esc(r.title)}</li>`).join('')}</ol></div></div>`);
}

function renderReview() {
  const p = preview;
  $('review-empty').hidden = true; $('review-body').hidden = false;
  $('review-body').innerHTML = `<p class="review-summary">${esc(p.summary)}</p>
    ${p.notes.map(n => `<p class="note">${esc(n)}</p>`).join('')}
    ${callsBox(p.calls)}${evidenceBox(p)}${checksBox(p.checks)}${beforeAfter(p)}`;
  $('review-actions').hidden = false;
  $('apply-btn').disabled = !p.applicable;
}

async function applyPreview(auto = false) {
  if (!preview) return;
  try {
    const before = state.feed.top.map(r => r.id);
    await busy('Applying…', () => api('/api/apply', {preview_id: preview.id}));
    await refresh();
    lastFlash = state.feed.top.map(r => r.id).filter(id => !before.includes(id));
    render();
    $('review-actions').hidden = true;
    $('review-body').insertAdjacentHTML('beforeend', `<p class="applied">${auto ? 'Auto-applied' : 'Applied'}. Your feed now has ${state.feed.eligible} eligible items. Use Undo to restore the previous feed.</p>`);
    preview = null;
  } catch (e) { $('review-body').insertAdjacentHTML('beforeend', `<p class="err-box">${esc(e.message)}</p>`); }
}

async function undo() {
  try {
    const before = state.feed.top.map(r => r.id);
    await busy('Undoing…', () => api('/api/undo', {}));
    await refresh();
    lastFlash = state.feed.top.map(r => r.id).filter(id => !before.includes(id));
    render();
    $('review-body').hidden = false; $('review-empty').hidden = true; $('review-actions').hidden = true;
    $('review-body').innerHTML = `<p class="applied">Undone. Your feed is back to ${state.feed.eligible} eligible items.</p>`;
    preview = null;
  } catch (e) { showError(e.message); }
}

// ---------------------------------------------------------------- new category flow
let definition = null;
async function proposeDefinition() {
  try {
    definition = await busy('The model is writing a definition…', () => api('/api/category/define', {description: $('category-text').value}));
  } catch (e) { return showError(e.message); }
  window.studioLastDefinition = definition;
  $('definition-box').hidden = false;
  $('def-label').value = definition.label; $('def-definition').value = definition.definition;
  const ev = definition.evidence.map(e => `<li>${esc(e.title || e.item_id)}: <i>“${esc(e.quote)}”</i> <span class="muted">(${esc(e.field)}, ${e.quote_verified ? 'quote found' : 'quote NOT found'})</span></li>`).join('');
  $('def-evidence').innerHTML = `<p class="help">Model status: <b>${esc(definition.status)}</b>${definition.duplicate ? ' · this label already exists, please rename it' : ''}. ${esc(definition.rationale)}</p>
    ${ev ? `<p class="help">Supporting quotes:</p><ul class="help">${ev}</ul>` : ''}
    ${definition.alternatives.length ? `<p class="help">Other readings: ${esc(definition.alternatives.join('; '))}</p>` : ''}`;
  // Show the definition stage in the review column as well.
  $('review-empty').hidden = true; $('review-body').hidden = false; $('review-actions').hidden = true;
  $('review-body').innerHTML = `<p class="review-summary">Proposed definition (step 1 of 2)</p>${callsBox(definition.calls)}
    ${stageBox(definition.label || '(no label)', `<p>${esc(definition.definition)}</p><ul>${ev}</ul>`)}
    <p class="note">Review or edit the label and definition on the left, then classify all videos.</p>`;
}

// ---------------------------------------------------------------- wiring
async function main() {
  await refresh();
  setupProvider();
  setupTabs();
  addItemRow();
  $('manual-kind').addEventListener('change', fillManualValues);
  $('manual-preview').addEventListener('click', () => runPreview('Building preview…', () => api('/api/preview/manual', {
    kind: $('manual-kind').value, value: $('manual-value').value, action: $('manual-action').value, strength: $('manual-strength').value})));
  $('interpret-preview').addEventListener('click', () => runPreview('The model is interpreting your request…',
    () => api('/api/preview/interpret', {request: $('interpret-text').value})));
  $('category-define').addEventListener('click', proposeDefinition);
  $('category-classify').addEventListener('click', () => runPreview('The model is classifying every video, then checking each quote…',
    () => api('/api/preview/category', {label: $('def-label').value, definition: $('def-definition').value,
      action: $('category-action').value, strength: $('category-strength').value})));
  $('add-item-row').addEventListener('click', () => addItemRow());
  $('items-preview').addEventListener('click', () => {
    const rows = [...$('item-rows').children].map((_, i) => ({title: $(`item-title-${i}`).value, description: $(`item-desc-${i}`).value}));
    runPreview('The model is classifying the new videos…', () => api('/api/preview/items', {items: validNewItems(rows)}));
  });
  $('apply-btn').addEventListener('click', () => applyPreview(false));
  $('discard-btn').addEventListener('click', () => { preview = null; $('review-body').hidden = true; $('review-actions').hidden = true; $('review-empty').hidden = false; });
  $('undo-btn').addEventListener('click', undo);
}

main().catch(e => showError(e.message));
