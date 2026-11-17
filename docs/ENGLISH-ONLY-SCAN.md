# English-only scan (17 November 2026)

Owner decision: English everywhere. All KuaiRec text is translated into English before processing, and the
application, the models and the screen work on that English text only. This page lists every place where
CJK characters (U+3000–U+303F, U+3400–U+9FFF, U+FF00–U+FFEF) remain, and why.

How it was checked:

- Text files tracked by git: `python tools/cjk_scan.py` (every tracked file; binary files skipped).
- PDF files tracked by git: their text layer was extracted and scanned (pypdf). No PDF has a CJK character.
- Images outside the evidence folders (the guide screenshots, `docs/images/`, the BCIT logo) were inspected
  visually: English only. The guide screenshots were retaken on the English application and checked by the
  CJK probe when they were taken.
- The running application: `tests/browser/cjk_check.cjs` (part of `run-all-tests.cmd`) walks every screen
  and every step of the recorded demo and fails on any visible CJK character; the recorder runs the same
  probe live during a take (take 13: 69 checks, none).

## Remaining hits

| Where | Hits | Why it keeps Chinese | Loaded for display or sent to a model? |
| --- | --- | --- | --- |
| Release `comp9500-kuairec-assets-v1` (`data/raw/kuairec_caption_category.csv`, `data/kuairec_gloss_en.json` inside the archive) | the KuaiRec source text | The unchanged official KuaiRec caption table, published with its CC BY-SA 4.0 attribution; the gloss is the translation input of the English layer | No. The application loads only `data/kuairec_text_en-v1.json`. `scripts/lab_eval.py score --text original` reads the source table only to re-score the frozen 17 November run |
| Release `comp9500-kuairec-english-v1`, `kuairec_text_en-v1.label-map.json` | original label names (keys) | Maps each original KuaiRec label to its English label; needed to derive the English version of the frozen evaluation set | No. Read only by `scripts/build_english_eval_set.py` |
| `docs/evidence/lab-eval-set-20261117/cases.frozen.json` | 2,153 | The frozen, human-reviewed evaluation set; its SHA-256 is committed and must not change | No. Read by the scorer of the 17 November run and once by `build_english_eval_set.py`, which machine-translated its 33 Chinese text fields (one gpt-5-mini call, before any prediction of the English run) |
| `docs/evidence/lab-eval-set-20261117/README.md` | 126 | Frozen record of the set (examples quoted from it) | No |
| `docs/evidence/lab-eval/20261117-main/per-case.csv`, `runs/*.jsonl` (5 files) | 1,460; 409–952 per hosted model; 62; 5 | Frozen predictions and per-case scores of the 17 November original-text run | No. The Results page reads only `summary.json`, which has no CJK character |
| Screenshots in `docs/evidence/2026-11-13/`, `2026-11-14/`, `2026-11-14-integrated/`, and the contact sheets of takes 11 and 12 (`2026-11-17-video/`, `2026-11-17-video-take12/`) | images of the earlier interface | Frozen evidence of earlier runs and takes, made before the English text layer | No |

Everything else is English. The 16 non-evidence files that held Chinese (tests, one reproduction script, two
historical deliverable notes) were converted in commit `65ed5c7`. Where a test checks how code that still
exists handles CJK or full-width characters, the input is built from code points at run time, so the
source file itself has no CJK character. The popularity evidence of 17 November now names categories by
their English labels.
