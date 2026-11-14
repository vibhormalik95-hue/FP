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
  return {ready: true, applied: false, plan_id: plan, history_action: 'none', groups, proposal: null, feed: feed(after),
    scope_items: ITEMS.map(id => ({item_id: id, source_text: 'Description ' + id})), evidence_context: [], note: 'Authored note of the review.',
    grounding: 'vocabulary', model_calls: [{request_sha256: '1'.repeat(64), schema_sha256: '2'.repeat(64), response_sha256: '3'.repeat(64), raw_response: {status: 'propose', marker: 'RAW-REPLY-MARKER'}}],
    model_provenance: model, vocabulary: {terms, checks,
      controls: groups.map(g => ({label: g.label, ...g.proposal.action, relation: g.proposal.reason, item_ids: g.proposal.item_ids,
        terms: g.proposal.vocabulary_terms.map(t => terms.find(x => x.term_id === t.term_id))})),
      not_selected: ITEMS.filter(id => !groups.some(g => g.proposal.item_ids.includes(id))).map(id => ({item_id: id, terms: terms.filter(t => t.item_ids.includes(id)).map(({kind, level, value}) => ({kind, level, value}))}))}};
}
const state = (groups, ids, extra = {}) => ({groups, revision: groups.length, can_undo: groups.length > 0, feed: feed(ids),
  local_models_allowed: false, external_adapter_available: true, category_adapter_available: true, ...extra});

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
  // The harness joins text fragments with a space. Compare text with single spaces only.
  const ui = harness(api, props), raw = ui.text;
  ui.text = (...node) => raw(...node).replace(/\s+/g, ' ').replace(/ ([.,;:)])/g, '$1').replace(/\( /g, '(').trim();
  return {calls, ui};
}
async function request(ui, method = 'vocabulary', text = REQUEST) {
  await ui.open(); ui.choose('semantic-backend', method); await ui.settle();
  if (method !== 'manual_category') ui.choose('semantic-text', text);
  ui.find(n => n.type === 'button' && n.props.className === 'primary' && !ui.text(n).startsWith('Approve')).props.onClick(); await ui.settle();
}
const variant = ui => ui.region('Review board').props['data-variant'];
const stages = ui => ui.nodes(ui.region('Stages of this control')).filter(n => n.type === 'li').map(n => n.props['data-state']).join(' ');
const options = ui => ui.nodes(ui.find(n => n.props.id === 'semantic-backend')).filter(n => n.type === 'input' && !n.props.disabled).map(n => n.props.value);

