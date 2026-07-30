# Run PM_01–PM_07 permission flows with fresh app state per test.
param(
    [string]$Device = "ZA222RFQ75",
    [int[]]$Skip = @(),
    [ValidateSet('All', 'Positive', 'Negative', 'Mixed')]
    [string]$Mode = 'All'
)

$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$maestro = "C:\Users\HP\maestro\maestro\bin\maestro.bat"
$pkg = "com.hp.impulse.sprocket"
$permDir = Join-Path $PSScriptRoot "..\ATP TestCase Flows\permission"
$logDir = Join-Path $PSScriptRoot "..\logs\permission-suite"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Reset-SprocketAppData {
    param([string]$Serial)
    & $adb -s $Serial shell pm clear $pkg | Out-Null
    Start-Sleep -Seconds 12
}

$flows = Get-ChildItem -Path $permDir -Filter "PM_*.yaml" |
    Where-Object { $_.Name -match '^PM_\d{2} ' } |
    Sort-Object Name

switch ($Mode) {
    'Positive' { $flows = $flows | Where-Object { $_.Name -match '^PM_(01|04|05|06) ' } }
    'Negative' { $flows = $flows | Where-Object { $_.Name -match '^PM_(02|03|07) ' } }
    'Mixed'    { $flows = $flows | Where-Object { $_.Name -match '^PM_(03|04|06|07) ' } }
}

$results = @()
foreach ($flow in $flows) {
    if ($flow.BaseName -match 'PM_(\d+)' -and $Skip -contains [int]$Matches[1]) {
        Write-Host "SKIP $($flow.Name)" -ForegroundColor Yellow
        continue
    }
    Write-Host "`n========== $($flow.Name) ==========" -ForegroundColor Cyan
    Reset-SprocketAppData -Serial $Device
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
