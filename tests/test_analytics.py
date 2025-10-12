"""
Tests for analytics API endpoints and functionality
"""
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app.main import app
from app.api.analytics import analytics_storage

client = TestClient(app)

class TestAnalyticsAPI:
    """Test analytics API endpoints"""
    
    def setup_method(self):
        """Clear analytics storage before each test"""
        analytics_storage["events"].clear()
        analytics_storage["consent_data"].clear()
        analytics_storage["session_metrics"].clear()
    
    def test_collect_analytics_events_success(self):
        """Test successful analytics event collection"""
        event_data = {
            "events": [
                {
                    "event_type": "page_view",
                    "data": {
                        "page_title": "VidNet - HD Video Downloader",
                        "page_location": "http://localhost:3000",
                        "page_path": "/"
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "session_id": "sess_test_123",
                    "user_agent": "Mozilla/5.0 (Test Browser)"
                }
            ],
            "client_id": "test_client_123"
        }
        
        response = client.post("/api/v1/analytics/events", json=event_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["events_stored"] == 1
        
        # Verify event was stored
        assert len(analytics_storage["events"]) == 1
        stored_event = analytics_storage["events"][0]
        assert stored_event["event_type"] == "page_view"
        assert stored_event["client_id"] == "test_client_123"
    
    def test_collect_multiple_analytics_events(self):
        """Test collecting multiple analytics events in one request"""
        event_data = {
            "events": [
                {
                    "event_type": "page_view",
                    "data": {"page_title": "VidNet"},
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "session_id": "sess_test_123"
                },
                {
                    "event_type": "download_start",
                    "data": {
                        "platform": "youtube",
                        "quality": "1080p",
                        "type": "video"
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "session_id": "sess_test_123"
                }
            ],
            "client_id": "test_client_123"
        }
        
        response = client.post("/api/v1/analytics/events", json=event_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["events_stored"] == 2
        
        # Verify both events were stored
        assert len(analytics_storage["events"]) == 2
        event_types = [event["event_type"] for event in analytics_storage["events"]]
        assert "page_view" in event_types
        assert "download_start" in event_types
    
    def test_record_consent_success(self):
        """Test successful consent recording"""
        consent_data = {
            "analytics": True,
            "marketing": False,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        
        response = client.post("/api/v1/analytics/consent", json=consent_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "consent_id" in data
        
        # Verify consent was stored
        assert len(analytics_storage["consent_data"]) == 1
        stored_consent = analytics_storage["consent_data"][0]
        assert stored_consent["analytics"] is True
        assert stored_consent["marketing"] is False
    
    def test_analytics_dashboard_empty(self):
        """Test analytics dashboard with no data"""
        response = client.get("/api/v1/analytics/dashboard")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_events"] == 0
        assert data["page_views"] == 0
        assert data["downloads_total"] == 0
        assert data["downloads_by_platform"] == {}
        assert data["error_events"] == 0
    
    def test_analytics_dashboard_with_data(self):
        """Test analytics dashboard with sample data"""
        # Add sample events
        current_time = int(datetime.now().timestamp() * 1000)
        
        sample_events = [
            {
                "event_type": "page_view",
                "data": {"page_title": "VidNet"},
                "timestamp": current_time,
                "session_id": "sess_1",
                "client_id": "client_1"
            },
            {
                "event_type": "download_start",
                "data": {
                    "platform": "youtube",
                    "quality": "1080p",
                    "type": "video"
                },
                "timestamp": current_time,
                "session_id": "sess_1",
                "client_id": "client_1"
            },
            {
                "event_type": "download_start",
                "data": {
                    "platform": "tiktok",
                    "quality": "720p",
                    "type": "video"
                },
                "timestamp": current_time,
                "session_id": "sess_2",
                "client_id": "client_2"
            }
        ]
        
        analytics_storage["events"].extend(sample_events)
        
        response = client.get("/api/v1/analytics/dashboard")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_events"] == 3
        assert data["page_views"] == 1
        assert data["downloads_total"] == 2
        assert data["downloads_by_platform"]["youtube"] == 1
        assert data["downloads_by_platform"]["tiktok"] == 1
        assert data["downloads_by_quality"]["1080p"] == 1
        assert data["downloads_by_quality"]["720p"] == 1
    
    def test_analytics_dashboard_time_filter(self):
        """Test analytics dashboard with time filtering"""
        # Add events from different time periods
        now = datetime.now()
        old_time = int((now - timedelta(hours=25)).timestamp() * 1000)  # 25 hours ago
        recent_time = int((now - timedelta(hours=1)).timestamp() * 1000)  # 1 hour ago
        
        old_event = {
            "event_type": "page_view",
            "data": {"page_title": "VidNet"},
            "timestamp": old_time,
            "session_id": "sess_old",
            "client_id": "client_old"
        }
        
        recent_event = {
            "event_type": "page_view",
            "data": {"page_title": "VidNet"},
            "timestamp": recent_time,
            "session_id": "sess_recent",
            "client_id": "client_recent"
        }
        
        analytics_storage["events"].extend([old_event, recent_event])
        
        # Request dashboard for last 24 hours
        response = client.get("/api/v1/analytics/dashboard?hours=24")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only include recent event
        assert data["total_events"] == 1
        assert data["page_views"] == 1
        assert data["time_range"]["hours"] == "24"
    
    def test_get_client_events(self):
        """Test retrieving events for a specific client"""
        # Add events for different clients
        events = [
            {
                "event_type": "page_view",
                "data": {"page_title": "VidNet"},
                "timestamp": int(datetime.now().timestamp() * 1000),
                "session_id": "sess_1",
                "client_id": "client_target"
            },
            {
                "event_type": "download_start",
                "data": {"platform": "youtube"},
                "timestamp": int(datetime.now().timestamp() * 1000),
                "session_id": "sess_1",
                "client_id": "client_target"
            },
            {
                "event_type": "page_view",
                "data": {"page_title": "VidNet"},
                "timestamp": int(datetime.now().timestamp() * 1000),
                "session_id": "sess_2",
                "client_id": "client_other"
            }
        ]
        
        analytics_storage["events"].extend(events)
        
        response = client.get("/api/v1/analytics/events/client_target")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["client_id"] == "client_target"
        assert data["total_events"] == 2
        
        # Verify only target client events are returned
        for event in data["events"]:
            assert event["client_id"] == "client_target"
    
    def test_get_client_events_with_filter(self):
        """Test retrieving filtered events for a specific client"""
        # Add different event types for the same client
        events = [
            {
                "event_type": "page_view",
                "data": {"page_title": "VidNet"},
                "timestamp": int(datetime.now().timestamp() * 1000),
                "session_id": "sess_1",
                "client_id": "client_test"
            },
            {
                "event_type": "download_start",
                "data": {"platform": "youtube"},
                "timestamp": int(datetime.now().timestamp() * 1000),
                "session_id": "sess_1",
                "client_id": "client_test"
            }
        ]
        
        analytics_storage["events"].extend(events)
        
        response = client.get("/api/v1/analytics/events/client_test?event_type=download_start")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_events"] == 1
        assert data["events"][0]["event_type"] == "download_start"
    
    def test_clear_analytics_data_without_confirmation(self):
        """Test clearing analytics data without confirmation"""
        response = client.delete("/api/v1/analytics/data")
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "confirmation_required"
    
    def test_clear_analytics_data_with_confirmation(self):
        """Test clearing analytics data with confirmation"""
        # Add some test data
        analytics_storage["events"].append({
            "event_type": "test",
            "data": {},
            "timestamp": int(datetime.now().timestamp() * 1000),
            "session_id": "test",
            "client_id": "test"
        })
        
        analytics_storage["consent_data"].append({
            "client_id": "test",
            "analytics": True,
            "marketing": False,
            "timestamp": int(datetime.now().timestamp() * 1000)
        })
        
        # Verify data exists
        assert len(analytics_storage["events"]) > 0
        assert len(analytics_storage["consent_data"]) > 0
        
        response = client.delete("/api/v1/analytics/data?confirm=true")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify data was cleared
        assert len(analytics_storage["events"]) == 0
        assert len(analytics_storage["consent_data"]) == 0
    
    def test_analytics_health_check(self):
        """Test analytics health check endpoint"""
        response = client.get("/api/v1/analytics/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "healthy"
        assert "storage" in data
        assert "events_count" in data["storage"]
        assert "consent_count" in data["storage"]
        assert "timestamp" in data
    
    def test_invalid_event_data(self):
        """Test handling of invalid event data"""
        invalid_data = {
            "events": [
                {
                    "event_type": "test",
                    # Missing required fields
                }
            ]
        }
        
        response = client.post("/api/v1/analytics/events", json=invalid_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_invalid_consent_data(self):
        """Test handling of invalid consent data"""
        invalid_data = {
            "analytics": "not_a_boolean",  # Should be boolean
            "marketing": True,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        
        response = client.post("/api/v1/analytics/consent", json=invalid_data)
        
        assert response.status_code == 422  # Validation error

class TestAnalyticsIntegration:
    """Integration tests for analytics functionality"""
    
    def test_full_analytics_workflow(self):
        """Test complete analytics workflow from consent to dashboard"""
        # Clear storage
        analytics_storage["events"].clear()
        analytics_storage["consent_data"].clear()
        
        # 1. Record consent
        consent_data = {
            "analytics": True,
            "marketing": True,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        
        consent_response = client.post("/api/v1/analytics/consent", json=consent_data)
        assert consent_response.status_code == 200
        
        # 2. Send analytics events
        event_data = {
            "events": [
                {
                    "event_type": "page_view",
                    "data": {"page_title": "VidNet"},
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "session_id": "sess_integration_test"
                },
                {
                    "event_type": "download_start",
                    "data": {
                        "platform": "youtube",
                        "quality": "1080p",
                        "type": "video"
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "session_id": "sess_integration_test"
                },
                {
                    "event_type": "download_complete",
                    "data": {
                        "platform": "youtube",
                        "quality": "1080p",
                        "type": "video",
                        "processing_time": 3000
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "session_id": "sess_integration_test"
                }
            ],
            "client_id": "integration_test_client"
        }
        
        events_response = client.post("/api/v1/analytics/events", json=event_data)
        assert events_response.status_code == 200
        
        # 3. Check dashboard
        dashboard_response = client.get("/api/v1/analytics/dashboard")
        assert dashboard_response.status_code == 200
        
        dashboard_data = dashboard_response.json()
        assert dashboard_data["total_events"] == 3
        assert dashboard_data["page_views"] == 1
        assert dashboard_data["downloads_total"] == 1  # Only download_start events count
        assert dashboard_data["downloads_by_platform"]["youtube"] == 1
        assert dashboard_data["consent_stats"]["analytics_accepted"] == 1
        
        # 4. Check client events
        client_events_response = client.get("/api/v1/analytics/events/integration_test_client")
        assert client_events_response.status_code == 200
        
        client_data = client_events_response.json()
        assert client_data["total_events"] == 3
        
        # 5. Health check
        health_response = client.get("/api/v1/analytics/health")
        assert health_response.status_code == 200
        
        health_data = health_response.json()
        assert health_data["status"] == "healthy"
        assert health_data["storage"]["events_count"] == 3
        assert health_data["storage"]["consent_count"] == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])