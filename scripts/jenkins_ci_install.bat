@echo off
setlocal EnableExtensions
if "%~1"=="" (
  echo ERROR: %~nx0 requires workspace root as first argument.
  exit /b 1
)
cd /d "%~1"
echo === SAFE DISK CLEANUP PRE ===
REM Run sibling .bats from the scripts directory (avoids broken quoting when repo path has spaces).
pushd "%~dp0"
if not exist "jenkins_resolve_python.bat" (
  echo ERROR: jenkins_resolve_python.bat not found in %CD%
  echo ERROR: This file must exist in the repo under scripts\ — commit scripts\jenkins_resolve_python.bat and re-clone or pull.
  popd
  exit /b 1
)
if not exist "safe_disk_cleanup.bat" (
  echo ERROR: safe_disk_cleanup.bat not found in %CD%
  popd
  exit /b 1
)
call safe_disk_cleanup.bat PRE "%~1"

REM Use the same Python 3.11–3.13 resolution as other Jenkins scripts. Bare "python" may hit
REM a broken install (e.g. Python 3.14 preview with corrupted pip on PATH).
call jenkins_resolve_python.bat
set "RESOLVE_EC=%ERRORLEVEL%"
popd
if not "%RESOLVE_EC%"=="0" (
  echo ERROR: jenkins_resolve_python.bat failed — install Python 3.12/3.13 or set PYTHON_EXE_OVERRIDE.
  echo 1> install_failed.flag
  exit /b 1
)
if not defined PYTHON_EXE (
  echo ERROR: PYTHON_EXE not set after jenkins_resolve_python.bat
  echo 1> install_failed.flag
  exit /b 1
)
echo [install] Using PYTHON_EXE=%PYTHON_EXE%

"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo [install] pip not usable; trying ensurepip...
  "%PYTHON_EXE%" -m ensurepip --upgrade
  if errorlevel 1 (
    echo ERROR: ensurepip failed for "%PYTHON_EXE%"
    echo 1> install_failed.flag
    exit /b 1
  )
)

"%PYTHON_EXE%" -m pip install --upgrade pip || (echo 1> install_failed.flag & exit /b 1)
"%PYTHON_EXE%" -m pip install -r scripts/requirements-python.txt || (echo 1> install_failed.flag & exit /b 1)

REM npm is optional on the devices agent (Maestro ATP uses Python only). Fail only when
REM JENKINS_REQUIRE_NPM=1 or npm is on PATH but install fails.
if /I "%JENKINS_SKIP_NPM%"=="1" goto :skip_npm_root
if /I "%SKIP_NPM_INSTALL%"=="1" goto :skip_npm_root
call :maybe_npm_install "%~1" package.json
if errorlevel 1 exit /b 1
:skip_npm_root
if /I "%JENKINS_SKIP_NPM%"=="1" goto :skip_npm_ai_doctor
if /I "%SKIP_NPM_INSTALL%"=="1" goto :skip_npm_ai_doctor
if exist ai-doctor\package.json (
  pushd ai-doctor
  call :maybe_npm_install "%~1" package.json
  if errorlevel 1 (
    popd
    exit /b 1
  )
  popd
)
:skip_npm_ai_doctor
if not exist build-summary mkdir build-summary
endlocal
exit /b 0

:maybe_npm_install
REM %1 = workspace root (for install_failed.flag), %2 = package.json path relative to cwd
set "WS_ROOT=%~1"
if not exist "%~2" exit /b 0
where npm >nul 2>&1
if errorlevel 1 (
  if /I "%JENKINS_REQUIRE_NPM%"=="1" (
    echo ERROR: npm required ^(JENKINS_REQUIRE_NPM=1^) but not on PATH. Install Node.js LTS on this agent.
    echo 1> "%WS_ROOT%\install_failed.flag"
    exit /b 1
  )
  echo [install] WARN: npm not on PATH — skipping Node install for %~2 ^(Maestro ATP does not need it^).
  echo [install] WARN: Set JENKINS_REQUIRE_NPM=1 to fail when npm is missing.
  exit /b 0
)
echo [install] npm install in %CD% ^(%~2^)...
call npm ci
if errorlevel 1 call npm install
if errorlevel 1 (
  echo ERROR: npm ci / npm install failed in %CD%
  echo 1> "%WS_ROOT%\install_failed.flag"
  exit /b 1
)
exit /b 0
