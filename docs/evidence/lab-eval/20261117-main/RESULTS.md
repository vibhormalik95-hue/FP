# KuaiRec language controls: local vs frontier models on the frozen reviewed set

Set lab-eval-set-20261117-frozen (SHA-256 d4af21e6ed311448…), reviewed by Vibhor Malik at 2026-11-17T02:27:25+00:00. Review CSV SHA-256 384c47777bef2984…. Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.

## Nonliteral request to existing KuaiRec labels (NL, 20 cases)

| Model | Exact intended profile | 95% CI (Wilson) | Action correct % | Label precision | Label recall | Label F1 | F1 95% CI | Missed required labels | Unwanted clarifications |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 17/20 | [0.6396, 0.9476] | 95% | 0.9500 | 0.9000 | 0.9167 | [0.8, 1.0] | 4 | 1 |
| gpt-5-mini | 16/20 | [0.584, 0.9193] | 95% | 0.9158 | 0.9500 | 0.9304 | [0.823, 0.9967] | 2 | 1 |
| gpt-5 | 17/20 | [0.6396, 0.9476] | 100% | 0.9432 | 0.9750 | 0.9426 | [0.8732, 1.0] | 1 | 0 |
| llama3.1_8b | 0/20 | [0.0, 0.1611] | 5% | 0.0333 | 0.0500 | 0.0400 | [0.0, 0.12] | 30 | 17 |
| qwen2.5-coder_7b-instruct | 0/20 | [0.0, 0.1611] | 0% | 0.0000 | 0.0000 | 0.0000 | [0.0, 0.0] | 32 | 20 |

Exact: the reference action and every required label, no label outside required + acceptable. Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.

## Should not propose: ambiguous, unsupported, no match (AB, 14 cases)

| Model | Correct abstention | 95% CI (Wilson) | False acceptance | Status matches reference |
| --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 12/14 | [0.6006, 0.9599] | 2 | 12 |
| gpt-5-mini | 7/14 | [0.268, 0.732] | 7 | 6 |
| gpt-5 | 10/14 | [0.4535, 0.8828] | 4 | 10 |
| llama3.1_8b | 11/14 | [0.5241, 0.9243] | 0 | 5 |
| qwen2.5-coder_7b-instruct | 9/14 | [0.3876, 0.8366] | 0 | 3 |

Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.

## New category membership on a shared pool of 150 KuaiRec items (NC, 6 cases)

| Model | Member precision | Member recall | Member F1 | F1 95% CI | Raw-verdict F1 | Missed members |
| --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 1.0000 | 0.7931 | 0.8750 | [0.7907, 0.9593] | 0.9696 | 21 |
| gpt-5-mini | 0.9421 | 0.9336 | 0.9355 | [0.887, 0.9816] | 0.9618 | 6 |
| gpt-5 | 0.9578 | 0.8938 | 0.9176 | [0.8511, 0.9761] | 0.9526 | 11 |
| llama3.1_8b | 0.2910 | 0.1311 | 0.1795 | [0.0, 0.3846] | 0.1710 | 83 |
| qwen2.5-coder_7b-instruct | 0.9722 | 0.3300 | 0.4692 | [0.3072, 0.6276] | 0.6207 | 64 |

Selected = verdict match, quotation found in the item, and the independent check supports it. Every model used the reviewed reference definition. Measured with the freeze-time quotation rule; the shipped app is stricter since 1de3955 (quotations of 2+ characters, 3+ letters for Latin text, whole tags). Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.

## Downstream effect on the trained SASRec ranking (200 sampled users, seed 2026)

| Control | TCP@10 (boost/only cases) | TCER@10 (hide/reduce cases) | NDCG@10 | HR@1 |
| --- | --- | --- | --- | --- |
| none | 0.0063 | 0.0118 | 0.0242 | 0.0050 |
| reference | 0.5290 | 0.0000 | 0.0153 | 0.0062 |
| claude-sonnet-5-5-cli | 0.5625 | 0.0000 | 0.0144 | 0.0040 |
| gpt-5 | 0.5521 | 0.0000 | 0.0156 | 0.0056 |
| gpt-5-mini | 0.5178 | 0.0000 | 0.0145 | 0.0044 |
| llama3.1_8b | 0.0167 | 0.0109 | 0.0237 | 0.0050 |
| qwen2.5-coder_7b-instruct | 0.0585 | 0.0118 | 0.0217 | 0.0048 |

TCP/TCER: share of the top ten that is in the REFERENCE target set. none = no control; reference = the reviewed control. Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.

