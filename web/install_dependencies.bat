@echo off
REM ApexGirl Bot Web Remote - Dependency Installer
REM This script helps install Python packages on Windows without compiler errors

echo ============================================================
echo ApexGirl Bot Web Remote - Dependency Installer
echo ============================================================
echo.

cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo Current Python version:
python --version
echo.

echo Step 1: Upgrading pip to latest version...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo Warning: Failed to upgrade pip
    echo.
) else (
    echo Pip upgraded successfully!
    echo.
)

echo Step 2: Installing packages individually...
echo This avoids compiler issues by using pre-built binaries.
echo.

echo Installing Flask...
pip install Flask
if errorlevel 1 (
    echo ERROR: Failed to install Flask
    goto :error
)

echo Installing flask-cors...
pip install flask-cors
if errorlevel 1 (
    echo ERROR: Failed to install flask-cors
    goto :error
)

echo Installing opencv-python...
pip install opencv-python
if errorlevel 1 (
    echo ERROR: Failed to install opencv-python
    goto :error
)

echo Installing numpy...
pip install numpy
if errorlevel 1 (
    echo Warning: Failed to install latest numpy
    echo Trying specific version...
    pip install numpy==1.24.3
    if errorlevel 1 (
        echo ERROR: Failed to install numpy
        goto :error
    )
)

echo.
echo ============================================================
echo SUCCESS! All dependencies installed successfully!
echo ============================================================
echo.
echo You can now run the server using:
echo   - Double-click: start_web_remote.bat
echo   - Or command line: python server.py
echo.
pause
exit /b 0

:error
echo.
echo ============================================================
echo Installation encountered errors.
echo ============================================================
echo.
echo Please try:
echo 1. Run this script as Administrator
echo 2. Update Python to the latest version
echo 3. Manual installation:
echo    pip install --only-binary :all: Flask flask-cors opencv-python numpy
echo.
pause
exit /b 1
