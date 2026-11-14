// Offline tests of the language-control workflow in the panel and the review
// board. Authored API replies only: no browser, no server and no model.
import test from 'node:test';
import assert from 'node:assert/strict';
import {harness} from './support/panelHarness.mjs';

const model = {backend: 'authored-test-replies', model: 'none', digest: 'd'.repeat(64)};
const provenance = {source_sha256: 'a'.repeat(64), catalogue_sha256: 'e'.repeat(64), request_sha256: 'b'.repeat(64), action_sha256: 'c'.repeat(64), model};
const ITEMS = [1, 2, 3, 4];
const card = id => ({item_id: id, score: 1, base_score: 1, rank: id, categories: id < 3 ? ['Cooking'] : id === 3 ? ['Travel'] : [], source_text: 'Description ' + id});
const feed = ids => ({baseline_items: ITEMS, items: ids.map(card), available_items: ids.length, group_exposure: []});
const terms = [
  {term_id: 'T01', kind: 'category', level: 1, field: 'first_level_category_name', value: 'Cooking', item_ids: [1, 2]},
  {term_id: 'T02', kind: 'category', level: 1, field: 'first_level_category_name', value: 'Travel', item_ids: [3]},
  {term_id: 'T03', kind: 'tag', level: null, field: 'topic_tag', value: 'street food', item_ids: [3]},
];
const checks = [{check: 'Each selected term exists with exactly the supplied value', passed: true, detail: ''},
  {check: 'No control selects more than half of the supplied items', passed: true, detail: '2 of 4'}];
function sealed(label, action, item_ids, chosen) {
  return {label, request: REQUEST, revision: 'rev-' + label, scope_ids: ITEMS, eligible_sha256: 'f'.repeat(64),
    proposal: {status: 'review', requires_review: true, reason: 'Authored relation for ' + label, action, item_ids, action_source: 'model', grounding: 'vocabulary',
      evidence: item_ids.map(id => ({item_id: id, field: chosen[0].field, quote: chosen[0].value})), provenance,
      vocabulary_terms: chosen.map(({item_ids: _, ...term}) => term)}};
}
const REQUEST = 'Remove what makes me hungry.';
const hungry = sealed('Exclude: Cooking', {operation: 'exclude', strength: 'none', intent_span: 'what makes me hungry'}, [1, 2], [terms[0]]);
const travel = sealed('Increase: Travel', {operation: 'boost', strength: 'standard', intent_span: 'more travel'}, [3], [terms[1]]);
function ready(groups, after, plan = 'plan-1') {
  return {ready: true, applied: false, plan_id: plan, history_action: 'none', groups, proposal: null, feed: feed(after), calls_attempted: 1,
    scope_items: ITEMS.map(id => ({item_id: id, source_text: 'Description ' + id})), evidence_context: [], note: 'Authored note of the review.',
    grounding: 'vocabulary', reason: 'Authored reason of the whole reply.', plan_notes: [],
    model_calls: [{request_sha256: '1'.repeat(64), schema_sha256: '2'.repeat(64), response_sha256: '3'.repeat(64), raw_response: {status: 'propose', marker: 'RAW-REPLY-MARKER'}}],
    model_provenance: model, vocabulary: {terms, checks,
      controls: groups.map(g => ({label: g.label, ...g.proposal.action, relation: g.proposal.reason, item_ids: g.proposal.item_ids,
        terms: g.proposal.vocabulary_terms.map(t => terms.find(x => x.term_id === t.term_id))})),
      not_selected: ITEMS.filter(id => !groups.some(g => g.proposal.item_ids.includes(id))).map(id => ({item_id: id, terms: terms.filter(t => t.item_ids.includes(id)).map(({kind, level, value}) => ({kind, level, value}))}))}};
}
const state = (groups, ids, extra = {}) => ({groups, revision: groups.length, can_undo: groups.length > 0, feed: feed(ids),
  local_models_allowed: false, external_adapter_available: true, category_adapter_available: true, ...extra});

// A clock that moves only when a test moves it.
function clock() {
  let now = Date.UTC(2026, 10, 14, 10, 0, 0);
  const waiting = [];
  return {now: () => now, later: (work, wait) => { waiting.push({at: now + wait, work}); return () => {}; }, every: () => () => {},
    advance(ms) { now += ms; for (const entry of waiting.splice(0)) if (entry.at <= now) entry.work(); else waiting.push(entry); }};
}

function fixture(replies = {}, props = {}) {
  const calls = [];
  const api = async (path, body) => {
    calls.push({path, body});
    const key = path.split('?')[0];
    if (key in replies) { const value = typeof replies[key] === 'function' ? replies[key](body) : replies[key]; return value instanceof Error ? Promise.reject(value) : structuredClone(value); }
    if (key === 'semantic/groups') return state([], ITEMS);
    if (key === 'semantic/vocabulary/terms') return {terms, source_sha256: 'a'.repeat(64), note: 'Authored note about the terms.'};
    throw Error('Unexpected API call ' + path);
  };
  const timers = clock();
  // The harness joins text fragments with a space. Compare text with single spaces only.
  const ui = harness(api, {timers, ...props}), raw = ui.text;
  ui.text = (...node) => raw(...node).replace(/\s+/g, ' ').replace(/ ([.,;:)])/g, '$1').replace(/\( /g, '(').trim();
  return {calls, ui, timers};
}
const primary = ui => ui.find(n => n.type === 'button' && n.props.className === 'primary' && n.props.onClick && !ui.text(n).startsWith('Approve'));
async function request(ui, method = 'vocabulary', text = REQUEST) {
  await ui.open(); ui.choose('semantic-backend', method); await ui.settle();
  if (method !== 'manual_category') ui.choose('semantic-text', text);
  primary(ui).props.onClick(); await ui.settle();
}
const variant = ui => ui.region('Review board').props['data-variant'];
const stages = ui => ui.nodes(ui.region('Stages of this control')).filter(n => n.type === 'li').map(n => n.props['data-state']).join(' ');
const stageText = (ui, name) => ui.text(ui.nodes(ui.region('Stages of this control')).find(n => n.type === 'li' && ui.text(n).startsWith(name)));
const methods = ui => ui.nodes(ui.find(n => n.props.id === 'semantic-backend')).filter(n => n.type === 'input').map(n => [n.props.value, Boolean(n.props.disabled)]);
const panelMessage = ui => ui.text(ui.find(n => n.props.role === 'status' && n.props.className === 'alert'));

