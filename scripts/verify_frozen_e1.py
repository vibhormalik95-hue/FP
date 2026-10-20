"""Hash the original E1 manifest only; never execute experiments or parse evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


ORIGINAL_MANIFEST_SHA256 = "80ff8138e6ad7abd3e8482bc59fcaa044dfe7f7ca507edabdd569d217635e595"


def verify(root: Path, manifest: Path, expected_count: int = 288,
           *, expected_manifest_sha256: str = ORIGINAL_MANIFEST_SHA256) -> dict:
    root = root.resolve(strict=True)
    raw = manifest.read_bytes()
    manifest_sha256 = hashlib.sha256(raw).hexdigest()
    if manifest_sha256 != expected_manifest_sha256:
        raise ValueError("Frozen E1 manifest fingerprint mismatch")
    files = json.loads(raw)["files"]
    if not isinstance(files, dict) or len(files) != expected_count:
        raise ValueError("Unexpected frozen E1 manifest file count")
    allowed_results = {"llm", "models", "parser_cache", "parser_ollama_test",
                       "parser_ollama_test_interrupted", "rule"}
    allowed_data = {"parser_dev.jsonl", "parser_manifest.json", "parser_test.jsonl",
                    "preprocessing-log.json", "preprocessing-replay-log.json",
                    "processed.json", "processed.sha256", "smoke_fixture.json"}
    targets = []
    # Validate the entire inventory before opening any evidence file.
    for name, expected in files.items():
        path = PurePosixPath(name)
        parts = path.parts
        if ("\\" in name or ":" in name or path.is_absolute() or ".." in parts
                or len(parts) < 3 or parts[0] != "cmp9500-recommender"):
            raise ValueError("Unsafe manifest path")
        rel = parts[1:]
        allowed = ((len(rel) == 2 and rel[0] == "data" and rel[1] in allowed_data)
                   or (len(rel) >= 3 and rel[0] == "results" and rel[1] in allowed_results))
        if not allowed or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Unexpected path or digest outside the frozen E1 inventory")
        target = root.joinpath(*rel).resolve()
        if not target.is_relative_to(root) or target != root.joinpath(*rel):
            raise ValueError("Manifest target escapes its declared E1 path")
        targets.append((target, expected))
    missing = mismatched = matched = 0
    for target, expected in targets:
        if not target.is_file():
            missing += 1
            continue
        with target.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual == expected:
            matched += 1
        else:
            mismatched += 1
    return {"status": "passed" if matched == expected_count else "failed",
            "manifest_sha256": manifest_sha256,
            "expected": expected_count, "matched": matched,
            "missing": missing, "mismatched": mismatched,
            "scope": "E1 byte hashes only; no evidence parsing or experiment execution"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_root", type=Path)
    args = parser.parse_args()
    result = verify(args.archive_root,
                    args.archive_root / "results/audit_revision/frozen-input-manifest.json")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
