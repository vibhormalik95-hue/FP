# Evaluation protocol: offline control compliance

Execution protocol version 1.0 was recorded on 28 September 2026 UTC before the research runs. This documentation revision, dated 29 September 2026 UTC, clarifies post-audit interpretation and adds explicitly post-hoc sensitivity reporting; it is not a newly prespecified protocol. Original data, prompts, configurations, checkpoints and outputs remain frozen. The original release preserves the earlier document.

The supplied proposal copy is unsigned, with both research paths and the office approval field unmarked. The revised scope therefore awaits approval evidence and supervisor review. This is an offline,
single-intent feasibility benchmark, with all 865 eligible users, 20 training epochs,
and training seeds 42, 43 and 44. This main-run scope was frozen before examining
test outcomes, after a 256-user/3-epoch setup training completed quickly enough to
support the full cohort. That setup was not used to select settings from test metrics.
Alternative cohorts or seeds must be identified as separate runs.
The raw public data and global chronological split are described in the dataset
manifest. Synthetic requests are experimental assignments, not inferred human intent.

## Leakage and candidate policy

Train the recommender only on interactions before the global training cutoff.
Construct the request history from the subsequent window. Final test events occur
after a second global cutoff. Model scoring uses each user's training and request
history, with a frozen model for all five conditions in a seed. The first test
positive event is the single next-item target for HR@1 and NDCG@K. Neither that item
nor any other test event enters request selection, parser inputs, score inputs,
hyperparameter selection or user-profile initialization.

Requests use the categories represented in each user's training plus request
history. For each operation (boost/mute), select one such category by the SHA256
hash of request seed 2026, user ID and operation, modulo the sorted supported
category count. Select the latest historical item bearing that category as the
item-feedback exemplar. This creates two requests per eligible user. Historical
categories may repeat between the two requests; requests are independent resets.
Items can have multiple category labels. IDs remain opaque unless a genuine mapping
is provided; the study does not claim natural semantic understanding of unknown IDs.
Do not extrapolate this narrow canonical-text task to unrestricted natural language.

The catalogue is fixed from positive events strictly before the global training
cutoff. All those catalogue items are initially candidates, including items seen
in an individual user's training or request history. This is the frozen all-catalogue policy, identical across conditions. The retained 865-user cohort has no repeated training items and no test items overlapping a user's training plus request history. A need to preserve repeated held-out targets therefore does not justify this choice in this cohort. Seen candidates can still occupy recommendation slots and reduce next-item quality; an unseen-only comparison would be a separately labelled follow-up, not a retroactive change to the recorded experiment. A hard mute then removes the appropriate item(s); the system
does not reinsert forbidden items to fill a short feed. Categories are fixed
catalogue metadata. No sampled negatives are used for ranking.

## Conditions and parser provenance

| Condition | Inputs and action |
|---|---|
| A | Item-feedback proxy: boost the historical exemplar by +0.25 on minmax-normalized scores, or remove that exemplar. No actual KuaiRec per-interaction like is assumed. |
| B | Exactly A's rankings plus verified cached/template explanations. This is a rank-invariance negative control, not evidence about human responses to explanation. |
| C | Parse `Show more category_N` or `Do not show category_N`, then apply the category command to the frozen scores. |
| D | Parse an editable explicit profile statement (`My preference is to see more category_N` or `My preference is to avoid category_N`) with the same backend's profile parser; apply the resulting profile. |
| E | Combine C and D plus explanations. Merge matching directives once, using the control command's current weight for the same category. Do not sum duplicate intent. |

C–E start from the same frozen recommender scores as A, without first inheriting
the exemplar's item feedback. This isolates an item-specific versus category-level
interface comparison. It is not a factorial experiment estimating three independent
channel contributions. D is a single explicit preference; it does not claim a
human-authored rich personal profile. The archived interaction history is available
for ranking but is not injected as directives into the profile parser.

