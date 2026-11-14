import React from 'react';
import {actionWords, feedDiff, planRows} from './reviewModel.js';

// Display only. One table for each control in the plan, one row for each item in
// the evidence scope: what the item says, its categories and tags, why the
// control selects it or does not select it, and the result if the plan is
// approved. Approval happens in the decision block of the review board, never here.

function labelsCell(labels) {
  if (labels === null) return <span className="review-reason">not available</span>;
  if (labels.length === 0) return <span>no category and no tag</span>;
  const categories = labels.filter(label => label.kind !== 'tag').sort((a, b) => (a.level || 1) - (b.level || 1)).map(label => label.value);
  const tags = labels.filter(label => label.kind === 'tag').map(label => label.value);
  return <>{categories.length > 0 && <span className="label-categories">{categories.join(' > ')}</span>}
    {tags.length > 0 && <span className="label-tags">tags: {tags.join(', ')}</span>}</>;
}

function reasoned(text, reason) {
  return <>{text}{reason ? <span className="review-reason"> {reason}</span> : null}</>;
}

function controlTable(group, several, callWord) {
  const staged = group.rows.some(row => row.first !== null), audited = group.rows.some(row => row.second !== null);
  return <div className="comparison-scroll" key={group.key} tabIndex={0} role="region" aria-label={`Evidence table of the control ${group.label}. It can scroll sideways.`}>
    <table>
      {several && <caption>Control: {group.label} · {actionWords(group.action)} · {group.isNew ? 'new in this review' : 'already applied'}</caption>}
      <thead><tr><th scope="col">Item</th><th scope="col">Description in the item data</th><th scope="col">Its categories and tags</th>
        {staged ? <><th scope="col">{audited ? `Classification under the definition (${callWord} 2)` : 'Classification under the definition'}</th>
          {audited && <th scope="col">Separate evidence assessment ({callWord} 3)</th>}<th scope="col">Decision of the application</th></>
          : <th scope="col">Selected or not, and through what</th>}
        <th scope="col">{several ? 'Net result if approved' : 'Result if approved'}</th></tr></thead>
      <tbody data-group={group.label} data-route={group.route} data-new={group.isNew ? 'true' : 'false'}>
        {group.rows.map(row => <tr key={row.key} data-item={row.id} data-member={row.member ? 'true' : 'false'} data-verdict={row.verdict || undefined}
          data-assessment={row.assessment || undefined} className={row.member ? 'review-member' : ''}>
          <th scope="row">{row.id}{row.member && <span className="review-mark"> selected</span>}</th>
          <td data-cell="description">{row.description ?? 'No description in the item data'}</td>
          <td data-cell="labels">{labelsCell(row.labels)}</td>
          {staged ? <><td data-cell="evidence">{reasoned(row.first, row.firstReason)}</td>
            {audited && <td data-cell="assessment">{reasoned(row.second, row.secondReason)}</td>}<td data-cell="decision">{row.final}</td></>
            : <td data-cell="evidence">{row.evidence}</td>}
          <td data-cell="result"><b>{row.result}</b></td></tr>)}
      </tbody>
    </table>
  </div>;
}

export default function ReviewTable({pending, current, context, words}) {
  const groups = planRows(pending, current, context);
  const fresh = groups.filter(group => group.isNew), applied = groups.filter(group => !group.isNew);
  const several = groups.length > 1, callWord = words?.authored ? 'reply' : 'call';
  return <section className="review-table" aria-label="Review of every supplied item">
    <h4>Evidence for every item in the scope</h4>
    <p className="help">Each row is one item of the evidence scope. A marked row is selected. An unmarked row is not selected, and the row says why.</p>
    <p className="help narrow-only">The table is wider than the screen. Move it sideways to see the reason and the result.</p>
    {fresh.map(group => controlTable(group, several, callWord))}
    {applied.length > 0 && <details className="applied-tables"><summary>Controls that are already applied ({applied.length}): the same table for each one</summary>
      {applied.map(group => controlTable(group, true, callWord))}</details>}
    {several && <p className="help">An item in several controls shows one net result. Removal takes priority over a rank change.</p>}
    <p className="help">A quotation or a category name shows that the words exist in the item data. It does not show that the decision is right. Read each row before you approve.</p>
  </section>;
}

// The first ten items now and after approval. Text notes mark each change, so
// that the difference does not depend on colour.
export function BeforeAfter({current, pending}) {
  const diff = feedDiff(current?.feed?.items, pending?.feed?.items);
  const list = (title, entries, label) => <div className="feed-list" aria-label={label}>
    <h5>{title}</h5>
    <ol>{entries.map(entry => <li key={entry.id} data-item={entry.id} className={entry.note ? 'changed' : ''}>Item {entry.id}{entry.note && <span className="feed-note"> ({entry.note})</span>}</li>)}</ol>
    {entries.length === 0 && <p className="help">No eligible item.</p>}
  </div>;
  return <section className="before-after" aria-label="Preview of the feed before and after">
    <h4>Preview: the first ten items now and after approval</h4>
    <div className="feed-lists">{list('Now (applied feed)', diff.before, 'First ten items now')}{list('After approval', diff.after, 'First ten items after approval')}</div>
    <p className="help">{diff.unchanged ? 'The first ten items and their order stay the same.' : <>
      {diff.leaves.length > 0 && <>Leaves the list: {diff.leaves.join(', ')}. </>}
      {diff.enters.length > 0 && <>Enters the list: {diff.enters.join(', ')}. </>}
      {diff.moved.length > 0 && <>Changes position: {diff.moved.map(move => `${move.id} (${move.from} to ${move.to})`).join(', ')}. </>}</>}
      {' '}Eligible items now: <b>{current?.feed?.available_items ?? 'unknown'}</b>. After approval: <b>{pending?.feed?.available_items ?? 'unknown'}</b>.</p>
    <p className="help"><b>The applied feed is unchanged until you approve.</b> The item cards below still show the applied feed.</p>
  </section>;
}
