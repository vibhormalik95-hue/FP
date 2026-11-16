@echo off
rem End-to-end test of every workflow. With no arguments it uses the mock provider (no key, no cost).
rem   studio-test.cmd --provider anthropic --model claude-sonnet-5-5
rem Results go to studio-results\<date-time>-<provider>-<model>\ (summary.md, results.json, calls.csv).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call studio-setup.cmd || exit /b 1
".venv\Scripts\python.exe" -m studio.cli %*
