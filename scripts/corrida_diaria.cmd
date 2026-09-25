@echo off
REM Corrida diaria v2 (la lanza el Programador de tareas de Windows).
REM El log lo escribe pipeline.run en data\logs\run_<corrida>.log
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
py -m pipeline.run --todo %*
exit /b %ERRORLEVEL%
