"""R6 findings E1a-E1c: the legacy launchers say that they are legacy and name the canonical Lab.

The canonical application is run-app.cmd -> scripts/run_app.py on 127.0.0.1:8765. Studio is not
restored; no launcher may point to its absent recovery path (run-studio.cmd, docs/studio-guide.md).
"""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import quickstart  # noqa: E402
import run_demo  # noqa: E402

STUDIO = ('run-studio', 'studio-guide', 'Feed Control Studio', 'python -m studio')


def text(name):
    return (ROOT / 'scripts' / name).read_text(encoding='utf-8')


def test_e1a_no_launcher_points_to_the_absent_studio_recovery_path():
    assert not (ROOT / 'run-studio.cmd').exists() and not (ROOT / 'docs' / 'studio-guide.md').exists()
    for name in ('quickstart.py', 'run_demo.py'):
        source = text(name)
        assert not [mark for mark in STUDIO if mark in source], name
        assert 'scripts/run_app.py' in source and '8765' in source and 'LEGACY' in source, name
    # The first paragraph is the --help description of both programs.
    assert quickstart.__doc__.startswith('LEGACY / REPRODUCTION') and run_demo.__doc__.startswith('LEGACY / REPRODUCTION')


def test_e1a_the_manual_step_prints_the_canonical_lab(monkeypatch, capsys):
    class Server:
        def poll(self):
            return None
    monkeypatch.setattr(quickstart, 'require_free_port', lambda port: None)
    monkeypatch.setattr(quickstart, 'run_demo', lambda *args: Server())
    monkeypatch.setattr(quickstart, 'wait_until_served', lambda port, server: None)
    monkeypatch.setattr(quickstart, 'serve_until_stopped', lambda server: None)
    monkeypatch.setattr(quickstart, 'stop_server', lambda server: None)
    quickstart.manual(type('A', (), {'port': 8123, 'scenario': 'tags'})())
    out = capsys.readouterr().out
    assert 'run-app.cmd' in out and '8765' in out and 'Studio' not in out and 'run-studio' not in out


def test_e1b_personal_cli_is_labelled_retired_and_refused_with_the_canonical_lab():
    doc = run_demo.__doc__
    assert '--provider personal-cli --reviewed-config' not in doc        # no longer advertised as an example
    assert 'personal-cli  RETIRED' in doc
    with pytest.raises(SystemExit) as stopped:
        run_demo.main(['--provider', 'personal-cli', '--scenario', 'category'])
    message = str(stopped.value.code)
    assert 'retired' in message and 'scripts/run_app.py' in message and 'studio' not in message.lower()


@pytest.mark.parametrize('name', ['run_app.ps1', 'run_app.sh'])
def test_e1c_the_port_8000_launchers_are_labelled_legacy_and_name_run_app(name):
    source = text(name)
    head = source.split('\n')[:5]
    assert any('LEGACY' in line and 'port-8000' in line for line in head)
    assert 'mount the Feed Control Lab' in source and 'run-app.cmd' in source and 'scripts/run_app.py' in source
    # The notice is printed before the legacy server starts, not only kept in a comment.
    notice = next(i for i, line in enumerate(source.split('\n')) if line.startswith(('Write-Host', 'echo')) and 'LEGACY' in line)
    start = next(i for i, line in enumerate(source.split('\n')) if 'uvicorn feedctrl.api:app' in line)
    assert notice < start
