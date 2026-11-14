"""Audit guards must protect their own tests without leaking into other modules."""
import importlib

import pytest


@pytest.mark.parametrize("name", [
    "test_review_timeout_regression_offline",
    "test_prompt_contract_regression_offline",
    "test_scaffold_binding_regression_offline",
    "test_structural_reference_regression_offline",
])
def test_audit_guard_is_scoped_and_still_blocks_forbidden_operations(name):
    module = importlib.import_module(name)
    assert module.guard_active is False
    module.guard("socket.__new__", ())
    assert module.events == []
    module.setUpModule()
    try:
        for event in ("socket.__new__", "subprocess.Popen", "os.system", "ctypes.dlopen"):
            with pytest.raises(RuntimeError):
                module.guard(event, ())
            assert module.events == [event]
            module.events.clear()  # These are deliberately tested guard rejections.
    finally:
        module.tearDownModule()
    assert module.guard_active is False
    module.guard("socket.__new__", ())
    assert module.events == []
