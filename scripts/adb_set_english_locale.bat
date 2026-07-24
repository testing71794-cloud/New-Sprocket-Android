@echo off
setlocal EnableExtensions
REM Force Android system locale to English (US) before Facebook OAuth WebView.
REM Usage: scripts\adb_set_english_locale.bat DEVICE_SERIAL

set "DEVICE=%~1"
if "%DEVICE%"=="" (
  echo Usage: %~nx0 DEVICE_SERIAL
  exit /b 1
)

if defined ANDROID_HOME (
  set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
) else (
  set "ADB=adb"
)

"%ADB%" -s "%DEVICE%" shell settings put system system_locales en-US
if errorlevel 1 (
  echo [adb_set_english_locale] WARN: settings put system_locales failed on %DEVICE%
  "%ADB%" -s "%DEVICE%" shell setprop persist.sys.locale en-US
)

echo [adb_set_english_locale] system_locales=en-US on %DEVICE%
exit /b 0
