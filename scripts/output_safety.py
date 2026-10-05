"""Output guards for new experiments; delivered research records are read-only."""
from pathlib import Path


def project_path(path: str | Path, root: Path) -> Path:
    path = Path(path)
    return (path if path.is_absolute() else root / path).resolve()


def require_new_output(path: str | Path, root: Path, *, directory: bool) -> Path:
    """Reject frozen destinations and existing outputs before expensive work.

    An existing empty directory may be used, but no nonempty run/model directory
    or existing data file is overwritten. There is deliberately no force flag.
    """
    target = project_path(path, root)
    frozen_file = (root / "data/processed.json").resolve()
    frozen_dirs = [(root / "results" / name).resolve() for name in ("models", "rule", "llm")]
    if target == frozen_file or any(target == base or target.is_relative_to(base) for base in frozen_dirs):
        raise ValueError(f"Protected frozen evidence destination: {target}; choose a new experiment path")
    if target.exists():
        if not directory or not target.is_dir() or any(target.iterdir()):
            raise ValueError(f"Output already exists: {target}; choose a new experiment path")
    return target
