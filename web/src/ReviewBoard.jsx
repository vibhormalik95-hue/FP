import React from 'react';
import ReviewTable, {BeforeAfter} from './ReviewTable.jsx';
import {actionWords, fieldWords, localChecks, outcomeView, outsideScope, planConflicts, plural, providerWords, routeOf, sourceWords, splitGroups, termWords} from './reviewModel.js';

// The review board shows every result of a request in three separate blocks:
// what came back (a model reply, an authored reply, or your own selection), what
// the application checked, and what the person decides. Text of a reply is shown
// only in the first block. The board has no state of its own. The panel owns the
// state and the handlers.

// The complete text of the field that holds each cited quotation. Display only:
// match the complete citation, never borrow another item's field.
export function definitionEvidence(evidence, context) {
  return evidence.map((e,n)=>{
    const row=context?.find(r=>r.item_id===e.item_id&&r.field===e.field&&r.quote===e.quote);
    const available=typeof row?.supplied_field_text==='string';
    return <div className="help" key={n} role="group" aria-label="Definition cited source context">
      <p>Item {e.item_id}, {fieldWords(e.field)}: the complete text that holds the quotation "{e.quote}". The application checked the words, not the meaning.</p>
      {available?<p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{row.supplied_field_text}</p>:
        <p>Full source field unavailable for this citation.</p>}
      {row?.truncated&&<p>[truncated]</p>}
      {available&&!row.quote_present&&<p>[quote not found in current text]</p>}
    </div>;
  });
}

function block(kind, title, children, extra) {
  return <section className={`block ${extra || ''}`} data-block={kind} aria-label={title} id={kind === 'decision' ? 'review-decision' : undefined} tabIndex={kind === 'decision' ? -1 : undefined}><h4>{title}</h4>{children}</section>;
}

function heading(text) {
  // The panel moves focus here after each result, so that the result is in view and announced.
  return <h3 id="review-heading" tabIndex={-1}>{text}</h3>;
}

// passed: true, false, or null when this page cannot confirm the check from the data that it has.
function checkList(checks) {
  return <ul className="checks">{checks.map((c, n) => <li key={n} data-check={c.check} data-passed={c.passed === true ? 'true' : c.passed === false ? 'false' : 'unknown'}>
    <b>{c.passed === true ? 'Passed' : c.passed === false ? 'Failed' : 'Not confirmed on this page'}:</b> {c.check}{c.detail ? <span className="review-reason"> ({c.detail})</span> : null}</li>)}</ul>;
}

// For a cited definition: is each quotation present in the complete field of its own item?
function citationChecks(evidence, context) {
  const rows = (evidence || []).map(e => (context || []).find(r => r.item_id === e.item_id && r.field === e.field && r.quote === e.quote));
  const found = rows.filter(row => typeof row?.supplied_field_text === 'string' && row.quote_present === true).length;
  const absent = rows.some(row => typeof row?.supplied_field_text === 'string' && row.quote_present !== true);
  // A citation without its field on this page is not a failure of the server check; the page just cannot repeat it.
  return checkList([{check: 'Every cited quotation is present in the complete text of its own item',
    passed: absent ? false : rows.length > 0 && found === rows.length ? true : null, detail: `${found} of ${rows.length}`}]);
}

function rawReplies(calls, words) {
  // A reply that is not JSON comes back as bounded text (`raw_text`); it is shown as text, never as markup.
  const replies = (calls || []).filter(call => call && (call.raw_response !== undefined || call.raw_output !== undefined || typeof call.raw_text === 'string'));
  if (!replies.length) return null;
  return <details className="raw"><summary>{replies.length === 1 ? words.raw : `${words.rawMany} (${replies.length})`}</summary>
    {replies.map((call, n) => <pre key={n}>{call.raw_response !== undefined || call.raw_output !== undefined ? JSON.stringify(call.raw_response !== undefined ? call.raw_response : call.raw_output, null, 2) : call.raw_text}</pre>)}</details>;
}

function providerLine(model, words) {
  const text = providerWords(model, words);
  return text ? <p className="help" data-role="provider-line">{text}</p> : null;
}

