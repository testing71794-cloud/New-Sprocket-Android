# Run adb with a hard timeout (Jenkins-safe).
# IMPORTANT:
# - Never redirect stdout/stderr on "adb start-server" via pipes — that deadlocks on Windows.
# - Never invoke adb via cmd.exe /c with a quoted path — usernames with spaces (e.g. "CA Global")
#   break ArgumentList quoting and yield empty "adb devices" output.
# - Do NOT kill all adb.exe on every timeout — that resets USB recovery Maestro may already be doing.
param(
    [Parameter(Mandatory = $true)][string]$AdbExe,
    [Parameter(Mandatory = $true)][string[]]$AdbArgs,
    [int]$TimeoutSec = 20,
    [string]$OutFile = "",
    [switch]$KillAllAdbOnTimeout
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

function Stop-HungClient {
    param([System.Diagnostics.Process]$Proc, [bool]$KillAll)
    if ($null -ne $Proc) {
        try {
            if (-not $Proc.HasExited) { Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue }
        } catch {}
    }
    if ($KillAll) {
        Get-Process adb -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

try {
    if ($isStartServer -or $isKillServer) {
        # No stdout/stderr redirect — avoids WinGet/platform-tools deadlock under Jenkins.
        $p = Start-Process -FilePath $AdbExe -ArgumentList $AdbArgs `
            -WorkingDirectory $workDir `
            -WindowStyle Hidden -PassThru
        $waitMs = [Math]::Min([Math]::Max($TimeoutSec, 1), 20) * 1000
        $finished = $p.WaitForExit($waitMs)
        if (-not $finished) {
            # Parent often lingers while daemon is up — do NOT kill it (that wedges USB/adb).
            Write-Host ("WARN: adb " + $argText + " still running after " + ($waitMs / 1000) + "s; leaving process, continuing")
            exit 0
        }
        exit $p.ExitCode
    }

    # devices / other commands: ProcessStartInfo with async stream reads (space-safe, no cmd.exe).
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $AdbExe
    $psi.Arguments = $argText
    $psi.WorkingDirectory = $workDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()
    $stdoutTask = $p.StandardOutput.ReadToEndAsync()
    $stderrTask = $p.StandardError.ReadToEndAsync()
    $finished = $p.WaitForExit($TimeoutSec * 1000)
    if (-not $finished) {
        Write-Host ("ERROR: adb " + $argText + " timed out after " + $TimeoutSec + "s - killing hung client")
        Stop-HungClient -Proc $p -KillAll:([bool]$KillAllAdbOnTimeout)
        if ($KillAllAdbOnTimeout) {
            Write-Host "WARN: also killed all adb.exe processes (KillAllAdbOnTimeout)"
        }
        exit 2
    }

    $outText = ""
    try { $outText = $stdoutTask.Result } catch {}
    try {
        $errText = $stderrTask.Result
        if (-not [string]::IsNullOrWhiteSpace($errText)) {
            if ([string]::IsNullOrWhiteSpace($outText)) { $outText = $errText }
            else { $outText = $outText.TrimEnd() + "`r`n" + $errText }
        }
    } catch {}

    Set-Content -LiteralPath $outPath -Value $outText -Encoding ascii
    if (-not [string]::IsNullOrWhiteSpace($outText)) {
        Write-Host $outText.TrimEnd()
    } else {
        Write-Host "WARN: adb $argText produced empty output (exit=$($p.ExitCode))"
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
