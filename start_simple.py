#!/usr/bin/env python3
"""
Simple Local Development Server for VidNet
Starts the application without Redis dependency for basic testing
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up environment variables for local development without Redis"""
    logger.info("🔧 Setting up local environment (Redis-free mode)...")
    
    env_vars = {
        "ENVIRONMENT": "development",
        "REDIS_URL": "redis://fake-redis:6379",  # Fake Redis URL for testing
        "PERFORMANCE_MONITORING_ENABLED": "false",  # Disable to avoid Redis dependency
        "RATE_LIMIT_REQUESTS_PER_MINUTE": "1000",
        "RATE_LIMIT_REQUESTS_PER_HOUR": "10000", 
        "RATE_LIMIT_BURST_LIMIT": "50",
        "METADATA_CACHE_TTL": "300",
        "DOWNLOAD_CACHE_TTL": "180",
        "DEBUG": "true",
        "DISABLE_REDIS": "true"  # Flag to disable Redis-dependent features
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        
    logger.info("✅ Environment variables set (Redis disabled)")

def check_dependencies():
    """Check if core dependencies are available"""
    logger.info("📦 Checking core dependencies...")
    
    try:
        import fastapi
        import uvicorn
        logger.info("✅ FastAPI and Uvicorn available")
        return True
    except ImportError as e:
        logger.error(f"❌ Missing dependencies: {e}")
        logger.info("💡 Install with: pip install fastapi uvicorn")
        return False

def start_application():
    """Start the FastAPI application"""
    logger.info("🚀 Starting VidNet application (development mode)...")
    
    try:
        # Start uvicorn server
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload",
            "--log-level", "info"
        ]
        
        logger.info("Starting server with command: " + " ".join(cmd))
        
        # Start the process
        process = subprocess.Popen(cmd)
        
        # Wait a moment for server to start
        logger.info("⏳ Waiting for server to start...")
        time.sleep(5)
        
        # Test if server is running
        try:
            import httpx
            response = httpx.get("http://127.0.0.1:8000/health", timeout=10)
            if response.status_code == 200:
                logger.info("✅ Application started successfully!")
                logger.info("🌐 Application available at: http://127.0.0.1:8000")
                logger.info("📊 API documentation at: http://127.0.0.1:8000/docs")
                logger.info("🧪 Test page at: http://127.0.0.1:8000/test_frontend_integration.html")
                
                print("\n" + "="*60)
                print("🎉 VidNet is running in development mode!")
                print("="*60)
                print("📱 Main App: http://127.0.0.1:8000")
                print("📚 API Docs: http://127.0.0.1:8000/docs")
                print("🧪 Test Page: http://127.0.0.1:8000/test_frontend_integration.html")
                print("="*60)
                print("⚠️  Note: Running without Redis (some features disabled)")
                print("🛑 Press Ctrl+C to stop the server")
                print("="*60)
                
                # Keep the process running
                try:
                    process.wait()
                except KeyboardInterrupt:
                    logger.info("\n⚠️ Shutting down server...")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    logger.info("✅ Server stopped")
                
                return True
            else:
                logger.error(f"❌ Health check failed: {response.status_code}")
                process.terminate()
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to application: {e}")
            logger.info("💡 The server might still be starting. Try accessing http://127.0.0.1:8000 manually")
            
            # Keep the process running anyway
            try:
                process.wait()
            except KeyboardInterrupt:
                logger.info("\n⚠️ Shutting down server...")
                process.terminate()
                
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        return False

def main():
    """Main entry point"""
    print("🎬 VidNet Simple Development Server")
    print("=" * 50)
    print("This version runs without Redis for basic testing")
    print("For full functionality, use Docker or install Redis")
    print("=" * 50)
    
    try:
        # Setup environment
        setup_environment()
        
        # Check dependencies
        if not check_dependencies():
            logger.error("❌ Missing required dependencies")
            return False
            
        # Start application
        return start_application()
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")
        return True
    except Exception as e:
        logger.error(f"💥 Startup failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)