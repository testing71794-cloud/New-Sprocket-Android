@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM script_rev=2026-07-windows-precheck-adb-timeout-1

set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%set_maestro_java.bat" "%~1" || exit /b 1

if defined JAVA_HOME set "PATH=%JAVA_HOME%\bin;%PATH%"
if defined MAESTRO_HOME set "PATH=%MAESTRO_HOME%;%PATH%"
if defined ADB_HOME set "PATH=%ADB_HOME%;%PATH%"

set "ADB_EXE="
if defined ADB_HOME if exist "%ADB_HOME%\adb.exe" set "ADB_EXE=%ADB_HOME%\adb.exe"
if not defined ADB_EXE (
  for /f "delims=" %%W in ('where adb 2^>nul') do (
    set "ADB_EXE=%%W"
    goto :adb_resolved
  )
)
:adb_resolved

set "MAESTRO_BIN="
if defined MAESTRO_HOME (
  if exist "%MAESTRO_HOME%\maestro.bat" set "MAESTRO_BIN=%MAESTRO_HOME%\maestro.bat"
  if not defined MAESTRO_BIN if exist "%MAESTRO_HOME%\maestro.cmd" set "MAESTRO_BIN=%MAESTRO_HOME%\maestro.cmd"
)

set "ADB_TIMEOUT_PS=%SCRIPT_DIR%windows_agent\adb_run_timeout.ps1"
if not exist "%ADB_TIMEOUT_PS%" (
  echo ERROR: missing "%ADB_TIMEOUT_PS%"
  exit /b 1
)

echo =====================================
echo PRECHECK JAVA
echo =====================================
echo [DEBUG] JAVA_HOME=%JAVA_HOME%
echo [DEBUG] MAESTRO_HOME=%MAESTRO_HOME%
if defined ADB_HOME echo [DEBUG] ADB_HOME=%ADB_HOME%
if defined ADB_EXE echo [DEBUG] ADB_EXE=%ADB_EXE%
if defined MAESTRO_BIN echo [DEBUG] MAESTRO_BIN=%MAESTRO_BIN%
where java
"%JAVA_HOME%\bin\java.exe" -version
if errorlevel 1 exit /b 1
echo =====================================

echo Checking ADB...
if not defined ADB_EXE (
  echo ERROR: adb.exe not found
  exit /b 1
)

echo [DEBUG] killing any hung adb.exe ^(best-effort^)
taskkill /F /IM adb.exe /T >nul 2>&1
ping 127.0.0.1 -n 2 >nul 2>&1

echo [DEBUG] adb start-server ^(timeout 8s, no pipe redirect^)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ADB_TIMEOUT_PS%" -AdbExe "%ADB_EXE%" -AdbArgs start-server -TimeoutSec 8
if errorlevel 1 (
  echo WARN: adb start-server failed — continuing to devices check
)

echo [DEBUG] adb devices ^(timeout 25s^)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ADB_TIMEOUT_PS%" -AdbExe "%ADB_EXE%" -AdbArgs devices -TimeoutSec 25
set "ADB_EC=!ERRORLEVEL!"
if not "!ADB_EC!"=="0" (
  echo ERROR: adb devices failed or timed out ^(exit=!ADB_EC!^).
  echo Fix on the Windows agent:
  echo   1^) Install Android SDK platform-tools ^(not only WinGet Google.PlatformTools^)
  echo   2^) Plug phone, enable USB debugging, accept RSA prompt
  echo   3^) In an agent-user cmd:  "%%ADB_EXE%%" kill-server ^& "%%ADB_EXE%%" devices
  echo   4^) Ensure Jenkins agent user can see the device ^(same Windows login as USB session^)
  exit /b 1
)
echo =====================================

echo Checking Maestro...
if not defined MAESTRO_BIN (
  echo ERROR: maestro.bat not found under MAESTRO_HOME
  exit /b 1
)
echo [DEBUG] "%MAESTRO_BIN%" --version ^(timeout via cmd /c^)
REM maestro --help can be slow; prefer --version only
call "%MAESTRO_BIN%" --version
if errorlevel 1 exit /b 1

echo =====================================
echo Validating Maestro YAML (ATP TestCase Flows)...
set "REPO_ROOT=%CD%"
for %%P in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fP"
python "%SCRIPT_DIR%validate_maestro_yaml.py" "%REPO_ROOT%\ATP TestCase Flows"
if errorlevel 1 (
  echo ERROR: Maestro YAML validation failed
  exit /b 1
)
echo Maestro YAML validation OK
echo =====================================

echo Precheck complete
exit /b 0