Correctly parsed identical intent can make C, D and E exactly equal. Report that
equality rather than constructing artificial improvements for E. Hard mute's zero
category exposure is policy enforcement by construction, not proof of LLM advantage. The proposal's directional exposure hypothesis is technically met by C/D/E under the recorded Wilcoxon/BH analysis. With correct canonical parsing, category-wide +0.25 boosts and hard mutes are structurally advantaged over A's one-item intervention; the matching rule parser meets the same criterion. Statistical significance depends on cohort, base scores and nonzero exposure, but this benchmark does not meaningfully discriminate LLM capability from deterministic enforcement.

The rule parser is a diagnostic comparator. An Ollama run must actually invoke the
model and retain its validated result and model/prompt provenance. Cache identical
text, category vocabulary, backend, model and options; cache reuse across users and
training seeds means repeated requests are not independent LLM draws. Controls and
profile text use separate cache identities. Only current explicit preferences may
change state. Unknown or ambiguous text can return clarification.

Operational parser errors remain in request-level output. The failing channel
becomes a no-op and is scored in the intention-to-treat cohort, with failure and
clarification reported separately. A valid D profile remains active if C fails in E.
Never replace an unavailable Ollama call with a rule-parser success. Completely
unavailable LLM runs and partially degraded runs receive explicit status and CLI
exit code 2. Audit requests.json before interpreting any run.

## Metrics and denominator

Let `L` be the returned first K=10 distinct items, `n=|L|`, and `t` the number with
the requested category (each item counts once even if category labels repeat).

* **TCP@10**, on boost requests: `t/10`; larger favors compliance.
* **TCER@10**, on mute requests: `t/10`; smaller favors compliance.
* **Fill rate**: `n/10`, plus conditional exposure `t/n` when `n>0` (undefined for
  an empty feed). Report both alongside TCER. Fixed-denominator TCER alone can be
  gamed by returning no feed.
* **Compliant filled success**: 1 only when ten items were delivered AND a boost
  request has at least one target item or a mute request has zero target items.
  An empty feed never succeeds.
* **HR@1**: 1 if the top item equals the first held-out next-item target, otherwise
  0. An empty feed scores 0. This is not membership in the full test-history set.
* **NDCG@10**, secondary descriptive: `1/log2(rank+1)` if the same next-item target
  is in the top ten, otherwise 0. The IDCG for one relevant item is 1.

Catalogue shortage or broad mutes can make full-fill success impossible. Report the
shortage rather than removing the request. All parser errors, clarifications and
intent-matching rates remain visible. Profile intent correctness requires its
single parsed category and operation to match the assigned request.

## Inference and robustness

The independent unit is the **user**. Average each metric within a user and operation
across requests and seeds before computing paired differences. Users are weighted
equally. Do not treat the two requests or three training seeds as independent users.
Require a complete identical request cohort and all A–E rows in every pooled seed.
Do not pool rule and LLM runs. The aggregate file includes descriptive seed outcomes.

The six primary comparisons are C, D and E versus A for boost TCP and mute TCER.
Use two-sided Wilcoxon signed-rank tests on user differences, Pratt zero handling,
tie-adjusted normal approximation, no continuity correction. Round differences to
12 decimal places before ranking to avoid floating-point tie artifacts. An all-zero
vector has p=1. Apply Benjamini–Hochberg adjustment jointly to these six p-values.
B is excluded because its effect is structurally zero. BH assumes independence or
suitable positive dependence; inference remains exploratory with correlated
contrasts. Signed-rank inference assumes symmetric differences and is approximate
for finite samples. A paired sign-flip sensitivity test is also reported (exact
enumeration for at most 16 nonzero user differences; 10,000 Monte Carlo flips with
the +1 correction otherwise). This tests a related symmetry/exchangeability null.

Report mean paired effect and two-sided 95% percentile bootstrap interval with
5,000 resamples of users. All requests and seeds move together inside the averaged
user statistic. Intervals describe uncertainty across users conditional on the
chosen trained seeds and cached parser outputs, not unrestricted training-seed or
LLM-generation variability. Percentile intervals
are a transparent approximation and may be unreliable for sparse/degenerate
statistics. Flag degenerate differences and small samples.

