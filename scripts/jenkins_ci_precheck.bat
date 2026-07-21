@echo off
setlocal EnableExtensions
cd /d "%~1"
call "%~dp0resolve_windows_tools.bat" "%JAVA_HOME%" "%MAESTRO_HOME%" "%ANDROID_HOME%" "%~1"
where java
java -version
call "%~dp0precheck_environment.bat" "%~2" "%~3" || (
  echo 1> "precheck_failed.flag"
  echo 1> "pipeline_failed.flag"
  exit /b 1
)
