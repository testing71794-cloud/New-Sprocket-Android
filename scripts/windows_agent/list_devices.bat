@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM script_rev=2026-07-windows-agent-list-devices-adb-timeout-3
REM Writes detected_devices.txt under the Jenkins workspace (paths may contain spaces).
REM Avoid aggressive taskkill loops — they interrupt USB/ADB recovery (Maestro waits up to 5 min).
goto :script_body

REM Sleep without timeout.exe (Jenkins non-TTY safe).
:sleep_seconds
set /a "_ss=%~1"
if !_ss! LSS 1 set "_ss=1"
if !_ss! GTR 180 set "_ss=180"
set /a "_ss_ping=!_ss!+1"
ping 127.0.0.1 -n !_ss_ping! >nul
exit /b 0

:script_body
REM Optional %1 = workspace root (from Python cmd.exe argv); else WORKSPACE env; else parent of scripts\.
set "REPO_ROOT="
if not "%~1"=="" (
  for %%I in ("%~1") do set "REPO_ROOT=%%~fI"
) else if not "%WORKSPACE%"=="" (
  for %%I in ("%WORKSPACE%") do set "REPO_ROOT=%%~fI"
) else (
  set "SCRIPT_DIR=%~dp0"
  for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
)
if not defined REPO_ROOT (
  echo ERROR: REPO_ROOT not resolved. Pass workspace as arg1 or set WORKSPACE.
  exit /b 1
)
cd /d "%REPO_ROOT%"

set "OUT_FILE=%REPO_ROOT%\detected_devices.txt"
set "DEBUG_LOG=%REPO_ROOT%\reports\_agent\list_devices_debug.log"
if not exist "%REPO_ROOT%\reports\_agent" mkdir "%REPO_ROOT%\reports\_agent"

(
echo =====================================
echo LIST DEVICES ^(windows_agent^)
echo =====================================
echo script_rev        : 2026-07-windows-agent-list-devices-adb-timeout-3
echo arg1 workspace    : %~1
echo WORKSPACE env     : %WORKSPACE%
echo REPO_ROOT         : %REPO_ROOT%
echo CD                : %CD%
echo OUT_FILE          : %OUT_FILE%
echo =====================================
) > "%DEBUG_LOG%"

call "%~dp0set_adb_env.bat" >> "%DEBUG_LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: set_adb_env.bat failed>> "%DEBUG_LOG%"
  type "%DEBUG_LOG%"
  exit /b 1
)

REM Optional: log Java/Maestro paths when set_maestro_java is available (not required for adb).
if exist "%~dp0..\set_maestro_java.bat" (
  call "%~dp0..\set_maestro_java.bat" >> "%DEBUG_LOG%" 2>&1
)

if not defined ADB_DETECT_WAIT_ATTEMPTS set "ADB_DETECT_WAIT_ATTEMPTS=5"
if not defined ADB_DETECT_WAIT_SECS set "ADB_DETECT_WAIT_SECS=8"
if not defined ADB_DEVICES_TIMEOUT_SEC set "ADB_DEVICES_TIMEOUT_SEC=90"

echo =========================>> "%DEBUG_LOG%"
echo Connected Android devices>> "%DEBUG_LOG%"
echo =========================>> "%DEBUG_LOG%"

if not defined ADB_EXE (
  if defined ADB_HOME if exist "%ADB_HOME%\adb.exe" set "ADB_EXE=%ADB_HOME%\adb.exe"
)
if not defined ADB_EXE (
  echo ERROR: adb.exe not found. Set ANDROID_HOME or add platform-tools to PATH.>> "%DEBUG_LOG%"
  type "%DEBUG_LOG%"
  exit /b 1
)
echo ADB_EXE=%ADB_EXE%>> "%DEBUG_LOG%"
echo ADB_EXE="%ADB_EXE%"
echo [list_devices] script_rev=2026-07-windows-agent-list-devices-adb-timeout-3
echo [list_devices] ADB_DEVICES_TIMEOUT_SEC=%ADB_DEVICES_TIMEOUT_SEC% attempts=%ADB_DETECT_WAIT_ATTEMPTS%
echo [list_devices] Progress is live below; a hung adb devices call can take up to %ADB_DEVICES_TIMEOUT_SEC%s per attempt.

del /q "%OUT_FILE%" 2>nul

set "ADB_TIMEOUT_PS=%~dp0adb_run_timeout.ps1"
if not exist "%ADB_TIMEOUT_PS%" (
  echo ERROR: missing "%ADB_TIMEOUT_PS%">> "%DEBUG_LOG%"
  type "%DEBUG_LOG%"
  exit /b 1
)

set /a "_ATT=0"
:detect_loop
set /a "_ATT+=1"
echo.>> "%DEBUG_LOG%"
echo [detect] attempt !_ATT!/%ADB_DETECT_WAIT_ATTEMPTS% ^(wait %ADB_DETECT_WAIT_SECS%s, devices_timeout=%ADB_DEVICES_TIMEOUT_SEC%s^)>> "%DEBUG_LOG%"
echo [list_devices] attempt !_ATT!/%ADB_DETECT_WAIT_ATTEMPTS% ...