test('model methods are offered only where the server allows them, and none is selected by default', async () => {
  const {ui} = fixture(); await ui.open();
  assert.deepEqual(options(ui), ['manual_category', 'vocabulary', 'configured_model', 'staged', 'induction']);
  assert.equal(ui.find(n => n.props.id === 'semantic-backend').props['data-value'], 'manual_category');
  const none = fixture({'semantic/groups': state([], ITEMS, {external_adapter_available: false, category_adapter_available: false})}); await none.ui.open();
  assert.deepEqual(options(none.ui), ['manual_category']);
  const local = fixture({'semantic/groups': state([], ITEMS, {external_adapter_available: false, category_adapter_available: false, local_models_allowed: true, configured_model: 'local-model'})}); await local.ui.open();
  assert.deepEqual(options(local.ui), ['manual_category', 'staged', 'ollama', 'induction']);
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
  for (const value of ['Remove from the feed', 'what makes me hungry', 'Authored relation for Exclude: Cooking', 'category "Cooking"', 'RAW-REPLY-MARKER', 'The model can be wrong']) assert.ok(output.includes(value), value);
  for (const value of ['Each selected term exists with exactly the supplied value', 'Passed', 'category "Cooking": 1, 2', 'authored-test-replies', 'It does not show that the meaning is right']) assert.ok(checked.includes(value), value);
  for (const value of ['Exclude: Cooking', 'items 1, 2', 'Nothing has changed yet.', 'Approve before']) assert.ok(decision.includes(value), value);
  assert.equal(output.includes('Each selected term exists'), false);   // a check is never shown as model output
  assert.ok(ui.text(ui.region('Review board')).includes('PREVIEW · NOTHING IS APPLIED YET'));
  const rows = ui.nodes(ui.region('Review of every supplied item')).filter(n => n.type === 'tr' && n.props['data-item']);
  assert.deepEqual(rows.map(n => [n.props['data-item'], n.props['data-member']]), [[1, 'true'], [2, 'true'], [3, 'false'], [4, 'false']]);
  const table = ui.text(ui.region('Review of every supplied item'));
  for (const value of ['Description 3', 'selected through category "Cooking"', 'not selected: none of its categories or tags was chosen', 'not selected: this item has no category and no tag', 'Removed from the feed', 'Unchanged']) assert.ok(table.includes(value), value);
  const preview = ui.text(ui.region('Preview of the feed before and after'));
  for (const value of ['Leaves the list: 1, 2', 'The applied feed is unchanged until you approve.']) assert.ok(preview.includes(value), value);
  assert.equal(stages(ui), 'done done done now todo todo');
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 0);
  ui.button('Approve this exact item set and apply').props.onClick(); await ui.settle();
  assert.deepEqual(calls.find(c => c.path === 'semantic/apply').body, {user_id: 1, plan_id: 'plan-1'});
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
  assert.ok(ui.text().includes('The approved change is applied'));
  assert.equal(stages(ui), 'done done done done done now');
  assert.ok(ui.text(ui.region('Language controls panel')).includes('Exclude: Cooking'));   // listed under the applied controls
  ui.button('Undo the last change (review first)').props.onClick(); await ui.settle();
  assert.equal(variant(ui), 'review');
  assert.ok(ui.text(ui.region('Your decision')).includes('restores the controls that were active before the last approved change'));
  assert.ok(ui.text(ui.region('Your selection')).includes('No model is used for this step.'));
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 1);                  // the undo review alone applies nothing
  ui.button('Approve the undo').props.onClick(); await ui.settle();
  assert.deepEqual(calls.filter(c => c.path === 'semantic/apply').map(c => c.body.plan_id), ['plan-1', 'plan-undo']);
  const restored = ui.text(ui.region('What changed'));
  for (const value of ['UNDONE', 'The earlier feed is restored', 'none', 'Entered the first ten: 1, 2']) assert.ok(restored.includes(value), value);
  assert.ok(ui.text().includes('The undo is applied. The earlier feed is restored.'));
  assert.deepEqual(fed.slice(-2), [2, 4]);
});

test('mixed request: each control is its own row group and one approval applies both', async () => {
  const {calls, ui} = fixture({'semantic/vocabulary/preview': ready([travel, hungry], [3, 4]), 'semantic/apply': {applied: true, ...state([travel, hungry], [3, 4])}});
  await request(ui, 'vocabulary', 'More travel, and remove what makes me hungry.');
  const bodies = ui.nodes(ui.region('Review of every supplied item')).filter(n => n.type === 'tbody');
  assert.deepEqual(bodies.map(n => [n.props['data-group'], n.props['data-new']]), [['Increase: Travel', 'true'], ['Exclude: Cooking', 'true']]);
  assert.ok(ui.text(ui.region('Review of every supplied item')).includes('Control: Increase: Travel'));
  assert.ok(ui.text(ui.region('Your decision')).includes('One approval applies all 2 new controls together.'));
  const table = ui.text(ui.region('Review of every supplied item'));
  for (const value of ['Score +0.25', 'Removed from the feed', 'Net result if approved']) assert.ok(table.includes(value), value);
  const output = ui.text(ui.region('Model output (not verified)'));
  for (const value of ['more travel', 'what makes me hungry', 'Show more (standard, +0.25)']) assert.ok(output.includes(value), value);
  ui.button('Approve this exact item set and apply').props.onClick(); await ui.settle();
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 1);
  assert.ok(ui.text(ui.region('What changed')).includes('New controls'));
});

