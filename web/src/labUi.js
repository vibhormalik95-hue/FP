// Small pure helpers for the Language controls (Lab) view and the global toolbar.
// They decide only display text and which endpoints a button calls; no scoring.

// The provider configurations measured in docs/evidence/lab-eval/20261117-main/RESULTS.md
// (runs/*.meta.json). Claude was measured through the local Claude CLI, not the Anthropic API.
export const MEASURED_CONFIGS = [
  {provider: 'openai', model: 'gpt-5', effort: 'low'},
  {provider: 'openai', model: 'gpt-5-mini', effort: 'low'},
  {provider: 'claude-cli', model: 'claude-sonnet-5-5', effort: 'low'},
];

export function isMeasuredConfig(provider, model, effort) {
  const m = String(model || '').trim();
  return MEASURED_CONFIGS.some(c => c.provider === provider && c.model === m && c.effort === effort);
}

// The text of one reasoning-effort option: "(measured)" only for a measured provider + model + effort.
export function effortOptionLabel(provider, model, effort) {
  return isMeasuredConfig(provider, model, effort) ? `${effort} (measured)` : effort;
}

// The scorer of the Lab feed, from /api/lab/status model_mode. Unknown stays unknown.
export function labScorer(modelMode) {
  if (modelMode === 'trained SASRec checkpoint') return {eyebrow: 'TRAINED SASREC RANKING', words: 'the trained SASRec recommender', trained: true};
  if (typeof modelMode === 'string' && modelMode.startsWith('diagnostic scorer'))
    return {eyebrow: 'DIAGNOSTIC SCORER · NO TRAINED CHECKPOINT', words: 'a diagnostic scorer (no trained checkpoint loaded)', trained: false};
  return {eyebrow: 'SCORER NOT VERIFIED', words: 'a scorer that the server did not report', trained: false};
}

// One waiting line per task. It does not change with time, so it never claims that a backend stage finished.
const WAITING = {
  interpret: 'Waiting for the model and the server checks…',
  define: 'Waiting for the model to draft a definition…',
  classify: 'Waiting for the classification calls and the server checks…',
  'new-items': 'Waiting for the model and the server checks…',
};
export function waitingLabel(task) {
  return WAITING[task] || null;
}

// The summary line of a list of model calls. Calls can run in parallel, so the summed
// latency is not the elapsed time and is not called "total".
export function callsSummary(calls) {
  const list = calls || [];
  const cost = list.reduce((s, c) => s + (c.cost_usd || 0), 0);
  const latency = list.map(c => c.latency_s).filter(x => typeof x === 'number').reduce((a, b) => a + b, 0);
  return {count: list.length, cost, latency, latencyText: `sum of call latencies ${latency.toFixed(1)} s`};
}

// The endpoints the global "Reset this user" calls. The Lab keeps its own per-user state on the
// server, so it is reset with /api/lab/reset whenever the Lab is available.
export function resetEndpoints(labStatus) {
  return labStatus?.available ? ['reset', 'lab/reset'] : ['reset'];
}

// Where "Open the language controls" leads: the Lab when the server has it, else the earlier view.
export function languageViewTarget(labStatus) {
  return labStatus?.available ? 'lab' : 'steering';
}

// The provider chip of the status strip. In the Lab views it names the Lab provider from
// /api/lab/status (refreshed after each provider save), never the earlier route's provider.
export function providerChip({labView, labStatus, status}) {
  if (labView) {
    const p = labStatus?.provider;
    if (!p) return {text: 'LAB PROVIDER NOT REPORTED', authored: false};
    return {text: `LAB PROVIDER · ${p.label || p.provider} · ${p.model}${p.effort ? ` · effort ${p.effort}` : ''}`, authored: false};
  }
  const p = status?.provider;
  if (!p) return null;
  const authored = p.live_model === false;
  return {text: authored ? 'AUTHORED REPLIES · NO MODEL' : `PROVIDER · ${p.backend} · ${p.model}`, authored};
}
