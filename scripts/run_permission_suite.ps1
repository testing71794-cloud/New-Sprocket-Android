# Run PM_01–PM_30 permission flows sequentially with fresh app state per test.
# Each flow starts with launchApp clearState: true; adb pm clear adds a clean baseline.
param(
    [string]$Device = "ZA222RFQ75",
    [int[]]$Skip = @()
)

$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$maestro = "C:\Users\HP\maestro\maestro\bin\maestro.bat"
$permDir = Join-Path $PSScriptRoot "..\ATP TestCase Flows\permission"
$logDir = Join-Path $PSScriptRoot "..\logs\permission-suite"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$flows = Get-ChildItem -Path $permDir -Filter "PM_*.yaml" |
    Where-Object { $_.Name -match '^PM_\d{2} ' } |
    Sort-Object Name

$results = @()
foreach ($flow in $flows) {
    if ($flow.BaseName -match 'PM_(\d+)' -and $Skip -contains [int]$Matches[1]) {
        Write-Host "SKIP $($flow.Name)" -ForegroundColor Yellow
        continue
    }
    Write-Host "`n========== $($flow.Name) ==========" -ForegroundColor Cyan
    & $adb -s $Device shell pm clear com.hp.impulse.sprocket | Out-Null
    Start-Sleep -Seconds 1
    $outFile = Join-Path $logDir ($flow.BaseName + ".log")
    & $maestro --device $Device test $flow.FullName 2>&1 | Tee-Object -FilePath $outFile
    $exit = $LASTEXITCODE
    $status = if ($exit -eq 0) { "PASS" } else { "FAIL" }
    $results += [pscustomobject]@{ Flow = $flow.Name; Status = $status; Exit = $exit }
    Write-Host "$status $($flow.Name)" -ForegroundColor $(if ($status -eq "PASS") { "Green" } else { "Red" })
}

Write-Host "`n========== SUMMARY =========="
$results | Format-Table -AutoSize
$fail = ($results | Where-Object Status -eq "FAIL").Count
Write-Host "Passed: $($results.Count - $fail) / $($results.Count)  Failed: $fail"
if ($fail -gt 0) { exit 1 }
