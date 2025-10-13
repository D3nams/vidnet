#!/usr/bin/env python3
"""
Clean deployment script for VidNet to Render
This ensures no conflicting configurations exist
"""
import os
import subprocess
import sys

def clean_deploy():
    """Clean deployment process"""
    
    print("🧹 Cleaning deployment configuration...")
    
    # Remove any potential conflicting files
    conflicting_files = [
        'Procfile',
        'app.py',
        'wsgi.py',
        'gunicorn.conf.py'
    ]
    
    for file in conflicting_files:
        if os.path.exists(file):
            print(f"🗑️  Removing conflicting file: {file}")
            os.remove(file)
    
    print("✅ Deployment configuration cleaned!")
    
    # Verify key files exist
    required_files = [
        'render.yaml',
        'Dockerfile.minimal',
        'requirements.txt',
        'app/main.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    
    print("✅ All required files present!")
    
    # Git operations
    print("📦 Preparing Git commit...")
    
    try:
        # Add all changes
        subprocess.run(['git', 'add', '.'], check=True)
        
        # Commit changes
        subprocess.run([
            'git', 'commit', '-m', 
            'Fix deployment: Remove waitress dependency, use uvicorn only'
        ], check=True)
        
        # Push to main branch
        subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        
        print("✅ Changes pushed to GitHub!")
        print("🚀 Render should now deploy automatically!")
        print("\n📋 Next steps:")
        print("1. Check your Render dashboard for deployment progress")
        print("2. Monitor logs for any issues")
        print("3. Test the deployed application once ready")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")
        return False

if __name__ == "__main__":
    success = clean_deploy()
    sys.exit(0 if success else 1)