test('model methods are offered only where the server allows them; with no provider they stay visible, disabled, with the reason (M12)', async () => {
  const {ui} = fixture(); await ui.open();
  assert.deepEqual(methods(ui), [['manual_category', false], ['vocabulary', false], ['configured_model', false], ['staged', false], ['induction', false]]);
  assert.equal(ui.find(n => n.props.id === 'semantic-backend').props['data-value'], 'manual_category');
  const none = fixture({'semantic/groups': state([], ITEMS, {external_adapter_available: false, category_adapter_available: false})}); await none.ui.open();
  assert.deepEqual(methods(none.ui), [['manual_category', false], ['vocabulary', true], ['configured_model', true], ['staged', true]]);
  const text = none.ui.text(none.ui.region('Language controls panel'));
  for (const value of ['(needs a model provider)', 'This server was started without a model provider.', 'python scripts/quickstart.py']) assert.ok(text.includes(value), value);
  const local = fixture({'semantic/groups': state([], ITEMS, {external_adapter_available: false, category_adapter_available: false, local_models_allowed: true, configured_model: 'local-model'})}); await local.ui.open();
  assert.deepEqual(methods(local.ui).map(m => m[0]), ['manual_category', 'staged', 'ollama', 'induction']);
});

test('with authored replies no text names a model; the earlier one-call method is hidden and the scope is locked (M2, M4)', async () => {
  const {ui, calls} = fixture({'semantic/vocabulary/preview': ready([hungry], [3, 4])}, {provider: {backend: 'scripted-authored-replies', model: 'none', live_model: false}});
  await ui.open();
  assert.deepEqual(methods(ui).map(m => m[0]), ['manual_category', 'vocabulary', 'configured_model', 'staged']);
  const panelText = ui.text(ui.region('Language controls panel'));
  assert.ok(panelText.includes('(authored replies, no model)'));
  assert.ok(panelText.includes('This server answers with hand-written replies for the bundled examples. It has no model.'));
  ui.choose('semantic-backend', 'vocabulary'); await ui.settle();
  assert.equal(ui.find(n => n.props.id === 'semantic-count').props.disabled, true);
  ui.choose('semantic-text', REQUEST); primary(ui).props.onClick(); await ui.settle();
  assert.deepEqual(calls.find(c => c.path === 'semantic/vocabulary/preview').body.candidate_ids, ITEMS);
  const reply = ui.text(ui.region('Authored reply (written by hand, not a model)'));
  for (const value of ['Reason in the authored reply:', 'Names in the authored reply:', 'An authored reply shows the screens only.']) assert.ok(reply.includes(value), value);
  assert.ok(ui.text(ui.region('Review board')).includes('PREVIEW · NOTHING IS APPLIED YET · AUTHORED REPLIES, NO MODEL'));
  const all = ui.text(ui.region('Review board')).replace(/not a model|no model|nothing about a model|No model answered/gi, '');
  assert.equal(/\bmodel\b/i.test(all), false, all.match(/.{40}\bmodel\b.{40}/i)?.[0]);
});

test('category and tag method: existing names are listed before any model call, and the request has exactly the declared fields', async () => {
  const {calls, ui} = fixture({'semantic/vocabulary/preview': ready([hungry], [3, 4])});
  await ui.open(); ui.choose('semantic-backend', 'vocabulary'); await ui.settle();
  const listed = ui.text(ui.region('Existing categories and tags in the scope'));
  for (const value of ['Cooking (2)', 'Travel (1)', 'street food (1)', 'Authored note about the terms.']) assert.ok(listed.includes(value), value);
  assert.equal(calls.filter(c => c.path === 'semantic/vocabulary/preview').length, 0);
  assert.deepEqual(calls.find(c => c.path === 'semantic/vocabulary/terms').body, {user_id: 1, candidate_ids: ITEMS});
  ui.choose('semantic-text', REQUEST);
  ui.button('Interpret my request').props.onClick(); await ui.settle();
  assert.deepEqual(calls.find(c => c.path === 'semantic/vocabulary/preview').body, {user_id: 1, text: REQUEST, candidate_ids: ITEMS, mode: 'merge'});
  assert.equal(calls.filter(c => c.path === 'semantic/vocabulary/preview').length, 1);
});

