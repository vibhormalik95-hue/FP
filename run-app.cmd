@echo off
rem Start the Feed Control Lab on real KuaiRec (A to E study view + language controls).
rem Usage: run-app.cmd [--provider openai --model gpt-5-mini]
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First install: py -3.12 -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -e ".[test,recommender,providers]"
  exit /b 1
)
if not exist "web\dist\index.html" (
  pushd web & call npm ci & call npm run build & popd
)
".venv\Scripts\python.exe" scripts\run_app.py %*
exit /b %ERRORLEVEL%
