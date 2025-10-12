"""
Comprehensive error handling system for VidNet MVP.

This module provides custom exception classes, error response formatting,
retry logic, and user-friendly error suggestions.
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum


logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standardized error codes for consistent error handling."""
    
    # Validation errors
    INVALID_URL = "invalid_url"
    INVALID_QUALITY = "invalid_quality"
    INVALID_FORMAT = "invalid_format"
    VALIDATION_ERROR = "validation_error"
    
    # Platform errors
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    PLATFORM_UNAVAILABLE = "platform_unavailable"
    PLATFORM_RATE_LIMITED = "platform_rate_limited"
    
    # Video errors
    VIDEO_NOT_FOUND = "video_not_found"
    VIDEO_PRIVATE = "video_private"
    VIDEO_DELETED = "video_deleted"
    VIDEO_REGION_BLOCKED = "video_region_blocked"
    VIDEO_AGE_RESTRICTED = "video_age_restricted"
    
    # Quality errors
    QUALITY_NOT_AVAILABLE = "quality_not_available"
    AUDIO_NOT_AVAILABLE = "audio_not_available"
    
    # Processing errors
    EXTRACTION_FAILED = "extraction_failed"
    DOWNLOAD_FAILED = "download_failed"
    CONVERSION_FAILED = "conversion_failed"
    PROCESSING_TIMEOUT = "processing_timeout"
    
    # System errors
    CACHE_ERROR = "cache_error"
    STORAGE_ERROR = "storage_error"
    NETWORK_ERROR = "network_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INTERNAL_ERROR = "internal_error"


class VidNetException(Exception):
    """
    Base exception class for all VidNet errors.
    
    Provides structured error information including error codes,
    user-friendly messages, and actionable suggestions.
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int = 400,
        suggestion: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False
    ):
        """
        Initialize VidNet exception.
        
        Args:
            message: Human-readable error message
            error_code: Standardized error code
            status_code: HTTP status code
            suggestion: Actionable suggestion for the user
            details: Additional error details
            retryable: Whether the operation can be retried
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.suggestion = suggestion or self._get_default_suggestion()
        self.details = details or {}
        self.retryable = retryable
    
    def _get_default_suggestion(self) -> str:
        """Get default suggestion based on error code."""
        suggestions = {
            ErrorCode.INVALID_URL: "Please check that the URL is valid and from a supported platform",
            ErrorCode.UNSUPPORTED_PLATFORM: "Try a URL from YouTube, TikTok, Instagram, Facebook, Twitter, Reddit, or Vimeo",
            ErrorCode.VIDEO_NOT_FOUND: "Check that the video exists and is publicly accessible",
            ErrorCode.VIDEO_PRIVATE: "This video is private and cannot be downloaded",
            ErrorCode.VIDEO_DELETED: "This video has been deleted or removed",
            ErrorCode.QUALITY_NOT_AVAILABLE: "Try selecting a different quality option",
            ErrorCode.RATE_LIMIT_EXCEEDED: "Please wait a moment before trying again",
            ErrorCode.PROCESSING_TIMEOUT: "The request took too long to process. Please try again",
            ErrorCode.SERVICE_UNAVAILABLE: "The service is temporarily unavailable. Please try again later"
        }
        return suggestions.get(self.error_code, "Please try again or contact support if the problem persists")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "success": False,
            "error": self.error_code.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "retryable": self.retryable,
            "details": self.details
        }


# Validation Errors
class ValidationError(VidNetException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=422,
            **kwargs
        )
        if field:
            self.details["field"] = field


class InvalidURLError(VidNetException):
    """Raised when URL validation fails."""
    
    def __init__(self, url: str, **kwargs):
        super().__init__(
            message=f"Invalid URL format: {url}",
            error_code=ErrorCode.INVALID_URL,
            status_code=422,
            suggestion="Please provide a valid URL starting with http:// or https://",
            **kwargs
        )
        self.details["url"] = url


