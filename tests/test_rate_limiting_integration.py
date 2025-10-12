"""
Integration tests for rate limiting and performance optimization.

This module tests the rate limiting middleware and performance monitoring
integration with the FastAPI application.
"""

import asyncio
import time
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.middleware.rate_limiter import rate_limiter
from app.services.performance_monitor import performance_monitor


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_endpoint_available(client):
    """Test that health endpoint is available."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_monitoring_health_endpoint(client):
    """Test monitoring health endpoint."""
    response = client.get("/api/v1/monitoring/health")
    assert response.status_code in [200, 503]  # May be degraded during testing
    
    data = response.json()
    assert "success" in data
    if data["success"]:
        assert "data" in data
        assert "status" in data["data"]


def test_monitoring_metrics_endpoint(client):
    """Test monitoring metrics endpoint."""
    response = client.get("/api/v1/monitoring/metrics")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "endpoint_stats" in data["data"]
    assert "system_metrics" in data["data"]


def test_rate_limit_stats_endpoint(client):
    """Test rate limit statistics endpoint."""
    response = client.get("/api/v1/monitoring/rate-limit-stats")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data


def test_system_metrics_endpoint(client):
    """Test system metrics endpoint."""
    response = client.get("/api/v1/monitoring/system")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    
    system_data = data["data"]
    assert "cpu_percent" in system_data
    assert "memory_percent" in system_data
    assert "timestamp" in system_data


def test_performance_monitoring_tracks_requests(client):
    """Test that performance monitoring tracks requests correctly."""
    # Clear existing metrics
    performance_monitor.request_metrics.clear()
    performance_monitor.endpoint_stats.clear()
    
    # Make some test requests
    for i in range(5):
        response = client.get("/health")
        assert response.status_code == 200
    
    # Check that metrics were recorded
    endpoint_stats = performance_monitor.get_endpoint_stats()
    
    # Should have recorded the health endpoint requests
    health_endpoint_found = False
    for endpoint, stats in endpoint_stats.items():
        if "/health" in endpoint:
            health_endpoint_found = True
            assert stats["total_requests"] >= 5
            break
    
    assert health_endpoint_found, "Health endpoint statistics not found"


def test_rate_limiting_headers_present(client):
    """Test that rate limiting headers are present in responses."""
    # Mock rate limiter to avoid Redis dependency in tests
    with patch.object(rate_limiter, 'is_rate_limited', return_value=(False, {
        'requests_per_minute': 1,
        'requests_per_hour': 1,
        'minute_limit': 60,
        'hour_limit': 1000,
        'reset_time': int(time.time() + 60)
    })):
        response = client.get("/api/v1/monitoring/health")
        
        # Check for rate limiting headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers


@pytest.mark.asyncio
async def test_rate_limiter_initialization():
    """Test rate limiter initialization."""
    # Test that rate limiter can be initialized
    await rate_limiter.initialize()
    
    # Test client ID extraction
    from fastapi import Request
    
    # Mock request object
    class MockClient:
        host = "127.0.0.1"
    
    class MockRequest:
        client = MockClient()
        headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
    
    request = MockRequest()
    client_id = rate_limiter.get_client_id(request)
    assert client_id == "192.168.1.1"  # Should use first forwarded IP


@pytest.mark.asyncio
async def test_performance_monitor_initialization():
    """Test performance monitor initialization."""
    # Test that performance monitor can start and stop
    await performance_monitor.start_monitoring()
    assert performance_monitor._monitoring_active is True
    
    await performance_monitor.stop_monitoring()
    assert performance_monitor._monitoring_active is False


def test_graceful_degradation_response_format(client):
    """Test graceful degradation response format."""
    # Mock degradation condition
    with patch.object(rate_limiter, 'should_degrade_service', return_value=True):
        # Test download endpoint (should be degraded)
        response = client.post(
            "/api/v1/download",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "quality": "720p",
                "format": "video"
            }
        )
        
        # Should return service degraded response
        assert response.status_code == 503
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "service_degraded"
        assert "retry_after" in data


def test_monitoring_dashboard_endpoint(client):
    """Test monitoring dashboard endpoint."""
    response = client.get("/api/v1/monitoring/dashboard")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    
    dashboard_data = data["data"]
    assert "overview" in dashboard_data
    assert "health_status" in dashboard_data
    assert "endpoint_stats" in dashboard_data
    assert "rate_limit_metrics" in dashboard_data


def test_performance_alerts_endpoint(client):
    """Test performance alerts endpoint."""
    response = client.get("/api/v1/monitoring/alerts")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    
    alerts_data = data["data"]
    assert "alerts" in alerts_data
    assert "alert_count" in alerts_data
    assert "thresholds" in alerts_data


def test_export_metrics_endpoint(client):
    """Test metrics export endpoint."""
    response = client.post("/api/v1/monitoring/export")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "exported_file" in data["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])