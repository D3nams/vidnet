"""
Error handling middleware for VidNet MVP.

This module provides comprehensive error handling middleware with
user-friendly error responses, logging, and monitoring integration.
"""

import time
import logging
import traceback
from typing import Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.exceptions import VidNetException, InternalError, ErrorCode


logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling all application errors with consistent formatting.
    
    Provides structured error responses, logging, and performance tracking
    for all types of errors that occur during request processing.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request and handle any errors that occur.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in the chain
            
        Returns:
            Response object with error handling applied
        """
        start_time = time.time()
        
        try:
            # Process the request
            response = await call_next(request)
            return response
            
        except VidNetException as e:
            # Handle known VidNet exceptions
            return await self._handle_vidnet_exception(request, e, start_time)
            
        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            return await self._handle_http_exception(request, e, start_time)
            
        except RequestValidationError as e:
            # Handle Pydantic validation errors
            return await self._handle_validation_exception(request, e, start_time)
            
        except Exception as e:
            # Handle unexpected exceptions
            return await self._handle_unexpected_exception(request, e, start_time)
    
    async def _handle_vidnet_exception(
        self, 
        request: Request, 
        exc: VidNetException, 
        start_time: float
    ) -> JSONResponse:
        """Handle VidNet custom exceptions."""
        response_time = (time.time() - start_time) * 1000
        
        # Log the error
        log_data = {
            "error_code": exc.error_code.value,
            "error_message": exc.message,
            "path": request.url.path,
            "method": request.method,
            "response_time_ms": round(response_time, 2),
            "retryable": exc.retryable
        }
        
        if exc.status_code >= 500:
            logger.error(f"VidNet error: {exc.message}", extra=log_data)
        else:
            logger.warning(f"VidNet error: {exc.message}", extra=log_data)
        
        # Create response
        response_data = exc.to_dict()
        response_data["response_time_ms"] = round(response_time, 2)
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response_data
        )
    
    async def _handle_http_exception(
        self, 
        request: Request, 
        exc: HTTPException, 
        start_time: float
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        response_time = (time.time() - start_time) * 1000
        
        # Log the error
        logger.warning(
            f"HTTP exception: {exc.detail}",
            extra={
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
                "response_time_ms": round(response_time, 2)
            }
        )
        
        # Map to appropriate error code
        error_code = self._map_http_status_to_error_code(exc.status_code)
        
        # Create user-friendly response
        response_data = {
            "success": False,
            "error": error_code.value,
            "message": str(exc.detail),
            "suggestion": self._get_http_error_suggestion(exc.status_code),
            "retryable": exc.status_code >= 500,
            "response_time_ms": round(response_time, 2)
        }
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response_data
        )
    
    async def _handle_validation_exception(
        self, 
        request: Request, 
        exc: RequestValidationError, 
        start_time: float
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        response_time = (time.time() - start_time) * 1000
        
        # Extract the first validation error for a cleaner message
        error_detail = exc.errors()[0] if exc.errors() else {}
        field_name = error_detail.get('loc', ['unknown'])[-1] if error_detail.get('loc') else 'unknown'
        error_msg = error_detail.get('msg', 'Validation error')
        
        # Log the error
        logger.warning(
            f"Validation error: {error_msg}",
            extra={
                "field": field_name,
                "path": request.url.path,
                "method": request.method,
                "response_time_ms": round(response_time, 2),
                "errors": exc.errors()
            }
        )
        
        # Create user-friendly error message
        if 'url' in str(field_name).lower():
            user_message = "Please provide a valid video URL from a supported platform"
            suggestion = "Check that the URL is from YouTube, TikTok, Instagram, Facebook, Twitter, Reddit, Vimeo, or a direct video link"
        elif 'quality' in str(field_name).lower():
            user_message = "Please select a valid quality option"
            suggestion = "Available qualities are typically: 720p, 1080p, 4K"
        else:
            user_message = f"Invalid {field_name}: {error_msg}"
            suggestion = "Please check your input and try again"
        
        response_data = {
            "success": False,
            "error": ErrorCode.VALIDATION_ERROR.value,
            "message": user_message,
            "suggestion": suggestion,
            "retryable": False,
            "details": {
                "field": field_name,
                "validation_errors": exc.errors()
            },
            "response_time_ms": round(response_time, 2)
        }
        
        return JSONResponse(
            status_code=422,
            content=response_data
        )
    
    async def _handle_unexpected_exception(
        self, 
        request: Request, 
        exc: Exception, 
        start_time: float
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        response_time = (time.time() - start_time) * 1000
        
        # Log the full error with traceback
        logger.error(
            f"Unexpected error: {str(exc)}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "response_time_ms": round(response_time, 2),
                "traceback": traceback.format_exc()
            }
        )
        
        # Create internal error
        internal_error = InternalError(reason=str(exc))
        response_data = internal_error.to_dict()
        response_data["response_time_ms"] = round(response_time, 2)
        
        return JSONResponse(
            status_code=500,
            content=response_data
        )
    
    def _map_http_status_to_error_code(self, status_code: int) -> ErrorCode:
        """Map HTTP status codes to error codes."""
        mapping = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.VALIDATION_ERROR,
            403: ErrorCode.VIDEO_PRIVATE,
            404: ErrorCode.VIDEO_NOT_FOUND,
            408: ErrorCode.PROCESSING_TIMEOUT,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.INTERNAL_ERROR,
            502: ErrorCode.SERVICE_UNAVAILABLE,
            503: ErrorCode.SERVICE_UNAVAILABLE,
            504: ErrorCode.PROCESSING_TIMEOUT
        }
        return mapping.get(status_code, ErrorCode.INTERNAL_ERROR)
    
    def _get_http_error_suggestion(self, status_code: int) -> str:
        """Get user-friendly suggestions for HTTP errors."""
        suggestions = {
            400: "Please check your request and try again",
            401: "Authentication required",
            403: "Access to this resource is forbidden",
            404: "The requested resource was not found",
            408: "The request timed out. Please try again",
            429: "Too many requests. Please wait before trying again",
            500: "An internal server error occurred. Please try again later",
            502: "Service temporarily unavailable. Please try again later",
            503: "Service temporarily unavailable. Please try again later",
            504: "The request timed out. Please try again"
        }
        return suggestions.get(
            status_code, 
            "An error occurred. Please try again or contact support"
        )


class ErrorSuggestionSystem:
    """
    System for providing contextual error suggestions to users.
    
    Analyzes errors and provides actionable suggestions based on
    error patterns, user context, and common resolution strategies.
    """
    
    def __init__(self):
        """Initialize the error suggestion system."""
        self.common_patterns = {
            # URL-related patterns
            "youtube.com": {
                "suggestions": [
                    "Make sure the video is public and not deleted",
                    "Check if the video is available in your region",
                    "Try copying the URL directly from the browser address bar"
                ]
            },
            "tiktok.com": {
                "suggestions": [
                    "Ensure the TikTok video is public",
                    "Try using the share link from the TikTok app",
                    "Check if the video is still available"
                ]
            },
            "instagram.com": {
                "suggestions": [
                    "Make sure the Instagram post is public",
                    "Try using the direct post URL",
                    "Check if the account is not private"
                ]
            },
            "facebook.com": {
                "suggestions": [
                    "Ensure the Facebook video is public",
                    "Try using the direct video URL",
                    "Check if the post is still available"
                ]
            }
        }
    
    def get_suggestions_for_url(self, url: str, error_code: ErrorCode) -> list[str]:
        """
        Get contextual suggestions for URL-related errors.
        
        Args:
            url: The URL that caused the error
            error_code: The specific error code
            
        Returns:
            List of actionable suggestions
        """
        suggestions = []
        
        # Platform-specific suggestions
        for platform, config in self.common_patterns.items():
            if platform in url.lower():
                suggestions.extend(config["suggestions"])
                break
        
        # Error-specific suggestions
        error_suggestions = {
            ErrorCode.VIDEO_NOT_FOUND: [
                "Verify the video URL is correct and complete",
                "Check if the video has been deleted or made private",
                "Try accessing the video in a web browser first"
            ],
            ErrorCode.VIDEO_PRIVATE: [
                "This video is private and cannot be downloaded",
                "Ask the video owner to make it public",
                "Try a different video that is publicly accessible"
            ],
            ErrorCode.UNSUPPORTED_PLATFORM: [
                "Use a URL from YouTube, TikTok, Instagram, Facebook, Twitter, Reddit, or Vimeo",
                "Check our supported platforms list",
                "Try converting the video to a supported format first"
            ],
            ErrorCode.QUALITY_NOT_AVAILABLE: [
                "Try selecting a lower quality option",
                "Check what qualities are available for this video",
                "Some videos may not have high-quality versions"
            ]
        }
        
        if error_code in error_suggestions:
            suggestions.extend(error_suggestions[error_code])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion not in seen:
                seen.add(suggestion)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions[:3]  # Limit to 3 most relevant suggestions
    
    def get_recovery_steps(self, error_code: ErrorCode) -> Dict[str, Any]:
        """
        Get structured recovery steps for an error.
        
        Args:
            error_code: The error code to get recovery steps for
            
        Returns:
            Dictionary with recovery information
        """
        recovery_steps = {
            ErrorCode.NETWORK_ERROR: {
                "immediate": ["Check your internet connection", "Try again in a few moments"],
                "if_persists": ["Try using a different network", "Contact support if the issue continues"],
                "estimated_resolution": "1-5 minutes"
            },
            ErrorCode.PROCESSING_TIMEOUT: {
                "immediate": ["Try again with the same URL", "Check if the video is very long"],
                "if_persists": ["Try a shorter video first", "Contact support for large file processing"],
                "estimated_resolution": "Immediate to 10 minutes"
            },
            ErrorCode.RATE_LIMIT_EXCEEDED: {
                "immediate": ["Wait a few minutes before trying again"],
                "if_persists": ["Reduce the frequency of requests", "Try again during off-peak hours"],
                "estimated_resolution": "1-15 minutes"
            },
            ErrorCode.SERVICE_UNAVAILABLE: {
                "immediate": ["Try again in a few minutes"],
                "if_persists": ["Check our status page", "Try again later"],
                "estimated_resolution": "5-30 minutes"
            }
        }
        
        return recovery_steps.get(error_code, {
            "immediate": ["Try the operation again"],
            "if_persists": ["Contact support if the problem continues"],
            "estimated_resolution": "Unknown"
        })


# Global error suggestion system instance
error_suggestion_system = ErrorSuggestionSystem()