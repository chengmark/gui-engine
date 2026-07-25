# Build gui.py into a Windows .exe with PyInstaller.
# Usage: .\build_exe.ps1
# Output: dist\gui-engine\gui-engine.exe  (plus a scripts\ folder beside it)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -q -r requirements.txt pyinstaller

$collect = @(
    "--collect-all", "pydivert",
    "--collect-all", "pycaw",
    "--collect-all", "comtypes"
)

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "gui-engine" `
    --onedir `
    --paths "." `
    --hidden-import "run" `
    --hidden-import "record" `
    --hidden-import "coord_helper" `
    --hidden-import "limit_download" `
    --hidden-import "runner" `
    --hidden-import "runner.cli" `
    --hidden-import "runner.engine" `
    --hidden-import "runner.background" `
    --hidden-import "runner.script_io" `
    --hidden-import "runner.subroutines" `
    --hidden-import "runner.triggers" `
    --hidden-import "runner.mouse" `
    --hidden-import "runner.volume" `
    --hidden-import "runner.state" `
    --hidden-import "runner.utils" `
    --hidden-import "runner.constants" `
    --hidden-import "handlers" `
    --hidden-import "handlers.script" `
    --hidden-import "handlers.import_script" `
    --hidden-import "handlers.delay" `
    --hidden-import "handlers.key_down" `
    --hidden-import "handlers.key_up" `
    --hidden-import "handlers.key_press" `
    --hidden-import "handlers.key_hold_and_release" `
    --hidden-import "handlers.mouse_click" `
    --hidden-import "handlers.mouse_move" `
    --hidden-import "handlers.mouse_move_to" `
    --hidden-import "handlers.click_on" `
    --hidden-import "handlers.set_volume" `
    --hidden-import "handlers.toggle_mute" `
    --hidden-import "gui.services" `
    --hidden-import "gui.toast" `
    --hidden-import "keyboard" `
    --hidden-import "pynput" `
    --hidden-import "psutil" `
    --hidden-import "pydivert" `
    @collect `
    gui.py

$scriptsOut = Join-Path $PSScriptRoot "dist\gui-engine\scripts"
if (-not (Test-Path $scriptsOut)) {
    New-Item -ItemType Directory -Path $scriptsOut | Out-Null
}

# Copy local scripts into the dist folder if present
$scriptsSrc = Join-Path $PSScriptRoot "scripts"
if (Test-Path $scriptsSrc) {
    Copy-Item -Path (Join-Path $scriptsSrc "*") -Destination $scriptsOut -Recurse -Force
}

Write-Host ""
Write-Host "Built: dist\gui-engine\gui-engine.exe"
Write-Host "Put JSON scripts in: dist\gui-engine\scripts\"
