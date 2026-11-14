// Display logic for the language-control review. No React and no network calls,
// so that every rule on this page can be tested with plain data.
//
// Nothing here decides membership or approves a change. The server validates and
// seals each proposal. These functions only arrange what the server returned.

export const WEIGHT = {light: 0.10, standard: 0.25, strong: 0.40};
export const STAGES = ['Request', 'Interpretation', 'Evidence', 'Preview', 'Apply', 'Undo'];

// Which kind of evidence produced a group. The value selects the wording only.
export function routeOf(group) {
  const proposal = group?.proposal || {};
  if (proposal.grounding === 'vocabulary') return 'vocabulary';
  if (proposal.induction) return proposal.induction.envelope?.evidence_audit ? 'staged' : 'induction';
  if (proposal.provenance?.model?.backend === 'manual_category') return 'manual';
  return 'description';
}

export function actionWords(action) {
  if (!action) return 'No action';
  if (action.operation === 'exclude') return 'Remove from the feed';
  const weight = WEIGHT[action.strength];
  const size = weight === undefined ? action.strength : `${action.strength}, ${action.operation === 'boost' ? '+' : '-'}${weight.toFixed(2)}`;
  return action.operation === 'boost' ? `Show more (${size})` : `Show less, still in the feed (${size})`;
}

export function termWords(term) {
  if (!term) return '';
  const kind = term.kind === 'tag' ? 'tag' : term.level && term.level > 1 ? `category (level ${term.level})` : 'category';
  return `${kind} "${term.value}"`;
}

// Net effect per item across every group in a plan. Exclusion takes priority.
export function netEffects(groups) {
  const net = {};
  for (const group of groups || []) {
    const action = group.proposal.action;
    for (const id of group.proposal.item_ids) {
      const entry = net[id] || (net[id] = {excluded: false, delta: 0});
      if (action.operation === 'exclude') entry.excluded = true;
      else entry.delta += (action.operation === 'boost' ? 1 : -1) * (WEIGHT[action.strength] || 0);
    }
  }
  return net;
}

export function resultWords(entry) {
  if (!entry) return 'Unchanged';
  if (entry.excluded) return 'Removed from the feed';
  // Sums of 0.10, 0.25 and 0.40 can leave a binary remainder instead of zero.
  return entry.delta > 1e-9 ? 'Ranked higher' : entry.delta < -1e-9 ? 'Ranked lower' : 'Unchanged';
}

// A group is identified by the hash that the server sealed it with.
export function splitGroups(planGroups, appliedGroups) {
  const applied = new Set((appliedGroups || []).map(group => group.revision));
  const planned = new Set((planGroups || []).map(group => group.revision));
  return {
    added: (planGroups || []).filter(group => !applied.has(group.revision)),
    kept: (planGroups || []).filter(group => applied.has(group.revision)),
    removed: (appliedGroups || []).filter(group => !planned.has(group.revision)),
  };
}

// Categories and tags of each item, from the term list of the evidence scope.
export function labelsByItem(terms) {
  const labels = {};
  for (const term of terms || []) for (const id of term.item_ids || []) {
    (labels[id] || (labels[id] = [])).push({kind: term.kind, level: term.level ?? null, value: term.value});
  }
  return labels;
}

function quoted(text) {
  return text ? ` · "${text}"` : '';
}

