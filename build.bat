@echo off
echo ===================================
echo   Brisk Dex - build the .exe
echo ===================================
echo.
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo Node.js is not installed or not on PATH.
    echo Download it from https://nodejs.org, install it, then run this again.
    pause
    exit /b 1
)
echo Installing dependencies (first run only, this can take a few minutes)...
call npm install
if %errorlevel% neq 0 (
    echo.
    echo npm install failed - see the errors above.
    pause
    exit /b 1
)
echo.
echo Building the installer...
call npm run dist
if %errorlevel% neq 0 (
    echo.
    echo Build failed - see the errors above.
    pause
    exit /b 1
)
echo.
echo Done! Find the installer in the "dist" folder.
pause
