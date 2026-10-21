@echo off
setlocal
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
if not defined ENV_FILE if exist "%~dp0.env" set "ENV_FILE=%~dp0.env"
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)

rem Examples:
rem   run.bat --input-dir C:\books\in
rem   run.bat --input-dir C:\books\in --output-dir C:\books\out --no-same-dir
rem   run.bat "C:\books\in\My Audiobook.m4b"
rem   run.bat --config config.example.yml --no-loop
"%PYTHON%" -m m4b_tag_fixer --same-dir %*
exit /b %ERRORLEVEL%
