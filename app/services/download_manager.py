"""
Asynchronous video download processing service for VidNet MVP.

This module provides async task queue system for video downloads with quality selection,
temporary file management, auto-cleanup, and progress tracking.
"""

import asyncio
import os
import uuid
import time
import logging
import shutil
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from pathlib import Path
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

from app.models.video import DownloadRequest, DownloadResponse, VideoMetadata
from app.services.video_processor import VideoProcessor
from app.services.audio_extractor import AudioExtractor, AudioExtractionError, NoAudioTrackError
from app.services.cache_manager import cache_manager
from app.core.config import settings
from app.core.exceptions import (
    DownloadError, ProcessingTimeoutError, StorageError, NetworkError,
    VidNetException, ExtractionError
)
from app.core.retry import retry_async


# Configure logging
logger = logging.getLogger(__name__)


# Keep backward compatibility
class DownloadTimeoutError(ProcessingTimeoutError):
    """Deprecated - use ProcessingTimeoutError instead."""
    pass


class DownloadTask:
    """Represents a download task with progress tracking."""
    
    def __init__(self, task_id: str, request: DownloadRequest):
        self.task_id = task_id
        self.request = request
        self.status = "pending"
        self.progress = 0
        self.error_message: Optional[str] = None
        self.download_url: Optional[str] = None
        self.file_path: Optional[str] = None
        self.file_size: Optional[int] = None
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.estimated_time: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "download_url": self.download_url,
            "file_size": self.file_size,
            "estimated_time": self.estimated_time,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "request": {
                "url": self.request.url,
                "quality": self.request.quality,
                "format": self.request.format,
                "audio_quality": self.request.audio_quality
            }
        }