function contextRows(rows, names) {
  if (!rows?.length) return null;
  const lines = rows.map(e=><p className="help" key={`${e.item_id}-${e.field}-${e.quote}`}>Item {e.item_id}, {fieldWords(e.field)}: “{e.supplied_field_text??'unavailable'}”{e.truncated?' [truncated]':''}{e.quote_present?'':' [quote not found in current text]'}</p>);
  // A chosen category or tag name is the whole evidence, and the table shows it for every item: keep this list folded.
  if (names) return <details className="raw" aria-label="Full cited source context"><summary>The complete field of each selected item that carries a chosen name ({rows.length})</summary>{lines}</details>;
  return <div role="group" aria-label="Full cited source context">
    <p className="help">The complete text that holds each quotation. The application checked the words, not the meaning. Look for a negation or a contrary sentence before you approve:</p>
    {lines}
  </div>;
}

// The reason that the reply gives for the whole request, when the answer holds one.
function replyReason(pending) {
  for (const value of [pending.reply_reason, pending.reason]) if (typeof value === 'string' && value.trim()) return value;
  const raw = (pending.model_calls || []).map(call => call?.raw_response).find(value => value && typeof value.reason === 'string' && value.reason.trim());
  return raw ? raw.reason : null;
}

// What came back for one new control. The words differ by method; the facts come from the sealed record.
function replyOutput(group, pending, words) {
  const proposal = group.proposal, route = routeOf(group), action = proposal.action;
  if (route === 'vocabulary') {
    const control = (pending.vocabulary?.controls || []).find(candidate => candidate.label === group.label);
    const terms = control?.terms || proposal.vocabulary_terms || [];
    return <div key={group.revision} className="control-output" data-route="vocabulary">
      <p><b>{group.label}</b></p>
      <p className="help">Direction and strength, {words.read}: <b>{actionWords(action)}</b>.</p>
      <p className="help">Part of your request that names the subject: “{action.intent_span}”.</p>
      <p className="help">{words.controlReason} {control?.relation ?? proposal.reason}</p>
      <p className="help">{words.names} {terms.map(termWords).join('; ') || 'none'}.</p>
    </div>;
  }
  if (route === 'staged' || route === 'induction') {
    const induction = proposal.induction, audit = induction.envelope?.evidence_audit;
    return <div key={group.revision} className="control-output" data-route={route}>
      <p>{words.name} <b>{group.label}</b></p>
      <p className="help">The name becomes the name of the control. It cannot be changed on this page.</p>
      <p className="help">Definition that you reviewed: {induction.validated_category.definition}</p>
      <p className="help">{words.reason} {proposal.reason}</p>
      {audit&&<p className="help">Separate evidence assessment: {words.authored ? words.second : `${audit.assessment.model.model_id}, settings hash ${String(audit.assessment.model.model_revision).slice(0, 12)}`}. It did not see the classifications. {words.authored ? 'Both replies are written by hand.' : 'It can be the same model. Agreement of the two calls is not independent proof.'}</p>}
      <p className="help">Direction and strength: <b>{actionWords(action)}</b>, chosen by you.</p>
      {rawReplies([...(induction.definition_model_calls||[]),...(induction.model_calls||[]),...(induction.evidence_audit_model_calls||[])], words)}
    </div>;
  }
  const chosen = ['manual','user_confirmed_target'].includes(proposal.action_source);
  return <div key={group.revision} className="control-output" data-route="description">
    <p><b>{group.label}</b></p>
    <p className="help">Direction and strength: <b>{actionWords(action)}</b>, {chosen?'chosen by you':words.read}.</p>
    {!chosen&&<p className="help">Part of your request that names the subject: “{action.intent_span}”.</p>}
    <p className="help">{words.controlReason} {proposal.reason}</p>
    <p className="help">{words.quotations} {(proposal.evidence||[]).map(e=>`item ${e.item_id}, ${fieldWords(e.field)}: “${e.quote}”`).join('; ')||'none'}.</p>
  </div>;
}