// One block of rows per group, one row per item in the evidence scope.
// `context` = {terms, vocabulary, descriptions, categories}; every part is optional.
export function planRows(pending, current, context = {}) {
  const groups = pending?.groups || [];
  const net = netEffects(groups);
  const {added} = splitGroups(groups, current?.groups);
  const fresh = new Set(added.map(group => group.revision));
  const labels = context.terms ? labelsByItem(context.terms) : null;
  const text = {...(context.descriptions || {})};
  for (const row of pending?.scope_items || []) text[row.item_id] = row.source_text;
  const controls = pending?.vocabulary?.controls || [];
  return groups.map((group, index) => {
    const proposal = group.proposal, route = routeOf(group);
    const envelope = proposal.induction?.envelope, audit = envelope?.evidence_audit;
    const primary = Object.fromEntries((audit?.primary_envelope?.field_evidence || envelope?.field_evidence || []).map(row => [row.item_id, row]));
    const final = Object.fromEntries((envelope?.field_evidence || []).map(row => [row.item_id, row]));
    const assessed = Object.fromEntries((audit?.assessment?.assessments || []).map(row => [row.item_id, row]));
    const cited = {};
    for (const row of proposal.evidence || []) (cited[row.item_id] || (cited[row.item_id] = [])).push(row);
    // For a category-and-tag control the server lists the members of each chosen term.
    const control = route === 'vocabulary' ? controls.find(candidate => candidate.label === group.label) : null;
    const chosen = control?.terms || null;
    const rows = group.scope_ids.map(id => {
      const member = proposal.item_ids.includes(id);
      const own = labels ? (labels[id] || []) : null;
      let evidence, second = null, reason = null;
      if (route === 'staged' || route === 'induction') {
        evidence = primary[id] ? `${primary[id].verdict}${quoted(primary[id].evidence_quote)}` : member ? 'selected' : 'not selected';
        second = assessed[id] ? `${assessed[id].assessment}${quoted(assessed[id].quote)}` : null;
        reason = final[id]?.reason || null;
      } else if (route === 'vocabulary') {
        const through = chosen ? chosen.filter(term => (term.item_ids || []).includes(id))
          : (cited[id] || []).map(row => (proposal.vocabulary_terms || []).find(term => term.field === row.field && term.value === row.quote) || {kind: row.field === 'topic_tag' ? 'tag' : 'category', value: row.quote});
        evidence = member ? `selected through ${through.map(termWords).join(' and ') || 'a chosen term'}`
          : own && own.length === 0 ? 'not selected: this item has no category and no tag'
          : 'not selected: none of its categories or tags was chosen';
      } else if (route === 'manual') {
        evidence = member ? `selected: its category is ${proposal.action.intent_span}` : `not selected: its category is not ${proposal.action.intent_span}`;
      } else {
        evidence = member ? `selected${(cited[id] || []).map(row => `${quoted(row.quote)} (${row.field})`).join('')}` : 'not selected: no quotation was cited for this item';
      }
      return {key: `${index}-${id}`, id, member, description: text[id] ?? null, labels: own, evidence, second, reason,
        verdict: primary[id]?.verdict || null, assessment: assessed[id]?.assessment || null, result: resultWords(net[id])};
    });
    return {key: `${index}-${group.revision || group.label}`, label: group.label, route, isNew: fresh.has(group.revision),
      action: proposal.action, request: proposal.target_confirmation?.original_request || group.request, rows};
  });
}

// The first ten items now and after approval, with the items that leave, enter or move.
export function feedDiff(beforeItems, afterItems) {
  const before = (beforeItems || []).map(item => item.item_id), after = (afterItems || []).map(item => item.item_id);
  const leaves = before.filter(id => !after.includes(id)), enters = after.filter(id => !before.includes(id));
  const moved = after.filter(id => before.includes(id) && before.indexOf(id) !== after.indexOf(id))
    .map(id => ({id, from: before.indexOf(id) + 1, to: after.indexOf(id) + 1}));
  return {
    before: before.map((id, index) => ({id, rank: index + 1, note: leaves.includes(id) ? 'leaves' : ''})),
    after: after.map((id, index) => {
      const was = before.indexOf(id);
      return {id, rank: index + 1, note: was < 0 ? 'enters' : was > index ? `up ${was - index}` : was < index ? `down ${index - was}` : ''};
    }),
    leaves, enters, moved, unchanged: leaves.length === 0 && enters.length === 0 && moved.length === 0,
  };
}

const CASE_NAMES = {
  literal: 'A literal category name', mixed: 'Two preferences in one request', ambiguous: 'An ambiguous request',
  unsupported: 'A request that the controls cannot express', negated: 'A negated command', no_match: 'A request that matches nothing',
};

// Bundled example requests of one method. The server sends a flat dictionary:
// "<method>" is the main request and "<method>:<case>" is a further example.
export function exampleOptions(requests, method) {
  if (!requests || typeof requests !== 'object' || !method) return [];
  const options = [];
  if (typeof requests[method] === 'string') options.push({key: method, name: 'The main bundled request', text: requests[method]});
  for (const key of Object.keys(requests)) {
    if (!key.startsWith(method + ':') || typeof requests[key] !== 'string') continue;
    const name = key.slice(method.length + 1);
    options.push({key, name: CASE_NAMES[name] || name.replace(/[_-]+/g, ' '), text: requests[key]});
  }
  return options;
}

