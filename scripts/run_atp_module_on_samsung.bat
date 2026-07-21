@echo off
setlocal EnableExtensions
REM Run one ATP module folder on Samsung only (local Sprocket). Does not change Jenkins device list.
REM Usage: scripts\run_atp_module_on_samsung.bat onboarding
REM        scripts\run_atp_module_on_samsung.bat signup

set "REPO_ROOT=%~dp0.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
cd /d "%REPO_ROOT%"

if "%~1"=="" (
  echo Usage: %~nx0 ^<atp-folder^> [app_package]
  echo Example: %~nx0 onboarding com.hp.impulse.sprocket
  exit /b 1
)

set "ATP_FOLDER=%~1"
set "APP_PACKAGE=%~2"
if "%APP_PACKAGE%"=="" set "APP_PACKAGE=com.hp.impulse.sprocket"

set "SPROCKET_DEVICE=RZCWA2B05RB"
if not "%SPROCKET_DEVICE_SERIAL%"=="" set "SPROCKET_DEVICE=%SPROCKET_DEVICE_SERIAL%"

REM Pin orchestrator to Samsung for this process only.
set "ORCH_DEVICES_FILE=%REPO_ROOT%\detected_devices.sprocket.txt"
set "ATP_DEVICE_SERIAL=%SPROCKET_DEVICE%"

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

echo === ATP module on Samsung %SPROCKET_DEVICE% ^(local Sprocket^) ===
echo Folder: %ATP_FOLDER%
echo App:    %APP_PACKAGE%
echo.

python scripts\jenkins_atp_stage.py all "%ATP_FOLDER%" "%APP_PACKAGE%" true maestro.bat
exit /b %ERRORLEVEL%