// The request of the person, shown above the three blocks. It is the person's own text, not a reply.
function requestLines(added) {
  const lines = [];
  for (const group of added) {
    const route = routeOf(group), confirmation = group.proposal.target_confirmation;
    if (route === 'manual') continue;
    const text = confirmation?.original_request || group.request;
    const line = route === 'staged' || route === 'induction' ? `Your description: “${text}”` : `Your request: “${text}”`;
    if (!lines.includes(line)) lines.push(line);
    if (confirmation) lines.push(`Target that you stated and confirmed: “${group.request}” You gave this meaning and the action yourself. The page makes no claim about automatic recognition of intent.`);
  }
  return lines.map((line, n) => <p className="your-request" key={n}>{line}</p>);
}

// The checks of one control. `shared` is true when the checks of the whole reply and the provider line are shown once above.
function applicationChecks(group, pending, context, shared, words) {
  const route = routeOf(group), proposal = group.proposal;
  const control = route === 'vocabulary' ? (pending.vocabulary?.controls || []).find(candidate => candidate.label === group.label) : null;
  const envelope = proposal.induction?.envelope, audit = envelope?.evidence_audit;
  // The server states which items of the control are outside the scope; without that field the page computes it for a manual control.
  const effect = (pending.scope_effects || []).find(entry => entry.label === group.label);
  const outside = Array.isArray(effect?.outside_scope_item_ids) ? effect.outside_scope_item_ids : outsideScope(group, context);
  const noDecision = proposal.induction?.validated_category?.unknown_ids || [];
  return <div key={group.revision} className="control-checks" data-route={route}>
    <p><b>{group.label}</b></p>
    {!(shared.checks && route === 'vocabulary') && <>
      {!shared.server && <p className="help">This page repeated these checks from the reviewed record:</p>}
      {checkList(localChecks(group, pending, context))}</>}
    {control&&<p className="help">Items that each chosen name selects: {control.terms.map(term=>`${termWords(term)}: ${(term.item_ids||[]).join(', ')||'none'}`).join('; ')}.</p>}
    {effect?.message&&<p className="help" data-role="scope-effect">{effect.message}</p>}
    {outside.length>0&&<p className="help" data-role="outside-scope">{plural(outside.length,'item')} with {route==='manual'?'this category':'a chosen name'} {outside.length===1?'is':'are'} outside the evidence scope and {outside.length===1?'does':'do'} not change: {outside.join(', ')}.</p>}
    {audit&&<p className="help">Numbers that an item must contain: {audit.literal_constraints.terms.join(', ')||'none'}. {words.authored?'The second reply':'The second call'} can only remove an item from the selection. It never adds one.</p>}
    {envelope&&<p className="help">Selected items that have an existing category: {envelope.overlaps.map(o=>`${o.member_ids.join(', ')} (${String(o.category_id).replace(/^original:/,'')})`).join('; ')||'none'}.</p>}
    {envelope&&<p className="help">Items without a decision (not selected): {noDecision.join(', ')||'none'}. The name was compared only with the categories in the scope.</p>}
    {envelope?.normalizations?.map(e=><p className="help" key={e.item_id}>Item {e.item_id}: the reply named the field "{e.original_field}" without a quotation for an item without a decision. The application left that field out. The item stays without a decision. The raw reply is kept.</p>)}
    <p className="help">Selected items: {proposal.item_ids.join(', ')||'none'}. Evidence scope: {group.scope_ids.join(', ')}.</p>
    {!shared.provider && providerLine(proposal.provenance?.model, words)}
  </div>;
}

function planNotes(pending) {
  const notes = Array.isArray(pending.plan_notes) ? pending.plan_notes : planConflicts(pending.groups);
  if (!notes.length) return null;
  return <div className="plan-notes" role="group" aria-label="Notes about the whole plan">
    <p><b>Notes about the whole plan</b></p>
    <ul>{notes.map((note, n) => <li key={n} data-kind={note.kind || 'note'}><b>Note:</b> {note.message}{Array.isArray(note.item_ids) && note.item_ids.length > 0 && !String(note.message).includes(String(note.item_ids[0])) ? ` (${note.item_ids.length === 1 ? 'item' : 'items'} ${note.item_ids.join(', ')})` : ''}</li>)}</ul>
    <p className="help">A note is not a failed check. Read it before you approve.</p>
  </div>;
}

