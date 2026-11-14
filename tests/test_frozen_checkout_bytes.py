"""Frozen validation inputs must retain their committed bytes on every OS."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import pytest

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "tools/hosted_validation_current/inputs"
PIN = "e4e36c14e3947324e1f34458f49df432130c7b5904aefda672953daabbb91655"

def driver():
    spec = importlib.util.spec_from_file_location("frozen_checkout_driver", ROOT / "tools/hosted_validation_current/driver.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_original_manifest_and_all_input_bytes():
    raw = (INPUTS / "MANIFEST.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PIN
    for name, expected in json.loads(raw).items():
        data = (INPUTS / name).read_bytes()
        assert len(data) == expected["bytes"], name
        assert hashlib.sha256(data).hexdigest() == expected["sha256"], name

@pytest.mark.parametrize("scenario", ["category", "indirect"])
def test_inert_original_input_loader(scenario):
    module = driver()
    assert module.INPUT_MANIFEST_SHA256 == PIN
    assert module.load_inputs(INPUTS, scenario)["rows"]

def test_input_drift_still_rejected(tmp_path):
    target = tmp_path / "inputs"
    shutil.copytree(INPUTS, target)
    path = target / "01-category-discovery/metadata.csv"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Input drift"):
        driver().load_inputs(target, "category")
