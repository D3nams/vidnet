"""
Scalability and load testing scripts for VidNet API.

This module provides comprehensive load testing to validate system scalability
and performance under various load conditions.
"""

import asyncio
import time
import statistics
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import httpx
import pytest
from unittest.mock import patch

from app.main import app
from app.middleware.rate_limiter import rate_limiter
from app.services.performance_monitor import performance_monitor


logger = logging.getLogger(__name__)


@dataclass
class LoadTestConfig:
    """Configuration for load tests."""
    concurrent_users: int
    test_duration_seconds: int
    ramp_up_seconds: int
    target_rps: Optional[int] = None  # Requests per second
    endpoints: List[str] = None
    
    def __post_init__(self):
        if self.endpoints is None:
            self.endpoints = [
                "/api/v1/metadata",
                "/api/v1/download", 
                "/api/v1/monitoring/health",
                "/api/v1/monitoring/metrics"
            ]


@dataclass
class RequestResult:
    """Result of a single request."""
    endpoint: str
    method: str
    status_code: int
    response_time: float
    success: bool
    error: Optional[str]
    timestamp: float
    user_id: int
    request_size: int = 0
    response_size: int = 0


@dataclass
class LoadTestResults:
    """Results of a load test."""
    config: LoadTestConfig
    requests: List[RequestResult]
    start_time: float
    end_time: float
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def total_requests(self) -> int:
        return len(self.requests)
    
    @property
    def successful_requests(self) -> int:
        return sum(1 for r in self.requests if r.success)
    
    @property
    def failed_requests(self) -> int:
        return self.total_requests - self.successful_requests
    
    @property
    def success_rate(self) -> float:
        return (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
    
    @property
    def requests_per_second(self) -> float:
        return self.total_requests / self.duration if self.duration > 0 else 0
    
    @property
    def response_times(self) -> List[float]:
        return [r.response_time for r in self.requests if r.success]
    
    def get_percentile(self, percentile: float) -> float:
        """Get response time percentile."""
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * percentile / 100)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test results summary."""
        response_times = self.response_times
        
        return {
            'config': asdict(self.config),
            'duration': self.duration,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': self.success_rate,
            'requests_per_second': self.requests_per_second,
            'response_times': {
                'min': min(response_times) if response_times else 0,
                'max': max(response_times) if response_times else 0,
                'mean': statistics.mean(response_times) if response_times else 0,
                'median': statistics.median(response_times) if response_times else 0,
                'p95': self.get_percentile(95),
                'p99': self.get_percentile(99)
            },
            'status_codes': self._get_status_code_distribution(),
            'endpoint_stats': self._get_endpoint_stats(),
            'error_analysis': self._get_error_analysis()
        }
    
    def _get_status_code_distribution(self) -> Dict[int, int]:
        """Get distribution of status codes."""
        distribution = {}
        for request in self.requests:
            code = request.status_code
            distribution[code] = distribution.get(code, 0) + 1
        return distribution
    
    def _get_endpoint_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics per endpoint."""
        endpoint_stats = {}
        
        for endpoint in self.config.endpoints:
            endpoint_requests = [r for r in self.requests if r.endpoint == endpoint]
            if not endpoint_requests:
                continue
            
            successful = [r for r in endpoint_requests if r.success]
            response_times = [r.response_time for r in successful]
            
            endpoint_stats[endpoint] = {
                'total_requests': len(endpoint_requests),
                'successful_requests': len(successful),
                'success_rate': (len(successful) / len(endpoint_requests) * 100) if endpoint_requests else 0,
                'avg_response_time': statistics.mean(response_times) if response_times else 0,
                'p95_response_time': sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
            }
        
        return endpoint_stats
    
    def _get_error_analysis(self) -> Dict[str, Any]:
        """Get error analysis."""
        errors = [r.error for r in self.requests if r.error]
        error_counts = {}
        for error in errors:
            error_counts[error] = error_counts.get(error, 0) + 1
        
        return {
            'total_errors': len(errors),
            'error_types': error_counts,
            'error_rate_by_time': self._get_error_rate_by_time()
        }
    
    def _get_error_rate_by_time(self) -> List[Dict[str, Any]]:
        """Get error rate over time."""
        if not self.requests:
            return []
        
        # Group requests by 10-second intervals
        interval_seconds = 10
        start_time = min(r.timestamp for r in self.requests)
        end_time = max(r.timestamp for r in self.requests)
        
        intervals = []
        current_time = start_time
        
        while current_time < end_time:
            interval_end = current_time + interval_seconds
            interval_requests = [
                r for r in self.requests 
                if current_time <= r.timestamp < interval_end
            ]
            
            if interval_requests:
                errors = sum(1 for r in interval_requests if not r.success)
                error_rate = (errors / len(interval_requests) * 100) if interval_requests else 0
                
                intervals.append({
                    'start_time': current_time,
                    'end_time': interval_end,
                    'total_requests': len(interval_requests),
                    'errors': errors,
                    'error_rate': error_rate
                })
            
            current_time = interval_end
        
        return intervals