function decisionSummary(pending, current) {
  const action = pending.history_action || 'none', {added, kept, removed} = splitGroups(pending.groups, current?.groups);
  if (action === 'undo') return <p>If you approve, the application restores the controls that were active before the last approved change. Controls after the undo: <b>{pending.groups.map(g=>g.label).join(', ')||'none'}</b>.</p>;
  if (action === 'clear') return <p>If you approve, the application removes every applied control.</p>;
  return <>
    <p>If you approve:</p>
    <ul>{added.map(g=><li key={g.revision}><b>{g.label}</b>: {actionWords(g.proposal.action)} for {g.proposal.item_ids.length===1?'item':'items'} {g.proposal.item_ids.join(', ')}.</li>)}
      {removed.map(g=><li key={g.revision}>The applied control <b>{g.label}</b> ends.</li>)}
      {kept.length>0&&<li>Controls that stay applied: {kept.map(g=>g.label).join(', ')}.</li>}</ul>
    {added.length>1&&<p className="help">One approval applies all {added.length} new controls together.</p>}
    <p className="help">Only items in the evidence scope change. Other items with the same category, tag or subject stay as they are.</p>
  </>;
}

function expiredDecision(controls, what) {
  return <>
    <p><b>This review is older than five minutes.</b> The server no longer accepts it. Nothing was applied.</p>
    <p className="help">{what}</p>
    <button className="secondary" disabled={controls.disabled} onClick={controls.discard}>Close this expired review</button>
  </>;
}

