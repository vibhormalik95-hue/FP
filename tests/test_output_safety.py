"""Regression checks for CLI paths that previously overwrote frozen evidence."""
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import fetch_data, run_pipeline, train, benchmark_base, generate_explanations
from scripts.output_safety import require_new_output


def arguments(**changes):
    values = dict(output=None, data=None, models=None, fixture=False,
                  skip_data=False, skip_train=False, seeds=[42])
    values.update(changes)
    return Namespace(**values)


def test_default_full_run_keeps_new_data_and_models_under_new_output(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pipeline, 'ROOT', tmp_path)
    args = arguments()
    out = run_pipeline.configure_paths(args)
    assert Path(args.data) == out / 'data/processed.json'
    assert Path(args.models) == out / 'models'
    assert not out.exists()  # Preflight creates nothing.


def test_replay_reads_frozen_inputs_without_rewriting_them(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pipeline, 'ROOT', tmp_path)
    frozen_data = tmp_path / 'data/processed.json'
    frozen_model = tmp_path / 'results/models/seed_42/model.pt'
    frozen_data.parent.mkdir(parents=True)
    frozen_model.parent.mkdir(parents=True)
    frozen_data.write_bytes(b'frozen-data')
    frozen_model.write_bytes(b'frozen-model')
    args = arguments(skip_data=True, skip_train=True)
    run_pipeline.configure_paths(args)
    assert Path(args.data) == frozen_data
    assert Path(args.models) == frozen_model.parent.parent
    assert frozen_data.read_bytes() == b'frozen-data'
    assert frozen_model.read_bytes() == b'frozen-model'


@pytest.mark.parametrize('destination,is_directory', [
    ('data/processed.json', False), ('results/models/seed_99', True),
    ('results/rule/new-seed', True), ('results/llm/new-record.json', False),
])
def test_protected_paths_rejected_even_if_missing(tmp_path, destination, is_directory):
    with pytest.raises(ValueError, match='Protected frozen'):
        require_new_output(destination, tmp_path, directory=is_directory)
    assert not (tmp_path / destination).exists()


def test_existing_nonempty_outputs_are_preserved_and_new_empty_directory_allowed(tmp_path):
    existing = tmp_path / 'my-run'
    existing.mkdir()
    assert require_new_output(existing, tmp_path, directory=True) == existing
    record = existing / 'result.json'
    record.write_bytes(b'preserve')
    with pytest.raises(ValueError, match='already exists'):
        require_new_output(existing, tmp_path, directory=True)
    with pytest.raises(ValueError, match='already exists'):
        require_new_output(record, tmp_path, directory=False)
    assert record.read_bytes() == b'preserve'


@pytest.mark.parametrize('module,argv,expensive_function', [
    (fetch_data, ['--output', 'data/processed.json'], 'preprocess_kuairec'),
    (train, ['--output', 'results/models'], 'load_data'),
    (benchmark_base, ['--output', 'results/base-quality.json'], 'load_data'),
    (generate_explanations, ['--output', 'results/explanations.json'], 'load_model'),
])
def test_cli_rejects_overwrite_before_data_or_model_work(tmp_path, monkeypatch, module, argv, expensive_function):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    target = tmp_path / argv[1]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix:
        target.write_bytes(b'preserve')
    else:
        target.mkdir()
    work = Mock(side_effect=AssertionError('Should never execute'))
    monkeypatch.setattr(module, expensive_function, work)
    monkeypatch.setattr('sys.argv', [str(module.__file__), *argv])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2
    work.assert_not_called()


def test_pipeline_rejects_frozen_output_before_external_calls(monkeypatch):
    run = Mock(side_effect=AssertionError('Should never execute'))
    monkeypatch.setattr(run_pipeline.subprocess, 'run', run)
    monkeypatch.setattr('sys.argv', [str(run_pipeline.__file__), '--output', 'results/llm'])
    with pytest.raises(SystemExit) as error:
        run_pipeline.main()
    assert error.value.code == 2
    run.assert_not_called()


def test_duplicate_seed_cannot_overwrite_checkpoint_in_same_new_run(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pipeline, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='unique'):
        run_pipeline.configure_paths(arguments(seeds=[42, 42]))
