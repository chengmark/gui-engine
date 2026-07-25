# Copy scripts/ from the scripts branch into the working tree without staging them.
# Safe to run on main: files stay gitignored and are not added to the index.

$ErrorActionPreference = "Stop"
$branch = "scripts"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (git rev-parse --verify "$branch^{commit}" 2>$null)) {
    Write-Error "Branch '$branch' not found. Fetch or create it first."
}

$files = git ls-tree -r --name-only $branch -- scripts/
if (-not $files) {
    Write-Error "No files under scripts/ on branch '$branch'."
}

# Use git archive so UTF-8 bytes are preserved (git show via PowerShell corrupts CJK text).
$zipPath = Join-Path ([System.IO.Path]::GetTempPath()) "gui-engine-scripts-sync.zip"
try {
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    git archive --format=zip -o $zipPath $branch scripts
    Expand-Archive -Path $zipPath -DestinationPath $root -Force
}
finally {
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
}

Write-Host "Synced $($files.Count) file(s) from '$branch' into scripts/ (not staged)."
