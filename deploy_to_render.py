#!/usr/bin/env python3
"""
VidNet Deployment Script for Render
Automates the deployment process and validates configuration
"""

import os
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RenderDeployment:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.required_files = [
            "render.yaml",
            "Dockerfile", 
            "requirements.txt",
            "app/main.py",
            "static/index.html"
        ]
        self.environment_vars = {
            "ENVIRONMENT": "production",
            "PERFORMANCE_MONITORING_ENABLED": "true",
            "RATE_LIMIT_REQUESTS_PER_MINUTE": "100",
            "RATE_LIMIT_REQUESTS_PER_HOUR": "2000",
            "RATE_LIMIT_BURST_LIMIT": "20",
            "METADATA_CACHE_TTL": "3600",
            "DOWNLOAD_CACHE_TTL": "1800"
        }
        
    def check_prerequisites(self) -> bool:
        """Check if all required files and configurations exist"""
        logger.info("🔍 Checking deployment prerequisites...")
        
        missing_files = []
        for file_path in self.required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                missing_files.append(file_path)
                
        if missing_files:
            logger.error(f"❌ Missing required files: {missing_files}")
            return False
            
        logger.info("✅ All required files present")
        return True
        
    def validate_render_config(self) -> bool:
        """Validate render.yaml configuration"""
        logger.info("📋 Validating Render configuration...")
        
        render_config_path = self.project_root / "render.yaml"
        
        try:
            with open(render_config_path, 'r') as f:
                import yaml
                config = yaml.safe_load(f)
                
            # Check required services
            if 'services' not in config:
                logger.error("❌ No services defined in render.yaml")
                return False
                
            services = config['services']
            
            # Check for web service
            web_service = None
            redis_service = None
            
            for service in services:
                if service.get('type') == 'web':
                    web_service = service
                elif service.get('type') == 'redis':
                    redis_service = service
                    
            if not web_service:
                logger.error("❌ No web service found in render.yaml")
                return False
                
            if not redis_service:
                logger.error("❌ No Redis service found in render.yaml")
                return False
                
            # Validate web service configuration
            required_web_fields = ['name', 'env', 'dockerfilePath']
            for field in required_web_fields:
                if field not in web_service:
                    logger.error(f"❌ Missing required field in web service: {field}")
                    return False
                    
            logger.info("✅ Render configuration is valid")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating render.yaml: {e}")
            return False
            
    def validate_dockerfile(self) -> bool:
        """Validate Dockerfile configuration"""
        logger.info("🐳 Validating Dockerfile...")
        
        dockerfile_path = self.project_root / "Dockerfile"
        
        try:
            with open(dockerfile_path, 'r') as f:
                dockerfile_content = f.read()
                
            required_instructions = [
                'FROM python:3.12-slim',
                'COPY requirements.txt',
                'RUN pip install',
                'COPY . .',
                'EXPOSE 8000',
                'CMD ["uvicorn"'
            ]
            
            for instruction in required_instructions:
                if instruction not in dockerfile_content:
                    logger.error(f"❌ Missing Dockerfile instruction: {instruction}")
                    return False
                    
            logger.info("✅ Dockerfile is valid")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating Dockerfile: {e}")
            return False
            
    def check_dependencies(self) -> bool:
        """Check if all Python dependencies are properly specified"""
        logger.info("📦 Checking Python dependencies...")
        
        requirements_path = self.project_root / "requirements.txt"
        
        try:
            with open(requirements_path, 'r') as f:
                requirements = f.read()
                
            critical_deps = [
                'fastapi',
                'uvicorn',
                'yt-dlp',
                'redis',
                'httpx',
                'pydantic'
            ]
            
            missing_deps = []
            for dep in critical_deps:
                if dep not in requirements:
                    missing_deps.append(dep)
                    
            if missing_deps:
                logger.error(f"❌ Missing critical dependencies: {missing_deps}")
                return False
                
            logger.info("✅ All critical dependencies present")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking dependencies: {e}")
            return False
            
    def validate_environment_variables(self) -> bool:
        """Validate environment variable configuration"""
        logger.info("🔧 Validating environment variables...")
        
        render_config_path = self.project_root / "render.yaml"
        
        try:
            with open(render_config_path, 'r') as f:
                import yaml
                config = yaml.safe_load(f)
                
            web_service = None
            for service in config['services']:
                if service.get('type') == 'web':
                    web_service = service
                    break
                    
            if not web_service or 'envVars' not in web_service:
                logger.error("❌ No environment variables defined in web service")
                return False
                
            env_vars = {var['key']: var.get('value', 'FROM_SERVICE') for var in web_service['envVars']}
            
            required_env_vars = [
                'ENVIRONMENT',
                'REDIS_URL',
                'PERFORMANCE_MONITORING_ENABLED'
            ]
            
            missing_vars = []
            for var in required_env_vars:
                if var not in env_vars:
                    missing_vars.append(var)
                    
            if missing_vars:
                logger.error(f"❌ Missing required environment variables: {missing_vars}")
                return False
                
            logger.info("✅ Environment variables are properly configured")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating environment variables: {e}")
            return False
            
    def run_local_tests(self) -> bool:
        """Run local tests before deployment"""
        logger.info("🧪 Running local tests...")
        
        try:
            # Check if test file exists
            test_file = self.project_root / "test_final_integration.py"
            if not test_file.exists():
                logger.warning("⚠️ Integration test file not found, skipping tests")
                return True
                
            # Run pytest if available
            try:
                result = subprocess.run([
                    sys.executable, "-m", "pytest", 
                    str(test_file), 
                    "-v", "--tb=short"
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    logger.info("✅ Local tests passed")
                    return True
                else:
                    logger.error(f"❌ Local tests failed:\n{result.stdout}\n{result.stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                logger.error("❌ Tests timed out")
                return False
            except FileNotFoundError:
                logger.warning("⚠️ pytest not available, skipping automated tests")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error running tests: {e}")
            return False
            
    def create_deployment_checklist(self) -> Dict[str, Any]:
        """Create a deployment checklist"""
        logger.info("📝 Creating deployment checklist...")
        
        checklist = {
            "pre_deployment": {
                "prerequisites_check": False,
                "render_config_validation": False,
                "dockerfile_validation": False,
                "dependencies_check": False,
                "environment_variables": False,
                "local_tests": False
            },
            "deployment_steps": [
                "1. Connect GitHub repository to Render",
                "2. Create new Web Service from repository",
                "3. Render will automatically detect render.yaml",
                "4. Verify environment variables are set correctly",
                "5. Monitor deployment logs for any issues",
                "6. Test deployed application endpoints",
                "7. Verify Redis connection and caching",
                "8. Test video download functionality",
                "9. Monitor performance metrics",
                "10. Set up monitoring and alerts"
            ],
            "post_deployment": [
                "Verify health check endpoint",
                "Test metadata extraction",
                "Test video download workflow", 
                "Test audio extraction",
                "Verify analytics tracking",
                "Test error handling",
                "Monitor performance metrics",
                "Set up log monitoring",
                "Configure domain (if custom domain needed)",
                "Set up SSL certificate (automatic with Render)"
            ]
        }
        
        return checklist
        
    def generate_deployment_guide(self) -> str:
        """Generate a comprehensive deployment guide"""
        guide = """
# VidNet Deployment Guide for Render

## Prerequisites ✅
- GitHub repository with your VidNet code
- Render account (free tier available)
- All required files present in repository

## Deployment Steps

### 1. Prepare Repository
```bash
# Ensure all files are committed and pushed
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### 2. Create Render Services

#### Option A: Automatic (Recommended)
1. Go to https://render.com/dashboard
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml`
5. Click "Apply" to create both web and Redis services

#### Option B: Manual Setup
1. Create Redis service first:
   - Name: `vidnet-redis`
   - Plan: Starter (free)
   - Region: Oregon
   
2. Create Web service:
   - Name: `vidnet-api`
   - Environment: Docker
   - Dockerfile path: `./Dockerfile`
   - Build command: `docker build -t vidnet-api .`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`

### 3. Environment Variables
The following environment variables will be automatically set from render.yaml:
- `ENVIRONMENT=production`
- `REDIS_URL` (automatically from Redis service)
- `PERFORMANCE_MONITORING_ENABLED=true`
- Rate limiting configurations
- Cache TTL settings

### 4. Monitor Deployment
1. Watch deployment logs in Render dashboard
2. Wait for "Deploy succeeded" message
3. Test the health endpoint: `https://your-app.onrender.com/health`

### 5. Post-Deployment Testing
Run these tests to verify deployment:

```bash
# Test health endpoint
curl https://your-app.onrender.com/health

# Test API status
curl https://your-app.onrender.com/api/v1/monitoring/status

# Test metadata extraction
curl -X POST https://your-app.onrender.com/api/v1/metadata \\
  -H "Content-Type: application/json" \\
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

## Important Notes

### Performance Considerations
- Free tier has limitations (750 hours/month)
- Services sleep after 15 minutes of inactivity
- First request after sleep may be slow (cold start)
- Consider upgrading to paid plan for production use

### Monitoring
- Use Render's built-in metrics dashboard
- Monitor logs for errors and performance issues
- Set up alerts for service downtime

### Scaling
- Render automatically handles HTTPS/SSL
- Can easily scale to multiple instances
- Built-in load balancing

### Troubleshooting
Common issues and solutions:

1. **Build fails**: Check Dockerfile and requirements.txt
2. **Service won't start**: Check environment variables and Redis connection
3. **Slow performance**: Consider upgrading plan or optimizing code
4. **Memory issues**: Monitor usage and optimize if needed

## Security
- All traffic is automatically HTTPS
- Environment variables are encrypted
- Regular security updates applied automatically
- No need to manage SSL certificates

## Cost Estimation
- Free tier: $0/month (with limitations)
- Starter plan: ~$7/month for web service + $7/month for Redis
- Professional plan: ~$25/month for better performance

## Support
- Render documentation: https://render.com/docs
- Community forum: https://community.render.com
- Email support for paid plans
"""
        return guide
        
    def run_deployment_validation(self) -> bool:
        """Run complete deployment validation"""
        logger.info("🚀 Starting deployment validation...")
        
        validation_steps = [
            ("Prerequisites", self.check_prerequisites),
            ("Render Config", self.validate_render_config),
            ("Dockerfile", self.validate_dockerfile),
            ("Dependencies", self.check_dependencies),
            ("Environment Variables", self.validate_environment_variables),
            ("Local Tests", self.run_local_tests)
        ]
        
        all_passed = True
        results = {}
        
        for step_name, step_func in validation_steps:
            logger.info(f"\n{'='*50}")
            logger.info(f"Validating: {step_name}")
            logger.info(f"{'='*50}")
            
            try:
                result = step_func()
                results[step_name] = result
                
                if result:
                    logger.info(f"✅ {step_name} validation passed")
                else:
                    logger.error(f"❌ {step_name} validation failed")
                    all_passed = False
                    
            except Exception as e:
                logger.error(f"💥 {step_name} validation crashed: {e}")
                results[step_name] = False
                all_passed = False
                
        # Generate summary
        logger.info(f"\n{'='*60}")
        logger.info("DEPLOYMENT VALIDATION SUMMARY")
        logger.info(f"{'='*60}")
        
        for step_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{step_name}: {status}")
            
        if all_passed:
            logger.info("\n🎉 ALL VALIDATIONS PASSED!")
            logger.info("Your application is ready for deployment to Render!")
            
            # Generate deployment guide
            guide = self.generate_deployment_guide()
            guide_path = self.project_root / "DEPLOYMENT_GUIDE.md"
            
            with open(guide_path, 'w') as f:
                f.write(guide)
                
            logger.info(f"📖 Deployment guide saved to: {guide_path}")
            
        else:
            logger.error("\n⚠️ SOME VALIDATIONS FAILED!")
            logger.error("Please fix the issues above before deploying.")
            
        return all_passed

def main():
    """Main deployment validation runner"""
    print("🚀 VidNet Render Deployment Validator")
    print("=" * 50)
    
    deployment = RenderDeployment()
    
    try:
        success = deployment.run_deployment_validation()
        
        if success:
            print("\n✅ Ready for deployment!")
            print("\nNext steps:")
            print("1. Push your code to GitHub")
            print("2. Go to https://render.com/dashboard")
            print("3. Create a new Web Service from your repository")
            print("4. Render will automatically use your render.yaml configuration")
            print("5. Monitor the deployment logs")
            print("\nSee DEPLOYMENT_GUIDE.md for detailed instructions.")
            sys.exit(0)
        else:
            print("\n❌ Not ready for deployment!")
            print("Please fix the validation errors above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Deployment validation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Deployment validation failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()