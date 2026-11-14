import React from 'react';

// Display only. One row per supplied item, so the whole reviewed scope can be
// read at once: what the item says, what was proposed for it and on which words.
// The detailed record stays in the panel; approval still happens there.
const WEIGHT = {light: 0.10, standard: 0.25, strong: 0.40};
export default function ReviewTable({pending, current}) {
  const groups = pending.groups, action = pending.history_action || 'none';
  const text = Object.fromEntries((pending.scope_items || []).map(r => [r.item_id, r.source_text]));
  // Net effect per item across every group in the plan. Exclusion wins.
  const net = {};
  for (const g of groups) for (const id of g.proposal.item_ids) {
    const a = g.proposal.action, entry = net[id] || (net[id] = {excluded: false, delta: 0});
    if (a.operation === 'exclude') entry.excluded = true;
    else entry.delta += (a.operation === 'boost' ? 1 : -1) * (WEIGHT[a.strength] || 0);
  }
  const result = id => !net[id] ? 'Unchanged' : net[id].excluded ? 'Removed from the feed'
    : net[id].delta > 0 ? 'Ranked higher' : net[id].delta < 0 ? 'Ranked lower' : 'Unchanged';
  const rows = [];
  for (const g of groups) {
    const proposal = g.proposal, envelope = proposal.induction?.envelope, audit = envelope?.evidence_audit;
    const primary = Object.fromEntries((audit?.primary_envelope?.field_evidence || envelope?.field_evidence || []).map(r => [r.item_id, r]));
    const final = Object.fromEntries((envelope?.field_evidence || []).map(r => [r.item_id, r]));
    const assessed = Object.fromEntries((audit?.assessment?.assessments || []).map(r => [r.item_id, r]));
    const quoted = Object.fromEntries((proposal.evidence || []).map(r => [r.item_id, r]));
    for (const id of g.scope_ids) {
      const member = proposal.item_ids.includes(id);
      rows.push({key: `${g.label}-${id}`, id, group: g.label, member,
        first: primary[id] ? `${primary[id].verdict}${primary[id].evidence_quote ? ` · “${primary[id].evidence_quote}”` : ''}` : member ? `selected${quoted[id]?.quote ? ` · “${quoted[id].quote}”` : ''}` : 'not selected',
        second: assessed[id] ? `${assessed[id].assessment}${assessed[id].quote ? ` · “${assessed[id].quote}”` : ''}` : null,
        reason: final[id]?.reason || null});
    }
  }
  const staged = rows.some(r => r.second !== null), several = groups.length > 1;
  const title = action === 'undo' ? 'Undo: restore the state before the last approved change'
    : action === 'clear' ? 'Remove every reviewed group'
    : groups.map(g => `${g.label}: ${g.proposal.action.operation}`).join(' + ');
  return <section className="review-table" aria-label="Review of every supplied item">
    <p className="eyebrow review-flag">PREVIEW · NOTHING IS APPLIED YET</p>
    <h3>{title}</h3>
    <p className="help">Eligible items now: <b>{current?.feed.available_items ?? '–'}</b>. After approval: <b>{pending.feed.available_items}</b>. The feed below stays as it is until you approve in the panel.</p>
    {rows.length > 0 && <div className="comparison-scroll"><table><thead><tr><th>Item</th>{several && <th>Group</th>}<th>Supplied description</th><th>{staged ? 'Classification under the definition' : 'Proposal'}</th>{staged && <th>Separate evidence assessment</th>}<th>{several ? 'Net result if approved' : 'Result if approved'}</th></tr></thead>
      <tbody>{rows.map(r => <tr key={r.key} data-item={r.id} className={r.member ? 'review-member' : ''}><th>{r.id}</th>{several && <td>{r.group}</td>}<td>{text[r.id] ?? 'No description supplied'}</td><td>{r.first}</td>{staged && <td>{r.second}</td>}
        <td><b>{result(r.id)}</b>{r.reason && !r.member ? <span className="review-reason"> {r.reason}</span> : null}</td></tr>)}</tbody></table></div>}
    {several && <p className="help">An item in several groups shows one net result. Exclusion takes priority over a rank change.</p>}
    <p className="help">A quotation shows that the words exist in the description. It does not show that the decision is right. Read each row before you approve.</p>
  </section>;
}
