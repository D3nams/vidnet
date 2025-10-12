"""
Integration tests for the metadata API endpoint.

Tests the POST /api/v1/metadata endpoint with various URL types,
caching behavior, error handling, and response time optimization.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.main import app
from app.models.video import VideoMetadata, VideoQuality
from app.services.video_processor import VideoProcessorError, UnsupportedPlatformError, VideoNotFoundError, ExtractionError


# Test client
client = TestClient(app)


class TestMetadataAPI:
    """Test suite for metadata API endpoint."""
    
    def test_metadata_endpoint_exists(self):
        """Test that the metadata endpoint is properly registered."""
        response = client.post("/api/v1/metadata", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404
    
    def test_invalid_request_body(self):
        """Test handling of invalid request body."""
        # Empty body
        response = client.post("/api/v1/metadata", json={})
        assert response.status_code == 422
        
        # Missing URL
        response = client.post("/api/v1/metadata", json={"not_url": "test"})
        assert response.status_code == 422
        
        # Invalid URL type
        response = client.post("/api/v1/metadata", json={"url": 123})
        assert response.status_code == 422
    
    def test_empty_url_validation(self):
        """Test validation of empty URLs."""
        test_cases = [
            "",
            "   ",
            None
        ]
        
        for url in test_cases:
            if url is None:
                continue  # Skip None as it would cause different error
            response = client.post("/api/v1/metadata", json={"url": url})
            assert response.status_code == 422
            data = response.json()
            assert "success" in data
            assert data["success"] is False
            assert "error" in data
            assert "message" in data
    
    def test_invalid_url_format(self):
        """Test validation of invalid URL formats."""
        test_cases = [
            "not-a-url",
            "ftp://example.com/video",
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "file:///etc/passwd"
        ]
        
        for url in test_cases:
            response = client.post("/api/v1/metadata", json={"url": url})
            assert response.status_code in [400, 422]
            data = response.json()
            assert data["success"] is False
    
    @patch('app.services.cache_manager.cache_manager.get_metadata')
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_successful_metadata_extraction_youtube(self, mock_extract, mock_cache_get):
        """Test successful metadata extraction for YouTube URL."""
        # Mock cache miss
        mock_cache_get.return_value = None
        
        # Mock successful extraction
        mock_metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=180,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="1080p", format="mp4", filesize=50000000, fps=30),
                VideoQuality(quality="720p", format="mp4", filesize=30000000, fps=30)
            ],
            audio_available=True,
            file_extension=None,
            original_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        mock_extract.return_value = mock_metadata
        
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["cached"] is False
        assert "data" in data
        assert data["data"]["title"] == "Test Video"
        assert data["data"]["platform"] == "youtube"
        assert len(data["data"]["available_qualities"]) == 2
        assert "response_time_ms" in data
        assert data["response_time_ms"] > 0
    
    @patch('app.services.cache_manager.cache_manager.get_metadata')
    def test_cached_metadata_response(self, mock_cache_get):
        """Test fast response when metadata is cached."""
        # Mock cache hit
        cached_data = {
            "title": "Cached Video",
            "thumbnail": "https://example.com/thumb.jpg",
            "duration": 120,
            "platform": "youtube",
            "available_qualities": [
                {"quality": "720p", "format": "mp4", "filesize": 25000000, "fps": 30}
            ],
            "audio_available": True,
            "file_extension": None,
            "original_url": "https://www.youtube.com/watch?v=cached123",
            "cached_at": "2023-01-01T00:00:00Z",
            "cache_ttl": 3600
        }
        mock_cache_get.return_value = cached_data
        
        start_time = time.time()
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=cached123"
        })
        response_time = (time.time() - start_time) * 1000
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["cached"] is True
        assert data["data"]["title"] == "Cached Video"
        assert data["response_time_ms"] < 200  # Should be fast with cache
        assert response_time < 200  # Actual response time should be fast
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_unsupported_platform_error(self, mock_extract):
        """Test handling of unsupported platform errors."""
        mock_extract.side_effect = UnsupportedPlatformError("Unsupported platform: example.com")
        
        response = client.post("/api/v1/metadata", json={
            "url": "https://unsupported-platform.com/video/123"
        })
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "unsupported_platform"
        assert "Unsupported platform" in data["message"]
        assert "suggestion" in data
        assert "response_time_ms" in data
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_video_not_found_error(self, mock_extract):
        """Test handling of video not found errors."""
        mock_extract.side_effect = VideoNotFoundError("Video not found or unavailable")
        
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=nonexistent"
        })
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "video_not_found"
        assert "not found" in data["message"]
        assert "suggestion" in data
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_extraction_error(self, mock_extract):
        """Test handling of extraction errors."""
        mock_extract.side_effect = ExtractionError("Failed to extract metadata")
        
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=error123"
        })
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "extraction_error"
        assert "Failed to extract" in data["message"]
        assert "suggestion" in data
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_timeout_error(self, mock_extract):
        """Test handling of timeout errors."""
        async def slow_extract(*args, **kwargs):
            await asyncio.sleep(35)  # Longer than 30s timeout
            return None
        
        mock_extract.side_effect = slow_extract
        
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=slow123"
        })
        
        assert response.status_code == 503
        data = response.json()
        
        assert data["success"] is False
        assert data["error"] == "timeout"
        assert "timed out" in data["message"]
        assert "suggestion" in data
    
    def test_multiple_platform_urls(self):
        """Test metadata extraction with various platform URLs."""
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.tiktok.com/@user/video/1234567890",
            "https://www.instagram.com/p/ABC123/",
            "https://www.facebook.com/watch/?v=1234567890",
            "https://twitter.com/user/status/1234567890",
            "https://www.reddit.com/r/videos/comments/abc123/title/",
            "https://vimeo.com/123456789",
            "https://example.com/video.mp4"
        ]
        
        for url in test_urls:
            response = client.post("/api/v1/metadata", json={"url": url})
            # Should not return 422 (validation error) for supported platforms
            # May return other errors due to mocking, but validation should pass
            assert response.status_code != 422, f"Validation failed for {url}"
    
    def test_url_normalization(self):
        """Test that URLs are properly normalized."""
        # Test URL without protocol
        response = client.post("/api/v1/metadata", json={
            "url": "www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        # Should not fail validation (protocol should be added)
        assert response.status_code != 422
    
    def test_response_time_tracking(self):
        """Test that response time is properly tracked."""
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        
        data = response.json()
        assert "response_time_ms" in data
        assert isinstance(data["response_time_ms"], (int, float))
        assert data["response_time_ms"] > 0
    
    def test_health_check_endpoint(self):
        """Test the metadata health check endpoint."""
        response = client.get("/api/v1/metadata/health")
        
        assert response.status_code in [200, 503]  # Healthy or degraded
        data = response.json()
        
        assert "service" in data
        assert data["service"] == "metadata"
        assert "status" in data
        assert "cache" in data
        assert "supported_platforms" in data
        assert "timestamp" in data
    
    def test_stats_endpoint(self):
        """Test the metadata statistics endpoint."""
        response = client.get("/api/v1/metadata/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "service" in data
        assert data["service"] == "metadata"
        assert "cache_performance" in data
        assert "timestamp" in data
        
        # Check cache performance metrics
        cache_perf = data["cache_performance"]
        assert "hit_rate" in cache_perf
        assert "miss_rate" in cache_perf
        assert "error_rate" in cache_perf
        assert "total_requests" in cache_perf
    
    @patch('app.services.cache_manager.cache_manager.get_metadata')
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    @patch('app.services.cache_manager.cache_manager.cache_metadata')
    def test_caching_integration(self, mock_cache_set, mock_extract, mock_cache_get):
        """Test that metadata is properly cached after extraction."""
        # Mock cache miss initially
        mock_cache_get.return_value = None
        
        # Mock successful extraction
        mock_metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=180,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=30000000, fps=30)
            ],
            audio_available=True,
            file_extension=None,
            original_url="https://www.youtube.com/watch?v=test123"
        )
        mock_extract.return_value = mock_metadata
        mock_cache_set.return_value = True
        
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=test123"
        })
        
        assert response.status_code == 200
        
        # Verify that cache_metadata was called
        mock_cache_set.assert_called_once()
        
        # Verify the cached data structure
        call_args = mock_cache_set.call_args
        cached_url = call_args[0][0]
        cached_metadata = call_args[0][1]
        
        assert cached_url == "https://www.youtube.com/watch?v=test123"
        assert cached_metadata["title"] == "Test Video"
        assert cached_metadata["platform"] == "youtube"
    
    def test_error_response_format(self):
        """Test that error responses follow the correct format."""
        # Test with invalid URL to trigger validation error
        response = client.post("/api/v1/metadata", json={
            "url": "not-a-valid-url"
        })
        
        data = response.json()
        
        # Check error response structure
        assert "success" in data
        assert data["success"] is False
        assert "error" in data
        assert "message" in data
        assert "response_time_ms" in data
        
        # Suggestion should be present for user-facing errors
        if response.status_code in [400, 404, 422]:
            assert "suggestion" in data
    
    def test_concurrent_requests(self):
        """Test handling of concurrent requests to the same URL."""
        import threading
        import queue
        
        url = "https://www.youtube.com/watch?v=concurrent123"
        results = queue.Queue()
        
        def make_request():
            response = client.post("/api/v1/metadata", json={"url": url})
            results.put(response.status_code)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that all requests completed (regardless of success/failure)
        status_codes = []
        while not results.empty():
            status_codes.append(results.get())
        
        assert len(status_codes) == 5
        # All requests should return some response (not hang)
        for status_code in status_codes:
            assert status_code in [200, 400, 404, 500, 503]


class TestMetadataAPIPerformance:
    """Performance tests for metadata API."""
    
    @patch('app.services.cache_manager.cache_manager.get_metadata')
    def test_cached_response_performance(self, mock_cache_get):
        """Test that cached responses meet performance targets (<200ms)."""
        # Mock cache hit
        cached_data = {
            "title": "Fast Cached Video",
            "thumbnail": "https://example.com/thumb.jpg",
            "duration": 120,
            "platform": "youtube",
            "available_qualities": [
                {"quality": "720p", "format": "mp4", "filesize": 25000000, "fps": 30}
            ],
            "audio_available": True,
            "file_extension": None,
            "original_url": "https://www.youtube.com/watch?v=fast123"
        }
        mock_cache_get.return_value = cached_data
        
        # Measure response time
        start_time = time.time()
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=fast123"
        })
        actual_response_time = (time.time() - start_time) * 1000
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that response time meets target
        assert actual_response_time < 200, f"Response time {actual_response_time}ms exceeds 200ms target"
        assert data["response_time_ms"] < 200, f"Reported response time {data['response_time_ms']}ms exceeds target"
        assert data["cached"] is True
    
    def test_response_time_reporting_accuracy(self):
        """Test that reported response times are accurate."""
        start_time = time.time()
        response = client.post("/api/v1/metadata", json={
            "url": "https://www.youtube.com/watch?v=timing123"
        })
        actual_time = (time.time() - start_time) * 1000
        
        data = response.json()
        reported_time = data["response_time_ms"]
        
        # Reported time should be within reasonable range of actual time
        # Allow for some variance due to measurement differences
        assert abs(reported_time - actual_time) < 50, f"Reported time {reported_time}ms differs significantly from actual {actual_time}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])