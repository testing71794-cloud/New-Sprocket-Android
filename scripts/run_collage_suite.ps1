# Run Collage ATP flows from atp_collage_mapping.csv (Excel sheet order).
# CLI: maestro --device SERIAL test --debug-output PATH FLOW
# See: https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options
param(
    [string]$Device = "16091FDD4004N6",
    [string[]]$Skip = @()
)

$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$maestro = "C:\Users\HP\maestro\maestro\bin\maestro.bat"
$pkg = "com.caglobal.hp.sprocket"
$repoRoot = Split-Path $PSScriptRoot -Parent
$collageDir = Join-Path $repoRoot "ATP TestCase Flows\collage"
$mapping = Join-Path $collageDir "atp_collage_mapping.csv"
$logDir = Join-Path $repoRoot "logs\collage-suite"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $mapping)) {
    Write-Error "Missing mapping: $mapping"
    exit 1
}

$rows = Import-Csv $mapping
$flows = @()
foreach ($row in $rows) {
    $rel = ($row.FlowFile -replace '/', '\').Trim()
    if (-not $rel) { continue }
    $full = Join-Path $repoRoot "ATP TestCase Flows\$rel"
    if (-not (Test-Path $full)) {
        $full = Join-Path $repoRoot $rel
    }
    if (-not (Test-Path $full)) {
        Write-Warning "Missing flow: $rel"
        continue
    }
    $flows += [pscustomobject]@{ Id = $row.TestCaseID; Path = $full; Name = Split-Path $full -Leaf }
}

$results = @()
foreach ($flow in $flows) {
    if ($Skip -contains $flow.Id) {
        Write-Host "SKIP $($flow.Id) $($flow.Name)" -ForegroundColor Yellow
        continue
    }
    Write-Host "`n========== $($flow.Id) $($flow.Name) ==========" -ForegroundColor Cyan
    $outFile = Join-Path $logDir ($flow.Name + ".log")
    & $maestro --no-ansi --device $Device test --debug-output $logDir $flow.Path 2>&1 |
        Tee-Object -FilePath $outFile
    $exit = $LASTEXITCODE
    $status = if ($exit -eq 0) { "PASS" } else { "FAIL" }
    $results += [pscustomobject]@{ Id = $flow.Id; Flow = $flow.Name; Status = $status; Exit = $exit }
    Write-Host "$status $($flow.Id)" -ForegroundColor $(if ($status -eq "PASS") { "Green" } else { "Red" })
}

Write-Host "`n========== SUMMARY =========="
$results | Format-Table -AutoSize
$pass = @($results | Where-Object Status -eq "PASS").Count
$fail = @($results | Where-Object Status -eq "FAIL").Count
Write-Host "Passed: $pass / $($results.Count)  Failed: $fail"
$summaryCsv = Join-Path $logDir "last_run_summary.csv"
$results | Export-Csv -Path $summaryCsv -NoTypeInformation
Write-Host "Summary CSV: $summaryCsv"
if ($fail -gt 0) { exit 1 }
