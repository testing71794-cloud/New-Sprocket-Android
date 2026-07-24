# Safe local disk cleanup for HP Sprocket / Maestro workstations.
# Does NOT delete Downloads, APKs you keep, or Jenkins job history unless -Aggressive.
param(
    [switch]$Aggressive,
    [switch]$WhatIf
)

$ErrorActionPreference = "Continue"
function GB([long]$b) { "{0:N2} GB" -f ($b / 1GB) }
function DirBytes([string]$p) {
    if (-not (Test-Path -LiteralPath $p)) { return 0L }
    $sum = 0L
    Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            if ($_.PSIsContainer) {
                $sum += [int64](Get-ChildItem $_.FullName -Recurse -Force -ErrorAction SilentlyContinue |
                    Measure-Object Length -Sum).Sum
            } else { $sum += [int64]$_.Length }
        } catch {}
    }
    return $sum
}

function Remove-PathSafe([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path)) { return 0L }
    $before = 0L
    try {
        if ((Get-Item -LiteralPath $Path -Force).PSIsContainer) {
            $before = [int64](Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
                Measure-Object Length -Sum).Sum
        } else {
            $before = [int64](Get-Item -LiteralPath $Path -Force).Length
        }
    } catch {}
    if ($WhatIf) {
        Write-Host ("[WhatIf] would remove {0}: {1}" -f $Label, (GB $before))
        return $before
    }
    try {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        Write-Host ("[ok] removed {0}: {1}" -f $Label, (GB $before))
        return $before
    } catch {
        Write-Host ("[warn] could not remove {0}: {1}" -f $Label, $_.Exception.Message)
        return 0L
    }
}

$cFreeBefore = (Get-PSDrive C).Free
Write-Host ("C: free before: {0}" -f (GB $cFreeBefore))
$freed = 0L

# --- Temp leftovers ---
$temp = $env:TEMP
$patterns = @('maestro*', '*.apk', 'adb-*', 'adb_out_*', 'adb_devices_*', '*instrument*', 'hsperfdata*', 'jna*', 'jansi*', 'Maestro*')
foreach ($pat in $patterns) {
    Get-ChildItem -LiteralPath $temp -Force -ErrorAction SilentlyContinue -Filter $pat | ForEach-Object {
        $freed += Remove-PathSafe $_.FullName ("Temp\" + $_.Name)
    }
}

# --- Maestro debug/tests older than 3 days (keep recent) ---
$maestroTests = Join-Path $env:USERPROFILE ".maestro\tests"
if (Test-Path $maestroTests) {
    $cutoff = (Get-Date).AddDays(-3)
    Get-ChildItem $maestroTests -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object { $freed += Remove-PathSafe $_.FullName (".maestro\tests\" + $_.Name) }
}

# --- Maestro apps cache (large APK copies; Maestro will re-fetch) ---
$maestroApps = Join-Path $env:USERPROFILE ".maestro\apps"
if ($Aggressive -and (Test-Path $maestroApps)) {
    $freed += Remove-PathSafe $maestroApps ".maestro\apps (Aggressive)"
}

# --- Repo generated noise ---
$repo = Split-Path $PSScriptRoot -Parent
$repoTargets = @(
    (Join-Path $repo ".video_frames_pm"),
    (Join-Path $repo "_archive6_extract"),
    (Join-Path $repo ".maestro-runtime"),
    (Join-Path $repo ".maestro-workspace")
)
foreach ($t in $repoTargets) {
    if (Test-Path $t) { $freed += Remove-PathSafe $t ("repo\" + (Split-Path $t -Leaf)) }
}

# Old module-run maestro-debug under reports (keep summaries/xlsx)
$reports = Join-Path $repo "reports"
if (Test-Path $reports) {
    Get-ChildItem $reports -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @('maestro-debug', 'startup-diagnostics', 'screenshots') } |
        ForEach-Object {
            $rel = $_.FullName.Substring($repo.Length).TrimStart('\')
            $freed += Remove-PathSafe $_.FullName $rel
        }
}

# Gradle caches (safe regenerable)
if ($Aggressive) {
    $gradleCaches = Join-Path $env:USERPROFILE ".gradle\caches"
    if (Test-Path $gradleCaches) {
        $freed += Remove-PathSafe $gradleCaches ".gradle\caches (Aggressive)"
    }
}

# Windows Delivery Optimization / thumbnail optional - skip

$cFreeAfter = (Get-PSDrive C).Free
Write-Host ""
Write-Host ("Approx removed this pass: {0}" -f (GB $freed))
Write-Host ("C: free after:  {0}  (delta +{1})" -f (GB $cFreeAfter), (GB ([math]::Max(0, $cFreeAfter - $cFreeBefore))))
Write-Host "Done. Downloads and Jenkins workspaces were left alone."
