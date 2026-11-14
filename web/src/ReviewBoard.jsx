import React from 'react';
import ReviewTable, {BeforeAfter} from './ReviewTable.jsx';
import {actionWords, localChecks, outcomeCopy, routeOf, splitGroups, termWords} from './reviewModel.js';

// The review board shows every result of a request in three separate blocks:
// what the model returned, what the application checked, and what the person
// decides. It has no state of its own. The panel owns the state and the handlers.

// Display only: match the complete citation, never borrow another item's field.
export function definitionEvidence(evidence, context) {
  return evidence.map((e,n)=>{
    const row=context?.find(r=>r.item_id===e.item_id&&r.field===e.field&&r.quote===e.quote);
    const available=typeof row?.supplied_field_text==='string';
    return <div className="help" key={n} aria-label="Definition cited source context">
      <p>Item {e.item_id}, {e.field}: "{e.quote}". {e.reason}</p>
      <p>Complete supplied field (quote custody, not semantic relevance):</p>
      {available?<p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{row.supplied_field_text}</p>:
        <p>Full source field unavailable for this citation.</p>}
      {row?.truncated&&<p>[truncated]</p>}
      {available&&!row.quote_present&&<p>[quote not found in current text]</p>}
    </div>;
  });
}

function block(title, children, extra) {
  return <section className={`block ${extra || ''}`} aria-label={title}><h4>{title}</h4>{children}</section>;
}

// passed: true, false, or null when this page cannot confirm the check from the data that it has.
function checkList(checks) {
  return <ul className="checks">{checks.map((c, n) => <li key={n} data-passed={c.passed === true ? 'true' : c.passed === false ? 'false' : 'unknown'}>
    <b>{c.passed === true ? 'Passed' : c.passed === false ? 'Failed' : 'Not confirmed on this page'}:</b> {c.check}{c.detail ? <span className="review-reason"> ({c.detail})</span> : null}</li>)}</ul>;
}

// For a cited definition: is each quotation present in the complete field of its own item?
function citationChecks(evidence, context) {
  const rows = (evidence || []).map(e => (context || []).find(r => r.item_id === e.item_id && r.field === e.field && r.quote === e.quote));
  const found = rows.filter(row => typeof row?.supplied_field_text === 'string' && row.quote_present === true).length;
  const absent = rows.some(row => typeof row?.supplied_field_text === 'string' && row.quote_present !== true);
  // A citation without its field on this page is not a failure of the server check; the page just cannot repeat it.
  return checkList([{check: 'Every cited quotation is present in the complete field of its own item',
    passed: absent ? false : rows.length > 0 && found === rows.length ? true : null, detail: `${found} of ${rows.length}`}]);
}

function rawReplies(calls) {
  const replies = (calls || []).filter(call => call && (call.raw_response !== undefined || call.raw_output !== undefined));
  if (!replies.length) return null;
  return <details className="raw"><summary>Raw model {replies.length === 1 ? 'reply' : `replies (${replies.length})`}</summary>
    {replies.map((call, n) => <pre key={n}>{JSON.stringify(call.raw_response !== undefined ? call.raw_response : call.raw_output, null, 2)}</pre>)}</details>;
}

function providerLine(model) {
  if (!model) return null;
  const name = model.model ?? model.model_id, digest = model.digest ?? model.model_revision;
  if (model.backend === 'manual_category') return <p className="help">Provider: none. This control uses no model.</p>;
  return <p className="help">Provider and model, as the route declares them: {model.backend} / {name}; digest {digest}. The application records this declaration. It cannot attest it.</p>;
}

function contextRows(rows, names) {
  if (!rows?.length) return null;
  const lines = rows.map(e=><p className="help" key={`${e.item_id}-${e.field}-${e.quote}`}>Item {e.item_id}, {e.field}: “{e.supplied_field_text??'unavailable'}”{e.truncated?' [truncated]':''}{e.quote_present?'':' [quote not found in current text]'}</p>);
  // A chosen category or tag name is the whole evidence, and the table shows it for every item: keep this list folded.
  if (names) return <details className="raw" aria-label="Full cited source context"><summary>The complete field of each selected item that carries a chosen name ({rows.length})</summary>{lines}</details>;
  return <div aria-label="Full cited source context">
    <p className="help">Full supplied text around each cited quotation (display only; check for negation or contrary meaning before you approve):</p>
    {lines}
  </div>;
}