test('clarification: alternatives are shown and none is selected; adopting one only fills the request box', async () => {
  const stop = {ready: false, applied: false, status: 'clarify', reason: 'Semantic scope or negation has competing interpretations', outcome_source:'model_report', grounding: 'vocabulary',
    clarification: {model_reason: 'Authored: heavy can mean several things.', alternatives: ['Heavy as in rich food.', 'Heavy as in loud music.'], negation_resolved: true,
      question: 'Please state the intended target explicitly in your instruction.', notice: 'These are unverified model interpretations. None was selected or applied.'},
    vocabulary: {terms, checks: [{check: 'An abstention selects nothing', passed: true, detail: 'status ambiguous with 0 controls'}]},
    model_calls: [{raw_response: {status: 'ambiguous'}}], model_provenance: model};
  const {calls, ui} = fixture({'semantic/vocabulary/preview': stop});
  await request(ui, 'vocabulary', 'Enough of the heavy stuff.');
  assert.equal(variant(ui), 'outcome');
  const board = ui.text(ui.region('Review board'));
  for (const value of ['NO CHANGE PROPOSED · NOTHING WAS APPLIED', 'The request has more than one possible meaning', 'Authored: heavy can mean several things.', 'Heavy as in rich food.', 'Heavy as in loud music.',
    'An abstention selects nothing', 'Nothing was applied.', 'What you can do next', 'None was selected or applied']) assert.ok(board.includes(value), value);
  assert.equal(ui.nodes().some(n => n.type === 'button' && ui.text(n) === 'Approve this exact item set and apply'), false);
  assert.equal(stages(ui), 'done now todo todo todo todo');
  const before = calls.length;
  ui.nodes().filter(n => n.type === 'button' && ui.text(n) === 'Add this meaning to my request')[1].props.onClick(); ui.render(); await ui.settle();
  assert.ok(ui.find(n => n.props.id === 'semantic-text').props.value.includes('Heavy as in loud music.'));
  assert.equal(calls.length, before);                                    // nothing is sent until the person submits
  assert.ok(ui.text().includes('Nothing was sent.'));
});

test('negated command: the page says that no model was called and shows the failed application check', async () => {
  const stop = {ready: false, applied: false, status: 'clarify', reason: 'Command negation requires an explicit reviewed interpretation', outcome_source:'application_check', calls_attempted:0, grounding: 'vocabulary',
    vocabulary: {terms, checks: [{check: 'The request does not negate a command', passed: false, detail: 'Conservative English wording guard; it runs before any model call'}]},
    model_calls: [], model_provenance: model};
  const {ui} = fixture({'semantic/vocabulary/preview': stop});
  await request(ui, 'vocabulary', 'Do not hide the cooking videos.');
  const output = ui.text(ui.region('Model output (not verified)')), checked = ui.region('Application checks');
  assert.ok(output.includes('No model call was made. The application stopped the request with its own check.'));
  assert.ok(ui.text(checked).includes('Command negation requires an explicit reviewed interpretation'));
  assert.deepEqual(ui.nodes(checked).filter(n => n.type === 'li').map(n => n.props['data-passed']), ['false']);
  assert.ok(ui.text(checked).includes('Failed'));
});

for (const [status, heading, reason] of [['unsupported', 'The reply reports that the controls cannot express this request', 'A limit for each day is a quota.'],
  ['no_match', 'The reply reports no match', 'No existing category or tag is about astronomy.'],
  ['error', 'The application rejected the reply', 'Proposal rejected (ValueError): unknown term']]) {
  test(`${status}: its own heading, the reason, a next step, and nothing applied`, async () => {
    const {calls, ui} = fixture({'semantic/vocabulary/preview': {ready: false, applied: false, status, reason, outcome_source: status === 'error' ? 'reply_rejected' : 'model_report', grounding: 'vocabulary', vocabulary: {terms, checks: []}, model_calls: [{raw_response: {status}}], model_provenance: model}});
    await request(ui);
    assert.equal(ui.region('Result without a proposed change').props['data-status'], status);
    const board = ui.text(ui.region('Review board'));
    for (const value of [heading, reason, 'Nothing was applied.', 'What you can do next']) assert.ok(board.includes(value), value);
    assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 0);
    assert.ok(ui.text().includes('Nothing was applied.'));
  });
}

test('a provider failure is shown as the server sent it, with nothing applied', async () => {
  const message = 'Category and tag match failed (RouteError); no preferences changed: The provider rejected the API key (HTTP 401). Check the variable and start the server again.';
  const {calls, ui} = fixture({'semantic/vocabulary/preview': new Error(message)});
  await request(ui);
  assert.equal(variant(ui), 'failure');
  const board = ui.text(ui.region('Review board'));
  for (const value of [message, 'The request failed', 'Nothing was applied.', 'correct that setting and start the server again']) assert.ok(board.includes(value), value);
  assert.equal(calls.filter(c => c.path === 'semantic/apply').length, 0);
});