function reviewVariant({pending, current, context, controls, words, expired, deadlineText, dataNote}) {
  const action = pending.history_action || 'none', {added} = splitGroups(pending.groups, current?.groups);
  const routes = added.map(routeOf);
  const selection = action !== 'none' || added.length === 0 || routes.every(route => route === 'manual');
  const title = action === 'undo' ? 'Undo: restore the state before the last approved change'
    : action === 'clear' ? 'Remove every applied control'
    : added.length === 1 ? `Proposed change: ${added[0].label}` : added.length > 1 ? `Proposed change: ${added.length} controls` : 'Proposed change: no new control';
  const calls = added.some(group => ['staged', 'induction'].includes(routeOf(group))) ? [] : pending.model_calls || [];
  // One reply of the category and tag route can hold several controls: its checks and its provider are shown once.
  const replyChecks = added.some(group => routeOf(group) === 'vocabulary') ? pending.vocabulary?.checks || [] : Array.isArray(pending.checks) ? pending.checks : [];
  const models = added.map(group => JSON.stringify(group.proposal.provenance?.model ?? null));
  const shared = {checks: replyChecks.length > 0 && added.some(group => routeOf(group) === 'vocabulary'), server: replyChecks.length > 0,
    provider: added.length > 1 && models.every(value => value === models[0])};
  const reason = selection ? null : replyReason(pending);
  const approve = action === 'undo' ? 'Approve the undo' : action === 'clear' ? 'Approve: remove every control' : 'Approve this exact item set and apply';
  return <>
    <p className="eyebrow review-flag">{expired ? 'EXPIRED · NOTHING WAS APPLIED' : `PREVIEW · NOTHING IS APPLIED YET${selection ? '' : words.flag}`}</p>
    {heading(title)}
    <p className="help"><a href="#review-decision" onClick={event => { event.preventDefault(); const target = typeof document !== 'undefined' && document.getElementById('review-decision'); if (target) { target.scrollIntoView({block: 'start'}); target.focus({preventScroll: true}); } }}>Go to your decision</a></p>
    {action === 'none' && requestLines(added)}
    <div className="blocks">
      {selection ? block('reply', 'Your selection', action === 'undo' ? <p className="help">You asked to undo the last approved change. No model is used for this step.</p>
        : action === 'clear' ? <p className="help">You asked to remove every applied control. No model is used for this step.</p>
        : added.length === 0 ? <p className="help">This plan adds no new control.</p>
        : added.map(group => <div key={group.revision} className="control-output" data-route="manual">
          <p><b>{group.label}</b></p><p className="help">You chose the existing category <b>{group.proposal.action.intent_span}</b> and the action <b>{actionWords(group.proposal.action)}</b>. No model is used.</p></div>))
        : block('reply', words.block, <>
          {reason && <p className="help" data-role="reply-reason">{words.reason} {reason}</p>}
          {added.map(group => replyOutput(group, pending, words))}
          {rawReplies(calls, words)}
          <p className="help">{words.caution}</p></>)}
      {block('checks', 'Application checks', action === 'undo' ? <p className="help">The application checks that the earlier controls still match the current source data before it restores them.</p>
        : action === 'clear' ? <p className="help">Every control is removed. No check is necessary.</p> : <>
        {replyChecks.length > 0 && <div className="control-checks"><p><b>Checks of the {words.authored ? 'authored reply' : selection ? 'request' : 'reply'}</b></p>{checkList(replyChecks)}</div>}
        {added.map(group => applicationChecks(group, pending, context, shared, words))}
        {planNotes(pending)}
        {shared.provider && providerLine(added[0].proposal.provenance?.model, words)}
        {contextRows(pending.evidence_context, added.length > 0 && added.every(group => routeOf(group) === 'vocabulary'))}
        <p className="help">These checks are mechanical. A passed check shows that names, IDs and quotations exist in the item data. It does not show that the meaning is right.</p></>)}
      {block('decision', 'Your decision', expired ? expiredDecision(controls, `To get a new review, press the button of the request again.${selection ? '' : words.authored ? ' The server reads the authored reply again.' : ' A model method calls the model again.'}`) : <>
        {decisionSummary(pending, current)}
        {(Array.isArray(pending.plan_notes) ? pending.plan_notes : planConflicts(pending.groups)).length > 0 && <p className="help" data-role="notes-pointer">Read the notes about the whole plan under "Application checks" before you approve.</p>}
        <p><b>Nothing has changed yet.</b> The feed below stays as it is until you approve.</p>
        <p className="help" data-role="deadline">{deadlineText ? `Approve before ${deadlineText}.` : 'Approve within five minutes.'} After that time the server no longer accepts this review.</p>
        {controls.blocked && <p className="help" role="status">{controls.blocked}</p>}
        <button className="primary" disabled={controls.disabled || Boolean(controls.blocked)} onClick={controls.apply}>{approve}</button>
        <button className="secondary" disabled={controls.disabled} onClick={controls.discard}>Discard this review and apply nothing</button>
      </>, 'decision')}
    </div>
    {action === 'none' && pending.groups.length > 0 && <ReviewTable pending={pending} current={current} context={context} words={words}/>}
    <BeforeAfter current={current} pending={pending}/>
    {action === 'none' && <p className="help">Only the items in the scope were assessed. A quotation does not prove that an item fits.</p>}
    {dataNote && <p className="help data-note">{dataNote}</p>}
  </>;
}

