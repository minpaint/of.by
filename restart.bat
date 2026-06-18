@echo off
setlocal
cd /d "%~dp0"

set "VENV_ROOT=C:\venvs"
set "VENV_NAME=of_by"
set "VENV_DIR=%VENV_ROOT%\%VENV_NAME%"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

echo Restarting server...
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 1 /nobreak >nul

if not exist "%VENV_PYTHON%" (
    echo Virtual environment not found.
    echo Run start.bat first.
    pause
    exit /b 1
)

"%VENV_PYTHON%" manage.py runserver 8005
pause
