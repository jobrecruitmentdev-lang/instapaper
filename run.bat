@echo off
title Instapaper Multi-Account Automation
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo         INSTAPAPER MULTI-ACCOUNT AUTOMATION RUNNER
echo ============================================================
echo.

REM 1. Check Python installation
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM 2. Check Virtual Environment
if not exist ".venv\Scripts\python.exe" (
    echo [*] Setting up virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM 3. Check and install dependencies
echo [*] Checking dependencies
.venv\Scripts\pip.exe install -q -r requirements.txt

echo.
REM 4. Run the automation engine
.venv\Scripts\python.exe main.py

echo.
echo ============================================================
echo Execution ended.
echo ============================================================
pause