REM Soft recovery only — hard taskkill only on later attempts (USB needs time to re-enumerate).
if !_ATT! EQU 2 (
  echo [detect] soft restart: adb kill-server>> "%DEBUG_LOG%"
  echo [list_devices] soft restart: adb kill-server
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ADB_TIMEOUT_PS%" -AdbExe "%ADB_EXE%" -AdbArgs kill-server -TimeoutSec 10 >> "%DEBUG_LOG%" 2>&1
  call :sleep_seconds 3
)
if !_ATT! GEQ 4 (
  echo [detect] hard restart: taskkill adb.exe ^(last-resort^)>> "%DEBUG_LOG%"
  echo [list_devices] hard restart: taskkill adb.exe
  taskkill /F /IM adb.exe /T >nul 2>&1
  call :sleep_seconds 5
)

echo Starting ADB server...>> "%DEBUG_LOG%"
echo [list_devices] adb start-server ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ADB_TIMEOUT_PS%" -AdbExe "%ADB_EXE%" -AdbArgs start-server -TimeoutSec 12 >> "%DEBUG_LOG%" 2>&1
REM Give daemon + USB a settle window before devices (do not race).
echo [detect] waiting 5s for adb daemon/USB settle...>> "%DEBUG_LOG%"
echo [list_devices] waiting 5s for adb daemon/USB settle...
call :sleep_seconds 5

set "ADB_DEVICES_TMP=%TEMP%\adb_devices_list_%RANDOM%.txt"
echo.>> "%DEBUG_LOG%"
echo --- adb devices ^(full output, timeout %ADB_DEVICES_TIMEOUT_SEC%s^) --->> "%DEBUG_LOG%"
echo [list_devices] adb devices ^(timeout %ADB_DEVICES_TIMEOUT_SEC%s^) ...
REM Do not KillAllAdbOnTimeout — leave daemon alive so USB can finish recovering.
powershell -NoProfile -ExecutionPolicy Bypass -File "%ADB_TIMEOUT_PS%" -AdbExe "%ADB_EXE%" -AdbArgs devices -TimeoutSec %ADB_DEVICES_TIMEOUT_SEC% -OutFile "%ADB_DEVICES_TMP%" >> "%DEBUG_LOG%" 2>&1
set "ADB_EC=!ERRORLEVEL!"
if not exist "%ADB_DEVICES_TMP%" (
  echo. > "%ADB_DEVICES_TMP%"
)
if not "!ADB_EC!"=="0" if not "!ADB_EC!"=="1" (
  echo [WARN] adb devices soft-fail exit=!ADB_EC! on attempt !_ATT!>> "%DEBUG_LOG%"
  echo [list_devices] WARN: adb devices exit=!ADB_EC!
)
type "%ADB_DEVICES_TMP%" >> "%DEBUG_LOG%"
type "%ADB_DEVICES_TMP%"
echo --- end adb devices --->> "%DEBUG_LOG%"
(
for /f "usebackq skip=1 tokens=1,2" %%A in ("%ADB_DEVICES_TMP%") do (
  if /I "%%B"=="device" echo %%A
)
) > "%OUT_FILE%"
del /q "%ADB_DEVICES_TMP%" 2>nul

set /a COUNT=0
for /f "usebackq delims=" %%A in ("%OUT_FILE%") do set /a COUNT+=1

if !COUNT! GTR 0 goto :detect_done

if !_ATT! LSS %ADB_DETECT_WAIT_ATTEMPTS% (
  echo [WARN] No device in state "device" yet; waiting %ADB_DETECT_WAIT_SECS%s...>> "%DEBUG_LOG%"
  echo [list_devices] no device yet; waiting %ADB_DETECT_WAIT_SECS%s...
  call :sleep_seconds %ADB_DETECT_WAIT_SECS%
  goto :detect_loop
)

echo.>> "%DEBUG_LOG%"
echo Devices detected: 0>> "%DEBUG_LOG%"
echo Device list saved to: "%OUT_FILE%">> "%DEBUG_LOG%"
echo [HINT] adb devices hang = USB/daemon wedged. As Jenkins agent user ^(interactive desktop^):>> "%DEBUG_LOG%"
echo [HINT]   1^) Unplug/replug phone, unlock, accept RSA if prompted>> "%DEBUG_LOG%"
echo [HINT]   2^) Close Maestro Studio / leftover maestro java>> "%DEBUG_LOG%"
echo [HINT]   3^) "%%ADB_EXE%%" kill-server ^& "%%ADB_EXE%%" devices>> "%DEBUG_LOG%"
echo [HINT]   4^) Ensure only C:\Tools\platform-tools\adb.exe is used ^(not WinGet^)>> "%DEBUG_LOG%"
type "%DEBUG_LOG%"
exit /b 1

:detect_done
echo.>> "%DEBUG_LOG%"
echo Devices detected: !COUNT!>> "%DEBUG_LOG%"
echo Device list saved to: "%OUT_FILE%">> "%DEBUG_LOG%"
echo [DEBUG] list_devices OK — wrote "%OUT_FILE%">> "%DEBUG_LOG%"
type "%OUT_FILE%"
exit /b 0
