import hashlib
import json

import pytest

from scripts.verify_frozen_e1 import verify


def inventory(tmp_path, entries):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": entries}), encoding="utf-8")
    return manifest


def verify_fixture(root, manifest, expected_count=288):
    # Explicit test seam: the production CLI always pins the original manifest.
    return verify(root, manifest, expected_count,
                  expected_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())


def test_matching_missing_and_changed_bytes(tmp_path):
    target = tmp_path / "data/processed.json"
    target.parent.mkdir()
    target.write_bytes(b"synthetic bytes, not research data")
    manifest = inventory(tmp_path, {
        "cmp9500-recommender/data/processed.json": hashlib.sha256(target.read_bytes()).hexdigest()
    })
    assert verify_fixture(tmp_path, manifest, 1)["matched"] == 1
    target.write_bytes(b"changed")
    assert verify_fixture(tmp_path, manifest, 1)["mismatched"] == 1
    target.unlink()
    assert verify_fixture(tmp_path, manifest, 1)["missing"] == 1


@pytest.mark.parametrize("name", [
    "cmp9500-recommender/results/experiment2/reserved.json",
    "cmp9500-recommender/../outside.json",
    "C:/outside.json",
    "cmp9500-recommender/data/processed.json:stream",
])
def test_rejects_unexpected_inventory_before_hashing(tmp_path, monkeypatch, name):
    target = tmp_path / "data/processed.json"
    target.parent.mkdir()
    target.write_bytes(b"synthetic fixture")
    manifest = inventory(tmp_path, {
        "cmp9500-recommender/data/processed.json": "0" * 64,
        name: "0" * 64,
    })
    def unexpected_hash(*args):
        pytest.fail("Evidence must not be hashed before all paths are validated")
    monkeypatch.setattr(hashlib, "file_digest", unexpected_hash)
    with pytest.raises(ValueError):
        verify_fixture(tmp_path, manifest, 2)


def test_requires_complete_expected_inventory(tmp_path):
    manifest = inventory(tmp_path, {})
    with pytest.raises(ValueError, match="file count"):
        verify_fixture(tmp_path, manifest)


def test_changed_manifest_rejected_before_parsing_or_hashing(tmp_path, monkeypatch):
    manifest = inventory(tmp_path, {})
    def unexpected_access(*args, **kwargs):
        pytest.fail("Changed manifest must be rejected before parsing or evidence hashing")
    monkeypatch.setattr(json, "loads", unexpected_access)
    monkeypatch.setattr(hashlib, "file_digest", unexpected_access)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        verify(tmp_path, manifest)
