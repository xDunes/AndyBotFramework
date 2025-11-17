@echo off
REM ApexGirl Bot Web Remote - Startup Script

echo ============================================================
echo ApexGirl Bot Web Remote - Starting Server
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

REM Check if requirements are installed
echo Checking dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    echo.
    echo Upgrading pip first...
    python -m pip install --upgrade pip
    echo.
    echo Installing dependencies this may take a minute...
    pip install Flask flask-cors opencv-python numpy
    echo.
)

REM Get local IP address
echo Getting your computer's IP address...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set "ip=%%a"
    goto :found
)
:found
set "ip=%ip:~1%"

echo.
echo ============================================================
echo Server is starting...
echo.
echo You can access the web interface at:
echo   - Local:   http://localhost:5000
echo   - Network: http://%ip%:5000
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

REM Start the server
python server.py

pause
