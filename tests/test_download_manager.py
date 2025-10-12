"""
Unit tests for download manager functionality.

Tests async task queue, download processing, file management, and cleanup.
"""

import pytest
import asyncio
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

from app.services.download_manager import DownloadManager, DownloadTask, DownloadError
from app.models.video import DownloadRequest, VideoMetadata, VideoQuality


class TestDownloadTask:
    """Test DownloadTask class functionality."""
    
    def test_download_task_creation(self):
        """Test DownloadTask creation and initialization."""
        request = DownloadRequest(
            url="https://youtube.com/watch?v=test",
            quality="1080p",
            format="video"
        )
        
        task = DownloadTask("test-task-id", request)
        
        assert task.task_id == "test-task-id"
        assert task.request == request
        assert task.status == "pending"
        assert task.progress == 0
        assert task.error_message is None
        assert task.download_url is None
        assert task.file_path is None
        assert task.file_size is None
        assert isinstance(task.created_at, datetime)
        assert task.started_at is None
        assert task.completed_at is None
        assert task.estimated_time is None
    
    def test_download_task_to_dict(self):
        """Test DownloadTask serialization to dictionary."""
        request = DownloadRequest(
            url="https://youtube.com/watch?v=test",
            quality="1080p",
            format="video"
        )
        
        task = DownloadTask("test-task-id", request)
        task.status = "processing"
        task.progress = 50
        task.started_at = datetime.now(timezone.utc)
        
        task_dict = task.to_dict()
        
        assert task_dict["task_id"] == "test-task-id"
        assert task_dict["status"] == "processing"
        assert task_dict["progress"] == 50
        assert task_dict["started_at"] is not None
        assert task_dict["request"]["url"] == "https://youtube.com/watch?v=test"
        assert task_dict["request"]["quality"] == "1080p"
        assert task_dict["request"]["format"] == "video"


