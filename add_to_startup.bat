@echo off
echo Creating startup shortcut...

set SCRIPT_PATH=%~dp0run_hidden.vbs
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_PATH=%STARTUP_FOLDER%\ClaudeUsageMonitor.lnk

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%SCRIPT_PATH%'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Claude Code Usage Monitor'; $s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo.
    echo [SUCCESS] Startup shortcut created!
    echo The monitor will now start automatically with Windows.
) else (
    echo.
    echo [ERROR] Failed to create shortcut.
)

echo.
pause
