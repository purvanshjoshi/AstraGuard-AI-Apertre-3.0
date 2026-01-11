#!/usr/bin/env python3
"""
Cross-platform build script for AstraGuard AI
Works on Windows, Linux, and macOS
Installs dependencies and prepares the application
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def run_command(cmd, cwd=None, description=""):
    """Run a command and return True if successful"""
    try:
        print(f"🔧 {description}")
        result = subprocess.run(cmd, shell=True, cwd=cwd, check=True,
                              capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {description}")
        print(f"   Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd.split()[0]}")
        return False

def check_command_available(cmd):
    """Check if a command is available"""
    try:
        subprocess.run([cmd, "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def main():
    print("🚀 Starting AstraGuard AI build process...")
    print(f"📍 Project root: {Path.cwd()}")
    print(f"🖥️  OS: {platform.system()} {platform.release()}")

    # Check for required commands
    print("\n🔍 Checking for required tools...")

    python_cmd = None
    for cmd in ["python3", "python"]:
        if check_command_available(cmd):
            python_cmd = cmd
            break

    if not python_cmd:
        print("❌ Error: Python is not installed or not in PATH")
        print("   Please install Python from https://python.org")
        sys.exit(1)

    if not check_command_available("npm"):
        print("❌ Error: npm is not installed or not in PATH")
        print("   Please install Node.js from https://nodejs.org")
        sys.exit(1)

    print(f"✅ Found Python: {python_cmd}")
    print("✅ Found npm")

    # Install Python dependencies
    print("\n📦 Installing Python dependencies...")
    req_file = Path("requirements.txt")
    if req_file.exists():
        if not run_command(f"{python_cmd} -m pip install --user -r requirements.txt",
                          description="Installing Python packages"):
            sys.exit(1)
    else:
        print("⚠️  requirements.txt not found, skipping Python dependencies")

    # Build frontend
    print("\n🏗️ Building Next.js frontend...")
    frontend_dir = Path("frontend/as_lp")
    if frontend_dir.exists():
        print(f"📍 Building in: {frontend_dir.absolute()}")

        package_file = frontend_dir / "package.json"
        if package_file.exists():
            # Install npm dependencies
            if not run_command("npm install", cwd=frontend_dir,
                             description="Installing npm dependencies"):
                sys.exit(1)

            # Build the frontend
            if not run_command("npm run build", cwd=frontend_dir,
                             description="Building frontend application"):
                sys.exit(1)
        else:
            print("⚠️  package.json not found in frontend directory")
    else:
        print(f"⚠️  Frontend directory not found: {frontend_dir}")

    print("\n✅ Build complete successfully!")
    print("\n🎉 AstraGuard AI is ready to run!")
    print("   Start the app with: npm run app")
    print("   Start API with: npm run api")
    print("   Start frontend with: npm run frontend")

if __name__ == "__main__":
    main()