class TestDownloadManager:
    """Test DownloadManager class functionality."""
    
    @pytest.fixture
    def temp_downloads_dir(self):
        """Create temporary downloads directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            downloads_dir = Path(temp_dir) / "downloads"
            downloads_dir.mkdir()
            yield downloads_dir
    
    @pytest.fixture
    def download_manager(self, temp_downloads_dir):
        """Create DownloadManager instance for testing."""
        manager = DownloadManager(max_concurrent_downloads=2)
        manager.downloads_dir = temp_downloads_dir
        return manager
    
    @pytest.fixture
    def sample_request(self):
        """Create sample download request."""
        return DownloadRequest(
            url="https://youtube.com/watch?v=test",
            quality="1080p",
            format="video"
        )
    
    @pytest.fixture
    def sample_audio_request(self):
        """Create sample audio extraction request."""
        return DownloadRequest(
            url="https://youtube.com/watch?v=test",
            quality="720p",
            format="audio",
            audio_quality="128kbps"
        )
    
    def test_download_manager_initialization(self, download_manager):
        """Test DownloadManager initialization."""
        assert download_manager.max_concurrent_downloads == 2
        assert isinstance(download_manager.active_tasks, dict)
        assert len(download_manager.active_tasks) == 0
        assert download_manager.cleanup_interval == 1800
        assert download_manager.file_ttl == 1800
        assert not download_manager._running
    
    @pytest.mark.asyncio
    async def test_start_stop_download_manager(self, download_manager):
        """Test starting and stopping download manager."""
        # Test start
        await download_manager.start()
        assert download_manager._running
        assert len(download_manager._worker_tasks) == 2
        assert download_manager._cleanup_task is not None
        
        # Test stop
        await download_manager.stop()
        assert not download_manager._running
        assert len(download_manager._worker_tasks) == 0
        assert download_manager._cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_submit_download_validation_error(self, download_manager):
        """Test download submission with validation error."""
        # Mock video processor to raise validation error
        with patch.object(download_manager, '_validate_download_request') as mock_validate:
            mock_validate.side_effect = DownloadError("Invalid URL")
            
            request = DownloadRequest(
                url="https://invalid-url.com/test",  # Valid URL format but invalid content
                quality="1080p",
                format="video"
            )
            
            with pytest.raises(DownloadError, match="Invalid URL"):
                await download_manager.submit_download(request)
    
    @pytest.mark.asyncio
    async def test_submit_download_success(self, download_manager, sample_request):
        """Test successful download submission."""
        # Mock validation and cache manager
        with patch.object(download_manager, '_validate_download_request') as mock_validate, \
             patch('app.services.download_manager.cache_manager') as mock_cache:
            
            mock_validate.return_value = None
            mock_cache.track_download = AsyncMock(return_value=True)
            
            await download_manager.start()
            
            task_id = await download_manager.submit_download(sample_request)
            
            assert task_id is not None
            assert task_id in download_manager.active_tasks
            
            task = download_manager.active_tasks[task_id]
            assert task.request == sample_request
            assert task.status == "pending"
            
            await download_manager.stop()
    
    @pytest.mark.asyncio
    async def test_get_task_status_active_task(self, download_manager, sample_request):
        """Test getting status of active task."""
        with patch.object(download_manager, '_validate_download_request'), \
             patch('app.services.download_manager.cache_manager') as mock_cache:
            
            mock_cache.track_download = AsyncMock(return_value=True)
            
            await download_manager.start()
            task_id = await download_manager.submit_download(sample_request)
            
            status = await download_manager.get_task_status(task_id)
            
            assert status is not None
            assert status.task_id == task_id
            assert status.status == "pending"
            assert status.progress == 0
            
            await download_manager.stop()
    
    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, download_manager):
        """Test getting status of non-existent task."""
        with patch('app.services.download_manager.cache_manager') as mock_cache:
            mock_cache.get_download_status = AsyncMock(return_value=None)
            
            status = await download_manager.get_task_status("non-existent-task")
            assert status is None
    
    @pytest.mark.asyncio
    async def test_cancel_download_success(self, download_manager, sample_request):
        """Test successful download cancellation."""
        with patch.object(download_manager, '_validate_download_request'), \
             patch('app.services.download_manager.cache_manager') as mock_cache:
            
            mock_cache.track_download = AsyncMock(return_value=True)
            
            await download_manager.start()
            task_id = await download_manager.submit_download(sample_request)
            
            # Cancel the task
            cancelled = await download_manager.cancel_download(task_id)
            
            assert cancelled is True
            
            task = download_manager.active_tasks[task_id]
            assert task.status == "failed"
            assert task.error_message == "Download cancelled by user"
            
            await download_manager.stop()
    
    @pytest.mark.asyncio
    async def test_cancel_download_not_found(self, download_manager):
        """Test cancelling non-existent download."""
        cancelled = await download_manager.cancel_download("non-existent-task")
        assert cancelled is False
    
    @pytest.mark.asyncio
    async def test_validate_download_request_success(self, download_manager, sample_request):
        """Test successful download request validation."""
        # Mock video processor
        mock_metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=120,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="1080p", format="mp4", filesize=1000000, fps=30),
                VideoQuality(quality="720p", format="mp4", filesize=500000, fps=30)
            ],
            audio_available=True,
            original_url=sample_request.url
        )
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract:
            mock_extract.return_value = mock_metadata
            
            # Should not raise exception
            await download_manager._validate_download_request(sample_request)
    
    @pytest.mark.asyncio
    async def test_validate_download_request_quality_not_available(self, download_manager):
        """Test validation with unavailable quality."""
        request = DownloadRequest(
            url="https://youtube.com/watch?v=test",
            quality="4K",  # Not available in mock metadata
            format="video"
        )
        
        mock_metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=120,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="1080p", format="mp4", filesize=1000000, fps=30),
                VideoQuality(quality="720p", format="mp4", filesize=500000, fps=30)
            ],
            audio_available=True,
            original_url=request.url
        )
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract:
            mock_extract.return_value = mock_metadata
            
            with pytest.raises(DownloadError, match="Quality 4K not available"):
                await download_manager._validate_download_request(request)
    
    @pytest.mark.asyncio
    async def test_validate_download_request_audio_not_available(self, download_manager):
        """Test validation with audio extraction when audio not available."""
        request = DownloadRequest(
            url="https://youtube.com/watch?v=test",
            quality="720p",
            format="audio"
        )
        
        mock_metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=120,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=500000, fps=30)
            ],
            audio_available=False,  # No audio available
            original_url=request.url
        )
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract:
            mock_extract.return_value = mock_metadata
            
            with pytest.raises(DownloadError, match="Audio extraction not available"):
                await download_manager._validate_download_request(request)
    
    def test_get_format_selector_video(self, download_manager):
        """Test format selector generation for video."""
        selector = download_manager._get_format_selector("1080p", "video")
        assert selector == "best[height<=1080]/best"
        
        selector = download_manager._get_format_selector("4K", "video")
        assert selector == "best[height<=2160]/best"
        
        selector = download_manager._get_format_selector("720p", "video")
        assert selector == "best[height<=720]/best"
    
    def test_get_format_selector_audio(self, download_manager):
        """Test format selector generation for audio."""
        selector = download_manager._get_format_selector("any", "audio")
        assert selector == "bestaudio/best"
    
    def test_progress_hook(self, download_manager, sample_request):
        """Test progress hook functionality."""
        task = DownloadTask("test-task", sample_request)
        
        # Test downloading status with total bytes
        progress_data = {
            'status': 'downloading',
            'downloaded_bytes': 500000,
            'total_bytes': 1000000,
            'eta': 30
        }
        
        download_manager._progress_hook(progress_data, task)
        
        assert task.progress == 50
        assert task.estimated_time == 30
        
        # Test downloading status with estimated total
        progress_data = {
            'status': 'downloading',
            'downloaded_bytes': 750000,
            'total_bytes_estimate': 1000000
        }
        
        download_manager._progress_hook(progress_data, task)
        
        assert task.progress == 75
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_files(self, download_manager, temp_downloads_dir):
        """Test cleanup of expired files."""
        # Create test files with different ages
        current_time = time.time()
        
        # Recent file (should not be deleted)
        recent_file = temp_downloads_dir / "recent_file.mp4"
        recent_file.touch()
        
        # Old file (should be deleted)
        old_file = temp_downloads_dir / "old_file.mp4"
        old_file.touch()
        
        # Modify file times
        os.utime(recent_file, (current_time, current_time))
        os.utime(old_file, (current_time - 2000, current_time - 2000))  # Older than TTL
        
        # Set shorter TTL for testing
        download_manager.file_ttl = 1800  # 30 minutes
        
        # Run cleanup
        await download_manager._cleanup_expired_files()
        
        # Check results
        assert recent_file.exists()
        assert not old_file.exists()
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_tasks(self, download_manager, sample_request):
        """Test cleanup of expired tasks from memory."""
        # Create completed task
        task = DownloadTask("test-task", sample_request)
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc) - timedelta(seconds=2000)  # Old task
        
        download_manager.active_tasks["test-task"] = task
        
        # Set shorter TTL for testing
        download_manager.file_ttl = 1800
        
        # Run cleanup
        await download_manager._cleanup_expired_files()
        
        # Task should be removed from memory
        assert "test-task" not in download_manager.active_tasks
    
    @pytest.mark.asyncio
    async def test_get_stats(self, download_manager, sample_request):
        """Test getting download manager statistics."""
        with patch.object(download_manager, '_validate_download_request'), \
             patch('app.services.download_manager.cache_manager') as mock_cache:
            
            mock_cache.track_download = AsyncMock(return_value=True)
            
            await download_manager.start()
            
            # Add some tasks
            task_id1 = await download_manager.submit_download(sample_request)
            task_id2 = await download_manager.submit_download(sample_request)
            
            # Modify task statuses
            download_manager.active_tasks[task_id1].status = "processing"
            download_manager.active_tasks[task_id2].status = "completed"
            
            stats = await download_manager.get_stats()
            
            assert stats["active_downloads"] == 1
            assert stats["completed_downloads"] == 1
            assert stats["total_tasks"] == 2
            assert stats["max_concurrent"] == 2
            assert "downloads_dir_size" in stats
            assert "cleanup_interval" in stats
            assert "file_ttl" in stats
            
            await download_manager.stop()
    
    def test_get_directory_size(self, download_manager, temp_downloads_dir):
        """Test directory size calculation."""
        # Create test files
        file1 = temp_downloads_dir / "file1.txt"
        file2 = temp_downloads_dir / "file2.txt"
        
        file1.write_text("Hello World")  # 11 bytes
        file2.write_text("Test")  # 4 bytes
        
        size = download_manager._get_directory_size(temp_downloads_dir)
        assert size == 15  # 11 + 4 bytes


class TestDownloadManagerIntegration:
    """Integration tests for download manager with mocked external dependencies."""
    
    @pytest.fixture
    def download_manager(self):
        """Create DownloadManager for integration testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(max_concurrent_downloads=1)
            manager.downloads_dir = Path(temp_dir) / "downloads"
            manager.downloads_dir.mkdir()
            yield manager
    
    @pytest.mark.asyncio
    async def test_full_download_workflow_video(self, download_manager):
        """Test complete video download workflow with mocked yt-dlp."""
        request = DownloadRequest(
            url="https://youtube.com/watch?v=test",
            quality="720p",
            format="video"
        )
        
        # Mock video processor validation
        mock_metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=120,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=500000, fps=30)
            ],
            audio_available=True,
            original_url=request.url
        )
        
        # Mock file creation
        def mock_download_with_ytdlp(url, opts):
            # Create a fake downloaded file
            fake_file = download_manager.downloads_dir / "test_video.mp4"
            fake_file.write_text("fake video content")
            return str(fake_file)
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract, \
             patch.object(download_manager, '_download_with_ytdlp', side_effect=mock_download_with_ytdlp), \
             patch('app.services.download_manager.cache_manager') as mock_cache:
            
            mock_extract.return_value = mock_metadata
            mock_cache.track_download = AsyncMock(return_value=True)
            
            await download_manager.start()
            
            # Submit download
            task_id = await download_manager.submit_download(request)
            
            # Wait for processing (with timeout)
            max_wait = 10  # seconds
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status = await download_manager.get_task_status(task_id)
                if status and status.status in ["completed", "failed"]:
                    break
                await asyncio.sleep(0.1)
            
            # Check final status
            final_status = await download_manager.get_task_status(task_id)
            assert final_status is not None
            assert final_status.status == "completed"
            assert final_status.progress == 100
            assert final_status.download_url is not None
            
            await download_manager.stop()
    
    @pytest.mark.asyncio
    async def test_full_download_workflow_audio(self, download_manager):
        """Test complete audio extraction workflow with mocked yt-dlp."""
        request = DownloadRequest(
            url="https://youtube.com/watch?v=test",
            quality="720p",
            format="audio",
            audio_quality="128kbps"
        )
        
        # Mock video processor validation
        mock_metadata = VideoMetadata(
            title="Test Audio",
            thumbnail="https://example.com/thumb.jpg",
            duration=180,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=500000, fps=30)
            ],
            audio_available=True,
            original_url=request.url
        )
        
        # Mock audio extraction result
        mock_audio_result = {
            'success': True,
            'output_path': str(download_manager.downloads_dir / "test_audio.mp3"),
            'file_size': 1024000,
            'quality': '128kbps',
            'duration': 180,
            'title': 'Test Audio',
            'platform': 'youtube',
            'original_url': request.url,
            'extraction_details': {'ffmpeg_returncode': 0}
        }
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract, \
             patch.object(download_manager.audio_extractor, 'extract_audio') as mock_audio_extract, \
             patch('app.services.download_manager.cache_manager') as mock_cache:
            
            mock_extract.return_value = mock_metadata
            mock_audio_extract.return_value = mock_audio_result
            mock_cache.track_download = AsyncMock(return_value=True)
            
            await download_manager.start()
            
            # Submit audio extraction
            task_id = await download_manager.submit_download(request)
            
            # Wait for processing (with timeout)
            max_wait = 10  # seconds
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                status = await download_manager.get_task_status(task_id)
                if status and status.status in ["completed", "failed"]:
                    break
                await asyncio.sleep(0.1)
            
            # Check final status
            final_status = await download_manager.get_task_status(task_id)
            assert final_status is not None
            assert final_status.status == "completed"
            assert final_status.progress == 100
            assert final_status.download_url is not None
            
            await download_manager.stop()


if __name__ == "__main__":
    pytest.main([__file__])