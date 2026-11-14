// Tests of the display logic with authored data. No browser and no model.
import test from 'node:test';
import assert from 'node:assert/strict';
import {actionWords, adoptText, categoryIdsReadable, changeRecord, controlLines, exampleOptions, feedDiff, labelsByItem, localChecks, netEffects, outcomeKind, outcomeView,
  outsideScope, planConflicts, planRows, plural, providerWords, resultWords, routeOf, scopeChoices, sourceWords, splitGroups, stageStates, STAGES, termWords} from '../src/reviewModel.js';

const model = {backend: 'authored', model: 'none', digest: 'd'.repeat(64)};
const hashes = {source_sha256: 'a'.repeat(64), request_sha256: 'b'.repeat(64), action_sha256: 'c'.repeat(64)};
function group(label, action, item_ids, extra = {}, scope = [1, 2, 3, 4]) {
  return {label, request: extra.request || 'remove the food', revision: 'rev-' + label, scope_ids: scope,
    proposal: {status: 'review', action, item_ids, evidence: [], provenance: {...hashes, model}, ...extra}};
}
const exclude = {operation: 'exclude', strength: 'none', intent_span: 'the food'};
const boost = {operation: 'boost', strength: 'standard', intent_span: 'more repair'};
const terms = [
  {term_id: 'T01', kind: 'category', level: 1, field: 'first_level_category_name', value: 'Cooking', item_ids: [1, 2]},
  {term_id: 'T02', kind: 'category', level: 2, field: 'second_level_category_name', value: 'Baking', item_ids: [2]},
  {term_id: 'T03', kind: 'tag', level: null, field: 'topic_tag', value: 'street food', item_ids: [3]},
];
const items = ids => ids.map(item_id => ({item_id}));

test('the route of a group follows the sealed record', () => {
  assert.equal(routeOf(group('a', exclude, [1], {grounding: 'vocabulary'})), 'vocabulary');
  assert.equal(routeOf(group('a', exclude, [1], {induction: {envelope: {evidence_audit: {}}}})), 'staged');
  assert.equal(routeOf(group('a', exclude, [1], {induction: {envelope: {}}})), 'induction');
  assert.equal(routeOf(group('a', exclude, [1], {provenance: {model: {backend: 'manual_category'}}})), 'manual');
  assert.equal(routeOf(group('a', exclude, [1])), 'description');
});

test('action and term wording is plain and complete', () => {
  assert.equal(actionWords(exclude), 'Remove from the feed');
  assert.equal(actionWords(boost), 'Show more (standard, +0.25)');
  assert.equal(actionWords({operation: 'reduce', strength: 'light'}), 'Show less, still in the feed (light, -0.10)');
  assert.equal(termWords(terms[0]), 'category "Cooking"');
  assert.equal(termWords(terms[1]), 'category (level 2) "Baking"');
  assert.equal(termWords(terms[2]), 'tag "street food"');
  assert.equal(plural(1, 'control'), '1 control');
  assert.equal(plural(2, 'control'), '2 controls');
  assert.equal(plural(1, 'quotation'), '1 quotation');
});

test('hand-written replies are never called a model (M2)', () => {
  const authored = sourceWords(true), model = sourceWords(false);
  for (const value of Object.values(authored)) if (typeof value === 'string') assert.equal(/\bmodel\b/i.test(value.replace(/not a model|no model|nothing about a model/gi, '')), false, value);
  assert.equal(authored.block, 'Authored reply (written by hand, not a model)');
  assert.equal(model.block, 'Model output (not verified)');
  assert.ok(providerWords({backend: 'scripted-authored-replies', model: 'none', digest: 'e'.repeat(64)}, authored).startsWith('Replies: written by hand'));
  assert.ok(providerWords({backend: 'route', model: 'm', digest: 'e'.repeat(64)}, model).includes('The application did not verify which model answered.'));
  assert.equal(providerWords({backend: 'manual_category'}, model), 'Provider: none. This control uses no model.');
});

