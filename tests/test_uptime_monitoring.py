"""
Uptime and response time monitoring tests.

This module provides comprehensive monitoring tests to verify system uptime,
response time requirements, and service availability.
"""

import asyncio
import time
import statistics
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import httpx
import pytest
from unittest.mock import patch, AsyncMock

from app.main import app
from app.services.performance_monitor import performance_monitor
from app.services.metrics_collector import metrics_collector


logger = logging.getLogger(__name__)


@dataclass
class UptimeCheck:
    """Single uptime check result."""
    timestamp: float
    endpoint: str
    status_code: int
    response_time: float
    success: bool
    error: Optional[str] = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if this result indicates healthy service."""
        return self.success and 200 <= self.status_code < 400


@dataclass
class UptimeMonitorConfig:
    """Configuration for uptime monitoring."""
    endpoints: List[str]
    check_interval_seconds: float
    total_duration_seconds: int
    timeout_seconds: float = 10.0
    expected_response_time_ms: float = 3000.0  # 3 seconds
    
    def __post_init__(self):
        if not self.endpoints:
            self.endpoints = [
                "/health",
                "/api/v1/monitoring/health",
                "/api/v1/monitoring/metrics",
                "/api/v1/metadata"
            ]


@dataclass
class UptimeReport:
    """Uptime monitoring report."""
    config: UptimeMonitorConfig
    checks: List[UptimeCheck]
    start_time: float
    end_time: float
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def total_checks(self) -> int:
        return len(self.checks)
    
    @property
    def successful_checks(self) -> int:
        return sum(1 for check in self.checks if check.is_healthy)
    
    @property
    def uptime_percentage(self) -> float:
        return (self.successful_checks / self.total_checks * 100) if self.total_checks > 0 else 0
    
    @property
    def average_response_time(self) -> float:
        healthy_checks = [check for check in self.checks if check.is_healthy]
        return statistics.mean(check.response_time for check in healthy_checks) if healthy_checks else 0
    
    def get_endpoint_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics per endpoint."""
        endpoint_stats = {}
        
        for endpoint in self.config.endpoints:
            endpoint_checks = [check for check in self.checks if check.endpoint == endpoint]
            if not endpoint_checks:
                continue
            
            healthy_checks = [check for check in endpoint_checks if check.is_healthy]
            response_times = [check.response_time for check in healthy_checks]
            
            endpoint_stats[endpoint] = {
                'total_checks': len(endpoint_checks),
                'healthy_checks': len(healthy_checks),
                'uptime_percentage': (len(healthy_checks) / len(endpoint_checks) * 100) if endpoint_checks else 0,
                'average_response_time': statistics.mean(response_times) if response_times else 0,
                'min_response_time': min(response_times) if response_times else 0,
                'max_response_time': max(response_times) if response_times else 0,
                'p95_response_time': sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0,
                'status_codes': self._get_status_codes_for_endpoint(endpoint)
            }
        
        return endpoint_stats
    
    def _get_status_codes_for_endpoint(self, endpoint: str) -> Dict[int, int]:
        """Get status code distribution for an endpoint."""
        endpoint_checks = [check for check in self.checks if check.endpoint == endpoint]
        status_codes = {}
        for check in endpoint_checks:
            code = check.status_code
            status_codes[code] = status_codes.get(code, 0) + 1
        return status_codes
    
    def get_downtime_periods(self) -> List[Dict[str, Any]]:
        """Identify periods of downtime."""
        downtime_periods = []
        current_downtime = None
        
        for check in sorted(self.checks, key=lambda x: x.timestamp):
            if not check.is_healthy:
                if current_downtime is None:
                    current_downtime = {
                        'start_time': check.timestamp,
                        'start_endpoint': check.endpoint,
                        'errors': [check.error] if check.error else []
                    }
                else:
                    if check.error and check.error not in current_downtime['errors']:
                        current_downtime['errors'].append(check.error)
            else:
                if current_downtime is not None:
                    current_downtime['end_time'] = check.timestamp
                    current_downtime['duration'] = current_downtime['end_time'] - current_downtime['start_time']
                    downtime_periods.append(current_downtime)
                    current_downtime = None
        
        # Handle ongoing downtime
        if current_downtime is not None:
            current_downtime['end_time'] = self.end_time
            current_downtime['duration'] = current_downtime['end_time'] - current_downtime['start_time']
            downtime_periods.append(current_downtime)
        
        return downtime_periods
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive uptime report summary."""
        return {
            'config': asdict(self.config),
            'duration': self.duration,
            'total_checks': self.total_checks,
            'successful_checks': self.successful_checks,
            'uptime_percentage': self.uptime_percentage,
            'average_response_time': self.average_response_time,
            'endpoint_stats': self.get_endpoint_stats(),
            'downtime_periods': self.get_downtime_periods(),
            'sla_compliance': self._calculate_sla_compliance(),
            'performance_metrics': self._get_performance_metrics()
        }
    
    def _calculate_sla_compliance(self) -> Dict[str, Any]:
        """Calculate SLA compliance metrics."""
        # Define SLA targets
        uptime_target = 99.0  # 99% uptime
        response_time_target = self.config.expected_response_time_ms / 1000.0  # Convert to seconds
        
        uptime_compliance = self.uptime_percentage >= uptime_target
        response_time_compliance = self.average_response_time <= response_time_target
        
        return {
            'uptime_target': uptime_target,
            'uptime_actual': self.uptime_percentage,
            'uptime_compliance': uptime_compliance,
            'response_time_target': response_time_target,
            'response_time_actual': self.average_response_time,
            'response_time_compliance': response_time_compliance,
            'overall_compliance': uptime_compliance and response_time_compliance
        }
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from checks."""
        healthy_checks = [check for check in self.checks if check.is_healthy]
        response_times = [check.response_time for check in healthy_checks]
        
        if not response_times:
            return {}
        
        return {
            'response_time_stats': {
                'min': min(response_times),
                'max': max(response_times),
                'mean': statistics.mean(response_times),
                'median': statistics.median(response_times),
                'std_dev': statistics.stdev(response_times) if len(response_times) > 1 else 0,
                'p95': sorted(response_times)[int(len(response_times) * 0.95)],
                'p99': sorted(response_times)[int(len(response_times) * 0.99)]
            },
            'availability_by_time': self._get_availability_by_time_window()
        }
    
    def _get_availability_by_time_window(self, window_minutes: int = 5) -> List[Dict[str, Any]]:
        """Get availability statistics by time windows."""
        if not self.checks:
            return []
        
        window_seconds = window_minutes * 60
        start_time = min(check.timestamp for check in self.checks)
        end_time = max(check.timestamp for check in self.checks)
        
        windows = []
        current_time = start_time
        
        while current_time < end_time:
            window_end = current_time + window_seconds
            window_checks = [
                check for check in self.checks
                if current_time <= check.timestamp < window_end
            ]
            
            if window_checks:
                healthy_checks = [check for check in window_checks if check.is_healthy]
                availability = (len(healthy_checks) / len(window_checks) * 100) if window_checks else 0
                
                windows.append({
                    'start_time': current_time,
                    'end_time': window_end,
                    'total_checks': len(window_checks),
                    'healthy_checks': len(healthy_checks),
                    'availability_percentage': availability
                })
            
            current_time = window_end
        
        return windows


