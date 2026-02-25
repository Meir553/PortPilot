# Build PortPilot executable. Run from project root.
# Requires: venv with PySide6 (pip install -r requirements.txt)

$ErrorActionPreference = "Stop"
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$venvPip = Join-Path $PSScriptRoot ".venv\Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating venv..."
    python -m venv .venv
}
if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: .venv not found. Run: python -m venv .venv"
    exit 1
}

Write-Host "Installing dependencies..."
& $venvPip install -r requirements.txt -q
& $venvPip install pyinstaller Pillow -q

if ((Test-Path "scripts\build_icon.py") -and -not (Test-Path "assets\icon.ico")) {
    Write-Host "Generating icon (assets\icon.ico missing)..."
    & $venvPython scripts\build_icon.py
}

Write-Host "Building with PyInstaller..."
& $venvPython -m PyInstaller portpilot.spec

if (Test-Path "dist\PortPilot.exe") {
    Write-Host "Done: dist\PortPilot.exe"
} else {
    Write-Host "ERROR: Build failed"
    exit 1
}