test('a ready review shows three separate blocks, the server checks, evidence for every item and the feed difference', async () => {
  const {calls, ui} = fixture({'semantic/vocabulary/preview': ready([hungry], [3, 4]), 'semantic/apply': {applied: true, ...state([hungry], [3, 4])}});
  await request(ui);
  assert.equal(variant(ui), 'review');
  const output = ui.text(ui.region('Model output (not verified)')), checked = ui.text(ui.region('Application checks')), decision = ui.text(ui.region('Your decision'));
  for (const value of ['Remove from the feed', 'what makes me hungry', 'Authored relation for Exclude: Cooking', 'Authored reason of the whole reply.', 'category "Cooking"', 'RAW-REPLY-MARKER', 'The model can be wrong']) assert.ok(output.includes(value), value);
  for (const value of ['Each selected term exists with exactly the supplied value', 'Passed', 'category "Cooking": 1, 2', 'authored-test-replies', 'It does not show that the meaning is right']) assert.ok(checked.includes(value), value);
  for (const value of ['Exclude: Cooking', 'items 1, 2', 'Nothing has changed yet.', 'Approve before', 'After that time the server no longer accepts this review.']) assert.ok(decision.includes(value), value);
  assert.equal(output.includes('Each selected term exists'), false);   // a check is never shown as model output
  assert.equal(checked.includes('Authored reason of the whole reply.'), false);   // text of a reply is never shown as an application result
  assert.ok(ui.text(ui.region('Review board')).includes('PREVIEW · NOTHING IS APPLIED YET'));
  assert.ok(ui.text(ui.region('Review board')).includes('Your request: “Remove what makes me hungry.”'));
  const rows = ui.nodes(ui.region('Review of every supplied item')).filter(n => n.type === 'tr' && n.props['data-item']);
  assert.deepEqual(rows.map(n => [n.props['data-item'], n.props['data-member']]), [[1, 'true'], [2, 'true'], [3, 'false'], [4, 'false']]);
  const table = ui.text(ui.region('Review of every supplied item'));
  for (const value of ['Description 3', 'selected through category "Cooking"', 'not selected: none of its categories or tags was chosen', 'not selected: this item has no category and no tag', 'Removed from the feed', 'Unchanged']) assert.ok(table.includes(value), value);
  const preview = ui.text(ui.region('Preview of the feed before and after'));
  for (const value of ['Leaves the list: 1, 2', 'The applied feed is unchanged until you approve.']) assert.ok(preview.includes(value), value);
  assert.equal(stages(ui), 'done done done now todo todo');
  assert.ok(panelMessage(ui).includes('The review is ready. Nothing is applied yet.'));
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 0);
  ui.button('Approve this exact item set and apply').props.onClick(); await ui.settle();
  assert.deepEqual(calls.find(c => c.path === 'semantic/apply').body, {user_id: 1, plan_id: 'plan-1'});
});

test('plan notes of the server stand under the application checks as notes, not as checks (M10)', async () => {
  const notes = [{kind: 'overrides', message: 'The control "Exclude: Cooking" removes items that the applied control "Increase: Cooking" ranks.', item_ids: [1, 2]}];
  const {ui} = fixture({'semantic/vocabulary/preview': {...ready([hungry], [3, 4]), plan_notes: notes}});
  await request(ui);
  const region = ui.region('Notes about the whole plan');
  assert.ok(ui.text(region).includes('Note: The control "Exclude: Cooking" removes items'));
  assert.equal(ui.nodes(region).some(n => n.props['data-passed']), false);
  assert.ok(ui.nodes(ui.region('Application checks')).includes(region));
});

test('after Apply the page records what changed and how to undo; Undo is reviewed first and then restores the earlier feed', async () => {
  let applied = false;
  const undo = {ready: true, applied: false, plan_id: 'plan-undo', history_action: 'undo', groups: [], proposal: null, feed: feed(ITEMS), scope_items: [], evidence_context: [], note: 'Authored note.'};
  const {calls, ui} = fixture({'semantic/vocabulary/preview': ready([hungry], [3, 4]), 'semantic/history/preview': undo,
    'semantic/apply': body => { applied = body.plan_id === 'plan-1'; return {applied: true, ...(applied ? state([hungry], [3, 4]) : state([], ITEMS))}; }});
  const fed = []; ui.changeProps({onFeed: value => fed.push(value.available_items)});
  await request(ui);
  ui.button('Approve this exact item set and apply').props.onClick(); await ui.settle();
  assert.equal(variant(ui), 'changed');
  const record = ui.text(ui.region('What changed'));
  for (const value of ['APPLIED', 'Exclude: Cooking', 'Remove from the feed', 'items 1, 2', '4 before, 2 after', 'Left the first ten: 1, 2', 'To undo:']) assert.ok(record.includes(value), value);
  assert.ok(panelMessage(ui).includes('The approved change is applied.'));
  assert.equal(stages(ui), 'done done done done done now');
  assert.ok(ui.text(ui.region('Language controls panel')).includes('Exclude: Cooking'));   // listed under the applied controls
  ui.button('Undo the last change (review first)').props.onClick(); await ui.settle();
  assert.equal(variant(ui), 'review');
  assert.ok(ui.text(ui.region('Your decision')).includes('restores the controls that were active before the last approved change'));
  assert.ok(ui.text(ui.region('Your selection')).includes('No model is used for this step.'));
  assert.equal(ui.text(ui.region('Review board')).includes('quotation does not prove'), false);   // m4
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 1);                  // the undo review alone applies nothing
  ui.button('Approve the undo').props.onClick(); await ui.settle();
  assert.deepEqual(calls.filter(c => c.path === 'semantic/apply').map(c => c.body.plan_id), ['plan-1', 'plan-undo']);
  const restored = ui.text(ui.region('What changed'));
  for (const value of ['UNDONE', 'The earlier feed is restored', 'none', 'Entered the first ten: 1, 2']) assert.ok(restored.includes(value), value);
  assert.ok(panelMessage(ui).includes('The undo is applied. The earlier feed is restored.'));
  assert.equal(stageText(ui, 'Undo'), 'Undo done');
  assert.deepEqual(fed.slice(-2), [2, 4]);
});

