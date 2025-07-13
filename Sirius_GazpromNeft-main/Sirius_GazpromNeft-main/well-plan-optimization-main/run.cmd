@echo off
REM Quick start script for Well Plan Optimization

echo Starting Well Plan Optimization...
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Virtual environment not found. Running setup first...
    call setup.cmd
    if errorlevel 1 (
        echo Setup failed. Please run setup.cmd manually.
        pause
        exit /b 1
    )
)

REM Activate virtual environment and run
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Starting Streamlit application on port 8080...
streamlit run src/wellplan/dashboard.py --server.port 8080

pause 