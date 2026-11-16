# Paper sources

**Draft, not ready for submission.** The fifteen run values are filled with the runs of 14 November 2026 on the integrated revision `ff92666` (records: `docs/evidence/2026-11-14-integrated/`). An earlier build of this paper held the values of revision `b7c5a91`; those records stay in `docs/evidence/2026-11-14/`.

| File | Content |
| --- | --- |
| `research-paper-2026-11-14.tex`, `research-paper-2026-11-14.pdf` | Current revision of the paper (8 pages with the references, IEEE conference format). |
| `references-2026-11-14.bib` | Complete bibliography of the current revision (22 entries). The current revision uses this file only. |
| `references.bib` | Bibliography of the October paper. Unchanged. |
| `research-paper-2026-10-19.tex` | The paper of 19 October 2026. A dated record; it stays as it is. Its PDF is in `deliverables/2026-10-19/`. |
| `IEEEtran.cls`, `IEEEtran.bst` | Document class and bibliography style. |

## Build

Run these commands in this folder. They need `pdflatex` and `bibtex`, and the LaTeX packages `mathptmx`, `microtype`, `booktabs` and `tikz`.

```
pdflatex research-paper-2026-11-14
bibtex research-paper-2026-11-14
pdflatex research-paper-2026-11-14
pdflatex research-paper-2026-11-14
```

The result has 8 pages. The page limit of the course is 6 to 8 pages with the references.

## Values of the 14 November demonstration runs

One block at the top of `research-paper-2026-11-14.tex` defines a macro for each value that comes from the demonstration runs on the 14 November application build.
A value that is not recorded yet prints as **[to fill: ...]** in the PDF, so that it cannot be read as a result.
Replace each `\TBF{...}` in that block by the recorded value and build again.

| Macro | Value |
| --- | --- |
| `\FinalRunDate` | Date of the runs, with the time zone. |
| `\FinalRevision`, `\FinalFingerprint` | Revision of the application and the first 12 characters of its source fingerprint. |
| `\FinalEvidencePath` | Folder of the run records in this repository. |
| `\FinalModel` | Model name as declared by the route. |
| `\FinalScenarioItems` | Number of items in the category-and-tag scenario, as a word. |
| `\FinalManual`, `\FinalTags`, `\FinalMixed`, `\FinalAbstain`, `\FinalDescriptions`, `\FinalNewCategory`, `\FinalFictional` | One cell each of the table of recorded outcomes. |
| `\FinalAssertions` | Scripted assertions passed, and the number of review decisions. It completes the sentence "In total, ...". |
| `\FinalRouteChecks` | What ran against each stand-in. It completes the sentence "Route checks: ...". |

The paragraph "Runs on the 14 November build" states the limits of those runs as fixed text: who produced the model replies, who made the review decisions, and which routes ran against stand-ins only.
Read that paragraph again before you report other runs, and change it if their conditions differ: the model route and the limits of its attestation, the reviewer, the exposure of the scenarios, the platform, and which checks used authored replies or stand-ins. New values in the macros alone are not sufficient.
Keep the paper at 8 pages: with values of ordinary length, about nine lines of the last column stay free.

## One sentence for the student

The subsection "Use of AI tools" ends with the sentence "The student reviewed the text." It prints with the marker **[student to confirm]**.
Only the student can confirm it. Remove the marker (the macro `\StudentConfirm`) after he has read the paper, or change the sentence.

## A version for a conference

This file uses the IEEE conference class and names the author, the supervisor and the course.
A conference can require another template and an anonymous submission. For example, UMAP and SIGIR use the ACM `acmart` class with the `sigconf` option.
Such a submission needs a separate version of this paper.
