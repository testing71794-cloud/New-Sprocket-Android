@echo off
setlocal EnableExtensions
REM Point Jenkins / local ATP at the parallel-install tree (Maestro 2.5.1+).
set "MAESTRO_HOME=C:\Tools\maestro-parallel\bin"
set "ATP_MAESTRO_PARALLEL_HOME=C:\Tools\maestro-parallel\bin"
echo MAESTRO_HOME=%MAESTRO_HOME%
echo ATP_MAESTRO_PARALLEL_HOME=%ATP_MAESTRO_PARALLEL_HOME%
python "%~dp0verify_maestro_parallel_cli.py"
exit /b %ERRORLEVEL%
