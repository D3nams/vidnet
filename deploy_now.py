#!/usr/bin/env python3
"""
Quick Deployment Script for VidNet
Simplified deployment process for immediate deployment
"""

import os
import subprocess
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_git_status():
    """Check if we're in a git repository and files are committed"""
    logger.info("📋 Checking Git status...")
    
    try:
        # Check if we're in a git repo
        result = subprocess.run(['git', 'status'], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("❌ Not in a Git repository")
            logger.info("💡 Initialize Git with:")
            logger.info("   git init")
            logger.info("   git add .")
            logger.info("   git commit -m 'Initial commit'")
            return False
            
        # Check for uncommitted changes
        if "nothing to commit" not in result.stdout:
            logger.warning("⚠️ You have uncommitted changes")
            logger.info("💡 Commit your changes with:")
            logger.info("   git add .")
            logger.info("   git commit -m 'Ready for deployment'")
            logger.info("   git push origin main")
            
        logger.info("✅ Git repository ready")
        return True
        
    except FileNotFoundError:
        logger.error("❌ Git not found. Please install Git first.")
        return False

def check_required_files():
    """Check if all required files exist"""
    logger.info("📁 Checking required files...")
    
    required_files = [
        "render.yaml",
        "Dockerfile", 
        "requirements.txt",
        "app/main.py",
        "static/index.html"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
            
    if missing_files:
        logger.error(f"❌ Missing files: {missing_files}")
        return False
        
    logger.info("✅ All required files present")
    return True

def show_deployment_instructions():
    """Show step-by-step deployment instructions"""
    logger.info("\n🚀 VidNet Deployment Instructions")
    logger.info("=" * 50)
    
    print("""
🎯 STEP 1: Prepare Your Repository
1. Make sure all changes are committed:
   git add .
   git commit -m "Ready for deployment"
   git push origin main

🎯 STEP 2: Deploy to Render
1. Go to: https://render.com/dashboard
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Render will automatically detect render.yaml
5. Click "Create Web Service"

🎯 STEP 3: Monitor Deployment
1. Watch the deployment logs in Render dashboard
2. Wait for "Deploy succeeded" message
3. Your app will be available at: https://your-app-name.onrender.com

🎯 STEP 4: Test Your Deployment
1. Visit your app URL
2. Test video metadata extraction
3. Verify all features work correctly

📋 What Render Will Do Automatically:
✅ Create web service with Docker
✅ Create Redis service for caching
✅ Set up environment variables
✅ Configure health checks
✅ Set up automatic deployments from GitHub

💰 Estimated Cost:
- Free tier: $0/month (with limitations)
- Starter plan: ~$14/month (recommended for production)

🆘 If You Need Help:
- Check deployment logs in Render dashboard
- Visit: https://render.com/docs
- Community: https://community.render.com
""")

def create_git_commands():
    """Create a batch file with git commands"""
    git_commands = """@echo off
echo ========================================
echo    Preparing VidNet for Deployment
echo ========================================
echo.

echo Checking Git status...
git status

echo.
echo Adding all files...
git add .

echo.
echo Committing changes...
git commit -m "Ready for VidNet deployment"

echo.
echo Pushing to GitHub...
git push origin main

echo.
echo ========================================
echo   Ready for Render Deployment!
echo ========================================
echo.
echo Next steps:
echo 1. Go to https://render.com/dashboard
echo 2. Create new Web Service from your GitHub repo
echo 3. Render will auto-detect render.yaml
echo.
pause
"""
    
    with open("prepare_deployment.bat", "w") as f:
        f.write(git_commands)
        
    logger.info("✅ Created prepare_deployment.bat")

def main():
    """Main deployment preparation"""
    logger.info("🎬 VidNet Deployment Preparation")
    logger.info("=" * 40)
    
    # Check required files
    if not check_required_files():
        logger.error("❌ Missing required files. Cannot proceed.")
        return False
        
    # Check git status
    git_ready = check_git_status()
    
    # Create helper scripts
    create_git_commands()
    
    # Show instructions
    show_deployment_instructions()
    
    if git_ready:
        logger.info("\n🎉 You're ready to deploy!")
        logger.info("Run: prepare_deployment.bat (or use git commands manually)")
    else:
        logger.info("\n⚠️ Set up Git first, then run prepare_deployment.bat")
        
    return True

if __name__ == "__main__":
    main()