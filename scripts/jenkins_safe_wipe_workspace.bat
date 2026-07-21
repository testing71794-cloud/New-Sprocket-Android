@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Safe workspace wipe for Windows Jenkins agents (non-TTY safe — no timeout.exe).
REM Always exits 0 so the pipeline can continue with unstash/checkout.
REM script_rev=2026-07-wipe-no-timeout-1

if "%~1"=="" (
  echo ERROR: %~nx0 requires workspace root as first argument.
  exit /b 0
)

set "WS=%~1"
echo [wipe] workspace=%WS%

if not exist "%WS%" (
  echo [wipe] workspace does not exist yet; nothing to wipe
  exit /b 0
)

echo [wipe] stopping common lockers ^(best-effort^)...
taskkill /F /IM maestro.exe /T >nul 2>&1
taskkill /F /IM adb.exe /T >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws='%WS%'; Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" -ErrorAction SilentlyContinue | ForEach-Object { $cmd=$_.CommandLine; if ($cmd -and ($cmd -match 'maestro|junit-suite|cli\.jar') -and ($cmd -match [regex]::Escape($ws))) { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} } }" >nul 2>&1

REM ping-sleep: timeout.exe aborts the whole Jenkins bat when stdin is redirected.
ping 127.0.0.1 -n 3 >nul 2>&1

echo [wipe] clearing read-only attributes...
attrib -R -S -H "%WS%\*.*" /S /D >nul 2>&1

if not defined TEMP set "TEMP=%LOCALAPPDATA%\Temp"
if not exist "%TEMP%" mkdir "%TEMP%" >nul 2>&1
set "EMPTY=%TEMP%\jenkins_empty_wipe_%RANDOM%%RANDOM%"
mkdir "%EMPTY%" >nul 2>&1
if not exist "%EMPTY%" (
  echo [wipe] WARNING: could not create empty mirror dir; falling back to rmdir loop
  goto :fallback_rm
)

echo [wipe] emptying workspace via robocopy /MIR ^(retry loop^)...
set /a ATTEMPT=0
:RETRY
set /a ATTEMPT+=1
robocopy "%EMPTY%" "%WS%" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS >nul 2>&1
set "RC=!ERRORLEVEL!"
if !RC! GEQ 8 (
  if !ATTEMPT! LSS 5 (
    echo [wipe] robocopy RC=!RC! attempt !ATTEMPT!/5; retrying...
    ping 127.0.0.1 -n 4 >nul 2>&1
    goto RETRY
  )
  echo [wipe] WARNING: robocopy could not fully empty workspace ^(RC=!RC!^). Continuing.
) else (
  echo [wipe] workspace contents cleared ^(robocopy RC=!RC!, attempt !ATTEMPT!^)
)
rmdir "%EMPTY%" >nul 2>&1

:fallback_rm
for /d %%D in ("%WS%\*") do rmdir /s /q "%%~fD" >nul 2>&1
del /f /q "%WS%\*" >nul 2>&1

echo [wipe] done ^(non-fatal if partial^)
exit /b 0
