# Run adb with a hard timeout (Jenkins-safe; avoids forever hang on "adb devices").
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File adb_run_timeout.ps1 -AdbExe "C:\...\adb.exe" -AdbArgs @("devices") -TimeoutSec 20
#   ... -OutFile "C:\temp\out.txt"
param(
    [Parameter(Mandatory = $true)][string]$AdbExe,
    [Parameter(Mandatory = $true)][string[]]$AdbArgs,
    [int]$TimeoutSec = 20,
    [string]$OutFile = ""
)

$ErrorActionPreference = "Continue"
if (-not (Test-Path -LiteralPath $AdbExe)) {
    Write-Host "ERROR: adb.exe not found: $AdbExe"
    exit 1
}

$outPath = $OutFile
if ([string]::IsNullOrWhiteSpace($outPath)) {
    $outPath = Join-Path $env:TEMP ("adb_out_" + [guid]::NewGuid().ToString("N") + ".txt")
}
$errPath = Join-Path $env:TEMP ("adb_err_" + [guid]::NewGuid().ToString("N") + ".txt")

try {
    $p = Start-Process -FilePath $AdbExe -ArgumentList $AdbArgs `
        -NoNewWindow -PassThru `
        -RedirectStandardOutput $outPath `
        -RedirectStandardError $errPath
} catch {
    Write-Host ("ERROR: failed to start adb: " + $_.Exception.Message)
    exit 1
}

$finished = $p.WaitForExit($TimeoutSec * 1000)
if (-not $finished) {
    $argText = ($AdbArgs -join " ")
    Write-Host ("ERROR: adb " + $argText + " timed out after " + $TimeoutSec + "s - killing hung adb")
    try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
    Get-Process adb -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $outPath) { Get-Content -LiteralPath $outPath -ErrorAction SilentlyContinue | Write-Host }
    if (Test-Path -LiteralPath $errPath) { Get-Content -LiteralPath $errPath -ErrorAction SilentlyContinue | Write-Host }
    exit 2
}

$code = $p.ExitCode
if (Test-Path -LiteralPath $outPath) {
    Get-Content -LiteralPath $outPath -ErrorAction SilentlyContinue | Write-Host
}
if (Test-Path -LiteralPath $errPath) {
    Get-Content -LiteralPath $errPath -ErrorAction SilentlyContinue | Write-Host
}
if ([string]::IsNullOrWhiteSpace($OutFile) -and (Test-Path -LiteralPath $outPath)) {
    Remove-Item -LiteralPath $outPath -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $errPath -Force -ErrorAction SilentlyContinue
exit $code
