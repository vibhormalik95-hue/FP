@echo off
rem Download the KuaiRec assets (CC BY-SA 4.0) from the GitHub Release and verify every SHA-256.
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\fetch_assets.py %*
) else (
  py -3 scripts\fetch_assets.py %*
)
exit /b %ERRORLEVEL%
