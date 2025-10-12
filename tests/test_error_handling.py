"""
Unit tests for comprehensive error handling system.

Tests custom exceptions, error response middleware, retry logic,
and error suggestion system.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.exceptions import (
    VidNetException, ErrorCode, ValidationError as VidNetValidationError,
    InvalidURLError, InvalidQualityError, UnsupportedPlatformError,
    VideoNotFoundError, VideoPrivateError, ExtractionError,
    NetworkError, ProcessingTimeoutError, classify_yt_dlp_error
)
from app.core.retry import RetryConfig, RetryManager, retry_async, retry_sync
from app.middleware.error_handler import ErrorHandlingMiddleware, ErrorSuggestionSystem


class TestVidNetExceptions:
    """Test custom VidNet exception classes."""
    
    def test_base_exception_creation(self):
        """Test VidNetException base class."""
        exc = VidNetException(
            message="Test error",
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
            suggestion="Try again",
            details={"key": "value"},
            retryable=True
        )
        
        assert exc.message == "Test error"
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.status_code == 500
        assert exc.suggestion == "Try again"
        assert exc.details == {"key": "value"}
        assert exc.retryable is True
    
    def test_exception_to_dict(self):
        """Test exception serialization to dictionary."""
        exc = VidNetException(
            message="Test error",
            error_code=ErrorCode.VIDEO_NOT_FOUND,
            status_code=404
        )
        
        result = exc.to_dict()
        
        assert result["success"] is False
        assert result["error"] == ErrorCode.VIDEO_NOT_FOUND.value
        assert result["message"] == "Test error"
        assert "suggestion" in result
        assert result["retryable"] is False
        assert "details" in result
    
    def test_default_suggestions(self):
        """Test default error suggestions."""
        exc = InvalidURLError(url="invalid-url")
        assert "valid" in exc.suggestion.lower()
        
        exc = UnsupportedPlatformError(platform="unknown")
        assert "youtube" in exc.suggestion.lower()
        
        exc = VideoNotFoundError(url="test-url")
        assert "exists" in exc.suggestion.lower()
    
    def test_invalid_url_error(self):
        """Test InvalidURLError specific functionality."""
        url = "not-a-valid-url"
        exc = InvalidURLError(url=url)
        
        assert exc.error_code == ErrorCode.INVALID_URL
        assert exc.status_code == 422
        assert exc.details["url"] == url
        assert "valid URL" in exc.message
    
    def test_invalid_quality_error(self):
        """Test InvalidQualityError with available qualities."""
        quality = "8K"
        available = ["720p", "1080p", "4K"]
        exc = InvalidQualityError(quality=quality, available_qualities=available)
        
        assert exc.error_code == ErrorCode.QUALITY_NOT_AVAILABLE
        assert exc.details["requested_quality"] == quality
        assert exc.details["available_qualities"] == available
        assert "720p, 1080p, 4K" in exc.suggestion
    
    def test_unsupported_platform_error(self):
        """Test UnsupportedPlatformError."""
        platform = "unknown-platform"
        exc = UnsupportedPlatformError(platform=platform)
        
        assert exc.error_code == ErrorCode.UNSUPPORTED_PLATFORM
        assert exc.status_code == 400
        assert exc.details["platform"] == platform
    
    def test_processing_timeout_error(self):
        """Test ProcessingTimeoutError."""
        timeout = 30
        exc = ProcessingTimeoutError(timeout_seconds=timeout)
        
        assert exc.error_code == ErrorCode.PROCESSING_TIMEOUT
        assert exc.status_code == 408
        assert exc.retryable is True
        assert exc.details["timeout_seconds"] == timeout
        assert "30 seconds" in exc.message


class TestYtDlpErrorClassification:
    """Test yt-dlp error classification system."""
    
    def test_video_not_found_classification(self):
        """Test classification of video not found errors."""
        error_messages = [
            "Video unavailable",
            "This video does not exist",
            "404 Not Found",
            "Video has been removed"
        ]
        
        for msg in error_messages:
            exc = classify_yt_dlp_error(msg)
            assert isinstance(exc, (VideoNotFoundError, VidNetException))
            assert exc.error_code in [ErrorCode.VIDEO_NOT_FOUND, ErrorCode.VIDEO_DELETED]
    
    def test_private_video_classification(self):
        """Test classification of private video errors."""
        exc = classify_yt_dlp_error("Video unavailable: Private video")
        assert exc.error_code == ErrorCode.VIDEO_PRIVATE
    
    def test_region_blocked_classification(self):
        """Test classification of region-blocked videos."""
        exc = classify_yt_dlp_error("Video not available in your country")
        assert exc.error_code == ErrorCode.VIDEO_REGION_BLOCKED
    
    def test_network_error_classification(self):
        """Test classification of network errors."""
        error_messages = [
            "Connection timeout",
            "Network unreachable",
            "Connection failed"
        ]
        
        for msg in error_messages:
            exc = classify_yt_dlp_error(msg)
            assert exc.error_code == ErrorCode.NETWORK_ERROR
            assert exc.retryable is True
    
    def test_rate_limit_classification(self):
        """Test classification of rate limit errors."""
        exc = classify_yt_dlp_error("Too many requests, rate limit exceeded")
        assert exc.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert exc.retryable is True
    
    def test_default_classification(self):
        """Test default classification for unknown errors."""
        exc = classify_yt_dlp_error("Some unknown error occurred")
        assert exc.error_code == ErrorCode.EXTRACTION_FAILED


class TestRetryLogic:
    """Test retry logic with exponential backoff."""
    
    def test_retry_config_delay_calculation(self):
        """Test retry delay calculation."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=10.0, jitter=False)
        
        # Test exponential backoff
        assert config.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert config.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert config.calculate_delay(2) == 4.0  # 1.0 * 2^2
        assert config.calculate_delay(3) == 8.0  # 1.0 * 2^3
        
        # Test max delay cap
        assert config.calculate_delay(10) == 10.0  # Capped at max_delay
    
    def test_retry_config_with_jitter(self):
        """Test retry delay with jitter."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=True)
        
        # With jitter, delays should vary slightly
        delays = [config.calculate_delay(1) for _ in range(10)]
        
        # All delays should be around 2.0 but with some variation
        assert all(1.8 <= delay <= 2.2 for delay in delays)
        assert len(set(delays)) > 1  # Should have some variation
    
    @pytest.mark.asyncio
    async def test_retry_manager_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        manager = RetryManager()
        
        async def success_func():
            return "success"
        
        result = await manager.retry_async(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_manager_success_after_retries(self):
        """Test successful execution after retries."""
        manager = RetryManager(RetryConfig(max_attempts=3, base_delay=0.01))
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError(reason="Temporary network issue")
            return "success"
        
        result = await manager.retry_async(flaky_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_manager_max_attempts_exceeded(self):
        """Test failure after max attempts."""
        manager = RetryManager(RetryConfig(max_attempts=2, base_delay=0.01))
        
        async def always_fail():
            raise NetworkError(reason="Always fails")
        
        with pytest.raises(NetworkError):
            await manager.retry_async(always_fail)
    
    @pytest.mark.asyncio
    async def test_retry_manager_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        manager = RetryManager(RetryConfig(max_attempts=3, base_delay=0.01))
        
        call_count = 0
        
        async def non_retryable_fail():
            nonlocal call_count
            call_count += 1
            raise InvalidURLError(url="bad-url")  # Not retryable
        
        with pytest.raises(InvalidURLError):
            await manager.retry_async(non_retryable_fail)
        
        assert call_count == 1  # Should not retry
    
    @pytest.mark.asyncio
    async def test_retry_manager_timeout(self):
        """Test overall timeout functionality."""
        manager = RetryManager(RetryConfig(max_attempts=10, base_delay=0.1, timeout=0.2))
        
        async def slow_func():
            await asyncio.sleep(0.1)
            raise NetworkError(reason="Slow network")
        
        with pytest.raises(ProcessingTimeoutError):
            await manager.retry_async(slow_func)
    
    def test_retry_sync_functionality(self):
        """Test synchronous retry functionality."""
        manager = RetryManager(RetryConfig(max_attempts=3, base_delay=0.01))
        
        call_count = 0
        
        def flaky_sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary connection issue")
            return "success"
        
        result = manager.retry_sync(flaky_sync_func, retryable_exceptions=[ConnectionError])
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator(self):
        """Test retry decorator functionality."""
        call_count = 0
        
        @retry_async(max_attempts=3, base_delay=0.01)
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError(reason="Temporary issue")
            return "decorated_success"
        
        result = await decorated_func()
        assert result == "decorated_success"
        assert call_count == 3


class TestErrorHandlingMiddleware:
    """Test error handling middleware."""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing."""
        return ErrorHandlingMiddleware(Mock())
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request for testing."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "POST"
        return request
    
    @pytest.mark.asyncio
    async def test_vidnet_exception_handling(self, middleware, mock_request):
        """Test handling of VidNet exceptions."""
        exc = VideoNotFoundError(url="test-url")
        
        response = await middleware._handle_vidnet_exception(mock_request, exc, time.time())
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        
        # Check response content
        content = response.body.decode()
        assert "video_not_found" in content
        assert "success" in content
        assert "false" in content.lower()
    
    @pytest.mark.asyncio
    async def test_http_exception_handling(self, middleware, mock_request):
        """Test handling of HTTP exceptions."""
        exc = HTTPException(status_code=404, detail="Not found")
        
        response = await middleware._handle_http_exception(mock_request, exc, time.time())
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_validation_exception_handling(self, middleware, mock_request):
        """Test handling of validation exceptions."""
        # Create a mock validation error
        errors = [{"loc": ["url"], "msg": "field required", "type": "value_error.missing"}]
        exc = RequestValidationError(errors)
        
        response = await middleware._handle_validation_exception(mock_request, exc, time.time())
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
        
        # Check response content
        content = response.body.decode()
        assert "validation_error" in content
        assert "valid video URL" in content
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_handling(self, middleware, mock_request):
        """Test handling of unexpected exceptions."""
        exc = ValueError("Unexpected error")
        
        response = await middleware._handle_unexpected_exception(mock_request, exc, time.time())
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        
        # Check response content
        content = response.body.decode()
        assert "internal_error" in content


