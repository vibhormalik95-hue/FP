"""Copy a bounded, hash-indexed AI-reference E2 evidence set into the repo.

The complete raw evidence remains in the versioned local delivery ZIP. This
copy retains the protocol/custody/evaluation audit trail without publishing the
retired test references or the 48 MB ranking-row array in Git.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil

FILES = (
    "protocol/protocol-freeze.json",
    "protocol/amendment-01-reference-custody.md",
    "protocol/custody-attempt-2-freeze.json",
    "custody/bank-lock.json",
    "custody/fresh-near-paraphrase-flags.json",
    "custody/screening-round-1.json",
    "custody/initial-label-lock.json",
    "custody/agreement.json",
    "custody/reference-freeze.json",
    "custody/full-freeze.json",
    "inference/run-01/protocol-before-inference.json",
    "inference/run-01/manifest.json",
    "inference/run-01/failures.json",
    "evaluation/manifest.json",
    "evaluation/parser-agreement-with-ai-reference.json",
    "evaluation/parser-failures.json",
    "evaluation/ranking-summary.json",
    "evaluation/predictions-committed-before-reference-join.json",
    "audit/local-terminal-receipt.json",
    "audit/inference-worker-terminal.log",
    "audit/scoring-terminal.log",
    "audit/independent-audit.json",
    "audit/final-e1-hash-verification.json",
    "audit/final-visual-review.json",
    "audit/protocol-review-before-authoring.json",
    "audit/custody-attempt-2-independent-review.json",
    "audit/pre-inference-source-review.json",
    "audit/post-prediction-amendment-provenance.json",
    "audit/prediction-commit-before-reference-join.json",
    "audit/prediction-commit-inventory-count-correction.json",
    "audit/prior-delivery-preservation-before.json",
    "audit/staging-revision-required.json",
    "audit/slide-composition-record.json",
    "audit/delivery-staging.json",
)


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    args = parser.parse_args()
    study, repo, delivery = args.study.resolve(), args.repo.resolve(), args.delivery.resolve()
    if (study / "audit/independent-audit.json").is_file() is False:
        raise ValueError("Missing independent calculation audit")
    stage = json.loads((study / "audit/delivery-staging.json").read_text(encoding="utf-8-sig"))
    if Path(stage["destination"]).resolve() != delivery:
        raise ValueError("Staged delivery mismatch")
    target = repo / "docs/ai-reference-e2-evidence"
    if target.exists():
        raise ValueError("Evidence target already exists; inspect before updating")
    copied = {}
    for relative in FILES:
        source = study / relative
        if not source.is_file():
            raise ValueError("Missing evidence: " + relative)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if digest(source) != digest(destination):
            raise ValueError("Evidence copy mismatch: " + relative)
        copied[relative] = {"sha256": digest(destination), "bytes": destination.stat().st_size}
    zip_meta = stage["copied"]["COMP9500-AIREF-E2-Execution-and-Audit-Evidence-2026-10-14.zip"]
    readme = f"""# Prospective AI-reference Experiment Two: compact evidence

The completed local evaluation used the frozen 100-case synthetic bank and AI
references. It is distinct from the exposed 100-question practice diagnostic
at commit `c6ebda06008c92e4141aa2d91991ac2c0328a1de`. All 288 frozen
Experiment 1 files are preserved. Tanishq and Khushi are separately contextualized
AI annotators; their agreement does not establish independent human truth.

This directory records the prospective protocol and administrative custody
restart, bank screening, both label and reference locks, full pre-inference
freeze, local terminal attempt receipts, parser/ranking results, and independent
calculation audit. `INDEX.json` lists the exact SHA-256 of each copied file.
The original failed-custody receipts were archived without repair. The later
inventory-count correction preserves its erroneous predecessor; both precede
the protected reference join. The first preliminary document staging was
retained because independent review found a stale paper conclusion; the
corrected seven-page paper and its reviewed staging are the delivered version.

Full raw cases, both original AI labels, final references, 200 predictions,
pre-call journals, failures, 41,520 ranking rows, 2,595 complete score vectors,
execution logs and per-file hashes are in the **local** evidence ZIP at
`{delivery / 'COMP9500-AIREF-E2-Execution-and-Audit-Evidence-2026-10-14.zip'}`.
Its SHA-256 is `{zip_meta['sha256']}` and size is {zip_meta['bytes']:,} bytes.
The large `evaluation/ranking-rows.json` (48,213,615 bytes), assigned-request
array (4,564,390 bytes), and raw references are intentionally kept out of Git
for repository size and retired-bank custody. This bank must not be reused as
an unseen test. Model-runner separation applies to the recorded inference;
the raw local bundle is the post-run audit source.

The model was local `llama3.1:8b` Q4_K_M on Ollama 0.34.0, digest
`46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`.
The presentation PDF was composed from original vector pages plus revised
text pages; a full Beamer source rebuild is unverified because local
`beamer.cls` is absent. The unsent professor email is a draft for Vibhor.
"""
    (target / "README.md").write_text(readme, encoding="utf-8")
    index = {"created_utc": datetime.now(timezone.utc).isoformat(),
             "status": "copied_and_sha256_verified", "files": copied,
             "raw_evidence_zip_sha256": zip_meta["sha256"],
             "raw_evidence_zip_bytes": zip_meta["bytes"]}
    (target / "INDEX.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": index["status"], "files": len(copied),
                      "total_bytes": sum(v["bytes"] for v in copied.values()),
                      "index_sha256": digest(target / "INDEX.json")}))


if __name__ == "__main__":
    main()
