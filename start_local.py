#!/usr/bin/env python3
"""
Local Development Startup Script for VidNet
Starts the application with proper configuration for local testing
"""

import os
import sys
import subprocess
import time
import signal
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalServer:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.processes = []
        
    def setup_environment(self):
        """Set up environment variables for local development"""
        logger.info("🔧 Setting up local environment...")
        
        env_vars = {
            "ENVIRONMENT": "development",
            "REDIS_URL": "redis://localhost:6379",
            "PERFORMANCE_MONITORING_ENABLED": "true",
            "RATE_LIMIT_REQUESTS_PER_MINUTE": "1000",  # Higher limit for development
            "RATE_LIMIT_REQUESTS_PER_HOUR": "10000",
            "RATE_LIMIT_BURST_LIMIT": "50",
            "METADATA_CACHE_TTL": "300",  # Shorter TTL for development
            "DOWNLOAD_CACHE_TTL": "180",
            "DEBUG": "true"
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
            
        logger.info("✅ Environment variables set")
        
    def check_redis(self):
        """Check if Redis is running"""
        logger.info("🔍 Checking Redis connection...")
        
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            r.ping()
            logger.info("✅ Redis is running")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.info("💡 To start Redis:")
            logger.info("   - Docker: docker run -d -p 6379:6379 redis:alpine")
            logger.info("   - Local: redis-server")
            return False
            
    def start_redis_docker(self):
        """Start Redis using Docker"""
        logger.info("🐳 Starting Redis with Docker...")
        
        try:
            # Check if Redis container is already running
            result = subprocess.run([
                "docker", "ps", "--filter", "name=vidnet-redis", "--format", "{{.Names}}"
            ], capture_output=True, text=True)
            
            if "vidnet-redis" in result.stdout:
                logger.info("✅ Redis container already running")
                return True
                
            # Start Redis container
            process = subprocess.Popen([
                "docker", "run", "-d", 
                "--name", "vidnet-redis",
                "-p", "6379:6379",
                "redis:alpine"
            ])
            
            # Wait a moment for Redis to start
            time.sleep(3)
            
            if self.check_redis():
                logger.info("✅ Redis started successfully")
                return True
            else:
                logger.error("❌ Failed to start Redis")
                return False
                
        except FileNotFoundError:
            logger.error("❌ Docker not found. Please install Docker or start Redis manually.")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to start Redis: {e}")
            return False
            
    def install_dependencies(self):
        """Install Python dependencies"""
        logger.info("📦 Checking Python dependencies...")
        
        requirements_file = self.project_root / "requirements.txt"
        
        if not requirements_file.exists():
            logger.error("❌ requirements.txt not found")
            return False
            
        try:
            # Check if dependencies are already installed
            import fastapi, uvicorn, redis
            logger.info("✅ Core dependencies already installed")
            return True
        except ImportError:
            logger.info("📥 Installing dependencies...")
            
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ Dependencies installed successfully")
                return True
            else:
                logger.error(f"❌ Failed to install dependencies: {result.stderr}")
                return False
                
    def start_application(self):
        """Start the FastAPI application"""
        logger.info("🚀 Starting VidNet application...")
        
        try:
            # Start uvicorn server
            process = subprocess.Popen([
                sys.executable, "-m", "uvicorn",
                "app.main:app",
                "--host", "0.0.0.0",
                "--port", "8000",
                "--reload",
                "--log-level", "info"
            ])
            
            self.processes.append(process)
            
            # Wait a moment for server to start
            time.sleep(3)
            
            # Test if server is running
            import httpx
            try:
                response = httpx.get("http://localhost:8000/health", timeout=5)
                if response.status_code == 200:
                    logger.info("✅ Application started successfully")
                    logger.info("🌐 Application available at: http://localhost:8000")
                    logger.info("📊 API documentation at: http://localhost:8000/docs")
                    logger.info("🧪 Integration test at: http://localhost:8000/test_frontend_integration.html")
                    return True
                else:
                    logger.error(f"❌ Application health check failed: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"❌ Failed to connect to application: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to start application: {e}")
            return False
            
    def cleanup(self):
        """Clean up processes"""
        logger.info("🧹 Cleaning up...")
        
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                logger.warning(f"⚠️ Error cleaning up process: {e}")
                
    def run(self):
        """Run the complete local development setup"""
        logger.info("🎬 Starting VidNet Local Development Server")
        logger.info("=" * 50)
        
        try:
            # Setup environment
            self.setup_environment()
            
            # Install dependencies
            if not self.install_dependencies():
                return False
                
            # Check/start Redis
            if not self.check_redis():
                if not self.start_redis_docker():
                    logger.error("❌ Could not start Redis. Please start it manually.")
                    return False
                    
            # Start application
            if not self.start_application():
                return False
                
            logger.info("\n🎉 VidNet is running successfully!")
            logger.info("Press Ctrl+C to stop the server")
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("\n⚠️ Shutting down...")
                
            return True
            
        except Exception as e:
            logger.error(f"💥 Startup failed: {e}")
            return False
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    server = LocalServer()
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        logger.info("\n⚠️ Received interrupt signal")
        server.cleanup()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        success = server.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()