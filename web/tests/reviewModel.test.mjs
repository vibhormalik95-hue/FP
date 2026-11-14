// Tests of the display logic with authored data. No browser and no model.
import test from 'node:test';
import assert from 'node:assert/strict';
import {actionWords, changeRecord, exampleOptions, feedDiff, labelsByItem, localChecks, netEffects, outcomeCopy, planRows,
  resultWords, routeOf, splitGroups, stageStates, STAGES, termWords} from '../src/reviewModel.js';

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
});

test('net effect: removal wins, opposite rank changes cancel', () => {
  const net = netEffects([group('up', boost, [1, 2]), group('out', exclude, [2]), group('down', {operation: 'reduce', strength: 'standard'}, [1])]);
  assert.equal(resultWords(net[2]), 'Removed from the feed');
  assert.equal(resultWords(net[1]), 'Unchanged');
  assert.equal(resultWords(net[3]), 'Unchanged');
  assert.equal(resultWords(netEffects([group('up', boost, [4])])[4]), 'Ranked higher');
  assert.equal(resultWords(netEffects([group('down', {operation: 'reduce', strength: 'light'}, [4])])[4]), 'Ranked lower');
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

test('description, manual and staged routes keep their own evidence wording', () => {
  const described = group('d', exclude, [1], {evidence: [{item_id: 1, field: 'caption', quote: 'eats a meal'}]});
  const manual = group('m', {operation: 'exclude', strength: 'none', intent_span: 'K1'}, [2], {provenance: {model: {backend: 'manual_category'}}});
  const staged = group('s', exclude, [1], {induction: {envelope: {
    field_evidence: [{item_id: 1, verdict: 'match', evidence_quote: 'q1', reason: 'because'}, {item_id: 2, verdict: 'unknown', evidence_quote: '', reason: 'withheld'}],
    evidence_audit: {primary_envelope: {field_evidence: [{item_id: 1, verdict: 'match', evidence_quote: 'q1'}, {item_id: 2, verdict: 'match', evidence_quote: 'q2'}]},
      assessment: {assessments: [{item_id: 1, assessment: 'supported', quote: 'q1'}, {item_id: 2, assessment: 'not_stated', quote: ''}]}, withheld: [{item_id: 2}]}}}}, [1, 2]);
  const rows = planRows({groups: [described, manual, staged], scope_items: []}, {groups: [manual]}, {});
  assert.equal(rows[0].rows[0].evidence, 'selected · "eats a meal" (caption)');
  assert.equal(rows[0].rows[1].evidence, 'not selected: no quotation was cited for this item');
  assert.equal(rows[1].isNew, false);
  assert.equal(rows[1].rows[1].evidence, 'selected: its category is K1');
  assert.equal(rows[1].rows[0].evidence, 'not selected: its category is not K1');
  assert.equal(rows[2].rows[0].evidence, 'match · "q1"');
  assert.equal(rows[2].rows[0].second, 'supported · "q1"');
  // The first call said match, the separate assessment disagreed: the final verdict is unknown.
  assert.equal(rows[2].rows[1].evidence, 'match · "q2"');
  assert.equal(rows[2].rows[1].second, 'not_stated');
  assert.equal(rows[2].rows[1].reason, 'withheld');
  assert.equal(rows[2].rows[1].member, false);
  assert.equal(rows[0].rows[0].labels, null);
});

test('labels by item come only from the supplied term list', () => {
  const labels = labelsByItem(terms);
  assert.deepEqual(labels[2], [{kind: 'category', level: 1, value: 'Cooking'}, {kind: 'category', level: 2, value: 'Baking'}]);
  assert.equal(labels[4], undefined);
});

test('feed difference names the items that leave, enter and move', () => {
  const items = ids => ids.map(item_id => ({item_id}));
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

test('each result without a change has a plain heading and a next step', () => {
  for (const status of ['clarify', 'no_match', 'unsupported', 'error', 'cancelled']) for (const method of ['vocabulary', 'configured_model', 'staged', 'manual_category']) {
    const copy = outcomeCopy(status, method);
    assert.ok(copy.heading.length > 10);
    assert.ok(copy.next.length >= 1 && copy.next.every(line => line.length > 10));
  }
  assert.equal(outcomeCopy('no_match', 'vocabulary').heading, 'No existing category or tag matches the request');
  assert.equal(outcomeCopy('unknown status', 'vocabulary').heading, 'The step stopped with an error');
  // The advice about alternatives appears only when the reply named some; a stop by the application's own guard says so.
  assert.equal(outcomeCopy('clarify', 'vocabulary').next.some(line => line.includes('alternatives')), false);
  assert.equal(outcomeCopy('clarify', 'vocabulary', {alternatives: true}).next.some(line => line.includes('alternatives')), true);
  assert.ok(outcomeCopy('clarify', 'vocabulary', {guard: true}).next[0].includes('positive instruction'));
});

test('the stage line reflects the phase of the control', () => {
  const states = input => stageStates(input).map(s => s.state).join(' ');
  assert.deepEqual(stageStates().map(s => s.name), STAGES);
  assert.equal(states({method: 'vocabulary', phase: 'idle'}), 'now todo todo todo todo todo');
  assert.equal(states({method: 'vocabulary', phase: 'working', busyStage: 'Interpretation'}), 'done now todo todo todo todo');
  assert.equal(states({method: 'staged', phase: 'working', busyStage: 'Evidence'}), 'done done now todo todo todo');
  assert.equal(states({method: 'staged', phase: 'interpretation'}), 'done now todo todo todo todo');
  assert.equal(states({method: 'vocabulary', phase: 'preview'}), 'done done done now todo todo');
  assert.equal(states({method: 'vocabulary', phase: 'preview', historyAction: 'undo'}), 'done done done done done now');
  assert.equal(states({method: 'vocabulary', phase: 'applied'}), 'done done done done done now');
  assert.equal(states({method: 'vocabulary', phase: 'undone'}), 'now todo todo todo todo todo');
  // The manual method has no interpretation by a model, in every phase.
  for (const phase of ['idle', 'working', 'interpretation', 'preview', 'applied', 'undone'])
    assert.equal(stageStates({method: 'manual_category', phase, busyStage: 'Evidence'})[1].state, 'skipped');
  assert.equal(stageStates({method: 'manual_category', phase: 'interpretation', stopped: true})[2].state, 'now');
  assert.equal(stageStates({method: 'vocabulary', phase: 'interpretation', stopped: true})[1].note, 'needs your input');
  assert.equal(stageStates({method: 'vocabulary', phase: 'applied'})[5].note, 'available');
});

test('local checks repeat only what the record lets the page recompute', () => {
  const described = group('d', exclude, [1], {evidence: [{item_id: 1, field: 'caption', quote: 'the food'}]});
  const context = [{item_id: 1, field: 'caption', quote: 'the food', quote_present: true, supplied_field_text: 'the food is here'}];
  const good = localChecks(described, {evidence_context: context});
  assert.ok(good.every(c => c.passed === true), JSON.stringify(good));
  assert.ok(good.some(c => c.check.startsWith('Every quotation is present')));
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
  assert.ok(localChecks(manual, {}, {categories}).find(c => c.check.includes('exactly the items of the category K1')).passed);
  assert.equal(localChecks(manual, {}, {categories: {...categories, 3: ['K1']}}).find(c => c.check.includes('exactly the items')).passed, false);
  assert.equal(localChecks(manual, {}, {}).some(c => c.check.includes('exactly the items')), false);
  const staged = group('s', exclude, [1], {induction: {envelope: {field_evidence: [{item_id: 1}, {item_id: 2}],
    evidence_audit: {assessment: {assessments: [{item_id: 1}, {item_id: 2}]}, withheld: [{item_id: 2}, {item_id: 3, missing_literal_terms: ['20']}]}}}}, [1, 2]);
  const stagedChecks = localChecks(staged, {});
  assert.ok(stagedChecks.every(c => c.passed === true), JSON.stringify(stagedChecks));
  assert.ok(stagedChecks.some(c => c.detail === 'items 2'));
});

test('the change record states what Apply and Undo did', () => {
  const items = ids => ids.map(item_id => ({item_id}));
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
});
