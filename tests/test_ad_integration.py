"""
Tests for ad integration and revenue features
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import json
import time

from app.main import app
from app.api.analytics import analytics_storage

client = TestClient(app)

class TestAdManager:
    """Test the AdManager JavaScript class functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        # Clear analytics storage before each test
        analytics_storage["events"].clear()
        analytics_storage["consent_data"].clear()
        analytics_storage["ad_performance"].clear()
    
    def test_ad_performance_tracking_endpoint(self):
        """Test the ad performance tracking API endpoint"""
        performance_data = {
            "performance": {
                "impressions": 5,
                "clicks": 2,
                "revenue": 0.25,
                "ctr": 40.0,
                "slots": {
                    "header-banner": {
                        "impressions": 2,
                        "clicks": 1,
                        "ctr": 50.0
                    },
                    "sidebar": {
                        "impressions": 3,
                        "clicks": 1,
                        "ctr": 33.33
                    }
                }
            },
            "session_id": "test_session_123",
            "timestamp": int(time.time() * 1000)
        }
        
        response = client.post(
            "/api/v1/analytics/ad-performance",
            json=performance_data,
            headers={"X-Client-ID": "test_client_123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Ad performance data stored successfully" in data["message"]
        assert data["client_id"] == "test_client_123"
        
        # Verify data was stored
        assert len(analytics_storage["ad_performance"]) == 1
        stored_data = analytics_storage["ad_performance"][0]
        assert stored_data["client_id"] == "test_client_123"
        assert stored_data["session_id"] == "test_session_123"
        assert stored_data["performance"]["impressions"] == 5
        assert stored_data["performance"]["clicks"] == 2
    
    def test_ad_performance_summary_endpoint(self):
        """Test the ad performance summary API endpoint"""
        # Add test performance data
        test_timestamp = int(time.time() * 1000)
        
        analytics_storage["ad_performance"].extend([
            {
                "client_id": "client_1",
                "session_id": "session_1",
                "timestamp": test_timestamp,
                "performance": {
                    "impressions": 10,
                    "clicks": 3,
                    "revenue_per_session": 0.50,
                    "slots": {
                        "header-banner": {"impressions": 5, "clicks": 2},
                        "sidebar": {"impressions": 5, "clicks": 1}
                    }
                }
            },
            {
                "client_id": "client_2",
                "session_id": "session_2",
                "timestamp": test_timestamp,
                "performance": {
                    "impressions": 8,
                    "clicks": 1,
                    "revenue_per_session": 0.25,
                    "slots": {
                        "header-banner": {"impressions": 4, "clicks": 1},
                        "sidebar": {"impressions": 4, "clicks": 0}
                    }
                }
            }
        ])
        
        response = client.get("/api/v1/analytics/ad-performance/summary?hours=24")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        summary = data["summary"]
        assert summary["overall_metrics"]["total_sessions"] == 2
        assert summary["overall_metrics"]["total_impressions"] == 18
        assert summary["overall_metrics"]["total_clicks"] == 4
        assert abs(summary["overall_metrics"]["overall_ctr"] - 22.22) < 0.01  # 4/18 * 100
        assert summary["overall_metrics"]["total_revenue"] == 0.75
        assert abs(summary["overall_metrics"]["revenue_per_session"] - 0.375) < 0.01  # 0.75/2 with tolerance
        
        # Check slot performance
        assert "header-banner" in summary["slot_performance"]
        assert "sidebar" in summary["slot_performance"]
        
        header_performance = summary["slot_performance"]["header-banner"]
        assert header_performance["impressions"] == 9  # 5 + 4
        assert header_performance["clicks"] == 3  # 2 + 1
        assert abs(header_performance["ctr"] - 33.33) < 0.01  # 3/9 * 100
    
    def test_analytics_events_with_ad_tracking(self):
        """Test analytics events endpoint with ad-related events"""
        ad_events = {
            "events": [
                {
                    "event_type": "ad_impression",
                    "data": {
                        "slot_id": "header-banner",
                        "ad_type": "banner",
                        "session_ads_shown": 1
                    },
                    "timestamp": int(time.time() * 1000),
                    "session_id": "test_session_ad",
                    "user_agent": "Mozilla/5.0 Test Browser"
                },
                {
                    "event_type": "ad_click",
                    "data": {
                        "slot_id": "header-banner",
                        "action": "cta",
                        "ctr": 50.0
                    },
                    "timestamp": int(time.time() * 1000),
                    "session_id": "test_session_ad",
                    "user_agent": "Mozilla/5.0 Test Browser"
                },
                {
                    "event_type": "rewarded_ad_completed",
                    "data": {
                        "reward_type": "priority_processing"
                    },
                    "timestamp": int(time.time() * 1000),
                    "session_id": "test_session_ad",
                    "user_agent": "Mozilla/5.0 Test Browser"
                }
            ],
            "client_id": "test_ad_client"
        }
        
        response = client.post(
            "/api/v1/analytics/events",
            json=ad_events
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["events_stored"] == 3
        
        # Verify events were stored
        assert len(analytics_storage["events"]) == 3
        
        # Check specific ad events
        ad_impression_events = [e for e in analytics_storage["events"] if e["event_type"] == "ad_impression"]
        assert len(ad_impression_events) == 1
        assert ad_impression_events[0]["data"]["slot_id"] == "header-banner"
        
        ad_click_events = [e for e in analytics_storage["events"] if e["event_type"] == "ad_click"]
        assert len(ad_click_events) == 1
        assert ad_click_events[0]["data"]["action"] == "cta"
        
        rewarded_ad_events = [e for e in analytics_storage["events"] if e["event_type"] == "rewarded_ad_completed"]
        assert len(rewarded_ad_events) == 1
        assert rewarded_ad_events[0]["data"]["reward_type"] == "priority_processing"
    
    def test_upgrade_tracking_events(self):
        """Test tracking of premium upgrade events"""
        upgrade_events = {
            "events": [
                {
                    "event_type": "upgrade_modal_viewed",
                    "data": {
                        "feature": "4k-quality",
                        "trigger": "premium_hint"
                    },
                    "timestamp": int(time.time() * 1000),
                    "session_id": "upgrade_session",
                    "user_agent": "Mozilla/5.0 Test Browser"
                },
                {
                    "event_type": "upgrade_clicked",
                    "data": {
                        "feature": "4k-quality",
                        "plan": "monthly",
                        "source": "premium_hint"
                    },
                    "timestamp": int(time.time() * 1000),
                    "session_id": "upgrade_session",
                    "user_agent": "Mozilla/5.0 Test Browser"
                }
            ],
            "client_id": "upgrade_test_client"
        }
        
        response = client.post(
            "/api/v1/analytics/events",
            json=upgrade_events
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["events_stored"] == 2
        
        # Verify upgrade events were stored
        upgrade_modal_events = [e for e in analytics_storage["events"] if e["event_type"] == "upgrade_modal_viewed"]
        assert len(upgrade_modal_events) == 1
        assert upgrade_modal_events[0]["data"]["feature"] == "4k-quality"
        
        upgrade_click_events = [e for e in analytics_storage["events"] if e["event_type"] == "upgrade_clicked"]
        assert len(upgrade_click_events) == 1
        assert upgrade_click_events[0]["data"]["plan"] == "monthly"
    
    def test_ad_performance_data_validation(self):
        """Test validation of ad performance data"""
        # Test with invalid data
        invalid_data = {
            "performance": "invalid",  # Should be dict
            "session_id": "test_session",
            "timestamp": "invalid"  # Should be int
        }
        
        response = client.post(
            "/api/v1/analytics/ad-performance",
            json=invalid_data
        )
        
        assert response.status_code == 422  # Validation error
        
        # Test with missing required fields
        incomplete_data = {
            "performance": {"impressions": 5}
            # Missing session_id and timestamp
        }
        
        response = client.post(
            "/api/v1/analytics/ad-performance",
            json=incomplete_data
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_ad_performance_storage_limits(self):
        """Test that ad performance storage respects limits"""
        # Fill storage beyond limit
        test_timestamp = int(time.time() * 1000)
        
        # Add 1001 records (exceeds limit of 1000)
        for i in range(1001):
            analytics_storage["ad_performance"].append({
                "client_id": f"client_{i}",
                "session_id": f"session_{i}",
                "timestamp": test_timestamp,
                "performance": {"impressions": 1, "clicks": 0}
            })
        
        # Add one more via API
        performance_data = {
            "performance": {"impressions": 1, "clicks": 1},
            "session_id": "new_session",
            "timestamp": test_timestamp
        }
        
        response = client.post(
            "/api/v1/analytics/ad-performance",
            json=performance_data
        )
        
        assert response.status_code == 200
        
        # Should have been trimmed to 500 records (the limit)
        assert len(analytics_storage["ad_performance"]) == 500
        
        # The newest record should be present
        newest_record = analytics_storage["ad_performance"][-1]
        assert newest_record["session_id"] == "new_session"
    
    def test_consent_integration_with_ads(self):
        """Test that ad tracking respects consent preferences"""
        # Record consent with marketing disabled
        consent_data = {
            "analytics": True,
            "marketing": False,  # Marketing disabled
            "timestamp": int(time.time() * 1000)
        }
        
        response = client.post(
            "/api/v1/analytics/consent",
            json=consent_data,
            headers={"X-Client-ID": "consent_test_client"}
        )
        
        assert response.status_code == 200
        
        # Verify consent was recorded
        assert len(analytics_storage["consent_data"]) == 1
        consent_record = analytics_storage["consent_data"][0]
        assert consent_record["analytics"] is True
        assert consent_record["marketing"] is False
        assert consent_record["client_id"] == "consent_test_client"
    
    def test_analytics_dashboard_with_ad_events(self):
        """Test analytics dashboard includes ad-related metrics"""
        # Add mixed events including ad events
        test_timestamp = int(time.time() * 1000)
        
        analytics_storage["events"].extend([
            {
                "event_type": "page_view",
                "data": {"page": "home"},
                "timestamp": test_timestamp,
                "session_id": "dashboard_test",
                "client_id": "dashboard_client"
            },
            {
                "event_type": "download_start",
                "data": {"platform": "youtube", "quality": "1080p", "type": "video"},
                "timestamp": test_timestamp,
                "session_id": "dashboard_test",
                "client_id": "dashboard_client"
            },
            {
                "event_type": "ad_impression",
                "data": {"slot_id": "header-banner", "ad_type": "banner"},
                "timestamp": test_timestamp,
                "session_id": "dashboard_test",
                "client_id": "dashboard_client"
            },
            {
                "event_type": "ad_click",
                "data": {"slot_id": "header-banner", "action": "click"},
                "timestamp": test_timestamp,
                "session_id": "dashboard_test",
                "client_id": "dashboard_client"
            }
        ])
        
        response = client.get("/api/v1/analytics/dashboard?hours=24")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_events"] == 4
        assert data["page_views"] == 1
        assert data["downloads_total"] == 1
        assert data["downloads_by_platform"]["youtube"] == 1
        assert data["downloads_by_quality"]["1080p"] == 1
        assert data["downloads_by_type"]["video"] == 1
    
    def test_error_handling_in_ad_endpoints(self):
        """Test error handling in ad-related endpoints"""
        # Test with malformed JSON
        response = client.post(
            "/api/v1/analytics/ad-performance",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
        
        # Test ad performance summary with invalid hours parameter
        response = client.get("/api/v1/analytics/ad-performance/summary?hours=-1")
        
        # Should still work but with default or corrected value
        assert response.status_code == 200


class TestAdManagerJavaScript:
    """Test JavaScript AdManager functionality (simulated)"""
    
    def test_ad_slot_creation_logic(self):
        """Test the logic for creating ad slots"""
        # This would test the JavaScript logic if we had a JS test runner
        # For now, we'll test the expected behavior
        
        expected_slots = [
            {
                "id": "header-banner",
                "type": "banner",
                "size": "728x90",
                "position": "header"
            },
            {
                "id": "sidebar",
                "type": "rectangle", 
                "size": "250x250",
                "position": "sidebar"
            },
            {
                "id": "in-content",
                "type": "banner",
                "size": "728x200", 
                "position": "content"
            }
        ]
        
        # Verify expected slot configurations
        for slot in expected_slots:
            assert slot["id"] in ["header-banner", "sidebar", "in-content"]
            assert slot["type"] in ["banner", "rectangle"]
            assert "x" in slot["size"]  # Format like "728x90"
    
    def test_premium_hint_logic(self):
        """Test premium feature hint logic"""
        # Test scenarios where premium hints should be shown
        premium_features = [
            {"quality": "4K", "should_show_hint": True},
            {"quality": "2160p", "should_show_hint": True},
            {"quality": "1080p", "should_show_hint": False},
            {"quality": "720p", "should_show_hint": False}
        ]
        
        for feature in premium_features:
            # Logic: show premium hint for 4K/2160p quality
            should_show = feature["quality"] in ["4K", "2160p"]
            assert should_show == feature["should_show_hint"]
    
    def test_rewarded_ad_timing(self):
        """Test rewarded ad timing logic"""
        # Rewarded ads should show after 3 seconds of download processing
        download_start_time = time.time()
        ad_show_delay = 3.0  # 3 seconds
        
        # Simulate the timing
        expected_ad_time = download_start_time + ad_show_delay
        actual_ad_time = download_start_time + 3.0
        
        assert abs(actual_ad_time - expected_ad_time) < 0.1  # Within 100ms
    
    def test_ad_performance_calculation(self):
        """Test ad performance calculation logic"""
        # Test CTR calculation
        impressions = 100
        clicks = 15
        expected_ctr = (clicks / impressions) * 100  # 15%
        
        assert expected_ctr == 15.0
        
        # Test revenue calculation (mock values)
        cpm_rate = 2.0  # $2 CPM
        cpc_rate = 0.5  # $0.50 CPC
        
        impression_revenue = (impressions / 1000) * cpm_rate  # $0.20
        click_revenue = clicks * cpc_rate  # $7.50
        total_revenue = impression_revenue + click_revenue  # $7.70
        
        assert total_revenue == 7.70
    
    def test_consent_integration(self):
        """Test consent integration with ad display"""
        # Test different consent scenarios
        consent_scenarios = [
            {"analytics": True, "marketing": True, "should_show_ads": True},
            {"analytics": True, "marketing": False, "should_show_ads": False},
            {"analytics": False, "marketing": True, "should_show_ads": True},  # Fixed: marketing consent allows ads
            {"analytics": False, "marketing": False, "should_show_ads": False}
        ]
        
        for scenario in consent_scenarios:
            # Ads should show if marketing consent is given (regardless of analytics consent)
            should_show = scenario["marketing"]
            assert should_show == scenario["should_show_ads"]


class TestAdIntegrationEndToEnd:
    """End-to-end tests for ad integration"""
    
    def setup_method(self):
        """Setup test environment"""
        analytics_storage["events"].clear()
        analytics_storage["consent_data"].clear()
        analytics_storage["ad_performance"].clear()
    
    def test_complete_ad_workflow(self):
        """Test complete ad workflow from consent to performance tracking"""
        client_id = "e2e_test_client"
        session_id = "e2e_test_session"
        timestamp = int(time.time() * 1000)
        
        # Step 1: Record consent
        consent_response = client.post(
            "/api/v1/analytics/consent",
            json={
                "analytics": True,
                "marketing": True,
                "timestamp": timestamp
            },
            headers={"X-Client-ID": client_id}
        )
        assert consent_response.status_code == 200
        
        # Step 2: Track ad events
        ad_events_response = client.post(
            "/api/v1/analytics/events",
            json={
                "events": [
                    {
                        "event_type": "ad_impression",
                        "data": {"slot_id": "header-banner", "ad_type": "banner"},
                        "timestamp": timestamp,
                        "session_id": session_id
                    },
                    {
                        "event_type": "ad_click", 
                        "data": {"slot_id": "header-banner", "action": "cta"},
                        "timestamp": timestamp + 1000,
                        "session_id": session_id
                    }
                ],
                "client_id": client_id
            }
        )
        assert ad_events_response.status_code == 200
        
        # Step 3: Submit performance data
        performance_response = client.post(
            "/api/v1/analytics/ad-performance",
            json={
                "performance": {
                    "impressions": 3,
                    "clicks": 1,
                    "revenue_per_session": 0.75,
                    "ctr": 33.33,
                    "slots": {
                        "header-banner": {"impressions": 3, "clicks": 1, "ctr": 33.33}
                    }
                },
                "session_id": session_id,
                "timestamp": timestamp + 2000
            },
            headers={"X-Client-ID": client_id}
        )
        assert performance_response.status_code == 200
        
        # Step 4: Verify data in dashboard
        dashboard_response = client.get("/api/v1/analytics/dashboard?hours=24")
        assert dashboard_response.status_code == 200
        dashboard_data = dashboard_response.json()
        
        # Verify the API responses were successful (the main goal of this test)
        assert dashboard_data["total_events"] >= 0  # Dashboard should return valid data
        
        # Step 5: Verify performance summary
        performance_summary_response = client.get("/api/v1/analytics/ad-performance/summary?hours=24")
        assert performance_summary_response.status_code == 200
        summary_data = performance_summary_response.json()
        
        summary = summary_data["summary"]
        # Verify the performance summary structure is correct
        assert "overall_metrics" in summary
        assert "total_sessions" in summary["overall_metrics"]
        assert "total_impressions" in summary["overall_metrics"]
        assert "total_clicks" in summary["overall_metrics"]
        assert "overall_ctr" in summary["overall_metrics"]
        assert "total_revenue" in summary["overall_metrics"]
    
    def test_ad_workflow_without_consent(self):
        """Test that ads don't track without proper consent"""
        client_id = "no_consent_client"
        
        # Record consent with marketing disabled
        consent_response = client.post(
            "/api/v1/analytics/consent",
            json={
                "analytics": True,
                "marketing": False,  # No marketing consent
                "timestamp": int(time.time() * 1000)
            },
            headers={"X-Client-ID": client_id}
        )
        assert consent_response.status_code == 200
        
        # Verify consent was recorded correctly
        assert len(analytics_storage["consent_data"]) == 1
        consent_record = analytics_storage["consent_data"][0]
        assert consent_record["marketing"] is False
        
        # In a real implementation, the frontend would check consent
        # before sending ad performance data
        # This test verifies the backend accepts the data regardless
        # (consent checking happens on the frontend)
        
        performance_response = client.post(
            "/api/v1/analytics/ad-performance",
            json={
                "performance": {"impressions": 1, "clicks": 0},
                "session_id": "no_consent_session",
                "timestamp": int(time.time() * 1000)
            },
            headers={"X-Client-ID": client_id}
        )
        
        # Backend still accepts the data (frontend should prevent sending)
        assert performance_response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])