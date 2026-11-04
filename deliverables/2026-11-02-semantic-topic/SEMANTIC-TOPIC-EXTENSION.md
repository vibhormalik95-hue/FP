# Optional semantic-topic control, 2 November 2026

This is an **exploratory extension**, separate from the frozen Experiment 1, revised AI-reference Experiment 2 and original A-E condition results. It responds to the 27 October discussion about control requests beyond opaque `category_N` IDs. It creates an ad-hoc set of existing catalog items from source text; it does **not** create videos, certify a new ground-truth taxonomy or establish that an LLM improved human satisfaction.

## What the meeting actually said

The automated transcript is imperfect. At 00:27 the **student** proposed making control "category agnostic" and not limited to categories already in the system. At 01:05 the professor asked first to show that a manually specified action changes the algorithm. At 03:11-03:29 the professor said a verifiable human interpretation is necessary and asked to show that an LLM can also affect the algorithm. The student proposed distinguishing a graded decrease from a complete mute around 01:46-02:54. The professor's explicit next-week requests later in the call were the baseline/manual/LLM pipeline and matching code explanation, five-condition examples, TCP/TCER explanation, results and remaining work. This extension implements a bounded form of the student's proposal; it is not represented as a newly approved research protocol.

## Source and boundary

The optional input is the official [KuaiRec caption/category CSV](https://github.com/chongminggao/KuaiRec/blob/main/kuairec_caption_category.csv), not the frozen `data/processed.json`. The copy downloaded on 2 November was 26,136,653 bytes, SHA-256 `7ccf10f348da6041742222f107da32e1be8b1c8c7b710d65963fa10d56a014f5`. Its `video_id` connects text to the existing candidate catalog. The loader uses `csv.DictReader(skipinitialspace=True)`, which is necessary for padded fields containing quoted commas. It found all 2,593 current candidate IDs; 2,460 have nonempty captions. Four stray rows without numeric video IDs were ignored, and every candidate ID was still accounted for. The CSV remains in ignored `data/raw/` on the local machine and is not committed.

The source text includes Chinese captions and semantic category names. The existing A-E parser remains limited to explicit opaque `category_N` IDs. The new path forms an **ad-hoc topic group** by checking whether supplied search terms appear in caption, cover text, topic tag or semantic name. It returns a few matched source-field names and the item IDs. An exact text match is observable; semantic relevance to a person's request is not independently established.

## Code and request flow

1. `feedctrl/semantic_controls.py:load_topic_index` reads the opt-in sidecar, checks columns and candidate coverage, and records its hash. It refuses incomplete or duplicate candidate IDs.
2. `POST /api/topic/preview` in `feedctrl/api.py` requires a normal session and one of two labelled modes. `manual` takes an explicit `boost`, `reduce` or `exclude` action, bounded strength for boost/reduce, and a literal source-text topic. `ollama` sends a natural-language request to the local Llama model, asking for an operation, bounded strength, topic and at most four short Chinese or English search terms. `validate_topic_command` enforces a strict schema. No remote model or rule fallback is used.
3. `match_topic` checks those terms against official text for existing candidate IDs. No match or a match across more than half the catalog fails visibly. The model cannot add new items or silently declare a topic as ground truth.
4. `rerank_topic` uses the same saved user history and trained SASRec scores. Boost/reduce use a bounded score adjustment: light +/-0.10, standard +/-0.25, or strong +/-0.40. `exclude` removes matched items and has no graded strength. In E context, existing saved category profile weights also apply. The preview is read-only and leaves A-E session state unchanged. The React panel labels the mode, chosen adjustment, item count, top-ten text-match count, eligible-item count and fill. These strengths are exploratory policy settings, not measured user preference intensity.

The path is **not** wired into the frozen E1/E2 evaluation harness. Its text-match count must not be called the original TCP or TCER, because the ad-hoc membership rule is a new proxy rather than the experiment's fixed category reference. An LLM may generate a term that matches source text but is still a poor interpretation. That requires human review and a prospective test design before a scientific performance claim.

## Executed mechanism example

The [receipt](manual-topic-receipt.json) was generated on the saved processed dataset and seed-42 trained model with the explicit source-text topic `青岛` (Qingdao), which is not an official `category_N` ID. Five of 2,593 candidate items had that text. The untouched top ten contained one matching item. Manual literal boost placed two text-matching items in the top ten; graded reduce and hard exclude placed zero there. All three previews filled ten slots. Reduce kept all 2,593 items eligible; exclude left 2,588. The rule `manual_literal` mode was used. **No Llama call, participant preference, fresh held-out evaluation or new statistical result was produced.**

To reproduce from the FP checkout, supply paths to the unchanged processed data, saved seed-42 model directory and downloaded official CSV:

```powershell
python scripts/reproduce_semantic_topic_preview.py DATA_JSON MODEL_DIR CAPTION_CSV
```

For the local UI, set `FEEDCTRL_DATA`, `FEEDCTRL_MODEL` and `FEEDCTRL_CAPTION_SIDECAR` to those three local paths, build `web` with `npm run build`, then launch an **isolated** app on another loopback port:

```powershell
python -m uvicorn feedctrl.api:create_app --factory --host 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8766/` and use "Explore a new topic." The status must say the official caption sidecar is loaded. `manual` is a literal diagnostic, while `ollama` is a real local model request only if Ollama is running. An ungrounded topic returns an explicit no-action response; an operational or still-invalid model response returns an error. Both preserve A-E state. The downloaded sidecar is not bundled in GitHub; see the official source link and verify its version/hash before using it.

The 4 November saved-model rerun also varies only the new bounded manual strength. With the same five text-matched candidates, light boost (+0.10) left one match in the top ten; strong boost (+0.40) showed four. Light reduce (-0.10) left one; strong reduce (-0.40) showed zero. Every preview still filled ten slots. This verifies a score-policy effect for one diagnostic topic; the weights were not learned or calibrated from user preferences.

## Verification and remaining evidence

The isolated parser/ranking/API tests use synthetic sidecars and a mocked Ollama response. They test coverage, validation, explicit error behavior and A-E state preservation, but do not establish live Llama quality. The focused file passed **6/6 tests**. The complete Python suite passed **283 tests with 1 skip** in 32.79 seconds; the skip requires private parser banks absent from this review checkout. `npm run build` passed. The saved-model manual receipt verifies one concrete ad-hoc topic. On 3 November, the reproducer was rerun against the saved data and model. Its counts and rankings matched the prior receipt; the receipt's Chinese topic and evidence fields were corrected from a Windows console encoding error, and the script now prints ASCII-escaped JSON so the command works in legacy consoles. The original A-E results and historical scientific claims remain separate. A future comparison with independently established intended topics, quality measures and predeclared cases would be needed to show that the LLM adds value beyond manual interpretation or simple lexical matching.

### 3 November live smoke, separate from evaluation

One already-installed local `llama3.1:8b` request through `/api/topic/preview` succeeded with a saved-model feed. For "Show me more videos about Qingdao," the returned `boost` command used the Chinese search terms `青岛`, `青岛市`, `山东` and `中国`. It matched 59 candidates and placed nine source-text matches in ten slots with full fill; the A-E feed was unchanged. The manual literal `青岛` matched five candidates. The broader Llama terms are a concrete precision limit. This single smoke establishes execution and provenance, not command accuracy against independent intent, user relevance, or superiority over a manual or rule method. The temporary local model was stopped after the call. The dated private meeting receipt records the exact digest and top-item IDs; those are not part of the frozen experiments.

### 4 November bounded strength check

The focused parser/ranking/API tests passed 6/6, the full Python suite passed 283 with one private-bank skip, and the Vite build passed for the first strength implementation. A real local Llama parse of "Show me a little more Qingdao videos" returned `boost`, `light` and +0.10, but the end-to-end API preview returned HTTP 502 with the A-E feed unchanged. A second Chinese-language preview also returned HTTP 502. The exact later diagnosis found two distinct failures: the English model terms had zero exact matches in the Chinese sidecar, while a Chinese response contained an unsupported one-character term and, on an earlier attempt, an unrelated topic. These are dated smoke observations, not reserved experimental outcomes.

The optional software path was then revised. It makes at most one **model** repair attempt after invalid or ungrounded output; it never switches to a rule interpretation. Validation visibly lists rejected unsupported terms when valid grounded terms remain. No-match or over-broad terms now produce a labelled no-action response rather than an apparent feed change. A still-invalid response remains an error. A subsequent local Chinese request reached the saved-model preview: `boost`, `light`, +0.10, one repair, one rejected one-character term, 73 candidate source-text matches, 1/10 text matches in a full top ten, and unchanged A-E state. The broad terms show that even a working LLM path is **not** a reliable human-topic interpretation. A subsequent English request with no grounded terms returned explicit no-action with unchanged A-E state; another intervening English attempt still returned an operational error, so robustness is not established. The revised code passed 10/10 focused tests, 287 full-suite tests with one private-bank skip, and `npm run build`. No frozen E1/E2 assets, protocol, result or reserved test was changed. The exact failed and successful outputs remain in private dated receipts.