test('the removal of every control has its own words and its own stage note (M11, m4)', async () => {
  const clear = {ready: true, applied: false, plan_id: 'plan-clear', history_action: 'clear', groups: [], proposal: null, feed: feed(ITEMS), scope_items: [], evidence_context: []};
  const {ui} = fixture({'semantic/groups': state([hungry], [3, 4]), 'semantic/history/preview': clear, 'semantic/apply': {applied: true, ...state([], ITEMS)}});
  await ui.open();
  assert.equal(stageText(ui, 'Undo'), 'Undo available');
  ui.button('Remove every applied control (review first)').props.onClick(); await ui.settle();
  assert.equal(stageText(ui, 'Preview'), 'Preview now: review the removal');
  assert.ok(ui.text(ui.region('Application checks')).includes('Every control is removed. No check is necessary.'));
  ui.button('Approve: remove every control').props.onClick(); await ui.settle();
  assert.ok(ui.text(ui.region('What changed')).includes('Every applied control is removed.'));
  assert.equal(stageText(ui, 'Request'), 'Request now: every control is removed');
});

test('mixed request: each control is its own row group and one approval applies both', async () => {
  const {calls, ui} = fixture({'semantic/vocabulary/preview': ready([travel, hungry], [3, 4]), 'semantic/apply': {applied: true, ...state([travel, hungry], [3, 4])}});
  await request(ui, 'vocabulary', 'More travel, and remove what makes me hungry.');
  const bodies = ui.nodes(ui.region('Review of every supplied item')).filter(n => n.type === 'tbody');
  assert.deepEqual(bodies.map(n => [n.props['data-group'], n.props['data-new']]), [['Increase: Travel', 'true'], ['Exclude: Cooking', 'true']]);
  assert.ok(ui.text(ui.region('Review board')).includes('Proposed change: 2 controls'));
  assert.ok(ui.text(ui.region('Your decision')).includes('One approval applies all 2 new controls together.'));
  const table = ui.text(ui.region('Review of every supplied item'));
  for (const value of ['Score +0.25; ranked higher: position 3 to 1', 'Removed from the feed', 'Net result if approved']) assert.ok(table.includes(value), value);
  const output = ui.text(ui.region('Model output (not verified)'));
  for (const value of ['more travel', 'what makes me hungry', 'Show more (standard, +0.25)']) assert.ok(output.includes(value), value);
  ui.button('Approve this exact item set and apply').props.onClick(); await ui.settle();
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 1);
  assert.ok(ui.text(ui.region('What changed')).includes('New controls'));
});

test('clarification: the meanings stay in the reply block; adding one keeps the words of the person and sends nothing (M3, m9)', async () => {
  const stop = {ready: false, applied: false, status: 'clarify', reason: 'Semantic scope or negation has competing interpretations', grounding: 'vocabulary', outcome_source: 'model_report', calls_attempted: 1,
    clarification: {model_reason: 'Authored: heavy can mean several things.', alternatives: ['Heavy as in rich food.', 'Heavy as in loud music.'], negation_resolved: true,
      question: 'Please state the intended target explicitly in your instruction.', notice: 'These are unverified model interpretations. None was selected or applied.'},
    vocabulary: {terms, checks: [{check: 'An abstention selects nothing', passed: true, detail: 'status ambiguous with 0 controls'}]},
    model_calls: [{raw_response: {status: 'ambiguous'}}], model_provenance: model};
  const {calls, ui} = fixture({'semantic/vocabulary/preview': stop});
  await request(ui, 'vocabulary', 'Enough of the heavy stuff.');
  assert.equal(variant(ui), 'outcome');
  const reply = ui.text(ui.region('Model output (not verified)')), checked = ui.text(ui.region('Application checks'));
  for (const value of ['Authored: heavy can mean several things.', 'Heavy as in rich food.', 'Heavy as in loud music.', 'None was selected or applied']) assert.ok(reply.includes(value), value);
  for (const value of ['Authored: heavy can mean several things.', 'Heavy as in loud music.']) assert.equal(checked.includes(value), false, value);
  for (const value of ['An abstention selects nothing', 'It did not check the reason.']) assert.ok(checked.includes(value), value);
  const board = ui.text(ui.region('Review board'));
  for (const value of ['NO CHANGE PROPOSED · NOTHING WAS APPLIED', 'The request has more than one possible meaning', 'Nothing was applied.', 'What you can do next']) assert.ok(board.includes(value), value);
  assert.equal(ui.nodes().some(n => n.type === 'button' && ui.text(n).startsWith('Approve')), false);
  assert.equal(stages(ui), 'done now todo todo todo todo');
  const before = calls.length;
  ui.nodes().filter(n => n.type === 'button' && ui.text(n) === 'Add this meaning to my request')[1].props.onClick(); ui.render(); await ui.settle();
  assert.equal(ui.find(n => n.props.id === 'semantic-text').props.value, 'Enough of the heavy stuff. (I mean: Heavy as in loud music.)');
  assert.equal(calls.length, before);                                    // nothing is sent until the person submits
  assert.ok(ui.text().includes('Nothing was sent.'));
});

