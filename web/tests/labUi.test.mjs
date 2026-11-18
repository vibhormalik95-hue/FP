// Offline tests of the Lab display helpers and their wiring (findings B1-B10).
// No browser, no server and no model.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {buildSync} from 'esbuild';
import {callsSummary, effortOptionLabel, isMeasuredConfig, labScorer, languageViewTarget, providerChip, resetEndpoints, waitingLabel} from '../src/labUi.js';

const src = name => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8');
const main = src('main.jsx'), lab = src('LabView.jsx'), semantic = src('SemanticPanel.jsx');

test('B1: the global reset also resets the Lab when the Lab is available', () => {
  assert.deepEqual(resetEndpoints({available: true}), ['reset', 'lab/reset']);
  assert.deepEqual(resetEndpoints({available: false}), ['reset']);
  assert.deepEqual(resetEndpoints(null), ['reset']);
  const resetUser = main.slice(main.indexOf('function resetUser()'), main.indexOf('const inline ='));
  assert.match(resetUser, /resetEndpoints\(labStatus\)/);
  assert.match(resetUser, /for \(const path of endpoints\) r = await api\(path/);
  assert.match(resetUser, /setLabReset\(/);
  assert.match(main, /<LabView [^>]*resetKey=\{labReset\}/);
  assert.match(lab, /refresh\(\); \} \}, \[user, resetKey\]\)/);
});

test('B2: the footer does not claim that a reload resets the server-held Lab state', () => {
  const footer = main.slice(main.indexOf('<footer>'), main.indexOf('</footer>'));
  assert.match(footer, /labStatus\?\.available \?/);
  assert.ok(footer.includes('The language controls are kept on the server for each user until you reset the user or the server is restarted.'));
  assert.ok(!footer.includes('<span>Session state is temporary. A reload of the page starts a new session without the applied controls.</span>'));
});

test('B3: in the Lab views the provider chip names the Lab provider, not the earlier route', () => {
  const labStatus = {available: true, provider: {provider: 'openai', label: 'OpenAI API', model: 'gpt-5-mini', effort: 'low'}};
  const status = {provider: {backend: 'ollama', model: 'old-route-model', live_model: true}};
  assert.equal(providerChip({labView: true, labStatus, status}).text, 'LAB PROVIDER · OpenAI API · gpt-5-mini · effort low');
  assert.equal(providerChip({labView: true, labStatus: null, status}).text, 'LAB PROVIDER NOT REPORTED');
  assert.equal(providerChip({labView: false, labStatus, status}).text, 'PROVIDER · ollama · old-route-model');
  assert.equal(providerChip({labView: false, labStatus, status: {provider: {live_model: false}}}).text, 'AUTHORED REPLIES · NO MODEL');
  assert.match(main, /const chip = providerChip\(\{labView, labStatus, status\}\)/);
  assert.ok(!main.includes('`PROVIDER · ${status.provider.backend} · ${status.provider.model}`'));
});

test('B4: "Open the language controls" leads to the Lab when the server has it', () => {
  assert.equal(languageViewTarget({available: true}), 'lab');
  assert.equal(languageViewTarget({available: false}), 'steering');
  assert.equal(languageViewTarget(null), 'steering');
  const button = main.split('\n').find(l => l.includes('>Open the language controls</button>'));
  assert.ok(button);
  assert.match(button, /setView\(languageViewTarget\(labStatus\)\)/);
  assert.ok(!button.includes("setView('steering')"));
});

test('B5: the panel has no dead pointer to the retired Studio', () => {
  assert.ok(!/run-studio|Feed Control Studio/.test(semantic));
});

test('B6: "(measured)" only for measured provider, model and effort; never for the Anthropic API', () => {
  assert.equal(effortOptionLabel('openai', 'gpt-5', 'low'), 'low (measured)');
  assert.equal(effortOptionLabel('openai', 'gpt-5-mini', 'low'), 'low (measured)');
  assert.equal(effortOptionLabel('claude-cli', 'claude-sonnet-5-5', 'low'), 'low (measured)');
  for (const model of ['claude-sonnet-5-5', 'claude-opus-5-5', ''])
    assert.equal(effortOptionLabel('anthropic', model, 'low'), 'low');
  assert.equal(effortOptionLabel('openai', 'gpt-4o', 'low'), 'low');
  assert.equal(effortOptionLabel('openai', 'gpt-5', 'medium'), 'medium');
  assert.equal(isMeasuredConfig('ollama', 'llama3.1:8b', 'low'), false);
  assert.ok(!lab.includes("' (measured)'"));
  assert.match(lab, /effortOptionLabel\(kind, model, x\)/);
});

