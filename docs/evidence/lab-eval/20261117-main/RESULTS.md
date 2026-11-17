# KuaiRec language controls: local vs frontier models on the frozen reviewed set

Set lab-eval-set-20261117-frozen (SHA-256 d4af21e6ed311448…), reviewed by Vibhor Malik at 2026-11-17T02:27:25+00:00. Review CSV SHA-256 384c47777bef2984…

## Nonliteral request to existing KuaiRec labels (NL, 20 cases)

| Model | Exact intended profile | 95% CI (Wilson) | Action correct % | Label precision | Label recall | Label F1 | F1 95% CI | Missed required labels | Unwanted clarifications |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 17/20 | [0.6396, 0.9476] | 95% | 0.9500 | 0.9000 | 0.9167 | [0.8, 1.0] | 4 | 1 |
| gpt-5-mini | 16/20 | [0.584, 0.9193] | 95% | 0.9158 | 0.9500 | 0.9304 | [0.823, 0.9967] | 2 | 1 |
| gpt-5 | 17/20 | [0.6396, 0.9476] | 100% | 0.9432 | 0.9750 | 0.9426 | [0.8732, 1.0] | 1 | 0 |

Exact: the reference action and every required label, no label outside required + acceptable.

## Should not propose: ambiguous, unsupported, no match (AB, 14 cases)

| Model | Correct abstention | 95% CI (Wilson) | False acceptance | Status matches reference |
| --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 12/14 | [0.6006, 0.9599] | 2 | 12 |
| gpt-5-mini | 7/14 | [0.268, 0.732] | 7 | 6 |
| gpt-5 | 10/14 | [0.4535, 0.8828] | 4 | 10 |

## New category membership on a shared pool of 150 KuaiRec items (NC, 6 cases)

| Model | Member precision | Member recall | Member F1 | F1 95% CI | Raw-verdict F1 | Missed members |
| --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 1.0000 | 0.7931 | 0.8750 | [0.7907, 0.9593] | 0.9696 | 21 |
| gpt-5-mini | 0.9421 | 0.9336 | 0.9355 | [0.887, 0.9816] | 0.9618 | 6 |
| gpt-5 | 0.9578 | 0.8938 | 0.9176 | [0.8511, 0.9761] | 0.9526 | 11 |

Selected = verdict match, quotation found in the item, and the independent check supports it. Every model used the reviewed reference definition.

## Downstream effect on the trained SASRec ranking (200 sampled users, seed 2026)

| Control | TCP@10 (boost/only cases) | TCER@10 (hide/reduce cases) | NDCG@10 | HR@1 |
| --- | --- | --- | --- | --- |
| none | 0.0063 | 0.0118 | 0.0242 | 0.0050 |
| reference | 0.5290 | 0.0000 | 0.0153 | 0.0062 |
| claude-sonnet-5-5-cli | 0.5625 | 0.0000 | 0.0144 | 0.0040 |
| gpt-5 | 0.5521 | 0.0000 | 0.0156 | 0.0056 |
| gpt-5-mini | 0.5178 | 0.0000 | 0.0145 | 0.0044 |

TCP/TCER: share of the top ten that is in the REFERENCE target set. none = no control; reference = the reviewed control.

## HR@1 non-inferiority against no control (proposal margin 10%)

| Model | Mean HR@1 diff | 95% CI lower | Relative margin | Non-inferior (relative 10%) | Non-inferior (absolute 0.10) | Mean NDCG@10 diff |
| --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | -0.0010 | -0.0027 | -0.0005 | False | True | -0.0097 |
| gpt-5 | 0.0006 | -0.0023 | -0.0005 | False | True | -0.0085 |
| gpt-5-mini | -0.0006 | -0.0021 | -0.0005 | False | True | -0.0096 |

Bootstrap over cases. HR@1 of the base ranking is very low, so the relative margin is tiny.

## TCP@10 fidelity: model control vs reviewed control (boost/only cases)

| Model | Cases | Mean TCP diff | Wilcoxon p | BH-adjusted p |
| --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 16 | 0.0335 | 0.4449 | 0.6543 |
| gpt-5 | 16 | 0.0231 | 0.6543 | 0.6543 |
| gpt-5-mini | 16 | -0.0111 | 0.4971 | 0.6543 |

## Paired comparisons between models (all 40 cases)

| Model A | Model B | Successes A | Successes B | Only A | Only B | McNemar p (BH) | Mean per-case score diff | Wilcoxon p (BH) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | gpt-5 | 33 | 32 | 5 | 4 | 1.0000 | 0.0306 | 0.5712 |
| claude-sonnet-5-5-cli | gpt-5-mini | 33 | 29 | 8 | 4 | 0.7617 | 0.1090 | 0.2691 |
| gpt-5 | gpt-5-mini | 32 | 29 | 6 | 3 | 0.7617 | 0.0784 | 0.2691 |

Success: exact profile (NL), abstention (AB), member F1 >= 0.8 (NC). Score: label F1, abstention, member F1.

## Latency, cost and failures

| Model | Calls | Call errors | Case errors | Median s/call | P90 s/call | Cost USD |
| --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 136 | 0 | 0 | 6.5780 | 7.7500 | 5.8624 |
| gpt-5-mini | 138 | 0 | 0 | 11.6560 | 16.7190 | 0.4749 |
| gpt-5 | 137 | 0 | 0 | 12.5160 | 23.8750 | 2.3888 |

Cost: list price x tokens (OpenAI, Anthropic), as reported (Claude CLI), zero for local models (electricity not counted).