// What the model returned for one new control. The words differ by method; the facts come from the sealed record.
function modelOutput(group, pending) {
  const proposal = group.proposal, route = routeOf(group), action = proposal.action;
  if (route === 'manual') return <div key={group.revision} className="control-output" data-route="manual">
    <p><b>{group.label}</b></p><p className="help">No model was used. You chose the existing category <b>{action.intent_span}</b> and the action <b>{actionWords(action)}</b>.</p></div>;
  if (route === 'vocabulary') {
    const control = (pending.vocabulary?.controls || []).find(candidate => candidate.label === group.label);
    const terms = control?.terms || proposal.vocabulary_terms || [];
    return <div key={group.revision} className="control-output" data-route="vocabulary">
      <p><b>{group.label}</b></p>
      <p className="help">Direction and strength, read from your request: <b>{actionWords(action)}</b>.</p>
      <p className="help">Part of your request that names the subject: “{action.intent_span}”.</p>
      <p className="help">Relation that the model states: {control?.relation ?? proposal.reason}</p>
      <p className="help">Existing names that the model chose: {terms.map(termWords).join('; ') || 'none'}.</p>
    </div>;
  }
  if (route === 'staged' || route === 'induction') {
    const induction = proposal.induction, audit = induction.envelope?.evidence_audit;
    return <div key={group.revision} className="control-output" data-route={route}>
      <p><b>{group.label}</b></p>
      <p className="help">Definition that you reviewed: {induction.validated_category.definition}</p>
      <p className="help">Model relationship: {proposal.reason}</p>
      <p className="help">Items that stay unknown: {induction.validated_category.unknown_ids.join(', ')||'None'}. Novelty is checked only against the supplied inventory.</p>
      {audit&&<p className="help">Separate evidence assessment: {audit.assessment.model.model_id}; digest {audit.assessment.model.model_revision}. It did not see the classifications. It can be the same model. Agreement of the two calls is not independent proof.</p>}
      <p className="help">Direction and strength: <b>{actionWords(action)}</b>, chosen by you.</p>
      {rawReplies([...(induction.definition_model_calls||[]),...(induction.model_calls||[]),...(induction.evidence_audit_model_calls||[])])}
    </div>;
  }
  const chosen = ['manual','user_confirmed_target'].includes(proposal.action_source);
  return <div key={group.revision} className="control-output" data-route="description">
    <p><b>{group.label}</b></p>
    <p className="help">Original request: {proposal.target_confirmation?.original_request||group.request}</p>
    {proposal.target_confirmation&&<p className="help">Target that you stated and confirmed: {group.request}. You supplied this interpretation and the action. The page makes no claim about automatic intent accuracy.</p>}
    <p className="help">Direction and strength: <b>{actionWords(action)}</b>, {chosen?'chosen by you':'read from your request by the model'}.</p>
    {!chosen&&<p className="help">Part of your request that names the subject: “{action.intent_span}”.</p>}
    <p className="help">Model relationship: {proposal.reason}</p>
    <p className="help">Quotations that the model cited: {(proposal.evidence||[]).map(e=>`item ${e.item_id}, ${e.field}: “${e.quote}”`).join('; ')||'none'}.</p>
  </div>;
}

// The checks of one control. `shared` is true when the checks of the whole reply and the provider line are shown once above.
function applicationChecks(group, pending, context, shared) {
  const route = routeOf(group), proposal = group.proposal;
  const control = route === 'vocabulary' ? (pending.vocabulary?.controls || []).find(candidate => candidate.label === group.label) : null;
  const envelope = proposal.induction?.envelope, audit = envelope?.evidence_audit;
  return <div key={group.revision} className="control-checks" data-route={route}>
    <p><b>{group.label}</b></p>
    {!(shared.checks && route === 'vocabulary') && checkList(localChecks(group, pending, context))}
    {control&&<p className="help">Items that each chosen name selects: {control.terms.map(term=>`${termWords(term)}: ${(term.item_ids||[]).join(', ')||'none'}`).join('; ')}.</p>}
    {audit&&<p className="help">Required literal terms: {audit.literal_constraints.terms.join(', ')||'none'}. A term that is present can still be negated, quoted or unrelated.</p>}
    {envelope&&<p className="help">Overlap with existing categories: {envelope.overlaps.map(o=>`${o.category_id}: ${o.member_ids.join(',')}`).join('; ')||'none in the supplied inventory'}.</p>}
    {envelope?.normalizations?.map(e=><p className="help" key={e.item_id}>Item {e.item_id}: an uncited field "{e.original_field}" of an unknown verdict was left out of the canonical evidence. The verdict stays unknown. The raw model output is retained.</p>)}
    <p className="help">Selected items: {proposal.item_ids.join(', ')||'none'}. Assessed scope: {group.scope_ids.join(', ')}.</p>
    {!shared.provider && providerLine(proposal.provenance?.model)}
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
  </>;
}