class InvalidQualityError(VidNetException):
    """Raised when quality selection is invalid."""
    
    def __init__(self, quality: str, available_qualities: List[str], **kwargs):
        super().__init__(
            message=f"Quality '{quality}' is not available",
            error_code=ErrorCode.QUALITY_NOT_AVAILABLE,
            status_code=422,
            suggestion=f"Available qualities: {', '.join(available_qualities)}",
            **kwargs
        )
        self.details.update({
            "requested_quality": quality,
            "available_qualities": available_qualities
        })


# Platform Errors
class UnsupportedPlatformError(VidNetException):
    """Raised when the platform is not supported."""
    
    def __init__(self, platform: str, **kwargs):
        super().__init__(
            message=f"Platform '{platform}' is not supported",
            error_code=ErrorCode.UNSUPPORTED_PLATFORM,
            status_code=400,
            **kwargs
        )
        self.details["platform"] = platform


class PlatformUnavailableError(VidNetException):
    """Raised when a platform is temporarily unavailable."""
    
    def __init__(self, platform: str, **kwargs):
        super().__init__(
            message=f"Platform '{platform}' is temporarily unavailable",
            error_code=ErrorCode.PLATFORM_UNAVAILABLE,
            status_code=503,
            retryable=True,
            **kwargs
        )
        self.details["platform"] = platform


# Video Errors
class VideoNotFoundError(VidNetException):
    """Raised when video cannot be found."""
    
    def __init__(self, url: str, **kwargs):
        super().__init__(
            message="Video not found or is not accessible",
            error_code=ErrorCode.VIDEO_NOT_FOUND,
            status_code=404,
            **kwargs
        )
        self.details["url"] = url


class VideoPrivateError(VidNetException):
    """Raised when video is private."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="This video is private and cannot be downloaded",
            error_code=ErrorCode.VIDEO_PRIVATE,
            status_code=403,
            **kwargs
        )


class VideoDeletedError(VidNetException):
    """Raised when video has been deleted."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="This video has been deleted or removed",
            error_code=ErrorCode.VIDEO_DELETED,
            status_code=404,
            **kwargs
        )