## HR@1 non-inferiority against no control (proposal margin 10%)

| Model | Mean HR@1 diff | 95% CI lower | Relative margin | Non-inferior (relative 10%) | Non-inferior (absolute 0.10) | Mean NDCG@10 diff |
| --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | -0.0010 | -0.0027 | -0.0005 | False | True | -0.0097 |
| gpt-5 | 0.0006 | -0.0023 | -0.0005 | False | True | -0.0085 |
| gpt-5-mini | -0.0006 | -0.0021 | -0.0005 | False | True | -0.0096 |
| llama3.1_8b | 0.0000 | 0.0000 | -0.0005 | True | True | -0.0004 |
| qwen2.5-coder_7b-instruct | -0.0002 | -0.0006 | -0.0005 | False | True | -0.0024 |

Bootstrap over cases. HR@1 of the base ranking is very low, so the relative margin is tiny. Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.

## TCP@10 fidelity: model control vs reviewed control (boost/only cases)

| Model | Cases | Mean TCP diff | Wilcoxon p | BH-adjusted p |
| --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 16 | 0.0335 | 0.4449 | 0.6214 |
| gpt-5 | 16 | 0.0231 | 0.6543 | 0.6543 |
| gpt-5-mini | 16 | -0.0111 | 0.4971 | 0.6214 |
| llama3.1_8b | 16 | -0.5122 | 0.0000 | 0.0001 |
| qwen2.5-coder_7b-instruct | 16 | -0.4704 | 0.0000 | 0.0001 |

Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.

## Paired comparisons between models (all 40 cases)

| Model A | Model B | Successes A | Successes B | Only A | Only B | McNemar p (BH) | Mean per-case score diff | Wilcoxon p (BH) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | gpt-5 | 33 | 32 | 5 | 4 | 1.0000 | 0.0306 | 0.6082 |
| claude-sonnet-5-5-cli | gpt-5-mini | 33 | 29 | 8 | 4 | 0.5539 | 0.1090 | 0.2243 |
| claude-sonnet-5-5-cli | llama3.1_8b | 33 | 11 | 24 | 2 | 0.0001 | 0.5677 | 0.0000 |
| claude-sonnet-5-5-cli | qwen2.5-coder_7b-instruct | 33 | 9 | 25 | 1 | 0.0000 | 0.5942 | 0.0000 |
| gpt-5 | gpt-5-mini | 32 | 29 | 6 | 3 | 0.6348 | 0.0784 | 0.2243 |
| gpt-5 | llama3.1_8b | 32 | 11 | 24 | 3 | 0.0001 | 0.5370 | 0.0001 |
| gpt-5 | qwen2.5-coder_7b-instruct | 32 | 9 | 26 | 3 | 0.0001 | 0.5635 | 0.0001 |
| gpt-5-mini | llama3.1_8b | 29 | 11 | 24 | 6 | 0.0024 | 0.4586 | 0.0031 |
| gpt-5-mini | qwen2.5-coder_7b-instruct | 29 | 9 | 25 | 5 | 0.0006 | 0.4852 | 0.0009 |
| llama3.1_8b | qwen2.5-coder_7b-instruct | 11 | 9 | 5 | 3 | 0.8073 | 0.0265 | 0.6082 |

Success: exact profile (NL), abstention (AB), member F1 >= 0.8 (NC). Score: label F1, abstention, member F1. Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.

## Latency, cost and failures

| Model | Calls | Call errors | Case errors | Median s/call | P90 s/call | Cost USD |
| --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5-cli | 136 | 0 | 0 | 6.5780 | 7.7500 | 5.8624 |
| gpt-5-mini | 138 | 0 | 0 | 11.6560 | 16.7190 | 0.4749 |
| gpt-5 | 137 | 0 | 0 | 12.5160 | 23.8750 | 2.3888 |
| llama3.1_8b | 106 | 13 | 9 | 125.7660 | 267.3590 | 0 |
| qwen2.5-coder_7b-instruct | 138 | 10 | 5 | 109.0320 | 159.3750 | 0 |

Cost: list price x tokens (OpenAI, Anthropic), as reported (Claude CLI), zero for local models (electricity not counted). Predictions produced at commit: claude-sonnet-5-5-cli 8dd978f; gpt-5 8dd978f; gpt-5-mini 8dd978f; llama3.1_8b 9071f05; qwen2.5-coder_7b-instruct 9071f05. Scored at commit fbb3e59.