function reviewVariant({pending, current, context, controls}) {
  const action = pending.history_action || 'none', {added} = splitGroups(pending.groups, current?.groups);
  const title = action === 'undo' ? 'Undo: restore the state before the last approved change'
    : action === 'clear' ? 'Remove every applied control'
    : `Proposed change: ${(added.length ? added : pending.groups).map(g => `${g.label}: ${actionWords(g.proposal.action)}`).join(' + ')}`;
  const calls = added.some(group => ['staged', 'induction'].includes(routeOf(group))) ? [] : pending.model_calls || [];
  // One reply of the category and tag route can hold several controls: its checks and its provider are shown once.
  const replyChecks = added.some(group => routeOf(group) === 'vocabulary') ? pending.vocabulary?.checks || [] : [];
  const models = added.map(group => JSON.stringify(group.proposal.provenance?.model ?? null));
  const shared = {checks: replyChecks.length > 0, provider: added.length > 1 && models.every(value => value === models[0])};
  return <>
    <p className="eyebrow review-flag">PREVIEW · NOTHING IS APPLIED YET</p>
    <h3>{title}</h3>
    <div className="blocks">
      {block('Model output (not verified)', action !== 'none' ? <p className="help">No model is used for this step.</p> : <>
        {added.map(group => modelOutput(group, pending))}
        {added.length === 0 && <p className="help">This plan adds no new control.</p>}
        {rawReplies(calls)}
        <p className="help">The model can be wrong. This block repeats what it returned. Nothing here is approved.</p></>)}
      {block('Application checks', action !== 'none' ? <p className="help">The application checks that the earlier controls still match the current source data before it restores them.</p> : <>
        {shared.checks && <div className="control-checks"><p><b>Checks of the model reply</b></p>{checkList(replyChecks)}</div>}
        {added.map(group => applicationChecks(group, pending, context, shared))}
        {shared.provider && providerLine(added[0].proposal.provenance?.model)}
        {contextRows(pending.evidence_context, added.length > 0 && added.every(group => routeOf(group) === 'vocabulary'))}
        <p className="help">These checks are mechanical. A passed check shows that names, IDs and quotations exist in the supplied data. It does not show that the meaning is right.</p></>)}
      {block('Your decision', <>
        {decisionSummary(pending, current)}
        <p><b>Nothing has changed yet.</b> The feed below stays as it is until you approve. This review expires five minutes after it appears.</p>
        {controls.blocked && <p className="help" role="status">{controls.blocked}</p>}
        <button className="primary" disabled={controls.disabled || Boolean(controls.blocked)} onClick={controls.apply}>Approve this exact item set and apply</button>
        <button className="secondary" disabled={controls.disabled} onClick={controls.discard}>Discard this review and apply nothing</button>
      </>, 'decision')}
    </div>
    {pending.groups.length > 0 && <ReviewTable pending={pending} current={current} context={context}/>}
    <BeforeAfter current={current} pending={pending}/>
    <p className="help">{pending.note}</p>
  </>;
}

function resolutionVariant({resolution, clarification, controls}) {
  return <section aria-label="Unresolved semantic interpretations">
    <p className="eyebrow review-flag">INTERPRETATION · NOTHING IS APPROVED OR APPLIED</p>
    <h3>Resolve competing category meanings</h3>
    <div className="blocks">
      {block('Model output (not verified)', <>
        <p className="help">{clarification.notice}</p>
        <p className="help">Model explanation: {clarification.model_reason}</p>
        <div aria-label="Unapproved primary category">
          <strong>{clarification.candidate.label}</strong>
          <p>{clarification.candidate.definition}</p>
          <p className="help">Objective: {resolution.objective}</p>
          <p className="help">Model rationale: {clarification.candidate.rationale}</p>
          {definitionEvidence(clarification.candidate.evidence,resolution?.evidence_context)}
        </div>
        {clarification.alternatives.length>0&&<><p className="help">Competing interpretations:</p>
          <ul>{clarification.alternatives.map((a,n)=><li key={n}>{a}</li>)}</ul></>}
        {rawReplies(resolution.model_calls)}
      </>)}
      {block('Application checks', <>
        {citationChecks(clarification.candidate.evidence, resolution?.evidence_context)}
        <p className="help">The application did not accept this definition as it is, because the reply names competing meanings.</p>
        <p className="help">{resolution.provenance.backend} / {resolution.provenance.model_id}; digest {resolution.provenance.model_revision}. Assessed scope: {resolution.scope_ids.join(', ')}.</p>
        <p className="help">Alternatives are unvalidated text descriptions and cannot be classified directly.</p>
      </>)}
      {block('Your decision', <>
        <p className="help">{clarification.question} Editing it does not call a model; only a new explicit review submission does.</p>
        <p className="help">Choosing the primary meaning makes no model call and approves neither evidence nor membership. This choice expires after five minutes.</p>
        <label><input type="radio" name="category-resolution" disabled={controls.disabled} checked={controls.resolutionChoice==='review_primary'} onChange={()=>controls.setResolutionChoice('review_primary')}/> I resolve the competing meanings by choosing this exact, unchanged primary definition for review.</label>
        <button className="primary" disabled={controls.disabled||controls.resolutionChoice!=='review_primary'} onClick={()=>controls.resolveDefinition('review_primary')}>Continue to definition review</button>
        <button className="secondary" disabled={controls.disabled} onClick={()=>controls.resolveDefinition('cancel')}>Cancel category clarification</button>
      </>, 'decision')}
    </div>
  </section>;
}

