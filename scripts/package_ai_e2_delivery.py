"""Stage versioned COMP9500 files, then seal the local SHA-256 inventory.

The full evidence ZIP is local delivery only; repository review uses compact
receipts and summaries. Prior delivery files are verified, never overwritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import zipfile


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return sha256(stream.read()).hexdigest()


def data(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def new_json(path: Path, record: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def verify_prior(study: Path, destination: Path) -> dict:
    prior = data(study / "audit/prior-delivery-preservation-before.json")
    if prior["status"] != "passed":
        raise ValueError("Prior delivery baseline was not verified")
    for name, expected in prior["all_existing_files"].items():
        path = destination / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Previous delivery changed: {name}")
    return prior["all_existing_files"]


def stage(study: Path, aborted: Path, repo: Path, destination: Path) -> None:
    verify_prior(study, destination)
    if data(study / "evaluation/manifest.json")["status"] != "ai_reference_evaluation_completed":
        raise ValueError("Completed evaluation required")
    if data(study / "audit/independent-audit.json")["status"] != "passed":
        raise ValueError("Passed independent audit required")
    if data(study / "audit/final-visual-review.json")["status"] != "passed":
        raise ValueError("Passed page and slide review required")
    pairs = {
        "deliverables/COMP9500-Research-Paper-AIREF-E2-2026-10-14.pdf": "COMP9500-Research-Paper-AIREF-E2-2026-10-14.pdf",
        "deliverables/COMP9500-BCIT-Presentation-AIREF-E2-2026-10-14.pdf": "COMP9500-BCIT-Presentation-AIREF-E2-2026-10-14.pdf",
        "deliverables/COMP9500-Weekly-Progress-Update-AIREF-E2-2026-10-14.docx": "COMP9500-Weekly-Progress-Update-AIREF-E2-2026-10-14.docx",
        "deliverables/COMP9500-Evidence-and-Completion-Checklist-AIREF-E2-2026-10-14.docx": "COMP9500-Evidence-and-Completion-Checklist-AIREF-E2-2026-10-14.docx",
        "deliverables/COMP9500-Methods-Record-AIREF-E2-2026-10-14.md": "COMP9500-Methods-Record-AIREF-E2-2026-10-14.md",
        "deliverables/COMP9500-Professor-Email-Draft-AIREF-E2-2026-10-14.txt": "COMP9500-Professor-Email-Draft-AIREF-E2-2026-10-14.txt",
        "paper/ai-reference-report.tex": "COMP9500-Research-Paper-Source-AIREF-E2-2026-10-14.tex",
        "presentation-bcit/ai-reference-main.tex": "COMP9500-BCIT-Presentation-Source-AIREF-E2-2026-10-14.tex",
    }
    copied = {}
    for source, name in pairs.items():
        origin, target = repo / source, destination / name
        if target.exists() or not origin.is_file():
            raise ValueError(f"Missing source or existing target: {source} -> {name}")
        with origin.open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        if digest(origin) != digest(target):
            raise ValueError(f"Copy mismatch: {name}")
        copied[name] = {"sha256": digest(target), "bytes": target.stat().st_size}
    evidence_name = "COMP9500-AIREF-E2-Execution-and-Audit-Evidence-2026-10-14.zip"
    evidence = destination / evidence_name
    if evidence.exists():
        raise ValueError("Evidence ZIP already exists")
    with zipfile.ZipFile(evidence, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6,
                         allowZip64=True) as archive:
        for label, root in (("completed-custody-attempt-2", study), ("aborted-custody-attempt-1", aborted)):
            for path in sorted(root.rglob("*")):
                relative = path.relative_to(root)
                temporary = ("__pycache__" in relative.parts or path.suffix == ".pyc"
                             or relative.parts[:2] in (("artifacts", "latex-build"),
                                                      ("artifacts", "visual-renders"))
                             or (relative.parts[:1] == ("artifacts",)
                                 and path.name.startswith("slide-inserts")))
                if path.is_file() and not temporary:
                    archive.write(path, f"{label}/{path.relative_to(root).as_posix()}")
    with zipfile.ZipFile(evidence) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError("ZIP CRC verification failed: " + bad)
        entries = len(archive.infolist())
    copied[evidence_name] = {"sha256": digest(evidence), "bytes": evidence.stat().st_size,
                             "entries": entries}
    receipt = {"staged_utc": datetime.now(timezone.utc).isoformat(),
               "status": "versioned_delivery_staged_prior_files_preserved",
               "destination": str(destination.resolve()), "copied": copied,
               "previous_files_preserved": len(verify_prior(study, destination)),
               "email_unsent": True, "evidence_zip_local_only": True}
    new_json(study / "audit/delivery-staging.json", receipt)
    print(json.dumps({"status": receipt["status"], "destination": receipt["destination"],
                      "new_files": len(copied), "zip_bytes": copied[evidence_name]["bytes"],
                      "zip_sha256": copied[evidence_name]["sha256"]}))


def finalize(study: Path, destination: Path) -> None:
    prior = verify_prior(study, destination)
    staged = data(study / "audit/delivery-staging.json")
    for name, item in staged["copied"].items():
        if digest(destination / name) != item["sha256"]:
            raise ValueError("Staged delivery changed: " + name)
    push = destination / "COMP9500-AIREF-E2-Git-Push-Receipt-2026-10-14.json"
    if not push.is_file() or data(push)["status"] != "committed_and_pushed_verified":
        raise ValueError("Verified Git push receipt required")
    manifest = destination / "COMP9500-AIREF-E2-Delivery-Manifest-2026-10-14.json"
    sums = destination / "COMP9500-AIREF-E2-SHA256SUMS-2026-10-14.txt"
    if manifest.exists() or sums.exists():
        raise ValueError("New manifest outputs required")
    files = {p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
             for p in sorted(destination.iterdir()) if p.is_file()}
    if not set(prior).issubset(files) or not set(staged["copied"]).issubset(files):
        raise ValueError("Delivery file inventory incomplete")
    record = {"sealed_utc": datetime.now(timezone.utc).isoformat(),
              "status": "reviewed_local_delivery_complete", "path": str(destination.resolve()),
              "previous_file_count": len(prior), "new_staged_file_count": len(staged["copied"]),
              "email_unsent": True, "files": files,
              "manifest_excludes_self_and_sha256s_to_avoid_recursive_hashes": True}
    new_json(manifest, record)
    with sums.open("x", encoding="utf-8", newline="\n") as stream:
        for name, item in sorted(files.items()):
            stream.write(item["sha256"] + "  " + name + "\n")
        stream.write(digest(manifest) + "  " + manifest.name + "\n")
    print(json.dumps({"status": record["status"], "path": record["path"],
                      "files": len(files) + 2, "manifest_sha256": digest(manifest),
                      "sums_sha256": digest(sums)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", choices=("stage", "finalize"))
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--aborted", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "stage":
        if args.aborted is None or args.repo is None:
            parser.error("stage requires --aborted and --repo")
        stage(args.study, args.aborted, args.repo, args.destination)
    else:
        finalize(args.study, args.destination)
