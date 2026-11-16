@echo off
rem One-time setup: creates .venv and installs the Studio. Needs Python 3.11+ on PATH.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment in .venv ...
  python -m venv .venv || (echo Python 3.11 or newer is required. & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -e ".[studio,test]" || exit /b 1
echo Setup complete. Start the app with run-studio.cmd