HR@1 noninferiority is **exploratory**, not the primary efficacy claim. The unsigned proposal says “within 10%” without selecting an absolute or relative interpretation. The original execution protocol chose an absolute margin of 0.10 (ten percentage points). For `delta = HR_treatment − HR_A`, its null is `delta <= -0.10`. A one-sided 95% lower bootstrap bound is the 5th percentile; a Bonferroni simultaneous lower bound uses alpha `0.05/3` for C, D, E. The archived decision requires this bound to be strictly above the negative margin and n>=30 users.

The post-audit, analysis-only supplement also uses a relative margin of `0.10 × mean(HR_A)` with the identical paired-user aggregation and lower-bound rule. The matched A mean averages both request types and three seeds within user, then weights all 865 users equally. It is 0.00250481696 (0.25048%); using only boost requests would incorrectly substitute a different baseline for this pooled comparison. The relative margin is 0.000250481696. The C/D/E simultaneous lower bound is approximately −0.0007707129: absolute comparison passes numerically, relative comparison does not. This sensitivity holds the observed-baseline margin fixed and is not a prospectively specified ratio analysis. Neither raw results nor original hypotheses were modified. Reproduce it with `scripts/analyze_revision.py`; outputs are `results/audit_revision/analysis-v1.json` and `.md`.

Report both interpretations, observed baseline, effect, bounds and the `margin_exceeds_baseline` warning. The absolute result cannot establish preservation of useful quality: even a zero-hit treatment cannot lose 0.10 from this baseline. Do not present a numerical pass as meaningful noninferiority, or nonsignificant superiority as equivalence. Choosing a meaningful margin for a new study requires substantive justification before inspecting its outcomes; later supervisor interpretation cannot retroactively preregister this one.

## Parser thresholds and provenance

The unsigned proposal's Objective 3 and Expected Outcomes specify an 85% exact-accuracy target; Expected Outcomes separately classifies accuracy below 70% as degraded. The frozen Llama result is 79/100: target missed, degradation floor cleared. Its 70.02%–85.83% Wilson interval is descriptive for an authored benchmark. These aggregate thresholds do not erase failures on ambiguous and adversarial cases. The 100 cases were authored by one agent under the rubric, rather than independently generated/adjudicated from the whole taxonomy. The development and test strings have no exact case-insensitive matches, but `dev_012` and `test_044` differ only by a final period. Retain both files unchanged and disclose this near overlap. See `PARSER_BENCHMARK.md` for development/freeze history.

## Required audit checks and interpretive limits

1. Remove or mutate final test labels: requests and every ranking must be unchanged.
2. Reproduce metric values manually, including multi-label items and short/empty feeds.
3. Verify A=B item-for-item; verify C=D=E when both parsers return the same intent.
4. Check parser failures never disappear and never trigger silent rule fallback.
5. Compare pooled user count with the unique user IDs; seed repetition must not
   inflate n. Validate BH against a hand-computed example.
6. Preserve raw requests, parsed outputs, ranking/score/history hashes, per-request
   metrics, dataset fingerprint, seed configuration and model provenance. Evaluation
   `data_sha256` hashes canonical sorted JSON; the preparation manifest also records
   the separate exact file-byte SHA256. These encodings intentionally have different hashes.

The dataset is observational, users are filtered for sequential eligibility, and
control requests are synthetic. No randomized human study, online engagement lift,
causal explanation benefit, satisfaction gain or production deployment claim is
supported by this protocol. The 135-hour schedule is prospective allocation,
not an assertion of past work completed.

## Primary implementation references

* SciPy Wilcoxon: https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.wilcoxon.html
* SciPy paired/bootstrap interval definitions: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html
* statsmodels BH correction: https://www.statsmodels.org/dev/generated/statsmodels.stats.multitest.fdrcorrection.html

The implementation's percentile bootstrap and BH are direct, tested NumPy/Python
implementations; SciPy provides the signed-rank test. The references describe
the statistical procedures, not independent validation of this experiment.
