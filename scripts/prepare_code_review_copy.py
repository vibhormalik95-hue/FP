"""Package an explicitly partial code-review copy without research data/results.

This tool inventories excluded research files by SHA-256 without interpreting
their contents. It never opens reserved material for annotation or evaluation.
The copy is not blind-annotator material and cannot reproduce the experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "README.md", "START-HERE.md", "NOTICE.md", "CONTRACT.md", ".gitignore",
    "pyproject.toml", "requirements-tested.txt",
}
DOC_FILES = {
    "135-hour-plan.md", "academic-use.md", "annotation-handoff.md", "app.md",
    "defence-guide.md", "evaluation-protocol.md", "experiment2-protocol.md",
    "experiment2-runbook.md", "experiment2-status.md", "final-progress-report.md",
    "meeting-templates.md", "proposal-amendment.md", "publication-roadmap.md",
    "repository-handoff.md", "supervisor-decision-packet.md",
    "supervisor-progress-2026-10-02.md", "windows-and-colab.md", "LLM_RUNTIME.md",
    "experiment2-annotation-rubric.md", "supervisor-email-draft.md",
    "documentation-update-2026-10-04.md",
}
DELIVERABLE_FILES = {
    "COMP9500-Research-Paper.pdf", "COMP9500-BCIT-Presentation.pdf",
    "COMP9500-Experiment2-Status.pdf", "COMP9500-Final-Progress-Report.pdf",
    "COMP9500-135-Hour-Plan.docx", "COMP9500-Supervisor-Progress-Report.docx",
}
PAPER_FILES = {"manuscript.tex", "references.bib", "IEEEtran.cls", "IEEEtran.bst"}
PRESENTATION_FILES = {"main.tex", "bcit_logo.png", "speaker-notes.md", "README.md"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
REQUIRED = ROOT_FILES | {
    "deliverables/COMP9500-Research-Paper.pdf",
    "deliverables/COMP9500-BCIT-Presentation.pdf",
    "presentation-bcit/main.tex", "paper/manuscript.tex",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def selection(path: Path) -> tuple[bool, str]:
    parts = path.parts
    if parts[0] in {"results", "data", "slides"}:
        return False, "Research evidence, data, caches and predictions are excluded."
    if "sealed" in path.name.lower() or path.suffix in {".pyc", ".log"}:
        return False, "Reserved or generated file."
    if len(parts) == 1 and path.name in ROOT_FILES:
        return True, "Explicit root-file allowlist."
    if len(parts) == 2 and parts[0] in {"feedctrl", "tests", "scripts"}:
        return (path.suffix in {".py", ".cjs", ".mjs", ".sh", ".ps1"},
                "Implementation and test source allowlist.")
    if parts[0] == "web" and (
        (len(parts) == 2 and path.name in {"package.json", "package-lock.json", "vite.config.js", "index.html"})
        or (len(parts) > 2 and parts[1] in {"src", "dist"}
            and path.suffix in {".jsx", ".js", ".css", ".html", ".svg", ".png"})
    ):
        return True, "Frontend source, lockfile and production build."
    if len(parts) == 2 and parts[0] == "docs" and path.name in DOC_FILES:
        return True, "Explicit current-document allowlist; source evidence excluded."
    if len(parts) == 3 and parts[:2] == ("docs", "supervision") and path.suffix in {".md", ".csv", ".ics"}:
        return True, "Supervision planning and activity records."
    if len(parts) == 2 and parts[0] == "deliverables" and path.name in DELIVERABLE_FILES:
        return True, "Explicit current-deliverable allowlist."
    if len(parts) == 2 and parts[0] == "paper" and path.name in PAPER_FILES:
        return True, "Editable paper and template."
    if len(parts) == 2 and parts[0] == "presentation-bcit" and path.name in PRESENTATION_FILES:
        return True, "Editable current BCIT presentation."
    if len(parts) == 2 and parts[0] == "notices" and path.suffix == ".txt":
        return True, "Third-party notice."
    return False, "Not on the explicit sharing allowlist."


README = """# COMP 9500: partial code-review copy

