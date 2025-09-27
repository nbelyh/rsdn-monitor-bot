@echo off
echo Starting RSDN Bot...

REM Check if .env file exists
if not exist .env (
    echo Error: .env file not found
    echo Please copy .env.example to .env and configure it first
    pause
    exit /b 1
)

REM Start the bot
python main.py

if errorlevel 1 (
    echo.
    echo Bot stopped with error. Check the logs for details.
    pause
)

echo.
echo Bot stopped.
pause