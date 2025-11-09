#!/usr/bin/env python3
"""
verify_setup.py
Verify that all requirements are met before running the server.
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_check(name, status, details=""):
    """Print a check result."""
    symbol = "✓" if status else "✗"
    color = "\033[92m" if status else "\033[91m"  # Green or Red
    reset = "\033[0m"
    print(f"{color}{symbol}{reset} {name}")
    if details:
        print(f"  → {details}")


def check_python_version():
    """Check Python version is 3.8+."""
    version = sys.version_info
    is_ok = version.major == 3 and version.minor >= 8
    details = f"Python {version.major}.{version.minor}.{version.micro}"
    return is_ok, details


def check_module(module_name):
    """Check if a Python module is installed."""
    try:
        __import__(module_name)
        return True, "Installed"
    except ImportError:
        return False, "Not installed"


def check_command(command):
    """Check if a command exists."""
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            return True, version
        return False, "Command failed"
    except FileNotFoundError:
        return False, "Not found"
    except Exception as e:
        return False, str(e)


def check_env_var(var_name):
    """Check if environment variable is set."""
    value = os.getenv(var_name)
    if value:
        masked = value[:8] + "..." if len(value) > 8 else value
        return True, f"Set ({masked})"
    return False, "Not set"


def check_directory(dir_path):
    """Check if directory exists."""
    path = Path(dir_path)
    if path.exists() and path.is_dir():
        return True, f"Exists at {path.absolute()}"
    return False, "Does not exist"


def check_file(file_path):
    """Check if file exists."""
    path = Path(file_path)
    if path.exists() and path.is_file():
        size = path.stat().st_size
        return True, f"Exists ({size} bytes)"
    return False, "Does not exist"


def main():
    """Run all verification checks."""
    print_header("Webflow CMS Automation - Setup Verification")
    
    all_passed = True
    
    # Python Version
    print_header("Python Version")
    status, details = check_python_version()
    print_check("Python 3.8+", status, details)
    if not status:
        all_passed = False
    
    # Python Dependencies
    print_header("Python Dependencies")
    modules = [
        ("flask", "Flask"),
        ("requests", "Requests"),
        ("openai", "OpenAI"),
        ("bs4", "BeautifulSoup4"),
        ("selenium", "Selenium"),
        ("PIL", "Pillow"),
    ]
    
    for import_name, display_name in modules:
        status, details = check_module(import_name)
        print_check(display_name, status, details)
        if not status:
            all_passed = False
    
    # System Commands
    print_header("System Requirements")
    
    # Chrome/Chromium
    chrome_found = False
    for cmd in ["google-chrome", "chromium", "chromium-browser", "chrome"]:
        status, details = check_command(cmd)
        if status:
            print_check(f"Chrome ({cmd})", True, details)
            chrome_found = True
            break
    
    if not chrome_found:
        print_check("Chrome/Chromium", False, "Not found in PATH")
        all_passed = False
    
    # ChromeDriver
    status, details = check_command("chromedriver")
    print_check("ChromeDriver", status, details)
    if not status:
        all_passed = False
    
    # Environment Variables
    print_header("Environment Variables")
    env_vars = [
        "OPENAI_API_KEY",
        "WEBFLOW_TOKEN",
    ]
    
    for var in env_vars:
        status, details = check_env_var(var)
        print_check(var, status, details)
        if not status:
            all_passed = False
    
    print("\nNote: collection_id and site_id come from webhook request")
    
    # Optional Environment Variables
    print("\nOptional:")
    for var in ["PORT", "LOG_LEVEL"]:
        status, details = check_env_var(var)
        print_check(var, status, details)
    
    # Project Files
    print_header("Project Files")
    files = [
        "server.py",
        "scrape_images_js.py",
        "select_best_image.py",
        "upload_mock_image.py",
        "chatgpt_to_webflow.py",
        "requirements.txt",
    ]
    
    for file in files:
        status, details = check_file(file)
        print_check(file, status, details)
        if not status:
            all_passed = False
    
    # Project Directories
    print_header("Project Directories")
    dirs = ["images", "best_match"]
    
    for dir_path in dirs:
        status, details = check_directory(dir_path)
        print_check(dir_path, status, details)
        if not status:
            print(f"  → Creating directory: {dir_path}")
            Path(dir_path).mkdir(exist_ok=True)
    
    # Summary
    print_header("Summary")
    
    if all_passed:
        print("\n✓ All required checks passed!")
        print("\nYou can now start the server:")
        print("  python server.py")
        print("\nOr run tests:")
        print("  python test_server.py")
        return 0
    else:
        print("\n✗ Some checks failed!")
        print("\nPlease fix the issues above before running the server.")
        print("\nRefer to INSTALLATION.md for detailed setup instructions.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nVerification cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during verification: {e}")
        sys.exit(1)

