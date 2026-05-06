@echo off
setlocal

cd /d "%~dp0"

where conda >nul 2>&1
if errorlevel 1 (
    echo [ERROR] conda command not found in PATH.
    echo Please open Anaconda Prompt once, or add conda to PATH.
    pause
    exit /b 1
)

call conda activate Pdf2Any
if errorlevel 1 (
    echo [ERROR] Failed to activate conda environment: Pdf2Any
    pause
    exit /b 1
)

python main.py %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] main.py exited with code %EXIT_CODE%
    pause
)

exit /b %EXIT_CODE%