// Plain words for a result that proposes no change.
// options.alternatives: the reply named alternatives. options.guard: the application stopped the request before any model call.
export function outcomeCopy(status, method, options = {}) {
  const other = method === 'vocabulary' ? 'Try the method that matches your request to item descriptions.'
    : method === 'configured_model' || method === 'ollama' ? 'Try the method that matches your request to existing categories and tags.'
    : method === 'manual_category' ? 'Choose another category, or use a method with a model.'
    : 'Use another method, for example an existing category.';
  if (status === 'clarify') return {heading: 'The request needs clarification',
    next: [options.guard ? 'Write the request as a positive instruction, for example "show more ..." or "remove ...". The application does not guess the meaning of a negated command.'
        : 'Write the request again and name one clear subject and one direction (more, less or none).',
      ...(options.alternatives ? ['Use one of the alternatives that the model named as your new request.'] : []), other]};
  if (status === 'no_match') return {heading: method === 'vocabulary' ? 'No existing category or tag matches the request' : 'Nothing in the evidence matches the request',
    next: ['Check the evidence scope: only the listed items and their data were used.', 'Write the request with other words.', other]};
  if (status === 'unsupported') return {heading: 'The controls cannot express this request',
    next: ['The controls can show more, show less or remove a set of items. They cannot count items, use a time or a condition, or make an exception.',
      'Write a request that asks for more, less or none of one subject.', other]};
  if (status === 'cancelled') return {heading: 'The review was cancelled', next: ['Start again with a new request.']};
  return {heading: 'The step stopped with an error',
    next: ['Read the message. It comes from the application or from the model provider.',
      'If the message names a connection, a key or a model, correct that setting and start the server again.',
      'If the message says that the reply was rejected, send the request again or use another method.']};
}

// The six stages of one control, from the real state of the panel.
// phase: idle | working | interpretation | preview | applied | undone
export function stageStates({method = 'manual_category', phase = 'idle', busyStage = null, historyAction = 'none', stopped = false} = {}) {
  const manual = method === 'manual_category';
  const index = name => STAGES.indexOf(name);
  let now = 0, note = {};
  if (phase === 'working') now = Math.max(0, index(busyStage || 'Interpretation'));
  else if (phase === 'interpretation') { now = index('Interpretation'); note.Interpretation = stopped ? 'needs your input' : 'review it'; }
  else if (phase === 'preview') now = historyAction === 'none' ? index('Preview') : index('Undo');
  else if (phase === 'applied') now = index('Undo');
  // The manual method has no interpretation by a model: a stop there belongs to the evidence stage.
  if (manual && now === index('Interpretation')) { now = index('Evidence'); if (stopped) note.Evidence = 'needs your input'; }
  if (phase === 'applied') note.Undo = 'available';
  if (phase === 'preview' && historyAction !== 'none') note.Undo = 'review it';
  if (phase === 'preview' && historyAction === 'none') note.Preview = 'your decision';
  if (phase === 'undone') note.Request = 'the last change is undone';
  return STAGES.map((name, position) => {
    if (manual && name === 'Interpretation') return {name, state: 'skipped', note: 'no model'};
    const state = phase === 'applied' ? (position < index('Undo') ? 'done' : 'now') : position < now ? 'done' : position === now ? 'now' : 'todo';
    return {name, state, note: note[name] || ''};
  });
}

function shortHash(value) {
  return typeof value === 'string' && value.length >= 12 ? value.slice(0, 12) : null;
}

