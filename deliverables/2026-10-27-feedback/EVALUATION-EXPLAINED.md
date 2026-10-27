# TCP, TCER and the offline-validity question

Prepared 27 October 2026. This explains **existing** metrics and a new demonstration arithmetic check; it is not a rerun of a frozen scientific test. Source of code definitions: `feedctrl/evaluation.py:51-72` and `docs/evaluation-protocol.md:77-98` at FP `bec8442dd7fbd43535ded943f886add2cb50cd8d`. The original May proposal mentions a target-category-proportion measure related to Lu et al. and proposes held-out watch behavior as ground truth. It does not specify TCER by name. The project uses TCER for the same target exposure fraction on mute requests; the project documents do not establish a longer formal expansion of those letters.

## What is calculated

For a request targeting one category, take the first `K=10` **distinct** ranked items. Let `t` be how many carry that category. Each item counts once even if it has several labels. Then:

- **TCP@10 on a boost request** is `t/10`; larger target-category proportion favors the specified boost.
- **TCER@10 on a mute request** is also `t/10`; lower unwanted target exposure favors the specified mute.
- **Fill** is `number of returned items/10`. Conditional exposure is `t/number returned` when the list is nonempty. A zero-item list has TCER zero but is not a useful success; `compliant_filled_success` requires all ten items.
- **HR@1** asks if the first item equals the one held-out next-item target. **NDCG@10** gives `1/log2(rank+1)` if that same item is in the top ten, else zero. They are historical next-item agreement proxies, not satisfaction.

## Worked numbers and exact code trace

The 27 October user-14 rule-mode demonstration receipt begins with a neutral top ten containing **six** `category_28` items. For a hypothetical explicit request to mute `category_28`, the target is established from the supplied command before parsing. The same saved-model scorer and candidate catalog are kept. The neutral exposure is `6/10 = 0.60`. Current `controls.rerank` excludes every candidate bearing the muted category; the reproduced C list remains ten items and contains zero category_28 items, so `TCER@10 = 0/10 = 0`, `fill = 10/10 = 1`, and filled compliance is one **for that one demo request**. This checks the arithmetic and implementation. It does not show that an actual user wanted the mute.

For a category_1 boost in the same demonstration, neutral exposure is `0/10`; rule-controlled C exposure is `9/10 = 0.90`, with full fill. The result demonstrates category-wide policy impact, not a unique LLM contribution. E1's cohort means, 11.615% to 79.222% TCP and 6.112% to zero TCER, come from a separate frozen run across users and seeds. Do not replace those means with this one-user example.

## Answer to the professor's concern

**TCP can be computed offline; intended benefit cannot be inferred from TCP alone.** A static dataset supplies item-category labels, rankings and logged next-item targets, so the fraction is reproducible. The current E1 request target was synthetically assigned from **earlier** training/request history (`evaluation.generate_requests:23-48`), not extracted as a genuine preference from held-out future behavior. That avoids test-label leakage in request construction but means the request is not known human intent. Hard mute mechanically drives exposure to zero, and a category-wide boost has greater reach than one-item feedback. User-level paired statistics quantify this finite offline comparison; they do not cure the construct-validity gap.

The proposal's wording says the request is derived from held-out behavior and also treats that behavior as the outcome. That risks using the test answer to define the desired control. The implemented protocol instead uses earlier history. This is a material proposal departure, documented in the recovered archive's `docs/proposal-amendment.md`; it should be acknowledged to the professor, not silently called the same design. A manual reference would establish the intended operation and category independently of the evaluated parser. Even a perfect manual reference would establish interpretation and control compliance, not human satisfaction.

## Proposed comparison, only after protocol agreement

If the professor wants LLM-specific added value beyond existing evidence, write and lock a **new** prospective protocol before viewing held-out outcomes. Audit the completed AI-reference and student-label records first. The new design would use independent human-intent labels for natural requests, the same user, candidate catalog, base scores and ranking policy for each method, and explicit cells for (1) neutral history-only, (2) simulated item feedback A, (3) manually encoded intended control as a reference upper bound, (4) rules, and (5) LLM interpretation. Compare whole-command agreement **separately** from downstream exposure, filled compliance, HR@1/NDCG and failure rate. Specify K, denominators, cases, unsupported intent handling, aggregation and statistical tests before running. Never tune on the held-out bank. A rule parser is not a human reference and matching two LLMs is not independent human validation.

This comparison is proposed, not executed or automatically required by the original 135-hour plan. Current code only supports explicit `category_N` and hard mute in the live app; richer topic names, graded decrease and category-agnostic requests are potential extensions, not established commitments. The professor has not yet accepted an alternate TCP interpretation or protocol in the available transcript.
