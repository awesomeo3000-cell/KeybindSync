param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$repoPrefix = $repo.TrimEnd('\') + '\'
$baseline = Join-Path $PSScriptRoot "cleanup-baseline-20260803"
$files = @(
    "README.md",
    "CHANGELOG.md",
    "src\wow_keybind_app.py",
    "src\wow_keybind_sync.py",
    "tests\test_numpad_keys.py",
    "tests\test_process_safety.py"
)

foreach ($relative in $files) {
    $source = Join-Path $baseline $relative
    $destination = Join-Path $repo $relative
    $destinationParent = (Resolve-Path -LiteralPath (Split-Path -Parent $destination)).Path
    if (-not $destinationParent.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase) -and $destinationParent -ne $repo) {
        throw "Rollback destination escaped RepoRoot: $destination"
    }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing preserved baseline: $source"
    }
    Copy-Item -LiteralPath $source -Destination $destination -Force
    $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    $destinationHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
    if ($sourceHash -ne $destinationHash) {
        throw "Rollback verification failed for $relative"
    }
    Write-Output "RESTORED $relative SHA256=$destinationHash"
}

$newTest = Join-Path $repo "tests\test_cleanup.py"
if (Test-Path -LiteralPath $newTest -PathType Leaf) {
    Remove-Item -LiteralPath $newTest -Force
}
if (Test-Path -LiteralPath $newTest) {
    throw "Rollback verification failed: $newTest still exists"
}
Write-Output "REMOVED tests\test_cleanup.py"
Write-Output "Rollback verified for $repo"
