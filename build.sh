#!/bin/bash
# Cross-platform build script for AstraGuard AI
# Compatible with Linux, macOS, and Windows (with bash)
# Installs dependencies and prepares the application

set -e  # Exit on any error

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get absolute path (cross-platform)
get_absolute_path() {
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows (MSYS/MinGW or Git Bash)
        cygpath -w "$(cd "$1" && pwd)" 2>/dev/null || echo "$(cd "$1" && pwd)"
    else
        # Unix-like systems
        cd "$1" && pwd
    fi
}

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(get_absolute_path "$SCRIPT_DIR")"

echo "🚀 Starting AstraGuard AI build process..."
echo "📍 Project root: $PROJECT_ROOT"
echo "🖥️  OS: $OSTYPE"

# Check for required commands
echo "🔍 Checking for required tools..."

if ! command_exists python3 && ! command_exists python; then
    echo "❌ Error: Python is not installed or not in PATH"
    exit 1
fi

if ! command_exists npm; then
    echo "❌ Error: npm is not installed or not in PATH"
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command_exists python3; then
    PYTHON_CMD="python"
    echo "⚠️  Using 'python' instead of 'python3'"
fi

echo "📦 Installing Python dependencies..."
cd "$PROJECT_ROOT"
if [ -f "requirements.txt" ]; then
    $PYTHON_CMD -m pip install --user -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install Python dependencies"
        exit 1
    fi
else
    echo "⚠️  requirements.txt not found, skipping Python dependencies"
fi

echo "🏗️ Building Next.js frontend..."
FRONTEND_DIR="$PROJECT_ROOT/frontend/as_lp"
if [ -d "$FRONTEND_DIR" ]; then
    cd "$FRONTEND_DIR"
    echo "📍 Building in: $(pwd)"

    if [ -f "package.json" ]; then
        echo "📦 Installing npm dependencies..."
        npm install
        if [ $? -ne 0 ]; then
            echo "❌ Failed to install npm dependencies"
            exit 1
        fi

        echo "🏗️ Running build..."
        npm run build
        if [ $? -ne 0 ]; then
            echo "❌ Failed to build frontend"
            exit 1
        fi
    else
        echo "⚠️  package.json not found in frontend directory"
    fi
else
    echo "⚠️  Frontend directory not found: $FRONTEND_DIR"
fi

# Return to project root
cd "$PROJECT_ROOT"

echo "✅ Build complete successfully!"
echo ""
echo "🎉 AstraGuard AI is ready to run!"
echo "   Start the app with: npm run app"
echo "   Start API with: npm run api"
echo "   Start frontend with: npm run frontend"
