// Display logic for the language-control review. No React and no network calls,
// so that every rule on this page can be tested with plain data.
//
// Nothing here decides membership or approves a change. The server validates and
// seals each proposal. These functions only arrange what the server returned.

export const WEIGHT = {light: 0.10, standard: 0.25, strong: 0.40};
export const STAGES = ['Request', 'Interpretation', 'Evidence', 'Preview', 'Apply', 'Undo'];
// The server accepts a review for 300 seconds after it made it. The page starts its
// own clock when the answer arrives, so it ends a little earlier than the server.
export const REVIEW_SECONDS = 300;
export const REVIEW_MARGIN_SECONDS = 5;

export const plural = (count, one, many = one + 's') => `${count} ${count === 1 ? one : many}`;

// The words for the source of a reply. A server that answers with hand-written
// replies is never called a model.
export function sourceWords(authored) {
  return authored ? {
    authored: true,
    block: 'Authored reply (written by hand, not a model)',
    the: 'the authored reply', The: 'The authored reply', suffix: 'authored replies, no model',
    reason: 'Reason in the authored reply:', controlReason: 'Reason for this control in the authored reply:', names: 'Names in the authored reply:', quotations: 'Quotations in the authored reply:',
    name: 'Name in the authored reply:', raw: 'Raw authored reply', rawMany: 'Raw authored replies',
    caution: 'An authored reply shows the screens only. It says nothing about a model.',
    waiting: 'Reading the authored reply', flag: ' · AUTHORED REPLIES, NO MODEL',
    call: 'reply lookup', second: 'a second authored reply', read: 'taken from the authored reply',
  } : {
    authored: false,
    block: 'Model output (not verified)',
    the: 'the model', The: 'The model', suffix: 'model',
    reason: 'Reason that the model gave:', controlReason: 'Reason that the model gave for this control:', names: 'Existing names that the model chose:', quotations: 'Quotations that the model cited:',
    name: 'Name proposed by the model:', raw: 'Raw model reply', rawMany: 'Raw model replies',
    caution: 'The model can be wrong. This block repeats what it returned. Nothing here is approved.',
    waiting: 'Waiting for the provider', flag: '',
    call: 'model call', second: 'a second model call', read: 'read from your request by the model',
  };
}

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

const FIELD_WORDS = {caption: 'description', manual_cover_text: 'cover text', topic_tag: 'tags',
  first_level_category_name: 'category name', second_level_category_name: 'category name, level 2', third_level_category_name: 'category name, level 3'};
export const fieldWords = field => FIELD_WORDS[field] || field || 'no field';

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

export function rankMap(items) {
  return Object.fromEntries((items || []).map((item, index) => [item.item_id, index + 1]));
}

