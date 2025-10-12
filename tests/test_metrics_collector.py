"""
Tests for the metrics collector service.

This module tests the comprehensive metrics collection functionality,
including business metrics, performance tracking, and dashboard data.
"""

import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from collections import defaultdict

from app.services.metrics_collector import (
    MetricsCollector, MetricType, MetricEvent, BusinessMetrics
)


class TestMetricsCollector:
    """Test suite for MetricsCollector class."""
    
    @pytest.fixture
    def metrics_collector(self):
        """Create a fresh metrics collector instance for testing."""
        return MetricsCollector(max_events_history=1000)
    
    def test_initialization(self, metrics_collector):
        """Test metrics collector initialization."""
        assert metrics_collector.max_events_history == 1000
        assert len(metrics_collector.metric_events) == 0
        assert len(metrics_collector.business_metrics_history) == 0
        assert metrics_collector.business_metrics.downloads_total == 0
        assert metrics_collector.business_metrics.audio_extractions_total == 0
        assert isinstance(metrics_collector.counters, defaultdict)
        assert isinstance(metrics_collector.gauges, defaultdict)
        assert isinstance(metrics_collector.histograms, defaultdict)
        assert isinstance(metrics_collector.timers, defaultdict)
    
    def test_record_metric_counter(self, metrics_collector):
        """Test recording counter metrics."""
        metrics_collector.record_metric(
            name="test_counter",
            value=5,
            metric_type=MetricType.COUNTER,
            tags={"platform": "youtube"},
            metadata={"test": True}
        )
        
        # Check that event was recorded
        assert len(metrics_collector.metric_events) == 1
        event = metrics_collector.metric_events[0]
        assert event.metric_name == "test_counter"
        assert event.value == 5
        assert event.metric_type == MetricType.COUNTER
        assert event.tags == {"platform": "youtube"}
        assert event.metadata == {"test": True}
        
        # Check counter was updated
        assert metrics_collector.counters["test_counter"] == 5
        
        # Record another counter event
        metrics_collector.record_metric("test_counter", 3, MetricType.COUNTER)
        assert metrics_collector.counters["test_counter"] == 8
    
    def test_record_metric_gauge(self, metrics_collector):
        """Test recording gauge metrics."""
        metrics_collector.record_metric("cpu_usage", 75.5, MetricType.GAUGE)
        
        assert len(metrics_collector.metric_events) == 1
        assert metrics_collector.gauges["cpu_usage"] == 75.5
        
        # Gauge should be overwritten, not accumulated
        metrics_collector.record_metric("cpu_usage", 80.0, MetricType.GAUGE)
        assert metrics_collector.gauges["cpu_usage"] == 80.0
    
    def test_record_metric_histogram(self, metrics_collector):
        """Test recording histogram metrics."""
        values = [1.2, 2.5, 3.1, 1.8, 2.9]
        
        for value in values:
            metrics_collector.record_metric("response_time", value, MetricType.HISTOGRAM)
        
        assert len(metrics_collector.metric_events) == 5
        assert len(metrics_collector.histograms["response_time"]) == 5
        assert metrics_collector.histograms["response_time"] == values
    
    def test_record_metric_timer(self, metrics_collector):
        """Test recording timer metrics."""
        times = [0.1, 0.2, 0.15, 0.3]
        
        for time_val in times:
            metrics_collector.record_metric("processing_time", time_val, MetricType.TIMER)
        
        assert len(metrics_collector.timers["processing_time"]) == 4
        assert metrics_collector.timers["processing_time"] == times
    
    def test_track_download_success(self, metrics_collector):
        """Test tracking successful download events."""
        metrics_collector.track_download(
            platform="youtube",
            quality="1080p",
            processing_time=2.5,
            success=True,
            user_id="user123",
            file_size=50000000  # 50MB
        )
        
        # Check business metrics updated
        assert metrics_collector.business_metrics.downloads_total == 1
        assert metrics_collector.business_metrics.downloads_by_platform["youtube"] == 1
        assert metrics_collector.business_metrics.downloads_by_quality["1080p"] == 1
        
        # Check platform stats
        platform_stat = metrics_collector.platform_stats["youtube"]
        assert platform_stat["downloads"] == 1
        assert platform_stat["total_processing_time"] == 2.5
        assert platform_stat["success_rate"] == 100.0
        assert platform_stat["error_count"] == 0
        
        # Check quality stats
        quality_stat = metrics_collector.quality_stats["1080p"]
        assert quality_stat["downloads"] == 1
        assert quality_stat["total_file_size"] == 50000000
        
        # Check user session
        session = metrics_collector.user_sessions["user123"]
        assert session["downloads"] == 1
        assert session["audio_extractions"] == 0
        assert "youtube" in session["platforms_used"]
    
    def test_track_download_failure(self, metrics_collector):
        """Test tracking failed download events."""
        metrics_collector.track_download(
            platform="tiktok",
            quality="720p",
            processing_time=1.0,
            success=False,
            user_id="user456"
        )
        
        # Check platform stats for failure
        platform_stat = metrics_collector.platform_stats["tiktok"]
        assert platform_stat["downloads"] == 0  # Failed downloads don't count as downloads
        assert platform_stat["error_count"] == 1
        assert platform_stat["success_rate"] == 0.0
    
    def test_track_audio_extraction(self, metrics_collector):
        """Test tracking audio extraction events."""
        metrics_collector.track_audio_extraction(
            platform="youtube",
            quality="320kbps",
            processing_time=1.5,
            success=True,
            user_id="user789",
            file_size=5000000  # 5MB
        )
        
        # Check business metrics
        assert metrics_collector.business_metrics.audio_extractions_total == 1
        
        # Check platform stats
        platform_stat = metrics_collector.platform_stats["youtube"]
        assert platform_stat["audio_extractions"] == 1
        
        # Check user session
        session = metrics_collector.user_sessions["user789"]
        assert session["audio_extractions"] == 1
        assert "youtube" in session["platforms_used"]
    
    def test_track_cache_operation(self, metrics_collector):
        """Test tracking cache operations."""
        # Track cache hit
        metrics_collector.track_cache_operation("get", True, 0.001)
        
        # Track cache miss
        metrics_collector.track_cache_operation("get", False, 0.005)
        
        # Check counters
        assert metrics_collector.counters["cache_operations_total"] == 2
        assert metrics_collector.counters["cache_hits"] == 1
        assert metrics_collector.counters["cache_misses"] == 1
        
        # Check timers
        assert len(metrics_collector.timers["cache_response_time"]) == 2
    
    def test_track_error(self, metrics_collector):
        """Test tracking error events."""
        metrics_collector.track_error(
            error_type="validation",
            endpoint="/api/v1/download",
            platform="youtube",
            user_id="user123"
        )
        
        # Check error counter
        assert metrics_collector.counters["errors_total"] == 1
        
        # Check platform error count
        assert metrics_collector.platform_stats["youtube"]["error_count"] == 1
    
    @patch('app.services.metrics_collector.cache_manager')
    def test_get_cache_metrics(self, mock_cache_manager, metrics_collector):
        """Test getting cache performance metrics."""
        # Mock cache manager stats
        mock_cache_manager.get_cache_stats.return_value = {
            'hit_rate': 85.5,
            'miss_rate': 14.5,
            'total_requests': 1000,
            'hits': 855,
            'misses': 145,
            'errors': 0
        }
        
        # Add some cache operations
        metrics_collector.counters["cache_operations_total"] = 1000
        metrics_collector.counters["cache_hits"] = 855
        metrics_collector.counters["cache_misses"] = 145
        metrics_collector.timers["cache_response_time"] = [0.001, 0.002, 0.001, 0.003]
        
        cache_metrics = metrics_collector.get_cache_metrics()
        
        assert cache_metrics["hit_rate"] == 85.5
        assert cache_metrics["miss_rate"] == 14.5
        assert cache_metrics["total_operations"] == 1000
        assert cache_metrics["hits"] == 855
        assert cache_metrics["misses"] == 145
        assert "average_response_time_ms" in cache_metrics
        assert "cache_manager_stats" in cache_metrics
        assert "alerts" in cache_metrics
    
    def test_get_platform_metrics(self, metrics_collector):
        """Test getting platform-specific metrics."""
        # Add some platform data
        metrics_collector.track_download("youtube", "1080p", 2.0, True, "user1")
        metrics_collector.track_download("youtube", "720p", 1.5, True, "user2")
        metrics_collector.track_download("tiktok", "720p", 1.0, True, "user3")
        metrics_collector.track_audio_extraction("youtube", "320kbps", 1.0, True, "user1")
        
        platform_metrics = metrics_collector.get_platform_metrics()
        
        # Check YouTube metrics
        youtube_metrics = platform_metrics["youtube"]
        assert youtube_metrics["downloads"] == 2
        assert youtube_metrics["audio_extractions"] == 1
        assert youtube_metrics["total_operations"] == 3
        assert youtube_metrics["success_rate"] == 100.0
        assert youtube_metrics["popularity_rank"] == 1  # Most popular
        
        # Check TikTok metrics
        tiktok_metrics = platform_metrics["tiktok"]
        assert tiktok_metrics["downloads"] == 1
        assert tiktok_metrics["audio_extractions"] == 0
        assert tiktok_metrics["total_operations"] == 1
        assert tiktok_metrics["popularity_rank"] == 2  # Less popular
    
    def test_get_quality_metrics(self, metrics_collector):
        """Test getting quality-specific metrics."""
        # Add downloads with different qualities
        metrics_collector.track_download("youtube", "1080p", 2.0, True, "user1", 50000000)
        metrics_collector.track_download("youtube", "1080p", 2.2, True, "user2", 55000000)
        metrics_collector.track_download("youtube", "720p", 1.5, True, "user3", 30000000)
        
        quality_metrics = metrics_collector.get_quality_metrics()
        
        # Check 1080p metrics
        hd_metrics = quality_metrics["1080p"]
        assert hd_metrics["downloads"] == 2
        assert hd_metrics["usage_percentage"] == pytest.approx(66.67, rel=1e-2)
        assert hd_metrics["average_file_size_mb"] > 0
        
        # Check 720p metrics
        sd_metrics = quality_metrics["720p"]
        assert sd_metrics["downloads"] == 1
        assert sd_metrics["usage_percentage"] == pytest.approx(33.33, rel=1e-2)
    
    def test_get_user_engagement_metrics(self, metrics_collector):
        """Test getting user engagement metrics."""
        current_time = time.time()
        
        # Create user sessions with different activity levels
        metrics_collector.user_sessions["user1"] = {
            'first_visit': current_time - 3600,  # 1 hour ago
            'last_activity': current_time - 100,  # Recent activity
            'downloads': 3,
            'audio_extractions': 1,
            'platforms_used': {"youtube", "tiktok"}
        }
        
        metrics_collector.user_sessions["user2"] = {
            'first_visit': current_time - 7200,  # 2 hours ago
            'last_activity': current_time - 200,  # Recent activity
            'downloads': 1,
            'audio_extractions': 0,
            'platforms_used': {"youtube"}
        }
        
        metrics_collector.user_sessions["user3"] = {
            'first_visit': current_time - 90000,  # 25 hours ago
            'last_activity': current_time - 90000,  # Old activity
            'downloads': 2,
            'audio_extractions': 1,
            'platforms_used': {"instagram"}
        }
        
        engagement_metrics = metrics_collector.get_user_engagement_metrics()
        
        assert engagement_metrics["total_users"] == 3
        assert engagement_metrics["active_users_24h"] == 2  # user1 and user2
        assert engagement_metrics["returning_users"] == 2  # user1 (4 ops) and user3 (3 ops) have >1 operations
        assert engagement_metrics["retention_rate"] == pytest.approx(66.67, rel=1e-2)  # 2 returning users out of 3 total
        assert engagement_metrics["total_operations"] == 8  # 3+1+1+0+2+1
        assert engagement_metrics["average_operations_per_user"] == pytest.approx(2.67, rel=1e-2)
    
    def test_get_performance_alerts(self, metrics_collector):
        """Test generating performance alerts."""
        # Set up conditions that should trigger alerts
        
        # Low cache hit rate
        metrics_collector.counters["cache_hits"] = 40
        metrics_collector.counters["cache_misses"] = 60
        
        # Low platform success rate
        metrics_collector.platform_stats["youtube"]["downloads"] = 70
        metrics_collector.platform_stats["youtube"]["error_count"] = 30
        metrics_collector.platform_stats["youtube"]["success_rate"] = 70.0  # Below warning threshold
        
        # High processing time
        metrics_collector.platform_stats["tiktok"]["downloads"] = 10
        metrics_collector.platform_stats["tiktok"]["total_processing_time"] = 120.0  # 12s average
        metrics_collector.platform_stats["tiktok"]["success_rate"] = 100.0
        
        alerts = metrics_collector.get_performance_alerts()
        
        # Should have alerts for cache hit rate and platform issues
        assert len(alerts) > 0
        
        # Check for cache hit rate alert
        cache_alerts = [a for a in alerts if a.get('type') == 'cache_hit_rate']
        assert len(cache_alerts) > 0
        
        # Check for platform success rate alert
        success_rate_alerts = [a for a in alerts if a.get('type') == 'platform_success_rate']
        assert len(success_rate_alerts) > 0
        
        # Check for processing time alert
        processing_time_alerts = [a for a in alerts if a.get('type') == 'processing_time']
        assert len(processing_time_alerts) > 0
    
    @patch('app.services.metrics_collector.performance_monitor')
    @patch('app.services.metrics_collector.cache_manager')
    def test_get_dashboard_data(self, mock_cache_manager, mock_performance_monitor, metrics_collector):
        """Test getting comprehensive dashboard data."""
        # Mock dependencies
        mock_performance_monitor.get_performance_summary.return_value = {
            'total_requests': 1000,
            'average_response_time': 1.5,
            'error_rate': 2.0
        }
        
        mock_performance_monitor.get_system_metrics.return_value = {
            'cpu_percent': 45.0,
            'memory_percent': 60.0
        }
        
        mock_performance_monitor.get_health_status.return_value = {
            'status': 'healthy',
            'health_score': 95
        }
        
        mock_cache_manager.get_cache_stats.return_value = {
            'hit_rate': 85.0,
            'total_requests': 500
        }
        
        # Add some business data
        metrics_collector.business_metrics.downloads_total = 100
        metrics_collector.business_metrics.audio_extractions_total = 25
        
        dashboard_data = metrics_collector.get_dashboard_data()
        
        # Check structure
        assert "overview" in dashboard_data
        assert "performance" in dashboard_data
        assert "business_metrics" in dashboard_data
        assert "cache_performance" in dashboard_data
        assert "alerts" in dashboard_data
        assert "timestamp" in dashboard_data
        
        # Check overview data
        overview = dashboard_data["overview"]
        assert overview["total_downloads"] == 100
        assert overview["total_audio_extractions"] == 25
        assert overview["total_operations"] == 125
        assert "overall_success_rate" in overview
        assert "cache_hit_rate" in overview
    
    def test_export_metrics(self, metrics_collector, tmp_path):
        """Test exporting metrics to file."""
        # Add some test data
        metrics_collector.track_download("youtube", "1080p", 2.0, True, "user1")
        metrics_collector.track_audio_extraction("youtube", "320kbps", 1.0, True, "user1")
        
        # Export to temporary file
        export_file = tmp_path / "test_metrics.json"
        metrics_collector.export_metrics(str(export_file), time_window_hours=1)
        
        # Verify file was created and contains data
        assert export_file.exists()
        
        with open(export_file, 'r') as f:
            exported_data = json.load(f)
        
        # Check structure
        assert "export_info" in exported_data
        assert "dashboard_data" in exported_data
        assert "metric_events" in exported_data
        assert "business_metrics" in exported_data
        assert "platform_stats" in exported_data
        assert "quality_stats" in exported_data
        
        # Check export info
        export_info = exported_data["export_info"]
        assert export_info["time_window_hours"] == 1
        assert "timestamp" in export_info
        assert "total_events" in export_info
    
    def test_histogram_memory_management(self, metrics_collector):
        """Test that histograms don't grow indefinitely."""
        # Add more than 1000 values to a histogram
        for i in range(1500):
            metrics_collector.record_metric("test_histogram", i, MetricType.HISTOGRAM)
        
        # Should be limited to 1000 values
        assert len(metrics_collector.histograms["test_histogram"]) == 1000
        
        # Should contain the most recent 1000 values
        histogram_values = metrics_collector.histograms["test_histogram"]
        assert histogram_values[0] == 500  # First of the last 1000
        assert histogram_values[-1] == 1499  # Last value
    
    def test_timer_memory_management(self, metrics_collector):
        """Test that timers don't grow indefinitely."""
        # Add more than 1000 values to a timer
        for i in range(1200):
            metrics_collector.record_metric("test_timer", i * 0.001, MetricType.TIMER)
        
        # Should be limited to 1000 values
        assert len(metrics_collector.timers["test_timer"]) == 1000
        
        # Should contain the most recent 1000 values
        timer_values = metrics_collector.timers["test_timer"]
        assert timer_values[0] == 0.2  # First of the last 1000 (200 * 0.001)
        assert timer_values[-1] == 1.199  # Last value (1199 * 0.001)


