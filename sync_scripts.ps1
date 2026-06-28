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

$destDir = Join-Path $root "scripts"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null

foreach ($path in $files) {
    $relative = $path -replace '^scripts/', ''
    $dest = Join-Path $destDir $relative
    $parent = Split-Path -Parent $dest
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $content = git show "${branch}:${path}"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($dest, $content, $utf8NoBom)
}

Write-Host "Synced $($files.Count) file(s) from '$branch' into scripts/ (not staged)."