function resolutionVariant({resolution, clarification, controls, words, expired, deadlineText}) {
  const candidate = clarification.candidate;
  return <section aria-label="Unresolved semantic interpretations">
    <p className="eyebrow review-flag">{expired ? 'EXPIRED · NOTHING WAS APPROVED OR APPLIED' : `INTERPRETATION · NOTHING IS APPROVED OR APPLIED${words.flag}`}</p>
    {heading('Choose between the meanings of the category')}
    <p className="your-request">Your description: “{resolution.objective}”</p>
    <div className="blocks">
      {block('reply', words.block, <>
        <p className="help">{words.The} proposed this definition and named other possible meanings. Nothing is approved.</p>
        <div role="group" aria-label="Unapproved primary category">
          <p>{words.name} <strong>{candidate.label}</strong></p>
          <p>{candidate.definition}</p>
          <p className="help">{words.reason} {candidate.rationale}</p>
          {clarification.model_reason && clarification.model_reason !== candidate.rationale && <p className="help">{words.reason} {clarification.model_reason}</p>}
          <p className="help">{words.quotations} {candidate.evidence.map(e=>`item ${e.item_id}, ${fieldWords(e.field)}: “${e.quote}”. ${e.reason}`).join(' ')||'none'}</p>
        </div>
        {clarification.alternatives.length>0&&<><p className="help">Other meanings that {words.the} named:</p>
          <ul>{clarification.alternatives.map((a,n)=><li key={n}>{a}</li>)}</ul></>}
        {rawReplies(resolution.model_calls, words)}
        <p className="help">{words.caution}</p>
      </>)}
      {block('checks', 'Application checks', <>
        {citationChecks(candidate.evidence, resolution?.evidence_context)}
        {definitionEvidence(candidate.evidence,resolution?.evidence_context)}
        <p className="help">The application did not accept this definition as it is, because the reply names other meanings.</p>
        <p className="help">The other meanings are text only. The application cannot classify items with them.</p>
        {providerLine({backend: resolution.provenance.backend, model_id: resolution.provenance.model_id, model_revision: resolution.provenance.model_revision}, words)}
        <p className="help">Evidence scope: {resolution.scope_ids.join(', ')}.</p>
      </>)}
      {block('decision', 'Your decision', expired ? expiredDecision(controls, 'To get a new proposal, press "Propose a definition for review" again.') : <>
        <p className="help">You can continue with this exact definition, or cancel and change your description in the panel. A change of the description calls nothing. Only "Propose a definition for review" starts a new call.</p>
        <p className="help">Your choice makes no call and approves neither evidence nor membership. {deadlineText ? `Choose before ${deadlineText}.` : 'Choose within five minutes.'}</p>
        <label><input type="checkbox" name="category-resolution" disabled={controls.disabled} checked={controls.resolutionChoice==='review_primary'} onChange={()=>controls.setResolutionChoice(controls.resolutionChoice==='review_primary'?'':'review_primary')}/> I choose this exact, unchanged definition for review.</label>
        <button className="primary" disabled={controls.disabled||controls.resolutionChoice!=='review_primary'} onClick={()=>controls.resolveDefinition('review_primary')}>Continue to definition review</button>
        <button className="secondary" disabled={controls.disabled} onClick={()=>controls.resolveDefinition('cancel')}>Cancel category clarification</button>
      </>, 'decision')}
    </div>
  </section>;
}

function definitionVariant({definition, controls, words, expired, deadlineText}) {
  const d = definition.definition;
  return <div role="group" aria-label="Category definition review">
    <p className="eyebrow review-flag">{expired ? 'EXPIRED · NOTHING WAS CLASSIFIED OR APPLIED' : `INTERPRETATION · NOTHING IS CLASSIFIED OR APPLIED YET${words.flag}`}</p>
    {heading('Review the proposed definition')}
    <p className="your-request">Your description: “{d.objective}”</p>
    <div className="blocks">
      {block('reply', words.block, <>
        <p>{words.name} <strong>{d.proposal.label}</strong></p>
        <p>{d.proposal.definition}</p>
        <p className="help">{words.reason} {d.proposal.rationale}</p>
        <p className="help">{words.quotations} {d.proposal.evidence.map(e=>`item ${e.item_id}, ${fieldWords(e.field)}: “${e.quote}”. ${e.reason}`).join(' ')||'none'}</p>
        {rawReplies(definition.model_calls, words)}
        <p className="help">{words.caution}</p>
      </>)}
      {block('checks', 'Application checks', <>
        {citationChecks(d.proposal.evidence, definition.evidence_context)}
        {definitionEvidence(d.proposal.evidence,definition.evidence_context)}
        {d.operator_resolution&&<div role="group" aria-label="Explicit category resolution record">
          <p className="help">You chose this unchanged definition yourself. The original model result remains clarification, not an approval. You must still review the evidence.</p>
          <p className="help">Other meanings in the first reply: {d.original_clarification.clarification.alternatives.join('; ')}</p>
        </div>}
        {d.source_constraints&&<p className="help">Numbers that an item must contain: {d.source_constraints.terms.join(', ')||'none'}. If the definition holds a number, an item is selected only if its own text holds the same number. An item that gives the number in other words is not selected.</p>}
        {providerLine({backend: d.provenance.backend, model_id: d.provenance.model_id, model_revision: d.provenance.model_revision}, words)}
        <p className="help">Evidence scope: {definition.scope_ids.join(', ')}. No membership and no feed change is approved yet.</p>
        <p className="help">A quotation that exists is not proof that the definition is right.</p>
      </>)}
      {block('decision', 'Your decision', expired ? expiredDecision(controls, 'To get a new definition, press "Propose a definition for review" again.') : <>
        <p className="help">Do not approve a definition that claims something that the descriptions do not state, even if the quotation exists.</p>
        <p className="help">To get another definition, reject this one and change your description in the panel. {deadlineText ? `Decide before ${deadlineText}.` : 'Decide within five minutes.'}</p>
        <label><input type="checkbox" checked={controls.evidenceReviewed} disabled={controls.disabled} onChange={e=>controls.setEvidenceReviewed(e.target.checked)}/> I checked that the quotations support the complete definition.</label>
        <button className="primary" disabled={controls.disabled||!controls.evidenceReviewed} onClick={controls.classify}>Approve the definition and classify the items of the scope</button>
        <button className="secondary" disabled={controls.disabled} onClick={controls.rejectDefinition}>Reject this definition</button>
      </>, 'decision')}
    </div>
  </div>;
}

