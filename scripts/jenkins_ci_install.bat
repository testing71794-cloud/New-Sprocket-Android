@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM script_rev=2026-05-jenkins-ci-install-quoted-1
if "%~1"=="" (
  echo ERROR: %~nx0 requires workspace root as first argument.
  exit /b 1
)
cd /d "%~1"
set "WS_ROOT=%~1"
call "%~dp0resolve_windows_tools.bat" "%JAVA_HOME%" "%MAESTRO_HOME%" "%ANDROID_HOME%" "%WS_ROOT%"
if defined JENKINS_WORKLOAD_PROFILE echo [workload] profile=%JENKINS_WORKLOAD_PROFILE%
echo === SAFE DISK CLEANUP PRE ===
echo [DEBUG] cd /d "%WS_ROOT%"
pushd "%~dp0"
if not exist "jenkins_resolve_python.bat" (
  echo ERROR: jenkins_resolve_python.bat not found in "%CD%"
  popd
  exit /b 1
)
if not exist "safe_disk_cleanup.bat" (
  echo ERROR: safe_disk_cleanup.bat not found in "%CD%"
  popd
  exit /b 1
)
echo [DEBUG] call "%~dp0safe_disk_cleanup.bat" PRE "%WS_ROOT%"
call "%~dp0safe_disk_cleanup.bat" PRE "%WS_ROOT%"

echo [DEBUG] call "%~dp0jenkins_resolve_python.bat"
call "%~dp0jenkins_resolve_python.bat"
set "RESOLVE_EC=!ERRORLEVEL!"
popd
if not "!RESOLVE_EC!"=="0" (
  echo ERROR: jenkins_resolve_python.bat failed — install Python 3.12/3.13 or set PYTHON_EXE_OVERRIDE.
  echo 1> "%WS_ROOT%\install_failed.flag"
  exit /b 1
)
if not defined PYTHON_EXE (
  echo ERROR: PYTHON_EXE not set after jenkins_resolve_python.bat
  echo 1> "%WS_ROOT%\install_failed.flag"
  exit /b 1
)
echo [install] Using PYTHON_EXE=%PYTHON_EXE%

"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo [install] pip not usable; trying ensurepip...
  "%PYTHON_EXE%" -m ensurepip --upgrade
  if errorlevel 1 (
    echo ERROR: ensurepip failed for "%PYTHON_EXE%"
    echo 1> "%WS_ROOT%\install_failed.flag"
    exit /b 1
  )
)

"%PYTHON_EXE%" -m pip install --upgrade pip || (
  echo 1> "%WS_ROOT%\install_failed.flag"
  exit /b 1
)
"%PYTHON_EXE%" -m pip install -r "%WS_ROOT%\scripts\requirements-python.txt" || (
  echo 1> "%WS_ROOT%\install_failed.flag"
  exit /b 1
)

if /I "%JENKINS_SKIP_NPM%"=="1" goto :skip_npm_root
if /I "%SKIP_NPM_INSTALL%"=="1" goto :skip_npm_root
call :maybe_npm_install "%WS_ROOT%" "package.json"
if errorlevel 1 exit /b 1
:skip_npm_root
if /I "%JENKINS_SKIP_NPM%"=="1" goto :skip_npm_ai_doctor
if /I "%SKIP_NPM_INSTALL%"=="1" goto :skip_npm_ai_doctor
if exist "%WS_ROOT%\ai-doctor\package.json" (
  pushd "%WS_ROOT%\ai-doctor"
  call :maybe_npm_install "%WS_ROOT%" "package.json"
  if errorlevel 1 (
    popd
    exit /b 1
  )
  popd
)
:skip_npm_ai_doctor
if not exist "%WS_ROOT%\build-summary" mkdir "%WS_ROOT%\build-summary"
endlocal
exit /b 0

:maybe_npm_install
set "WS_ROOT=%~1"
if not exist "%~2" exit /b 0
where npm >nul 2>&1
if errorlevel 1 (
  if /I "%JENKINS_REQUIRE_NPM%"=="1" (
    echo ERROR: npm required ^(JENKINS_REQUIRE_NPM=1^) but not on PATH.
    echo 1> "%WS_ROOT%\install_failed.flag"
    exit /b 1
  )
  echo [install] WARN: npm not on PATH — skipping Node install for %~2.
  exit /b 0
)
echo [install] npm install in "%CD%" ^(%~2^)...
call npm ci
if errorlevel 1 call npm install
if errorlevel 1 (
  echo ERROR: npm ci / npm install failed in "%CD%"
  echo 1> "%WS_ROOT%\install_failed.flag"
  exit /b 1
)
exit /b 0
