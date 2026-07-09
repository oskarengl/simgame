@echo off
echo ======================================================================
echo GPU Simulation Environment Setup
echo ======================================================================
echo.

REM Check if .venv already exists
if exist .venv (
    echo Virtual environment already exists.
    echo.
    echo To use it:
    echo   1. Activate: .venv\Scripts\activate
    echo   2. Run: python main_gpu.py
    echo.
    pause
    exit /b 0
)

echo This script will help you set up Python 3.11 or 3.12 for the GPU simulation.
echo.
echo STEP 1: Find your Python 3.11 or 3.12 installation
echo.
echo Common locations:
echo   - C:\Python311\python.exe
echo   - C:\Python312\python.exe
echo   - C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe
echo.
echo Please enter the FULL PATH to your Python 3.11 or 3.12 executable:
echo   (e.g., C:\Python311\python.exe)
echo.
set /p PYTHON_PATH="Python path: "

REM Check if path exists
if not exist "%PYTHON_PATH%" (
    echo.
    echo ERROR: Path not found: %PYTHON_PATH%
    echo.
    echo Please download Python 3.11 or 3.12 from:
    echo   https://www.python.org/downloads/
    echo.
    echo During installation, check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM Check version
echo.
echo Checking Python version...
"%PYTHON_PATH%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Could not run Python at that path
    pause
    exit /b 1
)

"%PYTHON_PATH%" --version | findstr /R "3\.1[12]" >nul
if errorlevel 1 (
    echo.
    echo ERROR: That Python is not version 3.11 or 3.12
    "%PYTHON_PATH%" --version
    echo.
    echo Please use Python 3.11 or 3.12
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo Creating virtual environment...
echo ======================================================================
echo.

"%PYTHON_PATH%" -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo Installing dependencies...
echo ======================================================================
echo.

.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo WARNING: Some dependencies may have failed to install
    echo You can try manually: .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
)

echo.
echo ======================================================================
echo Setup Complete!
echo ======================================================================
echo.
echo To run the GPU simulation:
echo   1. Activate the environment:
echo      .venv\Scripts\activate
echo.
echo   2. Run the simulation:
echo      python main_gpu.py
echo.
echo ======================================================================
pause

