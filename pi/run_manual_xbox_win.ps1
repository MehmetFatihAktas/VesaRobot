$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$VenvDir = Join-Path $RepoRoot ".venv-manual-win"
$ProfilePath = Join-Path $ScriptDir "manual_profile.windows.json"

if (-not (Test-Path $VenvDir)) {
    & (Join-Path $ScriptDir "setup_manual_env_win.ps1")
}

if (-not (Test-Path $ProfilePath)) {
    Copy-Item (Join-Path $ScriptDir "manual_profile.windows.example.json") $ProfilePath
}

$Python = Join-Path $VenvDir "Scripts\python.exe"
$Port = $args[0]

if (-not $Port) {
    $portScript = @'
from serial.tools import list_ports
for port in list_ports.comports():
    if port.vid == 0x16C0 and port.pid == 0x0483:
        print(port.device)
        break
'@
    $Port = (& $Python -c $portScript).Trim()
}

if (-not $Port) {
    throw "Teensy COM port bulunamadi."
}

Write-Host "Using Teensy port: $Port"
Write-Host "Using profile: $ProfilePath"
& $Python (Join-Path $ScriptDir "manual_xbox_bridge_win.py") --port $Port --profile $ProfilePath
