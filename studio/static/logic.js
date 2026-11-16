// Pure helpers shared by the page and the Node tests. No DOM access here.

export function money(value) {
  if (value === null || value === undefined) return 'n/a';
  if (value === 0) return '$0.00';
  return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(3)}`;
}

export function seconds(value) {
  return value === null || value === undefined ? '–' : `${Number(value).toFixed(1)} s`;
}

export function callSummary(calls) {
  const ok = calls.filter(c => !c.error);
  const cost = ok.reduce((s, c) => s + (c.cost_usd || 0), 0);
  const tasks = {};
  for (const c of calls) tasks[c.task] = (tasks[c.task] || 0) + 1;
  const stages = Object.entries(tasks).map(([t, n]) => (n > 1 ? `${t} ×${n}` : t)).join(', ');
  return {count: calls.length, failed: calls.length - ok.length, cost, stages};
}

export function changeSentence(changes) {
  const parts = [];
  if (changes.eligible_before !== changes.eligible_after)
    parts.push(`eligible items ${changes.eligible_before} → ${changes.eligible_after}`);
  else parts.push(`eligible items unchanged (${changes.eligible_after})`);
  if (changes.entered.length) parts.push(`${changes.entered.length} enter the top 12`);
  if (changes.left.length) parts.push(`${changes.left.length} leave the top 12`);
  if (changes.moved_up.length) parts.push(`${changes.moved_up.length} move up`);
  if (changes.moved_down.length) parts.push(`${changes.moved_down.length} move down`);
  return parts.join('; ');
}

export function maskKey(key) {
  // Never show any character of a key.
  return key ? '•'.repeat(Math.min(24, Math.max(8, key.length))) : '';
}

export function providerLine(p) {
  if (!p) return '';
  const who = {anthropic: 'Anthropic API', openai: 'OpenAI-compatible', mock: 'Mock (no AI)', 'claude-cli': 'Claude CLI'}[p.provider] || p.provider;
  const key = p.key_source ? ` · key ${p.key_source === 'pasted' ? 'pasted (memory only)' : 'from environment'}` : '';
  const effort = p.effort ? ` · effort ${p.effort}` : '';
  return `${who} · ${p.model}${effort}${key}`;
}

export function verdictLabel(row) {
  if (row.selected) return 'selected';
  if (row.verdict === 'match' && !row.quote_verified) return 'match, quote not found';
  if (row.verdict === 'match' && row.assessment && !row.assessment.supports) return 'match, assessor disagrees';
  return row.verdict.replace('_', ' ');
}

export function validNewItems(rows) {
  return rows.map(r => ({title: (r.title || '').trim(), description: (r.description || '').trim()}))
    .filter(r => r.title && r.description);
}