class VideoRegionBlockedError(VidNetException):
    """Raised when video is blocked in the user's region."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="This video is not available in your region",
            error_code=ErrorCode.VIDEO_REGION_BLOCKED,
            status_code=403,
            suggestion="Try using a VPN or accessing from a different location",
            **kwargs
        )


# Processing Errors
class ExtractionError(VidNetException):
    """Raised when metadata extraction fails."""
    
    def __init__(self, reason: Optional[str] = None, **kwargs):
        message = "Failed to extract video information"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.EXTRACTION_FAILED,
            status_code=500,
            retryable=True,
            **kwargs
        )
        if reason:
            self.details["reason"] = reason


class DownloadError(VidNetException):
    """Raised when video download fails."""
    
    def __init__(self, reason: Optional[str] = None, **kwargs):
        message = "Failed to download video"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.DOWNLOAD_FAILED,
            status_code=500,
            retryable=True,
            **kwargs
        )
        if reason:
            self.details["reason"] = reason


class ConversionError(VidNetException):
    """Raised when audio conversion fails."""
    
    def __init__(self, reason: Optional[str] = None, **kwargs):
        message = "Failed to convert audio"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.CONVERSION_FAILED,
            status_code=500,
            retryable=True,
            **kwargs
        )
        if reason:
            self.details["reason"] = reason


class ProcessingTimeoutError(VidNetException):
    """Raised when processing takes too long."""
    
    def __init__(self, timeout_seconds: int, **kwargs):
        super().__init__(
            message=f"Processing timed out after {timeout_seconds} seconds",
            error_code=ErrorCode.PROCESSING_TIMEOUT,
            status_code=408,
            retryable=True,
            **kwargs
        )
        self.details["timeout_seconds"] = timeout_seconds


# System Errors
class CacheError(VidNetException):
    """Raised when cache operations fail."""
    
    def __init__(self, operation: str, **kwargs):
        super().__init__(
            message=f"Cache operation failed: {operation}",
            error_code=ErrorCode.CACHE_ERROR,
            status_code=500,
            retryable=True,
            **kwargs
        )
        self.details["operation"] = operation


class StorageError(VidNetException):
    """Raised when storage operations fail."""
    
    def __init__(self, operation: str, **kwargs):
        super().__init__(
            message=f"Storage operation failed: {operation}",
            error_code=ErrorCode.STORAGE_ERROR,
            status_code=500,
            retryable=True,
            **kwargs
        )
        self.details["operation"] = operation


class NetworkError(VidNetException):
    """Raised when network operations fail."""
    
    def __init__(self, reason: Optional[str] = None, **kwargs):
        message = "Network error occurred"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.NETWORK_ERROR,
            status_code=503,
            retryable=True,
            **kwargs
        )
        if reason:
            self.details["reason"] = reason


class RateLimitExceededError(VidNetException):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, retry_after: Optional[int] = None, **kwargs):
        message = "Rate limit exceeded"
        if retry_after:
            message += f". Try again in {retry_after} seconds"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=429,
            retryable=True,
            **kwargs
        )
        if retry_after:
            self.details["retry_after"] = retry_after


class ServiceUnavailableError(VidNetException):
    """Raised when service is temporarily unavailable."""
    
    def __init__(self, service: Optional[str] = None, **kwargs):
        message = "Service temporarily unavailable"
        if service:
            message = f"{service} is temporarily unavailable"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=503,
            retryable=True,
            **kwargs
        )
        if service:
            self.details["service"] = service


class InternalError(VidNetException):
    """Raised for unexpected internal errors."""
    
    def __init__(self, reason: Optional[str] = None, **kwargs):
        message = "An internal error occurred"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
            retryable=False,
            **kwargs
        )
        if reason:
            self.details["reason"] = reason


def classify_yt_dlp_error(error_msg: str) -> VidNetException:
    """
    Classify yt-dlp errors into appropriate VidNet exceptions.
    
    Args:
        error_msg: Error message from yt-dlp
        
    Returns:
        Appropriate VidNetException subclass
    """
    error_lower = error_msg.lower()
    
    # Region blocking (check first, more specific)
    if any(pattern in error_lower for pattern in [
        "not available in your country", "blocked in your country",
        "geo-blocked", "region blocked"
    ]):
        return VideoRegionBlockedError()
    
    # Age restriction
    if "age" in error_lower and "restrict" in error_lower:
        return VidNetException(
            message="This video is age-restricted and cannot be downloaded",
            error_code=ErrorCode.VIDEO_AGE_RESTRICTED,
            status_code=403
        )
    
    # Video not found patterns (check after more specific patterns)
    if any(pattern in error_lower for pattern in [
        "video unavailable", "not available", "does not exist",
        "video not found", "404", "removed"
    ]):
        if "private" in error_lower:
            return VideoPrivateError()
        elif "deleted" in error_lower or "removed" in error_lower:
            return VideoDeletedError()
        else:
            return VideoNotFoundError(url="")
    
    # Network/timeout errors
    if any(pattern in error_lower for pattern in [
        "timeout", "connection", "network", "unreachable"
    ]):
        return NetworkError(reason=error_msg)
    
    # Rate limiting
    if any(pattern in error_lower for pattern in [
        "rate limit", "too many requests", "429"
    ]):
        return RateLimitExceededError()
    
    # Platform unavailable
    if any(pattern in error_lower for pattern in [
        "service unavailable", "server error", "503"
    ]):
        return PlatformUnavailableError(platform="unknown")
    
    # Default to extraction error
    return ExtractionError(reason=error_msg)