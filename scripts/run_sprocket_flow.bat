@echo off
setlocal EnableExtensions
REM Local HP Sprocket checks on Samsung only. Jenkins continues using Motorola via detected_devices.txt.
REM Usage: scripts\run_sprocket_flow.bat "ATP TestCase Flows\splash\SP_01.yaml"
REM        scripts\run_sprocket_flow.bat "ATP TestCase Flows\onboarding\ON_01.yaml"

set "REPO_ROOT=%~dp0.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

if not "%~1"=="" (
  set "FLOW_PATH=%~1"
) else (
  echo Usage: %~nx0 ^<path-to-flow.yaml^>
  exit /b 1
)
if not exist "%FLOW_PATH%" (
  echo ERROR: Flow not found: %FLOW_PATH%
  exit /b 1
)

REM Samsung M34 — lab Sprocket device (Motorola ZA222RFQ75 stays on Jenkins).
set "SPROCKET_DEVICE=RZCWA2B05RB"
if not "%SPROCKET_DEVICE_SERIAL%"=="" set "SPROCKET_DEVICE=%SPROCKET_DEVICE_SERIAL%"

if not defined MAESTRO_HOME set "MAESTRO_HOME="
if not defined JAVA_HOME set "JAVA_HOME="
if not defined ANDROID_HOME set "ANDROID_HOME="
call "%~dp0resolve_windows_tools.bat" "%JAVA_HOME%" "%MAESTRO_HOME%" "%ANDROID_HOME%"
if not defined MAESTRO_HOME (
  echo ERROR: Could not resolve MAESTRO_HOME on this machine. Install Maestro or set MAESTRO_HOME.
  exit /b 1
)
if not defined JAVA_HOME (
  echo ERROR: Could not resolve JAVA_HOME on this machine. Install JDK 17+ or set JAVA_HOME.
  exit /b 1
)
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%MAESTRO_HOME%;%PATH%"

set "MAESTRO_BIN=%MAESTRO_HOME%\maestro.bat"
if not exist "%MAESTRO_BIN%" (
  echo ERROR: maestro.bat not found under MAESTRO_HOME=%MAESTRO_HOME%
  exit /b 1
)

echo === Sprocket local run (Samsung %SPROCKET_DEVICE% only) ===
echo Flow: %FLOW_PATH%
echo.

"%MAESTRO_BIN%" --device "%SPROCKET_DEVICE%" test "%FLOW_PATH%"
exit /b %ERRORLEVEL%
