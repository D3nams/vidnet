"""
Tests for storage management API endpoints.

This module tests the REST API endpoints for storage monitoring,
cleanup operations, and backup/recovery management.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.storage_manager import storage_manager, StorageStats
from app.core.exceptions import StorageError


class TestStorageAPI:
    """Test cases for storage management API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_storage_stats(self):
        """Mock storage statistics."""
        return StorageStats(
            total_size=1024 * 1024,  # 1MB
            file_count=10,
            oldest_file_age=3600,  # 1 hour
            newest_file_age=60,    # 1 minute
            average_file_size=102400,  # 100KB
            quota_usage_percent=75.5,
            status="warning"
        )
    
    @patch.object(storage_manager, 'get_storage_stats')
    def test_get_storage_stats_success(self, mock_get_stats, client, mock_storage_stats):
        """Test successful storage stats retrieval."""
        mock_get_stats.return_value = mock_storage_stats
        
        response = client.get("/api/v1/storage/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        stats_data = data["data"]
        assert stats_data["total_size"] == 1024 * 1024
        assert stats_data["file_count"] == 10
        assert stats_data["quota_usage_percent"] == 75.5
        assert stats_data["status"] == "warning"
        assert "total_size_human" in stats_data
        assert "quota_config" in stats_data
    
    @patch.object(storage_manager, 'get_storage_stats')
    def test_get_storage_stats_error(self, mock_get_stats, client):
        """Test storage stats retrieval error handling."""
        mock_get_stats.side_effect = StorageError("Storage unavailable")
        
        response = client.get("/api/v1/storage/stats")
        
        assert response.status_code == 500
        assert "Failed to get storage statistics" in response.json()["detail"]
    
    def test_trigger_cleanup_success(self, client):
        """Test successful cleanup trigger."""
        response = client.post("/api/v1/storage/cleanup")
        
        assert response.status_code == 202
        data = response.json()
        
        assert data["success"] is True
        assert "Cleanup operation started" in data["message"]
        assert data["aggressive_mode"] is False
    
    def test_trigger_cleanup_aggressive(self, client):
        """Test aggressive cleanup trigger."""
        response = client.post("/api/v1/storage/cleanup?aggressive=true")
        
        assert response.status_code == 202
        data = response.json()
        
        assert data["success"] is True
        assert data["aggressive_mode"] is True
    
    @patch.object(storage_manager, 'get_storage_stats')
    def test_get_cleanup_status(self, mock_get_stats, client, mock_storage_stats):
        """Test cleanup status retrieval."""
        mock_get_stats.return_value = mock_storage_stats
        
        response = client.get("/api/v1/storage/cleanup/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        
        status_data = data["data"]
        assert "current_status" in status_data
        assert "quota_usage_percent" in status_data
        assert "cleanup_interval_seconds" in status_data
    
    def test_create_backup_success(self, client):
        """Test successful backup creation trigger."""
        response = client.post("/api/v1/storage/backup")
        
        assert response.status_code == 202
        data = response.json()
        
        assert data["success"] is True
        assert "Backup operation started" in data["message"]
    
    def test_list_backups_success(self, client):
        """Test successful backup listing."""
        # This test will work with the actual backup directory
        # If no backups exist, it should return an empty list
        response = client.get("/api/v1/storage/backups")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "total_count" in data["data"]
        assert "backups" in data["data"]
        assert isinstance(data["data"]["backups"], list)
    
    @patch('pathlib.Path.exists')
    def test_list_backups_no_backup_dir(self, mock_exists, client):
        """Test backup listing when backup directory doesn't exist."""
        mock_exists.return_value = False
        
        response = client.get("/api/v1/storage/backups")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["total_count"] == 0
        assert len(data["data"]["backups"]) == 0
    
    @patch.object(storage_manager.backup_dir, '__truediv__')
    def test_restore_backup_success(self, mock_truediv, client):
        """Test successful backup restoration trigger."""
        # Mock backup path exists
        mock_backup_path = Mock()
        mock_backup_path.exists.return_value = True
        mock_truediv.return_value = mock_backup_path
        
        response = client.post("/api/v1/storage/restore/vidnet_backup_20240101_120000")
        
        assert response.status_code == 202
        data = response.json()
        
        assert data["success"] is True
        assert "Restore operation" in data["message"]
        assert data["backup_name"] == "vidnet_backup_20240101_120000"
    
    @patch.object(storage_manager.backup_dir, '__truediv__')
    def test_restore_backup_not_found(self, mock_truediv, client):
        """Test backup restoration with non-existent backup."""
        # Mock backup path doesn't exist
        mock_backup_path = Mock()
        mock_backup_path.exists.return_value = False
        mock_truediv.return_value = mock_backup_path
        
        response = client.post("/api/v1/storage/restore/nonexistent_backup")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch.object(storage_manager, 'get_storage_stats')
    @patch('os.access')
    @patch('pathlib.Path.exists')
    def test_storage_health_check_healthy(self, mock_path_exists, mock_access, mock_get_stats, client, mock_storage_stats):
        """Test storage health check with healthy status."""
        # Set healthy status
        mock_storage_stats.status = "healthy"
        mock_storage_stats.oldest_file_age = 1800  # 30 minutes
        mock_get_stats.return_value = mock_storage_stats
        
        # Mock directory access and existence
        mock_access.return_value = True
        mock_path_exists.return_value = True
        
        response = client.get("/api/v1/storage/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"
        assert len(data["data"]["issues"]) == 0
        assert "storage_stats" in data["data"]
        assert "directories" in data["data"]
        assert "cleanup_status" in data["data"]
    
    @patch.object(storage_manager, 'get_storage_stats')
    def test_storage_health_check_critical(self, mock_get_stats, client, mock_storage_stats):
        """Test storage health check with critical status."""
        # Set critical status
        mock_storage_stats.status = "critical"
        mock_storage_stats.quota_usage_percent = 95.0
        mock_get_stats.return_value = mock_storage_stats
        
        with patch('os.access', return_value=True), \
             patch.object(storage_manager.downloads_dir, 'exists', return_value=True), \
             patch.object(storage_manager.temp_dir, 'exists', return_value=True), \
             patch.object(storage_manager.logs_dir, 'exists', return_value=True), \
             patch.object(storage_manager.backup_dir, 'exists', return_value=True):
            
            response = client.get("/api/v1/storage/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["status"] == "critical"
        assert len(data["data"]["issues"]) > 0
        assert "Storage usage critical" in str(data["data"]["issues"])
    
    @patch.object(storage_manager, 'get_storage_stats')
    @patch('pathlib.Path.exists')
    @patch('os.access')
    def test_storage_health_check_directory_issues(self, mock_access, mock_path_exists, mock_get_stats, client, mock_storage_stats):
        """Test storage health check with directory access issues."""
        mock_get_stats.return_value = mock_storage_stats
        
        # Mock directory access issues
        mock_path_exists.return_value = False
        mock_access.return_value = False
        
        response = client.get("/api/v1/storage/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["status"] == "critical"
        assert len(data["data"]["issues"]) > 0
        
        # Check directory status
        directories = data["data"]["directories"]
        assert "downloads" in directories
        assert directories["downloads"]["exists"] is False
    
    @patch.object(storage_manager, 'get_storage_stats')
    def test_storage_health_check_error(self, mock_get_stats, client):
        """Test storage health check error handling."""
        mock_get_stats.side_effect = Exception("Storage system error")
        
        response = client.get("/api/v1/storage/health")
        
        assert response.status_code == 500
        assert "Storage health check failed" in response.json()["detail"]


class TestStorageAPIBackgroundTasks:
    """Test background task functionality in storage API."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @patch('app.api.storage._background_cleanup')
    def test_background_cleanup_task(self, mock_cleanup, client):
        """Test that cleanup triggers background task."""
        mock_cleanup.return_value = AsyncMock()
        
        response = client.post("/api/v1/storage/cleanup")
        
        assert response.status_code == 202
        # Note: In real tests, we'd need to wait for background task completion
        # or use a different testing approach for background tasks
    
    @patch('app.api.storage._background_backup')
    def test_background_backup_task(self, mock_backup, client):
        """Test that backup triggers background task."""
        mock_backup.return_value = AsyncMock()
        
        response = client.post("/api/v1/storage/backup")
        
        assert response.status_code == 202
    
    @patch('app.api.storage._background_restore')
    @patch.object(storage_manager.backup_dir, '__truediv__')
    def test_background_restore_task(self, mock_truediv, mock_restore, client):
        """Test that restore triggers background task."""
        # Mock backup exists
        mock_backup_path = Mock()
        mock_backup_path.exists.return_value = True
        mock_truediv.return_value = mock_backup_path
        
        mock_restore.return_value = AsyncMock()
        
        response = client.post("/api/v1/storage/restore/test_backup")
        
        assert response.status_code == 202


class TestStorageAPIValidation:
    """Test input validation and error handling in storage API."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_cleanup_with_invalid_aggressive_param(self, client):
        """Test cleanup with invalid aggressive parameter."""
        # FastAPI should handle boolean conversion automatically
        response = client.post("/api/v1/storage/cleanup?aggressive=invalid")
        
        # Should still work as FastAPI converts to False for invalid boolean
        assert response.status_code == 202
    
    def test_restore_with_empty_backup_name(self, client):
        """Test restore with empty backup name."""
        response = client.post("/api/v1/storage/restore/")
        
        # Should return 404 for empty path
        assert response.status_code in [404, 405]  # Method not allowed or not found
    
    def test_restore_with_invalid_backup_name(self, client):
        """Test restore with invalid backup name characters."""
        with patch.object(storage_manager.backup_dir, '__truediv__') as mock_truediv:
            mock_backup_path = Mock()
            mock_backup_path.exists.return_value = False
            mock_truediv.return_value = mock_backup_path
            
            response = client.post("/api/v1/storage/restore/invalid../backup")
            
            assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__])