class DownloadManager:
    """
    Asynchronous download manager with task queue and file management.
    
    Features:
    - Async task queue for concurrent downloads
    - Progress tracking and status updates
    - Temporary file management with auto-cleanup
    - Quality selection for video and audio
    - Background task processing
    """
    
    def __init__(self, max_concurrent_downloads: int = 5):
        """
        Initialize download manager.
        
        Args:
            max_concurrent_downloads: Maximum number of concurrent downloads
        """
        self.max_concurrent_downloads = max_concurrent_downloads
        self.video_processor = VideoProcessor()
        self.audio_extractor = AudioExtractor()
        
        # Task management
        self.active_tasks: Dict[str, DownloadTask] = {}
        self.task_queue = asyncio.Queue()
        self.download_semaphore = asyncio.Semaphore(max_concurrent_downloads)
        
        # File management
        self.downloads_dir = Path("downloads")
        self.downloads_dir.mkdir(exist_ok=True)
        
        # Cleanup settings
        self.cleanup_interval = 1800  # 30 minutes in seconds
        self.file_ttl = 1800  # 30 minutes file TTL
        
        # Background tasks
        self._worker_tasks: List[asyncio.Task] = []
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Thread pool for blocking operations
        self.thread_pool = ThreadPoolExecutor(max_workers=max_concurrent_downloads)
    
    async def start(self):
        """Start the download manager and background tasks."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting download manager")
        
        # Start worker tasks
        for i in range(self.max_concurrent_downloads):
            task = asyncio.create_task(self._worker())
            self._worker_tasks.append(task)
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        
        logger.info(f"Download manager started with {self.max_concurrent_downloads} workers")
    
    async def stop(self):
        """Stop the download manager and cleanup resources."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping download manager")
        
        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._worker_tasks, self._cleanup_task, return_exceptions=True)
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        self._worker_tasks.clear()
        self._cleanup_task = None
        
        logger.info("Download manager stopped")
    
    async def submit_download(self, request: DownloadRequest) -> str:
        """
        Submit a download request and return task ID.
        
        Args:
            request: Download request with URL, quality, and format
            
        Returns:
            str: Unique task ID for tracking
            
        Raises:
            DownloadError: If request validation fails
        """
        try:
            # Generate unique task ID
            task_id = str(uuid.uuid4())
            
            # Validate request
            await self._validate_download_request(request)
            
            # Create download task
            task = DownloadTask(task_id, request)
            self.active_tasks[task_id] = task
            
            # Track task in cache
            await cache_manager.track_download(task_id, "pending", task.to_dict())
            
            # Add to queue
            await self.task_queue.put(task)
            
            logger.info(f"Download task {task_id} submitted for {request.url}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to submit download request: {e}")
            raise DownloadError(f"Failed to submit download: {str(e)}")
    
    async def get_task_status(self, task_id: str) -> Optional[DownloadResponse]:
        """
        Get download task status.
        
        Args:
            task_id: Task identifier
            
        Returns:
            DownloadResponse with current status or None if not found
        """
        try:
            # Check active tasks first
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                return DownloadResponse(
                    task_id=task.task_id,
                    status=task.status,
                    download_url=task.download_url,
                    error_message=task.error_message,
                    progress=task.progress,
                    estimated_time=task.estimated_time,
                    file_size=task.file_size,
                    created_at=task.created_at
                )
            
            # Check cache for completed/failed tasks
            cached_task = await cache_manager.get_download_status(task_id)
            if cached_task:
                return DownloadResponse(
                    task_id=cached_task["task_id"],
                    status=cached_task["status"],
                    download_url=cached_task.get("metadata", {}).get("download_url"),
                    error_message=cached_task.get("metadata", {}).get("error_message"),
                    progress=cached_task.get("metadata", {}).get("progress", 0),
                    estimated_time=cached_task.get("metadata", {}).get("estimated_time"),
                    file_size=cached_task.get("metadata", {}).get("file_size"),
                    created_at=datetime.fromisoformat(cached_task["updated_at"])
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return None
    
    async def cancel_download(self, task_id: str) -> bool:
        """
        Cancel a download task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            bool: True if cancelled successfully
        """
        try:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status in ["pending", "processing"]:
                    task.status = "failed"
                    task.error_message = "Download cancelled by user"
                    
                    # Update cache
                    await cache_manager.track_download(task_id, "failed", {
                        "error_message": "Download cancelled by user",
                        "progress": task.progress
                    })
                    
                    # Clean up file if exists
                    if task.file_path and os.path.exists(task.file_path):
                        try:
                            os.remove(task.file_path)
                        except Exception as e:
                            logger.warning(f"Failed to remove cancelled file {task.file_path}: {e}")
                    
                    logger.info(f"Download task {task_id} cancelled")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return False
    
    async def _validate_download_request(self, request: DownloadRequest):
        """
        Validate download request.
        
        Args:
            request: Download request to validate
            
        Raises:
            DownloadError: If validation fails
        """
        try:
            # Validate URL by extracting metadata
            metadata = await self.video_processor.extract_metadata(request.url)
            
            # Check if requested quality is available
            available_qualities = [q.quality for q in metadata.available_qualities]
            if request.quality not in available_qualities:
                raise DownloadError(f"Quality {request.quality} not available. Available: {', '.join(available_qualities)}")
            
            # Check audio availability for audio extraction
            if request.format == "audio" and not metadata.audio_available:
                raise DownloadError("Audio extraction not available for this video")
            
        except VideoProcessorError as e:
            raise DownloadError(f"Video validation failed: {str(e)}")
        except Exception as e:
            raise DownloadError(f"Request validation failed: {str(e)}")
    
    async def _worker(self):
        """Background worker to process download tasks."""
        while self._running:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                # Process task with semaphore to limit concurrency
                async with self.download_semaphore:
                    await self._process_download_task(task)
                
            except asyncio.TimeoutError:
                # No tasks in queue, continue
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)
    
    async def _process_download_task(self, task: DownloadTask):
        """
        Process a single download task.
        
        Args:
            task: Download task to process
        """
        try:
            logger.info(f"Processing download task {task.task_id}")
            
            # Update task status
            task.status = "processing"
            task.started_at = datetime.now(timezone.utc)
            task.progress = 0
            
            await cache_manager.track_download(task.task_id, "processing", {
                "progress": 0,
                "started_at": task.started_at.isoformat()
            })
            
            # Download the video/audio
            if task.request.format == "video":
                await self._download_video(task)
            else:
                await self._download_audio(task)
            
            # Mark as completed
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)
            task.progress = 100
            
            await cache_manager.track_download(task.task_id, "completed", {
                "download_url": task.download_url,
                "file_size": task.file_size,
                "progress": 100,
                "completed_at": task.completed_at.isoformat()
            })
            
            logger.info(f"Download task {task.task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Download task {task.task_id} failed: {e}")
            
            task.status = "failed"
            task.error_message = str(e)
            
            await cache_manager.track_download(task.task_id, "failed", {
                "error_message": str(e),
                "progress": task.progress
            })
            
            # Clean up partial file
            if task.file_path and os.path.exists(task.file_path):
                try:
                    os.remove(task.file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up failed download file: {cleanup_error}")
    
    async def _download_video(self, task: DownloadTask):
        """
        Download video with specified quality.
        
        Args:
            task: Download task with video request
        """
        try:
            # Generate unique filename
            timestamp = int(time.time())
            filename = f"video_{task.task_id}_{timestamp}.%(ext)s"
            file_path = self.downloads_dir / filename
            
            # Configure yt-dlp options for video download
            ydl_opts = {
                'format': self._get_format_selector(task.request.quality, 'video'),
                'outtmpl': str(file_path),
                'writesubtitles': False,
                'writeautomaticsub': False,
                'writedescription': False,
                'writeinfojson': False,
                'writethumbnail': False,
                'quiet': True,
                'no_warnings': True,
                'extractaudio': False,
                'progress_hooks': [lambda d: self._progress_hook(d, task)],
            }
            
            # Download in thread pool
            loop = asyncio.get_event_loop()
            actual_file_path = await loop.run_in_executor(
                self.thread_pool,
                self._download_with_ytdlp,
                task.request.url,
                ydl_opts
            )
            
            # Update task with file info
            task.file_path = actual_file_path
            task.file_size = os.path.getsize(actual_file_path) if os.path.exists(actual_file_path) else None
            task.download_url = f"/downloads/{os.path.basename(actual_file_path)}"
            
        except Exception as e:
            raise DownloadError(f"Video download failed: {str(e)}")
    
    async def _download_audio(self, task: DownloadTask):
        """
        Download and extract audio with specified quality.
        
        Args:
            task: Download task with audio request
        """
        try:
            # Generate unique filename
            timestamp = int(time.time())
            filename = f"audio_{task.task_id}_{timestamp}.mp3"
            file_path = self.downloads_dir / filename
            
            # Get audio quality from request
            audio_quality = task.request.audio_quality or "128kbps"
            
            # Update progress to show audio extraction started
            task.progress = 10
            await cache_manager.track_download(task.task_id, "processing", {
                "progress": 10,
                "status_message": "Starting audio extraction..."
            })
            
            # Extract audio using the dedicated audio extractor with progress tracking
            extraction_result = await self._extract_audio_with_progress(
                task, audio_quality, str(file_path)
            )
            
            # Update task with file info
            task.file_path = extraction_result['output_path']
            task.file_size = extraction_result['file_size']
            task.download_url = f"/downloads/{os.path.basename(extraction_result['output_path'])}"
            
            logger.info(f"Audio extraction completed for task {task.task_id}: {task.file_path}")
            
        except NoAudioTrackError as e:
            raise DownloadError(f"No audio track available: {str(e)}")
        except AudioExtractionError as e:
            raise DownloadError(f"Audio extraction failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in audio extraction for task {task.task_id}: {str(e)}")
            raise DownloadError(f"Audio extraction failed: {str(e)}")
    
    def _download_with_ytdlp(self, url: str, ydl_opts: Dict[str, Any]) -> str:
        """
        Download using yt-dlp in thread pool.
        
        Args:
            url: Video URL
            ydl_opts: yt-dlp options
            
        Returns:
            str: Path to downloaded file
            
        Raises:
            DownloadError: If download fails
        """
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info to get the actual filename
                info = ydl.extract_info(url, download=False)
                
                # Download the file
                ydl.download([url])
                
                # Find the actual downloaded file
                outtmpl = ydl_opts['outtmpl']
                actual_filename = ydl.prepare_filename(info)
                
                if not os.path.exists(actual_filename):
                    # Try to find the file with different extensions
                    base_path = os.path.splitext(actual_filename)[0]
                    for ext in ['.mp4', '.webm', '.mkv', '.mp3', '.m4a']:
                        test_path = base_path + ext
                        if os.path.exists(test_path):
                            actual_filename = test_path
                            break
                
                if not os.path.exists(actual_filename):
                    raise DownloadError("Downloaded file not found")
                
                return actual_filename
                
        except yt_dlp.DownloadError as e:
            raise DownloadError(f"yt-dlp download failed: {str(e)}")
        except Exception as e:
            raise DownloadError(f"Download failed: {str(e)}")
    
    def _progress_hook(self, d: Dict[str, Any], task: DownloadTask):
        """
        Progress hook for yt-dlp downloads.
        
        Args:
            d: Progress data from yt-dlp
            task: Download task to update
        """
        try:
            if d['status'] == 'downloading':
                # Calculate progress percentage
                if 'total_bytes' in d and d['total_bytes']:
                    progress = int((d['downloaded_bytes'] / d['total_bytes']) * 100)
                elif 'total_bytes_estimate' in d and d['total_bytes_estimate']:
                    progress = int((d['downloaded_bytes'] / d['total_bytes_estimate']) * 100)
                else:
                    # Use speed and ETA to estimate progress
                    progress = min(task.progress + 5, 95)  # Increment slowly if no total
                
                task.progress = max(task.progress, progress)  # Only increase progress
                
                # Estimate remaining time
                if 'eta' in d and d['eta']:
                    task.estimated_time = d['eta']
                
                # Update cache periodically (every 10% progress)
                if task.progress % 10 == 0:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(cache_manager.track_download(task.task_id, "processing", {
                                "progress": task.progress,
                                "estimated_time": task.estimated_time
                            }))
                    except RuntimeError:
                        # No event loop running, skip cache update
                        pass
                    
        except Exception as e:
            logger.warning(f"Progress hook error for task {task.task_id}: {e}")
    
    def _get_format_selector(self, quality: str, format_type: str) -> str:
        """
        Get yt-dlp format selector for quality and type.
        
        Args:
            quality: Requested quality (e.g., '1080p')
            format_type: 'video' or 'audio'
            
        Returns:
            str: yt-dlp format selector
        """
        if format_type == 'audio':
            return 'bestaudio/best'
        
        # Map quality to height
        quality_map = {
            '4K': '2160',
            '2160p': '2160',
            '1440p': '1440',
            '1080p': '1080',
            '720p': '720',
            '480p': '480',
            '360p': '360',
            '240p': '240',
            '144p': '144'
        }
        
        height = quality_map.get(quality, '720')
        
        # Return format selector that prefers the requested quality
        return f'best[height<={height}]/best'
    
    async def _cleanup_worker(self):
        """Background worker to clean up expired files."""
        while self._running:
            try:
                await self._cleanup_expired_files()
                await asyncio.sleep(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    async def _cleanup_expired_files(self):
        """Clean up expired download files."""
        try:
            current_time = time.time()
            cleanup_count = 0
            
            # Clean up files in downloads directory
            for file_path in self.downloads_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    
                    if file_age > self.file_ttl:
                        try:
                            file_path.unlink()
                            cleanup_count += 1
                            logger.debug(f"Cleaned up expired file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to remove expired file {file_path}: {e}")
            
            # Clean up completed tasks from memory
            expired_tasks = []
            for task_id, task in self.active_tasks.items():
                if task.status in ["completed", "failed"] and task.completed_at:
                    task_age = (datetime.now(timezone.utc) - task.completed_at).total_seconds()
                    if task_age > self.file_ttl:
                        expired_tasks.append(task_id)
            
            for task_id in expired_tasks:
                del self.active_tasks[task_id]
            
            if cleanup_count > 0 or expired_tasks:
                logger.info(f"Cleanup completed: {cleanup_count} files, {len(expired_tasks)} tasks removed")
                
        except Exception as e:
            logger.error(f"File cleanup error: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get download manager statistics.
        
        Returns:
            Dict with current statistics
        """
        try:
            active_count = len([t for t in self.active_tasks.values() if t.status == "processing"])
            pending_count = self.task_queue.qsize()
            completed_count = len([t for t in self.active_tasks.values() if t.status == "completed"])
            failed_count = len([t for t in self.active_tasks.values() if t.status == "failed"])
            
            return {
                "active_downloads": active_count,
                "pending_downloads": pending_count,
                "completed_downloads": completed_count,
                "failed_downloads": failed_count,
                "total_tasks": len(self.active_tasks),
                "max_concurrent": self.max_concurrent_downloads,
                "downloads_dir_size": self._get_directory_size(self.downloads_dir),
                "cleanup_interval": self.cleanup_interval,
                "file_ttl": self.file_ttl
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}
    
    async def _extract_audio_with_progress(self, task: DownloadTask, quality: str, output_path: str) -> Dict[str, Any]:
        """
        Extract audio with progress tracking.
        
        Args:
            task: Download task
            quality: Audio quality
            output_path: Output file path
            
        Returns:
            Extraction result dictionary
        """
        try:
            # Update progress stages
            progress_stages = [
                (20, "Validating video..."),
                (40, "Extracting audio..."),
                (70, "Converting to MP3..."),
                (90, "Adding metadata..."),
            ]
            
            for progress, message in progress_stages:
                task.progress = progress
                await cache_manager.track_download(task.task_id, "processing", {
                    "progress": progress,
                    "status_message": message
                })
                
                # Small delay to show progress updates
                await asyncio.sleep(0.5)
            
            # Perform the actual extraction
            extraction_result = await self.audio_extractor.extract_audio(
                video_url=task.request.url,
                quality=quality,
                output_path=output_path
            )
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Audio extraction with progress failed: {str(e)}")
            raise
    
    def _get_directory_size(self, directory: Path) -> int:
        """Get total size of directory in bytes."""
        try:
            total_size = 0
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception:
            return 0


# Global download manager instance
download_manager = DownloadManager()