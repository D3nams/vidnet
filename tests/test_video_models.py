"""
Unit tests for video data models.

Tests for VideoQuality, VideoMetadata, DownloadRequest, and DownloadResponse models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.video import VideoQuality, VideoMetadata, DownloadRequest, DownloadResponse


class TestVideoQuality:
    """Test cases for VideoQuality model."""
    
    def test_valid_video_quality(self):
        """Test creating a valid VideoQuality instance."""
        quality = VideoQuality(
            quality="1080p",
            format="mp4",
            filesize=1024000,
            fps=30
        )
        
        assert quality.quality == "1080p"
        assert quality.format == "mp4"
        assert quality.filesize == 1024000
        assert quality.fps == 30
    
    def test_video_quality_format_normalization(self):
        """Test that video format is normalized to lowercase."""
        quality = VideoQuality(quality="720p", format="MP4")
        assert quality.format == "mp4"
    
    def test_invalid_quality_format(self):
        """Test validation error for invalid quality format."""
        with pytest.raises(ValidationError) as exc_info:
            VideoQuality(quality="invalid", format="mp4")
        
        assert "Quality must be one of" in str(exc_info.value)
    
    def test_invalid_video_format(self):
        """Test validation error for invalid video format."""
        with pytest.raises(ValidationError) as exc_info:
            VideoQuality(quality="1080p", format="invalid")
        
        assert "Format must be one of" in str(exc_info.value)
    
    def test_invalid_fps_range(self):
        """Test validation error for invalid FPS values."""
        # Test negative FPS
        with pytest.raises(ValidationError) as exc_info:
            VideoQuality(quality="1080p", format="mp4", fps=-1)
        assert "FPS must be between 1 and 120" in str(exc_info.value)
        
        # Test FPS too high
        with pytest.raises(ValidationError) as exc_info:
            VideoQuality(quality="1080p", format="mp4", fps=150)
        assert "FPS must be between 1 and 120" in str(exc_info.value)
    
    def test_optional_fields(self):
        """Test that optional fields can be None."""
        quality = VideoQuality(quality="720p", format="webm")
        assert quality.filesize is None
        assert quality.fps is None


class TestVideoMetadata:
    """Test cases for VideoMetadata model."""
    
    def test_valid_video_metadata(self):
        """Test creating a valid VideoMetadata instance."""
        qualities = [VideoQuality(quality="720p", format="mp4")]
        
        metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=300,
            platform="youtube",
            available_qualities=qualities,
            audio_available=True,
            original_url="https://youtube.com/watch?v=test123"
        )
        
        assert metadata.title == "Test Video"
        assert metadata.platform == "youtube"
        assert len(metadata.available_qualities) == 1
        assert metadata.audio_available is True
    
    def test_title_validation(self):
        """Test title validation rules."""
        qualities = [VideoQuality(quality="720p", format="mp4")]
        
        # Empty title
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadata(
                title="",
                thumbnail="https://example.com/thumb.jpg",
                duration=300,
                platform="youtube",
                available_qualities=qualities,
                original_url="https://youtube.com/watch?v=test123"
            )
        assert "Title cannot be empty" in str(exc_info.value)
        
        # Title too long
        long_title = "x" * 501
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadata(
                title=long_title,
                thumbnail="https://example.com/thumb.jpg",
                duration=300,
                platform="youtube",
                available_qualities=qualities,
                original_url="https://youtube.com/watch?v=test123"
            )
        assert "Title cannot exceed 500 characters" in str(exc_info.value)
    
    def test_title_whitespace_trimming(self):
        """Test that title whitespace is trimmed."""
        qualities = [VideoQuality(quality="720p", format="mp4")]
        
        metadata = VideoMetadata(
            title="  Test Video  ",
            thumbnail="https://example.com/thumb.jpg",
            duration=300,
            platform="youtube",
            available_qualities=qualities,
            original_url="https://youtube.com/watch?v=test123"
        )
        
        assert metadata.title == "Test Video"
    
    def test_thumbnail_url_validation(self):
        """Test thumbnail URL validation."""
        qualities = [VideoQuality(quality="720p", format="mp4")]
        
        # Invalid URL format
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadata(
                title="Test Video",
                thumbnail="not-a-url",
                duration=300,
                platform="youtube",
                available_qualities=qualities,
                original_url="https://youtube.com/watch?v=test123"
            )
        assert "Invalid thumbnail URL format" in str(exc_info.value)
    
    def test_duration_validation(self):
        """Test duration validation rules."""
        qualities = [VideoQuality(quality="720p", format="mp4")]
        
        # Negative duration
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadata(
                title="Test Video",
                thumbnail="https://example.com/thumb.jpg",
                duration=-1,
                platform="youtube",
                available_qualities=qualities,
                original_url="https://youtube.com/watch?v=test123"
            )
        assert "Duration cannot be negative" in str(exc_info.value)
        
        # Duration too long (over 24 hours)
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadata(
                title="Test Video",
                thumbnail="https://example.com/thumb.jpg",
                duration=86401,
                platform="youtube",
                available_qualities=qualities,
                original_url="https://youtube.com/watch?v=test123"
            )
        assert "Duration cannot exceed 24 hours" in str(exc_info.value)
    
    def test_empty_qualities_validation(self):
        """Test that at least one quality must be available."""
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadata(
                title="Test Video",
                thumbnail="https://example.com/thumb.jpg",
                duration=300,
                platform="youtube",
                available_qualities=[],
                original_url="https://youtube.com/watch?v=test123"
            )
        assert "At least one quality option must be available" in str(exc_info.value)
    
    def test_file_extension_for_direct_links(self):
        """Test file extension validation for direct links."""
        qualities = [VideoQuality(quality="720p", format="mp4")]
        
        # Direct link without file extension should fail
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadata(
                title="Test Video",
                thumbnail="https://example.com/thumb.jpg",
                duration=300,
                platform="direct",
                available_qualities=qualities,
                original_url="https://example.com/video.mp4"
            )
        assert "File extension is required for direct links" in str(exc_info.value)
        
        # Direct link with file extension should work
        metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=300,
            platform="direct",
            available_qualities=qualities,
            file_extension=".mp4",
            original_url="https://example.com/video.mp4"
        )
        assert metadata.file_extension == ".mp4"
    
    def test_file_extension_dot_prefix(self):
        """Test that file extension gets dot prefix if missing."""
        qualities = [VideoQuality(quality="720p", format="mp4")]
        
        metadata = VideoMetadata(
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration=300,
            platform="direct",
            available_qualities=qualities,
            file_extension="mp4",
            original_url="https://example.com/video.mp4"
        )
        assert metadata.file_extension == ".mp4"


class TestDownloadRequest:
    """Test cases for DownloadRequest model."""
    
    def test_valid_download_request(self):
        """Test creating a valid DownloadRequest instance."""
        request = DownloadRequest(
            url="https://youtube.com/watch?v=test123",
            quality="1080p",
            format="video"
        )
        
        assert request.url == "https://youtube.com/watch?v=test123"
        assert request.quality == "1080p"
        assert request.format == "video"
        assert request.audio_quality is None
    
    def test_audio_download_request(self):
        """Test creating an audio download request."""
        request = DownloadRequest(
            url="https://youtube.com/watch?v=test123",
            quality="720p",
            format="audio",
            audio_quality="320kbps"
        )
        
        assert request.format == "audio"
        assert request.audio_quality == "320kbps"
    
    def test_url_validation(self):
        """Test URL validation in download request."""
        # Empty URL
        with pytest.raises(ValidationError) as exc_info:
            DownloadRequest(url="", quality="1080p")
        assert "URL cannot be empty" in str(exc_info.value)
        
        # Invalid URL format
        with pytest.raises(ValidationError) as exc_info:
            DownloadRequest(url="not-a-url", quality="1080p")
        assert "Invalid URL format" in str(exc_info.value)
    
    def test_url_whitespace_trimming(self):
        """Test that URL whitespace is trimmed."""
        request = DownloadRequest(
            url="  https://youtube.com/watch?v=test123  ",
            quality="1080p"
        )
        assert request.url == "https://youtube.com/watch?v=test123"
    
    def test_quality_validation(self):
        """Test quality validation in download request."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadRequest(
                url="https://youtube.com/watch?v=test123",
                quality="invalid"
            )
        assert "Quality must be one of" in str(exc_info.value)
    
    def test_audio_quality_required_for_audio_format(self):
        """Test that audio quality is required for audio format."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadRequest(
                url="https://youtube.com/watch?v=test123",
                quality="720p",
                format="audio"
            )
        assert "Audio quality is required for audio extraction" in str(exc_info.value)


class TestDownloadResponse:
    """Test cases for DownloadResponse model."""
    
    def test_valid_download_response(self):
        """Test creating a valid DownloadResponse instance."""
        response = DownloadResponse(
            task_id="test-task-123",
            status="pending"
        )
        
        assert response.task_id == "test-task-123"
        assert response.status == "pending"
        assert response.download_url is None
        assert response.error_message is None
        assert isinstance(response.created_at, datetime)
    
    def test_completed_response(self):
        """Test completed download response."""
        response = DownloadResponse(
            task_id="test-task-123",
            status="completed",
            download_url="https://example.com/download/video.mp4",
            progress=100,
            file_size=1024000
        )
        
        assert response.status == "completed"
        assert response.download_url == "https://example.com/download/video.mp4"
        assert response.progress == 100
        assert response.file_size == 1024000
    
    def test_failed_response(self):
        """Test failed download response."""
        response = DownloadResponse(
            task_id="test-task-123",
            status="failed",
            error_message="Video not found"
        )
        
        assert response.status == "failed"
        assert response.error_message == "Video not found"
    
    def test_task_id_validation(self):
        """Test task ID validation."""
        # Empty task ID
        with pytest.raises(ValidationError) as exc_info:
            DownloadResponse(task_id="", status="pending")
        assert "Task ID cannot be empty" in str(exc_info.value)
        
        # Invalid characters in task ID
        with pytest.raises(ValidationError) as exc_info:
            DownloadResponse(task_id="task@123", status="pending")
        assert "Task ID must contain only alphanumeric characters" in str(exc_info.value)
    
    def test_progress_validation(self):
        """Test progress validation."""
        # Progress below 0
        with pytest.raises(ValidationError) as exc_info:
            DownloadResponse(task_id="test-123", status="processing", progress=-1)
        assert "Progress must be between 0 and 100" in str(exc_info.value)
        
        # Progress above 100
        with pytest.raises(ValidationError) as exc_info:
            DownloadResponse(task_id="test-123", status="processing", progress=101)
        assert "Progress must be between 0 and 100" in str(exc_info.value)
    
    def test_estimated_time_validation(self):
        """Test estimated time validation."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadResponse(task_id="test-123", status="processing", estimated_time=-1)
        assert "Estimated time cannot be negative" in str(exc_info.value)
    
    def test_download_url_required_for_completed(self):
        """Test that download URL is required when status is completed."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadResponse(task_id="test-123", status="completed")
        assert "Download URL is required when status is completed" in str(exc_info.value)
    
    def test_error_message_required_for_failed(self):
        """Test that error message is required when status is failed."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadResponse(task_id="test-123", status="failed")
        assert "Error message is required when status is failed" in str(exc_info.value)