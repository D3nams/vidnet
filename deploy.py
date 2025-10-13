#!/usr/bin/env python3
"""
Simple deployment script for VidNet
"""
import subprocess
import sys

def deploy():
    """Deploy to Render"""
    
    print("🚀 Deploying VidNet to Render...")
    
    try:
        # Add all changes
        subprocess.run(['git', 'add', '.'], check=True)
        
        # Commit changes
        subprocess.run([
            'git', 'commit', '-m', 
            'Clean deployment: Remove unnecessary files, use waitress-serve'
        ], check=True)
        
        # Push to main branch
        subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        
        print("✅ Deployed successfully!")
        print("🔗 Check your Render dashboard for deployment status")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment failed: {e}")
        return False

if __name__ == "__main__":
    success = deploy()
    sys.exit(0 if success else 1)