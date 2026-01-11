@echo off
REM Cross-platform build script for AstraGuard AI (Windows)
REM Compatible with Windows Command Prompt and PowerShell
REM Installs dependencies and prepares the application

echo 🚀 Starting AstraGuard AI build process...
echo 📍 Project root: %~dp0
echo 🖥️  OS: Windows

REM Check for required commands
echo 🔍 Checking for required tools...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Error: Python is not installed or not in PATH
    echo    Please install Python from https://python.org
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Error: npm is not installed or not in PATH
    echo    Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

echo 📦 Installing Python dependencies...
if exist "requirements.txt" (
    python -m pip install --user -r requirements.txt
    if %errorlevel% neq 0 (
        echo ❌ Failed to install Python dependencies
        pause
        exit /b 1
    )
) else (
    echo ⚠️  requirements.txt not found, skipping Python dependencies
)

echo 🏗️ Building Next.js frontend...
if exist "frontend\as_lp" (
    cd "frontend\as_lp"
    echo 📍 Building in: %cd%

    if exist "package.json" (
        echo 📦 Installing npm dependencies...
        npm install
        if %errorlevel% neq 0 (
            echo ❌ Failed to install npm dependencies
            cd ..\..
            pause
            exit /b 1
        )

        echo 🏗️ Running build...
        npm run build
        if %errorlevel% neq 0 (
            echo ❌ Failed to build frontend
            cd ..\..
            pause
            exit /b 1
        )
    ) else (
        echo ⚠️  package.json not found in frontend directory
    )

    cd ..\..
) else (
    echo ⚠️  Frontend directory not found: frontend\as_lp
)

echo ✅ Build complete successfully!
echo.
echo 🎉 AstraGuard AI is ready to run!
echo    Start the app with: npm run app
echo    Start API with: npm run api
echo    Start frontend with: npm run frontend
echo.
pause