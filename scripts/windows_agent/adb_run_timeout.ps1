# Run adb with a hard timeout (Jenkins-safe).
# IMPORTANT: Never RedirectStandardOutput/Error on "adb start-server" on Windows —
# that pipe pattern deadlocks and looks like a hang/timeout.
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

$workDir = Split-Path -Parent $AdbExe
$argText = ($AdbArgs -join " ")
$isStartServer = ($AdbArgs.Count -ge 1 -and $AdbArgs[0] -eq "start-server")
$isKillServer = ($AdbArgs.Count -ge 1 -and $AdbArgs[0] -eq "kill-server")

$outPath = $OutFile
$tempOut = $false
if ([string]::IsNullOrWhiteSpace($outPath)) {
    $outPath = Join-Path $env:TEMP ("adb_out_" + [guid]::NewGuid().ToString("N") + ".txt")
    $tempOut = $true
}

try {
    if ($isStartServer -or $isKillServer) {
        # No stdout/stderr redirect — avoids WinGet/platform-tools deadlock under Jenkins.
        $p = Start-Process -FilePath $AdbExe -ArgumentList $AdbArgs `
            -WorkingDirectory $workDir `
            -WindowStyle Hidden -PassThru
        $waitMs = [Math]::Min($TimeoutSec, 8) * 1000
        $finished = $p.WaitForExit($waitMs)
        if (-not $finished) {
            # start-server parent sometimes lingers while daemon is already up.
            Write-Host ("WARN: adb " + $argText + " still running after " + ($waitMs / 1000) + "s; continuing")
            exit 0
        }
        exit $p.ExitCode
    }

    # Other commands (devices, etc.): redirect via cmd.exe file redirect, not PowerShell pipes.
    $argLine = ($AdbArgs | ForEach-Object {
            if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
        }) -join " "
    $inner = '"' + $AdbExe + '" ' + $argLine + ' > "' + $outPath + '" 2>&1'
    $p = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", $inner) `
        -WorkingDirectory $workDir `
        -WindowStyle Hidden -PassThru
    $finished = $p.WaitForExit($TimeoutSec * 1000)
    if (-not $finished) {
        Write-Host ("ERROR: adb " + $argText + " timed out after " + $TimeoutSec + "s - killing hung adb")
        try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
        Get-Process adb -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $outPath) {
            Get-Content -LiteralPath $outPath -ErrorAction SilentlyContinue | Write-Host
        }
        exit 2
    }
    if (Test-Path -LiteralPath $outPath) {
        Get-Content -LiteralPath $outPath -ErrorAction SilentlyContinue | Write-Host
    }
    $code = $p.ExitCode
    if ($tempOut -and (Test-Path -LiteralPath $outPath)) {
        Remove-Item -LiteralPath $outPath -Force -ErrorAction SilentlyContinue
    }
    exit $code
} catch {
    Write-Host ("ERROR: failed to run adb: " + $_.Exception.Message)
    exit 1
}
