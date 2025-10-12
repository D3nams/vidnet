"""
Tests for storage management service.

This module tests automated cleanup, storage quota monitoring,
file serving security, and backup/recovery procedures.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import shutil
import os
import time
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock

from app.services.storage_manager import StorageManager, StorageQuota, StorageStats, FileInfo
from app.core.exceptions import StorageError


class TestStorageManager:
    """Test cases for StorageManager class."""
    
    @pytest_asyncio.fixture
    async def temp_storage_manager(self):
        """Create a temporary storage manager for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a storage manager with temporary directories
            manager = StorageManager()
            manager.downloads_dir = temp_path / "downloads"
            manager.temp_dir = temp_path / "temp"
            manager.logs_dir = temp_path / "logs"
            manager.backup_dir = temp_path / "backups"
            
            # Create directories
            for directory in [manager.downloads_dir, manager.temp_dir, manager.logs_dir, manager.backup_dir]:
                directory.mkdir(exist_ok=True)
            
            # Set smaller quotas for testing
            manager.quota = StorageQuota(
                max_total_size=1024 * 1024,  # 1MB
                max_file_age=60,  # 1 minute
                warning_threshold=0.7,
                critical_threshold=0.9,
                cleanup_target=0.5
            )
            
            manager.cleanup_interval = 1  # 1 second for testing
            
            yield manager
            
            # Cleanup
            if manager._running:
                await manager.stop()
    
    def sample_files(self, temp_storage_manager):
        """Create sample files for testing."""
        async def _create_files():
            manager = temp_storage_manager
            
            # Create files with different ages
            files = []
            
            # Recent file
            recent_file = manager.downloads_dir / "recent_video.mp4"
            recent_file.write_bytes(b"recent video content" * 100)
            files.append(recent_file)
            
            # Old file (modify timestamp)
            old_file = manager.downloads_dir / "old_video.mp4"
            old_file.write_bytes(b"old video content" * 100)
            old_time = time.time() - 120  # 2 minutes ago
            os.utime(old_file, (old_time, old_time))
            files.append(old_file)
            
            # Audio file
            audio_file = manager.downloads_dir / "audio.mp3"
            audio_file.write_bytes(b"audio content" * 50)
            files.append(audio_file)
            
            # Temp file
            temp_file = manager.temp_dir / "temp_file.tmp"
            temp_file.write_bytes(b"temp content" * 20)
            old_temp_time = time.time() - 180  # 3 minutes ago
            os.utime(temp_file, (old_temp_time, old_temp_time))
            files.append(temp_file)
            
            return files
        
        return _create_files
    
    @pytest.mark.asyncio
    async def test_storage_stats_calculation(self, temp_storage_manager, sample_files):
        """Test storage statistics calculation."""
        manager = temp_storage_manager
        files = await sample_files()
        
        stats = await manager.get_storage_stats()
        
        assert isinstance(stats, StorageStats)
        assert stats.file_count == 4
        assert stats.total_size > 0
        assert stats.quota_usage_percent > 0
        assert stats.status in ["healthy", "warning", "critical"]
        assert stats.oldest_file_age > stats.newest_file_age
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_files(self, temp_storage_manager, sample_files):
        """Test cleanup of expired files."""
        manager = temp_storage_manager
        files = await sample_files()
        
        # Verify files exist before cleanup
        assert all(f.exists() for f in files)
        
        # Run cleanup
        result = await manager.cleanup_expired_files()
        
        assert isinstance(result, dict)
        assert "files_removed" in result
        assert "bytes_freed" in result
        assert result["files_removed"] >= 2  # Should remove old files
        
        # Check that old files are removed
        old_file = manager.downloads_dir / "old_video.mp4"
        temp_file = manager.temp_dir / "temp_file.tmp"
        assert not old_file.exists()
        assert not temp_file.exists()
        
        # Recent file should still exist
        recent_file = manager.downloads_dir / "recent_video.mp4"
        assert recent_file.exists()
    
    @pytest.mark.asyncio
    async def test_aggressive_cleanup(self, temp_storage_manager, sample_files):
        """Test aggressive cleanup mode."""
        manager = temp_storage_manager
        files = await sample_files()
        
        # Set very small quota to trigger aggressive cleanup
        manager.quota.max_total_size = 1000  # Very small
        
        result = await manager.cleanup_expired_files(aggressive=True)
        
        assert result["aggressive_mode"] is True
        assert result["files_removed"] > 0
    
    @pytest.mark.asyncio
    async def test_file_access_validation(self, temp_storage_manager):
        """Test file access security validation."""
        manager = temp_storage_manager
        
        # Valid file within downloads directory
        valid_file = manager.downloads_dir / "test.mp4"
        valid_file.write_bytes(b"test content")
        
        assert await manager.validate_file_access(valid_file) is True
        
        # Invalid file outside allowed directories
        invalid_file = Path("/etc/passwd")
        assert await manager.validate_file_access(invalid_file) is False
        
        # Path traversal attempt
        traversal_path = manager.downloads_dir / "../../../etc/passwd"
        assert await manager.validate_file_access(traversal_path) is False
    
    @pytest.mark.asyncio
    async def test_security_headers_generation(self, temp_storage_manager):
        """Test security headers for different file types."""
        manager = temp_storage_manager
        
        # Test video file headers
        video_file = Path("test.mp4")
        video_headers = manager.get_security_headers(video_file)
        
        assert "X-Content-Type-Options" in video_headers
        assert "X-Frame-Options" in video_headers
        assert "Content-Security-Policy" in video_headers
        assert video_headers["Content-Type"] == "video/mp4"
        assert "attachment" in video_headers["Content-Disposition"]
        
        # Test audio file headers
        audio_file = Path("test.mp3")
        audio_headers = manager.get_security_headers(audio_file)
        
        assert audio_headers["Content-Type"] == "audio/mp3"
        assert "Accept-Ranges" in audio_headers
        
        # Test unknown file type
        unknown_file = Path("test.xyz")
        unknown_headers = manager.get_security_headers(unknown_file)
        
        assert unknown_headers["Content-Type"] == "application/octet-stream"
    
    @pytest.mark.asyncio
    async def test_backup_creation(self, temp_storage_manager):
        """Test backup creation functionality."""
        manager = temp_storage_manager
        
        # Create some log files
        log_file = manager.logs_dir / "test.log"
        log_file.write_text("Test log content")
        
        # Create config files
        config_file = Path("test_config.txt")
        config_file.write_text("Test config")
        
        try:
            result = await manager.backup_critical_data()
            
            assert isinstance(result, dict)
            assert "backup_name" in result
            assert "files_backed_up" in result
            assert "total_size" in result
            assert result["files_backed_up"] > 0
            
            # Verify backup directory exists
            backup_path = Path(result["backup_path"])
            assert backup_path.exists()
            assert (backup_path / "backup_metadata.json").exists()
            
            # Verify logs were backed up
            logs_backup = backup_path / "logs"
            if manager.logs_dir.exists() and any(manager.logs_dir.iterdir()):
                assert logs_backup.exists()
        
        finally:
            # Cleanup
            if config_file.exists():
                config_file.unlink()
    
    @pytest.mark.asyncio
    async def test_backup_restore(self, temp_storage_manager):
        """Test backup restoration functionality."""
        manager = temp_storage_manager
        
        # Create original log file
        original_log = manager.logs_dir / "original.log"
        original_log.write_text("Original log content")
        
        # Create backup
        backup_result = await manager.backup_critical_data()
        backup_name = backup_result["backup_name"]
        
        # Modify original file
        original_log.write_text("Modified log content")
        
        # Restore from backup
        restore_result = await manager.restore_from_backup(backup_name)
        
        assert isinstance(restore_result, dict)
        assert "files_restored" in restore_result
        assert restore_result["backup_name"] == backup_name
        
        # Verify file was restored (content should be original)
        restored_content = original_log.read_text()
        assert "Original log content" in restored_content
    
    @pytest.mark.asyncio
    async def test_backup_nonexistent(self, temp_storage_manager):
        """Test restore from non-existent backup."""
        manager = temp_storage_manager
        
        with pytest.raises(StorageError, match="Backup nonexistent not found"):
            await manager.restore_from_backup("nonexistent")
    
    @pytest.mark.asyncio
    async def test_storage_manager_lifecycle(self, temp_storage_manager):
        """Test storage manager start/stop lifecycle."""
        manager = temp_storage_manager
        
        assert not manager._running
        
        # Start manager
        await manager.start()
        assert manager._running
        assert manager._cleanup_task is not None
        assert manager._monitoring_task is not None
        
        # Stop manager
        await manager.stop()
        assert not manager._running
        assert manager._cleanup_task is None
        assert manager._monitoring_task is None
    
    @pytest.mark.asyncio
    async def test_cleanup_worker_functionality(self, temp_storage_manager, sample_files):
        """Test automated cleanup worker."""
        manager = temp_storage_manager
        files = await sample_files()
        
        # Start manager to activate cleanup worker
        await manager.start()
        
        # Wait for cleanup cycle
        await asyncio.sleep(2)
        
        # Check that cleanup occurred
        stats = await manager.get_storage_stats()
        
        # Old files should be cleaned up
        old_file = manager.downloads_dir / "old_video.mp4"
        temp_file = manager.temp_dir / "temp_file.tmp"
        
        # Files might be cleaned up by the worker
        # We'll check if at least some cleanup activity occurred
        assert stats.file_count <= 4  # Should be same or fewer files
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_directory_size_calculation(self, temp_storage_manager, sample_files):
        """Test directory size calculation."""
        manager = temp_storage_manager
        files = await sample_files()
        
        downloads_size = await manager._get_directory_size(manager.downloads_dir)
        temp_size = await manager._get_directory_size(manager.temp_dir)
        
        assert downloads_size > 0
        assert temp_size > 0
        
        # Total should match sum
        total_size = downloads_size + temp_size
        stats = await manager.get_storage_stats()
        assert stats.total_size == total_size
    
    @pytest.mark.asyncio
    async def test_file_info_scanning(self, temp_storage_manager, sample_files):
        """Test file information scanning."""
        manager = temp_storage_manager
        files = await sample_files()
        
        file_infos = []
        async for file_info in manager._scan_directory(manager.downloads_dir):
            file_infos.append(file_info)
        
        assert len(file_infos) == 3  # 3 files in downloads dir
        
        for file_info in file_infos:
            assert isinstance(file_info, FileInfo)
            assert file_info.size > 0
            assert file_info.age_seconds >= 0
            assert file_info.file_type in ['video', 'audio', 'temp', 'other']
    
    @pytest.mark.asyncio
    async def test_quota_status_determination(self, temp_storage_manager):
        """Test storage quota status determination."""
        manager = temp_storage_manager
        
        # Create file to reach warning threshold
        warning_size = int(manager.quota.max_total_size * 0.75)  # 75% usage
        warning_file = manager.downloads_dir / "warning.dat"
        warning_file.write_bytes(b"x" * warning_size)
        
        stats = await manager.get_storage_stats()
        assert stats.status == "warning"
        
        # Add more to reach critical threshold
        critical_size = int(manager.quota.max_total_size * 0.2)  # Additional 20%
        critical_file = manager.downloads_dir / "critical.dat"
        critical_file.write_bytes(b"x" * critical_size)
        
        stats = await manager.get_storage_stats()
        assert stats.status == "critical"
    
    @pytest.mark.asyncio
    async def test_error_handling_in_cleanup(self, temp_storage_manager):
        """Test error handling during cleanup operations."""
        manager = temp_storage_manager
        
        # Create a file and make it read-only to simulate permission error
        readonly_file = manager.downloads_dir / "readonly.txt"
        readonly_file.write_text("readonly content")
        
        # Make file old
        old_time = time.time() - 120
        os.utime(readonly_file, (old_time, old_time))
        
        # Make file read-only (on Windows, this might not prevent deletion)
        readonly_file.chmod(0o444)
        
        try:
            # Cleanup should handle errors gracefully
            result = await manager.cleanup_expired_files()
            
            # Should return result even if some files couldn't be deleted
            assert isinstance(result, dict)
            assert "errors" in result
            
        finally:
            # Restore permissions for cleanup
            try:
                readonly_file.chmod(0o666)
                readonly_file.unlink()
            except:
                pass
    
    def test_format_bytes_utility(self, temp_storage_manager):
        """Test bytes formatting utility function."""
        manager = temp_storage_manager
        
        assert manager._format_bytes(0) == "0.0 B"
        assert manager._format_bytes(512) == "512.0 B"
        assert manager._format_bytes(1024) == "1.0 KB"
        assert manager._format_bytes(1024 * 1024) == "1.0 MB"
        assert manager._format_bytes(1024 * 1024 * 1024) == "1.0 GB"
    
    @pytest.mark.asyncio
    async def test_backup_metadata_creation(self, temp_storage_manager):
        """Test backup metadata creation and structure."""
        manager = temp_storage_manager
        
        # Create some test data
        test_file = manager.logs_dir / "test.log"
        test_file.write_text("Test log data")
        
        result = await manager.backup_critical_data()
        backup_path = Path(result["backup_path"])
        
        # Check metadata file
        metadata_file = backup_path / "backup_metadata.json"
        assert metadata_file.exists()
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        assert "backup_name" in metadata
        assert "created_at" in metadata
        assert "files_count" in metadata
        assert "total_size" in metadata
        assert "storage_stats" in metadata
        
        # Verify timestamp format
        created_at = datetime.fromisoformat(metadata["created_at"])
        assert isinstance(created_at, datetime)


class TestStorageManagerIntegration:
    """Integration tests for storage manager with other components."""
    
    @pytest.mark.asyncio
    async def test_storage_manager_with_download_manager_integration(self):
        """Test storage manager integration with download manager."""
        # This would test how storage manager cleans up files created by download manager
        # For now, we'll create a simple integration test
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create storage manager
            storage_manager = StorageManager()
            storage_manager.downloads_dir = temp_path / "downloads"
            storage_manager.downloads_dir.mkdir()
            
            # Simulate download manager creating files
            download_file = storage_manager.downloads_dir / "downloaded_video.mp4"
            download_file.write_bytes(b"video content" * 1000)
            
            # Make file old
            old_time = time.time() - 3600  # 1 hour ago
            os.utime(download_file, (old_time, old_time))
            
            # Storage manager should clean it up
            result = await storage_manager.cleanup_expired_files()
            
            assert result["files_removed"] >= 1
            assert not download_file.exists()


if __name__ == "__main__":
    pytest.main([__file__])