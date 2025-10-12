"""
Integration tests for error handling system.

Tests error handling across the entire application stack,
from API endpoints to service layers.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json

from app.main import app
from app.core.exceptions import (
    VideoNotFoundError, UnsupportedPlatformError, ProcessingTimeoutError,
    NetworkError, ExtractionError
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestAPIErrorHandling:
    """Test error handling through API endpoints."""
    
    def test_validation_error_response(self, client):
        """Test validation error handling in API."""
        # Test missing URL
        response = client.post("/api/v1/metadata", json={})
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "validation_error"
        assert "suggestion" in data
        assert "response_time_ms" in data
    
    def test_invalid_url_error_response(self, client):
        """Test invalid URL error handling."""
        response = client.post("/api/v1/metadata", json={"url": "not-a-url"})
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "valid" in data["message"].lower()
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_video_not_found_error_response(self, mock_extract, client):
        """Test video not found error handling."""
        mock_extract.side_effect = VideoNotFoundError(url="https://youtube.com/watch?v=invalid")
        
        response = client.post("/api/v1/metadata", json={"url": "https://youtube.com/watch?v=invalid"})
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "video_not_found"
        assert "suggestion" in data
        assert data["retryable"] is False
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_unsupported_platform_error_response(self, mock_extract, client):
        """Test unsupported platform error handling."""
        mock_extract.side_effect = UnsupportedPlatformError(platform="unknown")
        
        response = client.post("/api/v1/metadata", json={"url": "https://unknown-platform.com/video"})
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "unsupported_platform"
        assert "youtube" in data["suggestion"].lower()
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_network_error_response(self, mock_extract, client):
        """Test network error handling."""
        mock_extract.side_effect = NetworkError(reason="Connection timeout")
        
        response = client.post("/api/v1/metadata", json={"url": "https://youtube.com/watch?v=test"})
        
        assert response.status_code == 503
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "network_error"
        assert data["retryable"] is True
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_processing_timeout_error_response(self, mock_extract, client):
        """Test processing timeout error handling."""
        mock_extract.side_effect = ProcessingTimeoutError(timeout_seconds=30)
        
        response = client.post("/api/v1/metadata", json={"url": "https://youtube.com/watch?v=test"})
        
        assert response.status_code == 408
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "processing_timeout"
        assert data["retryable"] is True
        assert "30 seconds" in data["message"]
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_unexpected_error_response(self, mock_extract, client):
        """Test unexpected error handling."""
        mock_extract.side_effect = ValueError("Unexpected error")
        
        response = client.post("/api/v1/metadata", json={"url": "https://youtube.com/watch?v=test"})
        
        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "internal_error"
        assert data["retryable"] is False


class TestServiceLayerErrorHandling:
    """Test error handling in service layers."""
    
    @patch('yt_dlp.YoutubeDL.extract_info')
    @pytest.mark.asyncio
    async def test_video_processor_error_classification(self, mock_extract_info):
        """Test that video processor correctly classifies yt-dlp errors."""
        from app.services.video_processor import VideoProcessor
        
        processor = VideoProcessor()
        
        # Test video not found
        mock_extract_info.side_effect = Exception("Video unavailable")
        
        with pytest.raises(ExtractionError):
            await processor.extract_metadata("https://youtube.com/watch?v=invalid")
    
    @pytest.mark.asyncio
    async def test_retry_mechanism_in_video_processor(self):
        """Test that retry mechanism works in video processor."""
        from app.services.video_processor import VideoProcessor
        
        processor = VideoProcessor()
        
        # Test with invalid URL that should not be retried
        with pytest.raises(UnsupportedPlatformError):
            await processor.extract_metadata("not-a-url")


class TestErrorResponseFormat:
    """Test error response format consistency."""
    
    def test_error_response_structure(self, client):
        """Test that all error responses have consistent structure."""
        # Test validation error
        response = client.post("/api/v1/metadata", json={})
        data = response.json()
        
        # Check required fields
        required_fields = ["success", "error", "message", "suggestion", "response_time_ms"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        assert data["success"] is False
        assert isinstance(data["error"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["suggestion"], str)
        assert isinstance(data["response_time_ms"], (int, float))
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_retryable_error_indication(self, mock_extract, client):
        """Test that retryable errors are properly indicated."""
        # Test retryable error
        mock_extract.side_effect = NetworkError(reason="Temporary network issue")
        
        response = client.post("/api/v1/metadata", json={"url": "https://youtube.com/watch?v=test"})
        data = response.json()
        
        assert "retryable" in data
        assert data["retryable"] is True
        
        # Test non-retryable error
        mock_extract.side_effect = UnsupportedPlatformError(platform="unknown")
        
        response = client.post("/api/v1/metadata", json={"url": "https://unknown.com/video"})
        data = response.json()
        
        assert "retryable" in data
        assert data["retryable"] is False


class TestErrorSuggestions:
    """Test error suggestion system integration."""
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_platform_specific_suggestions(self, mock_extract, client):
        """Test that platform-specific suggestions are provided."""
        mock_extract.side_effect = VideoNotFoundError(url="https://youtube.com/watch?v=invalid")
        
        response = client.post("/api/v1/metadata", json={"url": "https://youtube.com/watch?v=invalid"})
        data = response.json()
        
        # Should contain actionable suggestions
        assert "suggestion" in data
        assert len(data["suggestion"]) > 0
        assert isinstance(data["suggestion"], str)
    
    @patch('app.services.video_processor.VideoProcessor.extract_metadata')
    def test_error_details_preservation(self, mock_extract, client):
        """Test that error details are preserved in responses."""
        mock_extract.side_effect = ProcessingTimeoutError(timeout_seconds=30)
        
        response = client.post("/api/v1/metadata", json={"url": "https://youtube.com/watch?v=test"})
        data = response.json()
        
        # Should contain error details
        assert "details" in data
        assert "timeout_seconds" in data["details"]
        assert data["details"]["timeout_seconds"] == 30


if __name__ == "__main__":
    pytest.main([__file__])