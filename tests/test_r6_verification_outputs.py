"""R6 findings E5 and D4a-D4c: safe prospective outputs, and scripts that cannot exit 0 after a failed check.

No server, no model, no process of the experiment: the HTTP calls of the reproduction scripts go to a
fake opener, and the stages of the verification sequence to a fake subprocess.run.
"""
import importlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.output_safety import require_new_output  # noqa: E402


# ---------------------------------------------------------------- E5
def test_e5_every_prospective_output_is_new_and_allowed_and_no_old_receipt_is_written(tmp_path, monkeypatch):
    import run_llm_verification as verification
    commands = []
    monkeypatch.setattr(verification.subprocess, 'run',
                        lambda command, **kwargs: commands.append(command) or subprocess.CompletedProcess(command, 0))
    root = tmp_path / 'llm-verification-new'
    assert verification.main(['--output-root', str(root)]) == 0
    assert len(commands) == 4
    outputs = [Path(command[command.index('--output') + 1]) for command in commands if '--output' in command]
    assert len(outputs) == 4 and all(path.is_relative_to(root) for path in outputs)
    results = (ROOT / 'results').resolve()
    assert not any(str(part).startswith(str(results)) for command in commands for part in command)
    for path in outputs:                                 # each one is a path that output_safety accepts
        require_new_output(path, ROOT, directory=path.suffix != '.json')
    assert json.loads((root / 'stage-status.json').read_text())[-1]['stage'] == 'explanation_sample'
    # The default is a fresh folder under runs/, never results/llm.
    default = verification.stages(Path('runs/llm-verification-x'))
    assert all('results/llm' not in ' '.join(command) for _, command in default)
    with pytest.raises(ValueError, match='Protected frozen'):
        require_new_output('results/llm', ROOT, directory=True)
    # An existing output root is refused before any stage runs.
    commands.clear()
    with pytest.raises(ValueError, match='already exists'):
        (root / 'x').mkdir(exist_ok=True)
        verification.main(['--output-root', str(root)])
    assert commands == []


# ---------------------------------------------------------------- D4a and D4b
class FakeOpener:
    """Answers every call of a reproduction script with a fixed body; nothing listens anywhere."""

    def __init__(self, answers):
        self.answers = answers

    def open(self, request, timeout=None):
        path = request.full_url.split('127.0.0.1:9', 1)[1]
        body = next((value for prefix, value in self.answers if path.startswith(prefix)), {})
        response = io.BytesIO(json.dumps(body).encode())
        response.status = 200
        return response


def _install(monkeypatch, module, answers):
    monkeypatch.setattr(module.urllib.request, 'build_opener', lambda *args: FakeOpener(answers))


ANSWERS = [('/api/session', {'session_id': 's'}), ('/api/steering/preview', {'ready': False}),
           ('/api/steering?', {'commands': [], 'can_undo': False})]


def test_d4a_the_dialogue_audit_exits_1_when_a_check_fails(tmp_path, monkeypatch, capsys):
    module = importlib.import_module('reproduce_dialogue_steering')
    _install(monkeypatch, module, ANSWERS)
    output = tmp_path / 'dialogue.json'
    assert module.main(['http://127.0.0.1:9', str(output)]) == 1
    record = json.loads(output.read_text())
    assert record['all_checks_passed'] is False and record['failed_checks']
    assert 'confirmed_english_light_qingdao.interpretation_matches_expected' in record['failed_checks']
    assert module.failed_checks({'cases': [{'name': 'a', 'fixed_ae_unchanged': True}], 'comparisons': {'x': True}}) == []


def test_d4b_the_reviewed_smokes_exit_1_when_a_check_fails(tmp_path, monkeypatch):
    module = importlib.import_module('reproduce_reviewed_steering')
    _install(monkeypatch, module, ANSWERS)
    output = tmp_path / 'reviewed.json'
    assert module.main(['http://127.0.0.1:9', str(output)]) == 1
    record = json.loads(output.read_text())
    assert 'manual_equals_live_english' in record['failed_checks'] and record['all_checks_passed'] is False
    assert module.failed_checks({key: True for key in module.SUMMARY_CHECKS}) == []


# ---------------------------------------------------------------- D4c
@pytest.mark.skipif(shutil.which('node') is None, reason='needs Node.js to run the video-save block of demo_flows.cjs')
def test_d4c_a_failed_requested_video_save_ends_with_a_nonzero_exit_code(tmp_path):
    source = (ROOT / 'tests' / 'browser' / 'demo_flows.cjs').read_text(encoding='utf-8')
    match = re.search(r'\n    if \(VIDEO\) \{\n      // The recording is complete.*?\n      save\(\);\n    \}\n', source, re.S)
    assert match, 'the video-save block of demo_flows.cjs was not found'
    harness = ("const path = require('path');\n"
               "const fs = { renameSync() { throw new Error('disk full'); } };\n"
               "const VIDEO = true, OUT = 'out', SCENARIO = 'tags';\n"
               "const receipt = { outcome: 'all flows completed', video: { file: null, steps: [] } };\n"
               "const page = { video() { return { path: async () => 'recorded.webm' }; } };\n"
               "const context = { close: async () => {} };\n"
               "function save() {}\n"
               "(async () => {\n" + match.group(0) + "\n"
               "  console.log(JSON.stringify({ code: process.exitCode === undefined ? null : process.exitCode, receipt }));\n"
               "})();\n")
    script = tmp_path / 'video_block.cjs'
    script.write_text(harness, encoding='utf-8')
    done = subprocess.run(['node', str(script)], capture_output=True, text=True, timeout=60)
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result['receipt']['video']['error'] == 'disk full' and result['receipt']['video']['file'] is None
    assert result['code'] == 3 and done.returncode == 3
    assert 'video was not saved' in result['receipt']['outcome']