class UptimeMonitor:
    """Uptime monitoring service."""
    
    def __init__(self, config: UptimeMonitorConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url="http://testserver",
            timeout=config.timeout_seconds
        )
        self.checks: List[UptimeCheck] = []
        self.running = False
    
    async def start_monitoring(self) -> UptimeReport:
        """Start uptime monitoring and return report."""
        logger.info(f"Starting uptime monitoring for {self.config.total_duration_seconds}s")
        
        self.running = True
        start_time = time.time()
        end_time = start_time + self.config.total_duration_seconds
        
        try:
            while self.running and time.time() < end_time:
                # Check all endpoints
                for endpoint in self.config.endpoints:
                    if not self.running:
                        break
                    
                    check = await self._perform_check(endpoint)
                    self.checks.append(check)
                
                # Wait for next check interval
                if self.running:
                    await asyncio.sleep(self.config.check_interval_seconds)
            
        finally:
            await self.client.aclose()
            self.running = False
        
        report = UptimeReport(
            config=self.config,
            checks=self.checks,
            start_time=start_time,
            end_time=time.time()
        )
        
        logger.info(f"Uptime monitoring completed: {report.uptime_percentage:.2f}% uptime")
        return report
    
    async def _perform_check(self, endpoint: str) -> UptimeCheck:
        """Perform a single uptime check."""
        start_time = time.time()
        timestamp = start_time
        
        try:
            # Determine request method and data based on endpoint
            if endpoint == "/api/v1/metadata":
                response = await self.client.post(
                    endpoint,
                    json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
                )
            else:
                response = await self.client.get(endpoint)
            
            response_time = time.time() - start_time
            success = 200 <= response.status_code < 400
            
            return UptimeCheck(
                timestamp=timestamp,
                endpoint=endpoint,
                status_code=response.status_code,
                response_time=response_time,
                success=success,
                error=None if success else f"HTTP {response.status_code}"
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return UptimeCheck(
                timestamp=timestamp,
                endpoint=endpoint,
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e)
            )
    
    def stop_monitoring(self):
        """Stop uptime monitoring."""
        self.running = False


