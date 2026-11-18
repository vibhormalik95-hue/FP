# LEGACY / REPRODUCTION launcher: the historical port-8000 API (feedctrl.api:app) without the Lab.
# It does not mount the Feed Control Lab. The canonical application is run-app.cmd, which runs
# scripts/run_app.py on http://127.0.0.1:8765 (python scripts/run_app.py on any system).
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$AppPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $AppPython)) {
    throw 'Follow the Python 3.12 installation steps in docs/windows-and-colab.md: py -3.12 -m venv .venv, then install the CPU PyTorch wheel and pip install -e ".[test]" using .venv\Scripts\python.exe.'
}
if (-not (Test-Path 'web\dist\index.html')) {
    Push-Location web
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    } finally { Pop-Location }
}
Write-Host 'LEGACY launcher: historical API on port 8000 without the Lab. For the current app use run-app.cmd (scripts/run_app.py, port 8765).'
& $AppPython -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