test('net effect: removal wins, opposite rank changes cancel', () => {
  const net = netEffects([group('up', boost, [1, 2]), group('out', exclude, [2]), group('down', {operation: 'reduce', strength: 'standard'}, [1])]);
  assert.equal(resultWords(net[2]), 'Removed from the feed');
  assert.equal(resultWords(net[1]), 'Unchanged (the score changes cancel)');
  assert.equal(resultWords(net[3]), 'Unchanged');
});

test('"ranked higher" is said only when the position changes (M9)', () => {
  const up = netEffects([group('up', boost, [4])])[4], down = netEffects([group('down', {operation: 'reduce', strength: 'light'}, [4])])[4];
  assert.equal(resultWords(up, {before: 1, after: 1}), 'Score +0.25; position 1 stays');
  assert.equal(resultWords(up, {before: 6, after: 4}), 'Score +0.25; ranked higher: position 6 to 4');
  assert.equal(resultWords(down, {before: 2, after: 5}), 'Score -0.10; ranked lower: position 2 to 5');
  assert.equal(resultWords(up, {before: null, after: 9}), 'Score +0.25; enters the first ten at position 9');
  assert.equal(resultWords(down, {before: 10, after: null}), 'Score -0.10; leaves the first ten');
  assert.equal(resultWords(up), 'Score +0.25');
  for (const place of [{before: 1, after: 1}, {before: 3, after: 3}]) assert.equal(/ranked/.test(resultWords(up, place)), false);
});

test('a plan is split into new, kept and removed controls by the sealed revision', () => {
  const old = group('old', exclude, [1]), fresh = group('fresh', boost, [2]);
  const split = splitGroups([old, fresh], [old, group('gone', exclude, [3])]);
  assert.deepEqual(split.added.map(g => g.label), ['fresh']);
  assert.deepEqual(split.kept.map(g => g.label), ['old']);
  assert.deepEqual(split.removed.map(g => g.label), ['gone']);
});

test('category and tag route: every item has a row with its labels and the term that selects it', () => {
  const control = group('Exclude: Cooking + street food', exclude, [1, 2, 3], {grounding: 'vocabulary', vocabulary_terms: [terms[0], terms[2]],
    evidence: [{item_id: 1, field: 'first_level_category_name', quote: 'Cooking'}, {item_id: 2, field: 'first_level_category_name', quote: 'Cooking'}, {item_id: 3, field: 'topic_tag', quote: 'street food'}]});
  const pending = {groups: [control], scope_items: [1, 2, 3, 4].map(id => ({item_id: id, source_text: 'text ' + id})),
    vocabulary: {terms, controls: [{label: control.label, ...exclude, relation: 'r', terms: [terms[0], terms[2]], item_ids: [1, 2, 3]}]}};
  const [block] = planRows(pending, {groups: []}, {terms});
  assert.equal(block.route, 'vocabulary');
  assert.equal(block.isNew, true);
  assert.deepEqual(block.rows.map(r => [r.id, r.member, r.result]), [[1, true, 'Removed from the feed'], [2, true, 'Removed from the feed'], [3, true, 'Removed from the feed'], [4, false, 'Unchanged']]);
  assert.equal(block.rows[0].evidence, 'selected through category "Cooking"');
  assert.equal(block.rows[2].evidence, 'selected through tag "street food"');
  assert.equal(block.rows[3].evidence, 'not selected: this item has no category and no tag');
  assert.deepEqual(block.rows[1].labels.map(l => l.value), ['Cooking', 'Baking']);
  assert.equal(block.rows[0].description, 'text 1');
  // Without the per-control term members the sealed evidence still names the term.
  const [fallback] = planRows({...pending, vocabulary: undefined}, {groups: []}, {terms});
  assert.equal(fallback.rows[2].evidence, 'selected through tag "street food"');
  // An item with labels that were not chosen says so.
  const other = planRows({...pending, groups: [group('Exclude: street food', exclude, [3], {grounding: 'vocabulary', vocabulary_terms: [terms[2]]})],
    vocabulary: {terms, controls: [{label: 'Exclude: street food', terms: [terms[2]], item_ids: [3]}]}}, {groups: []}, {terms});
  assert.equal(other[0].rows[0].evidence, 'not selected: none of its categories or tags was chosen');
});

