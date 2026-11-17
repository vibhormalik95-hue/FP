---
title: "COMP 9500 weekly progress report"
subtitle: "LLM-Mediated Natural Language Controls for Short-Video Recommender Systems"
author: "Vibhor Malik, for Dr Borna Noureddin, BCIT"
date: "17 November 2026"
---

# Summary

- **Code and evidence:** <https://github.com/vibhormalik95-hue/FP/tree/comp9500-final-2026-11-r5> (tag `comp9500-final-2026-11-r5` on `main`).
- **Guide:** `docs/guide/PROFESSOR-GUIDE.pdf`: install, `fetch-assets.cmd`, start, paste an API key, each workflow, the Results page, the tests. The KuaiRec data, the English text layer and the trained checkpoints are GitHub Release assets (CC BY-SA 4.0); `fetch-assets.cmd` downloads them and checks every SHA-256.
- **Demo video:** `COMP9500-Feed-Control-Lab-demo.mp4` (take 14, 10:57, sent separately).
- **English status:** the app works in English only; measured numbers come from the original-text run; the English set is frozen at `4847d80` and its re-run is pending.

# Your requests from the meeting

1. **Manual categories as the reference, with measured performance that shows the language model working.** Done. The tab *Choose a category* applies existing KuaiRec categories and tags by hand (no model). On the frozen 40-case set, the model controls were compared with the human-reviewed reference controls: on 20 nonliteral requests gpt-5 and Claude Sonnet 5.5 chose the exact intended labels in 17 cases and gpt-5-mini in 16; on the trained ranking, the reviewed control raises the share of target videos in the top ten from 0.6% to 52.9%, and the model controls reach 51.8–56.3% (no significant difference from the reviewed control). Measured on the original-text run (17 Nov).
2. **Language creates new categories that feed the filter.** Done. The model proposes a definition from a description, the person reviews it, the model classifies every item in scope with a quotation, a separate call checks each quotation, and Apply uses the category as a filter (show only, more, less, hide). On 6 reviewed descriptions over 150 KuaiRec items, member F1 is 0.94 (gpt-5-mini), 0.92 (gpt-5) and 0.88 (Claude). In take 14 the new category "Dogs" selected 3 of 50 videos and two of them entered the top ten (details below).
3. **Language maps nonliteral requests to existing categories and tags.** Done. The tab *Say it your way* maps a request in any wording to the 266 KuaiRec categories and 201 frequent topic tags; the server checks every label. Results as in item 1; on 14 requests that should change nothing, Claude abstained on 12, gpt-5 on 10, gpt-5-mini on 7.
4. **Two or three conferences.** ACM UMAP 2027 (abstract 22 Jan, paper 29 Jan 2027; best fit), ACM SIGIR 2027 full papers (14 / 21 Jan 2027), ACM SIGIR 2027 demo papers (4 / 11 Feb 2027; fallback). All 23:59 AoE, read on the official pages on 16–17 November.
5. **What remains.** See the last section.

# This week

1. **English only.** All KuaiRec text (titles, captions, cover text, tags, category names) is translated into English before processing; the app, the models and the screen use only that English layer (`data/kuairec_text_en-v1.json`, machine translation of KuaiRec, CC BY-SA 4.0). A browser check walks every screen and every demo step and fails on any visible Chinese character; it passes.
2. **Why take 13 showed no new-category member, and the fixes.** The app selects an item for a new category only if the classifier says "match", its quotation is found in the item's text, and a separate evidence check (which sees the definition, the item and the quotation, not the verdict) supports it. I reproduced take 13 with every model request and response saved. The rule works as designed; both rejections came from the evidence check, which was valid for that definition: the definition demanded that "the main visual subject" be nature, which text can rarely show, and the hike description stressed "a view over the city". At the measured effort (low) instead of the take's minimal effort, item 2894 was accepted. I fixed three real defects, each with a regression test:
   - the scope was the top N of the *original* ranking, so 5 of the 10 classified videos were ones the user had already hidden; it is now the top N of the current feed;
   - the new-item review did not show the evidence check, so "match … not selected" looked contradictory; it now shows the check and its reason, and counts it among the checks;
   - the definition step now asks for conditions the item text can establish.
3. **Take 14** (gpt-5-mini at low effort, the measured setting; user 14 with the five news and incident categories hidden):
   - New category from "Videos about dogs. Any video whose title, description or tags mention a dog or a puppy belongs to the category.", scope the top 50 of the current feed: **3 of 50 selected** (items 2882, 8902, 7564).
   - **Top ten changed after Apply:** before 7383, 2894, 4367, 2687, 4506, 1146, 5993, 2882, 10184, 8777; after 2882, 8902, 7564, 7383, 2894, 4367, 2687, 4506, 1146, 5993.
   - **New item** "Our puppy's first walk in the park": matched on "puppy", the evidence check supported it, so it joined the category (4 members). It starts at the user's median score, so it does not enter the top ten by itself.
   - Checks: no silence of 5 s or more, the transcript matches all 103 script sentences, one frame every 30 s, no visible Chinese character (69 live checks). It took 4 live attempts (one aborted at the key check, one stopped when the laptop ran low on memory, one had a 6.7 s silence).
4. **Tests.** `run-all-tests.cmd` before the fixes: Python 1,763 passed, 75 skipped, 1 failed (a frozen 11 November profile that is failing by design); page 126/126; browser 29/29; English-only check 53 screens; workflows 14/14. After the fixes: Python 1,766 passed (3 new regression tests), same single failure; page 126/126; browser 29/29; English-only check 57 screens; workflows 17/17.

# Key measured numbers (frozen set; measured on the original-text run, 17 Nov)

| Measure | Claude Sonnet 5.5 | gpt-5 | gpt-5-mini | llama3.1:8b | qwen2.5-coder:7b |
|:------------------|:--------|:--------|:--------|:--------|:--------|
| Nonliteral request → exact intended labels (of 20) | 17 | 17 | 16 | 0 | 0 |
| Correct abstention when nothing should change (of 14) | 12 | 10 | 7 | 11* | 9* |
| New-category member F1 (150-item pool) | 0.875 | 0.918 | 0.936 | 0.179 | 0.469 |
| Target share in top 10, boost/only (none 0.006, reference 0.529) | 0.563 | 0.552 | 0.518 | 0.017 | 0.059 |

\* The local models declined almost every request, so these abstentions do not show judgement.

Source: `docs/evidence/lab-eval/20261117-main/RESULTS.md`. Claude (Opus 5.5) drafted the 40 cases and I reviewed all 1,211 judgements; Claude is also a measured model, a disclosed bias risk. Using hosted models is a declared departure from the proposal's local-only plan.

# Take 13 (alternative, if preferred)

Take 13 (10:12) shows the same four tabs on the English-only app with gpt-5 at minimal reasoning effort. In it, the new-category step selected 0 members, so the feed did not change (2,100 eligible before and after Apply), and the new hike item matched with a quotation but was not selected. The reason, found afterwards, was the separate evidence check, which the review screen did not yet show.

# What remains

- The English-input re-run of the frozen set (set frozen at `4847d80`; not yet reported).
- A live test of the Anthropic API route; a gemma4:31b run on a faster machine.
- Proposal items unchanged from the worksheet: per-item explanations and their cache (R09, R10), the ~200-word profile (R12), channel isolation (R19), a meaningful HR@1 non-inferiority result (R24). New items with descriptions are demonstrated but not measured.
- Choosing a venue together.
