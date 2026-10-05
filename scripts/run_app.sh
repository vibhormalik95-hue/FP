#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'Follow README.md: python3.12 -m venv .venv, then install the CPU PyTorch wheel and .venv/bin/python -m pip install -e ".[test,analysis]".'
  exit 1
fi
if [[ ! -f web/dist/index.html ]]; then
  (cd web && npm ci && npm run build)
fi
exec .venv/bin/python -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000
