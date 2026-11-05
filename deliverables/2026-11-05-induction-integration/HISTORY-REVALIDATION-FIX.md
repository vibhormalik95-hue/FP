# Current category inventory on history restore

Independent review found a real defect in local revisions `fa64e45` and
`9f46c20`: apply an induced group, clear it, preview undo, change an original
category mapping, then approve undo. The API restored the group because history
plans lacked the new-induction-only inventory context and ordinary ranking
revalidation trusted the recorded creation inventory.

## Reproduction and correction

Two new synthetic-fixture API regressions reproduced HTTP 200 instead of the
required HTTP 409, both for drift before history preview and for drift after
preview but before approval. These were executed before changing implementation;
both failed on `9f46c20`. No catalogue file, model output or frozen study changed.

`revalidate_category` now reconstructs the **current original/source inventory
projected onto each induced group's recorded evidence scope** on every ranking
use. It compares that inventory with the sealed creation inventory before checking
the complete category envelope. `feed` supplies the live original mappings to
`rank_groups`; direct callers with induced groups must also provide current
original mappings or validation fails closed.

This covers ordinary saved-feed reads, new proposals containing earlier induced
groups, history preview and final apply, rather than relying only on an optional
pending-plan field. Current metadata and eligible-item checks remain in place.
Changes outside the recorded candidate pool are outside this scoped inventory
comparison; this does not create a global taxonomy-freshness claim.

Saved user groups in the creation inventory remain sealed historical comparison
context. They are not reintroduced as live source taxonomy, which would make an
induced group invalidate itself immediately after being saved. New proposals
still compare against current saved groups, and their pending induction context
is still checked again on approval.

History preview now validates the prospective restored feed before replacing a
pending review or invalidating an in-flight request. If the restore is stale,
HTTP 409 leaves the entire per-user state unchanged, including its pending plan,
profile, revision and undo history. Successful clear/undo retains the existing
review-token and nonce behavior. Clearing stale groups remains possible.

## Verification

- The reported stale-undo sequence rejects both drift timings with HTTP 409.
- Rejected preview preserves a separate valid pending clear plan.
- Rejected approval preserves the complete user state and undo entry.
- Ordinary saved-feed reads reject current mapping drift without a state write.
- Direct induced ranking without current mappings fails closed.
- Clear followed by undo with unchanged mappings restores the exact prior groups
  and feed, avoiding accidental self-dependency.
- The shared explicit-membership ranking comparison now supplies current mappings.

The affected API/review suites passed **48 tests in 1.68 seconds**. The full suite
passed **460 tests, 1 skipped, in 30.89 seconds**; the private parser bank remains
absent and skipped. Log and JUnit hashes are recorded in `development-summary.json`.
All new induction outputs in these regressions are synthetic response doubles;
no additional live-model call or semantic accuracy claim is involved. The four
earlier Qwen abstentions and all frozen evidence remain unchanged.

Earlier immutable review ZIPs remain historical artifacts containing the reported
defect. Independent review subsequently verified the correction in `7bc5241`.

## Stale UI recovery

If the semantic-group read fails because its inventory is stale, the UI now shows
**Unavailable** and keeps **Review clearing semantic groups** enabled. Clearing
still requires the existing preview and explicit approval; undo and all other
stale-group validations remain unchanged. A known empty profile disables clear.

The final rendered check used a separate, explicitly synthetic fixture server:
the group read returned 409, the clear button remained enabled, review showed an
empty semantic profile, approval succeeded, and stale undo still returned 409.
No real catalogue or existing demo session was mutated. The affected API/review
checks passed **49 tests in 1.71 seconds**, including recovery with nonempty
original instruction/profile/feedback and literal-topic controls preserved.
The frontend production build passed (30 modules, 650 ms). No new inference ran.
The last complete Python suite remains the **460 passed / 1 skipped** checkpoint
at `7bc5241`; it was not repeated for this UI-only production change.
