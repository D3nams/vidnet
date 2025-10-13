#!/usr/bin/env python3
"""
Test deployment script to verify the application works before deploying to Render
"""
import os
import subprocess
import sys
import time
import requests

def test_local_deployment():
    """Test the application locally using the same configuration as production"""
    
    print("🧪 Testing VidNet deployment locally...")
    
    # Set environment variables
    os.environ['PORT'] = '8000'
    os.environ['ENVIRONMENT'] = 'production'
    
    # Start the application
    print("🚀 Starting application...")
    try:
        # Use the same command as in Dockerfile
        process = subprocess.Popen([
            'uvicorn', 'app.main:app', 
            '--host', '0.0.0.0', 
            '--port', '8000'
        ])
        
        # Wait for startup
        time.sleep(3)
        
        # Test health endpoint
        print("🔍 Testing health endpoint...")
        response = requests.get('http://localhost:8000/health', timeout=10)
        
        if response.status_code == 200:
            print("✅ Health check passed!")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
        # Test root endpoint
        print("🔍 Testing root endpoint...")
        response = requests.get('http://localhost:8000/', timeout=10)
        
        if response.status_code == 200:
            print("✅ Root endpoint working!")
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
            return False
            
        print("🎉 All tests passed! Ready for deployment.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        # Clean up
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            process.kill()

if __name__ == "__main__":
    success = test_local_deployment()
    sys.exit(0 if success else 1)