test('the result column reads the position from the two feeds (M9)', () => {
  const control = group('Increase: Repair', boost, [1], {grounding: 'vocabulary', vocabulary_terms: [terms[0]]});
  const pending = {groups: [control], feed: {items: items([1, 2, 3, 4])}, vocabulary: {controls: [{label: control.label, terms: [terms[0]]}]}};
  const [block] = planRows(pending, {groups: [], feed: {items: items([1, 2, 3, 4])}}, {terms});
  assert.equal(block.rows[0].result, 'Score +0.25; position 1 stays');
  const [moved] = planRows({...pending, feed: {items: items([1, 2, 3, 4])}}, {groups: [], feed: {items: items([2, 3, 1, 4])}}, {terms});
  assert.equal(moved.rows[0].result, 'Score +0.25; ranked higher: position 3 to 1');
});

test('the category of a row comes from the same source as the manual control (M13)', () => {
  // Scenario category: K1 is the category that the manual control offers; the item data has it in the tag column.
  const tagTerms = [{term_id: 'T1', kind: 'tag', level: null, value: 'K1', item_ids: [1]}];
  const labels = labelsByItem(tagTerms, {1: ['K1'], 2: ['K2']});
  assert.deepEqual(labels[1], [{kind: 'category', level: 1, value: 'K1'}, {kind: 'tag', level: null, value: 'K1'}]);
  const manual = group('Manual: K1', {operation: 'exclude', strength: 'none', intent_span: 'K1'}, [1], {provenance: {model: {backend: 'manual_category'}}}, [1, 2]);
  const [block] = planRows({groups: [manual]}, {groups: []}, {terms: tagTerms, categories: {1: ['K1'], 2: ['K2']}});
  assert.equal(block.rows[0].evidence, 'selected: its category is K1');
  assert.equal(block.rows[1].evidence, 'not selected: its category is not K1');
});

test('description, manual and staged routes keep their own evidence wording; each call keeps its own column (m6)', () => {
  const described = group('d', exclude, [1], {evidence: [{item_id: 1, field: 'caption', quote: 'eats a meal'}]});
  const manual = group('m', {operation: 'exclude', strength: 'none', intent_span: 'K1'}, [2], {provenance: {model: {backend: 'manual_category'}}});
  const staged = group('s', exclude, [1], {induction: {envelope: {
    field_evidence: [{item_id: 1, verdict: 'match', evidence_quote: 'q1', reason: 'because'}, {item_id: 2, verdict: 'unknown', evidence_quote: '', reason: 'withheld'}],
    evidence_audit: {primary_envelope: {field_evidence: [{item_id: 1, verdict: 'match', evidence_quote: 'q1', reason: 'first reason'}, {item_id: 2, verdict: 'not_match', evidence_quote: 'q2', reason: 'first reason 2'}]},
      assessment: {assessments: [{item_id: 1, assessment: 'supported', quote: 'q1', reason: 'second reason'}, {item_id: 2, assessment: 'not_stated', quote: '', reason: 'second reason 2'}]}, withheld: [{item_id: 2}]}}}}, [1, 2]);
  const rows = planRows({groups: [described, manual, staged], scope_items: []}, {groups: [manual]}, {});
  // New controls come first; the applied manual control comes last.
  assert.deepEqual(rows.map(block => [block.label, block.isNew]), [['d', true], ['s', true], ['m', false]]);
  assert.equal(rows[0].rows[0].evidence, 'selected · "eats a meal" (description)');
  assert.equal(rows[0].rows[1].evidence, 'not selected: no quotation was cited for this item');
  assert.equal(rows[2].rows[1].evidence, 'selected: its category is K1');
  assert.equal(rows[0].rows[0].labels, null);
  const [first, second] = rows[1].rows;
  assert.deepEqual([first.first, first.firstReason, first.second, first.secondReason, first.final],
    ['matches the definition · "q1"', 'first reason', 'supported · "q1"', 'second reason', 'Selected: the classification matches and the separate assessment supports it']);
  assert.deepEqual([second.first, second.firstReason, second.second, second.secondReason, second.final, second.member],
    ['does not match · "q2"', 'first reason 2', 'not stated', 'second reason 2', 'Not selected: the two calls do not agree', false]);
});

