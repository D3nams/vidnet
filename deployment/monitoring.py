"""
Production monitoring and health check utilities for VidNet.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional
import psutil
import redis
import httpx
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive health checking for VidNet services."""
    
    def __init__(self, redis_url: str, app_url: str = "http://localhost:8000"):
        self.redis_url = redis_url
        self.app_url = app_url
        self.redis_client = None
        self.http_client = httpx.AsyncClient(timeout=10.0)
        
    async def initialize(self):
        """Initialize health checker components."""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            logger.info("Health checker initialized")
        except Exception as e:
            logger.error(f"Failed to initialize health checker: {e}")
            raise
    
    async def check_application_health(self) -> Dict[str, Any]:
        """Check main application health."""
        try:
            response = await self.http_client.get(f"{self.app_url}/health")
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time": response.elapsed.total_seconds(),
                "status_code": response.status_code,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis connection and performance."""
        try:
            start_time = time.time()
            
            # Test basic connectivity
            ping_result = self.redis_client.ping()
            ping_time = time.time() - start_time
            
            # Get Redis info
            info = self.redis_client.info()
            
            # Check memory usage
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            memory_usage_percent = (used_memory / max_memory * 100) if max_memory > 0 else 0
            
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "ping_time": ping_time,
                "connected_clients": info.get('connected_clients', 0),
                "used_memory_mb": used_memory / 1024 / 1024,
                "memory_usage_percent": memory_usage_percent,
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Network stats
            network = psutil.net_io_counters()
            
            return {
                "status": "healthy",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_mb": memory.available / 1024 / 1024,
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_free_gb": disk.free / 1024 / 1024 / 1024,
                "network_bytes_sent": network.bytes_sent,
                "network_bytes_recv": network.bytes_recv,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def check_api_endpoints(self) -> Dict[str, Any]:
        """Check critical API endpoints."""
        endpoints = [
            "/api/v1/monitoring/status",
            "/api/v1/monitoring/metrics",
        ]
        
        results = {}
        
        for endpoint in endpoints:
            try:
                start_time = time.time()
                response = await self.http_client.get(f"{self.app_url}{endpoint}")
                response_time = time.time() - start_time
                
                results[endpoint] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                results[endpoint] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return results
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        results = {
            "overall_status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # Run all checks
        checks = {
            "application": self.check_application_health(),
            "redis": self.check_redis_health(),
            "system": self.check_system_resources(),
            "api_endpoints": self.check_api_endpoints()
        }
        
        # Execute checks concurrently
        for check_name, check_coro in checks.items():
            try:
                results["checks"][check_name] = await check_coro
            except Exception as e:
                results["checks"][check_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # Determine overall status
        unhealthy_checks = [
            name for name, result in results["checks"].items()
            if result.get("status") != "healthy"
        ]
        
        if unhealthy_checks:
            results["overall_status"] = "unhealthy"
            results["unhealthy_checks"] = unhealthy_checks
        
        return results
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.http_client:
            await self.http_client.aclose()


class ProductionMonitor:
    """Production monitoring with alerting capabilities."""
    
    def __init__(self, health_checker: HealthChecker):
        self.health_checker = health_checker
        self.alert_thresholds = {
            "cpu_critical": 90.0,
            "memory_critical": 90.0,
            "disk_critical": 95.0,
            "response_time_critical": 5.0,
            "redis_memory_critical": 90.0
        }
        self.monitoring_active = False
        self.monitoring_task = None
    
    async def start_monitoring(self, interval: int = 60):
        """Start continuous monitoring."""
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval)
        )
        logger.info(f"Production monitoring started (interval: {interval}s)")
    
    async def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Production monitoring stopped")
    
    async def _monitoring_loop(self, interval: int):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                health_status = await self.health_checker.comprehensive_health_check()
                await self._process_health_status(health_status)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(interval)
    
    async def _process_health_status(self, health_status: Dict[str, Any]):
        """Process health status and trigger alerts if needed."""
        checks = health_status.get("checks", {})
        
        # Check system resources
        system_check = checks.get("system", {})
        if system_check.get("status") == "healthy":
            await self._check_resource_alerts(system_check)
        
        # Check Redis performance
        redis_check = checks.get("redis", {})
        if redis_check.get("status") == "healthy":
            await self._check_redis_alerts(redis_check)
        
        # Check API performance
        api_checks = checks.get("api_endpoints", {})
        await self._check_api_alerts(api_checks)
        
        # Log overall status
        overall_status = health_status.get("overall_status")
        if overall_status != "healthy":
            logger.warning(f"System health degraded: {health_status}")
        else:
            logger.info("System health check passed")
    
    async def _check_resource_alerts(self, system_check: Dict[str, Any]):
        """Check system resource alerts."""
        cpu_percent = system_check.get("cpu_percent", 0)
        memory_percent = system_check.get("memory_percent", 0)
        disk_percent = system_check.get("disk_percent", 0)
        
        if cpu_percent > self.alert_thresholds["cpu_critical"]:
            await self._send_alert(
                "CPU_CRITICAL",
                f"CPU usage critical: {cpu_percent:.1f}%"
            )
        
        if memory_percent > self.alert_thresholds["memory_critical"]:
            await self._send_alert(
                "MEMORY_CRITICAL",
                f"Memory usage critical: {memory_percent:.1f}%"
            )
        
        if disk_percent > self.alert_thresholds["disk_critical"]:
            await self._send_alert(
                "DISK_CRITICAL",
                f"Disk usage critical: {disk_percent:.1f}%"
            )
    
    async def _check_redis_alerts(self, redis_check: Dict[str, Any]):
        """Check Redis performance alerts."""
        memory_usage = redis_check.get("memory_usage_percent", 0)
        ping_time = redis_check.get("ping_time", 0)
        
        if memory_usage > self.alert_thresholds["redis_memory_critical"]:
            await self._send_alert(
                "REDIS_MEMORY_CRITICAL",
                f"Redis memory usage critical: {memory_usage:.1f}%"
            )
        
        if ping_time > 1.0:  # 1 second ping time is concerning
            await self._send_alert(
                "REDIS_SLOW",
                f"Redis ping time high: {ping_time:.3f}s"
            )
    
    async def _check_api_alerts(self, api_checks: Dict[str, Any]):
        """Check API performance alerts."""
        for endpoint, check in api_checks.items():
            if check.get("status") != "healthy":
                await self._send_alert(
                    "API_ENDPOINT_DOWN",
                    f"API endpoint unhealthy: {endpoint}"
                )
            
            response_time = check.get("response_time", 0)
            if response_time > self.alert_thresholds["response_time_critical"]:
                await self._send_alert(
                    "API_SLOW_RESPONSE",
                    f"Slow API response: {endpoint} ({response_time:.3f}s)"
                )
    
    async def _send_alert(self, alert_type: str, message: str):
        """Send alert notification."""
        timestamp = datetime.utcnow().isoformat()
        alert_data = {
            "type": alert_type,
            "message": message,
            "timestamp": timestamp,
            "service": "vidnet-api"
        }
        
        # Log alert
        logger.error(f"ALERT [{alert_type}]: {message}")
        
        # Here you would integrate with your alerting system
        # Examples: Slack, PagerDuty, email, etc.
        # await self._send_slack_alert(alert_data)
        # await self._send_email_alert(alert_data)


# Health check endpoint for container orchestration
async def container_health_check() -> bool:
    """Simple health check for container orchestration platforms."""
    try:
        # Check if the application is responsive
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/health")
            return response.status_code == 200
    except Exception:
        return False


# Startup probe for Kubernetes/Docker
async def startup_probe() -> bool:
    """Startup probe to check if application is ready to serve traffic."""
    try:
        # More comprehensive check for startup
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check health endpoint
            health_response = await client.get("http://localhost:8000/health")
            if health_response.status_code != 200:
                return False
            
            # Check if API is responsive
            status_response = await client.get("http://localhost:8000/api/v1/monitoring/status")
            return status_response.status_code == 200
    except Exception:
        return False


# Readiness probe for Kubernetes/Docker
async def readiness_probe() -> bool:
    """Readiness probe to check if application can handle requests."""
    try:
        # Check if all dependencies are available
        health_checker = HealthChecker(
            redis_url="redis://localhost:6379",  # Will be overridden by env
            app_url="http://localhost:8000"
        )
        
        await health_checker.initialize()
        
        # Quick health check
        redis_health = await health_checker.check_redis_health()
        app_health = await health_checker.check_application_health()
        
        await health_checker.cleanup()
        
        return (
            redis_health.get("status") == "healthy" and
            app_health.get("status") == "healthy"
        )
    except Exception:
        return False


if __name__ == "__main__":
    import os
    
    async def main():
        """Run monitoring demo."""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        
        health_checker = HealthChecker(redis_url)
        await health_checker.initialize()
        
        monitor = ProductionMonitor(health_checker)
        
        try:
            # Run comprehensive health check
            health_status = await health_checker.comprehensive_health_check()
            print("Health Status:")
            print(health_status)
            
            # Start monitoring for 60 seconds
            await monitor.start_monitoring(interval=10)
            await asyncio.sleep(60)
            
        finally:
            await monitor.stop_monitoring()
            await health_checker.cleanup()
    
    asyncio.run(main())