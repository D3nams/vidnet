"""
Integration tests for complete download workflows.

Tests end-to-end download workflows from API request to file serving,
including video downloads, audio extraction, and file cleanup.
"""

import pytest
import asyncio
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.video import DownloadRequest, VideoMetadata, VideoQuality
from app.services.download_manager import download_manager


class TestCompleteDownloadWorkflows:
    """Integration tests for complete download workflows."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def temp_downloads_dir(self):
        """Create temporary downloads directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            downloads_dir = Path(temp_dir) / "downloads"
            downloads_dir.mkdir()
            
            # Patch the downloads directory in download manager
            with patch.object(download_manager, 'downloads_dir', downloads_dir):
                yield downloads_dir
    
    @pytest.fixture
    def mock_video_metadata(self):
        """Mock video metadata for testing."""
        return VideoMetadata(
            title="Test Video for Download",
            thumbnail="https://example.com/thumb.jpg",
            duration=300,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=1024000, fps=30),
                VideoQuality(quality="1080p", format="mp4", filesize=2048000, fps=30)
            ],
            audio_available=True,
            original_url="https://youtube.com/watch?v=test123"
        )
    
    @pytest.fixture
    def mock_audio_metadata(self):
        """Mock video metadata for audio extraction testing."""
        return VideoMetadata(
            title="Test Audio for Extraction",
            thumbnail="https://example.com/thumb.jpg",
            duration=240,
            platform="youtube",
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=1024000, fps=30)
            ],
            audio_available=True,
            original_url="https://youtube.com/watch?v=audio123"
        )
    
    @pytest.mark.asyncio
    async def test_complete_video_download_workflow(self, client, temp_downloads_dir, mock_video_metadata):
        """Test complete video download workflow from API request to file serving."""
        
        # Mock file creation for download
        def mock_download_with_ytdlp(url, opts):
            fake_file = temp_downloads_dir / "test_video_123.mp4"
            fake_file.write_text("fake video content for testing")
            return str(fake_file)
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract, \
             patch.object(download_manager, '_download_with_ytdlp', side_effect=mock_download_with_ytdlp), \
             patch('app.services.download_manager.cache_manager') as mock_cache, \
             patch('app.api.files.Path') as mock_files_path:
            
            mock_extract.return_value = mock_video_metadata
            mock_cache.track_download = AsyncMock(return_value=True)
            mock_cache.get_download_status = AsyncMock(return_value=None)
            
            # Mock file serving to use the same temp directory
            mock_files_path.side_effect = lambda x: temp_downloads_dir if x == "downloads" else Path(x)
            
            # Create a fresh download manager for this test
            test_manager = download_manager.__class__(max_concurrent_downloads=1)
            test_manager.downloads_dir = temp_downloads_dir
            
            # Patch the global download manager
            with patch('app.api.downloads.download_manager', test_manager):
                await test_manager.start()
                
                try:
                    # Step 1: Submit download request
                    download_request = {
                        "url": "https://youtube.com/watch?v=test123",
                        "quality": "720p",
                        "format": "video"
                    }
                    
                    response = client.post("/api/v1/download", json=download_request)
                    assert response.status_code == 200
                    
                    data = response.json()
                    assert data["success"] is True
                    task_id = data["data"]["task_id"]
                    assert data["data"]["status"] == "pending"
                    
                    # Step 2: Poll for completion
                    max_wait = 15  # seconds
                    start_time = time.time()
                    final_status = None
                    
                    while time.time() - start_time < max_wait:
                        status_response = client.get(f"/api/v1/status/{task_id}")
                        assert status_response.status_code == 200
                        
                        status_data = status_response.json()
                        assert status_data["success"] is True
                        
                        final_status = status_data["data"]
                        if final_status["status"] in ["completed", "failed"]:
                            break
                        
                        await asyncio.sleep(0.5)
                    
                    # Step 3: Verify completion
                    assert final_status is not None
                    assert final_status["status"] == "completed"
                    assert final_status["progress"] == 100
                    assert final_status["download_url"] is not None
                    
                    # Step 4: Test file serving
                    filename = final_status["download_url"].split("/")[-1]
                    file_response = client.get(f"/downloads/{filename}")
                    
                    assert file_response.status_code == 200
                    assert file_response.headers["content-type"] == "video/mp4"
                    assert "attachment" in file_response.headers["content-disposition"]
                    assert filename in file_response.headers["content-disposition"]
                    
                    # Step 5: Test file info endpoint
                    info_response = client.get(f"/downloads/info/{filename}")
                    assert info_response.status_code == 200
                    
                    info_data = info_response.json()
                    assert info_data["success"] is True
                    assert info_data["data"]["filename"] == filename
                    assert info_data["data"]["content_type"] == "video/mp4"
                    assert info_data["data"]["size_bytes"] > 0
                    
                    # Step 6: Test file listing
                    list_response = client.get("/downloads/")
                    assert list_response.status_code == 200
                    
                    list_data = list_response.json()
                    assert list_data["success"] is True
                    assert list_data["data"]["total_count"] >= 1
                    
                    filenames = [f["filename"] for f in list_data["data"]["files"]]
                    assert filename in filenames
                    
                finally:
                    # Cleanup
                    await test_manager.stop()
    
    @pytest.mark.asyncio
    async def test_complete_audio_extraction_workflow(self, client, temp_downloads_dir, mock_audio_metadata):
        """Test complete audio extraction workflow from API request to file serving."""
        
        # Mock audio extraction result
        def mock_extract_audio(video_url, quality, output_path):
            fake_file = Path(output_path)
            fake_file.write_text("fake audio content for testing")
            
            return {
                'success': True,
                'output_path': str(fake_file),
                'file_size': fake_file.stat().st_size,
                'quality': quality,
                'duration': 240,
                'title': 'Test Audio for Extraction',
                'platform': 'youtube',
                'original_url': video_url,
                'extraction_details': {'ffmpeg_returncode': 0}
            }
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract, \
             patch.object(download_manager.audio_extractor, 'extract_audio', side_effect=mock_extract_audio), \
             patch('app.services.download_manager.cache_manager') as mock_cache, \
             patch('app.api.files.Path') as mock_files_path:
            
            mock_extract.return_value = mock_audio_metadata
            mock_cache.track_download = AsyncMock(return_value=True)
            mock_cache.get_download_status = AsyncMock(return_value=None)
            
            # Mock file serving to use the same temp directory
            mock_files_path.side_effect = lambda x: temp_downloads_dir if x == "downloads" else Path(x)
            
            # Create a fresh download manager for this test
            test_manager = download_manager.__class__(max_concurrent_downloads=1)
            test_manager.downloads_dir = temp_downloads_dir
            
            # Patch the global download manager
            with patch('app.api.downloads.download_manager', test_manager):
                await test_manager.start()
                
                try:
                    # Step 1: Submit audio extraction request
                    audio_request = {
                        "url": "https://youtube.com/watch?v=audio123",
                        "quality": "720p",
                        "format": "audio",
                        "audio_quality": "128kbps"
                    }
                    
                    response = client.post("/api/v1/extract-audio", json=audio_request)
                    assert response.status_code == 200
                    
                    data = response.json()
                    assert data["success"] is True
                    task_id = data["data"]["task_id"]
                    assert data["data"]["status"] == "pending"
                    
                    # Step 2: Poll for completion
                    max_wait = 15  # seconds
                    start_time = time.time()
                    final_status = None
                    
                    while time.time() - start_time < max_wait:
                        status_response = client.get(f"/api/v1/status/{task_id}")
                        assert status_response.status_code == 200
                        
                        status_data = status_response.json()
                        assert status_data["success"] is True
                        
                        final_status = status_data["data"]
                        if final_status["status"] in ["completed", "failed"]:
                            break
                        
                        await asyncio.sleep(0.5)
                    
                    # Step 3: Verify completion
                    assert final_status is not None
                    assert final_status["status"] == "completed"
                    assert final_status["progress"] == 100
                    assert final_status["download_url"] is not None
                    
                    # Step 4: Test file serving
                    filename = final_status["download_url"].split("/")[-1]
                    file_response = client.get(f"/downloads/{filename}")
                    
                    assert file_response.status_code == 200
                    assert file_response.headers["content-type"] == "audio/mpeg"
                    assert "attachment" in file_response.headers["content-disposition"]
                    assert filename in file_response.headers["content-disposition"]
                    
                    # Step 5: Test file info endpoint
                    info_response = client.get(f"/downloads/info/{filename}")
                    assert info_response.status_code == 200
                    
                    info_data = info_response.json()
                    assert info_data["success"] is True
                    assert info_data["data"]["filename"] == filename
                    assert info_data["data"]["content_type"] == "audio/mpeg"
                    assert info_data["data"]["size_bytes"] > 0
                    
                finally:
                    # Cleanup
                    await test_manager.stop()
    
    @pytest.mark.asyncio
    async def test_download_cancellation_workflow(self, client, temp_downloads_dir, mock_video_metadata):
        """Test download cancellation workflow."""
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract, \
             patch('app.services.download_manager.cache_manager') as mock_cache:
            
            mock_extract.return_value = mock_video_metadata
            mock_cache.track_download = AsyncMock(return_value=True)
            mock_cache.get_download_status = AsyncMock(return_value=None)
            
            # Ensure download manager is started
            if not download_manager._running:
                await download_manager.start()
            
            try:
                # Step 1: Submit download request
                download_request = {
                    "url": "https://youtube.com/watch?v=test123",
                    "quality": "720p",
                    "format": "video"
                }
                
                response = client.post("/api/v1/download", json=download_request)
                assert response.status_code == 200
                
                data = response.json()
                task_id = data["data"]["task_id"]
                
                # Step 2: Cancel the download
                cancel_response = client.delete(f"/api/v1/cancel/{task_id}")
                assert cancel_response.status_code == 200
                
                cancel_data = cancel_response.json()
                assert cancel_data["success"] is True
                assert "cancelled successfully" in cancel_data["message"]
                
                # Step 3: Verify status shows failed
                status_response = client.get(f"/api/v1/status/{task_id}")
                assert status_response.status_code == 200
                
                status_data = status_response.json()
                final_status = status_data["data"]
                assert final_status["status"] == "failed"
                assert "cancelled by user" in final_status["error_message"]
                
            finally:
                # Cleanup
                if download_manager._running:
                    await download_manager.stop()
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, client, temp_downloads_dir):
        """Test error handling in download workflow."""
        
        # Mock video processor to raise an error
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract:
            mock_extract.side_effect = Exception("Video not found")
            
            # Step 1: Submit request that will fail validation
            download_request = {
                "url": "https://youtube.com/watch?v=invalid",
                "quality": "720p",
                "format": "video"
            }
            
            response = client.post("/api/v1/download", json=download_request)
            assert response.status_code == 400
            
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "download_error"
            assert "Video not found" in data["message"]
    
    @pytest.mark.asyncio
    async def test_invalid_request_validation(self, client):
        """Test validation of invalid requests."""
        
        # Test empty URL
        invalid_request = {
            "url": "",
            "quality": "720p",
            "format": "video"
        }
        
        response = client.post("/api/v1/download", json=invalid_request)
        assert response.status_code == 422
        
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "validation_error"
        
        # Test invalid quality
        invalid_quality_request = {
            "url": "https://youtube.com/watch?v=test",
            "quality": "999p",
            "format": "video"
        }
        
        response = client.post("/api/v1/download", json=invalid_quality_request)
        assert response.status_code == 422
        
        # Test audio extraction without audio quality (should succeed with default)
        valid_audio_request = {
            "url": "https://youtube.com/watch?v=validtest123456",
            "quality": "720p",
            "format": "audio"
            # Missing audio_quality - should get default
        }
        
        # Mock the validation to avoid yt-dlp issues
        with patch('app.api.downloads.download_manager') as mock_manager:
            mock_manager._running = True
            mock_manager.start = AsyncMock()
            mock_manager.submit_download = AsyncMock(return_value="test-task-id")
            
            response = client.post("/api/v1/extract-audio", json=valid_audio_request)
            assert response.status_code == 200  # Should succeed with default quality
            
            # Verify that default audio quality was set
            call_args = mock_manager.submit_download.call_args[0][0]
            assert call_args.audio_quality == "128kbps"
        
        # Test with invalid URL format
        invalid_url_request = {
            "url": "not-a-url",
            "quality": "720p",
            "format": "audio",
            "audio_quality": "128kbps"
        }
        
        response = client.post("/api/v1/extract-audio", json=invalid_url_request)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_download_stats_and_health_workflow(self, client):
        """Test download statistics and health check endpoints."""
        
        # Test download stats
        stats_response = client.get("/api/v1/downloads/stats")
        assert stats_response.status_code == 200
        
        stats_data = stats_response.json()
        assert stats_data["success"] is True
        assert "data" in stats_data
        assert "timestamp" in stats_data
        
        # Test health check
        health_response = client.get("/api/v1/downloads/health")
        # Status code can be 200 or 503 depending on service state
        assert health_response.status_code in [200, 503]
        
        health_data = health_response.json()
        assert health_data["service"] == "downloads"
        assert "status" in health_data
        assert "timestamp" in health_data
    
    @pytest.mark.asyncio
    async def test_file_security_workflow(self, client, temp_downloads_dir):
        """Test file serving security measures."""
        
        # Create a test file
        test_file = temp_downloads_dir / "test_security.mp4"
        test_file.write_text("test content")
        
        with patch('app.api.files.Path') as mock_path:
            mock_path.return_value = temp_downloads_dir
            mock_path.side_effect = lambda x: Path(x) if x != "downloads" else temp_downloads_dir
            
            # Test normal file access
            response = client.get("/downloads/test_security.mp4")
            assert response.status_code == 200
            
            # Test directory traversal attempt
            response = client.get("/downloads/test..file")
            assert response.status_code == 400
            
            # Test non-existent file
            response = client.get("/downloads/nonexistent.mp4")
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_concurrent_downloads_workflow(self, client, temp_downloads_dir, mock_video_metadata):
        """Test handling of concurrent download requests."""
        
        # Mock file creation for downloads
        def mock_download_with_ytdlp(url, opts):
            # Create unique files for each request
            import uuid
            fake_file = temp_downloads_dir / f"concurrent_video_{uuid.uuid4().hex[:8]}.mp4"
            fake_file.write_text("fake video content for concurrent test")
            return str(fake_file)
        
        with patch.object(download_manager.video_processor, 'extract_metadata') as mock_extract, \
             patch.object(download_manager, '_download_with_ytdlp', side_effect=mock_download_with_ytdlp), \
             patch('app.services.download_manager.cache_manager') as mock_cache:
            
            mock_extract.return_value = mock_video_metadata
            mock_cache.track_download = AsyncMock(return_value=True)
            mock_cache.get_download_status = AsyncMock(return_value=None)
            
            # Create a fresh download manager for this test
            test_manager = download_manager.__class__(max_concurrent_downloads=3)
            test_manager.downloads_dir = temp_downloads_dir
            
            # Patch the global download manager
            with patch('app.api.downloads.download_manager', test_manager):
                await test_manager.start()
                
                try:
                    # Submit multiple concurrent requests
                    task_ids = []
                    for i in range(3):
                        download_request = {
                            "url": f"https://youtube.com/watch?v=concurrent{i}",
                            "quality": "720p",
                            "format": "video"
                        }
                        
                        response = client.post("/api/v1/download", json=download_request)
                        assert response.status_code == 200
                        
                        data = response.json()
                        task_ids.append(data["data"]["task_id"])
                    
                    # Wait for all to complete
                    max_wait = 20  # seconds
                    start_time = time.time()
                    completed_tasks = 0
                    
                    while time.time() - start_time < max_wait and completed_tasks < len(task_ids):
                        completed_tasks = 0
                        
                        for task_id in task_ids:
                            status_response = client.get(f"/api/v1/status/{task_id}")
                            if status_response.status_code == 200:
                                status_data = status_response.json()
                                if status_data["data"]["status"] in ["completed", "failed"]:
                                    completed_tasks += 1
                        
                        await asyncio.sleep(0.5)
                    
                    # Verify all tasks completed
                    assert completed_tasks == len(task_ids)
                    
                    # Check download stats
                    stats_response = client.get("/api/v1/downloads/stats")
                    assert stats_response.status_code == 200
                    
                    stats_data = stats_response.json()
                    assert stats_data["data"]["total_tasks"] >= len(task_ids)
                    
                finally:
                    # Cleanup
                    await test_manager.stop()


if __name__ == "__main__":
    pytest.main([__file__])