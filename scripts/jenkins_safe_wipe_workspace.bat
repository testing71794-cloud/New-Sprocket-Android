@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Safe workspace wipe for Windows Jenkins agents.
REM Avoids hard-fail when files are locked (Maestro/Java/ADB/antivirus).
REM Clears CONTENTS of the workspace; does not require deleting the workspace root.
REM Always exits 0 so the pipeline can continue with unstash/checkout.

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

REM Stop common lockers that often hold handles under the workspace.
echo [wipe] stopping common lockers ^(best-effort^)...
taskkill /F /IM maestro.exe /T >nul 2>&1
taskkill /F /IM adb.exe /T >nul 2>&1
REM Do NOT kill all java.exe ^(Jenkins agent itself^). Only tip leftover Maestro JVM if cwd matches.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws='%WS%'; Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" -ErrorAction SilentlyContinue | ForEach-Object { $cmd=$_.CommandLine; if ($cmd -and ($cmd -match 'maestro|junit-suite|cli\.jar') -and ($cmd -match [regex]::Escape($ws))) { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} } }" >nul 2>&1

timeout /t 2 /nobreak >nul

echo [wipe] clearing read-only attributes...
attrib -R -S -H "%WS%\*.*" /S /D >nul 2>&1

set "EMPTY=%TEMP%\jenkins_empty_wipe_%RANDOM%"
mkdir "%EMPTY%" >nul 2>&1

echo [wipe] emptying workspace via robocopy /MIR ^(retry loop^)...
set /a ATTEMPT=0
:RETRY
set /a ATTEMPT+=1
robocopy "%EMPTY%" "%WS%" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS >nul 2>&1
set "RC=%ERRORLEVEL%"
REM robocopy 0-7 = success-ish; 8+ = failure
if %RC% GEQ 8 (
  if %ATTEMPT% LSS 5 (
    echo [wipe] robocopy RC=%RC% attempt %ATTEMPT%/5; retrying after delay...
    timeout /t 3 /nobreak >nul
    goto RETRY
  )
  echo [wipe] WARNING: robocopy could not fully empty workspace ^(RC=%RC%^). Continuing anyway.
) else (
  echo [wipe] workspace contents cleared ^(robocopy RC=%RC%, attempt %ATTEMPT%^)
)

rmdir "%EMPTY%" >nul 2>&1

REM Best-effort remove leftover top-level dirs that robocopy left
for /d %%D in ("%WS%\*") do (
  rmdir /s /q "%%~fD" >nul 2>&1
)
del /f /q "%WS%\*" >nul 2>&1

echo [wipe] done ^(non-fatal if partial^)
exit /b 0
