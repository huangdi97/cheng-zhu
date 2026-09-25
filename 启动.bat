@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=python"
"%PYTHON_EXE%" start.py %*
pause