class TestErrorSuggestionSystem:
    """Test error suggestion system."""
    
    @pytest.fixture
    def suggestion_system(self):
        """Create suggestion system instance."""
        return ErrorSuggestionSystem()
    
    def test_url_specific_suggestions(self, suggestion_system):
        """Test platform-specific URL suggestions."""
        # YouTube URL
        suggestions = suggestion_system.get_suggestions_for_url(
            "https://youtube.com/watch?v=test",
            ErrorCode.VIDEO_NOT_FOUND
        )
        assert any("public" in s.lower() for s in suggestions)
        assert any("region" in s.lower() for s in suggestions)
        
        # TikTok URL
        suggestions = suggestion_system.get_suggestions_for_url(
            "https://tiktok.com/@user/video/123",
            ErrorCode.VIDEO_NOT_FOUND
        )
        assert any("tiktok" in s.lower() for s in suggestions)
    
    def test_error_specific_suggestions(self, suggestion_system):
        """Test error-specific suggestions."""
        suggestions = suggestion_system.get_suggestions_for_url(
            "https://example.com/video",
            ErrorCode.UNSUPPORTED_PLATFORM
        )
        assert any("youtube" in s.lower() for s in suggestions)
        assert any("supported" in s.lower() for s in suggestions)
    
    def test_recovery_steps(self, suggestion_system):
        """Test recovery step generation."""
        steps = suggestion_system.get_recovery_steps(ErrorCode.NETWORK_ERROR)
        
        assert "immediate" in steps
        assert "if_persists" in steps
        assert "estimated_resolution" in steps
        assert isinstance(steps["immediate"], list)
        assert len(steps["immediate"]) > 0
    
    def test_suggestion_deduplication(self, suggestion_system):
        """Test that duplicate suggestions are removed."""
        # This would normally produce duplicate suggestions
        suggestions = suggestion_system.get_suggestions_for_url(
            "https://youtube.com/watch?v=test",
            ErrorCode.VIDEO_NOT_FOUND
        )
        
        # Check for duplicates
        assert len(suggestions) == len(set(suggestions))
        
        # Should be limited to 3 suggestions
        assert len(suggestions) <= 3


class TestErrorRecoveryMechanisms:
    """Test error recovery and suggestion mechanisms."""
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test complete error recovery workflow."""
        # Simulate a service that fails then recovers
        call_count = 0
        
        @retry_async(max_attempts=3, base_delay=0.01)
        async def recovering_service():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                raise NetworkError(reason="Network temporarily unavailable")
            elif call_count == 2:
                raise ProcessingTimeoutError(timeout_seconds=30)
            else:
                return {"status": "success", "data": "recovered"}
        
        result = await recovering_service()
        assert result["status"] == "success"
        assert call_count == 3
    
    def test_error_context_preservation(self):
        """Test that error context is preserved through the system."""
        original_url = "https://youtube.com/watch?v=invalid"
        
        try:
            raise VideoNotFoundError(url=original_url)
        except VideoNotFoundError as e:
            # Error should preserve context
            assert e.details.get("url") == original_url
            assert e.error_code == ErrorCode.VIDEO_NOT_FOUND
            
            # Should be serializable
            error_dict = e.to_dict()
            assert error_dict["error"] == ErrorCode.VIDEO_NOT_FOUND.value
            assert error_dict["details"]["url"] == original_url


if __name__ == "__main__":
    pytest.main([__file__])