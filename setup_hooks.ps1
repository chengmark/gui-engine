# One-time setup: use repo git hooks that protect scripts/ on main.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

git config core.hooksPath .githooks
Write-Host "Git hooks enabled from .githooks/ (core.hooksPath)."
