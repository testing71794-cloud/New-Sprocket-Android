# Run PC_01-PC_11 Pre-Cut flows. PC_10/PC_11 skip pm clear (keep already-connected printer).
param(
    [string]$Device = "ZA222RFQ75",
    [int[]]$Skip = @(),
    [ValidateSet('All', 'Positive', 'Negative')]
    [string]$Mode = 'All',
    # Studio Plus Wi-Fi password for PC_10/PC_11 (lab network).
    [string]$WifiPassword = "Caglobal@127",
    [string]$WifiSsid = "CAGlobal"
)

$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$maestro = "C:\Users\HP\maestro\maestro\bin\maestro.bat"
$pkg = "com.hp.impulse.sprocket"
$precutDir = Join-Path $PSScriptRoot "..\ATP TestCase Flows\precut"
$logDir = Join-Path $PSScriptRoot "..\logs\precut-suite"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Reset-SprocketAppData {
    param([string]$Serial)
    & $adb -s $Serial shell pm clear $pkg | Out-Null
    Start-Sleep -Seconds 12
}

$flows = Get-ChildItem -Path $precutDir -Filter "PC_*.yaml" |
    Where-Object { $_.Name -match '^PC_\d{2} ' } |
    Sort-Object Name

switch ($Mode) {
    'Positive' { $flows = $flows | Where-Object { $_.Name -match '^PC_(0[1-9]) ' } }
    'Negative' { $flows = $flows | Where-Object { $_.Name -match '^PC_(10|11) ' } }
}

$results = @()
foreach ($flow in $flows) {
    if ($flow.BaseName -match 'PC_(\d+)' -and $Skip -contains [int]$Matches[1]) {
        Write-Host "SKIP $($flow.Name)" -ForegroundColor Yellow
        continue
    }
    Write-Host "`n========== $($flow.Name) ==========" -ForegroundColor Cyan
    if ($flow.BaseName -notmatch '^PC_(10|11) ') {
        Reset-SprocketAppData -Serial $Device
    }
    $outFile = Join-Path $logDir ($flow.BaseName + ".log")
    # Named env params for Wi-Fi pairing on unsupported (Studio Plus) path.
    & $maestro --device $Device test `
        -e "WIFI_PASSWORD=$WifiPassword" `
        -e "WIFI_SSID=$WifiSsid" `
        $flow.FullName `
        --debug-output $logDir `
        2>&1 | Tee-Object -FilePath $outFile
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
