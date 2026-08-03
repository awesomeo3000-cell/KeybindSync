param([string]$RepoPath = (Join-Path $PSScriptRoot '..'))
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $RepoPath).Path
$source = Join-Path $PSScriptRoot 'global-alias-baseline-20260803'
$files = @('src\wow_keybind_app.py','src\wow_keybind_sync.py','tests\test_cleanup.py','README.md','CHANGELOG.md')
foreach ($relative in $files) {
    $src = Join-Path $source $relative
    $dst = Join-Path $repo $relative
    if (-not (Test-Path -LiteralPath $src)) { throw "Rollback source missing: $src" }
    $parent = Split-Path -Parent $dst
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
Write-Output "Rolled back $($files.Count) files into $repo"
