@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VENV_ROOT=C:\venvs"
set "VENV_NAME=of_by"
set "VENV_DIR=%VENV_ROOT%\%VENV_NAME%"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "BOOTSTRAP_PYTHON="
set "REQ_FILE=%CD%\requirements.txt"
set "REQ_HASH_FILE=%VENV_DIR%\.requirements.sha256"
set "CURRENT_HASH="
set "STORED_HASH="

echo Starting of.by server...

if not exist "%VENV_ROOT%" (
    echo Creating venv root: %VENV_ROOT%
    mkdir "%VENV_ROOT%"
    if errorlevel 1 goto :fail_make_root
)

if not exist "%VENV_PYTHON%" (
    echo Creating virtual environment: %VENV_DIR%
    where py >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_PYTHON=py -3"
    ) else (
        if exist "C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe" (
            set "BOOTSTRAP_PYTHON=C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe"
        ) else if exist "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" (
            set "BOOTSTRAP_PYTHON=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
        ) else if exist "C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe" (
            set "BOOTSTRAP_PYTHON=C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe"
        ) else (
            where python >nul 2>&1
            if not errorlevel 1 set "BOOTSTRAP_PYTHON=python"
        )
    )

    if not defined BOOTSTRAP_PYTHON goto :fail_find_python
    !BOOTSTRAP_PYTHON! -m venv "%VENV_DIR%"
    if errorlevel 1 goto :fail_make_venv
)

for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 '%REQ_FILE%').Hash"`) do (
    set "CURRENT_HASH=%%H"
)

if exist "%REQ_HASH_FILE%" (
    set /p STORED_HASH=<"%REQ_HASH_FILE%"
)

if not defined STORED_HASH goto :install_requirements
if /I not "!CURRENT_HASH!"=="!STORED_HASH!" goto :install_requirements
goto :start_server

:install_requirements
echo Installing dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :fail_pip
"%VENV_PYTHON%" -m pip install -r "%REQ_FILE%"
if errorlevel 1 goto :fail_pip
>"%REQ_HASH_FILE%" echo(!CURRENT_HASH!

:start_server
echo Dependencies are ready.
echo Starting Django on port 8005...
"%VENV_PYTHON%" manage.py runserver 8005
goto :end

:fail_make_root
echo Failed to create venv root folder.
goto :fail

:fail_make_venv
echo Failed to create virtual environment.
goto :fail

:fail_find_python
echo Could not find a usable Python interpreter.
echo Install Python or update start.bat with the correct python.exe path.
goto :fail

:fail_pip
echo Failed to install dependencies.
goto :fail

:fail
pause
exit /b 1

:end
pause