test('a stop by the application before any call says so, from the server field (M1, F1)', async () => {
  const stop = {ready: false, applied: false, status: 'clarify', reason: 'The request text matches the negated-command pattern.', grounding: 'vocabulary',
    outcome_source: 'application_check', calls_attempted: 0,
    vocabulary: {terms, checks: [{check: 'The request text does not match the negated-command pattern', passed: false, detail: 'do not, followed by hide'}]},
    model_calls: [], model_provenance: model};
  const {ui} = fixture({'semantic/vocabulary/preview': stop});
  await request(ui, 'vocabulary', 'Do not hide the cooking videos.');
  const output = ui.text(ui.region('Model output (not verified)')), checked = ui.region('Application checks');
  assert.ok(output.includes('No model call was made. The application stopped the request with its own check.'));
  assert.ok(ui.text(checked).includes('Stopped: The request text matches the negated-command pattern.'));
  assert.deepEqual(ui.nodes(checked).filter(n => n.type === 'li').map(n => n.props['data-passed']), ['false']);
  assert.ok(ui.text(checked).includes('No model call was started.'));
  assert.ok(ui.text(ui.region('Your decision')).includes('positive instruction'));
});

test('a failed call is never reported as "no call" (M1, F1)', async () => {
  // An older server without outcome_source: the page says only what it knows.
  const old = {ready: false, applied: false, status: 'error', reason: 'The model call failed: The provider is not reachable.', grounding: 'vocabulary', model_calls: [], model_provenance: model};
  const {ui} = fixture({'semantic/vocabulary/preview': old});
  await request(ui);
  assert.equal(/No model (call )?was (called|made)/.test(ui.text(ui.region('Review board'))), false);
  // The server names a provider failure: its own heading and sentence.
  const failed = fixture({'semantic/vocabulary/preview': {...old, outcome_source: 'provider_failure', calls_attempted: 1}});
  await request(failed.ui);
  const board = failed.ui.text(failed.ui.region('Review board'));
  for (const value of ['The call to the provider failed', 'A call to the provider was started. No usable reply came back.', 'Message of the server: The model call failed: The provider is not reachable.', '1 model call started for this request.', 'Nothing was applied.']) assert.ok(board.includes(value), value);
  assert.equal(stages(failed.ui).split(' ')[1], 'now');
});

test('a rejected reply has its own heading; its raw reply stays in the reply block (M5)', async () => {
  const rejected = {ready: false, applied: false, status: 'error', reason: 'Every quotation is present in the text of its own item: failed for item 1.', outcome_source: 'reply_rejected', calls_attempted: 2,
    checks: [{check: 'Every quotation is present in the description of its own item', passed: false, detail: 'item 1: "words that are not there"'}],
    action: {operation: 'exclude', strength: 'none', intent_span: 'x'}, model_calls: [{raw_response: {marker: 'REJECTED-RAW'}}]};
  const {ui} = fixture({'semantic/preview': rejected});
  await request(ui, 'configured_model', 'Remove x.');
  assert.ok(ui.text(ui.region('Review board')).includes('The application rejected the reply'));
  assert.ok(ui.text(ui.region('Model output (not verified)')).includes('REJECTED-RAW'));
  const checked = ui.text(ui.region('Application checks'));
  for (const value of ['Rejected:', 'Failed: Every quotation is present in the description of its own item', 'words that are not there']) assert.ok(checked.includes(value), value);
  assert.equal(stages(ui).split(' ')[2], 'now');   // the stop was in the evidence stage
});

test('with authored replies a typed request gets one plain refusal for every method (M4)', async () => {
  const provider = {backend: 'scripted-authored-replies', model: 'none', live_model: false};
  for (const [method, route] of [['vocabulary', 'semantic/vocabulary/preview'], ['configured_model', 'semantic/preview'], ['staged', 'semantic/definition/preview']]) {
    const refusal = {ready: false, applied: false, status: 'error', outcome_source: 'provider_failure', calls_attempted: 1, reason: 'The server holds no authored reply for this request.'};
    const {ui} = fixture({[route]: refusal}, {provider});
    await request(ui, method, 'Hide everything about trains.');
    const board = ui.text(ui.region('Review board'));
    for (const value of ['No authored reply exists for this request', 'None exists. Nothing was interpreted.', 'Message of the server: The server holds no authored reply for this request.', 'Nothing was applied.']) assert.ok(board.includes(value), `${method}: ${value}`);
    assert.equal(ui.nodes().some(n => n.type === 'button' && /Use this as|Add this meaning/.test(ui.text(n))), false);
  }
});

for (const [status, heading, reason] of [['unsupported', 'The reply reports that the controls cannot express this request', 'A limit for each day is a quota.'],
  ['no_match', 'The reply reports no match', 'No existing category or tag is about astronomy.']]) {
  test(`${status}: its own heading, the reason in the reply block, a next step, and nothing applied (M3)`, async () => {
    const {calls, ui} = fixture({'semantic/vocabulary/preview': {ready: false, applied: false, status, reason, outcome_source: 'model_report', calls_attempted: 1, grounding: 'vocabulary', vocabulary: {terms, checks: []}, model_calls: [{raw_response: {status}}], model_provenance: model}});
    await request(ui);
    assert.equal(ui.region('Result without a proposed change').props['data-status'], status);
    const board = ui.text(ui.region('Review board'));
    for (const value of [heading, 'Nothing was applied.', 'What you can do next']) assert.ok(board.includes(value), value);
    assert.ok(ui.text(ui.region('Model output (not verified)')).includes(reason));
    assert.equal(ui.text(ui.region('Application checks')).includes(reason), false);
    assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 0);
    assert.ok(panelMessage(ui).includes(`${heading}. Nothing was applied.`));
  });
}

