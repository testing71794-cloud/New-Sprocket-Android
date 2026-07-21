@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Resolve ADB_HOME only (device discovery). Prefer Android SDK over WinGet Platform Tools.
REM WinGet adb often hangs under Jenkins service sessions.
REM script_rev=2026-07-windows-agent-adb-env-prefer-sdk-1

set "ADB_HOME="
set "ADB_EXE="

if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" set "ADB_HOME=%ANDROID_HOME%\platform-tools"
if not defined ADB_HOME if defined ANDROID_SDK_ROOT if exist "%ANDROID_SDK_ROOT%\platform-tools\adb.exe" set "ADB_HOME=%ANDROID_SDK_ROOT%\platform-tools"
if not defined ADB_HOME if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" set "ADB_HOME=%LOCALAPPDATA%\Android\Sdk\platform-tools"
if not defined ADB_HOME if exist "%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe" set "ADB_HOME=%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools"
if not defined ADB_HOME if exist "C:\Android\Sdk\platform-tools\adb.exe" set "ADB_HOME=C:\Android\Sdk\platform-tools"
if not defined ADB_HOME if exist "C:\Android\android-sdk\platform-tools\adb.exe" set "ADB_HOME=C:\Android\android-sdk\platform-tools"

REM WinGet Platform Tools — last resort (known to hang on start-server/devices in some CI sessions)
if not defined ADB_HOME if defined LOCALAPPDATA (
  for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools*") do (
    if exist "%%~fD\platform-tools\adb.exe" (
      set "ADB_HOME=%%~fD\platform-tools"
      echo [WARN] Using WinGet platform-tools adb — prefer installing Android SDK platform-tools if ADB hangs.
      goto :adb_ok
    )
  )
)

if not defined ADB_HOME (
  for /f "delims=" %%W in ('where adb 2^>nul') do (
    echo %%W | find /I "WinGet\Packages\Google.PlatformTools" >nul
    if errorlevel 1 (
      for %%P in ("%%~dpW.") do set "ADB_HOME=%%~fP"
      goto :adb_ok
    )
  )
)
REM If only WinGet adb is on PATH, take it.
if not defined ADB_HOME (
  for /f "delims=" %%W in ('where adb 2^>nul') do (
    for %%P in ("%%~dpW.") do set "ADB_HOME=%%~fP"
    goto :adb_ok
  )
)

:adb_ok
if defined ADB_HOME if exist "%ADB_HOME%\adb.exe" set "ADB_EXE=%ADB_HOME%\adb.exe"

if defined ADB_HOME echo ADB_HOME=%ADB_HOME%
if defined ADB_EXE echo ADB_EXE=%ADB_EXE%

endlocal & (
  set "ADB_HOME=%ADB_HOME%"
  set "ADB_EXE=%ADB_EXE%"
)
exit /b 0
