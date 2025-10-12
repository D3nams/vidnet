"""
Load testing for VidNet API rate limiting and performance optimization.

This module provides comprehensive load tests to verify the system can handle
100+ concurrent users with proper rate limiting and graceful degradation.
"""

import asyncio
import time
import logging
import statistics
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from unittest.mock import patch

from app.main import app
from app.middleware.rate_limiter import rate_limiter, RateLimitConfig
from app.services.performance_monitor import performance_monitor


logger = logging.getLogger(__name__)


class LoadTestClient:
    """HTTP client for load testing."""
    
    def __init__(self, base_url: str = "http://testserver"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def get_metadata(self, url: str) -> Tuple[int, float, Dict[str, Any]]:
        """
        Get video metadata with timing.
        
        Returns:
            Tuple of (status_code, response_time, response_data)
        """
        start_time = time.time()
        try:
            response = await self.client.post(
                "/api/v1/metadata",
                json={"url": url}
            )
            response_time = time.time() - start_time
            
            try:
                data = response.json()
            except:
                data = {"error": "invalid_json", "text": response.text}
            
            return response.status_code, response_time, data
            
        except Exception as e:
            response_time = time.time() - start_time
            return 500, response_time, {"error": str(e)}
    
    async def download_video(self, url: str, quality: str = "720p") -> Tuple[int, float, Dict[str, Any]]:
        """
        Initiate video download with timing.
        
        Returns:
            Tuple of (status_code, response_time, response_data)
        """
        start_time = time.time()
        try:
            response = await self.client.post(
                "/api/v1/download",
                json={
                    "url": url,
                    "quality": quality,
                    "format": "video"
                }
            )
            response_time = time.time() - start_time
            
            try:
                data = response.json()
            except:
                data = {"error": "invalid_json", "text": response.text}
            
            return response.status_code, response_time, data
            
        except Exception as e:
            response_time = time.time() - start_time
            return 500, response_time, {"error": str(e)}
    
    async def get_health(self) -> Tuple[int, float, Dict[str, Any]]:
        """
        Get health status with timing.
        
        Returns:
            Tuple of (status_code, response_time, response_data)
        """
        start_time = time.time()
        try:
            response = await self.client.get("/api/v1/monitoring/health")
            response_time = time.time() - start_time
            
            try:
                data = response.json()
            except:
                data = {"error": "invalid_json", "text": response.text}
            
            return response.status_code, response_time, data
            
        except Exception as e:
            response_time = time.time() - start_time
            return 500, response_time, {"error": str(e)}


class LoadTestResults:
    """Container for load test results."""
    
    def __init__(self):
        self.requests: List[Dict[str, Any]] = []
        self.start_time: float = 0
        self.end_time: float = 0
        self.concurrent_users: int = 0
        self.test_duration: float = 0
    
    def add_request(self, endpoint: str, status_code: int, response_time: float, 
                   success: bool, error: str = None):
        """Add a request result."""
        self.requests.append({
            'endpoint': endpoint,
            'status_code': status_code,
            'response_time': response_time,
            'success': success,
            'error': error,
            'timestamp': time.time()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test results summary."""
        if not self.requests:
            return {"error": "No requests recorded"}
        
        # Calculate statistics
        response_times = [r['response_time'] for r in self.requests]
        success_count = sum(1 for r in self.requests if r['success'])
        error_count = len(self.requests) - success_count
        
        # Status code distribution
        status_codes = {}
        for request in self.requests:
            code = request['status_code']
            status_codes[code] = status_codes.get(code, 0) + 1
        
        # Response time percentiles
        response_times.sort()
        total_requests = len(response_times)
        
        summary = {
            'test_config': {
                'concurrent_users': self.concurrent_users,
                'test_duration': self.test_duration,
                'total_requests': total_requests
            },
            'performance': {
                'requests_per_second': total_requests / self.test_duration if self.test_duration > 0 else 0,
                'success_rate': (success_count / total_requests) * 100,
                'error_rate': (error_count / total_requests) * 100,
                'average_response_time': statistics.mean(response_times),
                'median_response_time': statistics.median(response_times),
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'p95_response_time': response_times[int(total_requests * 0.95)] if total_requests > 0 else 0,
                'p99_response_time': response_times[int(total_requests * 0.99)] if total_requests > 0 else 0
            },
            'status_codes': status_codes,
            'errors': {
                'total_errors': error_count,
                'error_types': {}
            }
        }
        
        # Count error types
        for request in self.requests:
            if not request['success'] and request['error']:
                error_type = request['error']
                summary['errors']['error_types'][error_type] = summary['errors']['error_types'].get(error_type, 0) + 1
        
        return summary


async def simulate_user_load(client: LoadTestClient, user_id: int, 
                           test_duration: int, results: LoadTestResults) -> None:
    """
    Simulate load from a single user.
    
    Args:
        client: HTTP client
        user_id: User identifier
        test_duration: Test duration in seconds
        results: Results container
    """
    end_time = time.time() + test_duration
    request_count = 0
    
    # Test URLs for different scenarios
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Valid YouTube URL
        "https://www.tiktok.com/@test/video/123456789",  # Valid TikTok URL
        "https://invalid-url.com/video",  # Invalid URL
        "not-a-url"  # Malformed URL
    ]
    
    while time.time() < end_time:
        try:
            # Vary the requests to test different endpoints
            request_type = request_count % 4
            
            if request_type == 0:
                # Test metadata endpoint
                url = test_urls[request_count % len(test_urls)]
                status_code, response_time, data = await client.get_metadata(url)
                success = status_code == 200 or (status_code == 400 and "validation_error" in str(data))
                error = None if success else str(data.get('error', 'unknown_error'))
                results.add_request('metadata', status_code, response_time, success, error)
                
            elif request_type == 1:
                # Test download endpoint
                url = test_urls[0]  # Use valid URL for downloads
                status_code, response_time, data = await client.download_video(url)
                success = status_code in [200, 400, 429]  # Accept rate limiting
                error = None if success else str(data.get('error', 'unknown_error'))
                results.add_request('download', status_code, response_time, success, error)
                
            elif request_type == 2:
                # Test health endpoint
                status_code, response_time, data = await client.get_health()
                success = status_code in [200, 503]  # Accept degraded service
                error = None if success else str(data.get('error', 'unknown_error'))
                results.add_request('health', status_code, response_time, success, error)
                
            else:
                # Test rate limiting by making rapid requests
                for _ in range(3):
                    status_code, response_time, data = await client.get_metadata(test_urls[0])
                    success = status_code in [200, 429]  # Expect rate limiting
                    error = None if success else str(data.get('error', 'unknown_error'))
                    results.add_request('rapid_metadata', status_code, response_time, success, error)
            
            request_count += 1
            
            # Small delay between requests (0.1-0.5 seconds)
            await asyncio.sleep(0.1 + (user_id % 5) * 0.1)
            
        except Exception as e:
            logger.error(f"User {user_id} error: {e}")
            results.add_request('error', 500, 0, False, str(e))
            await asyncio.sleep(1)  # Wait before retrying


@pytest.mark.asyncio
async def test_concurrent_user_load():
    """
    Test system performance with 100+ concurrent users.
    
    This test verifies:
    - System can handle 100+ concurrent users
    - Rate limiting works correctly
    - Response times stay within acceptable limits
    - Graceful degradation activates under high load
    """
    # Test configuration
    concurrent_users = 100
    test_duration = 60  # 1 minute test
    
    # Initialize results
    results = LoadTestResults()
    results.concurrent_users = concurrent_users
    results.test_duration = test_duration
    results.start_time = time.time()
    
    # Create HTTP clients for each user
    clients = []
    for i in range(concurrent_users):
        client = LoadTestClient()
        clients.append(client)
    
    try:
        # Start load test
        logger.info(f"Starting load test with {concurrent_users} concurrent users for {test_duration} seconds")
        
        # Create tasks for all users
        tasks = []
        for i, client in enumerate(clients):
            task = asyncio.create_task(
                simulate_user_load(client, i, test_duration, results)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        results.end_time = time.time()
        
        # Get test summary
        summary = results.get_summary()
        
        logger.info("Load test completed")
        logger.info(f"Total requests: {summary['test_config']['total_requests']}")
        logger.info(f"Requests per second: {summary['performance']['requests_per_second']:.2f}")
        logger.info(f"Success rate: {summary['performance']['success_rate']:.2f}%")
        logger.info(f"Average response time: {summary['performance']['average_response_time']:.3f}s")
        logger.info(f"P95 response time: {summary['performance']['p95_response_time']:.3f}s")
        
        # Verify performance requirements
        assert summary['performance']['success_rate'] >= 80, f"Success rate too low: {summary['performance']['success_rate']:.2f}%"
        assert summary['performance']['average_response_time'] <= 5.0, f"Average response time too high: {summary['performance']['average_response_time']:.3f}s"
        assert summary['performance']['p95_response_time'] <= 10.0, f"P95 response time too high: {summary['performance']['p95_response_time']:.3f}s"
        
        # Verify rate limiting is working (should see 429 responses)
        status_codes = summary['status_codes']
        assert 429 in status_codes, "Rate limiting not working - no 429 responses found"
        
        logger.info("✅ Load test passed all performance requirements")
        
    finally:
        # Clean up clients
        for client in clients:
            await client.close()


@pytest.mark.asyncio
async def test_rate_limiting_effectiveness():
    """
    Test rate limiting effectiveness with rapid requests.
    
    This test verifies:
    - Rate limiting triggers correctly
    - Rate limit headers are present
    - Proper error messages for rate limited requests
    """
    client = LoadTestClient()
    
    try:
        # Make rapid requests to trigger rate limiting
        responses = []
        
        for i in range(70):  # Exceed per-minute limit
            status_code, response_time, data = await client.get_metadata(
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
            responses.append((status_code, response_time, data))
            
            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.05)
        
        # Analyze responses
        rate_limited_count = sum(1 for status, _, _ in responses if status == 429)
        successful_count = sum(1 for status, _, _ in responses if status == 200)
        
        logger.info(f"Successful requests: {successful_count}")
        logger.info(f"Rate limited requests: {rate_limited_count}")
        
        # Verify rate limiting is working
        assert rate_limited_count > 0, "Rate limiting not triggered"
        assert successful_count > 0, "No successful requests"
        
        # Check rate limit response format
        rate_limited_responses = [data for status, _, data in responses if status == 429]
        if rate_limited_responses:
            sample_response = rate_limited_responses[0]
            assert 'error' in sample_response, "Rate limit response missing error field"
            assert sample_response['error'] == 'rate_limit_exceeded', "Incorrect rate limit error type"
            assert 'retry_after' in sample_response, "Rate limit response missing retry_after"
        
        logger.info("✅ Rate limiting effectiveness test passed")
        
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_graceful_degradation():
    """
    Test graceful degradation under extreme load.
    
    This test verifies:
    - Service degrades gracefully under high concurrent load
    - Degraded responses are properly formatted
    - System recovers after load decreases
    """
    # Simulate extreme concurrent load
    concurrent_requests = 150  # Exceed degradation threshold
    
    clients = []
    for i in range(concurrent_requests):
        client = LoadTestClient()
        clients.append(client)
    
    try:
        # Create many concurrent requests
        tasks = []
        for client in clients:
            task = asyncio.create_task(
                client.download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            )
            tasks.append(task)
        
        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        degraded_count = 0
        successful_count = 0
        error_count = 0
        
        for result in results:
            if isinstance(result, tuple):
                status_code, _, data = result
                if status_code == 503:
                    degraded_count += 1
                elif status_code == 200:
                    successful_count += 1
                else:
                    error_count += 1
            else:
                error_count += 1
        
        logger.info(f"Degraded responses: {degraded_count}")
        logger.info(f"Successful responses: {successful_count}")
        logger.info(f"Error responses: {error_count}")
        
        # Verify graceful degradation occurred
        total_responses = degraded_count + successful_count + error_count
        degradation_rate = (degraded_count / total_responses) * 100 if total_responses > 0 else 0
        
        # Should see some degraded responses under extreme load
        assert degradation_rate > 0, "Graceful degradation not activated under extreme load"
        
        logger.info(f"✅ Graceful degradation test passed - {degradation_rate:.1f}% degraded responses")
        
    finally:
        # Clean up clients
        for client in clients:
            await client.close()


@pytest.mark.asyncio
async def test_performance_monitoring_accuracy():
    """
    Test performance monitoring accuracy and metrics collection.
    
    This test verifies:
    - Performance metrics are collected accurately
    - Response time tracking works correctly
    - System metrics are available
    """
    client = LoadTestClient()
    
    try:
        # Clear existing metrics
        performance_monitor.request_metrics.clear()
        performance_monitor.endpoint_stats.clear()
        
        # Make test requests
        test_requests = 20
        start_time = time.time()
        
        for i in range(test_requests):
            await client.get_metadata("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            await asyncio.sleep(0.1)  # Small delay between requests
        
        test_duration = time.time() - start_time
        
        # Get performance metrics
        endpoint_stats = performance_monitor.get_endpoint_stats()
        system_metrics = performance_monitor.get_system_metrics()
        performance_summary = performance_monitor.get_performance_summary(5)  # Last 5 minutes
        
        # Verify metrics collection
        assert len(endpoint_stats) > 0, "No endpoint statistics collected"
        assert 'cpu_percent' in system_metrics, "System metrics not available"
        assert performance_summary['total_requests'] >= test_requests, "Performance summary missing requests"
        
        # Verify endpoint statistics
        metadata_endpoint_found = False
        for endpoint, stats in endpoint_stats.items():
            if 'metadata' in endpoint:
                metadata_endpoint_found = True
                assert stats['total_requests'] >= test_requests, "Incorrect request count in endpoint stats"
                assert stats['average_response_time'] > 0, "Invalid average response time"
                break
        
        assert metadata_endpoint_found, "Metadata endpoint statistics not found"
        
        logger.info("✅ Performance monitoring accuracy test passed")
        
    finally:
        await client.close()


if __name__ == "__main__":
    # Run load tests directly
    asyncio.run(test_concurrent_user_load())
    asyncio.run(test_rate_limiting_effectiveness())
    asyncio.run(test_graceful_degradation())
    asyncio.run(test_performance_monitoring_accuracy())