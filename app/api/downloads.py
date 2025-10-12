"""
Download API endpoints for VidNet MVP.

This module provides download and audio extraction endpoints with async processing,
progress tracking, and file serving capabilities.
"""

import time
import logging
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from app.models.video import DownloadRequest, DownloadResponse
from app.services.download_manager import download_manager, DownloadError
from app.services.video_processor import VideoProcessor


# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/v1", tags=["downloads"])


async def get_video_processor() -> VideoProcessor:
    """Dependency to get VideoProcessor instance."""
    return VideoProcessor()


@router.post(
    "/download",
    response_model=DownloadResponse,
    responses={
        200: {"description": "Download initiated successfully"},
        400: {"description": "Invalid request or unsupported URL"},
        500: {"description": "Internal server error"},
        503: {"description": "Service temporarily unavailable"}
    },
    summary="Download video",
    description="Initiate video download with quality selection and background processing."
)
async def download_video(
    request: DownloadRequest,
    background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Initiate video download with background task processing.
    
    This endpoint:
    - Validates the download request
    - Submits the task to the async download queue
    - Returns a task ID for progress tracking
    - Processes download in the background
    
    Args:
        request: DownloadRequest with URL, quality, and format
        background_tasks: FastAPI background tasks
        
    Returns:
        JSONResponse with task ID and initial status
    """
    start_time = time.time()
    
    try:
        logger.info(f"Download request: {request.url}, quality: {request.quality}, format: {request.format}")
        
        # Ensure download manager is running
        if not download_manager._running:
            await download_manager.start()
        
        # Submit download task
        task_id = await download_manager.submit_download(request)
        
        response_time = (time.time() - start_time) * 1000
        
        response = DownloadResponse(
            task_id=task_id,
            status="pending",
            download_url=None,
            error_message=None,
            progress=0,
            estimated_time=None,
            file_size=None
        )
        
        logger.info(f"Download task {task_id} submitted, response time: {response_time:.2f}ms")
        
        # Convert datetime to string for JSON serialization
        response_data = response.model_dump()
        if isinstance(response_data.get('created_at'), datetime):
            response_data['created_at'] = response_data['created_at'].isoformat()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": response_data,
                "message": "Download initiated successfully",
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except DownloadError as e:
        response_time = (time.time() - start_time) * 1000
        logger.warning(f"Download request failed: {e}")
        
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "download_error",
                "message": str(e),
                "suggestion": "Please check your request parameters and try again",
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Unexpected download error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "internal_error",
                "message": "An unexpected error occurred while processing your download request",
                "suggestion": "Please try again later or contact support if the issue persists",
                "response_time_ms": round(response_time, 2)
            }
        )


@router.post(
    "/extract-audio",
    response_model=DownloadResponse,
    responses={
        200: {"description": "Audio extraction initiated successfully"},
        400: {"description": "Invalid request or audio not available"},
        500: {"description": "Internal server error"},
        503: {"description": "Service temporarily unavailable"}
    },
    summary="Extract audio",
    description="Extract audio from video as MP3 with quality selection and background processing."
)
async def extract_audio(
    request: DownloadRequest,
    background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Extract audio from video as MP3 with async processing.
    
    This endpoint:
    - Validates the audio extraction request
    - Ensures audio is available in the source video
    - Submits the task to the async download queue
    - Returns a task ID for progress tracking
    
    Args:
        request: DownloadRequest with format set to 'audio'
        background_tasks: FastAPI background tasks
        
    Returns:
        JSONResponse with task ID and initial status
    """
    start_time = time.time()
    
    try:
        # Ensure format is set to audio
        request.format = "audio"
        
        # Set default audio quality if not specified
        if not request.audio_quality:
            request.audio_quality = "128kbps"
        
        logger.info(f"Audio extraction request: {request.url}, quality: {request.audio_quality}")
        
        # Ensure download manager is running
        if not download_manager._running:
            await download_manager.start()
        
        # Submit audio extraction task
        task_id = await download_manager.submit_download(request)
        
        response_time = (time.time() - start_time) * 1000
        
        response = DownloadResponse(
            task_id=task_id,
            status="pending",
            download_url=None,
            error_message=None,
            progress=0,
            estimated_time=None,
            file_size=None
        )
        
        logger.info(f"Audio extraction task {task_id} submitted, response time: {response_time:.2f}ms")
        
        # Convert datetime to string for JSON serialization
        response_data = response.model_dump()
        if isinstance(response_data.get('created_at'), datetime):
            response_data['created_at'] = response_data['created_at'].isoformat()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": response_data,
                "message": "Audio extraction initiated successfully",
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except DownloadError as e:
        response_time = (time.time() - start_time) * 1000
        logger.warning(f"Audio extraction request failed: {e}")
        
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "audio_extraction_error",
                "message": str(e),
                "suggestion": "Please ensure the video has an audio track and try again",
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Unexpected audio extraction error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "internal_error",
                "message": "An unexpected error occurred while processing your audio extraction request",
                "suggestion": "Please try again later or contact support if the issue persists",
                "response_time_ms": round(response_time, 2)
            }
        )


