@echo off
rem Start Feed Control Studio at http://127.0.0.1:8765/ and open the browser.
rem Paste your API key into the page, or set ANTHROPIC_API_KEY before running.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call studio-setup.cmd || exit /b 1
".venv\Scripts\python.exe" -m studio %*