test('an error answer of the server is shown next to the request, with nothing applied', async () => {
  const message = 'Category and tag match failed (RouteError); no preferences changed: The provider rejected the API key (HTTP 401). Check the variable and start the server again.';
  const {calls, ui} = fixture({'semantic/vocabulary/preview': new Error(message)});
  await request(ui);
  assert.equal(variant(ui), 'failure');
  const board = ui.text(ui.region('Review board'));
  for (const value of [message, 'The request failed', 'Nothing was applied.', 'correct that setting and start the server again']) assert.ok(board.includes(value), value);
  assert.ok(panelMessage(ui).includes('The request failed. Nothing was applied.'));
  // M8: a change of method removes the old message.
  ui.choose('semantic-backend', 'manual_category'); await ui.settle();
  assert.equal(ui.nodes().some(n => n.props.role === 'status' && n.props.className === 'alert'), false);
});

test('discard forgets the review without any call; an edited request removes the review with a message (m8, M8)', async () => {
  const {calls, ui} = fixture({'semantic/vocabulary/preview': ready([hungry], [3, 4])});
  await request(ui);
  const before = calls.length;
  ui.button('Discard this review and apply nothing').props.onClick(); ui.render(); await ui.settle();
  assert.equal(ui.nodes().some(n => n.props['aria-label'] === 'Review board'), false);
  assert.ok(panelMessage(ui).includes('Review discarded. Nothing was applied.'));
  assert.equal(calls.length, before);
  ui.button('Interpret my request').props.onClick(); await ui.settle();
  assert.equal(variant(ui), 'review');
  ui.choose('semantic-text', 'Another request'); await ui.settle();
  assert.equal(ui.nodes().some(n => n.props['aria-label'] === 'Review board'), false);
  assert.ok(panelMessage(ui).includes('You changed the request. The review was discarded. Nothing was applied.'));
});

test('after a discard the earlier applied change is folded under its own title (M8)', async () => {
  const {ui} = fixture({'semantic/preview': body => ({...ready([], [3, 4], 'plan-m'), groups: [{...hungry, label: body.label, revision: 'rev-m', proposal: {...hungry.proposal, provenance: {...provenance, model: {backend: 'manual_category'}}}}], history_action: 'none'}),
    'semantic/apply': {applied: true, ...state([hungry], [3, 4])}}, {categories: ['Cooking', 'Travel']});
  await ui.open();
  ui.choose('semantic-category', 'Cooking'); await ui.settle();   // no category is selected at the start: the person chooses one
  ui.button('Show the proposed change').props.onClick(); await ui.settle();
  ui.button('Approve this exact item set and apply').props.onClick(); await ui.settle();
  assert.equal(variant(ui), 'changed');
  ui.choose('semantic-category', 'Travel'); await ui.settle();
  ui.button('Show the proposed change').props.onClick(); await ui.settle();
  ui.button('Discard this review and apply nothing').props.onClick(); ui.render(); await ui.settle();
  const earlier = ui.region('Last applied change');
  assert.equal(earlier.type, 'details');
  assert.ok(ui.text(earlier).startsWith('Last applied change ('));
  assert.equal(ui.nodes().some(n => n.props['aria-label'] === 'What changed'), false);
});

test('an expired review is marked, cannot be approved, and says how to get a new one (M7)', async () => {
  const {ui, timers, calls} = fixture({'semantic/vocabulary/preview': ready([hungry], [3, 4])});
  await request(ui);
  assert.ok(ui.text(ui.region('Your decision')).includes('Approve before'));
  timers.advance(296 * 1000); ui.render(); await ui.settle();
  assert.equal(ui.region('Review board').props['data-expired'], 'true');
  const board = ui.text(ui.region('Review board'));
  for (const value of ['EXPIRED · NOTHING WAS APPLIED', 'This review is older than five minutes.', 'A model method calls the model again.']) assert.ok(board.includes(value), value);
  assert.equal(ui.nodes().some(n => n.type === 'button' && ui.text(n).startsWith('Approve')), false);
  assert.equal(stageText(ui, 'Preview'), 'Preview now: expired; nothing applied');
  ui.button('Close this expired review').props.onClick(); ui.render(); await ui.settle();
  assert.ok(panelMessage(ui).includes('The expired review is closed. Nothing was applied.'));
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 0);
});

test('a review that the server no longer accepts becomes an expired result (M7)', async () => {
  const {ui} = fixture({'semantic/vocabulary/preview': ready([hungry], [3, 4]), 'semantic/apply': new Error('Review expired or changed; review again')});
  await request(ui);
  ui.button('Approve this exact item set and apply').props.onClick(); await ui.settle();
  assert.equal(ui.region('Result without a proposed change').props['data-kind'], 'expired');
  assert.ok(ui.text(ui.region('Review board')).includes('This review has expired'));
  assert.equal(ui.nodes().some(n => n.props['aria-label'] === 'Proposed change'), false);
});

test('during a call the page shows the seconds and "Stop waiting"; stopping discards the late result (m12)', async () => {
  let finish;
  const {ui, calls} = fixture({'semantic/vocabulary/preview': () => new Promise(resolve => { finish = resolve; })});
  await ui.open(); ui.choose('semantic-backend', 'vocabulary'); await ui.settle(); ui.choose('semantic-text', REQUEST);
  ui.button('Interpret my request').props.onClick(); ui.render();
  assert.ok(ui.text(primary(ui)).startsWith('Waiting for the provider: 0 s'));
  assert.equal(ui.region('Language controls panel').props['aria-busy'], 'true');
  ui.button('Stop waiting').props.onClick(); ui.render(); await ui.settle();
  assert.ok(panelMessage(ui).includes('can still finish on the server. This page discards its result.'));
  finish(ready([hungry], [3, 4])); await ui.settle();
  assert.equal(ui.nodes().some(n => n.props['aria-label'] === 'Review board'), false);
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 0);
});

