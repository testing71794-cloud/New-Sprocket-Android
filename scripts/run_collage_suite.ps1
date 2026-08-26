# Run Collage ATP flows. Mode: All (COL_01-21), Excel (COLX_01-15 → COL), Core (COL_01-15), Extra (16-21).
param(
    [string]$Device = "16091FDD4004N6",
    [int[]]$Skip = @(),
    [ValidateSet('All', 'Excel', 'Core', 'Extra')]
    [string]$Mode = 'All'
)

$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$maestro = "C:\Users\HP\maestro\maestro\bin\maestro.bat"
$pkg = "com.hp.impulse.sprocket"
$collageDir = Join-Path $PSScriptRoot "..\ATP TestCase Flows\collage"
$logDir = Join-Path $PSScriptRoot "..\logs\collage-suite"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Reset-SprocketAppData {
    param([string]$Serial)
    & $adb -s $Serial shell pm clear $pkg | Out-Null
    Start-Sleep -Seconds 12
}

switch ($Mode) {
    'Excel' {
        $flows = Get-ChildItem -Path $collageDir -Filter "COLX_*.yaml" |
            Where-Object { $_.Name -match '^COLX_\d{2} ' } |
            Sort-Object Name
    }
    'Core' {
        $flows = Get-ChildItem -Path $collageDir -Filter "COL_*.yaml" |
            Where-Object { $_.Name -match '^COL_(0[1-9]|1[0-5]) ' } |
            Sort-Object Name
    }
    'Extra' {
        $flows = Get-ChildItem -Path $collageDir -Filter "COL_*.yaml" |
            Where-Object { $_.Name -match '^COL_(1[6-9]|2[0-1]) ' } |
            Sort-Object Name
    }
    Default {
        $flows = Get-ChildItem -Path $collageDir -Filter "COL_*.yaml" |
            Where-Object { $_.Name -match '^COL_\d{2} ' } |
            Sort-Object Name
    }
}

$results = @()
foreach ($flow in $flows) {
    $num = $null
    if ($flow.BaseName -match 'COLX?_(\d+)') { $num = [int]$Matches[1] }
    if ($null -ne $num -and $Skip -contains $num) {
        Write-Host "SKIP $($flow.Name)" -ForegroundColor Yellow
        continue
    }
    Write-Host "`n========== $($flow.Name) ==========" -ForegroundColor Cyan
    # COL_21 keeps listed printer — do not pm clear.
    if ($flow.BaseName -notmatch '^COL_21 ') {
        Reset-SprocketAppData -Serial $Device
    }
    $outFile = Join-Path $logDir ($flow.BaseName + ".log")
    & $maestro --device $Device test $flow.FullName --debug-output $logDir 2>&1 |
        Tee-Object -FilePath $outFile
    $exit = $LASTEXITCODE
    $status = if ($exit -eq 0) { "PASS" } else { "FAIL" }
    $results += [pscustomobject]@{ Flow = $flow.Name; Status = $status; Exit = $exit }
    Write-Host "$status $($flow.Name)" -ForegroundColor $(if ($status -eq "PASS") { "Green" } else { "Red" })
}

Write-Host "`n========== SUMMARY =========="
$results | Format-Table -AutoSize
$pass = ($results | Where-Object Status -eq "PASS").Count
$fail = ($results | Where-Object Status -eq "FAIL").Count
Write-Host "Passed: $pass / $($results.Count)  Failed: $fail"
$summaryCsv = Join-Path $logDir "last_run_summary.csv"
$results | Export-Csv -Path $summaryCsv -NoTypeInformation
Write-Host "Summary CSV: $summaryCsv"
if ($fail -gt 0) { exit 1 }
