@echo off
rem Run every test suite, the browser flows and every workflow end to end.
rem Writes runs\all-tests-<UTC>\summary.md and summary.json. No key needed (mock provider).
rem With a model: run-all-tests.cmd --provider openai --model gpt-5-mini
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First install: py -3.12 -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -e ".[test,recommender,providers]"
  exit /b 1
)
if not exist "node_modules\playwright" call npm install --no-save --no-audit --no-fund playwright@1.56.1
if not exist "web\node_modules" (pushd web & call npm ci & popd)
if not exist "web\dist\index.html" (pushd web & call npm run build & popd)
".venv\Scripts\python.exe" scripts\run_all_tests.py %*
exit /b %ERRORLEVEL%