// What approval does to one item. `place` = {before, after}: its position in the
// first ten now and after approval (null when it is not in that list). The words
// "ranked higher" and "ranked lower" are used only when the position changes.
export function resultWords(entry, place) {
  if (!entry) return 'Unchanged';
  if (entry.excluded) return 'Removed from the feed';
  // Sums of 0.10, 0.25 and 0.40 can leave a binary remainder instead of zero.
  if (Math.abs(entry.delta) < 1e-9) return 'Unchanged (the score changes cancel)';
  const score = `Score ${entry.delta > 0 ? '+' : '-'}${Math.abs(entry.delta).toFixed(2)}`;
  if (!place) return score;
  const {before = null, after = null} = place;
  if (before === null && after === null) return `${score}; not in the first ten`;
  if (before === null) return `${score}; enters the first ten at position ${after}`;
  if (after === null) return `${score}; leaves the first ten`;
  if (before === after) return `${score}; position ${after} stays`;
  return `${score}; ${after < before ? 'ranked higher' : 'ranked lower'}: position ${before} to ${after}`;
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

// Categories and tags of each item. `categories` (item id -> category names) is the
// source that the manual control reads. `terms` is the list of names in the item
// data. A name that both sources give for the same kind is listed once.
export function labelsByItem(terms, categories) {
  const labels = {};
  const add = (id, label) => {
    const list = labels[id] || (labels[id] = []);
    if (!list.some(seen => seen.value === label.value && (seen.kind === 'tag') === (label.kind === 'tag') && (seen.level || 1) === (label.level || 1))) list.push(label);
  };
  for (const [id, names] of Object.entries(categories || {})) for (const value of names || []) add(id, {kind: 'category', level: 1, value});
  for (const term of terms || []) for (const id of term.item_ids || []) add(id, {kind: term.kind, level: term.level ?? null, value: term.value});
  return labels;
}

function quoted(text) {
  return text ? ` · "${text}"` : '';
}

const VERDICT_WORDS = {match: 'matches the definition', not_match: 'does not match', unknown: 'no decision'};
const ASSESSMENT_WORDS = {supported: 'supported', contradicted: 'contradicted', not_stated: 'not stated', ambiguous: 'ambiguous'};

// One block of rows per control, one row per item in the evidence scope. New
// controls come first, because they are what the person decides on.
// `context` = {terms, categories, descriptions}; every part is optional.
export function planRows(pending, current, context = {}) {
  const groups = pending?.groups || [];
  const net = netEffects(groups);
  const {added} = splitGroups(groups, current?.groups);
  const fresh = new Set(added.map(group => group.revision));
  const haveLabels = Array.isArray(context.terms) || Boolean(context.categories);
  const labels = labelsByItem(context.terms, context.categories);
  const text = {...(context.descriptions || {})};
  for (const row of pending?.scope_items || []) text[row.item_id] = row.source_text;
  const before = rankMap(current?.feed?.items), after = rankMap(pending?.feed?.items);
  const controls = pending?.vocabulary?.controls || [];
  const blocks = groups.map((group, index) => {
    const proposal = group.proposal, route = routeOf(group);
    const envelope = proposal.induction?.envelope, audit = envelope?.evidence_audit;
    const primary = Object.fromEntries((audit?.primary_envelope?.field_evidence || envelope?.field_evidence || []).map(row => [row.item_id, row]));
    const final = Object.fromEntries((envelope?.field_evidence || []).map(row => [row.item_id, row]));
    const assessed = Object.fromEntries((audit?.assessment?.assessments || []).map(row => [row.item_id, row]));
    const withheld = Object.fromEntries((audit?.withheld || []).map(row => [row.item_id, row]));
    const cited = {};
    for (const row of proposal.evidence || []) (cited[row.item_id] || (cited[row.item_id] = [])).push(row);
    // For a category-and-tag control the server lists the members of each chosen term.
    const control = route === 'vocabulary' ? controls.find(candidate => candidate.label === group.label) : null;
    const chosen = control?.terms || null;
    const rows = group.scope_ids.map(id => {
      const member = proposal.item_ids.includes(id);
      const own = haveLabels ? (labels[id] || []) : null;
      let evidence = null, first = null, firstReason = null, second = null, secondReason = null, finalWords = null;
      if (route === 'staged' || route === 'induction') {
        // Each column keeps the words and the reason of its own call. The application's decision has its own column.
        first = primary[id] ? `${VERDICT_WORDS[primary[id].verdict] || primary[id].verdict}${quoted(primary[id].evidence_quote)}` : 'no classification';
        firstReason = primary[id]?.reason || null;
        if (audit) {
          second = assessed[id] ? `${ASSESSMENT_WORDS[assessed[id].assessment] || assessed[id].assessment}${quoted(assessed[id].quote)}` : 'no assessment';
          secondReason = assessed[id]?.reason || null;
        }
        const held = withheld[id];
        finalWords = member ? (audit ? 'Selected: the classification matches and the separate assessment supports it' : 'Selected: the classification matches')
          : held?.missing_literal_terms?.length ? `Not selected: the item text does not hold ${held.missing_literal_terms.join(', ')}`
          : held ? 'Not selected: the two calls do not agree'
          : final[id]?.verdict === 'not_match' ? 'Not selected: it does not match the definition'
          : 'Not selected: no decision';
      } else if (route === 'vocabulary') {
        const through = chosen ? chosen.filter(term => (term.item_ids || []).includes(id))
          : (cited[id] || []).map(row => (proposal.vocabulary_terms || []).find(term => term.field === row.field && term.value === row.quote) || {kind: row.field === 'topic_tag' ? 'tag' : 'category', value: row.quote});
        evidence = member ? `selected through ${through.map(termWords).join(' and ') || 'a chosen name'}`
          : own && own.length === 0 ? 'not selected: this item has no category and no tag'
          : 'not selected: none of its categories or tags was chosen';
      } else if (route === 'manual') {
        evidence = member ? `selected: its category is ${proposal.action.intent_span}`
          : own && own.every(label => label.kind === 'tag') ? 'not selected: this item has no category'
          : `not selected: its category is not ${proposal.action.intent_span}`;
      } else {
        evidence = member ? `selected${(cited[id] || []).map(row => `${quoted(row.quote)} (${fieldWords(row.field)})`).join('')}` : 'not selected: no quotation was cited for this item';
      }
      return {key: `${index}-${id}`, id, member, description: text[id] ?? null, labels: own, evidence, first, firstReason, second, secondReason, final: finalWords,
        verdict: primary[id]?.verdict || null, assessment: assessed[id]?.assessment || null, result: resultWords(net[id], {before: before[id] ?? null, after: after[id] ?? null})};
    });
    return {key: `${index}-${group.revision || group.label}`, label: group.label, route, isNew: fresh.has(group.revision),
      action: proposal.action, request: proposal.target_confirmation?.original_request || group.request, rows};
  });
  return [...blocks.filter(block => block.isNew), ...blocks.filter(block => !block.isNew)];
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

// Display fallback for a server that sends no plan notes: items that one control
// of the plan removes and another control of the plan ranks.
export function planConflicts(groups) {
  const notes = [];
  const removing = (groups || []).filter(group => group.proposal.action.operation === 'exclude');
  for (const other of (groups || []).filter(group => group.proposal.action.operation !== 'exclude')) {
    for (const remover of removing) {
      const both = other.proposal.item_ids.filter(id => remover.proposal.item_ids.includes(id));
      if (both.length) notes.push({kind: 'overridden', item_ids: both,
        message: `The control "${remover.label}" removes ${both.length === 1 ? 'item' : 'items'} ${both.join(', ')}. The control "${other.label}" also names ${both.length === 1 ? 'it' : 'them'} and has no effect there. Removal takes priority.`});
    }
  }
  return notes;
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

// The choices of the evidence scope for a starting list of `available` items (ten at most).
export function scopeChoices(available) {
  const size = Math.max(0, Math.min(10, available || 0));
  const all = {value: 10, size, name: size === 10 ? 'First 10 items of the starting list' : `All ${size} items of the starting list`};
  return size > 6 ? [{value: 6, size: 6, name: 'First 6 items of the starting list'}, all] : [all];
}

// An alternative that the reply named becomes part of the person's own request.
// The person's words stay; the meaning is added.
export function adoptText(request, alternative) {
  const own = (request || '').trim(), meaning = (alternative || '').trim().replace(/[.\s]+$/, '');
  if (!meaning) return own;
  return own ? `${own} (I mean: ${meaning}.)` : meaning + '.';
}

// Can the original conditions C, D and E read the categories of the served data?
// Their parser accepts only category IDs of the form category_<number>.
export function categoryIdsReadable(categories) {
  return Array.isArray(categories) && categories.length > 0 && categories.every(name => /^category_\d+$/.test(name));
}

const SOURCES = ['application_check', 'provider_failure', 'reply_rejected', 'model_report'];

// The stage of the six that a failed step of the server belongs to (`failed_stage`).
export function stageOfFailure(failedStage, fallback = 'Interpretation') {
  if (['interpretation', 'definition'].includes(failedStage)) return 'Interpretation';
  if (['evidence', 'membership', 'evidence_assessment', 'combined'].includes(failedStage)) return 'Evidence';
  return fallback;
}

// Every text in a result that came from a reply. A sentence of the server that equals one of them is reply text too.
export function replyTexts(outcome) {
  return [outcome?.clarification?.model_reason, outcome?.reply_reason].filter(text => typeof text === 'string' && text.trim());
}

// Why a request ended without a proposal. The server names the source in
// `outcome_source`. The page never infers "no call was made" from an empty list.
export function outcomeKind(outcome) {
  if (!outcome) return 'unknown';
  if (outcome.page) return outcome.page;                              // expired | session | network: states that the page itself found
  if (outcome.thrown) return 'request_failed';                        // the server answered with an error status, not with a result
  if (outcome.method === 'manual_category') return 'manual';
  if (SOURCES.includes(outcome.outcome_source)) return outcome.outcome_source;
  // A server without `outcome_source`. Only positive evidence counts: competing meanings, or a raw reply in the
  // list of calls, can only come from a reply. An empty list proves nothing, so the result stays 'unknown'.
  if (outcome.clarification && (outcome.clarification.model_reason || outcome.clarification.alternatives?.length)) return 'model_report';
  const replied = (outcome.model_calls || []).some(call => call && (call.raw_response !== undefined || call.raw_output !== undefined || typeof call.raw_text === 'string'));
  if (replied && ['no_match', 'unsupported', 'clarify'].includes(outcome.status)) return 'model_report';
  if (replied && ['error', 'duplicate'].includes(outcome.status)) return 'reply_rejected';
  return 'unknown';
}

// Plain words for a result that proposes no change: heading, the sentences of the
// first block (what came back), of the second block (what the application did)
// and the next steps. Text that a reply holds is returned apart, as `replyReason`.
export function outcomeView(outcome, words = sourceWords(false)) {
  const kind = outcomeKind(outcome), status = outcome?.status || 'error', method = outcome?.method;
  const checks = outcome?.vocabulary?.checks || outcome?.checks || [];
  const failed = checks.filter(check => check.passed === false).map(check => `${check.check} ${check.detail || ''}`).join(' ');
  const reply = words.authored ? 'The authored reply' : 'The reply';
  const view = {kind, heading: 'The request stopped', first: [], replyReason: null, second: [], next: [], showReason: true};
  if (kind === 'expired') {
    view.heading = 'This review has expired';
    view.first = ['The proposal of this review is no longer open.'];
    view.second = ['A review is valid for five minutes. The server no longer accepts this one: it is too old, or a newer request replaced it.'];
    view.showReason = Boolean(outcome.reason);
    view.next = [`Send the request again to get a new review.${method && method !== 'manual_category' ? (words.authored ? ' The server reads the authored reply again.' : ' A model method calls the model again.') : ''}`];
  } else if (kind === 'session') {
    view.heading = 'The session has ended';
    view.first = ['No reply reached this page.'];
    view.second = ['The server does not know this session. It was started again, or the session ended. The controls that this page showed are no longer on the server.'];
    view.next = ['Reload the page to start a new session. A new session has no applied controls.'];
  } else if (kind === 'network') {
    view.heading = 'The page cannot reach the server';
    view.first = ['No reply reached this page.'];
    view.second = ['The request did not reach the server, or the answer did not come back.'];
    view.next = ['Check that the server runs.', 'Then reload the page. A server that was started again has no applied controls.'];
  } else if (kind === 'manual') {
    view.heading = status === 'no_match' ? 'No item in the scope has this category' : 'The request stopped';
    view.next = ['Choose another category, or a larger evidence scope.'];
  } else if (kind === 'application_check') {
    view.heading = 'The application stopped the request';
    view.first = [`${words.authored ? 'The server did not look up an authored reply.' : 'No model call was made.'} The application stopped the request with its own check.`];
    view.next = ['Read the reason and the failed check under "Application checks".'];
    if (status === 'limit') {
      view.heading = 'At most eight controls can be applied';
      view.next = ['Remove an applied control first, or choose "Replace every applied control".'];
    } else if (status === 'label_collision') {
      view.heading = 'An applied control has the same name';
      view.next = ['Change the name of this control, or remove the applied control first.'];
    } else if (/negat/i.test(failed + ' ' + (outcome.reason || ''))) view.next.push('The application does not interpret a negated command such as "do not hide ...". Write what you want as a positive instruction, for example "remove ..." or "show more ...".');
    else if (/budget|too (long|large|many)/i.test(failed + ' ' + (outcome.reason || ''))) view.next.push('Choose a smaller evidence scope.');
    else view.next.push('Change the request or the applied controls so that the check passes.');
  } else if (kind === 'provider_failure') {
    if (words.authored) {
      view.heading = 'No authored reply exists for this request';
      view.first = ['The server looked up an authored reply for this request. None exists. Nothing was interpreted.', 'The message of the server is under "Application checks".'];
      view.next = ['Choose a bundled example: "Insert the bundled scenario request" or the list of examples.', 'Use the method and the evidence scope of that example.', 'To use your own words, start the server with a model route (docs/model-routes.md).'];
    } else {
      view.heading = 'The call to the provider failed';
      view.first = ['A call to the provider was started. No usable reply came back.', 'The message is under "Application checks".'];
      view.next = ['Read the message. It says what to change.', 'If it names a connection, a key or a model, correct that setting and start the server again.', 'Then send the request again. Each attempt is a new call.'];
    }
  } else if (kind === 'reply_rejected') {
    view.heading = status === 'duplicate' ? 'The proposed name already exists' : 'The application rejected the reply';
    view.first = [`${reply} came back. The application rejected it and used nothing from it.`, 'The failed check or the reason is under "Application checks".'];
    view.next = status === 'duplicate' ? ['Describe the category in other words, so that it gets another name.']
      : status === 'clarify' ? ['The proposal was too broad or not consistent. Name a narrower subject, or split the request.', 'Or use another method.']
      : ['Send the request again, or write it with other words.', 'Or use another method.'];
  } else if (kind === 'model_report') {
    const own = replyTexts(outcome);
    view.replyReason = own[0] || (status === 'clarify' ? null : outcome.reason) || null;
    // The reason of the server stands under "Application checks" only when it is not the text of the reply.
    view.showReason = typeof outcome.reason === 'string' && outcome.reason.trim() !== '' && outcome.reason !== view.replyReason && !own.includes(outcome.reason);
    view.second = ['The application accepted this result because the reply selects nothing. It did not check the reason.'];
    if (status === 'no_match') {
      view.heading = `${reply} reports no match`;
      view.first = [method === 'vocabulary' ? `${reply} states that no existing category or tag matches the request.` : `${reply} states that nothing in the item data matches the request.`];
      view.next = ['Check the evidence scope: only the listed items and their data were used.', 'Write the request with other words.',
        ...(words.authored ? [] : [method === 'vocabulary' ? 'Or match the request to item descriptions with the third method.' : 'Or match the request to existing categories and tags with the second method.'])];
    } else if (status === 'unsupported') {
      view.heading = `${reply} reports that the controls cannot express this request`;
      view.first = [`${reply} states that the request needs an operation that the controls do not have.`];
      view.next = ['The controls can show more, show less or remove a set of items. They cannot count items, use a time or a condition, or make an exception.', 'Write a request that asks for more, less or none of one subject.'];
    } else {
      view.heading = 'The request has more than one possible meaning';
      view.first = [`${reply} reports that the request is not clear enough to act on.`];
      view.next = ['Write the request again and name one clear subject and one direction (more, less or none).',
        ...(outcome.clarification?.alternatives?.length && !words.authored ? ['Or add one of the listed meanings to your request.'] : [])];
    }
  } else if (kind === 'request_failed') {
    view.heading = 'The request failed';
    view.first = ['No usable reply reached this page.', 'The message of the server is under "Application checks".'];
    view.next = ['Read the message. It comes from the application or from the provider route.', 'If it names a connection, a key or a model, correct that setting and start the server again.', 'Then send the request again.'];
  } else {
    // An answer without a named source. Say only what the page knows.
    view.heading = status === 'clarify' ? 'The request needs clarification' : status === 'no_match' ? 'Nothing matches the request'
      : status === 'unsupported' ? 'The controls cannot express this request' : status === 'cancelled' ? 'The review was cancelled'
      : status === 'duplicate' ? 'The proposed name already exists' : 'The request stopped';
    view.first = ['No proposal reached the review.', 'The reason is under "Application checks".'];
    view.replyReason = outcome?.clarification?.model_reason || null;
    view.next = status === 'cancelled' ? ['Start again with a new request.'] : ['Read the reason.', 'Write the request again, or use another method.'];
  }
  return view;
}

// The six stages of one control, from the real state of the panel.
// phase: idle | working | stopped | interpretation | preview | expired | applied | undone | cleared
// `stage` names the stage of a call that runs, stopped or waits for review.
export function stageStates({method = 'manual_category', phase = 'idle', stage = null, historyAction = 'none', needsInput = false, canUndo = false} = {}) {
  const manual = method === 'manual_category';
  const index = name => STAGES.indexOf(name);
  // The manual method has no interpretation by a model: its first working stage is the evidence stage.
  const working = name => manual && name === 'Interpretation' ? 'Evidence' : name || (manual ? 'Evidence' : 'Interpretation');
  let now = 0;
  const note = {};
  if (phase === 'working') now = index(working(stage));
  else if (phase === 'stopped') { now = index(working(stage)); note[STAGES[now]] = 'stopped; nothing applied'; }
  else if (phase === 'interpretation') { now = index('Interpretation'); note.Interpretation = needsInput ? 'needs your input' : 'review it'; }
  else if (phase === 'expired') { now = index(stage || (historyAction === 'undo' ? 'Undo' : 'Preview')); note[STAGES[now]] = 'expired; nothing applied'; }
  else if (phase === 'preview') {
    now = historyAction === 'undo' ? index('Undo') : index('Preview');
    note[STAGES[now]] = historyAction === 'undo' ? 'review it' : historyAction === 'clear' ? 'review the removal' : 'your decision';
  } else if (phase === 'applied') now = index('Undo');
  if (phase === 'undone') note.Request = 'the last change is undone';
  if (phase === 'cleared') note.Request = 'every control is removed';
  return STAGES.map((name, position) => {
    if (manual && name === 'Interpretation') return {name, state: 'skipped', text: 'not used: no model'};
    let state = phase === 'applied' ? (position < index('Undo') ? 'done' : 'now') : position < now ? 'done' : position === now ? 'now' : 'todo';
    let words = state === 'done' ? 'done' : state === 'now' ? 'now' : 'not yet';
    if (name === 'Undo' && !note.Undo) {
      // The undo stage follows the server: it is available while an earlier state exists.
      if (phase === 'undone') { state = 'done'; words = 'done'; }
      else if (canUndo || phase === 'applied') words = state === 'now' ? 'now: available' : 'available';
    } else if (note[name]) words = `${words}: ${note[name]}`;
    return {name, state, text: words};
  });
}

function shortHash(value) {
  return typeof value === 'string' && value.length >= 12 ? value.slice(0, 12) : null;
}

// The provider line of a review. The names come from the server settings; nothing verifies which model answered.
export function providerWords(model, words = sourceWords(false)) {
  if (!model) return null;
  if (model.backend === 'manual_category') return 'Provider: none. This control uses no model.';
  const name = model.model ?? model.model_id, hash = shortHash(model.digest ?? model.model_revision);
  if (words.authored) return `Replies: written by hand for the bundled examples (${model.backend}). No model answered.${hash ? ` Hash of the reply table: ${hash}.` : ''}`;
  return `Provider and model, as the server settings name them: ${model.backend} / ${name}.${hash ? ` Settings hash ${hash} (it identifies the settings, not the model).` : ''} The application did not verify which model answered.`;
}

// Checks that this page can repeat from the reviewed record itself. The server
// made its own checks before it returned the review; these lines restate the
// ones that the response lets the page recompute. They say nothing about meaning.
// context.outside: items of the first ten that are not in the evidence scope.
export function localChecks(group, pending, context = {}) {
  const proposal = group.proposal, route = routeOf(group), scope = group.scope_ids || [], members = proposal.item_ids || [];
  const checks = [
    {check: 'Every selected item is in the evidence scope', passed: members.every(id => scope.includes(id)), detail: `${members.length} selected of ${scope.length} in the scope`},
    {check: 'No item is selected twice', passed: new Set(members).size === members.length, detail: null},
  ];
  if (route === 'description') {
    const evidence = proposal.evidence || [];
    checks.push({check: 'Every selected item has its own quotation', detail: `${plural(evidence.length, 'quotation')} for ${plural(members.length, 'item')}`,
      passed: evidence.length === members.length && evidence.every(row => members.includes(row.item_id))});
    const rows = (pending?.evidence_context || []).filter(row => evidence.some(e => e.item_id === row.item_id && e.field === row.field && e.quote === row.quote));
    if (rows.length) checks.push({check: 'Every quotation is present in the text of its own item',
      passed: rows.length === evidence.length && rows.every(row => row.quote_present === true), detail: `${rows.filter(row => row.quote_present === true).length} of ${evidence.length}`});
    if (typeof group.request === 'string' && typeof proposal.action?.intent_span === 'string')
      checks.push({check: 'The quoted part of your request is copied exactly from your request', passed: group.request.includes(proposal.action.intent_span), detail: `"${proposal.action.intent_span}"`});
    checks.push({check: 'The selection covers at most half of the evidence scope', passed: members.length <= scope.length / 2, detail: `${members.length} of ${scope.length}`});
  } else if (route === 'manual') {
    const categories = context.categories || {};
    const known = scope.filter(id => Array.isArray(categories[id]));
    if (known.length === scope.length) checks.push({check: `The selected items are exactly the items of the category ${proposal.action.intent_span} in the scope`,
      passed: scope.every(id => members.includes(id) === categories[id].includes(proposal.action.intent_span)), detail: `${members.length} of ${scope.length}`});
  } else if (route === 'staged' || route === 'induction') {
    const envelope = proposal.induction?.envelope || {}, audit = envelope.evidence_audit;
    checks.push({check: 'Every item in the scope has one classification', passed: (envelope.field_evidence || []).length === scope.length, detail: `${(envelope.field_evidence || []).length} of ${scope.length}`});
    if (audit) {
      const assessed = audit.assessment?.assessments || [], withheld = audit.withheld || [];
      checks.push({check: 'Every item in the scope has one separate evidence assessment', passed: assessed.length === scope.length, detail: `${assessed.length} of ${scope.length}`});
      const disagreed = withheld.filter(row => !row.missing_literal_terms?.length).map(row => row.item_id);
      const missing = withheld.filter(row => row.missing_literal_terms?.length).map(row => row.item_id);
      checks.push({check: 'An item on which the two calls disagree gets no decision and is not selected', passed: disagreed.every(id => !members.includes(id)), detail: disagreed.length ? `${disagreed.length === 1 ? 'item' : 'items'} ${disagreed.join(', ')}` : 'no disagreement'});
      checks.push({check: 'An item whose text lacks a number of the definition gets no decision and is not selected', passed: missing.every(id => !members.includes(id)), detail: missing.length ? `${missing.length === 1 ? 'item' : 'items'} ${missing.join(', ')}` : 'none'});
    }
  }
  const provenance = proposal.provenance || {};
  const sealed = [['source', provenance.source_sha256], ['request', provenance.request_sha256], ['action', provenance.action_sha256]]
    .filter(([, value]) => shortHash(value)).map(([name, value]) => `${name} ${shortHash(value)}`);
  if (sealed.length) checks.push({check: 'The record is bound to the source data, the request and the action by their hashes', passed: true, detail: sealed.join(' · ')});
  return checks;
}

// Items of a manual category that the control cannot reach, because they are outside the evidence scope.
export function outsideScope(group, context = {}) {
  if (routeOf(group) !== 'manual') return [];
  const categories = context.categories || {}, scope = group.scope_ids || [];
  return (context.outside || []).filter(id => !scope.includes(id) && Array.isArray(categories[id]) && categories[id].includes(group.proposal.action.intent_span));
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

// The lines under a card of the language feed: one for each applied control that names the item.
export function controlLines(groups, itemId) {
  return (groups || []).filter(group => group.proposal.item_ids.includes(itemId)).map(group => `Applied control: ${group.label} (${actionWords(group.proposal.action)}).`);
}