test('bundled examples: the main button and the list insert the exact text and call nothing', async () => {
  const scenarioRequests = {vocabulary: 'Main request text.', 'vocabulary:mixed': 'Two preferences text.', 'vocabulary:no_match': 'Nothing matches text.', configured_model: 'Described text.', label: 'Bundled label', synthetic: 'Brief.'};
  const {calls, ui} = fixture({}, {scenarioRequests});
  await ui.open(); ui.choose('semantic-backend', 'vocabulary'); await ui.settle();
  const before = calls.length;
  const select = ui.find(n => n.props.id === 'semantic-example');
  assert.deepEqual(ui.nodes(select).filter(n => n.type === 'option').map(n => [n.props.value, ui.text(n)]),
    [['', 'Choose an example to insert'], ['vocabulary', 'The main bundled request'], ['vocabulary:mixed', 'Two preferences in one request'], ['vocabulary:no_match', 'A request that matches nothing']]);
  ui.choose('semantic-example', 'vocabulary:mixed');
  assert.equal(ui.find(n => n.props.id === 'semantic-text').props.value, 'Two preferences text.');
  ui.button('Insert the bundled scenario request').props.onClick(); ui.render();
  assert.equal(ui.find(n => n.props.id === 'semantic-text').props.value, 'Main request text.');
  assert.equal(calls.length, before);
  // A method with one bundled request has the button and no list; its label is the bundled one.
  ui.choose('semantic-backend', 'configured_model'); await ui.settle();
  assert.equal(ui.nodes().some(n => n.props.id === 'semantic-example'), false);
  ui.button('Insert the bundled scenario request').props.onClick(); ui.render();
  assert.equal(ui.find(n => n.props.id === 'semantic-text').props.value, 'Described text.');
  assert.equal(ui.find(n => n.props.id === 'semantic-label').props.value, 'Bundled label');
});

test('manual method: the first block is "Your selection"; no model sentence and no fixed check line (M15, m1)', async () => {
  const manual = {label: 'Manual: Cooking', request: 'Cooking', revision: 'rev-manual', scope_ids: [3, 4], eligible_sha256: 'f'.repeat(64),
    proposal: {status: 'review', requires_review: true, reason: 'Exact existing-category baseline, no model', action: {operation: 'exclude', strength: 'none', intent_span: 'Cooking'}, item_ids: [], evidence: [],
      provenance: {...provenance, model: {backend: 'manual_category', model: 'none', digest: 'not_applicable'}}}};
  const reply = {ready: true, applied: false, plan_id: 'plan-manual', history_action: 'none', groups: [manual], proposal: manual.proposal, feed: feed([1, 2, 3, 4]),
    scope_items: [3, 4].map(id => ({item_id: id, source_text: 'Description ' + id})), evidence_context: [], note: 'Authored note.', model_calls: []};
  const {calls, ui} = fixture({'semantic/preview': reply}, {categories: ['Cooking', 'Travel']});
  await ui.open();
  const select = ui.find(n => n.props.id === 'semantic-category');
  assert.equal(select.type, 'select');
  assert.deepEqual(ui.nodes(select).filter(n => n.type === 'option').map(n => n.props.value), ['', 'Cooking', 'Travel']);
  assert.equal(select.props.value, '');
  assert.equal(ui.button('Show the proposed change').props.disabled, true);
  ui.choose('semantic-category', 'Cooking');
  assert.equal(ui.find(n => n.props.id === 'semantic-label').props.value, 'Manual: Cooking');
  assert.equal(stages(ui).split(' ')[1], 'skipped');
  ui.choose('semantic-operation', 'exclude');
  ui.button('Show the proposed change').props.onClick(); await ui.settle();
  const sent = calls.find(c => c.path === 'semantic/preview').body;
  assert.deepEqual([sent.backend, sent.category, sent.operation, sent.strength, sent.label, sent.candidate_ids], ['manual_category', 'Cooking', 'exclude', 'none', 'Manual: Cooking', ITEMS]);
  assert.equal(ui.nodes().some(n => n.props['aria-label'] === 'Model output (not verified)'), false);
  const selection = ui.text(ui.region('Your selection'));
  assert.ok(selection.includes('You chose the existing category Cooking'));
  assert.equal(/can be wrong|repeats what it returned/.test(selection), false);
  const checked = ui.text(ui.region('Application checks'));
  for (const value of ['The selected items are exactly the items of the category Cooking in the scope', 'Provider: none']) assert.ok(checked.includes(value), value);
  assert.equal(checked.includes('No model was used for this control'), false);
  assert.ok(ui.text(ui.region('Review of every supplied item')).includes('not selected: its category is not Cooking'));
});

