@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=python"
"%PYTHON_EXE%" quick_start.py %*
exit