function definitionVariant({definition, controls}) {
  const d = definition.definition;
  return <div aria-label="Category definition review">
    <p className="eyebrow review-flag">INTERPRETATION · NOTHING IS CLASSIFIED OR APPLIED YET</p>
    <h3>Stage 1: review the whole definition</h3>
    <div className="blocks">
      {block('Model output (not verified)', <>
        <strong>{d.proposal.label}</strong>
        <p>{d.proposal.definition}</p>
        <p className="help">Objective: {d.objective}</p>
        <p className="help">Model rationale: {d.proposal.rationale}</p>
        {definitionEvidence(d.proposal.evidence,definition.evidence_context)}
        {rawReplies(definition.model_calls)}
      </>)}
      {block('Application checks', <>
        {citationChecks(d.proposal.evidence, definition.evidence_context)}
        {d.operator_resolution&&<div aria-label="Explicit category resolution record">
          <p className="help">You explicitly chose the unchanged primary meaning. The original model result remains clarification, not automatic approval. Evidence review is still required.</p>
          <p className="help">Original competing meanings: {d.original_clarification.clarification.alternatives.join('; ')}</p>
        </div>}
        {d.source_constraints&&<p className="help">Literal witness requirements: {d.source_constraints.terms.join(', ')||'No digit-bearing terms'}. Every positive must contain these terms in supplied metadata. This conservative text constraint may withhold equivalent wording, unit conversions or ranges; presence does not establish truth.</p>}
        <p className="help">{d.provenance.backend} / {d.provenance.model_id}; digest {d.provenance.model_revision}. Assessed scope: {definition.scope_ids.join(', ')}. No membership or feed change is approved yet.</p>
        <p className="help">Each quotation is shown with the complete field that it comes from. A quotation that exists is not proof that the definition is right.</p>
      </>)}
      {block('Your decision', <>
        <p className="help">Reject a definition with unsupported properties, credentials or ratings, even if the quotation exists. Change the objective to start again. Approval expires after five minutes.</p>
        <label><input type="checkbox" checked={controls.evidenceReviewed} disabled={controls.disabled} onChange={e=>controls.setEvidenceReviewed(e.target.checked)}/> I reviewed whether the source evidence supports the entire definition.</label>
        <button className="primary" disabled={controls.disabled||!controls.evidenceReviewed} onClick={controls.classify}>Approve definition and classify supplied items</button>
      </>, 'decision')}
    </div>
  </div>;
}