test('B7: the Lab scorer label comes from /api/lab/status model_mode', () => {
  assert.equal(labScorer('trained SASRec checkpoint').eyebrow, 'TRAINED SASREC RANKING');
  assert.equal(labScorer('diagnostic scorer (no checkpoint)').eyebrow, 'DIAGNOSTIC SCORER · NO TRAINED CHECKPOINT');
  assert.equal(labScorer(undefined).eyebrow, 'SCORER NOT VERIFIED');
  assert.equal(labScorer('diagnostic scorer (no checkpoint)').trained, false);
  assert.ok(!lab.includes("'CURRENT FEED · TRAINED SASREC RANKING'"));
  assert.ok(!lab.includes("The feed is the trained recommender's ranking."));
  assert.match(lab, /modelMode=\{status\?\.model_mode\}/);
  assert.ok(!main.includes("'LANGUAGE CONTROLS · REAL KUAIREC FEED · TRAINED RECOMMENDER'"));
  assert.ok(!main.includes("'Real KuaiRec feed, ranked by the trained recommender."));
});

test('B8: the progress line is a waiting line that never claims a finished backend stage', () => {
  for (const task of ['interpret', 'define', 'classify', 'new-items']) {
    const line = waitingLabel(task);
    assert.match(line, /^Waiting for /);
    assert.ok(!/checks every|chooses|keeps only|drafts a label|passed/.test(line));
  }
  assert.equal(waitingLabel('apply'), null);
  assert.ok(!lab.includes('const STAGES'));
  assert.ok(!/Math\.floor\(s \/ 6\)/.test(lab));
  assert.match(lab, /setStage\(\{text: line, s: Math\.round/);
});

// Render EvidenceRows of the real LabView source with a minimal React and join text without separators.
function renderText(element) {
  const compiled = buildSync({entryPoints: [fileURLToPath(new URL('../src/LabView.jsx', import.meta.url))], bundle: true, write: false,
    format: 'cjs', external: ['react'], jsx: 'transform', logLevel: 'silent'}).outputFiles[0].text;
  const React = {createElement: (type, props, ...children) => ({type, props: props || {}, children}), Fragment: 'fragment', useState: x => [x, () => {}], useEffect: () => {}, useRef: x => ({current: x})};
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(n => { if (n === 'react') return React; throw Error(n); }, module, module.exports);
  const flat = node => node == null || typeof node === 'boolean' ? '' : Array.isArray(node) ? node.map(flat).join('')
    : typeof node !== 'object' ? String(node) : typeof node.type === 'function' ? flat(node.type({...node.props, children: node.children})) : node.children.map(flat).join('');
  return flat(element(module.exports));
}

test('B9: the selected / not selected word is separated from the reason', () => {
  const preview = {kind: 'new-items', evidence: [{item_id: 1, title: 'T', categories: [], tags: [], category_reason: 'r',
    new_categories: [{label: 'L', verdict: 'match', quote: 'q', quote_verified: true, assessment: {supports: true, reason: 'Reason text'}, selected: true},
      {label: 'M', verdict: 'no_match', quote: '', quote_verified: false, assessment: {supports: false, reason: 'Other reason'}, selected: false}]}]};
  const text = renderText(x => x.EvidenceRows({preview}));
  assert.match(text, /· selected Reason text/);
  assert.match(text, /· not selected Other reason/);
  const table = {kind: 'new-category', evidence: [{item_id: 2, title: 'T', verdict: 'match', quote: 'q', field: 'title', quote_verified: true, reason: 'Why', assessment: {supports: true, reason: 'Check why'}, selected: true}]};
  const t2 = renderText(x => x.EvidenceRows({preview: table}));
  assert.match(t2, /found Why/);
  assert.match(t2, /supports Check why/);
});

test('B10: summed latency of several calls is not called "total"', () => {
  const s = callsSummary([{latency_s: 2, cost_usd: 0.01}, {latency_s: 3.5, cost_usd: 0.02}, {latency_s: null, error: 'x'}]);
  assert.equal(s.count, 3);
  assert.equal(s.latencyText, 'sum of call latencies 5.5 s');
  assert.ok(Math.abs(s.cost - 0.03) < 1e-12);
  assert.ok(!/total/.test(s.latencyText));
  assert.ok(!lab.includes('s total</summary>'));
  assert.match(lab, /\{sum\.latencyText\}<\/summary>/);
});