function outcomeVariant({outcome, controls, words, request}) {
  const clarification = outcome.clarification;
  const selection = outcome.method === 'manual_category';
  const view = outcomeView(outcome, words);
  const calls = [...(outcome.model_calls || []), ...(outcome.evidence_audit_model_calls || [])];
  const checks = outcome.vocabulary?.checks || outcome.checks || [];
  // Text of a reply belongs to the first block. The application's own sentences belong to the second block.
  const replyText = view.kind === 'model_report';
  const attempted = typeof outcome.calls_attempted === 'number' ? outcome.calls_attempted : null;
  return <div role="group" aria-label="Result without a proposed change" data-status={outcome.status} data-kind={view.kind}>
    <p className="eyebrow review-flag">NO CHANGE PROPOSED · NOTHING WAS APPLIED{selection || !['model_report', 'reply_rejected', 'provider_failure'].includes(view.kind) ? '' : words.flag}</p>
    {heading(view.heading)}
    {outcome.request_text ? <p className="your-request">{selection ? `Your selection: ${outcome.request_text}` : `Your request: “${outcome.request_text}”`}</p> : null}
    <div className="blocks">
      {block('reply', selection ? 'Your selection' : words.block, <>
        {selection && <p className="help">No model is used for this method.</p>}
        {view.first.map((line, n) => <p className="help" key={n}>{line}</p>)}
        {replyText && view.replyReason && <p className="help" data-role="reply-reason">{words.reason} {view.replyReason}</p>}
        {replyText && clarification?.alternatives?.length > 0 && <><p className="help">Meanings that {words.the} named. None was selected or applied:</p>
          <ul aria-label="Alternatives named in the reply">{clarification.alternatives.map((a, n) => <li key={n}>{a}
            {controls.adoptAlternative && <button type="button" className="text-button" disabled={controls.disabled} onClick={() => controls.adoptAlternative(a)}>{controls.alternativeLabel}</button>}</li>)}</ul></>}
        {replyText && clarification && clarification.negation_resolved === false && <p className="help">{words.The} did not resolve a negation in the request.</p>}
        {rawReplies(calls, words)}
        {(replyText || view.kind === 'reply_rejected') && <p className="help">{words.caution}</p>}</>)}
      {block('checks', 'Application checks', <>
        {view.second.map((line, n) => <p className="help" key={n}>{line}</p>)}
        {view.showReason && <p role="status" data-role="reason"><b>{view.kind === 'application_check' ? 'Stopped' : view.kind === 'reply_rejected' ? 'Rejected' : ['provider_failure', 'request_failed', 'session', 'network', 'expired'].includes(view.kind) ? 'Message of the server' : 'Result'}:</b> {outcome.reason || 'No reason was given.'}</p>}
        {checks.length > 0 && checkList(checks)}
        {attempted !== null && !selection && <p className="help" data-role="calls-attempted">{words.authored ? `Authored replies looked up for this request: ${attempted}.` : attempted === 0 ? 'No model call was started.' : `${plural(attempted, 'model call')} started for this request.`}</p>}
        {outcome.model_provenance && !selection && providerLine(outcome.model_provenance, words)}
      </>)}
      {block('decision', 'Your decision', <>
        <p><b>Nothing was applied.</b> {['session', 'network'].includes(view.kind) ? 'The page cannot confirm the state of the server.' : 'The feed and the applied controls are unchanged.'}</p>
        {outcome.lost && <p className="help">{outcome.lost}</p>}
        <p>What you can do next:</p>
        <ul>{view.next.map((line, n) => <li key={n}>{line}</li>)}</ul>
      </>, 'decision')}
    </div>
  </div>;
}