test('description route: a quotation is shown with its item, and an alternative becomes a stated target that still needs confirmation', async () => {
  const stop = {ready: false, applied: false, status: 'clarify', reason: 'Semantic scope or negation has competing interpretations', action: {operation: 'exclude', strength: 'none', intent_span: 'heavy'},
    outcome_source: 'model_report', calls_attempted: 1,
    item_ids: [], evidence: [], clarification: {model_reason: 'Authored reason.', alternatives: ['Videos about rich food.'], negation_resolved: true, question: 'Please state the intended target explicitly in your instruction.', notice: 'Unverified.'},
    model_calls: [{raw_response: {status: 'ambiguous'}}]};
  const {calls, ui} = fixture({'semantic/preview': stop});
  await request(ui, 'configured_model', 'Less heavy stuff.');
  const before = calls.length;
  ui.button('Use this as my stated target').props.onClick(); ui.render(); await ui.settle();
  assert.equal(ui.find(n => n.props.id === 'semantic-confirmed-target').props.value, 'Videos about rich food.');
  assert.equal(ui.find(n => n.props.id === 'semantic-text').props.value, 'Less heavy stuff.');   // the original request is kept
  assert.equal(calls.length, before);
  assert.equal(ui.button('Interpret my request').props.disabled, true);                           // not before the person confirms the target
});

test('the data notice of a new category names the applied controls (M14)', async () => {
  const {ui} = fixture();
  await ui.open(); ui.choose('semantic-backend', 'staged'); await ui.settle();
  assert.ok(ui.text(ui.region('Language controls panel')).includes('the names and item IDs of the controls that are applied'));
});

test('the reason of a ready reply comes from reply_reason, and the deadline from review_window_seconds (F13, M7)', async () => {
  const {ui, timers} = fixture({'semantic/vocabulary/preview': {...ready([hungry], [3, 4]), reason: undefined, reply_reason: 'Reason of the reply from the new field.', review_window_seconds: 60}});
  await request(ui);
  assert.ok(ui.text(ui.region('Model output (not verified)')).includes('Reason that the model gave: Reason of the reply from the new field.'));
  timers.advance(56 * 1000); ui.render(); await ui.settle();
  assert.equal(ui.region('Review board').props['data-expired'], 'true');
});

test('an error answer with a structured result is a result without a change, in the stage that the server names (M4)', async () => {
  const payload = {ready: false, status: 'error', outcome_source: 'provider_failure', calls_attempted: 1, failed_stage: 'interpretation',
    reason: 'This server has no model. It has no reply for this request.', model_calls: []};
  const error = Object.assign(new Error('Semantic proposal failed (ProviderMessage); no preferences changed: ...'), {status: 502, payload});
  const {ui} = fixture({'semantic/preview': error}, {provider: {backend: 'scripted-authored-replies', live_model: false}});
  await request(ui, 'configured_model', 'Hide everything about trains.');
  assert.equal(variant(ui), 'outcome');
  const board = ui.text(ui.region('Review board'));
  for (const value of ['No authored reply exists for this request', 'Message of the server: This server has no model.', 'Authored replies looked up for this request: 1.']) assert.ok(board.includes(value), value);
  assert.equal(board.includes('Semantic proposal failed'), false);
  assert.equal(stages(ui).split(' ')[1], 'now');
  // A failure in the evidence stage of the staged method is shown there, with the lost definition.
  const late = {...payload, failed_stage: 'evidence_assessment', definition_consumed: true, calls_attempted: 3};
  const staged = fixture({'semantic/definition/preview': late});
  await request(staged.ui, 'staged', 'A category.');
  assert.equal(stages(staged.ui).split(' ')[2], 'now');
  assert.ok(staged.ui.text(staged.ui.region('Your decision')).includes('The definition that you approved is used up.'));
});

for (const [status, heading, next] of [['limit', 'At most eight controls can be applied', 'Replace every applied control'],
  ['label_collision', 'An applied control has the same name', 'Change the name of this control']]) {
  test(`${status}: an application check before any call, with its own heading and next step (contract 4)`, async () => {
    const stop = {ready: false, applied: false, status, outcome_source: 'application_check', calls_attempted: 0, failed_stage: 'interpretation', reason: 'Sentence of the server.',
      checks: [{check: 'Check of the server', passed: false, detail: 'detail'}], model_calls: []};
    const {ui} = fixture({'semantic/vocabulary/preview': stop});
    await request(ui);
    const board = ui.text(ui.region('Review board'));
    for (const value of [heading, next, 'Stopped: Sentence of the server.', 'No model call was made.', 'No model call was started.']) assert.ok(board.includes(value), value);
  });
}

test('a report of the model keeps its reason out of the application block also when the server repeats it as the reason (M3)', async () => {
  const stop = {ready: false, applied: false, status: 'clarify', outcome_source: 'model_report', calls_attempted: 1, reason: 'Which of the two meanings?', reply_reason: 'Which of the two meanings?',
    clarification: {alternatives: ['First meaning.', 'Second meaning.'], negation_resolved: true}, model_calls: [{raw_response: {status: 'ambiguous'}}]};
  const {ui} = fixture({'semantic/preview': stop});
  await request(ui, 'configured_model', 'Less heavy stuff.');
  assert.ok(ui.text(ui.region('Model output (not verified)')).includes('Which of the two meanings?'));
  assert.equal(ui.text(ui.region('Application checks')).includes('Which of the two meanings?'), false);
});

test('the server names the items of a control outside the scope (m1, scope_effects)', async () => {
  const effect = [{label: 'Exclude: Cooking', in_scope_item_ids: [1, 2], outside_scope_item_ids: [7, 9], message: 'This control selects 2 of the 4 items in the scope.'}];
  const {ui} = fixture({'semantic/vocabulary/preview': {...ready([hungry], [3, 4]), scope_effects: effect}});
  await request(ui);
  const checked = ui.text(ui.region('Application checks'));
  for (const value of ['This control selects 2 of the 4 items in the scope.', '2 items with a chosen name are outside the evidence scope and do not change: 7, 9.']) assert.ok(checked.includes(value), value);
});
