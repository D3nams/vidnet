"""
Metadata API endpoint for VidNet MVP.

This module provides the POST /api/v1/metadata endpoint with caching integration,
request validation, error handling, and response time optimization.
"""

import time
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
import asyncio

from app.models.video import VideoMetadata
from app.services.video_processor import VideoProcessor
from app.services.cache_manager import cache_manager
from app.services.platform_detector import validate_video_url
from app.core.exceptions import (
    VidNetException, UnsupportedPlatformError, VideoNotFoundError, 
    ExtractionError, InvalidURLError
)


# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/v1", tags=["metadata"])


class MetadataRequest(BaseModel):
    """Request model for metadata endpoint."""
    
    url: str = Field(..., description="Video URL to extract metadata from", min_length=1, max_length=2048)
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Basic URL validation - platform validation happens in endpoint."""
        if not v or not v.strip():
            raise ValueError('URL cannot be empty')
        
        # Basic URL validation and normalization
        url = v.strip()
        if not url.startswith(('http://', 'https://')):
            # Try to add https:// prefix
            url = f'https://{url}'
        
        return url


class MetadataResponse(BaseModel):
    """Response model for metadata endpoint."""
    
    success: bool = Field(..., description="Whether the request was successful")
    data: VideoMetadata = Field(None, description="Video metadata")
    cached: bool = Field(False, description="Whether data was served from cache")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    message: str = Field(None, description="Success or error message")


class ErrorResponse(BaseModel):
    """Error response model."""
    
    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    suggestion: str = Field(None, description="Suggested action for the user")
    response_time_ms: float = Field(..., description="Response time in milliseconds")


async def get_video_processor() -> VideoProcessor:
    """Dependency to get VideoProcessor instance."""
    return VideoProcessor()


@router.post(
    "/metadata",
    response_model=MetadataResponse,
    responses={
        200: {"description": "Metadata extracted successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request or unsupported URL"},
        404: {"model": ErrorResponse, "description": "Video not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service temporarily unavailable"}
    },
    summary="Extract video metadata",
    description="Extract metadata from a video URL with caching support. Target response time: <200ms with cache, <3s without cache."
)
async def get_metadata(
    request: MetadataRequest,
    processor: VideoProcessor = Depends(get_video_processor)
) -> JSONResponse:
    """
    Extract video metadata from URL with caching integration.
    
    This endpoint:
    - Validates the input URL and platform support
    - Checks Redis cache for existing metadata (target: <200ms)
    - Extracts metadata using yt-dlp if not cached
    - Caches the result for future requests
    - Provides comprehensive error handling
    
    Args:
        request: MetadataRequest containing the video URL
        processor: VideoProcessor dependency
        
    Returns:
        JSONResponse with metadata or error information
    """
    start_time = time.time()
    url = request.url
    
    try:
        logger.info(f"Metadata request for URL: {url}")
        
        # Validate URL format and platform support
        validation_result = validate_video_url(url)
        if not validation_result['is_valid']:
            response_time = (time.time() - start_time) * 1000
            error_msg = validation_result.get('error', 'Unknown error')
            
            # Determine error type based on validation result
            if 'unsupported' in error_msg.lower() or 'platform' in error_msg.lower():
                error_type = "unsupported_platform"
                suggestion = "Please check that the URL is from a supported platform (YouTube, TikTok, Instagram, Facebook, Twitter, Reddit, Vimeo, or direct video links)"
            else:
                error_type = "validation_error"
                suggestion = "Please check that the URL is valid and properly formatted"
            
            error_response = ErrorResponse(
                error=error_type,
                message=f"Invalid or unsupported URL: {error_msg}",
                suggestion=suggestion,
                response_time_ms=round(response_time, 2)
            )
            return JSONResponse(
                status_code=400,
                content=error_response.model_dump()
            )
        
        # Check cache first for fast response
        cached_metadata = await cache_manager.get_metadata(url)
        
        if cached_metadata:
            response_time = (time.time() - start_time) * 1000
            logger.info(f"Cache hit for {url}, response time: {response_time:.2f}ms")
            
            # Remove cache-specific fields before creating VideoMetadata
            metadata_dict = {k: v for k, v in cached_metadata.items() 
                           if k not in ['cached_at', 'cache_ttl']}
            
            try:
                video_metadata = VideoMetadata(**metadata_dict)
                
                response = MetadataResponse(
                    success=True,
                    data=video_metadata,
                    cached=True,
                    response_time_ms=round(response_time, 2),
                    message="Metadata retrieved from cache"
                )
                
                return JSONResponse(
                    status_code=200,
                    content=response.model_dump()
                )
                
            except Exception as e:
                logger.warning(f"Invalid cached data for {url}, extracting fresh: {e}")
                # Continue to fresh extraction if cached data is invalid
        
        # Extract metadata using video processor
        logger.info(f"Cache miss for {url}, extracting metadata")
        
        try:
            # Set a timeout for metadata extraction
            metadata = await asyncio.wait_for(
                processor.extract_metadata(url),
                timeout=30.0  # 30 second timeout
            )
            
            # Cache the metadata for future requests
            metadata_dict = metadata.model_dump()
            cache_success = await cache_manager.cache_metadata(url, metadata_dict)
            
            if not cache_success:
                logger.warning(f"Failed to cache metadata for {url}")
            
            response_time = (time.time() - start_time) * 1000
            logger.info(f"Metadata extracted for {url}, response time: {response_time:.2f}ms")
            
            response = MetadataResponse(
                success=True,
                data=metadata,
                cached=False,
                response_time_ms=round(response_time, 2),
                message="Metadata extracted successfully"
            )
            
            return JSONResponse(
                status_code=200,
                content=response.model_dump()
            )
            
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Timeout extracting metadata for {url}")
            
            error_response = ErrorResponse(
                error="timeout",
                message="Metadata extraction timed out",
                suggestion="Please try again later or check if the video URL is accessible",
                response_time_ms=round(response_time, 2)
            )
            
            return JSONResponse(
                status_code=503,
                content=error_response.model_dump()
            )
        
    except UnsupportedPlatformError as e:
        response_time = (time.time() - start_time) * 1000
        logger.warning(f"Unsupported platform for {url}: {e}")
        
        error_response = ErrorResponse(
            error="unsupported_platform",
            message=str(e),
            suggestion="Please check that the URL is from a supported platform (YouTube, TikTok, Instagram, Facebook, Twitter, Reddit, Vimeo, or direct video links)",
            response_time_ms=round(response_time, 2)
        )
        
        return JSONResponse(
            status_code=400,
            content=error_response.model_dump()
        )
        
    except VideoNotFoundError as e:
        response_time = (time.time() - start_time) * 1000
        logger.warning(f"Video not found for {url}: {e}")
        
        error_response = ErrorResponse(
            error="video_not_found",
            message=str(e),
            suggestion="Please check that the video URL is correct and the video is publicly accessible",
            response_time_ms=round(response_time, 2)
        )
        
        return JSONResponse(
            status_code=404,
            content=error_response.model_dump()
        )
        
    except ExtractionError as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Extraction error for {url}: {e}")
        
        error_response = ErrorResponse(
            error="extraction_error",
            message=str(e),
            suggestion="Please try again later or contact support if the issue persists",
            response_time_ms=round(response_time, 2)
        )
        
        return JSONResponse(
            status_code=500,
            content=error_response.model_dump()
        )
        
    except ValueError as e:
        response_time = (time.time() - start_time) * 1000
        logger.warning(f"Validation error for {url}: {e}")
        
        error_response = ErrorResponse(
            error="validation_error",
            message=str(e),
            suggestion="Please check that the URL is valid and from a supported platform",
            response_time_ms=round(response_time, 2)
        )
        
        return JSONResponse(
            status_code=400,
            content=error_response.model_dump()
        )
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Unexpected error for {url}: {e}")
        
        error_response = ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred while processing your request",
            suggestion="Please try again later or contact support if the issue persists",
            response_time_ms=round(response_time, 2)
        )
        
        return JSONResponse(
            status_code=500,
            content=error_response.model_dump()
        )


@router.get(
    "/metadata/health",
    summary="Health check for metadata service",
    description="Check the health of the metadata extraction service and cache"
)
async def metadata_health_check() -> JSONResponse:
    """
    Health check endpoint for metadata service.
    
    Returns:
        JSONResponse with service health status
    """
    try:
        # Check cache health
        cache_health = await cache_manager.health_check()
        
        # Check video processor
        processor = VideoProcessor()
        supported_platforms = await processor.get_supported_platforms()
        
        health_data = {
            "service": "metadata",
            "status": "healthy" if cache_health["status"] == "healthy" else "degraded",
            "cache": cache_health,
            "supported_platforms": supported_platforms,
            "timestamp": time.time()
        }
        
        status_code = 200 if health_data["status"] == "healthy" else 503
        
        return JSONResponse(
            status_code=status_code,
            content=health_data
        )
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        
        return JSONResponse(
            status_code=503,
            content={
                "service": "metadata",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )


@router.get(
    "/metadata/stats",
    summary="Get metadata service statistics",
    description="Get cache performance statistics and service metrics"
)
async def get_metadata_stats() -> JSONResponse:
    """
    Get metadata service statistics.
    
    Returns:
        JSONResponse with service statistics
    """
    try:
        cache_stats = cache_manager.get_cache_stats()
        
        stats_data = {
            "service": "metadata",
            "cache_performance": cache_stats,
            "timestamp": time.time()
        }
        
        return JSONResponse(
            status_code=200,
            content=stats_data
        )
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to retrieve statistics",
                "message": str(e),
                "timestamp": time.time()
            }
        )