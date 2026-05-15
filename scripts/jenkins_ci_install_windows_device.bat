@echo off
setlocal EnableExtensions
REM Windows USB device agent: Python deps only (Maestro ATP). Skips npm.
REM Full install (npm optional): scripts\jenkins_ci_install.bat
if "%~1"=="" (
  echo ERROR: %~nx0 requires workspace root as first argument.
  exit /b 1
)
set "JENKINS_SKIP_NPM=1"
set "JENKINS_WORKLOAD_PROFILE=windows-device"
echo [workload] profile=windows-device scope=device-agent pip-only
call "%~dp0jenkins_ci_install.bat" "%~1"
exit /b %ERRORLEVEL%
