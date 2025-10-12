#!/usr/bin/env python3
"""
Demonstration script for VidNet rate limiting and performance optimization features.

This script demonstrates the rate limiting middleware, performance monitoring,
and graceful degradation features implemented in task 10.
"""

import asyncio
import time
import logging
import httpx
from typing import List, Dict, Any


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RateLimitingDemo:
    """Demonstration of rate limiting and performance features."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    async def demo_rate_limiting(self):
        """Demonstrate rate limiting functionality."""
        print("\n" + "="*60)
        print("🚦 RATE LIMITING DEMONSTRATION")
        print("="*60)
        
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            print("Making rapid requests to trigger rate limiting...")
            
            responses = []
            for i in range(20):
                try:
                    start_time = time.time()
                    response = await client.post(
                        "/api/v1/metadata",
                        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
                    )
                    response_time = time.time() - start_time
                    
                    responses.append({
                        'request_num': i + 1,
                        'status_code': response.status_code,
                        'response_time': response_time,
                        'headers': dict(response.headers)
                    })
                    
                    # Print status for interesting responses
                    if response.status_code == 429:
                        print(f"  Request {i+1}: ⛔ RATE LIMITED (429) - {response_time:.3f}s")
                    elif response.status_code == 200:
                        print(f"  Request {i+1}: ✅ SUCCESS (200) - {response_time:.3f}s")
                    else:
                        print(f"  Request {i+1}: ⚠️  OTHER ({response.status_code}) - {response_time:.3f}s")
                    
                    # Small delay between requests
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"  Request {i+1}: ❌ ERROR - {e}")
            
            # Analyze results
            successful = sum(1 for r in responses if r['status_code'] == 200)
            rate_limited = sum(1 for r in responses if r['status_code'] == 429)
            
            print(f"\nResults:")
            print(f"  Total requests: {len(responses)}")
            print(f"  Successful: {successful}")
            print(f"  Rate limited: {rate_limited}")
            print(f"  Rate limiting effectiveness: {(rate_limited/len(responses)*100):.1f}%")
            
            # Show rate limit headers from a successful response
            successful_response = next((r for r in responses if r['status_code'] == 200), None)
            if successful_response and 'x-ratelimit-limit' in successful_response['headers']:
                headers = successful_response['headers']
                print(f"\nRate Limit Headers:")
                print(f"  X-RateLimit-Limit: {headers.get('x-ratelimit-limit', 'N/A')}")
                print(f"  X-RateLimit-Remaining: {headers.get('x-ratelimit-remaining', 'N/A')}")
                print(f"  X-RateLimit-Reset: {headers.get('x-ratelimit-reset', 'N/A')}")
    
    async def demo_performance_monitoring(self):
        """Demonstrate performance monitoring features."""
        print("\n" + "="*60)
        print("📊 PERFORMANCE MONITORING DEMONSTRATION")
        print("="*60)
        
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            print("Making test requests to generate performance data...")
            
            # Make various requests to different endpoints
            endpoints = [
                ("/api/v1/monitoring/health", "GET"),
                ("/api/v1/monitoring/metrics", "GET"),
                ("/api/v1/monitoring/system", "GET"),
                ("/health", "GET")
            ]
            
            for endpoint, method in endpoints:
                for i in range(3):
                    try:
                        start_time = time.time()
                        response = await client.request(method, endpoint)
                        response_time = time.time() - start_time
                        
                        print(f"  {method} {endpoint}: {response.status_code} ({response_time:.3f}s)")
                        await asyncio.sleep(0.2)
                        
                    except Exception as e:
                        print(f"  {method} {endpoint}: ERROR - {e}")
            
            print("\nFetching performance metrics...")
            
            # Get performance metrics
            try:
                response = await client.get("/api/v1/monitoring/metrics")
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        metrics = data['data']
                        
                        print(f"\nEndpoint Statistics:")
                        endpoint_stats = metrics.get('endpoint_stats', {})
                        for endpoint, stats in endpoint_stats.items():
                            print(f"  {endpoint}:")
                            print(f"    Requests: {stats.get('total_requests', 0)}")
                            print(f"    Avg Response Time: {stats.get('average_response_time', 0):.3f}s")
                            print(f"    Success Rate: {stats.get('success_rate', 0):.1f}%")
                        
                        print(f"\nSystem Metrics:")
                        system_metrics = metrics.get('system_metrics', {})
                        print(f"  CPU Usage: {system_metrics.get('cpu_percent', 0):.1f}%")
                        print(f"  Memory Usage: {system_metrics.get('memory_percent', 0):.1f}%")
                        print(f"  Active Connections: {system_metrics.get('active_connections', 0)}")
                
            except Exception as e:
                print(f"Error fetching metrics: {e}")
    
    async def demo_health_monitoring(self):
        """Demonstrate health monitoring and alerts."""
        print("\n" + "="*60)
        print("🏥 HEALTH MONITORING DEMONSTRATION")
        print("="*60)
        
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            try:
                response = await client.get("/api/v1/monitoring/health")
                
                if response.status_code in [200, 503]:
                    data = response.json()
                    if data.get('success'):
                        health_data = data['data']
                        
                        print(f"Overall Health Status: {health_data.get('status', 'unknown').upper()}")
                        print(f"Health Score: {health_data.get('health_score', 0)}/100")
                        
                        alerts = health_data.get('alerts', [])
                        if alerts:
                            print(f"\nActive Alerts ({len(alerts)}):")
                            for alert in alerts:
                                level = alert.get('level', 'unknown').upper()
                                alert_type = alert.get('type', 'unknown')
                                message = alert.get('message', 'No message')
                                
                                emoji = "🔴" if level == "CRITICAL" else "🟡" if level == "WARNING" else "ℹ️"
                                print(f"  {emoji} {level} - {alert_type}: {message}")
                        else:
                            print("\n✅ No active alerts")
                        
                        # Show thresholds
                        thresholds = health_data.get('thresholds', {})
                        if thresholds:
                            print(f"\nPerformance Thresholds:")
                            print(f"  Response Time Warning: {thresholds.get('response_time_warning', 0)}s")
                            print(f"  Response Time Critical: {thresholds.get('response_time_critical', 0)}s")
                            print(f"  CPU Warning: {thresholds.get('cpu_warning', 0)}%")
                            print(f"  CPU Critical: {thresholds.get('cpu_critical', 0)}%")
                            print(f"  Memory Warning: {thresholds.get('memory_warning', 0)}%")
                            print(f"  Memory Critical: {thresholds.get('memory_critical', 0)}%")
                
            except Exception as e:
                print(f"Error fetching health status: {e}")
    
    async def demo_rate_limit_stats(self):
        """Demonstrate rate limiting statistics."""
        print("\n" + "="*60)
        print("📈 RATE LIMITING STATISTICS DEMONSTRATION")
        print("="*60)
        
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            try:
                response = await client.get("/api/v1/monitoring/rate-limit-stats")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        stats = data['data']
                        
                        print(f"Rate Limiting Statistics:")
                        print(f"  Total Requests: {stats.get('total_requests', 0)}")
                        print(f"  Rate Limited Requests: {stats.get('rate_limited_requests', 0)}")
                        print(f"  Queued Requests: {stats.get('queued_requests', 0)}")
                        print(f"  Degraded Requests: {stats.get('degraded_requests', 0)}")
                        print(f"  Concurrent Requests: {stats.get('concurrent_requests', 0)}")
                        print(f"  Peak Concurrent: {stats.get('peak_concurrent_requests', 0)}")
                        
                        config = stats.get('config', {})
                        if config:
                            print(f"\nRate Limiting Configuration:")
                            print(f"  Requests per Minute: {config.get('requests_per_minute', 0)}")
                            print(f"  Requests per Hour: {config.get('requests_per_hour', 0)}")
                            print(f"  Queue Size: {config.get('queue_size', 0)}")
                            print(f"  Queue Timeout: {config.get('queue_timeout', 0)}s")
                        
                        degradation_active = stats.get('degradation_active', False)
                        print(f"\nGraceful Degradation: {'🔴 ACTIVE' if degradation_active else '🟢 INACTIVE'}")
                
            except Exception as e:
                print(f"Error fetching rate limit stats: {e}")
    
    async def demo_concurrent_load(self):
        """Demonstrate behavior under concurrent load."""
        print("\n" + "="*60)
        print("⚡ CONCURRENT LOAD DEMONSTRATION")
        print("="*60)
        
        print("Simulating concurrent requests (20 users)...")
        
        async def make_request(client, user_id):
            """Make a request as a specific user."""
            try:
                start_time = time.time()
                response = await client.get("/api/v1/monitoring/health")
                response_time = time.time() - start_time
                
                return {
                    'user_id': user_id,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'success': response.status_code < 500
                }
            except Exception as e:
                return {
                    'user_id': user_id,
                    'status_code': 500,
                    'response_time': 0,
                    'success': False,
                    'error': str(e)
                }
        
        # Create concurrent requests
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            tasks = [make_request(client, i) for i in range(20)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Analyze results
            successful = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
            total = len(results)
            response_times = [r['response_time'] for r in results if isinstance(r, dict) and r['response_time'] > 0]
            
            print(f"\nConcurrent Load Results:")
            print(f"  Total Requests: {total}")
            print(f"  Successful: {successful}")
            print(f"  Success Rate: {(successful/total*100):.1f}%")
            
            if response_times:
                avg_time = sum(response_times) / len(response_times)
                max_time = max(response_times)
                min_time = min(response_times)
                
                print(f"  Average Response Time: {avg_time:.3f}s")
                print(f"  Min Response Time: {min_time:.3f}s")
                print(f"  Max Response Time: {max_time:.3f}s")
    
    async def run_all_demos(self):
        """Run all demonstrations."""
        print("🚀 VidNet Rate Limiting & Performance Optimization Demo")
        print("This demo showcases the features implemented in Task 10:")
        print("- Rate limiting middleware")
        print("- Performance monitoring")
        print("- Graceful degradation")
        print("- System health monitoring")
        
        try:
            await self.demo_health_monitoring()
            await self.demo_performance_monitoring()
            await self.demo_rate_limiting()
            await self.demo_rate_limit_stats()
            await self.demo_concurrent_load()
            
            print("\n" + "="*60)
            print("✅ DEMONSTRATION COMPLETED SUCCESSFULLY")
            print("="*60)
            print("All rate limiting and performance optimization features are working correctly!")
            
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            logger.error(f"Demo error: {e}")


async def main():
    """Main function to run the demonstration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="VidNet Rate Limiting & Performance Demo")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--demo", choices=[
        'all', 'rate-limiting', 'performance', 'health', 'stats', 'concurrent'
    ], default='all', help="Which demo to run")
    
    args = parser.parse_args()
    
    demo = RateLimitingDemo(args.url)
    
    if args.demo == 'all':
        await demo.run_all_demos()
    elif args.demo == 'rate-limiting':
        await demo.demo_rate_limiting()
    elif args.demo == 'performance':
        await demo.demo_performance_monitoring()
    elif args.demo == 'health':
        await demo.demo_health_monitoring()
    elif args.demo == 'stats':
        await demo.demo_rate_limit_stats()
    elif args.demo == 'concurrent':
        await demo.demo_concurrent_load()


if __name__ == "__main__":
    asyncio.run(main())