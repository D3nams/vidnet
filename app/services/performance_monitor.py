"""
Performance monitoring service for VidNet API.

This module provides comprehensive performance monitoring, metrics collection,
and response time tracking for the VidNet application.
"""

import time
import asyncio
import logging
import psutil
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
from contextlib import asynccontextmanager
import json
from pathlib import Path

from app.services.cache_manager import cache_manager


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    timestamp: float
    endpoint: str
    method: str
    response_time: float
    status_code: int
    client_id: str
    user_agent: str = ""
    error_message: Optional[str] = None


@dataclass
class SystemMetrics:
    """System resource metrics."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    active_connections: int
    load_average: List[float] = field(default_factory=list)


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.
    
    Features:
    - Request response time tracking
    - System resource monitoring
    - Endpoint performance analytics
    - Real-time metrics collection
    - Performance alerts and thresholds
    - Historical data storage
    """
    
    def __init__(self, max_metrics_history: int = 10000):
        self.max_metrics_history = max_metrics_history
        
        # Metrics storage
        self.request_metrics: deque = deque(maxlen=max_metrics_history)
        self.system_metrics: deque = deque(maxlen=1000)  # Keep last 1000 system snapshots
        
        # Real-time counters
        self.endpoint_stats = defaultdict(lambda: {
            'total_requests': 0,
            'total_response_time': 0.0,
            'min_response_time': float('inf'),
            'max_response_time': 0.0,
            'error_count': 0,
            'success_count': 0,
            'last_request': None
        })
        
        # Performance thresholds
        self.thresholds = {
            'response_time_warning': 3.0,  # 3 seconds
            'response_time_critical': 10.0,  # 10 seconds
            'cpu_warning': 80.0,  # 80%
            'cpu_critical': 95.0,  # 95%
            'memory_warning': 80.0,  # 80%
            'memory_critical': 95.0,  # 95%
            'error_rate_warning': 5.0,  # 5%
            'error_rate_critical': 15.0  # 15%
        }
        
        # Monitoring state
        self._monitoring_active = False
        self._system_monitor_task: Optional[asyncio.Task] = None
        self._metrics_cleanup_task: Optional[asyncio.Task] = None
        
        # Thread-safe lock for metrics updates
        self._lock = threading.Lock()
        
        logger.info("Performance monitor initialized")
    
    async def start_monitoring(self):
        """Start performance monitoring tasks."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        
        # Start system monitoring task
        self._system_monitor_task = asyncio.create_task(self._system_monitor_worker())
        
        # Start metrics cleanup task
        self._metrics_cleanup_task = asyncio.create_task(self._metrics_cleanup_worker())
        
        logger.info("Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop performance monitoring tasks."""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        
        # Cancel monitoring tasks
        if self._system_monitor_task:
            self._system_monitor_task.cancel()
        
        if self._metrics_cleanup_task:
            self._metrics_cleanup_task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(
            self._system_monitor_task,
            self._metrics_cleanup_task,
            return_exceptions=True
        )
        
        logger.info("Performance monitoring stopped")
    
    def record_request(self, metrics: PerformanceMetrics):
        """
        Record request performance metrics.
        
        Args:
            metrics: Performance metrics for the request
        """
        with self._lock:
            # Add to metrics history
            self.request_metrics.append(metrics)
            
            # Update endpoint statistics
            endpoint_key = f"{metrics.method} {metrics.endpoint}"
            stats = self.endpoint_stats[endpoint_key]
            
            stats['total_requests'] += 1
            stats['total_response_time'] += metrics.response_time
            stats['min_response_time'] = min(stats['min_response_time'], metrics.response_time)
            stats['max_response_time'] = max(stats['max_response_time'], metrics.response_time)
            stats['last_request'] = metrics.timestamp
            
            if metrics.status_code >= 400:
                stats['error_count'] += 1
            else:
                stats['success_count'] += 1
            
            # Check for performance alerts
            self._check_performance_alerts(metrics)
    
    @asynccontextmanager
    async def track_request(self, endpoint: str, method: str, client_id: str, user_agent: str = ""):
        """
        Context manager to track request performance.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            client_id: Client identifier
            user_agent: User agent string
        """
        start_time = time.time()
        status_code = 200
        error_message = None
        
        try:
            yield
        except Exception as e:
            status_code = 500
            error_message = str(e)
            raise
        finally:
            response_time = time.time() - start_time
            
            metrics = PerformanceMetrics(
                timestamp=start_time,
                endpoint=endpoint,
                method=method,
                response_time=response_time,
                status_code=status_code,
                client_id=client_id,
                user_agent=user_agent,
                error_message=error_message
            )
            
            self.record_request(metrics)
    
    def get_endpoint_stats(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Get endpoint performance statistics.
        
        Args:
            endpoint: Specific endpoint to get stats for (optional)
            
        Returns:
            Dict with endpoint statistics
        """
        with self._lock:
            if endpoint:
                stats = self.endpoint_stats.get(endpoint, {})
                if stats and stats['total_requests'] > 0:
                    return {
                        endpoint: {
                            **stats,
                            'average_response_time': stats['total_response_time'] / stats['total_requests'],
                            'error_rate': (stats['error_count'] / stats['total_requests']) * 100,
                            'success_rate': (stats['success_count'] / stats['total_requests']) * 100
                        }
                    }
                return {}
            
            # Return all endpoint stats
            result = {}
            for endpoint_key, stats in self.endpoint_stats.items():
                if stats['total_requests'] > 0:
                    result[endpoint_key] = {
                        **stats,
                        'average_response_time': stats['total_response_time'] / stats['total_requests'],
                        'error_rate': (stats['error_count'] / stats['total_requests']) * 100,
                        'success_rate': (stats['success_count'] / stats['total_requests']) * 100
                    }
            
            return result
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get current system performance metrics.
        
        Returns:
            Dict with system metrics
        """
        try:
            # Get current system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get network connections (approximate active connections)
            try:
                connections = len(psutil.net_connections(kind='inet'))
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                connections = 0
            
            # Get load average (Unix-like systems)
            try:
                load_avg = list(psutil.getloadavg())
            except AttributeError:
                # Windows doesn't have load average
                load_avg = [cpu_percent / 100.0] * 3
            
            current_metrics = SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                disk_usage_percent=disk.percent,
                active_connections=connections,
                load_average=load_avg
            )
            
            # Store in history
            self.system_metrics.append(current_metrics)
            
            return {
                'cpu_percent': current_metrics.cpu_percent,
                'memory_percent': current_metrics.memory_percent,
                'memory_used_mb': current_metrics.memory_used_mb,
                'disk_usage_percent': current_metrics.disk_usage_percent,
                'active_connections': current_metrics.active_connections,
                'load_average': current_metrics.load_average,
                'timestamp': current_metrics.timestamp
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {
                'error': str(e),
                'timestamp': time.time()
            }
    
    def get_performance_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get performance summary for the specified time window.
        
        Args:
            time_window_minutes: Time window in minutes
            
        Returns:
            Dict with performance summary
        """
        cutoff_time = time.time() - (time_window_minutes * 60)
        
        with self._lock:
            # Filter metrics within time window
            recent_metrics = [m for m in self.request_metrics if m.timestamp >= cutoff_time]
            
            if not recent_metrics:
                return {
                    'time_window_minutes': time_window_minutes,
                    'total_requests': 0,
                    'message': 'No requests in the specified time window'
                }
            
            # Calculate summary statistics
            total_requests = len(recent_metrics)
            total_response_time = sum(m.response_time for m in recent_metrics)
            error_count = sum(1 for m in recent_metrics if m.status_code >= 400)
            
            response_times = [m.response_time for m in recent_metrics]
            response_times.sort()
            
            # Calculate percentiles
            p50_idx = int(len(response_times) * 0.5)
            p95_idx = int(len(response_times) * 0.95)
            p99_idx = int(len(response_times) * 0.99)
            
            summary = {
                'time_window_minutes': time_window_minutes,
                'total_requests': total_requests,
                'error_count': error_count,
                'error_rate': (error_count / total_requests) * 100,
                'success_rate': ((total_requests - error_count) / total_requests) * 100,
                'average_response_time': total_response_time / total_requests,
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'p50_response_time': response_times[p50_idx] if p50_idx < len(response_times) else 0,
                'p95_response_time': response_times[p95_idx] if p95_idx < len(response_times) else 0,
                'p99_response_time': response_times[p99_idx] if p99_idx < len(response_times) else 0,
                'requests_per_minute': total_requests / time_window_minutes,
                'timestamp': time.time()
            }
            
            return summary
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get overall system health status.
        
        Returns:
            Dict with health status and alerts
        """
        system_metrics = self.get_system_metrics()
        performance_summary = self.get_performance_summary(15)  # Last 15 minutes
        
        alerts = []
        health_score = 100
        
        # Check system resource alerts
        if system_metrics.get('cpu_percent', 0) > self.thresholds['cpu_critical']:
            alerts.append({
                'level': 'critical',
                'type': 'cpu',
                'message': f"CPU usage critical: {system_metrics['cpu_percent']:.1f}%"
            })
            health_score -= 30
        elif system_metrics.get('cpu_percent', 0) > self.thresholds['cpu_warning']:
            alerts.append({
                'level': 'warning',
                'type': 'cpu',
                'message': f"CPU usage high: {system_metrics['cpu_percent']:.1f}%"
            })
            health_score -= 10
        
        if system_metrics.get('memory_percent', 0) > self.thresholds['memory_critical']:
            alerts.append({
                'level': 'critical',
                'type': 'memory',
                'message': f"Memory usage critical: {system_metrics['memory_percent']:.1f}%"
            })
            health_score -= 30
        elif system_metrics.get('memory_percent', 0) > self.thresholds['memory_warning']:
            alerts.append({
                'level': 'warning',
                'type': 'memory',
                'message': f"Memory usage high: {system_metrics['memory_percent']:.1f}%"
            })
            health_score -= 10
        
        # Check performance alerts
        if performance_summary.get('total_requests', 0) > 0:
            avg_response_time = performance_summary.get('average_response_time', 0)
            error_rate = performance_summary.get('error_rate', 0)
            
            if avg_response_time > self.thresholds['response_time_critical']:
                alerts.append({
                    'level': 'critical',
                    'type': 'response_time',
                    'message': f"Average response time critical: {avg_response_time:.2f}s"
                })
                health_score -= 25
            elif avg_response_time > self.thresholds['response_time_warning']:
                alerts.append({
                    'level': 'warning',
                    'type': 'response_time',
                    'message': f"Average response time high: {avg_response_time:.2f}s"
                })
                health_score -= 10
            
            if error_rate > self.thresholds['error_rate_critical']:
                alerts.append({
                    'level': 'critical',
                    'type': 'error_rate',
                    'message': f"Error rate critical: {error_rate:.1f}%"
                })
                health_score -= 25
            elif error_rate > self.thresholds['error_rate_warning']:
                alerts.append({
                    'level': 'warning',
                    'type': 'error_rate',
                    'message': f"Error rate high: {error_rate:.1f}%"
                })
                health_score -= 10
        
        # Determine overall status
        if health_score >= 90:
            status = 'healthy'
        elif health_score >= 70:
            status = 'degraded'
        else:
            status = 'unhealthy'
        
        return {
            'status': status,
            'health_score': max(0, health_score),
            'alerts': alerts,
            'system_metrics': system_metrics,
            'performance_summary': performance_summary,
            'thresholds': self.thresholds,
            'timestamp': time.time()
        }
    
    def _check_performance_alerts(self, metrics: PerformanceMetrics):
        """
        Check for performance alerts based on metrics.
        
        Args:
            metrics: Request performance metrics
        """
        alerts = []
        
        # Check response time alerts
        if metrics.response_time > self.thresholds['response_time_critical']:
            alerts.append({
                'level': 'critical',
                'type': 'response_time',
                'endpoint': metrics.endpoint,
                'response_time': metrics.response_time,
                'timestamp': metrics.timestamp
            })
        elif metrics.response_time > self.thresholds['response_time_warning']:
            alerts.append({
                'level': 'warning',
                'type': 'response_time',
                'endpoint': metrics.endpoint,
                'response_time': metrics.response_time,
                'timestamp': metrics.timestamp
            })
        
        # Log alerts
        for alert in alerts:
            if alert['level'] == 'critical':
                logger.error(f"Performance alert: {alert}")
            else:
                logger.warning(f"Performance alert: {alert}")
    
    async def _system_monitor_worker(self):
        """Background worker to collect system metrics."""
        while self._monitoring_active:
            try:
                # Collect system metrics
                self.get_system_metrics()
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"System monitor worker error: {e}")
                await asyncio.sleep(60)
    
    async def _metrics_cleanup_worker(self):
        """Background worker to clean up old metrics."""
        while self._monitoring_active:
            try:
                # Clean up old metrics (older than 24 hours)
                cutoff_time = time.time() - (24 * 60 * 60)
                
                with self._lock:
                    # Clean request metrics
                    while self.request_metrics and self.request_metrics[0].timestamp < cutoff_time:
                        self.request_metrics.popleft()
                    
                    # Clean system metrics
                    while self.system_metrics and self.system_metrics[0].timestamp < cutoff_time:
                        self.system_metrics.popleft()
                
                logger.debug("Metrics cleanup completed")
                
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Metrics cleanup worker error: {e}")
                await asyncio.sleep(3600)
    
    def export_metrics(self, filepath: str):
        """
        Export metrics to JSON file.
        
        Args:
            filepath: Path to export file
        """
        try:
            export_data = {
                'endpoint_stats': self.get_endpoint_stats(),
                'performance_summary': self.get_performance_summary(),
                'health_status': self.get_health_status(),
                'export_timestamp': time.time()
            }
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Metrics exported to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()