@router.get(
    "/status/{task_id}",
    response_model=DownloadResponse,
    responses={
        200: {"description": "Task status retrieved successfully"},
        404: {"description": "Task not found"},
        500: {"description": "Internal server error"}
    },
    summary="Get download status",
    description="Get download progress and status for a specific task ID."
)
async def get_download_status(task_id: str) -> JSONResponse:
    """
    Get download task status and progress.
    
    This endpoint:
    - Retrieves current status of a download task
    - Returns progress percentage and estimated time
    - Provides download URL when completed
    - Returns error information if failed
    
    Args:
        task_id: Unique task identifier
        
    Returns:
        JSONResponse with task status and progress
    """
    start_time = time.time()
    
    try:
        logger.debug(f"Status request for task: {task_id}")
        
        # Get task status from download manager
        task_status = await download_manager.get_task_status(task_id)
        
        if not task_status:
            response_time = (time.time() - start_time) * 1000
            
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "task_not_found",
                    "message": f"Task {task_id} not found",
                    "suggestion": "Please check the task ID and try again",
                    "response_time_ms": round(response_time, 2)
                }
            )
        
        response_time = (time.time() - start_time) * 1000
        
        # Convert datetime to string for JSON serialization
        task_data = task_status.model_dump()
        if isinstance(task_data.get('created_at'), datetime):
            task_data['created_at'] = task_data['created_at'].isoformat()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": task_data,
                "message": f"Task status: {task_status.status}",
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Error getting status for task {task_id}: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "internal_error",
                "message": "An unexpected error occurred while retrieving task status",
                "suggestion": "Please try again later or contact support if the issue persists",
                "response_time_ms": round(response_time, 2)
            }
        )


@router.delete(
    "/cancel/{task_id}",
    responses={
        200: {"description": "Task cancelled successfully"},
        404: {"description": "Task not found"},
        400: {"description": "Task cannot be cancelled"},
        500: {"description": "Internal server error"}
    },
    summary="Cancel download",
    description="Cancel a pending or in-progress download task."
)
async def cancel_download(task_id: str) -> JSONResponse:
    """
    Cancel a download task.
    
    This endpoint:
    - Cancels pending or in-progress downloads
    - Cleans up any partial files
    - Updates task status to failed
    
    Args:
        task_id: Unique task identifier
        
    Returns:
        JSONResponse with cancellation status
    """
    start_time = time.time()
    
    try:
        logger.info(f"Cancel request for task: {task_id}")
        
        # Cancel the download task
        cancelled = await download_manager.cancel_download(task_id)
        
        response_time = (time.time() - start_time) * 1000
        
        if cancelled:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": f"Task {task_id} cancelled successfully",
                    "response_time_ms": round(response_time, 2)
                }
            )
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "task_not_found_or_completed",
                    "message": f"Task {task_id} not found or already completed",
                    "suggestion": "Check the task ID or task may have already finished",
                    "response_time_ms": round(response_time, 2)
                }
            )
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Error cancelling task {task_id}: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "internal_error",
                "message": "An unexpected error occurred while cancelling the task",
                "suggestion": "Please try again later or contact support if the issue persists",
                "response_time_ms": round(response_time, 2)
            }
        )


@router.get(
    "/downloads/stats",
    summary="Get download statistics",
    description="Get current download manager statistics and performance metrics"
)
async def get_download_stats() -> JSONResponse:
    """
    Get download manager statistics.
    
    Returns:
        JSONResponse with download statistics
    """
    try:
        stats = await download_manager.get_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": stats,
                "timestamp": time.time()
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting download stats: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "internal_error",
                "message": "Failed to retrieve download statistics",
                "details": str(e)
            }
        )


@router.get(
    "/downloads/health",
    summary="Health check for download service",
    description="Check the health of the download service and background workers"
)
async def download_health_check() -> JSONResponse:
    """
    Health check endpoint for download service.
    
    Returns:
        JSONResponse with service health status
    """
    try:
        # Check if download manager is running
        is_running = download_manager._running
        
        # Get basic stats
        stats = await download_manager.get_stats()
        
        # Check downloads directory
        downloads_dir = Path("downloads")
        downloads_dir_exists = downloads_dir.exists()
        
        health_data = {
            "service": "downloads",
            "status": "healthy" if is_running and downloads_dir_exists else "unhealthy",
            "download_manager_running": is_running,
            "downloads_directory_exists": downloads_dir_exists,
            "active_workers": len(download_manager._worker_tasks) if is_running else 0,
            "max_concurrent_downloads": download_manager.max_concurrent_downloads,
            "stats": stats,
            "timestamp": time.time()
        }
        
        status_code = 200 if health_data["status"] == "healthy" else 503
        
        return JSONResponse(
            status_code=status_code,
            content=health_data
        )
        
    except Exception as e:
        logger.error(f"Download health check error: {e}")
        
        return JSONResponse(
            status_code=503,
            content={
                "service": "downloads",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )