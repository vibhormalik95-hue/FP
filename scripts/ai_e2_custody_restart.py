"""Create a separately frozen reference-custody attempt after v1's receipt failure.

This deliberately reuses the prospectively selected v1 question bank, without
copying either v1 label or receipt into the new attempt. No model has seen the
fresh cases in an inference run. The v1 attempt remains byte-for-byte intact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def main(previous: Path, current: Path) -> None:
    if current.exists():
        raise FileExistsError(current)
    if not (previous / "custody/references-aborted.json").is_file():
        raise ValueError("Prior reference attempt must have an abort receipt")
    if (previous / "inference/opened.json").exists() or (previous / "custody/reference-freeze.json").exists():
        raise ValueError("Cannot reuse a bank after inference or final reference freeze")
    lock = json.loads((previous / "custody/bank-lock.json").read_text())
    if lock.get("n") != 100 or lock.get("selected_round") != 1:
        raise ValueError("Prior selected bank is not the frozen 100-case round")
    if digest(previous / "inference/questions.json") != lock["inference_questions_sha256"]:
        raise ValueError("Selected bank has changed")
    keep = [
        "protocol/ai-reference-e2-protocol-2026-10-14.md",
        "protocol/ai-reference-e2-role-prompts-2026-10-14.json",
        "protocol/ai-reference-e2-rubric-2026-10-14.md",
        "protocol/protocol-freeze.json",
        "authoring/authoring-brief.json",
        "authoring/round-1-author-receipt.json",
        "authoring/round-1-candidates.json",
        "authoring/round-1-intent-plan.json",
        "custody/bank-lock.json",
        "custody/bank-plan-action-receipt.json",
        "custody/fresh-near-paraphrase-flags.json",
        "custody/intent-plan.json",
        "custody/questions-master.json",
        "custody/screening-round-1-action-receipt.json",
        "custody/screening-round-1-preflight.json",
        "custody/screening-round-1.json",
        "custody/selection-round-1.json",
        "annotations/tanishq/questions.json",
        "annotations/khushi/questions.json",
        "inference/questions.json",
        "audit/protocol-review-before-authoring.json",
        "audit/agent-model-identity-before-authoring.json",
        "audit/e1-before-authoring.json",
        "audit/prior-delivery-preservation-before.json",
        "audit/local-terminal-receipt.json",
        "audit/no-case-boundary-preflight.json",
        "audit/no-case-guarded-api-health.json",
        "audit/pre-inference-source-review.json",
    ]
    keep.extend(str(p.relative_to(previous)).replace("\\", "/")
                for p in sorted((previous / "protocol/source").rglob("*")) if p.is_file())
    current.mkdir(parents=True)
    copied = {}
    for name in keep:
        source = previous / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = current / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(source) != digest(target):
            raise ValueError(f"Copy changed: {name}")
        copied[name] = digest(source)
    amendment = (
        "# Reference custody attempt 2 (pre-inference administrative amendment)\n\n"
        "The v1 receipt comparison stopped before agreement because both otherwise "
        "locked AI annotator receipts used `actualfinalized_utc` instead of the "
        "required `finalized_utc`. The original v1 labels, receipts, hashes and "
        "abort record remain untouched. No inference or result scoring occurred.\n\n"
        "This second custody attempt reuses exactly the previously frozen 100 "
        "question texts, IDs, selection, prompt, rubric, ranking inputs, seeds, "
        "metrics, model digest and validators. No cases are authored or selected "
        "again. The earlier independent labels and receipts are not copied or "
        "shown to the new annotator contexts. Tanishq and Khushi independently "
        "annotate the unchanged question-only sheets anew. Their receipts must "
        "contain the exact `finalized_utc` field with a real timezone-aware UTC "
        "timestamp; `actualfinalized_utc` may be retained as extra metadata but "
        "does not replace the required key. Both initial bytes are locked before "
        "any label comparison. Any new malformed/incomplete input aborts this "
        "second attempt.\n\n"
        "The original study ID remains the frozen bank/design identifier "
        "`AIREF-E2-20261014-v1`; this package is custody attempt 2, stored "
        "separately. Agreement is descriptive AI-reference agreement, with no "
        "human-ground-truth claim. No outcome-dependent change is permitted.\n"
    )
    amend_path = current / "protocol/amendment-01-reference-custody.md"
    amend_path.write_text(amendment, encoding="utf-8", newline="\n")
    previous_receipts = {}
    for role in ("tanishq", "khushi"):
        for kind in ("labels", "receipt"):
            previous_receipts[f"{role}_{kind}_sha256"] = digest(previous / f"annotations/{role}/{kind}.json")
    record = {
        "study_id": "AIREF-E2-20261014-v1",
        "custody_attempt_version": 2,
        "status": "new_independent_AI_annotation_required_before_comparison",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "previous_attempt": str(previous.resolve()),
        "current_attempt": str(current.resolve()),
        "previous_abort_sha256": digest(previous / "custody/references-aborted.json"),
        "previous_originals_preserved_hashes_only_not_role_inputs": previous_receipts,
        "selected_bank_reused_unchanged": True,
        "previous_selected_bank_lock_sha256": digest(previous / "custody/bank-lock.json"),
        "previous_protocol_freeze_sha256": digest(previous / "protocol/protocol-freeze.json"),
        "new_amendment_sha256": digest(amend_path),
        "copied_source_sha256": copied,
        "no_prior_labels_or_receipts_copied": True,
        "no_model_inference_in_previous_attempt": True,
    }
    write_new(current / "protocol/custody-attempt-2-freeze.json", record)
    print(json.dumps({"status": record["status"], "root": str(current.resolve()),
                      "freeze_sha256": digest(current / "protocol/custody-attempt-2-freeze.json"),
                      "bank_lock_sha256": record["previous_selected_bank_lock_sha256"],
                      "copied_files": len(copied)}))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: ai_e2_custody_restart.py PREVIOUS_ROOT NEW_ROOT")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
