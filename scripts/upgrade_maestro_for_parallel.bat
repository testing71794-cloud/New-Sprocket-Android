@echo off
setlocal EnableExtensions
echo ============================================
echo Maestro upgrade check - native parallel ATP
echo ============================================
echo.
echo MAESTRO_HOME=%MAESTRO_HOME%
echo JAVA_HOME=%JAVA_HOME%
echo.
python "%~dp0verify_maestro_parallel_cli.py"
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (
  echo.
  echo Native parallel is READY. Re-run Jenkins ATP with 2+ devices.
  exit /b 0
)
echo.
echo Native parallel NOT ready on this agent.
echo.
echo 1. Download latest Maestro for Windows from:
echo    https://github.com/mobile-dev-inc/Maestro/releases
echo 2. Extract and point Jenkins MAESTRO_HOME to the new bin folder
echo 3. Re-run: python scripts\verify_maestro_parallel_cli.py
echo.
echo Serialized fallback is now automatic on old Maestro ^(no env var required^).
echo Strict mode after upgrade: set ATP_REQUIRE_NATIVE_PARALLEL=1
echo.
exit /b %RC%