test('labels by item come only from the supplied term list and the category map', () => {
  const labels = labelsByItem(terms);
  assert.deepEqual(labels[2], [{kind: 'category', level: 1, value: 'Cooking'}, {kind: 'category', level: 2, value: 'Baking'}]);
  assert.equal(labels[4], undefined);
});

test('feed difference names the items that leave, enter and move', () => {
  const diff = feedDiff(items([1, 2, 3, 4]), items([2, 4, 5]));
  assert.deepEqual(diff.leaves, [1, 3]);
  assert.deepEqual(diff.enters, [5]);
  assert.deepEqual(diff.moved, [{id: 2, from: 2, to: 1}, {id: 4, from: 4, to: 2}]);
  assert.deepEqual(diff.before.map(e => e.note), ['leaves', '', 'leaves', '']);
  assert.deepEqual(diff.after.map(e => e.note), ['up 1', 'up 2', 'enters']);
  assert.equal(feedDiff(items([1, 2]), items([1, 2])).unchanged, true);
  assert.deepEqual(feedDiff(items([1, 2]), items([2, 1])).after.map(e => e.note), ['up 1', 'down 1']);
  assert.equal(feedDiff(undefined, undefined).unchanged, true);
});

test('a removal by one control and a rank change by another are named as a plan note (M10)', () => {
  const notes = planConflicts([group('Increase: Repair', boost, [4, 5]), group('Exclude: Repair', exclude, [4, 5])]);
  assert.equal(notes.length, 1);
  assert.deepEqual(notes[0].item_ids, [4, 5]);
  assert.ok(notes[0].message.includes('Removal takes priority'));
  assert.deepEqual(planConflicts([group('a', boost, [1]), group('b', exclude, [2])]), []);
});

test('bundled examples follow the key convention of the server', () => {
  const requests = {vocabulary: 'main', 'vocabulary:mixed': 'two', 'vocabulary:no_match': 'none', 'vocabulary:other_case': 'x',
    configured_model: 'described', label: 'L', staged: 'new category', synthetic: 'brief', 'vocabulary:bad': 7};
  assert.deepEqual(exampleOptions(requests, 'vocabulary').map(o => [o.key, o.name, o.text]), [
    ['vocabulary', 'The main bundled request', 'main'], ['vocabulary:mixed', 'Two preferences in one request', 'two'],
    ['vocabulary:no_match', 'A request that matches nothing', 'none'], ['vocabulary:other_case', 'other case', 'x']]);
  assert.deepEqual(exampleOptions(requests, 'configured_model').map(o => o.key), ['configured_model']);
  assert.deepEqual(exampleOptions(requests, 'manual_category'), []);
  assert.deepEqual(exampleOptions(null, 'vocabulary'), []);
});

test('the scope choices state the true size of the starting list (m21)', () => {
  assert.deepEqual(scopeChoices(10).map(c => c.name), ['First 6 items of the starting list', 'First 10 items of the starting list']);
  assert.deepEqual(scopeChoices(8).map(c => c.name), ['First 6 items of the starting list', 'All 8 items of the starting list']);
  assert.deepEqual(scopeChoices(4).map(c => [c.value, c.size]), [[10, 4]]);
});

