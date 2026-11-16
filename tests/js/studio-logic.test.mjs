import test from 'node:test';
import assert from 'node:assert/strict';
import {callSummary, changeSentence, maskKey, money, providerLine, validNewItems, verdictLabel}
  from '../../studio/static/logic.js';

test('money formats small and zero amounts', () => {
  assert.equal(money(0), '$0.00');
  assert.equal(money(0.0042), '$0.0042');
  assert.equal(money(0.1234), '$0.123');
  assert.equal(money(null), 'n/a');
});

test('callSummary counts stages, failures and cost', () => {
  const s = callSummary([{task: 'classify', cost_usd: 0.01}, {task: 'classify', cost_usd: 0.02},
    {task: 'assess', cost_usd: 0.005}, {task: 'define', error: 'boom', cost_usd: 0}]);
  assert.equal(s.count, 4);
  assert.equal(s.failed, 1);
  assert.equal(s.stages, 'classify ×2, assess, define');
  assert.ok(Math.abs(s.cost - 0.035) < 1e-9);
});

test('changeSentence describes eligibility and movement', () => {
  const t = changeSentence({eligible_before: 40, eligible_after: 36, entered: ['a', 'b'], left: ['c'], moved_up: [], moved_down: ['d']});
  assert.match(t, /40 → 36/);
  assert.match(t, /2 enter the top 12/);
  assert.match(t, /1 leave/);
  assert.match(t, /1 move down/);
  assert.match(changeSentence({eligible_before: 5, eligible_after: 5, entered: [], left: [], moved_up: [], moved_down: []}), /unchanged \(5\)/);
});

test('maskKey never reveals characters', () => {
  const masked = maskKey('sk-ant-secret-value-123');
  assert.ok(!/[a-z0-9]/i.test(masked));
  assert.equal(maskKey(''), '');
});

test('providerLine names the key source without the key', () => {
  const line = providerLine({provider: 'anthropic', model: 'claude-sonnet-5-5', effort: 'low', key_source: 'pasted'});
  assert.equal(line, 'Anthropic API · claude-sonnet-5-5 · effort low · key pasted (memory only)');
  assert.equal(providerLine({provider: 'mock', model: 'mock-literal-v1', key_source: null}), 'Mock (no AI) · mock-literal-v1');
});

test('verdictLabel explains why a match was not selected', () => {
  assert.equal(verdictLabel({verdict: 'match', selected: true}), 'selected');
  assert.equal(verdictLabel({verdict: 'match', selected: false, quote_verified: false}), 'match, quote not found');
  assert.equal(verdictLabel({verdict: 'match', selected: false, quote_verified: true, assessment: {supports: false}}), 'match, assessor disagrees');
  assert.equal(verdictLabel({verdict: 'not_match', selected: false}), 'not match');
});

test('validNewItems drops incomplete rows and trims', () => {
  assert.deepEqual(validNewItems([{title: ' A ', description: ' d '}, {title: 'B', description: ''}, {}]),
    [{title: 'A', description: 'd'}]);
});