function outcomeVariant({outcome, controls}) {
  const clarification = outcome.clarification;
  const calls = [...(outcome.model_calls || []), ...(outcome.evidence_audit_model_calls || [])];
  const checks = outcome.vocabulary?.checks || outcome.checks || [];
  const noCall = outcome.method !== 'manual_category' && !outcome.thrown && Array.isArray(outcome.model_calls) && calls.length === 0;
  const copy = outcomeCopy(outcome.status, outcome.method, {alternatives: Boolean(clarification?.alternatives?.length), guard: noCall});
  return <div aria-label="Result without a proposed change" data-status={outcome.status}>
    <p className="eyebrow review-flag">NO CHANGE PROPOSED · NOTHING WAS APPLIED</p>
    <h3>{copy.heading}</h3>
    <div className="blocks">
      {block('Model output (not verified)', outcome.method === 'manual_category' ? <p className="help">No model is used for this method.</p>
        : outcome.thrown ? <p className="help">No usable model reply reached the review. See the message under "Application checks".</p>
        : noCall ? <p className="help">No model was called. The application stopped the request with its own check.</p> : <>
        {clarification?.model_reason && <p className="help">Model explanation: {clarification.model_reason}</p>}
        {clarification?.alternatives?.length > 0 && <><p className="help">Interpretations that the model named. None was selected or applied:</p>
          <ul aria-label="Alternatives named by the model">{clarification.alternatives.map((a, n) => <li key={n}>{a}
            {controls.adoptAlternative && <button type="button" className="text-button" disabled={controls.disabled} onClick={() => controls.adoptAlternative(a)}>{controls.alternativeLabel}</button>}</li>)}</ul></>}
        {clarification && clarification.negation_resolved === false && <p className="help">The model did not resolve a negation in the request.</p>}
        {!clarification && <p className="help">The reply proposed no change. The reason is under "Application checks".</p>}
        {rawReplies(calls)}
        <p className="help">The model can be wrong. Nothing here is approved.</p></>)}
      {block('Application checks', <>
        {outcome.request_text ? <p className="help">Request that gave this result: “{outcome.request_text}”</p> : null}
        <p role="status"><b>{outcome.status}:</b> {outcome.reason || 'No reason was given.'}</p>
        {checks.length > 0 && checkList(checks)}
        {clarification?.notice && <p className="help">{clarification.notice}</p>}
        {outcome.model_provenance && providerLine(outcome.model_provenance)}
      </>)}
      {block('Your decision', <>
        <p><b>Nothing was applied.</b> The feed and the applied controls are unchanged.</p>
        {clarification?.question && <p className="help">{clarification.question}</p>}
        <p>What you can do next:</p>
        <ul>{copy.next.map((line, n) => <li key={n}>{line}</li>)}</ul>
      </>, 'decision')}
    </div>
  </div>;
}

function changedVariant({record}) {
  const time = record.time instanceof Date ? record.time.toLocaleTimeString() : String(record.time);
  const diff = record.diff;
  return <div aria-label="What changed" data-kind={record.kind}>
    <p className="eyebrow">{record.kind === 'apply' ? 'APPLIED' : record.kind === 'undo' ? 'UNDONE' : 'CLEARED'} · {time}</p>
    <h3>What changed</h3>
    {record.kind === 'apply' && <p>The approved change is applied. {record.added.length ? <>New {record.added.length === 1 ? 'control' : 'controls'}: {record.added.map((g, n) => <span key={n}><b>{g.label}</b> ({g.action}; {g.item_ids.length === 1 ? 'item' : 'items'} {g.item_ids.join(', ')}){n < record.added.length - 1 ? '; ' : '.'}</span>)}</> : 'No new control was added.'}
      {record.removed.length > 0 && <> Ended: {record.removed.map(g => g.label).join(', ')}.</>}</p>}
    {record.kind === 'undo' && <p>The last approved change is undone. The earlier feed is restored. Controls now applied: <b>{record.active.join(', ') || 'none'}</b>.</p>}
    {record.kind === 'clear' && <p>Every applied control is removed.</p>}
    <p className="help">Eligible items: {record.eligible_before ?? 'unknown'} before, {record.eligible_after ?? 'unknown'} after.
      {diff.unchanged ? ' The first ten items are the same as before.' : <>
        {diff.leaves.length > 0 && <> Left the first ten: {diff.leaves.join(', ')}.</>}
        {diff.enters.length > 0 && <> Entered the first ten: {diff.enters.join(', ')}.</>}
        {diff.moved.length > 0 && <> Changed position: {diff.moved.map(move => `${move.id} (${move.from} to ${move.to})`).join(', ')}.</>}</>}</p>
    {record.kind === 'apply'
      ? <p className="help"><b>To undo:</b> press "Undo the last change (review first)" in the panel, then approve the undo review.</p>
      : <p className="help">To make another change, write a new request in the panel.</p>}
  </div>;
}

export default function ReviewBoard(props) {
  const {variant, failure} = props;
  if (!variant && !failure) return null;
  return <section className="review-board" aria-label="Review board" data-variant={variant || 'failure'}>
    {failure && variant && <p className="alert error" role="alert">{failure}</p>}
    {variant === 'resolution' ? resolutionVariant(props)
      : variant === 'definition' ? definitionVariant(props)
      : variant === 'review' ? reviewVariant(props)
      : variant === 'outcome' ? outcomeVariant(props)
      : variant === 'changed' ? changedVariant(props)
      : outcomeVariant({outcome: {status: 'error', reason: failure, method: props.method, thrown: true}, controls: props.controls})}
  </section>;
}
