#!/usr/bin/env python3
"""
Test script to verify imports work correctly
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing import...")
    from app.main import app
    print("✅ Successfully imported app from app.main")
    print(f"App type: {type(app)}")
    print(f"App title: {app.title}")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\nTesting wsgi import...")
    import wsgi
    print("✅ Successfully imported wsgi module")
    print(f"Application type: {type(wsgi.application)}")
except Exception as e:
    print(f"❌ WSGI import failed: {e}")
    import traceback
    traceback.print_exc()