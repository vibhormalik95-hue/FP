---
title: "COMP 9500 weekly progress report"
subtitle: "LLM-Mediated Natural Language Controls for Short-Video Recommender Systems"
author: "Vibhor Malik, for Dr Borna Noureddin, BCIT"
date: "17 November 2026"
---

# Summary

- **Code and evidence:** <https://github.com/vibhormalik95-hue/FP/tree/comp9500-final-2026-11-r6> (tag `comp9500-final-2026-11-r6` on `main`).
- **Guide:** `docs/guide/PROFESSOR-GUIDE.pdf`: install, `fetch-assets.cmd`, start, paste an API key, each workflow, the Results page, the tests. The KuaiRec subset, the English text layer and the trained checkpoints are GitHub Release assets (CC BY-SA 4.0); `fetch-assets.cmd` downloads them and checks every SHA-256.
- **Demo video:** `COMP9500-Feed-Control-Lab-demo.mp4` (take 14, 10:57; to be sent separately by the owner, not in the repository).
- **English status:** The app works in English only; measured numbers come from the original-text run (17 Nov). An English-input run exists, but its identity could not be verified (the hosted runs were resumed across commits and the run manifest kept only the last commit), so no English-input figure is reported.

# Your requests from the meeting

1. **Manual categories as the reference, with measured performance that shows the language model working.** Done. The tab *Choose a category* applies existing KuaiRec categories and tags by hand (no model). On the frozen 40-case set, the model controls were compared with the human-reviewed reference controls: on 20 nonliteral requests gpt-5 and Claude Sonnet 5.5 chose the exact intended labels in 17 cases and gpt-5-mini in 16; on the trained ranking, the reviewed control raises the share of target videos in the top ten from 0.6% to 52.9%, and the model controls reach 51.8–56.3% (no significant difference from the reviewed control). Measured on the original-text run (17 Nov).
2. **Language creates new categories that feed the filter.** Done. The model proposes a definition from a description, the person reviews it, the model classifies every item in scope with a quotation, a separate call checks each quotation, and Apply uses the category as a filter (show only, more, less, hide). On 6 reviewed descriptions over 150 KuaiRec items, member F1 is 0.94 (gpt-5-mini), 0.92 (gpt-5) and 0.88 (Claude). In take 14 the new category "Dogs" selected 3 of 50 videos and two of them entered the top ten (details below).
3. **Language maps nonliteral requests to existing categories and tags.** Done. The tab *Say it your way* maps a request in any wording to the 266 KuaiRec categories and 201 frequent topic tags; the server checks every label. Results as in item 1; on 14 requests that should change nothing, Claude abstained on 12, gpt-5 on 10, gpt-5-mini on 7.
4. **Two or three conferences.** Two venues, three submission options: ACM UMAP 2027 full/short paper (abstract 22 Jan, paper 29 Jan 2027; best fit), ACM SIGIR 2027 full paper (14 / 21 Jan 2027) and ACM SIGIR 2027 demo paper (4 / 11 Feb 2027; fallback). All 23:59 AoE; dates re-checked on the official pages, see the conference-options file.
5. **What remains.** See the last section.

# This week

1. **English only.** All KuaiRec text (titles, captions, cover text, tags, category names) is translated into English before processing; the app, its model calls and the screen use only that English layer (`data/kuairec_text_en-v1.json`, machine translation of KuaiRec, CC BY-SA 4.0). A browser check walks every screen and every demo step and fails on any visible Chinese character.
2. **Fixes after take 13.** The new-category step of the earlier take 13 selected no member. I reproduced it with every model call saved and fixed three defects, each with a regression test: the scope is now the top of the *current* feed (not the original ranking), the new-item review shows the evidence check and its reason, and the definition step asks for conditions the item text can establish. Details: `docs/notes/2026-11-17-recording-and-qa-history.md`.
3. **Take 14** (gpt-5-mini at low effort, the measured setting; user 14 with the five news and incident categories hidden):
   - New category from "Videos about dogs. Any video whose title, description or tags mention a dog or a puppy belongs to the category.", scope the top 50 of the current feed: **3 of 50 selected** (items 2882, 8902, 7564).
   - **Top ten changed after Apply:** before 7383, 2894, 4367, 2687, 4506, 1146, 5993, 2882, 10184, 8777; after 2882, 8902, 7564, 7383, 2894, 4367, 2687, 4506, 1146, 5993.
   - **New item** "Our puppy's first walk in the park": matched on "puppy", the evidence check supported it, so it joined the category (4 members). It starts at the user's median score, so it does not enter the top ten by itself.
4. **Tests** (`run-all-tests.cmd`, mock provider, release r6): Python 1,882 passed, 44 skipped, 1 failed by design (the frozen 11 Nov guarded profile, whose offline guard cannot run on Windows); page unit tests 136/136; browser flow checks 42/42; English-only screens: 57, no visible CJK character; workflow checks 21/21.

# Key measured numbers (frozen set; measured on the original-text run, 17 Nov)

| Measure | Claude Sonnet 5.5 (Claude CLI) | gpt-5 | gpt-5-mini | llama3.1:8b | qwen2.5-coder:7b |
|:------------------|:--------|:--------|:--------|:--------|:--------|
| Nonliteral request → exact intended labels (of 20) | 17 | 17 | 16 | 0 | 0 |
| Correct abstention when nothing should change (of 14) | 12 | 10 | 7 | 11* | 9* |
| New-category member F1 (150-item pool) | 0.875 | 0.918 | 0.936 | 0.179 | 0.469 |
| Target share in top 10, boost/only (none 0.006, reference 0.529) | 0.563 | 0.552 | 0.518 | 0.017 | 0.059 |

\* The local models declined almost every request, so these abstentions do not show judgement.

Source: `docs/evidence/lab-eval/20261117-main/RESULTS.md`. Claude Sonnet 5.5 was measured through the local Claude command-line program (subscription), not the Anthropic API. The measured scoring differs from the shipped app in two points: it applied all "only" labels of a case as one group (the app intersects separate controls; affected cases NL06, NL08, NL15), and it used the quotation rule of the freeze (the shipped rule is stricter). Claude (Opus 5.5) drafted the 40 cases and I reviewed all 1,211 judgements (my own attestation, not independently verified); Claude is also a measured model, a disclosed bias risk. Using hosted models is a declared departure from the proposal's local-only plan.

# What remains

- English-input figures: a verified English-input run of the frozen set (English set frozen at `4847d80`).
- A live test of the Anthropic API route (needs a key); a gemma4:31b run on a faster machine.
- Proposal items unchanged from the worksheet: per-item explanations and their cache (R09, R10), the ~200-word profile (R12), channel isolation (R19), a meaningful HR@1 non-inferiority result (R24). New items with descriptions are demonstrated but not measured.
- Choosing a venue together.