test('an adopted meaning keeps the words of the person (m9)', () => {
  assert.equal(adoptText('I have had enough of the heavy stuff.', 'Heavy as in rich food: the category Cooking.'),
    'I have had enough of the heavy stuff. (I mean: Heavy as in rich food: the category Cooking.)');
  assert.equal(adoptText('', 'Rich food.'), 'Rich food.');
  assert.equal(adoptText('Keep this.', '  '), 'Keep this.');
});

test('the original conditions read only category IDs of the form category_N (B1)', () => {
  assert.equal(categoryIdsReadable(['category_0', 'category_12']), true);
  assert.equal(categoryIdsReadable(['Cooking', 'Repair']), false);
  assert.equal(categoryIdsReadable(['category_0', 'K1']), false);
  assert.equal(categoryIdsReadable([]), false);
});

test('the outcome source decides the words; an empty call list never means "no call" (M1, F1)', () => {
  const authored = sourceWords(true), model = sourceWords(false);
  // A server without outcome_source and an empty call list: the page does not claim that no call was made.
  const silent = outcomeView({status: 'error', reason: 'The model call failed: x', model_calls: [], method: 'vocabulary'}, model);
  assert.equal(silent.kind, 'unknown');
  assert.equal([...silent.first, ...silent.second].some(line => /No model|no .*call was made/i.test(line)), false);
  const stopped = outcomeView({status: 'clarify', outcome_source: 'application_check', calls_attempted: 0, method: 'vocabulary', reason: 'r',
    vocabulary: {checks: [{check: 'The request text matches the negated-command pattern', passed: false}]}}, model);
  assert.equal(stopped.kind, 'application_check');
  assert.ok(stopped.first[0].startsWith('No model call was made.'));
  assert.ok(stopped.next.some(line => line.includes('positive instruction')));
  const failed = outcomeView({status: 'error', outcome_source: 'provider_failure', calls_attempted: 1, method: 'vocabulary', reason: 'r'}, model);
  assert.equal(failed.heading, 'The call to the provider failed');
  assert.ok(failed.first[0].includes('No usable reply came back'));
  // The scripted provider has no reply for a typed request: one text for all methods (M4).
  for (const method of ['vocabulary', 'configured_model', 'staged']) {
    const refused = outcomeView({status: 'error', outcome_source: 'provider_failure', calls_attempted: 1, method, reason: 'r'}, authored);
    assert.equal(refused.heading, 'No authored reply exists for this request');
    assert.ok(refused.first.join(' ').includes('This server has no model.'));
  }
  const rejected = outcomeView({status: 'error', outcome_source: 'reply_rejected', calls_attempted: 2, method: 'configured_model', reason: 'r'}, model);
  assert.equal(rejected.heading, 'The application rejected the reply');
  assert.equal(outcomeView({status: 'duplicate', outcome_source: 'reply_rejected', method: 'staged'}, model).heading, 'The proposed name already exists');
});

test('a report of the model stays in the first block; the application block says what it did and did not check (M3)', () => {
  const model = sourceWords(false);
  const none = outcomeView({status: 'no_match', outcome_source: 'model_report', method: 'vocabulary', reason: 'No existing category is about astronomy.'}, model);
  assert.equal(none.heading, 'The reply reports no match');
  assert.equal(none.replyReason, 'No existing category is about astronomy.');
  assert.equal(none.showReason, false);
  assert.ok(none.second[0].includes('It did not check the reason.'));
  const unsupported = outcomeView({status: 'unsupported', outcome_source: 'model_report', method: 'vocabulary', reason: 'A quota.'}, model);
  assert.equal(unsupported.heading, 'The reply reports that the controls cannot express this request');
  assert.equal(unsupported.next.some(line => line.includes('item descriptions')), false);   // m10: the other method stops a quota too
  const unclear = outcomeView({status: 'clarify', method: 'vocabulary', clarification: {model_reason: 'Heavy can mean two things.', alternatives: ['a', 'b']}}, model);
  assert.equal(unclear.kind, 'model_report');
  assert.equal(unclear.replyReason, 'Heavy can mean two things.');
  assert.ok(unclear.next.some(line => line.includes('listed meanings')));
});