// Checks that this page can repeat from the reviewed record itself. The server
// made its own checks before it returned the review; these lines restate the
// ones that the response lets the page recompute. They say nothing about meaning.
export function localChecks(group, pending, context = {}) {
  const proposal = group.proposal, route = routeOf(group), scope = group.scope_ids || [], members = proposal.item_ids || [];
  const checks = [
    {check: 'Every selected item is in the evidence scope', passed: members.every(id => scope.includes(id)), detail: `${members.length} selected of ${scope.length} supplied`},
    {check: 'No item is selected twice', passed: new Set(members).size === members.length, detail: null},
  ];
  if (route === 'description') {
    const evidence = proposal.evidence || [];
    checks.push({check: 'Every selected item has its own quotation', detail: `${evidence.length} quotations for ${members.length} items`,
      passed: evidence.length === members.length && evidence.every(row => members.includes(row.item_id))});
    const rows = (pending?.evidence_context || []).filter(row => evidence.some(e => e.item_id === row.item_id && e.field === row.field && e.quote === row.quote));
    if (rows.length) checks.push({check: 'Every quotation is present in the supplied text of its own item',
      passed: rows.length === evidence.length && rows.every(row => row.quote_present === true), detail: `${rows.filter(row => row.quote_present === true).length} of ${evidence.length}`});
    if (typeof group.request === 'string' && typeof proposal.action?.intent_span === 'string')
      checks.push({check: 'The quoted part of the request is an exact part of the request', passed: group.request.includes(proposal.action.intent_span), detail: `"${proposal.action.intent_span}"`});
    checks.push({check: 'The selection covers at most half of the evidence scope', passed: members.length <= scope.length / 2, detail: `${members.length} of ${scope.length}`});
  } else if (route === 'manual') {
    const categories = context.categories || {};
    const known = scope.filter(id => Array.isArray(categories[id]));
    if (known.length === scope.length) checks.push({check: `The selected items are exactly the items of the category ${proposal.action.intent_span}`,
      passed: scope.every(id => members.includes(id) === categories[id].includes(proposal.action.intent_span)), detail: `${members.length} of ${scope.length}`});
    checks.push({check: 'No model was used for this control', passed: true, detail: null});
  } else if (route === 'staged' || route === 'induction') {
    const envelope = proposal.induction?.envelope || {}, audit = envelope.evidence_audit;
    checks.push({check: 'Every item in the scope has one classification', passed: (envelope.field_evidence || []).length === scope.length, detail: `${(envelope.field_evidence || []).length} of ${scope.length}`});
    if (audit) {
      const assessed = audit.assessment?.assessments || [], withheld = audit.withheld || [];
      checks.push({check: 'Every item in the scope has one separate evidence assessment', passed: assessed.length === scope.length, detail: `${assessed.length} of ${scope.length}`});
      const disagreed = withheld.filter(row => !row.missing_literal_terms?.length).map(row => row.item_id);
      const missing = withheld.filter(row => row.missing_literal_terms?.length).map(row => row.item_id);
      checks.push({check: 'An item on which the two model calls disagree stays unknown and is not selected', passed: disagreed.every(id => !members.includes(id)), detail: disagreed.length ? `items ${disagreed.join(', ')}` : 'no disagreement'});
      checks.push({check: 'An item without a required literal term stays unknown and is not selected', passed: missing.every(id => !members.includes(id)), detail: missing.length ? `items ${missing.join(', ')}` : 'none'});
    }
  }
  const provenance = proposal.provenance || {};
  const sealed = [['source', provenance.source_sha256], ['request', provenance.request_sha256], ['action', provenance.action_sha256]]
    .filter(([, value]) => shortHash(value)).map(([name, value]) => `${name} ${shortHash(value)}`);
  if (sealed.length) checks.push({check: 'The record is bound to the source, the request and the action by their hashes', passed: true, detail: sealed.join(' · ')});
  return checks;
}

// What Apply or Undo did, from the state before and the state that the server returned.
export function changeRecord(before, plan, after, time) {
  const {added, removed} = splitGroups(after?.groups, before?.groups);
  const diff = feedDiff(before?.feed?.items, after?.feed?.items);
  const brief = group => ({label: group.label, action: actionWords(group.proposal.action), item_ids: [...group.proposal.item_ids]});
  return {time, kind: plan?.history_action && plan.history_action !== 'none' ? plan.history_action : 'apply',
    added: added.map(brief), removed: removed.map(brief), active: (after?.groups || []).map(group => group.label), diff,
    eligible_before: before?.feed?.available_items ?? null, eligible_after: after?.feed?.available_items ?? null};
}