test('discard forgets the review without any call, and an edited request removes the review', async () => {
  const {calls, ui} = fixture({'semantic/vocabulary/preview': ready([hungry], [3, 4])});
  await request(ui);
  const before = calls.length;
  ui.button('Discard this review and apply nothing').props.onClick(); ui.render(); await ui.settle();
  assert.equal(ui.nodes().some(n => n.props['aria-label'] === 'Review board'), false);
  assert.ok(ui.text().includes('Review discarded. Nothing was applied.'));
  assert.equal(calls.length, before);
  ui.button('Interpret my request').props.onClick(); await ui.settle();
  assert.equal(variant(ui), 'review');
  ui.choose('semantic-text', 'Another request'); await ui.settle();
  assert.equal(ui.nodes().some(n => n.props['aria-label'] === 'Review board'), false);
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

test('manual method: the category comes from the supplied list, no model call is made, and the review says so', async () => {
  const manual = {label: 'Manual: Cooking', request: 'Cooking', revision: 'rev-manual', scope_ids: ITEMS, eligible_sha256: 'f'.repeat(64),
    proposal: {status: 'review', requires_review: true, reason: 'Exact existing-category baseline, no model', action: {operation: 'exclude', strength: 'none', intent_span: 'Cooking'}, item_ids: [1, 2], evidence: [],
      provenance: {...provenance, model: {backend: 'manual_category', model: 'none', digest: 'not_applicable'}}}};
  const reply = {ready: true, applied: false, plan_id: 'plan-manual', history_action: 'none', groups: [manual], proposal: manual.proposal, feed: feed([3, 4]),
    scope_items: ITEMS.map(id => ({item_id: id, source_text: 'Description ' + id})), evidence_context: [], note: 'Authored note.', model_calls: []};
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
  assert.ok(ui.text(ui.region('Your selection')).includes('No model is used.'));
  const checked = ui.text(ui.region('Application checks'));
  for (const value of ['The selected items are exactly the items of the category Cooking', 'Provider: none']) assert.ok(checked.includes(value), value);
  assert.ok(ui.text(ui.region('Review of every supplied item')).includes('not selected: its category is not Cooking'));
});

test('description route: a quotation is shown with its item, and an alternative becomes a stated target that still needs confirmation', async () => {
  const stop = {ready: false, applied: false, status: 'clarify', reason: 'Semantic scope or negation has competing interpretations', outcome_source:'model_report', action: {operation: 'exclude', strength: 'none', intent_span: 'heavy'},
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

test('authored replies stay distinct from model output and lock their bundled scope', async()=>{
  const {ui}=fixture({'semantic/vocabulary/preview':ready([hungry],[3,4])},{provider:{live_model:false}});
  await request(ui);
  assert.ok(ui.text(ui.region('Authored reply (written by hand, not a model)')).includes('An authored reply shows the screens only'));
  assert.ok(ui.text().includes('AUTHORED REPLIES, NO MODEL'));
  assert.equal(ui.find(n=>n.props.id==='semantic-count').props.disabled,true);
  assert.equal(options(ui).includes('induction'),false);
});

test('a failed provider attempt with no returned model_calls does not claim no call',async()=>{
  const {ui}=fixture({'semantic/vocabulary/preview':{ready:false,status:'error',reason:'Provider timed out',outcome_source:'provider_failure',calls_attempted:1,model_calls:[]}});
  await request(ui);
  const text=ui.text(ui.region('Review board'));
  assert.ok(text.includes('The call to the provider failed'));
  assert.ok(text.includes('1 model call started'));
  assert.equal(text.includes('No model call was made'),false);
});

test('manual invalid selection cannot call API even if handler is invoked',async()=>{
  const {ui,calls}=fixture({}, {categories:['K1','K2']});
  await ui.open();
  ui.button('Show the proposed change').props.onClick();await ui.settle();
  ui.choose('semantic-category','invented');
  ui.button('Show the proposed change').props.onClick();await ui.settle();
  assert.equal(calls.filter(c=>c.path==='semantic/preview').length,0);
  assert.equal(ui.button('Show the proposed change').props.disabled,true);
});

test('expired review disables approval without applying anything',async()=>{
  let expire;const timers={now:()=>1000,later:work=>{expire=work;return ()=>{};},every:()=>()=>{}};
  const {ui,calls}=fixture({'semantic/vocabulary/preview':ready([hungry],[3,4])},{timers});
  await request(ui);expire();ui.render();
  assert.ok(ui.text().includes('expired'));
  assert.equal(ui.nodes().some(n=>n.type==='button'&&ui.text(n)==='Approve this exact item set and apply'),false);
  assert.equal(calls.filter(c=>c.path==='semantic/apply').length,0);
});
