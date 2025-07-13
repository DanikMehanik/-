@echo off
REM Setup script for Well Plan Optimization
REM This script replaces the Dockerfile functionality for Windows

echo ========================================
echo Well Plan Optimization Setup
echo ========================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12 or later from https://python.org
    pause
    exit /b 1
)

REM Check if uv is installed
uv --version >nul 2>&1
if errorlevel 1 (
    echo Installing uv package manager...
    powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo ERROR: Failed to install uv
        pause
        exit /b 1
    )
)

echo.
echo Installing dependencies with uv...
uv sync --frozen --no-dev --all-extras

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Verifying installation...
python -V
python -c "import wellplan; print('wellplan module imported successfully')"

if errorlevel 1 (
    echo ERROR: Failed to import wellplan module
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo To run the application, use:
echo   streamlit run src/wellplan/dashboard.py --server.port 8080
echo.
echo Or run this script with the 'run' parameter:
echo   setup.cmd run
echo.

REM Check if run parameter is provided
if "%1"=="run" (
    echo Starting Streamlit application...
    streamlit run src/wellplan/dashboard.py --server.port 8080
)

pause 