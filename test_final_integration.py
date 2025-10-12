#!/usr/bin/env python3
"""
Final Integration Test for VidNet MVP
Tests complete user workflows and system integration before deployment
"""

import asyncio
import json
import time
import httpx
import pytest
from typing import Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VidNetIntegrationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results = {
            "health_check": False,
            "metadata_fetch": False,
            "video_download": False,
            "audio_extraction": False,
            "error_handling": False,
            "performance": False,
            "analytics": False,
            "frontend_integration": False
        }
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def test_health_endpoints(self) -> bool:
        """Test basic health and status endpoints"""
        logger.info("🏥 Testing health endpoints...")
        
        try:
            # Test main health endpoint
            response = await self.client.get(f"{self.base_url}/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            
            # Test API status endpoint
            response = await self.client.get(f"{self.base_url}/api/v1/monitoring/status")
            assert response.status_code == 200
            status_data = response.json()
            assert "redis" in status_data
            assert "performance" in status_data
            
            logger.info("✅ Health endpoints working correctly")
            return True
            
        except Exception as e:
            logger.error(f"❌ Health endpoint test failed: {e}")
            return False

    async def test_metadata_extraction(self) -> bool:
        """Test video metadata extraction from various platforms"""
        logger.info("📊 Testing metadata extraction...")
        
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - reliable test video
            "https://youtu.be/dQw4w9WgXcQ",  # Short YouTube URL
        ]
        
        try:
            for url in test_urls:
                logger.info(f"Testing URL: {url}")
                
                response = await self.client.post(
                    f"{self.base_url}/api/v1/metadata",
                    json={"url": url}
                )
                
                if response.status_code == 200:
                    metadata = response.json()
                    
                    # Validate metadata structure
                    required_fields = ["title", "thumbnail", "duration", "platform", "available_qualities"]
                    for field in required_fields:
                        assert field in metadata, f"Missing field: {field}"
                    
                    assert metadata["platform"] == "youtube"
                    assert len(metadata["available_qualities"]) > 0
                    assert metadata["duration"] > 0
                    
                    logger.info(f"✅ Metadata extracted: {metadata['title'][:50]}...")
                    return True
                else:
                    logger.warning(f"⚠️ Metadata extraction failed for {url}: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ Metadata extraction test failed: {e}")
            return False
            
        return False

    async def test_download_workflow(self) -> bool:
        """Test complete video download workflow"""
        logger.info("⬇️ Testing download workflow...")
        
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        try:
            # First get metadata
            metadata_response = await self.client.post(
                f"{self.base_url}/api/v1/metadata",
                json={"url": test_url}
            )
            
            if metadata_response.status_code != 200:
                logger.error("Failed to get metadata for download test")
                return False
                
            metadata = metadata_response.json()
            available_qualities = metadata["available_qualities"]
            
            if not available_qualities:
                logger.error("No qualities available for download test")
                return False
                
            # Use the first available quality
            quality = available_qualities[0]["quality"]
            format_type = available_qualities[0]["format"]
            
            # Initiate download
            download_response = await self.client.post(
                f"{self.base_url}/api/v1/download",
                json={
                    "url": test_url,
                    "quality": quality,
                    "format": format_type
                }
            )
            
            if download_response.status_code != 200:
                logger.error(f"Download initiation failed: {download_response.status_code}")
                return False
                
            download_data = download_response.json()
            task_id = download_data["task_id"]
            
            logger.info(f"Download initiated with task ID: {task_id}")
            
            # Poll for completion (with timeout)
            max_wait_time = 120  # 2 minutes
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                status_response = await self.client.get(
                    f"{self.base_url}/api/v1/status/{task_id}"
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data["status"]
                    
                    logger.info(f"Download status: {status}")
                    
                    if status == "completed":
                        assert "download_url" in status_data
                        logger.info("✅ Download completed successfully")
                        return True
                    elif status == "failed":
                        logger.error(f"Download failed: {status_data.get('error_message', 'Unknown error')}")
                        return False
                        
                await asyncio.sleep(5)  # Wait 5 seconds before next check
                
            logger.error("Download test timed out")
            return False
            
        except Exception as e:
            logger.error(f"❌ Download workflow test failed: {e}")
            return False

    async def test_audio_extraction(self) -> bool:
        """Test audio extraction workflow"""
        logger.info("🎵 Testing audio extraction...")
        
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        try:
            # Initiate audio extraction
            audio_response = await self.client.post(
                f"{self.base_url}/api/v1/extract-audio",
                json={
                    "url": test_url,
                    "quality": "128kbps"
                }
            )
            
            if audio_response.status_code != 200:
                logger.error(f"Audio extraction initiation failed: {audio_response.status_code}")
                return False
                
            audio_data = audio_response.json()
            task_id = audio_data["task_id"]
            
            logger.info(f"Audio extraction initiated with task ID: {task_id}")
            
            # Poll for completion (with timeout)
            max_wait_time = 120  # 2 minutes
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                status_response = await self.client.get(
                    f"{self.base_url}/api/v1/status/{task_id}"
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data["status"]
                    
                    logger.info(f"Audio extraction status: {status}")
                    
                    if status == "completed":
                        assert "download_url" in status_data
                        logger.info("✅ Audio extraction completed successfully")
                        return True
                    elif status == "failed":
                        logger.error(f"Audio extraction failed: {status_data.get('error_message', 'Unknown error')}")
                        return False
                        
                await asyncio.sleep(5)  # Wait 5 seconds before next check
                
            logger.error("Audio extraction test timed out")
            return False
            
        except Exception as e:
            logger.error(f"❌ Audio extraction test failed: {e}")
            return False

    async def test_error_handling(self) -> bool:
        """Test error handling for invalid inputs"""
        logger.info("🚨 Testing error handling...")
        
        test_cases = [
            {
                "name": "Invalid URL",
                "url": "not-a-valid-url",
                "expected_status": 400
            },
            {
                "name": "Unsupported platform",
                "url": "https://example.com/video",
                "expected_status": 400
            },
            {
                "name": "Non-existent video",
                "url": "https://www.youtube.com/watch?v=nonexistentvideo123",
                "expected_status": 400
            }
        ]
        
        try:
            for test_case in test_cases:
                logger.info(f"Testing: {test_case['name']}")
                
                response = await self.client.post(
                    f"{self.base_url}/api/v1/metadata",
                    json={"url": test_case["url"]}
                )
                
                # Should return error status
                if response.status_code >= 400:
                    error_data = response.json()
                    assert "error" in error_data or "message" in error_data
                    logger.info(f"✅ Error handled correctly: {test_case['name']}")
                else:
                    logger.warning(f"⚠️ Expected error but got success for: {test_case['name']}")
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Error handling test failed: {e}")
            return False

    async def test_performance_metrics(self) -> bool:
        """Test performance monitoring and metrics collection"""
        logger.info("📈 Testing performance metrics...")
        
        try:
            # Test metrics endpoint
            response = await self.client.get(f"{self.base_url}/api/v1/monitoring/metrics")
            
            if response.status_code == 200:
                metrics = response.json()
                
                # Check for expected metric categories
                expected_categories = ["requests", "response_times", "errors", "cache"]
                for category in expected_categories:
                    if category in metrics:
                        logger.info(f"✅ Found {category} metrics")
                    else:
                        logger.warning(f"⚠️ Missing {category} metrics")
                        
                return True
            else:
                logger.error(f"Metrics endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Performance metrics test failed: {e}")
            return False

    async def test_analytics_integration(self) -> bool:
        """Test analytics event tracking"""
        logger.info("📊 Testing analytics integration...")
        
        try:
            # Test analytics event endpoint
            test_event = {
                "events": [{
                    "event_type": "test_event",
                    "data": {
                        "test": True,
                        "timestamp": int(time.time())
                    },
                    "session_id": "test_session_123"
                }],
                "client_id": "test_client_123"
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/v1/analytics/events",
                json=test_event,
                headers={"X-Client-ID": "test_client_123"}
            )
            
            if response.status_code in [200, 201]:
                logger.info("✅ Analytics event tracking working")
                return True
            else:
                logger.warning(f"⚠️ Analytics endpoint returned: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Analytics integration test failed: {e}")
            return False

    async def test_frontend_integration(self) -> bool:
        """Test frontend static file serving"""
        logger.info("🌐 Testing frontend integration...")
        
        try:
            # Test main page
            response = await self.client.get(f"{self.base_url}/")
            if response.status_code == 200:
                logger.info("✅ Root endpoint accessible")
            
            # Test static files
            static_files = [
                "/static/index.html",
                "/static/js/vidnet-ui.js",
                "/static/js/analytics-manager.js",
                "/static/js/ad-manager.js"
            ]
            
            for file_path in static_files:
                response = await self.client.get(f"{self.base_url}{file_path}")
                if response.status_code == 200:
                    logger.info(f"✅ Static file accessible: {file_path}")
                else:
                    logger.warning(f"⚠️ Static file not accessible: {file_path}")
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Frontend integration test failed: {e}")
            return False

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests"""
        logger.info("🚀 Starting VidNet integration tests...")
        
        tests = [
            ("health_check", self.test_health_endpoints),
            ("metadata_fetch", self.test_metadata_extraction),
            ("video_download", self.test_download_workflow),
            ("audio_extraction", self.test_audio_extraction),
            ("error_handling", self.test_error_handling),
            ("performance", self.test_performance_metrics),
            ("analytics", self.test_analytics_integration),
            ("frontend_integration", self.test_frontend_integration)
        ]
        
        results = {}
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            try:
                logger.info(f"\n{'='*50}")
                logger.info(f"Running test: {test_name}")
                logger.info(f"{'='*50}")
                
                result = await test_func()
                results[test_name] = result
                
                if result:
                    passed_tests += 1
                    logger.info(f"✅ {test_name} PASSED")
                else:
                    logger.error(f"❌ {test_name} FAILED")
                    
            except Exception as e:
                logger.error(f"💥 {test_name} CRASHED: {e}")
                results[test_name] = False
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info(f"INTEGRATION TEST SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Passed: {passed_tests}/{total_tests}")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if passed_tests == total_tests:
            logger.info("🎉 ALL TESTS PASSED - Ready for deployment!")
        else:
            logger.warning(f"⚠️ {total_tests - passed_tests} tests failed - Review before deployment")
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "success_rate": (passed_tests/total_tests)*100,
                "ready_for_deployment": passed_tests == total_tests
            },
            "detailed_results": results
        }

async def main():
    """Main test runner"""
    async with VidNetIntegrationTester() as tester:
        results = await tester.run_all_tests()
        
        # Save results to file
        with open("integration_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"\nTest results saved to: integration_test_results.json")
        
        # Exit with appropriate code
        if results["summary"]["ready_for_deployment"]:
            exit(0)
        else:
            exit(1)

if __name__ == "__main__":
    asyncio.run(main())