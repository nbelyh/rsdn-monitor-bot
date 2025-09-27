@echo off
echo Installing RSDN Bot dependencies...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

REM Install dependencies
echo Installing Python packages...
pip install -r requirements.txt

if errorlevel 1 (
    echo Error: Failed to install dependencies
    echo Please check your internet connection and try again
    pause
    exit /b 1
)

echo.
echo ✅ Dependencies installed successfully!
echo.
echo Next steps:
echo 1. Copy .env.example to .env
echo 2. Edit .env with your Telegram bot token and chat ID
echo 3. Run: python test_bot.py (to test configuration)
echo 4. Run: python main.py (to start the bot)
echo.

pause