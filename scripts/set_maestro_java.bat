@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Resolve JAVA_HOME / MAESTRO_HOME for Maestro ATP on any Windows agent (spaces OK).
REM Prefer JDK 17 for Maestro; fall back to 21+. Do not hardcode one machine's paths.
REM script_rev=2026-07-set-maestro-java-portable-1

REM Optional %1 = Maestro launcher (MAESTRO_CMD): bare name or full path to maestro.bat / maestro.cmd

REM --- Java (prefer 17, then existing JAVA_HOME / MAESTRO_JAVA_HOME, then 21) ---
set "RESOLVED_JAVA="
if defined MAESTRO_JAVA_HOME if exist "%MAESTRO_JAVA_HOME%\bin\java.exe" set "RESOLVED_JAVA=%MAESTRO_JAVA_HOME%"
if not defined RESOLVED_JAVA if defined JAVA_HOME if exist "%JAVA_HOME%\bin\java.exe" set "RESOLVED_JAVA=%JAVA_HOME%"

REM Prefer Temurin/Adoptium 17 for Maestro stability
if not defined RESOLVED_JAVA (
  for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-17*") do (
    if exist "%%~fD\bin\java.exe" (
      set "RESOLVED_JAVA=%%~fD"
      goto :java_picked
    )
  )
)
if not defined RESOLVED_JAVA (
  for /d %%D in ("C:\Program Files\Microsoft\jdk-17*") do (
    if exist "%%~fD\bin\java.exe" (
      set "RESOLVED_JAVA=%%~fD"
      goto :java_picked
    )
  )
)
if not defined RESOLVED_JAVA (
  for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-21*") do (
    if exist "%%~fD\bin\java.exe" (
      set "RESOLVED_JAVA=%%~fD"
      goto :java_picked
    )
  )
)
if not defined RESOLVED_JAVA if defined USERPROFILE if exist "%USERPROFILE%\.jdks" (
  for /d %%D in ("%USERPROFILE%\.jdks\jbr-17*") do (
    if exist "%%~fD\bin\java.exe" (
      set "RESOLVED_JAVA=%%~fD"
      goto :java_picked
    )
  )
)
:java_picked
if not defined RESOLVED_JAVA (
  echo ERROR: No JDK found. Install Temurin 17+ or set JAVA_HOME / MAESTRO_JAVA_HOME.
  endlocal & exit /b 1
)
set "JAVA_HOME=%RESOLVED_JAVA%"
if "%JAVA_HOME:~-1%"=="\" set "JAVA_HOME=%JAVA_HOME:~0,-1%"

REM --- Maestro ---
set "RESOLVED_MAESTRO="

if defined MAESTRO_HOME (
  if exist "%MAESTRO_HOME%\maestro.bat" set "RESOLVED_MAESTRO=%MAESTRO_HOME%"
  if not defined RESOLVED_MAESTRO if exist "%MAESTRO_HOME%\maestro.cmd" set "RESOLVED_MAESTRO=%MAESTRO_HOME%"
)

if not defined RESOLVED_MAESTRO if not "%~1"=="" (
  if exist "%~f1" (
    for %%F in ("%~f1") do set "RESOLVED_MAESTRO=%%~dpF"
    if defined RESOLVED_MAESTRO if "!RESOLVED_MAESTRO:~-1!"=="\" set "RESOLVED_MAESTRO=!RESOLVED_MAESTRO:~0,-1!"
  )
)

if not defined RESOLVED_MAESTRO call :try_maestro_dir "%USERPROFILE%\maestro\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro_dir "%USERPROFILE%\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro_dir "%LOCALAPPDATA%\maestro\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro_dir "C:\maestro\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro_dir "C:\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro_dir "C:\Tools\maestro-parallel\bin"
if not defined RESOLVED_MAESTRO (
  for /d %%D in ("C:\Tools\maestro*") do (
    if not defined RESOLVED_MAESTRO call :try_maestro_dir "%%~fD\bin"
    if not defined RESOLVED_MAESTRO call :try_maestro_dir "%%~fD\maestro\bin"
  )
)
if not defined RESOLVED_MAESTRO (
  for /f "delims=" %%W in ('where maestro.bat 2^>nul') do (
    for %%P in ("%%~dpW.") do set "RESOLVED_MAESTRO=%%~fP"
    goto :maestro_picked
  )
)
if not defined RESOLVED_MAESTRO (
  for /f "delims=" %%W in ('where maestro.cmd 2^>nul') do (
    for %%P in ("%%~dpW.") do set "RESOLVED_MAESTRO=%%~fP"
    goto :maestro_picked
  )
)
:maestro_picked
if not defined RESOLVED_MAESTRO (
  echo ERROR: Maestro not found on this agent.
  echo Install Maestro CLI, then either:
  echo   1^) Add maestro.bat to the agent service user PATH, or
  echo   2^) Set job param MAESTRO_HOME to the folder containing maestro.bat, or
  echo   3^) Set MAESTRO_CMD to the full path of maestro.bat
  echo Searched: %%USERPROFILE%%\maestro\..., C:\maestro\..., C:\Tools\maestro*, PATH
  echo USERPROFILE=%USERPROFILE%
  endlocal & exit /b 1
)
set "MAESTRO_HOME=%RESOLVED_MAESTRO%"

set "PATH=%JAVA_HOME%\bin;%MAESTRO_HOME%;%PATH%"

REM --- ADB ---
set "ADB_HOME="
if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" set "ADB_HOME=%ANDROID_HOME%\platform-tools"
if not defined ADB_HOME if defined ANDROID_SDK_ROOT if exist "%ANDROID_SDK_ROOT%\platform-tools\adb.exe" set "ADB_HOME=%ANDROID_SDK_ROOT%\platform-tools"
if not defined ADB_HOME if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" set "ADB_HOME=%LOCALAPPDATA%\Android\Sdk\platform-tools"
if not defined ADB_HOME if defined LOCALAPPDATA (
  for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools*") do (
    if exist "%%~fD\platform-tools\adb.exe" (
      set "ADB_HOME=%%~fD\platform-tools"
      goto :adb_ok
    )
  )
)
if not defined ADB_HOME (
  for /f "delims=" %%W in ('where adb 2^>nul') do (
    for %%P in ("%%~dpW.") do set "ADB_HOME=%%~fP"
    goto :adb_ok
  )
)
:adb_ok
if defined ADB_HOME set "PATH=%ADB_HOME%;%PATH%"

echo JAVA_HOME=%JAVA_HOME%
echo MAESTRO_HOME=%MAESTRO_HOME%
if defined ADB_HOME echo ADB_HOME=%ADB_HOME%

endlocal & (
  set "JAVA_HOME=%JAVA_HOME%"
  set "MAESTRO_HOME=%MAESTRO_HOME%"
  set "ADB_HOME=%ADB_HOME%"
  set "PATH=%PATH%"
)
exit /b 0

:try_maestro_dir
if "%~1"=="" exit /b 0
if defined RESOLVED_MAESTRO exit /b 0
if exist "%~1\maestro.bat" set "RESOLVED_MAESTRO=%~1"
if not defined RESOLVED_MAESTRO if exist "%~1\maestro.cmd" set "RESOLVED_MAESTRO=%~1"
exit /b 0