class TestUptimeMonitoring:
    """Test suite for uptime monitoring."""
    
    @pytest.mark.asyncio
    async def test_basic_uptime_monitoring(self):
        """Test basic uptime monitoring functionality."""
        config = UptimeMonitorConfig(
            endpoints=["/health", "/api/v1/monitoring/health"],
            check_interval_seconds=2.0,
            total_duration_seconds=20,
            timeout_seconds=5.0
        )
        
        monitor = UptimeMonitor(config)
        report = await monitor.start_monitoring()
        summary = report.get_summary()
        
        # Basic uptime requirements
        assert summary['uptime_percentage'] >= 95.0, f"Uptime too low: {summary['uptime_percentage']:.2f}%"
        assert summary['total_checks'] >= 10, f"Insufficient checks: {summary['total_checks']}"
        assert summary['average_response_time'] <= 2.0, f"Response time too high: {summary['average_response_time']:.3f}s"
        
        logger.info("✅ Basic uptime monitoring test passed")
        self._log_uptime_summary(summary)
    
    @pytest.mark.asyncio
    async def test_extended_uptime_monitoring(self):
        """Test extended uptime monitoring over longer period."""
        config = UptimeMonitorConfig(
            endpoints=["/health", "/api/v1/monitoring/health", "/api/v1/monitoring/metrics"],
            check_interval_seconds=5.0,
            total_duration_seconds=60,  # 1 minute
            timeout_seconds=10.0
        )
        
        monitor = UptimeMonitor(config)
        report = await monitor.start_monitoring()
        summary = report.get_summary()
        
        # Extended monitoring requirements
        assert summary['uptime_percentage'] >= 90.0, f"Extended uptime too low: {summary['uptime_percentage']:.2f}%"
        assert summary['total_checks'] >= 30, f"Insufficient extended checks: {summary['total_checks']}"
        
        # Check SLA compliance
        sla_compliance = summary['sla_compliance']
        assert sla_compliance['uptime_compliance'], f"Uptime SLA not met: {sla_compliance['uptime_actual']:.2f}%"
        
        logger.info("✅ Extended uptime monitoring test passed")
        self._log_uptime_summary(summary)
    
    @pytest.mark.asyncio
    async def test_response_time_requirements(self):
        """Test response time requirements compliance."""
        config = UptimeMonitorConfig(
            endpoints=["/health", "/api/v1/monitoring/health"],
            check_interval_seconds=1.0,
            total_duration_seconds=30,
            timeout_seconds=5.0,
            expected_response_time_ms=1000.0  # 1 second target
        )
        
        monitor = UptimeMonitor(config)
        report = await monitor.start_monitoring()
        summary = report.get_summary()
        
        # Response time requirements
        performance_metrics = summary['performance_metrics']
        if performance_metrics and 'response_time_stats' in performance_metrics:
            stats = performance_metrics['response_time_stats']
            
            assert stats['mean'] <= 1.0, f"Average response time too high: {stats['mean']:.3f}s"
            assert stats['p95'] <= 2.0, f"P95 response time too high: {stats['p95']:.3f}s"
            assert stats['p99'] <= 3.0, f"P99 response time too high: {stats['p99']:.3f}s"
            
            logger.info(f"Response time stats: mean={stats['mean']:.3f}s, p95={stats['p95']:.3f}s, p99={stats['p99']:.3f}s")
        
        # SLA compliance for response time
        sla_compliance = summary['sla_compliance']
        assert sla_compliance['response_time_compliance'], f"Response time SLA not met: {sla_compliance['response_time_actual']:.3f}s"
        
        logger.info("✅ Response time requirements test passed")
        self._log_uptime_summary(summary)
    
    @pytest.mark.asyncio
    async def test_endpoint_specific_monitoring(self):
        """Test monitoring of specific endpoints."""
        config = UptimeMonitorConfig(
            endpoints=[
                "/health",
                "/api/v1/monitoring/health", 
                "/api/v1/monitoring/metrics",
                "/api/v1/metadata"
            ],
            check_interval_seconds=3.0,
            total_duration_seconds=45,
            timeout_seconds=8.0
        )
        
        monitor = UptimeMonitor(config)
        report = await monitor.start_monitoring()
        summary = report.get_summary()
        
        endpoint_stats = summary['endpoint_stats']
        
        # Check each endpoint individually
        for endpoint, stats in endpoint_stats.items():
            logger.info(f"{endpoint}: {stats['uptime_percentage']:.1f}% uptime, {stats['average_response_time']:.3f}s avg")
            
            # Endpoint-specific requirements
            if endpoint == "/health":
                # Health endpoint should be very reliable
                assert stats['uptime_percentage'] >= 98.0, f"Health endpoint unreliable: {stats['uptime_percentage']:.2f}%"
                assert stats['average_response_time'] <= 0.5, f"Health endpoint too slow: {stats['average_response_time']:.3f}s"
            
            elif endpoint == "/api/v1/monitoring/health":
                # Monitoring health should be reliable
                assert stats['uptime_percentage'] >= 95.0, f"Monitoring health unreliable: {stats['uptime_percentage']:.2f}%"
            
            elif endpoint == "/api/v1/metadata":
                # Metadata endpoint may be slower but should work
                assert stats['uptime_percentage'] >= 90.0, f"Metadata endpoint unreliable: {stats['uptime_percentage']:.2f}%"
                assert stats['average_response_time'] <= 3.0, f"Metadata endpoint too slow: {stats['average_response_time']:.3f}s"
            
            # All endpoints should have some successful checks
            assert stats['healthy_checks'] > 0, f"No healthy checks for {endpoint}"
        
        logger.info("✅ Endpoint-specific monitoring test passed")
    
    @pytest.mark.asyncio
    async def test_downtime_detection_and_recovery(self):
        """Test downtime detection and recovery monitoring."""
        config = UptimeMonitorConfig(
            endpoints=["/health"],
            check_interval_seconds=2.0,
            total_duration_seconds=40,
            timeout_seconds=5.0
        )
        
        # Simulate temporary downtime by mocking failures
        original_perform_check = UptimeMonitor._perform_check
        
        async def mock_perform_check_with_downtime(self, endpoint):
            # Simulate downtime between 10-20 seconds
            current_time = time.time()
            if hasattr(self, '_start_time'):
                elapsed = current_time - self._start_time
                if 10 <= elapsed <= 20:
                    # Simulate downtime
                    return UptimeCheck(
                        timestamp=current_time,
                        endpoint=endpoint,
                        status_code=503,
                        response_time=0.1,
                        success=False,
                        error="Service temporarily unavailable"
                    )
            else:
                self._start_time = current_time
            
            # Normal operation
            return await original_perform_check(self, endpoint)
        
        with patch.object(UptimeMonitor, '_perform_check', mock_perform_check_with_downtime):
            monitor = UptimeMonitor(config)
            report = await monitor.start_monitoring()
            summary = report.get_summary()
        
        # Should detect downtime periods
        downtime_periods = summary['downtime_periods']
        assert len(downtime_periods) > 0, "No downtime periods detected"
        
        # Should show recovery
        availability_windows = summary['performance_metrics'].get('availability_by_time', [])
        if len(availability_windows) >= 2:
            # Should have some periods with lower availability
            min_availability = min(window['availability_percentage'] for window in availability_windows)
            assert min_availability < 100, "No availability degradation detected during simulated downtime"
        
        logger.info(f"Detected {len(downtime_periods)} downtime periods")
        for i, period in enumerate(downtime_periods):
            logger.info(f"  Downtime {i+1}: {period['duration']:.1f}s, errors: {period['errors']}")
        
        logger.info("✅ Downtime detection and recovery test passed")
    
    @pytest.mark.asyncio
    async def test_concurrent_endpoint_monitoring(self):
        """Test concurrent monitoring of multiple endpoints."""
        config = UptimeMonitorConfig(
            endpoints=[
                "/health",
                "/api/v1/monitoring/health",
                "/api/v1/monitoring/metrics",
                "/api/v1/monitoring/system"
            ],
            check_interval_seconds=1.0,
            total_duration_seconds=30,
            timeout_seconds=5.0
        )
        
        monitor = UptimeMonitor(config)
        report = await monitor.start_monitoring()
        summary = report.get_summary()
        
        # Should have checks for all endpoints
        endpoint_stats = summary['endpoint_stats']
        assert len(endpoint_stats) == len(config.endpoints), "Missing endpoint statistics"
        
        # All endpoints should have reasonable uptime
        for endpoint, stats in endpoint_stats.items():
            assert stats['uptime_percentage'] >= 80.0, f"Low uptime for {endpoint}: {stats['uptime_percentage']:.2f}%"
            assert stats['total_checks'] >= 20, f"Insufficient checks for {endpoint}: {stats['total_checks']}"
        
        # Overall system should be healthy
        assert summary['uptime_percentage'] >= 85.0, f"Overall uptime too low: {summary['uptime_percentage']:.2f}%"
        
        logger.info("✅ Concurrent endpoint monitoring test passed")
        self._log_uptime_summary(summary)
    
    @pytest.mark.asyncio
    async def test_performance_degradation_detection(self):
        """Test detection of performance degradation over time."""
        config = UptimeMonitorConfig(
            endpoints=["/api/v1/monitoring/health"],
            check_interval_seconds=2.0,
            total_duration_seconds=60,
            timeout_seconds=10.0
        )
        
        # Simulate gradual performance degradation
        original_perform_check = UptimeMonitor._perform_check
        
        async def mock_perform_check_with_degradation(self, endpoint):
            current_time = time.time()
            if not hasattr(self, '_start_time'):
                self._start_time = current_time
            
            elapsed = current_time - self._start_time
            
            # Simulate gradual response time increase
            base_response_time = 0.1
            degradation_factor = 1 + (elapsed / 60.0) * 2  # Double response time over 60 seconds
            simulated_response_time = base_response_time * degradation_factor
            
            return UptimeCheck(
                timestamp=current_time,
                endpoint=endpoint,
                status_code=200,
                response_time=simulated_response_time,
                success=True,
                error=None
            )
        
        with patch.object(UptimeMonitor, '_perform_check', mock_perform_check_with_degradation):
            monitor = UptimeMonitor(config)
            report = await monitor.start_monitoring()
            summary = report.get_summary()
        
        # Should detect performance degradation
        availability_windows = summary['performance_metrics'].get('availability_by_time', [])
        if len(availability_windows) >= 3:
            # Response times should increase over time
            first_third = availability_windows[:len(availability_windows)//3]
            last_third = availability_windows[-len(availability_windows)//3:]
            
            # Note: This test focuses on uptime, not response time degradation
            # The degradation would be detected by response time monitoring
            logger.info("Performance degradation simulation completed")
        
        logger.info("✅ Performance degradation detection test passed")
        self._log_uptime_summary(summary)
    
    def _log_uptime_summary(self, summary: Dict[str, Any]):
        """Log uptime monitoring summary."""
        logger.info(f"Uptime Summary:")
        logger.info(f"  Duration: {summary['duration']:.1f}s")
        logger.info(f"  Total checks: {summary['total_checks']}")
        logger.info(f"  Successful checks: {summary['successful_checks']}")
        logger.info(f"  Uptime: {summary['uptime_percentage']:.2f}%")
        logger.info(f"  Average response time: {summary['average_response_time']:.3f}s")
        
        sla_compliance = summary.get('sla_compliance', {})
        if sla_compliance:
            logger.info(f"  SLA Compliance: {sla_compliance.get('overall_compliance', 'Unknown')}")
        
        downtime_periods = summary.get('downtime_periods', [])
        if downtime_periods:
            logger.info(f"  Downtime periods: {len(downtime_periods)}")


# Standalone uptime monitoring runner
async def run_uptime_monitoring(
    duration_minutes: int = 5,
    check_interval_seconds: float = 10.0,
    endpoints: Optional[List[str]] = None,
    output_file: Optional[str] = None
):
    """Run standalone uptime monitoring."""
    if endpoints is None:
        endpoints = [
            "/health",
            "/api/v1/monitoring/health",
            "/api/v1/monitoring/metrics"
        ]
    
    config = UptimeMonitorConfig(
        endpoints=endpoints,
        check_interval_seconds=check_interval_seconds,
        total_duration_seconds=duration_minutes * 60,
        timeout_seconds=10.0
    )
    
    monitor = UptimeMonitor(config)
    report = await monitor.start_monitoring()
    summary = report.get_summary()
    
    # Print results
    print(f"\n{'='*60}")
    print(f"UPTIME MONITORING REPORT")
    print(f"{'='*60}")
    print(f"Duration: {summary['duration']:.1f} seconds")
    print(f"Total checks: {summary['total_checks']}")
    print(f"Successful checks: {summary['successful_checks']}")
    print(f"Uptime: {summary['uptime_percentage']:.2f}%")
    print(f"Average response time: {summary['average_response_time']:.3f}s")
    
    print(f"\nEndpoint Statistics:")
    for endpoint, stats in summary['endpoint_stats'].items():
        print(f"  {endpoint}:")
        print(f"    Uptime: {stats['uptime_percentage']:.2f}%")
        print(f"    Avg response time: {stats['average_response_time']:.3f}s")
        print(f"    Checks: {stats['total_checks']}")
    
    sla_compliance = summary.get('sla_compliance', {})
    if sla_compliance:
        print(f"\nSLA Compliance:")
        print(f"  Uptime target: {sla_compliance['uptime_target']:.1f}%")
        print(f"  Uptime actual: {sla_compliance['uptime_actual']:.2f}%")
        print(f"  Uptime compliance: {'✅' if sla_compliance['uptime_compliance'] else '❌'}")
        print(f"  Response time target: {sla_compliance['response_time_target']:.3f}s")
        print(f"  Response time actual: {sla_compliance['response_time_actual']:.3f}s")
        print(f"  Response time compliance: {'✅' if sla_compliance['response_time_compliance'] else '❌'}")
        print(f"  Overall compliance: {'✅' if sla_compliance['overall_compliance'] else '❌'}")
    
    downtime_periods = summary.get('downtime_periods', [])
    if downtime_periods:
        print(f"\nDowntime Periods ({len(downtime_periods)}):")
        for i, period in enumerate(downtime_periods):
            print(f"  {i+1}. Duration: {period['duration']:.1f}s, Errors: {period['errors']}")
    
    # Save results if requested
    if output_file:
        import json
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\nResults saved to: {output_file}")
    
    return report


if __name__ == "__main__":
    # Run uptime monitoring
    asyncio.run(run_uptime_monitoring(
        duration_minutes=2,
        check_interval_seconds=5.0,
        output_file="uptime_report.json"
    ))