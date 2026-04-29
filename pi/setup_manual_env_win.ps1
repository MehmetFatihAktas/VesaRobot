$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$VenvDir = Join-Path $RepoRoot ".venv-manual-win"

if (-not (Test-Path $VenvDir)) {
    py -3 -m venv $VenvDir
}

$Python = Join-Path $VenvDir "Scripts\python.exe"

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $ScriptDir "requirements-manual-win.txt")

Write-Host "Windows manual control environment ready: $VenvDir"
