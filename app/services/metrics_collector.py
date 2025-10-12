"""
Custom metrics collection service for VidNet MVP.

This module provides comprehensive metrics collection for business analytics,
performance monitoring, and dashboard visualization.
"""

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import json
from pathlib import Path

from app.services.cache_manager import cache_manager
from app.services.performance_monitor import performance_monitor


logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric type enumeration."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricEvent:
    """Individual metric event data structure."""
    timestamp: float
    metric_name: str
    metric_type: MetricType
    value: Union[int, float]
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BusinessMetrics:
    """Business-specific metrics data structure."""
    timestamp: float
    downloads_total: int = 0
    downloads_by_platform: Dict[str, int] = field(default_factory=dict)
    downloads_by_quality: Dict[str, int] = field(default_factory=dict)
    audio_extractions_total: int = 0
    unique_users: int = 0
    conversion_rate: float = 0.0
    revenue_per_user: float = 0.0
    user_retention_rate: float = 0.0


class MetricsCollector:
    """
    Comprehensive metrics collection system for VidNet MVP.
    
    Features:
    - Custom business metrics tracking
    - Performance metrics aggregation
    - Cache hit rate monitoring
    - Real-time dashboard data
    - Metrics export and visualization
    - Alert generation based on thresholds
    """
    
    def __init__(self, max_events_history: int = 50000):
        self.max_events_history = max_events_history
        
        # Metrics storage
        self.metric_events: deque = deque(maxlen=max_events_history)
        self.business_metrics_history: deque = deque(maxlen=1000)
        
        # Real-time counters
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        self.timers = defaultdict(list)
        
        # Business metrics
        self.business_metrics = BusinessMetrics(timestamp=time.time())
        
        # Platform tracking
        self.platform_stats = defaultdict(lambda: {
            'downloads': 0,
            'audio_extractions': 0,
            'total_processing_time': 0.0,
            'success_rate': 0.0,
            'error_count': 0
        })
        
        # Quality tracking
        self.quality_stats = defaultdict(lambda: {
            'downloads': 0,
            'total_file_size': 0,
            'average_processing_time': 0.0
        })
        
        # User engagement tracking
        self.user_sessions = defaultdict(lambda: {
            'first_visit': time.time(),
            'last_activity': time.time(),
            'downloads': 0,
            'audio_extractions': 0,
            'platforms_used': set()
        })
        
        # Performance thresholds for alerts
        self.alert_thresholds = {
            'cache_hit_rate_warning': 70.0,  # Below 70%
            'cache_hit_rate_critical': 50.0,  # Below 50%
            'download_success_rate_warning': 90.0,  # Below 90%
            'download_success_rate_critical': 80.0,  # Below 80%
            'average_processing_time_warning': 5.0,  # Above 5 seconds
            'average_processing_time_critical': 10.0,  # Above 10 seconds
            'error_rate_warning': 5.0,  # Above 5%
            'error_rate_critical': 10.0  # Above 10%
        }
        
        logger.info("Metrics collector initialized")
    
    def record_metric(self, name: str, value: Union[int, float], 
                     metric_type: MetricType, tags: Optional[Dict[str, str]] = None,
                     metadata: Optional[Dict[str, Any]] = None):
        """
        Record a custom metric event.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric (counter, gauge, histogram, timer)
            tags: Optional tags for filtering and grouping
            metadata: Optional additional metadata
        """
        event = MetricEvent(
            timestamp=time.time(),
            metric_name=name,
            metric_type=metric_type,
            value=value,
            tags=tags or {},
            metadata=metadata or {}
        )
        
        self.metric_events.append(event)
        
        # Update real-time storage based on metric type
        if metric_type == MetricType.COUNTER:
            self.counters[name] += value
        elif metric_type == MetricType.GAUGE:
            self.gauges[name] = value
        elif metric_type == MetricType.HISTOGRAM:
            self.histograms[name].append(value)
            # Keep only last 1000 values for memory efficiency
            if len(self.histograms[name]) > 1000:
                self.histograms[name] = self.histograms[name][-1000:]
        elif metric_type == MetricType.TIMER:
            self.timers[name].append(value)
            # Keep only last 1000 values for memory efficiency
            if len(self.timers[name]) > 1000:
                self.timers[name] = self.timers[name][-1000:]
    
    def track_download(self, platform: str, quality: str, processing_time: float, 
                      success: bool, user_id: str, file_size: Optional[int] = None):
        """
        Track video download event.
        
        Args:
            platform: Platform name (youtube, tiktok, etc.)
            quality: Video quality (720p, 1080p, 4K)
            processing_time: Time taken to process download
            success: Whether download was successful
            user_id: User identifier
            file_size: Optional file size in bytes
        """
        # Record individual metrics
        self.record_metric("downloads_total", 1, MetricType.COUNTER, 
                          tags={"platform": platform, "quality": quality, "success": str(success)})
        
        self.record_metric("download_processing_time", processing_time, MetricType.TIMER,
                          tags={"platform": platform, "quality": quality})
        
        if file_size:
            self.record_metric("download_file_size", file_size, MetricType.HISTOGRAM,
                              tags={"platform": platform, "quality": quality})
        
        # Update business metrics (only for successful downloads)
        if success:
            self.business_metrics.downloads_total += 1
            self.business_metrics.downloads_by_platform[platform] = \
                self.business_metrics.downloads_by_platform.get(platform, 0) + 1
            self.business_metrics.downloads_by_quality[quality] = \
                self.business_metrics.downloads_by_quality.get(quality, 0) + 1
        
        # Update platform stats
        platform_stat = self.platform_stats[platform]
        
        if success:
            platform_stat['downloads'] += 1
            platform_stat['total_processing_time'] += processing_time
            # Calculate success rate
            total_attempts = platform_stat['downloads'] + platform_stat['error_count']
            platform_stat['success_rate'] = (platform_stat['downloads'] / total_attempts) * 100
        else:
            platform_stat['error_count'] += 1
            # Calculate success rate (failed downloads don't count as downloads)
            total_attempts = platform_stat['downloads'] + platform_stat['error_count']
            if total_attempts > 0:
                platform_stat['success_rate'] = (platform_stat['downloads'] / total_attempts) * 100
            else:
                platform_stat['success_rate'] = 0.0
        
        # Update quality stats (only for successful downloads)
        if success:
            quality_stat = self.quality_stats[quality]
            quality_stat['downloads'] += 1
            if file_size:
                quality_stat['total_file_size'] += file_size
            
            # Calculate average processing time
            if platform_stat['downloads'] > 0:
                quality_stat['average_processing_time'] = \
                    platform_stat['total_processing_time'] / platform_stat['downloads']
            else:
                quality_stat['average_processing_time'] = 0.0
        
        # Update user session
        self._update_user_session(user_id, platform, 'download')
    
    def track_audio_extraction(self, platform: str, quality: str, processing_time: float,
                             success: bool, user_id: str, file_size: Optional[int] = None):
        """
        Track audio extraction event.
        
        Args:
            platform: Platform name
            quality: Audio quality (128kbps, 320kbps)
            processing_time: Time taken to extract audio
            success: Whether extraction was successful
            user_id: User identifier
            file_size: Optional file size in bytes
        """
        # Record individual metrics
        self.record_metric("audio_extractions_total", 1, MetricType.COUNTER,
                          tags={"platform": platform, "quality": quality, "success": str(success)})
        
        self.record_metric("audio_extraction_time", processing_time, MetricType.TIMER,
                          tags={"platform": platform, "quality": quality})
        
        if file_size:
            self.record_metric("audio_file_size", file_size, MetricType.HISTOGRAM,
                              tags={"platform": platform, "quality": quality})
        
        # Update business metrics
        self.business_metrics.audio_extractions_total += 1
        
        # Update platform stats
        platform_stat = self.platform_stats[platform]
        platform_stat['audio_extractions'] += 1
        
        # Update user session
        self._update_user_session(user_id, platform, 'audio_extraction')
    
    def track_cache_operation(self, operation: str, hit: bool, response_time: float):
        """
        Track cache operation metrics.
        
        Args:
            operation: Cache operation type (get, set, invalidate)
            hit: Whether operation was a cache hit
            response_time: Time taken for cache operation
        """
        self.record_metric("cache_operations_total", 1, MetricType.COUNTER,
                          tags={"operation": operation, "hit": str(hit)})
        
        self.record_metric("cache_response_time", response_time, MetricType.TIMER,
                          tags={"operation": operation})
        
        if operation == "get":
            if hit:
                self.record_metric("cache_hits", 1, MetricType.COUNTER)
            else:
                self.record_metric("cache_misses", 1, MetricType.COUNTER)
    
    def track_error(self, error_type: str, endpoint: str, platform: Optional[str] = None,
                   user_id: Optional[str] = None):
        """
        Track error occurrence.
        
        Args:
            error_type: Type of error (validation, processing, network, etc.)
            endpoint: API endpoint where error occurred
            platform: Optional platform if error is platform-specific
            user_id: Optional user identifier
        """
        tags = {"error_type": error_type, "endpoint": endpoint}
        if platform:
            tags["platform"] = platform
        
        self.record_metric("errors_total", 1, MetricType.COUNTER, tags=tags)
        
        # Update platform error count if applicable
        if platform:
            self.platform_stats[platform]['error_count'] += 1
    
    def _update_user_session(self, user_id: str, platform: str, action: str):
        """
        Update user session tracking.
        
        Args:
            user_id: User identifier
            platform: Platform used
            action: Action performed (download, audio_extraction)
        """
        session = self.user_sessions[user_id]
        session['last_activity'] = time.time()
        session['platforms_used'].add(platform)
        
        if action == 'download':
            session['downloads'] += 1
        elif action == 'audio_extraction':
            session['audio_extractions'] += 1
    
    def get_cache_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache performance metrics.
        
        Returns:
            Dict with cache metrics and alerts
        """
        # Get cache stats from cache manager
        cache_stats = cache_manager.get_cache_stats()
        
        # Calculate additional metrics
        total_cache_ops = self.counters.get('cache_operations_total', 0)
        cache_hits = self.counters.get('cache_hits', 0)
        cache_misses = self.counters.get('cache_misses', 0)
        
        # Calculate hit rate
        hit_rate = 0.0
        if total_cache_ops > 0:
            hit_rate = (cache_hits / (cache_hits + cache_misses)) * 100
        
        # Generate alerts
        alerts = []
        if hit_rate < self.alert_thresholds['cache_hit_rate_critical']:
            alerts.append({
                'level': 'critical',
                'type': 'cache_hit_rate',
                'message': f"Cache hit rate critical: {hit_rate:.1f}%",
                'threshold': self.alert_thresholds['cache_hit_rate_critical']
            })
        elif hit_rate < self.alert_thresholds['cache_hit_rate_warning']:
            alerts.append({
                'level': 'warning',
                'type': 'cache_hit_rate',
                'message': f"Cache hit rate low: {hit_rate:.1f}%",
                'threshold': self.alert_thresholds['cache_hit_rate_warning']
            })
        
        # Calculate average response time
        cache_response_times = self.timers.get('cache_response_time', [])
        avg_response_time = sum(cache_response_times) / len(cache_response_times) if cache_response_times else 0
        
        return {
            'hit_rate': hit_rate,
            'miss_rate': 100 - hit_rate if hit_rate > 0 else 0,
            'total_operations': total_cache_ops,
            'hits': cache_hits,
            'misses': cache_misses,
            'average_response_time_ms': avg_response_time * 1000,
            'cache_manager_stats': cache_stats,
            'alerts': alerts,
            'timestamp': time.time()
        }
    
    def get_platform_metrics(self) -> Dict[str, Any]:
        """
        Get platform-specific performance metrics.
        
        Returns:
            Dict with platform metrics and performance data
        """
        platform_data = {}
        
        for platform, stats in self.platform_stats.items():
            total_operations = stats['downloads'] + stats['audio_extractions']
            avg_processing_time = 0
            
            if stats['downloads'] > 0:
                avg_processing_time = stats['total_processing_time'] / stats['downloads']
            
            platform_data[platform] = {
                'downloads': stats['downloads'],
                'audio_extractions': stats['audio_extractions'],
                'total_operations': total_operations,
                'success_rate': stats['success_rate'],
                'error_count': stats['error_count'],
                'average_processing_time': avg_processing_time,
                'popularity_rank': 0  # Will be calculated below
            }
        
        # Calculate popularity rankings
        sorted_platforms = sorted(platform_data.items(), 
                                key=lambda x: x[1]['total_operations'], reverse=True)
        
        for rank, (platform, data) in enumerate(sorted_platforms, 1):
            platform_data[platform]['popularity_rank'] = rank
        
        return platform_data
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """
        Get quality-specific metrics.
        
        Returns:
            Dict with quality metrics and usage patterns
        """
        quality_data = {}
        
        for quality, stats in self.quality_stats.items():
            avg_file_size = 0
            if stats['downloads'] > 0 and stats['total_file_size'] > 0:
                avg_file_size = stats['total_file_size'] / stats['downloads']
            
            quality_data[quality] = {
                'downloads': stats['downloads'],
                'average_file_size_mb': avg_file_size / (1024 * 1024) if avg_file_size > 0 else 0,
                'average_processing_time': stats['average_processing_time'],
                'usage_percentage': 0  # Will be calculated below
            }
        
        # Calculate usage percentages
        total_downloads = sum(stats['downloads'] for stats in self.quality_stats.values())
        if total_downloads > 0:
            for quality in quality_data:
                usage_count = quality_data[quality]['downloads']
                quality_data[quality]['usage_percentage'] = (usage_count / total_downloads) * 100
        
        return quality_data
    
    def get_user_engagement_metrics(self) -> Dict[str, Any]:
        """
        Get user engagement and retention metrics.
        
        Returns:
            Dict with user engagement data
        """
        current_time = time.time()
        active_users = 0
        returning_users = 0
        total_sessions = len(self.user_sessions)
        
        # Calculate active and returning users (last 24 hours)
        for user_id, session in self.user_sessions.items():
            time_since_last_activity = current_time - session['last_activity']
            
            # Active in last 24 hours
            if time_since_last_activity < 86400:  # 24 hours
                active_users += 1
            
            # Returning user (more than one total operation)
            if session['downloads'] + session['audio_extractions'] > 1:
                returning_users += 1
        
        # Calculate retention rate
        retention_rate = (returning_users / total_sessions * 100) if total_sessions > 0 else 0
        
        # Calculate average operations per user
        total_operations = sum(
            session['downloads'] + session['audio_extractions'] 
            for session in self.user_sessions.values()
        )
        avg_operations_per_user = total_operations / total_sessions if total_sessions > 0 else 0
        
        return {
            'total_users': total_sessions,
            'active_users_24h': active_users,
            'returning_users': returning_users,
            'retention_rate': retention_rate,
            'average_operations_per_user': avg_operations_per_user,
            'total_operations': total_operations,
            'timestamp': current_time
        }
    
    def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """
        Generate performance alerts based on current metrics.
        
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        # Cache hit rate alerts
        cache_metrics = self.get_cache_metrics()
        alerts.extend(cache_metrics.get('alerts', []))
        
        # Platform success rate alerts
        platform_metrics = self.get_platform_metrics()
        for platform, data in platform_metrics.items():
            success_rate = data['success_rate']
            
            if success_rate < self.alert_thresholds['download_success_rate_critical']:
                alerts.append({
                    'level': 'critical',
                    'type': 'platform_success_rate',
                    'platform': platform,
                    'message': f"{platform} success rate critical: {success_rate:.1f}%",
                    'threshold': self.alert_thresholds['download_success_rate_critical']
                })
            elif success_rate < self.alert_thresholds['download_success_rate_warning']:
                alerts.append({
                    'level': 'warning',
                    'type': 'platform_success_rate',
                    'platform': platform,
                    'message': f"{platform} success rate low: {success_rate:.1f}%",
                    'threshold': self.alert_thresholds['download_success_rate_warning']
                })
            
            # Processing time alerts
            avg_time = data['average_processing_time']
            if avg_time > self.alert_thresholds['average_processing_time_critical']:
                alerts.append({
                    'level': 'critical',
                    'type': 'processing_time',
                    'platform': platform,
                    'message': f"{platform} processing time critical: {avg_time:.2f}s",
                    'threshold': self.alert_thresholds['average_processing_time_critical']
                })
            elif avg_time > self.alert_thresholds['average_processing_time_warning']:
                alerts.append({
                    'level': 'warning',
                    'type': 'processing_time',
                    'platform': platform,
                    'message': f"{platform} processing time high: {avg_time:.2f}s",
                    'threshold': self.alert_thresholds['average_processing_time_warning']
                })
        
        return alerts
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for visualization.
        
        Returns:
            Dict with all dashboard metrics and data
        """
        # Get performance monitor data
        performance_summary = performance_monitor.get_performance_summary(60)
        system_metrics = performance_monitor.get_system_metrics()
        health_status = performance_monitor.get_health_status()
        
        # Get custom metrics
        cache_metrics = self.get_cache_metrics()
        platform_metrics = self.get_platform_metrics()
        quality_metrics = self.get_quality_metrics()
        user_engagement = self.get_user_engagement_metrics()
        alerts = self.get_performance_alerts()
        
        # Calculate key performance indicators
        total_downloads = self.business_metrics.downloads_total
        total_audio_extractions = self.business_metrics.audio_extractions_total
        total_operations = total_downloads + total_audio_extractions
        
        # Overall success rate
        total_errors = sum(self.counters.get(f'errors_total', 0) for _ in self.platform_stats)
        overall_success_rate = ((total_operations - total_errors) / total_operations * 100) if total_operations > 0 else 100
        
        dashboard_data = {
            'overview': {
                'total_downloads': total_downloads,
                'total_audio_extractions': total_audio_extractions,
                'total_operations': total_operations,
                'overall_success_rate': overall_success_rate,
                'cache_hit_rate': cache_metrics['hit_rate'],
                'active_users_24h': user_engagement['active_users_24h'],
                'system_health_score': health_status.get('health_score', 0),
                'total_alerts': len(alerts),
                'critical_alerts': len([a for a in alerts if a.get('level') == 'critical'])
            },
            'performance': {
                'system_metrics': system_metrics,
                'performance_summary': performance_summary,
                'health_status': health_status,
                'response_times': {
                    'api_average': performance_summary.get('average_response_time', 0),
                    'cache_average': cache_metrics['average_response_time_ms']
                }
            },
            'business_metrics': {
                'platform_metrics': platform_metrics,
                'quality_metrics': quality_metrics,
                'user_engagement': user_engagement,
                'downloads_by_platform': dict(self.business_metrics.downloads_by_platform),
                'downloads_by_quality': dict(self.business_metrics.downloads_by_quality)
            },
            'cache_performance': cache_metrics,
            'alerts': alerts,
            'timestamp': time.time()
        }
        
        return dashboard_data
    
    def export_metrics(self, filepath: str, time_window_hours: int = 24):
        """
        Export metrics to JSON file.
        
        Args:
            filepath: Path to export file
            time_window_hours: Time window for metrics export
        """
        try:
            cutoff_time = time.time() - (time_window_hours * 3600)
            
            # Filter recent events
            recent_events = [
                {
                    'timestamp': event.timestamp,
                    'metric_name': event.metric_name,
                    'metric_type': event.metric_type.value,
                    'value': event.value,
                    'tags': event.tags,
                    'metadata': event.metadata
                }
                for event in self.metric_events 
                if event.timestamp >= cutoff_time
            ]
            
            export_data = {
                'export_info': {
                    'timestamp': time.time(),
                    'time_window_hours': time_window_hours,
                    'total_events': len(recent_events)
                },
                'dashboard_data': self.get_dashboard_data(),
                'metric_events': recent_events,
                'business_metrics': {
                    'downloads_total': self.business_metrics.downloads_total,
                    'audio_extractions_total': self.business_metrics.audio_extractions_total,
                    'downloads_by_platform': dict(self.business_metrics.downloads_by_platform),
                    'downloads_by_quality': dict(self.business_metrics.downloads_by_quality)
                },
                'platform_stats': dict(self.platform_stats),
                'quality_stats': dict(self.quality_stats)
            }
            
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Metrics exported to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            raise


# Global metrics collector instance
metrics_collector = MetricsCollector()