function changedVariant({record, recordFresh, controls}) {
  const time = record.time instanceof Date ? record.time.toLocaleTimeString() : String(record.time);
  const diff = record.diff;
  const body = <>
    {record.kind === 'apply' && <p>The approved change is applied. {record.added.length ? <>New {record.added.length === 1 ? 'control' : 'controls'}: {record.added.map((g, n) => <span key={n}><b>{g.label}</b> ({g.action}; {g.item_ids.length === 1 ? 'item' : 'items'} {g.item_ids.join(', ')}){n < record.added.length - 1 ? '; ' : '.'}</span>)}</> : 'No new control was added.'}
      {record.removed.length > 0 && <> Ended: {record.removed.map(g => g.label).join(', ')}.</>}</p>}
    {record.kind === 'undo' && <p>The last approved change is undone. The earlier feed is restored. Controls now applied: <b>{record.active.join(', ') || 'none'}</b>.</p>}
    {record.kind === 'clear' && <p>Every applied control is removed.</p>}
    <p className="help">Eligible items: {record.eligible_before ?? 'unknown'} before, {record.eligible_after ?? 'unknown'} after.
      {diff.unchanged ? ' The first ten items and their order are the same as before.' : <>
        {diff.leaves.length > 0 && <> Left the first ten: {diff.leaves.join(', ')}.</>}
        {diff.enters.length > 0 && <> Entered the first ten: {diff.enters.join(', ')}.</>}
        {diff.moved.length > 0 && <> Changed position: {diff.moved.map(move => `${move.id} (${move.from} to ${move.to})`).join(', ')}.</>}</>}</p>
    {record.kind === 'apply' || record.kind === 'clear'
      ? <><p className="help"><b>To undo:</b> press "Undo this change (review first)", then approve the undo review. The same button is in the panel.</p>
        {recordFresh && controls?.undo && <button type="button" className="secondary" disabled={controls.disabled || !controls.canUndo} onClick={controls.undo}>Undo this change (review first)</button>}</>
      : <p className="help">To make another change, write a new request in the panel.</p>}
  </>;
  const flag = `${record.kind === 'apply' ? 'APPLIED' : record.kind === 'undo' ? 'UNDONE' : 'CLEARED'} · ${time}`;
  // After a new request starts, the record is an earlier change: keep it, folded, under a title that says so.
  if (!recordFresh) return <details className="earlier-record" aria-label="Last applied change" data-kind={record.kind}>
    <summary>Last applied change ({time}): {record.kind === 'apply' ? 'a change was applied' : record.kind === 'undo' ? 'a change was undone' : 'every control was removed'}</summary>{body}</details>;
  return <div role="group" aria-label="What changed" data-kind={record.kind}>
    <p className="eyebrow">{flag}</p>
    {heading('What changed')}
    {body}
  </div>;
}

export default function ReviewBoard(props) {
  const {variant, failure} = props;
  if (!variant && !failure) return null;
  const words = props.words || sourceWords(false), all = {...props, words};
  return <section id="review-board" className="review-board" aria-label="Review board" data-variant={variant || 'failure'} data-expired={props.expired ? 'true' : undefined}>
    {failure && variant && <p className="alert error" role="alert">{failure.message}</p>}
    {variant === 'resolution' ? resolutionVariant(all)
      : variant === 'definition' ? definitionVariant(all)
      : variant === 'review' ? reviewVariant(all)
      : variant === 'outcome' ? outcomeVariant(all)
      : variant === 'changed' ? changedVariant(all)
      : outcomeVariant({...all, outcome: {status: 'error', reason: failure.message, method: props.method, thrown: true, page: failure.kind || undefined, request_text: failure.request_text, lost: failure.lost}})}
  </section>;
}
