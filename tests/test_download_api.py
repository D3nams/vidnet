"""
Unit tests for download API endpoints.

Tests download initiation, status tracking, file serving, and error handling.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.video import DownloadRequest, DownloadResponse
from app.services.download_manager import DownloadError


class TestDownloadAPI:
    """Test download API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_download_request(self):
        """Sample download request data."""
        return {
            "url": "https://youtube.com/watch?v=test",
            "quality": "1080p",
            "format": "video"
        }
    
    @pytest.fixture
    def sample_audio_request(self):
        """Sample audio extraction request data."""
        return {
            "url": "https://youtube.com/watch?v=test",
            "quality": "720p",
            "format": "audio",
            "audio_quality": "128kbps"
        }
    
    def test_download_video_success(self, client, sample_download_request):
        """Test successful video download initiation."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager._running = True
            mock_manager.start = AsyncMock()
            mock_manager.submit_download = AsyncMock(return_value="test-task-id")
            
            response = client.post("/api/v1/download", json=sample_download_request)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["task_id"] == "test-task-id"
            assert data["data"]["status"] == "pending"
            assert "response_time_ms" in data
    
    def test_download_video_validation_error(self, client):
        """Test download with invalid request data."""
        invalid_request = {
            "url": "",  # Empty URL
            "quality": "1080p",
            "format": "video"
        }
        
        response = client.post("/api/v1/download", json=invalid_request)
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "validation_error"
    
    def test_download_video_download_error(self, client, sample_download_request):
        """Test download with download manager error."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager._running = True
            mock_manager.start = AsyncMock()
            mock_manager.submit_download = AsyncMock(
                side_effect=DownloadError("Quality not available")
            )
            
            response = client.post("/api/v1/download", json=sample_download_request)
            
            assert response.status_code == 400
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "download_error"
            assert "Quality not available" in data["message"]
    
    def test_download_video_internal_error(self, client, sample_download_request):
        """Test download with unexpected error."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager._running = True
            mock_manager.start = AsyncMock()
            mock_manager.submit_download = AsyncMock(
                side_effect=Exception("Unexpected error")
            )
            
            response = client.post("/api/v1/download", json=sample_download_request)
            
            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "internal_error"
    
    def test_extract_audio_success(self, client, sample_audio_request):
        """Test successful audio extraction initiation."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager._running = True
            mock_manager.start = AsyncMock()
            mock_manager.submit_download = AsyncMock(return_value="test-audio-task-id")
            
            response = client.post("/api/v1/extract-audio", json=sample_audio_request)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["task_id"] == "test-audio-task-id"
            assert data["data"]["status"] == "pending"
    
    def test_extract_audio_default_quality(self, client):
        """Test audio extraction with default quality."""
        request_without_audio_quality = {
            "url": "https://youtube.com/watch?v=test",
            "quality": "720p",
            "format": "audio"
            # No audio_quality specified
        }
        
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager._running = True
            mock_manager.start = AsyncMock()
            mock_manager.submit_download = AsyncMock(return_value="test-task-id")
            
            response = client.post("/api/v1/extract-audio", json=request_without_audio_quality)
            
            assert response.status_code == 200
            # Verify that default audio quality was set
            mock_manager.submit_download.assert_called_once()
            call_args = mock_manager.submit_download.call_args[0][0]
            assert call_args.audio_quality == "128kbps"
    
    def test_get_download_status_success(self, client):
        """Test successful status retrieval."""
        mock_response = DownloadResponse(
            task_id="test-task-id",
            status="processing",
            progress=50,
            estimated_time=30
        )
        
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.get_task_status = AsyncMock(return_value=mock_response)
            
            response = client.get("/api/v1/status/test-task-id")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["task_id"] == "test-task-id"
            assert data["data"]["status"] == "processing"
            assert data["data"]["progress"] == 50
    
    def test_get_download_status_not_found(self, client):
        """Test status retrieval for non-existent task."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.get_task_status = AsyncMock(return_value=None)
            
            response = client.get("/api/v1/status/non-existent-task")
            
            assert response.status_code == 404
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "task_not_found"
    
    def test_get_download_status_error(self, client):
        """Test status retrieval with error."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.get_task_status = AsyncMock(
                side_effect=Exception("Database error")
            )
            
            response = client.get("/api/v1/status/test-task-id")
            
            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "internal_error"
    
    def test_cancel_download_success(self, client):
        """Test successful download cancellation."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.cancel_download = AsyncMock(return_value=True)
            
            response = client.delete("/api/v1/cancel/test-task-id")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "cancelled successfully" in data["message"]
    
    def test_cancel_download_not_found(self, client):
        """Test cancellation of non-existent task."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.cancel_download = AsyncMock(return_value=False)
            
            response = client.delete("/api/v1/cancel/non-existent-task")
            
            assert response.status_code == 404
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "task_not_found_or_completed"
    
    def test_cancel_download_error(self, client):
        """Test cancellation with error."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.cancel_download = AsyncMock(
                side_effect=Exception("Cancellation error")
            )
            
            response = client.delete("/api/v1/cancel/test-task-id")
            
            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "internal_error"
    
    def test_get_download_stats_success(self, client):
        """Test successful stats retrieval."""
        mock_stats = {
            "active_downloads": 2,
            "pending_downloads": 1,
            "completed_downloads": 5,
            "failed_downloads": 1,
            "total_tasks": 9,
            "max_concurrent": 5
        }
        
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.get_stats = AsyncMock(return_value=mock_stats)
            
            response = client.get("/api/v1/downloads/stats")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["active_downloads"] == 2
            assert data["data"]["total_tasks"] == 9
    
    def test_get_download_stats_error(self, client):
        """Test stats retrieval with error."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.get_stats = AsyncMock(
                side_effect=Exception("Stats error")
            )
            
            response = client.get("/api/v1/downloads/stats")
            
            assert response.status_code == 500
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "internal_error"
    
    def test_download_health_check_healthy(self, client):
        """Test health check when service is healthy."""
        mock_stats = {
            "active_downloads": 1,
            "total_tasks": 5
        }
        
        with patch('app.api.downloads.download_manager') as mock_manager, \
             patch('pathlib.Path.exists', return_value=True):
            
            mock_manager._running = True
            mock_manager._worker_tasks = [Mock(), Mock()]
            mock_manager.max_concurrent_downloads = 5
            mock_manager.get_stats = AsyncMock(return_value=mock_stats)
            
            response = client.get("/api/v1/downloads/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "downloads"
            assert data["status"] == "healthy"
            assert data["download_manager_running"] is True
            assert data["downloads_directory_exists"] is True
    
    def test_download_health_check_unhealthy(self, client):
        """Test health check when service is unhealthy."""
        with patch('app.api.downloads.download_manager') as mock_manager, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_manager._running = False
            mock_manager._worker_tasks = []
            mock_manager.max_concurrent_downloads = 5
            mock_manager.get_stats = AsyncMock(return_value={})
            
            response = client.get("/api/v1/downloads/health")
            
            assert response.status_code == 503
            data = response.json()
            assert data["service"] == "downloads"
            assert data["status"] == "unhealthy"
            assert data["download_manager_running"] is False
            assert data["downloads_directory_exists"] is False
    
    def test_download_health_check_error(self, client):
        """Test health check with error."""
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager.get_stats = AsyncMock(
                side_effect=Exception("Health check error")
            )
            
            response = client.get("/api/v1/downloads/health")
            
            assert response.status_code == 503
            data = response.json()
            assert data["service"] == "downloads"
            assert data["status"] == "unhealthy"
            assert "error" in data


class TestFileAPI:
    """Test file serving API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def temp_downloads_dir(self):
        """Create temporary downloads directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            downloads_dir = Path(temp_dir)
            
            # Create test files
            video_file = downloads_dir / "test_video.mp4"
            audio_file = downloads_dir / "test_audio.mp3"
            
            video_file.write_text("fake video content")
            audio_file.write_text("fake audio content")
            
            # Patch the downloads directory
            with patch('app.api.files.Path') as mock_path:
                mock_path.return_value = downloads_dir
                mock_path.side_effect = lambda x: Path(x) if x != "downloads" else downloads_dir
                yield downloads_dir
    
    def test_download_file_success(self, client, temp_downloads_dir):
        """Test successful file download."""
        with patch('app.api.files.Path') as mock_path:
            mock_path.return_value = temp_downloads_dir
            mock_path.side_effect = lambda x: Path(x) if x != "downloads" else temp_downloads_dir
            
            response = client.get("/downloads/test_video.mp4")
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "video/mp4"
            assert "attachment" in response.headers["content-disposition"]
            assert "test_video.mp4" in response.headers["content-disposition"]
    
    def test_download_file_not_found(self, client, temp_downloads_dir):
        """Test download of non-existent file."""
        with patch('app.api.files.Path') as mock_path:
            mock_path.return_value = temp_downloads_dir
            mock_path.side_effect = lambda x: Path(x) if x != "downloads" else temp_downloads_dir
            
            response = client.get("/downloads/non_existent.mp4")
            
            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "File not found"
    
    def test_download_file_security_check(self, client, temp_downloads_dir):
        """Test security checks for malicious filenames."""
        # Test directory traversal attempt - FastAPI normalizes paths so this returns 404
        # which is actually the correct security behavior
        response = client.get("/downloads/../passwd")
        
        # FastAPI prevents path traversal at routing level, so we get 404
        assert response.status_code == 404
        
        # Test with a filename that contains suspicious characters but is valid for routing
        response2 = client.get("/downloads/test..file")
        assert response2.status_code == 400  # Our security check should catch this
        data = response2.json()
        assert data["detail"] == "Invalid filename"
    
    def test_get_file_info_success(self, client, temp_downloads_dir):
        """Test successful file info retrieval."""
        with patch('app.api.files.Path') as mock_path:
            mock_path.return_value = temp_downloads_dir
            mock_path.side_effect = lambda x: Path(x) if x != "downloads" else temp_downloads_dir
            
            response = client.get("/downloads/info/test_video.mp4")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["filename"] == "test_video.mp4"
            assert data["data"]["content_type"] == "video/mp4"
            assert "size_bytes" in data["data"]
            assert "download_url" in data["data"]
    
    def test_get_file_info_not_found(self, client, temp_downloads_dir):
        """Test file info for non-existent file."""
        with patch('app.api.files.Path') as mock_path:
            mock_path.return_value = temp_downloads_dir
            mock_path.side_effect = lambda x: Path(x) if x != "downloads" else temp_downloads_dir
            
            response = client.get("/downloads/info/non_existent.mp4")
            
            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "File not found"
    
    def test_list_files_success(self, client, temp_downloads_dir):
        """Test successful file listing."""
        with patch('app.api.files.Path') as mock_path:
            mock_path.return_value = temp_downloads_dir
            mock_path.side_effect = lambda x: Path(x) if x != "downloads" else temp_downloads_dir
            
            response = client.get("/downloads/")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["total_count"] == 2
            assert len(data["data"]["files"]) == 2
            
            # Check file names
            filenames = [f["filename"] for f in data["data"]["files"]]
            assert "test_video.mp4" in filenames
            assert "test_audio.mp3" in filenames
    
    def test_list_files_empty_directory(self, client):
        """Test file listing with empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir)
            
            with patch('app.api.files.Path') as mock_path:
                mock_path.return_value = empty_dir
                mock_path.side_effect = lambda x: Path(x) if x != "downloads" else empty_dir
                
                response = client.get("/downloads/")
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["total_count"] == 0
                assert len(data["data"]["files"]) == 0
    
    def test_list_files_no_directory(self, client):
        """Test file listing when downloads directory doesn't exist."""
        with patch('app.api.files.Path') as mock_path:
            non_existent_dir = Path("/non/existent/directory")
            mock_path.return_value = non_existent_dir
            mock_path.side_effect = lambda x: Path(x) if x != "downloads" else non_existent_dir
            
            response = client.get("/downloads/")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["total_count"] == 0
            assert len(data["data"]["files"]) == 0


if __name__ == "__main__":
    pytest.main([__file__])