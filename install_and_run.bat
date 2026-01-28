@echo off
echo ========================================
echo Claude Code Usage Monitor - Installer
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo [1/2] Installing dependencies...
pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

echo [2/2] Starting Claude Code Usage Monitor...
echo.
echo The monitor will appear in your system tray.
echo Click the icon to show/hide the usage widget.
echo.

pythonw claude_usage_monitor.py

echo Monitor started!
