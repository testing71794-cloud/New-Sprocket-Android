@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Resolve JAVA_HOME / MAESTRO_HOME / ANDROID_HOME for the CURRENT Windows user/machine.
REM Does not hardcode C:\Users\HP\... — works on any Jenkins agent or laptop.
REM Usage:
REM   call scripts\resolve_windows_tools.bat
REM   call scripts\resolve_windows_tools.bat "optional-java" "optional-maestro-bin" "optional-android-sdk"
REM After call, parent should use the printed SET lines or rely on endlocal& set pattern below.

set "OPT_JAVA=%~1"
set "OPT_MAESTRO=%~2"
set "OPT_ANDROID=%~3"

if not defined USERPROFILE set "USERPROFILE=%HOMEDRIVE%%HOMEPATH%"
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"

REM ---- JAVA (prefer 17 for Maestro) ----
set "RESOLVED_JAVA="
call :try_java "%OPT_JAVA%"
if not defined RESOLVED_JAVA call :try_java "%MAESTRO_JAVA_HOME%"
if not defined RESOLVED_JAVA (
  for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-17*") do call :try_java "%%~fD"
)
if not defined RESOLVED_JAVA call :try_java "%JAVA_HOME%"
if not defined RESOLVED_JAVA call :try_java "%USERPROFILE%\.jdks\jbr-17.0.8"
if not defined RESOLVED_JAVA call :try_java "%USERPROFILE%\.jdks\jbr-17.0.14"
if not defined RESOLVED_JAVA (
  for /d %%D in ("%USERPROFILE%\.jdks\jbr-17*") do call :try_java "%%~fD"
)
if not defined RESOLVED_JAVA (
  for /d %%D in ("C:\Program Files\Eclipse Adoptium\jdk-21*") do call :try_java "%%~fD"
)
if not defined RESOLVED_JAVA call :try_java "C:\Program Files\Microsoft\jdk-17.0.8.7-hotspot"
if not defined RESOLVED_JAVA call :try_java "C:\Program Files\Java\jdk-17"

REM ---- MAESTRO ----
set "RESOLVED_MAESTRO="
call :try_maestro "%OPT_MAESTRO%"
if not defined RESOLVED_MAESTRO call :try_maestro "%MAESTRO_HOME%"
if not defined RESOLVED_MAESTRO call :try_maestro "%USERPROFILE%\maestro\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro "%USERPROFILE%\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro "%LOCALAPPDATA%\maestro\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro "C:\maestro\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro "C:\maestro\bin"
if not defined RESOLVED_MAESTRO call :try_maestro "C:\Tools\maestro-parallel\bin"
if not defined RESOLVED_MAESTRO (
  for /d %%D in ("C:\Tools\maestro*") do (
    if not defined RESOLVED_MAESTRO call :try_maestro "%%~fD\bin"
    if not defined RESOLVED_MAESTRO call :try_maestro "%%~fD\maestro\bin"
  )
)
if not defined RESOLVED_MAESTRO (
  where maestro.bat >nul 2>&1 && for /f "delims=" %%P in ('where maestro.bat 2^>nul') do (
    if not defined RESOLVED_MAESTRO (
      set "RESOLVED_MAESTRO=%%~dpP"
      if "!RESOLVED_MAESTRO:~-1!"=="\" set "RESOLVED_MAESTRO=!RESOLVED_MAESTRO:~0,-1!"
    )
  )
)

REM ---- ANDROID SDK ----
set "RESOLVED_ANDROID="
call :try_android "%OPT_ANDROID%"
if not defined RESOLVED_ANDROID call :try_android "%ANDROID_HOME%"
if not defined RESOLVED_ANDROID call :try_android "%ANDROID_SDK_ROOT%"
if not defined RESOLVED_ANDROID call :try_android "%LOCALAPPDATA%\Android\Sdk"
if not defined RESOLVED_ANDROID call :try_android "%USERPROFILE%\AppData\Local\Android\Sdk"
if not defined RESOLVED_ANDROID call :try_android "%USERPROFILE%\Android\Sdk"
if not defined RESOLVED_ANDROID call :try_android "C:\Tools\android-sdk"
if not defined RESOLVED_ANDROID call :try_android "C:\Tools"
if not defined RESOLVED_ANDROID call :try_android "C:\Android\Sdk"
if not defined RESOLVED_ANDROID call :try_android "C:\Android"
REM WinGet Platform Tools last — can hang under Jenkins
if not defined RESOLVED_ANDROID if defined LOCALAPPDATA (
  for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools*") do (
    if not defined RESOLVED_ANDROID call :try_android "%%~fD"
  )
)

REM If only adb is on PATH (WinGet), derive ANDROID_HOME from adb.exe location.
if not defined RESOLVED_ANDROID (
  for /f "delims=" %%W in ('where adb 2^>nul') do (
    for %%P in ("%%~dpW..") do call :try_android "%%~fP"
    goto :after_where_adb
  )
)
:after_where_adb

echo [resolve_windows_tools] USERPROFILE=%USERPROFILE%
echo [resolve_windows_tools] JAVA_HOME=!RESOLVED_JAVA!
echo [resolve_windows_tools] MAESTRO_HOME=!RESOLVED_MAESTRO!
echo [resolve_windows_tools] ANDROID_HOME=!RESOLVED_ANDROID!

REM Export to caller via a props file in TEMP (and optional workspace arg %~4)
set "PROPS=%TEMP%\jenkins_resolved_tools.cmd"
(
  echo @echo off
  if defined RESOLVED_JAVA echo set "JAVA_HOME=!RESOLVED_JAVA!"
  if defined RESOLVED_JAVA echo set "MAESTRO_JAVA_HOME=!RESOLVED_JAVA!"
  if defined RESOLVED_JAVA echo set "PATH=!RESOLVED_JAVA!\bin;%%PATH%%"
  if defined RESOLVED_MAESTRO echo set "MAESTRO_HOME=!RESOLVED_MAESTRO!"
  if defined RESOLVED_MAESTRO echo set "PATH=!RESOLVED_MAESTRO!;%%PATH%%"
  if defined RESOLVED_ANDROID echo set "ANDROID_HOME=!RESOLVED_ANDROID!"
  if defined RESOLVED_ANDROID echo set "ANDROID_SDK_ROOT=!RESOLVED_ANDROID!"
  if defined RESOLVED_ANDROID echo set "ADB_HOME=!RESOLVED_ANDROID!\platform-tools"
  if defined RESOLVED_ANDROID echo set "PATH=!RESOLVED_ANDROID!\platform-tools;%%PATH%%"
) > "%PROPS%"

if not "%~4"=="" (
  copy /y "%PROPS%" "%~4\resolved_tools.cmd" >nul 2>&1
)

endlocal & (
  call "%TEMP%\jenkins_resolved_tools.cmd"
)
exit /b 0

:try_java
if "%~1"=="" exit /b 0
if defined RESOLVED_JAVA exit /b 0
if exist "%~1\bin\java.exe" set "RESOLVED_JAVA=%~1"
exit /b 0

:try_maestro
if "%~1"=="" exit /b 0
if defined RESOLVED_MAESTRO exit /b 0
if exist "%~1\maestro.bat" set "RESOLVED_MAESTRO=%~1"
if exist "%~1\maestro.cmd" set "RESOLVED_MAESTRO=%~1"
exit /b 0

:try_android
if "%~1"=="" exit /b 0
if defined RESOLVED_ANDROID exit /b 0
if exist "%~1\platform-tools\adb.exe" set "RESOLVED_ANDROID=%~1"
exit /b 0