This is a partial code-review copy. Repository visibility and the actual
sharing record are documented in docs/repository-handoff.md. Packaging this
copy does not itself upload files or invite a supervisor.

It contains implementation, test source, frontend source/build, current paper,
BCIT presentation and selected supervision documents. It excludes all research
data and result folders, Experiment 2 language banks, caches, parser predictions,
sealed material, original source evidence and dependency runtimes.

This is NOT the executable full evidence package. Research evaluation,
checkpoint inference, cached replay, full acceptance tests and archive/release
verification require the separate authoritative research archive. Some isolated
synthetic unit tests may run after dependency installation, but no full-suite or
experiment execution is claimed for this partial copy. References to omitted
evidence in the original README, source and documents are intentional.

This is NOT blind-annotator material. It contains parser implementation and
development summaries. The student must not read it while performing the
independent annotation pass. Resolve prior exposure and use the separate
annotation handoff before making any independence statement.

Experiment 1 is complete and frozen. Experiment 2 reserved results remain
pending. AI work is disclosed in docs/academic-use.md. Future student hours,
reading and personal verification must be logged as they actually occur.

sharing-manifest.json records included and excluded regular source files with
SHA-256 hashes. Excluded dependency/VCS directories are listed separately and
not traversed. Excluded-file hashes are an inventory, not disclosed file
contents or evidence of experimental execution. The manifest's own digest is
not embedded in itself. The adjacent ZIP fingerprint covers the whole copy.

Read docs/repository-handoff.md for the actual sharing record. Keep the
full research archive and its separate fingerprint as the evidence authority.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outgoing" / "COMP9500-Code-Review-Copy.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite an existing sharing copy: {output}")
    missing = sorted(p for p in REQUIRED if not (ROOT / p).is_file())
    if missing:
        raise SystemExit(f"Required current files are missing: {missing}")
    included, excluded, skipped = [], [], []
    for base, dirs, files in os.walk(ROOT, followlinks=False):
        base = Path(base)
        for name in sorted(dirs[:]):
            directory = base / name
            if name in SKIP_DIRS or name.startswith(".venv") or directory.is_symlink() or directory == output.parent:
                dirs.remove(name)
                skipped.append({"path": directory.relative_to(ROOT).as_posix(), "reason": "Dependency/VCS/output directory or symlink; not traversed."})
        for name in sorted(files):
            source = base / name
            relative = source.relative_to(ROOT)
            if source.is_symlink():
                skipped.append({"path": relative.as_posix(), "reason": "Symlink excluded; target not read."})
                continue
            selected, reason = selection(relative)
            record = {"path": relative.as_posix(), "bytes": source.stat().st_size,
                      "sha256": digest(source), "reason": reason}
            (included if selected else excluded).append(record)
    included.sort(key=lambda x: x["path"])
    excluded.sort(key=lambda x: x["path"])
    assert not any(r["path"].split("/")[0] in {"results", "data", "slides"} for r in included)
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "purpose": "Partial code review only; not executable full evidence or blind annotation material.",
                "experimental_execution_performed": False,
                "included_files": included, "excluded_files": excluded,
                "excluded_uninventoried_directories_or_links": sorted(skipped, key=lambda x: x["path"]),
                "generated_files": [{"path": "README-CODE-REVIEW.md", "sha256": hashlib.sha256(README.encode()).hexdigest()}]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for record in included:
            source = ROOT / record["path"]
            if digest(source) != record["sha256"]:
                raise SystemExit(f"Source changed during packaging: {record['path']}")
            archive.write(source, "COMP9500-Code-Review/" + record["path"])
        archive.writestr("COMP9500-Code-Review/README-CODE-REVIEW.md", README)
        archive.writestr("COMP9500-Code-Review/sharing-manifest.json", json.dumps(manifest, indent=2) + "\n")
    fingerprint = digest(output)
    output.with_suffix(output.suffix + ".sha256").write_text(f"{fingerprint}  {output.name}\n")
    print(json.dumps({"output": str(output), "sha256": fingerprint,
                      "included_files": len(included), "excluded_files": len(excluded)}, indent=2))


if __name__ == "__main__":
    main()
