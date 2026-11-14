# Paper sources

| File | Content |
| --- | --- |
| `research-paper-2026-11-14.tex`, `research-paper-2026-11-14.pdf` | Current revision of the paper (8 pages, IEEE conference format). |
| `references-2026-11-14.bib` | Six further references of the current revision. |
| `references.bib` | Bibliography of the October paper. Unchanged. The current revision uses both files. |
| `research-paper-2026-10-19.tex` | The paper of 19 October 2026. A dated record; it stays as it is. Its PDF is in `deliverables/2026-10-19/`. |
| `IEEEtran.cls`, `IEEEtran.bst` | Document class and bibliography style. |

## Build

Run these commands in this folder. They need `pdflatex` and `bibtex`.

```
pdflatex research-paper-2026-11-14
bibtex research-paper-2026-11-14
pdflatex research-paper-2026-11-14
pdflatex research-paper-2026-11-14
```

## Values of the final-build demonstration runs

One block at the top of `research-paper-2026-11-14.tex` defines a macro for each value that comes from the demonstration runs on the final application build (for example `\FinalRunDate` and `\FinalTags`).
A value that is not recorded yet prints as **[to fill: ...]** in the PDF, so that it cannot be read as a result.
Replace each `\TBF{...}` in that block by the recorded value and build again.
No other part of the paper depends on those runs.
