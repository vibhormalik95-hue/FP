$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$AppPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $AppPython)) {
    throw 'Follow the Python 3.12 installation steps in README.md: py -3.12 -m venv .venv, then install the CPU PyTorch wheel and pip install -e ".[test,analysis]" using .venv\Scripts\python.exe.'
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
& $AppPython -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
