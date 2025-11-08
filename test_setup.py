#!/usr/bin/env python3
"""
Quick setup verification script
Run this to check if your environment is configured correctly
"""

import sys
import os

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("❌ Python 3.11+ required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    required = [
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'alembic',
        'firebase_admin',
        'pydantic',
        'cryptography',
        'httpx'
    ]
    missing = []
    for package in required:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing.append(package)
    return len(missing) == 0

def check_env_file():
    """Check if .env file exists"""
    if os.path.exists('.env'):
        print("✅ .env file exists")
        return True
    else:
        print("❌ .env file not found")
        print("   Run: cp .env.example .env")
        return False

def check_firebase_credentials():
    """Check if Firebase credentials path exists"""
    try:
        from app.core.config import settings
        if os.path.exists(settings.firebase_credentials_path):
            print(f"✅ Firebase credentials found: {settings.firebase_credentials_path}")
            return True
        else:
            print(f"❌ Firebase credentials not found: {settings.firebase_credentials_path}")
            return False
    except Exception as e:
        print(f"⚠️  Could not check Firebase credentials: {e}")
        return False

def main():
    print("🔍 Checking FlowDash Backend Setup...\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        (".env File", check_env_file),
        ("Firebase Credentials", check_firebase_credentials),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{name}:")
        result = check_func()
        results.append(result)
    
    print("\n" + "="*50)
    if all(results):
        print("✅ All checks passed! You're ready to run the server.")
        print("\nNext steps:")
        print("  1. Start database: docker-compose -f docker-compose.dev.yml up -d")
        print("  2. Run migrations: alembic upgrade head")
        print("  3. Start server: uvicorn app.main:app --reload")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()