class TestMetricEvent:
    """Test suite for MetricEvent dataclass."""
    
    def test_metric_event_creation(self):
        """Test creating a metric event."""
        timestamp = time.time()
        event = MetricEvent(
            timestamp=timestamp,
            metric_name="test_metric",
            metric_type=MetricType.COUNTER,
            value=42,
            tags={"platform": "youtube"},
            metadata={"test": True}
        )
        
        assert event.timestamp == timestamp
        assert event.metric_name == "test_metric"
        assert event.metric_type == MetricType.COUNTER
        assert event.value == 42
        assert event.tags == {"platform": "youtube"}
        assert event.metadata == {"test": True}
    
    def test_metric_event_defaults(self):
        """Test metric event with default values."""
        event = MetricEvent(
            timestamp=time.time(),
            metric_name="test",
            metric_type=MetricType.GAUGE,
            value=1.0
        )
        
        assert event.tags == {}
        assert event.metadata == {}


class TestBusinessMetrics:
    """Test suite for BusinessMetrics dataclass."""
    
    def test_business_metrics_creation(self):
        """Test creating business metrics."""
        timestamp = time.time()
        metrics = BusinessMetrics(
            timestamp=timestamp,
            downloads_total=100,
            downloads_by_platform={"youtube": 60, "tiktok": 40},
            downloads_by_quality={"1080p": 70, "720p": 30},
            audio_extractions_total=25
        )
        
        assert metrics.timestamp == timestamp
        assert metrics.downloads_total == 100
        assert metrics.downloads_by_platform["youtube"] == 60
        assert metrics.downloads_by_quality["1080p"] == 70
        assert metrics.audio_extractions_total == 25
    
    def test_business_metrics_defaults(self):
        """Test business metrics with default values."""
        metrics = BusinessMetrics(timestamp=time.time())
        
        assert metrics.downloads_total == 0
        assert metrics.downloads_by_platform == {}
        assert metrics.downloads_by_quality == {}
        assert metrics.audio_extractions_total == 0
        assert metrics.unique_users == 0
        assert metrics.conversion_rate == 0.0
        assert metrics.revenue_per_user == 0.0
        assert metrics.user_retention_rate == 0.0


class TestMetricType:
    """Test suite for MetricType enum."""
    
    def test_metric_type_values(self):
        """Test metric type enum values."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.TIMER.value == "timer"
    
    def test_metric_type_from_string(self):
        """Test creating metric type from string."""
        assert MetricType("counter") == MetricType.COUNTER
        assert MetricType("gauge") == MetricType.GAUGE
        assert MetricType("histogram") == MetricType.HISTOGRAM
        assert MetricType("timer") == MetricType.TIMER
        
        with pytest.raises(ValueError):
            MetricType("invalid_type")