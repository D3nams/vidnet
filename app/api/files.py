"""
File serving API for VidNet MVP.

This module provides secure file serving for downloaded videos and audio files
with proper headers and auto-cleanup integration.
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import mimetypes

from app.services.download_manager import download_manager
from app.services.storage_manager import storage_manager


# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/downloads", tags=["files"])


@router.get(
    "/{filename}",
    summary="Download file",
    description="Download a processed video or audio file with proper headers and security checks"
)
async def download_file(filename: str, request: Request) -> FileResponse:
    """
    Serve downloaded files with security checks and proper headers.
    
    This endpoint:
    - Validates file exists and is within downloads directory
    - Sets appropriate content type and headers
    - Provides secure file serving with download disposition
    - Logs download access for monitoring
    
    Args:
        filename: Name of the file to download
        request: FastAPI request object
        
    Returns:
        FileResponse with the requested file
        
    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        # Security: Validate filename to prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            logger.warning(f"Suspicious filename access attempt: {filename} from {request.client.host}")
            raise HTTPException(
                status_code=400,
                detail="Invalid filename"
            )
        
        # Construct file path
        downloads_dir = Path("downloads")
        file_path = downloads_dir / filename
        
        # Check if file exists and is within downloads directory
        if not file_path.exists():
            logger.warning(f"File not found: {filename}")
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
        
        # Use storage manager for security validation
        if not await storage_manager.validate_file_access(file_path):
            logger.warning(f"Access denied for file: {filename}")
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )
        
        # Get file info
        file_size = file_path.stat().st_size
        file_mtime = file_path.stat().st_mtime
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            # Default content types for common video/audio formats
            ext = file_path.suffix.lower()
            content_type_map = {
                '.mp4': 'video/mp4',
                '.webm': 'video/webm',
                '.mkv': 'video/x-matroska',
                '.avi': 'video/x-msvideo',
                '.mov': 'video/quicktime',
                '.mp3': 'audio/mpeg',
                '.m4a': 'audio/mp4',
                '.wav': 'audio/wav',
                '.flac': 'audio/flac'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
        
        # Log download access
        logger.info(f"File download: {filename} ({file_size} bytes) from {request.client.host}")
        
        # Get security headers from storage manager
        security_headers = storage_manager.get_security_headers(file_path)
        
        # Add additional headers
        security_headers.update({
            'Content-Length': str(file_size),
            'Accept-Ranges': 'bytes'
        })
        
        # Create response with security headers
        response = FileResponse(
            path=str(file_path),
            media_type=content_type,
            filename=filename,
            headers=security_headers
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while serving file"
        )


@router.get(
    "/info/{filename}",
    summary="Get file information",
    description="Get information about a downloaded file without downloading it"
)
async def get_file_info(filename: str) -> JSONResponse:
    """
    Get information about a downloaded file.
    
    Args:
        filename: Name of the file to get info for
        
    Returns:
        JSONResponse with file information
    """
    try:
        # Security: Validate filename
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename"
            )
        
        # Construct file path
        downloads_dir = Path("downloads")
        file_path = downloads_dir / filename
        
        # Check if file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
        
        # Get file stats
        stat = file_path.stat()
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            ext = file_path.suffix.lower()
            content_type_map = {
                '.mp4': 'video/mp4',
                '.webm': 'video/webm',
                '.mkv': 'video/x-matroska',
                '.avi': 'video/x-msvideo',
                '.mov': 'video/quicktime',
                '.mp3': 'audio/mpeg',
                '.m4a': 'audio/mp4',
                '.wav': 'audio/wav',
                '.flac': 'audio/flac'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
        
        # Calculate file age
        file_age_seconds = time.time() - stat.st_mtime
        
        file_info = {
            "filename": filename,
            "size_bytes": stat.st_size,
            "size_human": _format_file_size(stat.st_size),
            "content_type": content_type,
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
            "age_seconds": int(file_age_seconds),
            "download_url": f"/downloads/{filename}",
            "expires_in_seconds": max(0, 1800 - int(file_age_seconds))  # 30 minutes TTL
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": file_info
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info for {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while getting file information"
        )


@router.get(
    "/",
    summary="List available files",
    description="List all available downloaded files with their information"
)
async def list_files() -> JSONResponse:
    """
    List all available downloaded files.
    
    Returns:
        JSONResponse with list of available files
    """
    try:
        downloads_dir = Path("downloads")
        
        if not downloads_dir.exists():
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "data": {
                        "files": [],
                        "total_count": 0,
                        "total_size_bytes": 0
                    }
                }
            )
        
        files = []
        total_size = 0
        current_time = time.time()
        
        for file_path in downloads_dir.iterdir():
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    file_age = current_time - stat.st_mtime
                    
                    # Determine content type
                    content_type, _ = mimetypes.guess_type(str(file_path))
                    if not content_type:
                        ext = file_path.suffix.lower()
                        content_type_map = {
                            '.mp4': 'video/mp4',
                            '.webm': 'video/webm',
                            '.mkv': 'video/x-matroska',
                            '.avi': 'video/x-msvideo',
                            '.mov': 'video/quicktime',
                            '.mp3': 'audio/mpeg',
                            '.m4a': 'audio/mp4',
                            '.wav': 'audio/wav',
                            '.flac': 'audio/flac'
                        }
                        content_type = content_type_map.get(ext, 'application/octet-stream')
                    
                    file_info = {
                        "filename": file_path.name,
                        "size_bytes": stat.st_size,
                        "size_human": _format_file_size(stat.st_size),
                        "content_type": content_type,
                        "created_at": stat.st_ctime,
                        "modified_at": stat.st_mtime,
                        "age_seconds": int(file_age),
                        "download_url": f"/downloads/{file_path.name}",
                        "expires_in_seconds": max(0, 1800 - int(file_age))
                    }
                    
                    files.append(file_info)
                    total_size += stat.st_size
                    
                except Exception as e:
                    logger.warning(f"Error processing file {file_path}: {e}")
                    continue
        
        # Sort by creation time (newest first)
        files.sort(key=lambda x: x['created_at'], reverse=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "files": files,
                    "total_count": len(files),
                    "total_size_bytes": total_size,
                    "total_size_human": _format_file_size(total_size)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while listing files"
        )


def _format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Human-readable size (e.g., "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"