test('states that the page itself finds have their own words (M7, m11)', () => {
  const words = sourceWords(false);
  assert.equal(outcomeKind({page: 'expired'}), 'expired');
  assert.equal(outcomeView({page: 'expired', method: 'vocabulary'}, words).heading, 'This review has expired');
  assert.ok(outcomeView({page: 'expired', method: 'vocabulary'}, words).next[0].includes('calls the model again'));
  assert.equal(outcomeView({page: 'network'}, words).heading, 'The page cannot reach the server');
  assert.equal(outcomeView({page: 'session'}, words).heading, 'The session has ended');
  assert.equal(outcomeView({thrown: true, method: 'manual_category', reason: 'x'}, words).heading, 'The request failed');
});

test('the stage line follows the real state of the panel (M11)', () => {
  const states = input => stageStates(input).map(s => s.state).join(' ');
  const texts = input => Object.fromEntries(stageStates(input).map(s => [s.name, s.text]));
  assert.deepEqual(stageStates().map(s => s.name), STAGES);
  assert.equal(states({method: 'vocabulary', phase: 'idle'}), 'now todo todo todo todo todo');
  assert.equal(states({method: 'vocabulary', phase: 'working', stage: 'Interpretation'}), 'done now todo todo todo todo');
  assert.equal(states({method: 'staged', phase: 'working', stage: 'Evidence'}), 'done done now todo todo todo');
  assert.equal(states({method: 'staged', phase: 'interpretation'}), 'done now todo todo todo todo');
  assert.equal(states({method: 'vocabulary', phase: 'preview'}), 'done done done now todo todo');
  assert.equal(states({method: 'vocabulary', phase: 'preview', historyAction: 'undo'}), 'done done done done done now');
  assert.equal(states({method: 'vocabulary', phase: 'applied'}), 'done done done done done now');
  // State 1 and 2: a removal of every control is not an undo.
  assert.equal(texts({method: 'vocabulary', phase: 'cleared'}).Request, 'now: every control is removed');
  assert.equal(texts({method: 'vocabulary', phase: 'preview', historyAction: 'clear'}).Preview, 'now: review the removal');
  // State 3: a stop in the evidence stage is shown there.
  assert.equal(texts({method: 'staged', phase: 'stopped', stage: 'Evidence'}).Evidence, 'now: stopped; nothing applied');
  // State 4: an expired review.
  assert.equal(texts({method: 'vocabulary', phase: 'expired'}).Preview, 'now: expired; nothing applied');
  // State 5 and 6: the undo stage follows the server.
  assert.equal(texts({method: 'vocabulary', phase: 'undone'}).Undo, 'done');
  assert.equal(texts({method: 'vocabulary', phase: 'idle', canUndo: true}).Undo, 'available');
  assert.equal(texts({method: 'vocabulary', phase: 'idle', canUndo: false}).Undo, 'not yet');
  // The manual method has no interpretation by a model, in every phase.
  for (const phase of ['idle', 'working', 'interpretation', 'preview', 'applied', 'undone', 'stopped'])
    assert.equal(stageStates({method: 'manual_category', phase, stage: 'Evidence'})[1].state, 'skipped');
});

test('local checks repeat only what the record lets the page recompute', () => {
  const described = group('d', exclude, [1], {evidence: [{item_id: 1, field: 'caption', quote: 'the food'}]});
  const context = [{item_id: 1, field: 'caption', quote: 'the food', quote_present: true, supplied_field_text: 'the food is here'}];
  const good = localChecks(described, {evidence_context: context});
  assert.ok(good.every(c => c.passed === true), JSON.stringify(good));
  assert.ok(good.some(c => c.check.startsWith('Every quotation is present')));
  assert.ok(good.some(c => c.detail === '1 quotation for 1 item'));
  // A quotation that the current text no longer holds is a failed check, not a hidden one.
  const bad = localChecks(described, {evidence_context: [{...context[0], quote_present: false}]});
  assert.equal(bad.find(c => c.check.startsWith('Every quotation is present')).passed, false);
  // Without the context rows the page does not claim that check.
  assert.equal(localChecks(described, {}).some(c => c.check.startsWith('Every quotation is present')), false);
  // More than half of the scope is a failed check.
  assert.equal(localChecks(group('wide', exclude, [1, 2, 3]), {}).find(c => c.check.startsWith('The selection covers')).passed, false);
  // A span that is not part of the request is a failed check.
  assert.equal(localChecks(group('span', {...exclude, intent_span: 'not in the request'}, [1]), {}).find(c => c.check.startsWith('The quoted part')).passed, false);
  const manual = group('m', {operation: 'exclude', strength: 'none', intent_span: 'K1'}, [2], {provenance: {...hashes, model: {backend: 'manual_category'}}});
  const categories = {1: ['K2'], 2: ['K1'], 3: ['K2'], 4: ['K3']};
  assert.ok(localChecks(manual, {}, {categories}).find(c => c.check.includes('exactly the items of the category K1 in the scope')).passed);
  assert.equal(localChecks(manual, {}, {categories: {...categories, 3: ['K1']}}).find(c => c.check.includes('exactly the items')).passed, false);
  assert.equal(localChecks(manual, {}, {}).some(c => c.check.includes('exactly the items')), false);
  // M15: no fixed "no model" line among the checks.
  assert.equal(localChecks(manual, {}, {categories}).some(c => /model/i.test(c.check)), false);
  const staged = group('s', exclude, [1], {induction: {envelope: {field_evidence: [{item_id: 1}, {item_id: 2}],
    evidence_audit: {assessment: {assessments: [{item_id: 1}, {item_id: 2}]}, withheld: [{item_id: 2}, {item_id: 3, missing_literal_terms: ['20']}]}}}}, [1, 2]);
  const stagedChecks = localChecks(staged, {});
  assert.ok(stagedChecks.every(c => c.passed === true), JSON.stringify(stagedChecks));
  assert.ok(stagedChecks.some(c => c.detail === 'item 2'));
});

test('a manual control names the items of its category outside the scope (m1)', () => {
  const manual = group('m', {operation: 'exclude', strength: 'none', intent_span: 'Cooking'}, [3], {provenance: {model: {backend: 'manual_category'}}}, [3, 4]);
  assert.deepEqual(outsideScope(manual, {categories: {1: ['Cooking'], 2: ['Travel'], 3: ['Cooking'], 5: ['Cooking']}, outside: [1, 2, 5]}), [1, 5]);
  assert.deepEqual(outsideScope(group('d', exclude, [1]), {outside: [5]}), []);
});

test('the change record states what Apply and Undo did', () => {
  const control = group('Exclude: Cooking', exclude, [1, 2]);
  const before = {groups: [], feed: {items: items([1, 2, 3]), available_items: 3}};
  const after = {groups: [control], feed: {items: items([3]), available_items: 1}};
  const applied = changeRecord(before, {history_action: 'none'}, after, 'now');
  assert.equal(applied.kind, 'apply');
  assert.deepEqual(applied.added, [{label: 'Exclude: Cooking', action: 'Remove from the feed', item_ids: [1, 2]}]);
  assert.deepEqual(applied.diff.leaves, [1, 2]);
  assert.deepEqual([applied.eligible_before, applied.eligible_after], [3, 1]);
  const undone = changeRecord(after, {history_action: 'undo'}, before, 'later');
  assert.equal(undone.kind, 'undo');
  assert.deepEqual(undone.removed.map(g => g.label), ['Exclude: Cooking']);
  assert.deepEqual(undone.active, []);
  assert.deepEqual(undone.diff.enters, [1, 2]);
  assert.equal(changeRecord(after, {history_action: 'clear'}, before, 'later').kind, 'clear');
  assert.deepEqual(controlLines([control], 1), ['Applied control: Exclude: Cooking (Remove from the feed).']);
  assert.deepEqual(controlLines([control], 3), []);
});
