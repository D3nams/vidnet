#!/usr/bin/env python3
"""
Simple test to verify the app works
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("🧪 Testing basic FastAPI import...")
    from fastapi import FastAPI
    print("✅ FastAPI imported successfully")
    
    print("🧪 Testing app import...")
    from app.main import app
    print("✅ App imported successfully")
    print(f"App type: {type(app)}")
    print(f"App title: {app.title}")
    
    print("🧪 Testing uvicorn...")
    import uvicorn
    print("✅ Uvicorn imported successfully")
    
    print("🚀 Starting test server on port 8000...")
    print("Visit: http://localhost:8000")
    print("Health check: http://localhost:8000/health")
    print("Press Ctrl+C to stop")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()