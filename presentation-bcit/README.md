# BCIT presentation

**Updated:** 4 October 2026, Vancouver time.

This supervisor review draft adapts the supplied BCIT Beamer template. It retains the original 4:3 slide size, Metropolis theme, blue and yellow colours, title-page logo and content-slide logo footer. Section separator pages are disabled to keep a 22-slide main talk. Six backup slides support discussion.

## Files

- `main.tex`: editable presentation source.
- `../deliverables/COMP9500-BCIT-Presentation.pdf`: current compiled presentation.
- `bcit_logo.png`: supplied logo, renamed to the lowercase filename expected by the template.
- `speaker-notes.md`: proposed 23-minute talk, sources, backup explanations and rehearsal checklist.

The full evidence archive also retains `template-provenance.json`, with hashes of the supplied template and logo, and the original `build-review.json`. Those historical records are omitted from this partial code-review copy.

## Build

From this directory:

```bash
mkdir -p .build
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=.build main.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=.build main.tex
cp .build/main.pdf ../deliverables/COMP9500-BCIT-Presentation.pdf
```

These commands keep auxiliary files under `.build/`, compile twice with pdfLaTeX, and copy the final PDF to the deliverables directory. The supplied template permits pdfLaTeX. Metropolis emits a font-engine warning because pdfLaTeX does not use Fira fonts through XeLaTeX or LuaLaTeX. The output uses the template's pdfLaTeX fallback. The existing title-page content box fits the available frame height while retaining the title treatment and logo placement. On a machine with the relevant Fira fonts installed, the supervisor's suggested XeLaTeX workflow may be used and its output should be inspected again.

## Evidence boundary

The presentation reports the frozen Experiment 1 findings and archived Experiment 2 development results. Experiment 2's reserved study is pending. H1 and H2 are unassessed and H3 has not run. The unavailable-runtime statement refers to the recorded 3 October check, separately from the archived successful local-model development runs. Full research execution on Windows and Colab remains unverified.

The schedule is a prospective 135-hour student work plan for 5 October to 18 December. It places the readiness decision on 23 October and reserved evaluation on 26 October to 1 November if the protocol requirements are satisfied. The complete paper draft is due by 27 November. December 18 is a proposed final date awaiting confirmation. Personal student reading, hours worked and verification belong in the activity log after they occur.

The full evidence archive retains the superseded PowerPoint draft as `deliverables/COMP9500-Research-Presentation.pptx`. It is omitted from this partial copy. Use the BCIT PDF for the current supervisor presentation. It is a LaTeX presentation.
