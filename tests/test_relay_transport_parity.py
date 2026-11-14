"""Offline parity between relay preflight and the application JSON transport."""
import importlib.util
import json
from pathlib import Path
import pytest
from feedctrl.model_adapters import _decode
from feedctrl.indirect_grounding import _response_snapshot

spec = importlib.util.spec_from_file_location("relay_parity_tools", Path(__file__).resolve().parents[1] / "scripts" / "relay_tools.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

@pytest.mark.parametrize("raw", [
    b'{"value":1,"value":2}',
    b'{"outer":{"value":1,"value":2}}',
    b'{"value":NaN}', b'{"value":Infinity}', b'{"value":-Infinity}',
    b'{"value":1e400}',
    b'{"value":"\\ud800"}',
    b'{"value":' + b'[' * 66 + b'0' + b']' * 66 + b'}',
])
def test_helper_rejects_same_invalid_transport_as_app(tmp_path, raw):
    (tmp_path / 'request-0001.json').write_text(json.dumps({'schema': {'type':'object'}}), encoding='utf-8')
    with pytest.raises((ValueError, RecursionError, UnicodeError)):
        _response_snapshot(_decode(raw.decode('utf-8-sig')))
    assert helper.problem(tmp_path, 1, raw) is not None
    answer = tmp_path / 'answer.json'
    answer.write_bytes(raw)
    with pytest.raises(SystemExit, match='NOT DELIVERED'):
        helper.deliver(tmp_path, 1, answer)
    assert not (tmp_path / 'response-0001.json').exists()

@pytest.mark.parametrize("raw", [b'{"value":1.25}', b'\xef\xbb\xbf{ "value": "ok" }\r\n'])
def test_helper_accepts_finite_json_without_altering_bytes(tmp_path, raw):
    (tmp_path / 'request-0001.json').write_text(json.dumps({'schema': {'type':'object'}}), encoding='utf-8')
    assert helper.problem(tmp_path, 1, raw) is None
    answer = tmp_path / 'answer.json'
    answer.write_bytes(raw)
    helper.deliver(tmp_path, 1, answer)
    assert (tmp_path / 'response-0001.json').read_bytes() == raw
