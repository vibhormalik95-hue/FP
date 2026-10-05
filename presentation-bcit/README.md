# BCIT presentation

This supervisor review draft adapts the supplied BCIT Beamer template. It retains the original 4:3 slide size, Metropolis theme, blue and yellow colours, title-page logo and content-slide logo footer. Section separator pages are disabled to keep a 22-slide main talk. Six backup slides support discussion.

## Files

- `main.tex`: editable presentation source.
- `main.pdf`: compiled presentation, also copied to `deliverables/COMP9500-BCIT-Presentation.pdf`.
- `bcit_logo.png`: supplied logo, renamed to the lowercase filename expected by the template.
- `speaker-notes.md`: proposed 23-minute talk, sources, backup explanations and rehearsal checklist.
- `template-provenance.json`: hashes of the supplied template source, reference PDF and logo, plus evidence inputs.
- `build-review.json`: actual build, content and rendering check record.

## Build

From this directory:

```bash
bash build.sh
```

The script writes auxiliary files under `.build/`, compiles twice with pdfLaTeX, and copies the final PDF to the presentation and deliverables directories. The recorded build uses pdfLaTeX, as the supplied template permits. Metropolis emits a font-engine warning because pdfLaTeX does not use Fira fonts through XeLaTeX or LuaLaTeX. The output uses the template's pdfLaTeX fallback. The title-page content box was adjusted to the available frame height to remove the template's overflow warning while retaining the title treatment and logo placement. On a machine with the relevant Fira fonts installed, the supervisor's suggested XeLaTeX workflow may be used and its output should be inspected again.

## Evidence boundary

The presentation reports the frozen Experiment 1 findings and archived Experiment 2 development results. Experiment 2's reserved study is blocked. H1 and H2 are unassessed, H3 has not run, and no result is substituted. The current unavailable-runtime statement refers to this delivery environment, not to the archived successful local-model development runs.

The schedule is a prospective 135-hour student work plan. December 18 is a proposed final date awaiting confirmation. Nothing here certifies personal student reading, hours worked or manual verification. Record those activities after performing them.

The historical PowerPoint draft remains in `deliverables/COMP9500-Research-Presentation.pptx`. Use this BCIT PDF for the current supervisor presentation. It is a LaTeX presentation, not a PowerPoint rendering check.
