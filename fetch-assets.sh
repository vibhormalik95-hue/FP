#!/usr/bin/env sh
# Download the KuaiRec assets (CC BY-SA 4.0) from the GitHub Release and verify every SHA-256.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then exec .venv/bin/python scripts/fetch_assets.py "$@"; fi
exec python3 scripts/fetch_assets.py "$@"
