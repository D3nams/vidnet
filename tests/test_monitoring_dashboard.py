"""
Tests for the monitoring dashboard API endpoints.

This module tests the monitoring API endpoints that provide
dashboard data, metrics, and performance monitoring.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.metrics_collector import MetricType


class TestMonitoringDashboardAPI:
    """Test suite for monitoring dashboard API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_metrics_collector(self):
        """Mock metrics collector for testing."""
        with patch('app.api.monitoring.metrics_collector') as mock:
            yield mock
    
    @pytest.fixture
    def mock_performance_monitor(self):
        """Mock performance monitor for testing."""
        with patch('app.api.monitoring.performance_monitor') as mock:
            yield mock
    
    @pytest.fixture
    def mock_rate_limiter(self):
        """Mock rate limiter for testing."""
        with patch('app.api.monitoring.rate_limiter') as mock:
            yield mock
    
    def test_get_dashboard_data_success(self, client, mock_metrics_collector):
        """Test successful dashboard data retrieval."""
        # Mock dashboard data
        mock_dashboard_data = {
            "overview": {
                "total_downloads": 1000,
                "total_audio_extractions": 250,
                "total_operations": 1250,
                "overall_success_rate": 95.5,
                "cache_hit_rate": 85.0,
                "active_users_24h": 150,
                "system_health_score": 92,
                "total_alerts": 2,
                "critical_alerts": 0
            },
            "performance": {
                "system_metrics": {
                    "cpu_percent": 45.0,
                    "memory_percent": 60.0,
                    "timestamp": 1234567890
                },
                "performance_summary": {
                    "total_requests": 5000,
                    "average_response_time": 1.2,
                    "error_rate": 2.5
                },
                "health_status": {
                    "status": "healthy",
                    "health_score": 92
                }
            },
            "business_metrics": {
                "platform_metrics": {
                    "youtube": {
                        "downloads": 600,
                        "success_rate": 96.0,
                        "popularity_rank": 1
                    },
                    "tiktok": {
                        "downloads": 400,
                        "success_rate": 94.0,
                        "popularity_rank": 2
                    }
                },
                "quality_metrics": {
                    "1080p": {
                        "downloads": 700,
                        "usage_percentage": 70.0
                    },
                    "720p": {
                        "downloads": 300,
                        "usage_percentage": 30.0
                    }
                },
                "user_engagement": {
                    "total_users": 500,
                    "active_users_24h": 150,
                    "retention_rate": 65.0
                }
            },
            "cache_performance": {
                "hit_rate": 85.0,
                "miss_rate": 15.0,
                "total_operations": 2000,
                "alerts": []
            },
            "alerts": [
                {
                    "level": "warning",
                    "type": "cache_hit_rate",
                    "message": "Cache hit rate low: 75.0%"
                }
            ],
            "timestamp": 1234567890
        }
        
        mock_metrics_collector.get_dashboard_data.return_value = mock_dashboard_data
        
        response = client.get("/api/v1/monitoring/dashboard")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "response_time_ms" in data
        
        dashboard_data = data["data"]
        assert dashboard_data["overview"]["total_downloads"] == 1000
        assert dashboard_data["overview"]["total_audio_extractions"] == 250
        assert dashboard_data["performance"]["system_metrics"]["cpu_percent"] == 45.0
        assert len(dashboard_data["alerts"]) == 1
        
        mock_metrics_collector.get_dashboard_data.assert_called_once()
    
    def test_get_dashboard_data_error(self, client, mock_metrics_collector):
        """Test dashboard data retrieval with error."""
        mock_metrics_collector.get_dashboard_data.side_effect = Exception("Database error")
        
        response = client.get("/api/v1/monitoring/dashboard")
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "dashboard_error"
        assert "Database error" in data["details"]
    
    def test_get_business_metrics_success(self, client, mock_metrics_collector):
        """Test successful business metrics retrieval."""
        # Mock business metrics data
        mock_platform_metrics = {
            "youtube": {
                "downloads": 600,
                "audio_extractions": 150,
                "total_operations": 750,
                "success_rate": 96.0,
                "error_count": 30,
                "average_processing_time": 2.1,
                "popularity_rank": 1
            },
            "tiktok": {
                "downloads": 400,
                "audio_extractions": 100,
                "total_operations": 500,
                "success_rate": 94.0,
                "error_count": 32,
                "average_processing_time": 1.8,
                "popularity_rank": 2
            }
        }
        
        mock_quality_metrics = {
            "1080p": {
                "downloads": 700,
                "average_file_size_mb": 45.2,
                "average_processing_time": 2.5,
                "usage_percentage": 70.0
            },
            "720p": {
                "downloads": 300,
                "average_file_size_mb": 25.1,
                "average_processing_time": 1.8,
                "usage_percentage": 30.0
            }
        }
        
        mock_user_engagement = {
            "total_users": 500,
            "active_users_24h": 150,
            "returning_users": 325,
            "retention_rate": 65.0,
            "average_operations_per_user": 2.5,
            "total_operations": 1250
        }
        
        # Mock business metrics object
        mock_business_metrics = Mock()
        mock_business_metrics.downloads_total = 1000
        mock_business_metrics.audio_extractions_total = 250
        mock_business_metrics.downloads_by_platform = {"youtube": 600, "tiktok": 400}
        mock_business_metrics.downloads_by_quality = {"1080p": 700, "720p": 300}
        
        mock_metrics_collector.get_platform_metrics.return_value = mock_platform_metrics
        mock_metrics_collector.get_quality_metrics.return_value = mock_quality_metrics
        mock_metrics_collector.get_user_engagement_metrics.return_value = mock_user_engagement
        mock_metrics_collector.business_metrics = mock_business_metrics
        
        response = client.get("/api/v1/monitoring/business-metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        business_data = data["data"]
        assert "platform_metrics" in business_data
        assert "quality_metrics" in business_data
        assert "user_engagement" in business_data
        assert "business_summary" in business_data
        
        # Check platform metrics
        assert business_data["platform_metrics"]["youtube"]["downloads"] == 600
        assert business_data["platform_metrics"]["youtube"]["success_rate"] == 96.0
        
        # Check business summary
        summary = business_data["business_summary"]
        assert summary["total_downloads"] == 1000
        assert summary["total_audio_extractions"] == 250
        assert summary["downloads_by_platform"]["youtube"] == 600
    
    def test_get_cache_metrics_success(self, client, mock_metrics_collector):
        """Test successful cache metrics retrieval."""
        mock_cache_metrics = {
            "hit_rate": 85.5,
            "miss_rate": 14.5,
            "total_operations": 2000,
            "hits": 1710,
            "misses": 290,
            "average_response_time_ms": 1.2,
            "cache_manager_stats": {
                "hit_rate": 85.5,
                "total_requests": 2000
            },
            "alerts": [
                {
                    "level": "warning",
                    "type": "cache_hit_rate",
                    "message": "Cache hit rate low: 75.0%",
                    "threshold": 80.0
                }
            ],
            "timestamp": 1234567890
        }
        
        mock_metrics_collector.get_cache_metrics.return_value = mock_cache_metrics
        
        response = client.get("/api/v1/monitoring/cache-metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        cache_data = data["data"]
        
        assert cache_data["hit_rate"] == 85.5
        assert cache_data["miss_rate"] == 14.5
        assert cache_data["total_operations"] == 2000
        assert len(cache_data["alerts"]) == 1
        assert cache_data["alerts"][0]["level"] == "warning"
    
    def test_get_performance_alerts_success(self, client, mock_metrics_collector):
        """Test successful performance alerts retrieval."""
        mock_alerts = [
            {
                "level": "critical",
                "type": "platform_success_rate",
                "platform": "instagram",
                "message": "instagram success rate critical: 75.0%",
                "threshold": 80.0
            },
            {
                "level": "warning",
                "type": "cache_hit_rate",
                "message": "Cache hit rate low: 78.0%",
                "threshold": 80.0
            },
            {
                "level": "warning",
                "type": "processing_time",
                "platform": "facebook",
                "message": "facebook processing time high: 6.5s",
                "threshold": 5.0
            }
        ]
        
        mock_thresholds = {
            "cache_hit_rate_warning": 80.0,
            "cache_hit_rate_critical": 60.0,
            "download_success_rate_warning": 90.0,
            "download_success_rate_critical": 80.0,
            "average_processing_time_warning": 5.0,
            "average_processing_time_critical": 10.0
        }
        
        mock_metrics_collector.get_performance_alerts.return_value = mock_alerts
        mock_metrics_collector.alert_thresholds = mock_thresholds
        
        response = client.get("/api/v1/monitoring/performance-alerts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        alerts_data = data["data"]
        
        assert len(alerts_data["alerts"]) == 3
        assert alerts_data["summary"]["total_alerts"] == 3
        assert alerts_data["summary"]["critical_alerts"] == 1
        assert alerts_data["summary"]["warning_alerts"] == 2
        
        # Check critical alerts
        critical_alerts = alerts_data["critical_alerts"]
        assert len(critical_alerts) == 1
        assert critical_alerts[0]["platform"] == "instagram"
        
        # Check warning alerts
        warning_alerts = alerts_data["warning_alerts"]
        assert len(warning_alerts) == 2
        
        # Check thresholds
        assert alerts_data["thresholds"]["cache_hit_rate_warning"] == 80.0
    
    def test_track_metric_event_success(self, client, mock_metrics_collector):
        """Test successful metric event tracking."""
        response = client.post(
            "/api/v1/monitoring/track-event",
            params={
                "metric_name": "custom_downloads",
                "value": 5,
                "metric_type": "counter",
                "tags": '{"platform": "youtube", "quality": "1080p"}',
                "metadata": '{"test": true, "source": "api"}'
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "Metric event tracked successfully"
        
        event_data = data["data"]
        assert event_data["metric_name"] == "custom_downloads"
        assert event_data["value"] == 5
        assert event_data["metric_type"] == "counter"
        assert event_data["tags"]["platform"] == "youtube"
        assert event_data["metadata"]["test"] is True
        
        # Verify metrics collector was called
        mock_metrics_collector.record_metric.assert_called_once()
        call_args = mock_metrics_collector.record_metric.call_args
        assert call_args[1]["name"] == "custom_downloads"
        assert call_args[1]["value"] == 5
        assert call_args[1]["metric_type"] == MetricType.COUNTER
    
    def test_track_metric_event_invalid_metric_type(self, client, mock_metrics_collector):
        """Test metric event tracking with invalid metric type."""
        response = client.post(
            "/api/v1/monitoring/track-event",
            params={
                "metric_name": "test_metric",
                "value": 1,
                "metric_type": "invalid_type"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "invalid_metric_type"
        assert "counter" in data["message"]
        assert "gauge" in data["message"]
    
    def test_track_metric_event_invalid_tags_json(self, client, mock_metrics_collector):
        """Test metric event tracking with invalid tags JSON."""
        response = client.post(
            "/api/v1/monitoring/track-event",
            params={
                "metric_name": "test_metric",
                "value": 1,
                "metric_type": "counter",
                "tags": "invalid json"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "invalid_tags"
        assert "valid JSON" in data["message"]
    
    def test_track_metric_event_invalid_metadata_json(self, client, mock_metrics_collector):
        """Test metric event tracking with invalid metadata JSON."""
        response = client.post(
            "/api/v1/monitoring/track-event",
            params={
                "metric_name": "test_metric",
                "value": 1,
                "metric_type": "counter",
                "metadata": "{invalid: json}"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "invalid_metadata"
        assert "valid JSON" in data["message"]
    
    def test_track_metric_event_no_optional_params(self, client, mock_metrics_collector):
        """Test metric event tracking without optional parameters."""
        response = client.post(
            "/api/v1/monitoring/track-event",
            params={
                "metric_name": "simple_metric",
                "value": 42.5,
                "metric_type": "gauge"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        event_data = data["data"]
        assert event_data["tags"] == {}
        assert event_data["metadata"] == {}
    
    def test_export_metrics_success(self, client, mock_metrics_collector):
        """Test successful metrics export."""
        response = client.post(
            "/api/v1/monitoring/export",
            params={"time_window_hours": 12}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "exported_file" in data["data"]
        assert "timestamp" in data["data"]
        assert data["data"]["time_window_hours"] == 12
        assert "Metrics exported" in data["message"]
        
        # Verify export was called with correct parameters
        mock_metrics_collector.export_metrics.assert_called_once()
        call_args = mock_metrics_collector.export_metrics.call_args
        assert call_args[0][1] == 12  # time_window_hours parameter
    
    def test_export_metrics_default_time_window(self, client, mock_metrics_collector):
        """Test metrics export with default time window."""
        response = client.post("/api/v1/monitoring/export")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["time_window_hours"] == 24  # Default value
        
        # Verify export was called with default time window
        mock_metrics_collector.export_metrics.assert_called_once()
        call_args = mock_metrics_collector.export_metrics.call_args
        assert call_args[0][1] == 24  # Default time_window_hours
    
    def test_export_metrics_invalid_time_window(self, client, mock_metrics_collector):
        """Test metrics export with invalid time window."""
        # Test time window too small
        response = client.post(
            "/api/v1/monitoring/export",
            params={"time_window_hours": 0}
        )
        assert response.status_code == 422  # Validation error
        
        # Test time window too large
        response = client.post(
            "/api/v1/monitoring/export",
            params={"time_window_hours": 200}
        )
        assert response.status_code == 422  # Validation error
    
    def test_export_metrics_error(self, client, mock_metrics_collector):
        """Test metrics export with error."""
        mock_metrics_collector.export_metrics.side_effect = Exception("File write error")
        
        response = client.post("/api/v1/monitoring/export")
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "export_error"
        assert "File write error" in data["details"]
    
    def test_health_endpoint_integration(self, client):
        """Test health endpoint integration with monitoring."""
        response = client.get("/api/v1/monitoring/health")
        
        # Should return some response (exact content depends on system state)
        assert response.status_code in [200, 503]  # Healthy or unhealthy
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_metrics_endpoint_integration(self, client):
        """Test metrics endpoint integration."""
        response = client.get("/api/v1/monitoring/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        
        metrics_data = data["data"]
        assert "endpoint_stats" in metrics_data
        assert "performance_summary" in metrics_data
        assert "system_metrics" in metrics_data
    
    def test_system_metrics_endpoint_integration(self, client):
        """Test system metrics endpoint integration."""
        response = client.get("/api/v1/monitoring/system")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        
        system_data = data["data"]
        assert "cpu_percent" in system_data
        assert "memory_percent" in system_data
        assert "timestamp" in system_data
    
    def test_alerts_endpoint_integration(self, client):
        """Test alerts endpoint integration."""
        response = client.get("/api/v1/monitoring/alerts")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        
        alerts_data = data["data"]
        assert "alerts" in alerts_data
        assert "alert_count" in alerts_data
        assert "thresholds" in alerts_data


class TestMonitoringDashboardIntegration:
    """Integration tests for monitoring dashboard functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_dashboard_html_accessibility(self, client):
        """Test that admin dashboard HTML is accessible."""
        # Note: This would require serving static files in test environment
        # For now, we'll test that the file exists
        import os
        dashboard_path = "static/admin-dashboard.html"
        assert os.path.exists(dashboard_path)
        
        # Verify HTML contains expected elements
        with open(dashboard_path, 'r') as f:
            content = f.read()
            assert "VidNet Admin Dashboard" in content
            assert "totalDownloads" in content
            assert "cacheHitRate" in content
            assert "platformChart" in content
    
    def test_dashboard_api_endpoints_exist(self, client):
        """Test that all expected dashboard API endpoints exist."""
        endpoints = [
            "/api/v1/monitoring/dashboard",
            "/api/v1/monitoring/business-metrics",
            "/api/v1/monitoring/cache-metrics",
            "/api/v1/monitoring/performance-alerts",
            "/api/v1/monitoring/health",
            "/api/v1/monitoring/metrics",
            "/api/v1/monitoring/system"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not return 404 (endpoint exists)
            assert response.status_code != 404
            # Should return JSON response
            assert response.headers.get("content-type", "").startswith("application/json")
    
    def test_dashboard_data_structure_consistency(self, client):
        """Test that dashboard data has consistent structure."""
        response = client.get("/api/v1/monitoring/dashboard")
        
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            
            dashboard_data = data["data"]
            
            # Check required top-level keys
            required_keys = ["overview", "performance", "business_metrics", "cache_performance", "alerts", "timestamp"]
            for key in required_keys:
                assert key in dashboard_data, f"Missing required key: {key}"
            
            # Check overview structure
            overview = dashboard_data["overview"]
            overview_keys = ["total_downloads", "total_audio_extractions", "total_operations", "overall_success_rate"]
            for key in overview_keys:
                assert key in overview, f"Missing overview key: {key}"
                assert isinstance(overview[key], (int, float)), f"Invalid type for {key}"
    
    @patch('app.api.monitoring.metrics_collector')
    def test_metrics_collection_workflow(self, mock_collector, client):
        """Test complete metrics collection workflow."""
        # Mock a complete workflow
        mock_collector.track_download.return_value = None
        mock_collector.track_cache_operation.return_value = None
        mock_collector.get_dashboard_data.return_value = {
            "overview": {"total_downloads": 1},
            "performance": {"system_metrics": {}},
            "business_metrics": {"platform_metrics": {}},
            "cache_performance": {"hit_rate": 85.0},
            "alerts": [],
            "timestamp": 1234567890
        }
        
        # Simulate tracking events
        response = client.post(
            "/api/v1/monitoring/track-event",
            params={
                "metric_name": "test_download",
                "value": 1,
                "metric_type": "counter"
            }
        )
        assert response.status_code == 200
        
        # Get dashboard data
        response = client.get("/api/v1/monitoring/dashboard")
        assert response.status_code == 200
        
        # Verify metrics collector was used
        mock_collector.record_metric.assert_called()
        mock_collector.get_dashboard_data.assert_called()