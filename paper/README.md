# Paper sources

**Draft, not ready for submission.** The current revision is `research-paper-2026-11-17.tex` (17 November 2026). It reports the integrated application on real KuaiRec and Experiment 3: the language controls measured on a frozen set of 40 cases, AI-drafted (Claude Opus 5.5) and human-reviewed, with three hosted and two local models (Llama 3.1 8B and Qwen2.5-Coder 7B Instruct through Ollama). Each table names the prediction commits (hosted `8dd978f`, local `9071f05`) and the scoring commit (`fbb3e59`); every code change after the freeze is listed in `docs/evidence/lab-eval/POST-FREEZE-AUDIT.md`. The downstream values were re-scored on 17 November with each model's exact controls, and the parser re-run applies the grounding rule of the frozen parser.

| File | Content |
| --- | --- |
| `research-paper-2026-11-17.tex`, `research-paper-2026-11-17.pdf` | **Current revision** (8 pages with the references, IEEE conference format). The deck of the same date has 43 pages. |
| `research-paper-2026-11-14.tex`, `research-paper-2026-11-14.pdf` | Revision of 14 November 2026: demonstration runs on invented scenarios, filled with the runs on the integrated revision `ff92666` (records: `docs/evidence/2026-11-14-integrated/`). A dated record; it stays as it is. An earlier build held the values of revision `b7c5a91` (records: `docs/evidence/2026-11-14/`). |
| `references-2026-11-14.bib` | Complete bibliography (22 entries). Both the 14 and the 17 November revisions use this file only. |
| `references.bib` | Bibliography of the October paper. Unchanged. |
| `research-paper-2026-10-19.tex` | The paper of 19 October 2026. A dated record; it stays as it is. Its PDF is in `deliverables/2026-10-19/`. |
| `IEEEtran.cls`, `IEEEtran.bst` | Document class and bibliography style. |

The presentation of the same date is `presentation-bcit/presentation-2026-11-17.tex` and `.pdf` (based on `presentation-bcit/ai-reference-main.tex` of 20 October, which stays as it is).

## Build

Run this command in this folder. It needs `pdflatex` and `bibtex` (MiKTeX or TeX Live) and the packages `mathptmx`, `microtype`, `booktabs` and `tikz`. `latexmk` needs Perl; on Windows the Perl of Git for Windows works (`C:\Program Files\Git\usr\bin` on the `PATH`).

```
latexmk -pdf research-paper-2026-11-17
```

Without `latexmk`: `pdflatex`, `bibtex`, `pdflatex`, `pdflatex` on `research-paper-2026-11-17`. The result has 8 pages. The page limit of the course is 6 to 8 pages with the references.

## Sources of the values of the 17 November revision

Every number is copied from a recorded file. Nothing is a placeholder: the `\TBF` macros of the 14 November revision are removed.

| Values | File |
| --- | --- |
| Experiment 3 (NL, AB, NC, downstream, non-inferiority, paired tests, cost) | `docs/evidence/lab-eval/20261117-main/RESULTS.md` and `summary.json` |
| Parser bank re-run (re-use of the Experiment 1 bank, not new evidence) | `docs/evidence/lab-eval/20261117-b-parser-rerun/summary.json` |
| Construction, review and freeze of the evaluation set | `docs/evidence/lab-eval-set-20261117/README.md` and `FROZEN.json` |
| Windows replay of Experiment 1 (16 November) | `FINAL2/AUDIT.md`, section 4 (outside the repository) |
| gemma4:31b probe (not run) | `docs/evidence/lab-eval/20261117-main/runs/local-chain.log` (local-only: ignored by git, not in the repository) |
| Popularity concentration of the seed-42 ranker (items 8958, 1116) | `docs/evidence/2026-11-17-popularity/top10-concentration-seed42.json` (only 27 distinct items appear in any of the 865 top tens) |
| Experiments 1 and 2, practice evaluation, 4 November study, development records | Unchanged from `research-paper-2026-11-14.tex` |

## Local models

The Llama 3.1 8B and Qwen2.5-Coder 7B rows of Experiment 3 are filled from `RESULTS.md` (scoring commit `fbb3e59`); no placeholder remains. Gemma4 31B was probed but not run (Section X, "Models not measured").

## One sentence for the student

The subsection "Use of AI tools" ends with the sentence "The student reviewed the text." It prints with the marker **[student to confirm]**.
Only the student can confirm it. Remove the marker (the macro `\StudentConfirm`) after he has read the paper, or change the sentence.

## History: values of the 14 November demonstration runs

In `research-paper-2026-11-14.tex`, one block at the top defines a macro for each value of the demonstration runs on the 14 November application build (`\FinalRunDate`, `\FinalRevision`, `\FinalFingerprint`, `\FinalEvidencePath`, `\FinalModel`, `\FinalScenarioItems`, the seven table cells, `\FinalAssertions`, `\FinalRouteChecks`). A value that was not recorded printed as **[to fill: ...]**. All of them were filled with the runs on revision `ff92666`. The paragraph "Runs on the 14 November build" states the limits of those runs: the model replies came from sub-agents of an AI system, an AI operator made every review decision, and the command-line and HTTP routes ran against stand-ins only. The 17 November revision keeps a short summary of these runs in Section IX.

## A version for a conference

This file uses the IEEE conference class and names the author, the supervisor and the course.
A conference can require another template and an anonymous submission. For example, UMAP and SIGIR use the ACM `acmart` class with the `sigconf` option (UMAP 2027 paper deadline 29 January 2027; SIGIR 2027 full papers 21 January 2027; SIGIR 2027 demonstrations 11 February 2027; source: `FINAL2/conference-options-verified.md`).
Such a submission needs a separate version of this paper.
