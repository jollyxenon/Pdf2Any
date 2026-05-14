@echo off
setlocal

cd /d "%~dp0"

where pixi >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pixi command not found in PATH.
    echo Please install pixi: https://pixi.sh/latest/
    pause
    exit /b 1
)

pixi run main %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] main.py exited with code %EXIT_CODE%
    pause
)

exit /b %EXIT_CODE%