class LoadTestClient:
    """HTTP client for load testing."""
    
    def __init__(self, base_url: str = "http://testserver"):
        self.base_url = base_url
        self.session = httpx.AsyncClient(
            base_url=base_url,
            timeout=30.0,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.session.aclose()
    
    async def make_request(self, method: str, endpoint: str, **kwargs) -> RequestResult:
        """Make a single request and return result."""
        start_time = time.time()
        timestamp = start_time
        
        try:
            response = await self.session.request(method, endpoint, **kwargs)
            response_time = time.time() - start_time
            
            # Determine success based on status code
            success = 200 <= response.status_code < 400 or response.status_code == 429  # Accept rate limiting
            error = None if success else f"HTTP {response.status_code}"
            
            return RequestResult(
                endpoint=endpoint,
                method=method,
                status_code=response.status_code,
                response_time=response_time,
                success=success,
                error=error,
                timestamp=timestamp,
                user_id=0,  # Will be set by caller
                request_size=len(kwargs.get('json', {})) if 'json' in kwargs else 0,
                response_size=len(response.content) if hasattr(response, 'content') else 0
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return RequestResult(
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e),
                timestamp=timestamp,
                user_id=0,
                request_size=0,
                response_size=0
            )


class LoadTestRunner:
    """Load test runner."""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results = LoadTestResults(
            config=config,
            requests=[],
            start_time=0,
            end_time=0
        )
    
    async def run_load_test(self) -> LoadTestResults:
        """Run the load test."""
        logger.info(f"Starting load test with {self.config.concurrent_users} users for {self.config.test_duration_seconds}s")
        
        self.results.start_time = time.time()
        
        # Create clients
        clients = []
        for i in range(self.config.concurrent_users):
            client = LoadTestClient()
            clients.append(client)
        
        try:
            # Create user tasks with ramp-up
            tasks = []
            for i, client in enumerate(clients):
                # Stagger user start times for ramp-up
                delay = (i / self.config.concurrent_users) * self.config.ramp_up_seconds
                task = asyncio.create_task(self._simulate_user(client, i, delay))
                tasks.append(task)
            
            # Wait for all users to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
        finally:
            # Clean up clients
            for client in clients:
                await client.close()
        
        self.results.end_time = time.time()
        
        logger.info(f"Load test completed: {self.results.total_requests} requests in {self.results.duration:.2f}s")
        return self.results
    
    async def _simulate_user(self, client: LoadTestClient, user_id: int, start_delay: float):
        """Simulate a single user's behavior."""
        # Wait for ramp-up delay
        await asyncio.sleep(start_delay)
        
        end_time = self.results.start_time + self.config.test_duration_seconds
        request_count = 0
        
        # Test data for different endpoints
        test_data = {
            "/api/v1/metadata": {
                "method": "POST",
                "json": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
            },
            "/api/v1/download": {
                "method": "POST", 
                "json": {
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "quality": "720p",
                    "format": "video"
                }
            },
            "/api/v1/monitoring/health": {
                "method": "GET"
            },
            "/api/v1/monitoring/metrics": {
                "method": "GET"
            }
        }
        
        while time.time() < end_time:
            # Select endpoint (round-robin with some randomness)
            endpoint = self.config.endpoints[request_count % len(self.config.endpoints)]
            request_data = test_data.get(endpoint, {"method": "GET"})
            
            # Make request
            result = await client.make_request(
                method=request_data["method"],
                endpoint=endpoint,
                **{k: v for k, v in request_data.items() if k != "method"}
            )
            result.user_id = user_id
            
            # Store result
            self.results.requests.append(result)
            request_count += 1
            
            # Calculate delay for target RPS
            if self.config.target_rps:
                delay = 1.0 / self.config.target_rps
                await asyncio.sleep(delay)
            else:
                # Small random delay to simulate realistic user behavior
                await asyncio.sleep(0.1 + (user_id % 10) * 0.05)


class ScalabilityTestSuite:
    """Test suite for scalability validation."""
    
    @pytest.mark.asyncio
    async def test_baseline_performance(self):
        """Test baseline performance with minimal load."""
        config = LoadTestConfig(
            concurrent_users=1,
            test_duration_seconds=30,
            ramp_up_seconds=1
        )
        
        runner = LoadTestRunner(config)
        results = await runner.run_load_test()
        summary = results.get_summary()
        
        # Baseline performance requirements
        assert summary['success_rate'] >= 95, f"Baseline success rate too low: {summary['success_rate']:.2f}%"
        assert summary['response_times']['mean'] <= 2.0, f"Baseline response time too high: {summary['response_times']['mean']:.3f}s"
        assert summary['response_times']['p95'] <= 5.0, f"Baseline P95 too high: {summary['response_times']['p95']:.3f}s"
        
        logger.info("✅ Baseline performance test passed")
        self._log_summary(summary)
    
    @pytest.mark.asyncio
    async def test_moderate_load(self):
        """Test performance under moderate concurrent load."""
        config = LoadTestConfig(
            concurrent_users=25,
            test_duration_seconds=60,
            ramp_up_seconds=10
        )
        
        runner = LoadTestRunner(config)
        results = await runner.run_load_test()
        summary = results.get_summary()
        
        # Moderate load requirements
        assert summary['success_rate'] >= 90, f"Moderate load success rate too low: {summary['success_rate']:.2f}%"
        assert summary['response_times']['mean'] <= 3.0, f"Moderate load response time too high: {summary['response_times']['mean']:.3f}s"
        assert summary['response_times']['p95'] <= 8.0, f"Moderate load P95 too high: {summary['response_times']['p95']:.3f}s"
        assert summary['requests_per_second'] >= 10, f"Moderate load RPS too low: {summary['requests_per_second']:.2f}"
        
        logger.info("✅ Moderate load test passed")
        self._log_summary(summary)
    
    @pytest.mark.asyncio
    async def test_high_concurrent_load(self):
        """Test performance under high concurrent load (100+ users)."""
        config = LoadTestConfig(
            concurrent_users=100,
            test_duration_seconds=120,
            ramp_up_seconds=30
        )
        
        runner = LoadTestRunner(config)
        results = await runner.run_load_test()
        summary = results.get_summary()
        
        # High load requirements (more lenient)
        assert summary['success_rate'] >= 80, f"High load success rate too low: {summary['success_rate']:.2f}%"
        assert summary['response_times']['mean'] <= 5.0, f"High load response time too high: {summary['response_times']['mean']:.3f}s"
        assert summary['response_times']['p95'] <= 15.0, f"High load P95 too high: {summary['response_times']['p95']:.3f}s"
        
        # Should see rate limiting under high load
        status_codes = summary['status_codes']
        assert 429 in status_codes, "Rate limiting not activated under high load"
        
        logger.info("✅ High concurrent load test passed")
        self._log_summary(summary)
    
    @pytest.mark.asyncio
    async def test_sustained_load(self):
        """Test performance under sustained load over time."""
        config = LoadTestConfig(
            concurrent_users=50,
            test_duration_seconds=300,  # 5 minutes
            ramp_up_seconds=30
        )
        
        runner = LoadTestRunner(config)
        results = await runner.run_load_test()
        summary = results.get_summary()
        
        # Sustained load requirements
        assert summary['success_rate'] >= 85, f"Sustained load success rate too low: {summary['success_rate']:.2f}%"
        assert summary['response_times']['mean'] <= 4.0, f"Sustained load response time too high: {summary['response_times']['mean']:.3f}s"
        
        # Check for performance degradation over time
        error_rates_by_time = summary['error_analysis']['error_rate_by_time']
        if len(error_rates_by_time) >= 2:
            first_half_errors = [interval['error_rate'] for interval in error_rates_by_time[:len(error_rates_by_time)//2]]
            second_half_errors = [interval['error_rate'] for interval in error_rates_by_time[len(error_rates_by_time)//2:]]
            
            first_half_avg = statistics.mean(first_half_errors) if first_half_errors else 0
            second_half_avg = statistics.mean(second_half_errors) if second_half_errors else 0
            
            # Error rate shouldn't increase significantly over time
            degradation = second_half_avg - first_half_avg
            assert degradation <= 10, f"Performance degraded over time: {degradation:.2f}% increase in error rate"
        
        logger.info("✅ Sustained load test passed")
        self._log_summary(summary)
    
    @pytest.mark.asyncio
    async def test_spike_load(self):
        """Test system behavior under sudden load spikes."""
        # First, establish baseline
        baseline_config = LoadTestConfig(
            concurrent_users=10,
            test_duration_seconds=30,
            ramp_up_seconds=5
        )
        
        baseline_runner = LoadTestRunner(baseline_config)
        baseline_results = await baseline_runner.run_load_test()
        baseline_summary = baseline_results.get_summary()
        
        # Then, create spike
        spike_config = LoadTestConfig(
            concurrent_users=150,
            test_duration_seconds=60,
            ramp_up_seconds=5  # Rapid ramp-up for spike
        )
        
        spike_runner = LoadTestRunner(spike_config)
        spike_results = await spike_runner.run_load_test()
        spike_summary = spike_results.get_summary()
        
        # Spike load requirements
        assert spike_summary['success_rate'] >= 70, f"Spike load success rate too low: {spike_summary['success_rate']:.2f}%"
        
        # Should handle graceful degradation
        status_codes = spike_summary['status_codes']
        assert 503 in status_codes or 429 in status_codes, "No graceful degradation during spike"
        
        # Recovery test - run baseline again
        recovery_runner = LoadTestRunner(baseline_config)
        recovery_results = await recovery_runner.run_load_test()
        recovery_summary = recovery_results.get_summary()
        
        # Should recover to near baseline performance
        performance_recovery = recovery_summary['success_rate'] / baseline_summary['success_rate']
        assert performance_recovery >= 0.9, f"Poor recovery after spike: {performance_recovery:.2f}"
        
        logger.info("✅ Spike load test passed")
        logger.info(f"Baseline: {baseline_summary['success_rate']:.1f}% success")
        logger.info(f"Spike: {spike_summary['success_rate']:.1f}% success")
        logger.info(f"Recovery: {recovery_summary['success_rate']:.1f}% success")
    
    @pytest.mark.asyncio
    async def test_endpoint_specific_scalability(self):
        """Test scalability of individual endpoints."""
        endpoints_to_test = [
            "/api/v1/metadata",
            "/api/v1/monitoring/health",
            "/api/v1/monitoring/metrics"
        ]
        
        endpoint_results = {}
        
        for endpoint in endpoints_to_test:
            config = LoadTestConfig(
                concurrent_users=50,
                test_duration_seconds=60,
                ramp_up_seconds=10,
                endpoints=[endpoint]  # Test single endpoint
            )
            
            runner = LoadTestRunner(config)
            results = await runner.run_load_test()
            summary = results.get_summary()
            
            endpoint_results[endpoint] = summary
            
            # Endpoint-specific requirements
            if endpoint == "/api/v1/metadata":
                # Metadata endpoint should be fast
                assert summary['response_times']['mean'] <= 1.0, f"Metadata endpoint too slow: {summary['response_times']['mean']:.3f}s"
            elif endpoint == "/api/v1/monitoring/health":
                # Health endpoint should be very fast and reliable
                assert summary['success_rate'] >= 95, f"Health endpoint unreliable: {summary['success_rate']:.2f}%"
                assert summary['response_times']['mean'] <= 0.5, f"Health endpoint too slow: {summary['response_times']['mean']:.3f}s"
            
            logger.info(f"✅ {endpoint} scalability test passed")
        
        # Compare endpoint performance
        for endpoint, summary in endpoint_results.items():
            logger.info(f"{endpoint}: {summary['success_rate']:.1f}% success, {summary['response_times']['mean']:.3f}s avg")
    
    @pytest.mark.asyncio
    async def test_memory_and_resource_usage(self):
        """Test memory and resource usage under load."""
        import psutil
        import os
        
        # Get initial resource usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        initial_cpu = process.cpu_percent()
        
        config = LoadTestConfig(
            concurrent_users=75,
            test_duration_seconds=120,
            ramp_up_seconds=20
        )
        
        # Monitor resources during test
        resource_samples = []
        
        async def monitor_resources():
            while True:
                try:
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    cpu_percent = process.cpu_percent()
                    resource_samples.append({
                        'timestamp': time.time(),
                        'memory_mb': memory_mb,
                        'cpu_percent': cpu_percent
                    })
                    await asyncio.sleep(5)  # Sample every 5 seconds
                except:
                    break
        
        # Run test with resource monitoring
        monitor_task = asyncio.create_task(monitor_resources())
        
        try:
            runner = LoadTestRunner(config)
            results = await runner.run_load_test()
            summary = results.get_summary()
        finally:
            monitor_task.cancel()
        
        # Analyze resource usage
        if resource_samples:
            max_memory = max(sample['memory_mb'] for sample in resource_samples)
            avg_memory = statistics.mean(sample['memory_mb'] for sample in resource_samples)
            max_cpu = max(sample['cpu_percent'] for sample in resource_samples)
            avg_cpu = statistics.mean(sample['cpu_percent'] for sample in resource_samples)
            
            memory_increase = max_memory - initial_memory
            
            logger.info(f"Resource usage during load test:")
            logger.info(f"  Memory: {initial_memory:.1f}MB -> {max_memory:.1f}MB (increase: {memory_increase:.1f}MB)")
            logger.info(f"  CPU: avg {avg_cpu:.1f}%, max {max_cpu:.1f}%")
            
            # Resource usage requirements
            assert memory_increase <= 500, f"Excessive memory usage increase: {memory_increase:.1f}MB"
            assert avg_cpu <= 80, f"High average CPU usage: {avg_cpu:.1f}%"
        
        logger.info("✅ Resource usage test passed")
        self._log_summary(summary)
    
    def _log_summary(self, summary: Dict[str, Any]):
        """Log test summary."""
        logger.info(f"Summary:")
        logger.info(f"  Total requests: {summary['total_requests']}")
        logger.info(f"  Success rate: {summary['success_rate']:.2f}%")
        logger.info(f"  RPS: {summary['requests_per_second']:.2f}")
        logger.info(f"  Response times: avg={summary['response_times']['mean']:.3f}s, p95={summary['response_times']['p95']:.3f}s")
        logger.info(f"  Status codes: {summary['status_codes']}")


# Standalone load test runner
async def run_custom_load_test(
    concurrent_users: int = 50,
    duration_seconds: int = 60,
    ramp_up_seconds: int = 10,
    target_rps: Optional[int] = None,
    output_file: Optional[str] = None
):
    """Run a custom load test with specified parameters."""
    config = LoadTestConfig(
        concurrent_users=concurrent_users,
        test_duration_seconds=duration_seconds,
        ramp_up_seconds=ramp_up_seconds,
        target_rps=target_rps
    )
    
    runner = LoadTestRunner(config)
    results = await runner.run_load_test()
    summary = results.get_summary()
    
    # Print results
    print(f"\n{'='*60}")
    print(f"LOAD TEST RESULTS")
    print(f"{'='*60}")
    print(f"Configuration:")
    print(f"  Concurrent users: {config.concurrent_users}")
    print(f"  Duration: {config.test_duration_seconds}s")
    print(f"  Ramp-up: {config.ramp_up_seconds}s")
    print(f"  Target RPS: {config.target_rps or 'None'}")
    print(f"\nResults:")
    print(f"  Total requests: {summary['total_requests']}")
    print(f"  Successful: {summary['successful_requests']}")
    print(f"  Failed: {summary['failed_requests']}")
    print(f"  Success rate: {summary['success_rate']:.2f}%")
    print(f"  Requests/second: {summary['requests_per_second']:.2f}")
    print(f"\nResponse Times:")
    print(f"  Min: {summary['response_times']['min']:.3f}s")
    print(f"  Max: {summary['response_times']['max']:.3f}s")
    print(f"  Mean: {summary['response_times']['mean']:.3f}s")
    print(f"  Median: {summary['response_times']['median']:.3f}s")
    print(f"  P95: {summary['response_times']['p95']:.3f}s")
    print(f"  P99: {summary['response_times']['p99']:.3f}s")
    print(f"\nStatus Codes:")
    for code, count in summary['status_codes'].items():
        print(f"  {code}: {count}")
    
    # Save results to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\nResults saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    # Run a quick load test
    asyncio.run(run_custom_load_test(
        concurrent_users=25,
        duration_seconds=30,
        ramp_up_seconds=5,
        output_file="load_test_results.json"
    ))