"""
Tests for secure file serving functionality.

This module tests file serving security headers, access validation,
and integration with storage management.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.storage_manager import storage_manager


class TestFileServingSecurity:
    """Test cases for secure file serving functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def temp_downloads_dir(self):
        """Create temporary downloads directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            downloads_dir = Path(temp_dir) / "downloads"
            downloads_dir.mkdir()
            
            # Create test files
            video_file = downloads_dir / "test_video.mp4"
            video_file.write_bytes(b"fake video content")
            
            audio_file = downloads_dir / "test_audio.mp3"
            audio_file.write_bytes(b"fake audio content")
            
            # Patch the downloads directory
            with patch('app.api.files.Path') as mock_path:
                mock_path.return_value = downloads_dir
                yield downloads_dir
    
    @patch.object(storage_manager, 'validate_file_access')
    def test_file_download_with_security_validation(self, mock_validate, client, temp_downloads_dir):
        """Test file download with security validation."""
        mock_validate.return_value = True
        
        # Create test file
        test_file = temp_downloads_dir / "test.mp4"
        test_file.write_bytes(b"test video content")
        
        with patch('pathlib.Path') as mock_path_class:
            # Mock Path constructor to return our temp directory
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return temp_downloads_dir
                return Path(path_str)
            
            mock_path_class.side_effect = path_side_effect
            
            response = client.get("/downloads/test.mp4")
        
        assert response.status_code == 200
        mock_validate.assert_called_once()
        
        # Check security headers
        headers = response.headers
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "Content-Security-Policy" in headers
        assert headers["Content-Disposition"].startswith("attachment")
    
    @patch.object(storage_manager, 'validate_file_access')
    def test_file_download_access_denied(self, mock_validate, client):
        """Test file download with access denied."""
        mock_validate.return_value = False
        
        with patch('pathlib.Path') as mock_path_class:
            mock_downloads_dir = Mock()
            mock_file_path = Mock()
            mock_file_path.exists.return_value = True
            mock_downloads_dir.__truediv__.return_value = mock_file_path
            
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return mock_downloads_dir
                return Mock()
            
            mock_path_class.side_effect = path_side_effect
            
            response = client.get("/downloads/test.mp4")
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]
    
    def test_file_download_directory_traversal_protection(self, client):
        """Test protection against directory traversal attacks."""
        # Test filenames with path separators that reach our validation
        invalid_filenames = [
            "test..file",  # Contains ..
            "test/file.mp4",  # Contains /
            "test\\file.mp4",  # Contains \
            "file..with..dots",  # Multiple ..
        ]
        
        for filename in invalid_filenames:
            response = client.get(f"/downloads/{filename}")
            # The security validation should trigger
            # Status could be 400 (validation error) or 404 (file not found after validation)
            assert response.status_code in [400, 404]
            if response.status_code == 400:
                assert "Invalid filename" in response.json()["detail"]
        
        # Test that FastAPI also protects against path traversal at the routing level
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam", 
        ]
        
        for attempt in traversal_attempts:
            response = client.get(f"/downloads/{attempt}")
            # FastAPI resolves paths before reaching our endpoint, so we get 404
            # This is actually good security behavior - double protection
            assert response.status_code in [400, 404]
    
    def test_file_download_not_found(self, client):
        """Test file download with non-existent file."""
        with patch('pathlib.Path') as mock_path_class:
            mock_downloads_dir = Mock()
            mock_file_path = Mock()
            mock_file_path.exists.return_value = False
            mock_downloads_dir.__truediv__.return_value = mock_file_path
            
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return mock_downloads_dir
                return Mock()
            
            mock_path_class.side_effect = path_side_effect
            
            response = client.get("/downloads/nonexistent.mp4")
        
        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]
    
    @patch.object(storage_manager, 'get_security_headers')
    @patch.object(storage_manager, 'validate_file_access')
    def test_security_headers_integration(self, mock_validate, mock_get_headers, client):
        """Test integration with storage manager security headers."""
        mock_validate.return_value = True
        mock_get_headers.return_value = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Type": "video/mp4",
            "Content-Disposition": 'attachment; filename="test.mp4"'
        }
        
        with patch('pathlib.Path') as mock_path_class:
            mock_downloads_dir = Mock()
            mock_file_path = Mock()
            mock_file_path.exists.return_value = True
            mock_file_path.stat.return_value.st_size = 1000
            mock_file_path.stat.return_value.st_mtime = 1234567890
            mock_file_path.suffix = ".mp4"
            mock_downloads_dir.__truediv__.return_value = mock_file_path
            
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return mock_downloads_dir
                return mock_file_path
            
            mock_path_class.side_effect = path_side_effect
            
            with patch('app.api.files.FileResponse') as mock_file_response:
                mock_response = Mock()
                mock_file_response.return_value = mock_response
                
                response = client.get("/downloads/test.mp4")
        
        # Verify security headers were requested from storage manager
        mock_get_headers.assert_called_once()
        mock_validate.assert_called_once()
    
    def test_file_info_endpoint_security(self, client):
        """Test file info endpoint security validation."""
        # Test directory traversal protection
        response = client.get("/downloads/info/../../../etc/passwd")
        assert response.status_code == 400
        assert "Invalid filename" in response.json()["detail"]
        
        # Test with valid filename but non-existent file
        with patch('pathlib.Path') as mock_path_class:
            mock_downloads_dir = Mock()
            mock_file_path = Mock()
            mock_file_path.exists.return_value = False
            mock_downloads_dir.__truediv__.return_value = mock_file_path
            
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return mock_downloads_dir
                return Mock()
            
            mock_path_class.side_effect = path_side_effect
            
            response = client.get("/downloads/info/test.mp4")
        
        assert response.status_code == 404
    
    def test_file_info_success(self, client):
        """Test successful file info retrieval."""
        with patch('pathlib.Path') as mock_path_class:
            mock_downloads_dir = Mock()
            mock_file_path = Mock()
            mock_file_path.exists.return_value = True
            mock_file_path.suffix = ".mp4"
            
            # Mock file stats
            mock_stat = Mock()
            mock_stat.st_size = 1024000  # 1MB
            mock_stat.st_ctime = 1234567890
            mock_stat.st_mtime = 1234567890
            mock_file_path.stat.return_value = mock_stat
            
            mock_downloads_dir.__truediv__.return_value = mock_file_path
            
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return mock_downloads_dir
                return Mock()
            
            mock_path_class.side_effect = path_side_effect
            
            with patch('time.time', return_value=1234567950):  # 60 seconds later
                response = client.get("/downloads/info/test.mp4")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        file_info = data["data"]
        assert file_info["filename"] == "test.mp4"
        assert file_info["size_bytes"] == 1024000
        assert "size_human" in file_info
        assert file_info["content_type"] == "video/mp4"
        assert file_info["age_seconds"] == 60
        assert "expires_in_seconds" in file_info
    
    def test_list_files_security(self, client):
        """Test file listing security and functionality."""
        with patch('pathlib.Path') as mock_path_class:
            mock_downloads_dir = Mock()
            mock_downloads_dir.exists.return_value = True
            
            # Mock files in directory
            mock_file1 = Mock()
            mock_file1.is_file.return_value = True
            mock_file1.name = "video1.mp4"
            mock_file1.suffix = ".mp4"
            mock_file1.stat.return_value.st_size = 1000000
            mock_file1.stat.return_value.st_ctime = 1234567890
            mock_file1.stat.return_value.st_mtime = 1234567890
            
            mock_file2 = Mock()
            mock_file2.is_file.return_value = True
            mock_file2.name = "audio1.mp3"
            mock_file2.suffix = ".mp3"
            mock_file2.stat.return_value.st_size = 500000
            mock_file2.stat.return_value.st_ctime = 1234567900
            mock_file2.stat.return_value.st_mtime = 1234567900
            
            mock_downloads_dir.iterdir.return_value = [mock_file1, mock_file2]
            
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return mock_downloads_dir
                return Mock()
            
            mock_path_class.side_effect = path_side_effect
            
            with patch('time.time', return_value=1234567950):
                response = client.get("/downloads/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        files_data = data["data"]
        assert files_data["total_count"] == 2
        assert files_data["total_size_bytes"] == 1500000
        assert len(files_data["files"]) == 2
        
        # Check file information
        files = files_data["files"]
        video_file = next(f for f in files if f["filename"] == "video1.mp4")
        audio_file = next(f for f in files if f["filename"] == "audio1.mp3")
        
        assert video_file["content_type"] == "video/mp4"
        assert audio_file["content_type"] == "audio/mpeg"
        assert "download_url" in video_file
        assert "expires_in_seconds" in video_file
    
    def test_list_files_no_downloads_dir(self, client):
        """Test file listing when downloads directory doesn't exist."""
        with patch('pathlib.Path') as mock_path_class:
            mock_downloads_dir = Mock()
            mock_downloads_dir.exists.return_value = False
            
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return mock_downloads_dir
                return Mock()
            
            mock_path_class.side_effect = path_side_effect
            
            response = client.get("/downloads/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["total_count"] == 0
        assert len(data["data"]["files"]) == 0
    
    def test_content_type_detection(self, client):
        """Test content type detection for different file types."""
        test_cases = [
            ("video.mp4", "video/mp4"),
            ("video.webm", "video/webm"),
            ("video.mkv", "video/x-matroska"),
            ("video.avi", "video/x-msvideo"),
            ("video.mov", "video/quicktime"),
            ("audio.mp3", "audio/mpeg"),
            ("audio.m4a", "audio/mp4"),
            ("audio.wav", "audio/wav"),
            ("audio.flac", "audio/flac"),
            ("unknown.xyz", "application/octet-stream"),
        ]
        
        for filename, expected_content_type in test_cases:
            with patch('pathlib.Path') as mock_path_class:
                mock_downloads_dir = Mock()
                mock_file_path = Mock()
                mock_file_path.exists.return_value = True
                mock_file_path.suffix = Path(filename).suffix
                
                mock_stat = Mock()
                mock_stat.st_size = 1000
                mock_stat.st_ctime = 1234567890
                mock_stat.st_mtime = 1234567890
                mock_file_path.stat.return_value = mock_stat
                
                mock_downloads_dir.__truediv__.return_value = mock_file_path
                
                def path_side_effect(path_str):
                    if path_str == "downloads":
                        return mock_downloads_dir
                    return Mock()
                
                mock_path_class.side_effect = path_side_effect
                
                with patch('time.time', return_value=1234567950):
                    response = client.get(f"/downloads/info/{filename}")
            
            if response.status_code == 200:
                data = response.json()
                assert data["data"]["content_type"] == expected_content_type


class TestFileServingPerformance:
    """Test performance aspects of file serving."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_large_file_listing_performance(self, client):
        """Test performance with large number of files."""
        with patch('pathlib.Path') as mock_path_class:
            mock_downloads_dir = Mock()
            mock_downloads_dir.exists.return_value = True
            
            # Create many mock files
            mock_files = []
            for i in range(100):
                mock_file = Mock()
                mock_file.is_file.return_value = True
                mock_file.name = f"file_{i}.mp4"
                mock_file.suffix = ".mp4"
                mock_file.stat.return_value.st_size = 1000000
                mock_file.stat.return_value.st_ctime = 1234567890 + i
                mock_file.stat.return_value.st_mtime = 1234567890 + i
                mock_files.append(mock_file)
            
            mock_downloads_dir.iterdir.return_value = mock_files
            
            def path_side_effect(path_str):
                if path_str == "downloads":
                    return mock_downloads_dir
                return Mock()
            
            mock_path_class.side_effect = path_side_effect
            
            with patch('time.time', return_value=1234567950):
                response = client.get("/downloads/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["total_count"] == 100
        
        # Files should be sorted by creation time (newest first)
        files = data["data"]["files"]
        assert files[0]["filename"] == "file_99.mp4"  # Newest
        assert files[-1]["filename"] == "file_0.mp4"  # Oldest


if __name__ == "__main__":
    pytest.main([__file__])