@echo off
echo ========================================
echo    VidNet Local Development Server
echo ========================================
echo.
echo Starting VidNet in minimal mode...
echo This version works without Redis/Docker
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if FastAPI is installed
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Installing required dependencies...
    pip install fastapi uvicorn
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Starting server...
echo.
echo ========================================
echo  VidNet will be available at:
echo  http://127.0.0.1:8000
echo ========================================
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the minimal application
python app_minimal.py

echo.
echo Server stopped.
pause