import React from 'react';
import {actionWords, feedDiff, planRows} from './reviewModel.js';

// Display only. One row per item in the evidence scope, for each control in the
// plan: what the item says, its categories and tags, why the control selects it
// or does not select it, and the result if the plan is approved. Approval happens
// in the decision block of the review board, never here.

function labelsCell(labels) {
  if (labels === null) return <span className="review-reason">not available</span>;
  if (labels.length === 0) return <span>no category and no tag</span>;
  const categories = labels.filter(label => label.kind !== 'tag').sort((a, b) => (a.level || 1) - (b.level || 1)).map(label => label.value);
  const tags = labels.filter(label => label.kind === 'tag').map(label => label.value);
  return <>{categories.length > 0 && <span className="label-categories">{categories.join(' > ')}</span>}
    {tags.length > 0 && <span className="label-tags">tags: {tags.join(', ')}</span>}</>;
}

export default function ReviewTable({pending, current, context}) {
  const groups = planRows(pending, current, context);
  const staged = groups.some(group => group.rows.some(row => row.second !== null));
  const several = groups.length > 1;
  const columns = staged ? 6 : 5;
  return <section className="review-table" aria-label="Review of every supplied item">
    <h4>Evidence for every item in the scope</h4>
    <p className="help">Each row is one item that the model or the application assessed. A marked row is selected. An unmarked row is not selected, and the row says why.</p>
    {groups.length > 0 && <div className="comparison-scroll"><table>
      <thead><tr><th>Item</th><th>Supplied description</th><th>Its categories and tags</th>
        <th>{staged ? 'Classification under the definition' : 'Selected or not, and through what'}</th>
        {staged && <th>Separate evidence assessment</th>}<th>{several ? 'Net result if approved' : 'Result if approved'}</th></tr></thead>
      {groups.map(group => <tbody key={group.key} data-group={group.label} data-route={group.route} data-new={group.isNew ? 'true' : 'false'}>
        {several && <tr className="review-group"><th colSpan={columns} scope="rowgroup">Control: {group.label} · {actionWords(group.action)} · {group.isNew ? 'new in this review' : 'already applied'}</th></tr>}
        {group.rows.map(row => <tr key={row.key} data-item={row.id} data-member={row.member ? 'true' : 'false'} data-verdict={row.verdict || undefined}
          data-assessment={row.assessment || undefined} className={row.member ? 'review-member' : ''}>
          <th scope="row">{row.id}{row.member && <span className="review-mark"> selected</span>}</th>
          <td>{row.description ?? 'No description supplied'}</td>
          <td>{labelsCell(row.labels)}</td>
          <td>{row.evidence}{staged && row.reason ? <span className="review-reason"> {row.reason}</span> : null}</td>
          {staged && <td>{row.second}</td>}
          <td><b>{row.result}</b></td></tr>)}
      </tbody>)}
    </table></div>}
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
    <p className="help">{diff.unchanged ? 'The first ten items stay the same.' : <>
      {diff.leaves.length > 0 && <>Leaves the list: {diff.leaves.join(', ')}. </>}
      {diff.enters.length > 0 && <>Enters the list: {diff.enters.join(', ')}. </>}
      {diff.moved.length > 0 && <>Changes position: {diff.moved.map(move => `${move.id} (${move.from} to ${move.to})`).join(', ')}. </>}</>}
      {' '}Eligible items now: <b>{current?.feed?.available_items ?? 'unknown'}</b>. After approval: <b>{pending?.feed?.available_items ?? 'unknown'}</b>.</p>
    <p className="help"><b>The applied feed is unchanged until you approve.</b> The item cards below still show the applied feed.</p>
  </section>;
}
