# Run adb with a hard timeout (Jenkins-safe).
# IMPORTANT:
# - Never redirect stdout/stderr on "adb start-server" via pipes — that deadlocks on Windows.
# - Never invoke adb via cmd.exe /c with a quoted path — usernames with spaces (e.g. "CA Global")
#   break ArgumentList quoting and yield empty "adb devices" output.
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

function Stop-HungAdb {
    param([System.Diagnostics.Process]$Proc)
    if ($null -ne $Proc) {
        try {
            if (-not $Proc.HasExited) { Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue }
        } catch {}
    }
    Get-Process adb -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

try {
    if ($isStartServer -or $isKillServer) {
        # No stdout/stderr redirect — avoids WinGet/platform-tools deadlock under Jenkins.
        # FilePath + ArgumentList (array) is space-safe for "CA Global" paths.
        $p = Start-Process -FilePath $AdbExe -ArgumentList $AdbArgs `
            -WorkingDirectory $workDir `
            -WindowStyle Hidden -PassThru
        $waitMs = [Math]::Min([Math]::Max($TimeoutSec, 1), 15) * 1000
        $finished = $p.WaitForExit($waitMs)
        if (-not $finished) {
            # start-server parent sometimes lingers while daemon is already up.
            Write-Host ("WARN: adb " + $argText + " still running after " + ($waitMs / 1000) + "s; continuing")
            try { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } } catch {}
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
        Write-Host ("ERROR: adb " + $argText + " timed out after " + $TimeoutSec + "s - killing hung adb")
        Stop-HungAdb -Proc $p
        if (Test-Path -LiteralPath $outPath) {
            Get-Content -LiteralPath $outPath -ErrorAction SilentlyContinue | Write-Host
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
