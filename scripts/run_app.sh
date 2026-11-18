#!/usr/bin/env bash
# LEGACY / REPRODUCTION launcher: the historical port-8000 API (feedctrl.api:app) without the Lab.
# It does not mount the Feed Control Lab. The canonical application is run-app.cmd, which runs
# scripts/run_app.py on http://127.0.0.1:8765 (python scripts/run_app.py on any system).
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'Follow README.md: python3.12 -m venv .venv, then install the CPU PyTorch wheel and .venv/bin/python -m pip install -e ".[test]".'
  exit 1
fi
if [[ ! -f web/dist/index.html ]]; then
  (cd web && npm ci && npm run build)
fi
echo 'LEGACY launcher: historical API on port 8000 without the Lab. For the current app run: .venv/bin/python scripts/run_app.py (port 8765).' >&2
exec .venv/bin/python -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000
