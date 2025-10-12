"""
File cleanup and storage management service for VidNet MVP.

This module provides automated cleanup service for temporary files, storage quota monitoring,
file serving with security headers, and backup/recovery procedures for critical data.
"""

import asyncio
import os
import shutil
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from pathlib import Path
import aiofiles
import aiofiles.os
from dataclasses import dataclass, asdict

from app.core.config import settings
from app.core.exceptions import StorageError


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class StorageQuota:
    """Storage quota configuration and tracking."""
    max_total_size: int  # Maximum total storage in bytes
    max_file_age: int    # Maximum file age in seconds
    warning_threshold: float = 0.8  # Warning at 80% capacity
    critical_threshold: float = 0.95  # Critical at 95% capacity
    cleanup_target: float = 0.7  # Clean up to 70% capacity


@dataclass
class StorageStats:
    """Storage statistics and metrics."""
    total_size: int
    file_count: int
    oldest_file_age: int
    newest_file_age: int
    average_file_size: int
    quota_usage_percent: float
    status: str  # 'healthy', 'warning', 'critical'
    last_cleanup: Optional[datetime] = None
    cleanup_count: int = 0


@dataclass
class FileInfo:
    """File information for cleanup and management."""
    path: Path
    size: int
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    age_seconds: int
    file_type: str  # 'video', 'audio', 'temp', 'other'


class StorageManager:
    """
    Comprehensive storage management service.
    
    Features:
    - Automated cleanup service for temporary files
    - Storage quota monitoring and management
    - File serving with proper security headers
    - Backup and recovery procedures for critical data
    - Performance monitoring and alerting
    """
    
    def __init__(self):
        """Initialize storage manager with configuration."""
        # Storage directories
        self.downloads_dir = Path("downloads")
        self.temp_dir = Path("temp")
        self.logs_dir = Path("logs")
        self.backup_dir = Path("backups")
        
        # Create directories if they don't exist
        for directory in [self.downloads_dir, self.temp_dir, self.logs_dir, self.backup_dir]:
            directory.mkdir(exist_ok=True)
        
        # Storage quota configuration
        self.quota = StorageQuota(
            max_total_size=int(os.getenv("STORAGE_MAX_SIZE", str(5 * 1024 * 1024 * 1024))),  # 5GB default
            max_file_age=int(os.getenv("STORAGE_MAX_FILE_AGE", "1800")),  # 30 minutes default
            warning_threshold=float(os.getenv("STORAGE_WARNING_THRESHOLD", "0.8")),
            critical_threshold=float(os.getenv("STORAGE_CRITICAL_THRESHOLD", "0.95")),
            cleanup_target=float(os.getenv("STORAGE_CLEANUP_TARGET", "0.7"))
        )
        
        # Cleanup configuration
        self.cleanup_interval = int(os.getenv("STORAGE_CLEANUP_INTERVAL", "300"))  # 5 minutes
        self.aggressive_cleanup_threshold = 0.9  # Start aggressive cleanup at 90%
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics tracking
        self.stats_history: List[StorageStats] = []
        self.max_stats_history = 100
        
        # Security headers for file serving
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Content-Security-Policy": "default-src 'none'",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    
    async def start(self):
        """Start storage management background tasks."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting storage manager")
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        
        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_worker())
        
        logger.info("Storage manager started")
    
    async def stop(self):
        """Stop storage management background tasks."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping storage manager")
        
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(
            self._cleanup_task, self._monitoring_task, 
            return_exceptions=True
        )
        
        self._cleanup_task = None
        self._monitoring_task = None
        
        logger.info("Storage manager stopped")
    
    async def get_storage_stats(self) -> StorageStats:
        """
        Get current storage statistics.
        
        Returns:
            StorageStats: Current storage metrics
        """
        try:
            total_size = 0
            file_count = 0
            file_ages = []
            file_sizes = []
            
            # Scan all managed directories
            for directory in [self.downloads_dir, self.temp_dir]:
                if directory.exists():
                    async for file_info in self._scan_directory(directory):
                        total_size += file_info.size
                        file_count += 1
                        file_ages.append(file_info.age_seconds)
                        file_sizes.append(file_info.size)
            
            # Calculate statistics
            quota_usage = (total_size / self.quota.max_total_size) * 100 if self.quota.max_total_size > 0 else 0
            
            # Determine status
            if quota_usage >= self.quota.critical_threshold * 100:
                status = "critical"
            elif quota_usage >= self.quota.warning_threshold * 100:
                status = "warning"
            else:
                status = "healthy"
            
            stats = StorageStats(
                total_size=total_size,
                file_count=file_count,
                oldest_file_age=max(file_ages) if file_ages else 0,
                newest_file_age=min(file_ages) if file_ages else 0,
                average_file_size=int(sum(file_sizes) / len(file_sizes)) if file_sizes else 0,
                quota_usage_percent=round(quota_usage, 2),
                status=status
            )
            
            # Add to history
            self.stats_history.append(stats)
            if len(self.stats_history) > self.max_stats_history:
                self.stats_history.pop(0)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            raise StorageError(f"Failed to get storage statistics: {str(e)}")
    
    async def cleanup_expired_files(self, aggressive: bool = False) -> Dict[str, Any]:
        """
        Clean up expired files based on age and storage quota.
        
        Args:
            aggressive: If True, use more aggressive cleanup thresholds
            
        Returns:
            Dict: Cleanup results with statistics
        """
        try:
            cleanup_start = time.time()
            files_removed = 0
            bytes_freed = 0
            errors = []
            
            # Get current stats to determine cleanup strategy
            current_stats = await self.get_storage_stats()
            
            # Determine cleanup thresholds
            if aggressive or current_stats.quota_usage_percent > self.aggressive_cleanup_threshold * 100:
                max_age = self.quota.max_file_age // 2  # More aggressive age limit
                target_usage = self.quota.cleanup_target * 0.8  # Lower target
                logger.info("Starting aggressive cleanup")
            else:
                max_age = self.quota.max_file_age
                target_usage = self.quota.cleanup_target
            
            # Collect files for cleanup
            cleanup_candidates = []
            
            for directory in [self.downloads_dir, self.temp_dir]:
                if directory.exists():
                    async for file_info in self._scan_directory(directory):
                        # Add to cleanup if file is too old
                        if file_info.age_seconds > max_age:
                            cleanup_candidates.append(file_info)
            
            # Sort by age (oldest first) for cleanup priority
            cleanup_candidates.sort(key=lambda f: f.age_seconds, reverse=True)
            
            # Remove files until we reach target usage or no more candidates
            current_usage = current_stats.quota_usage_percent / 100
            
            for file_info in cleanup_candidates:
                if current_usage <= target_usage:
                    break
                
                try:
                    await aiofiles.os.remove(file_info.path)
                    files_removed += 1
                    bytes_freed += file_info.size
                    
                    # Update current usage estimate
                    current_usage = ((current_stats.total_size - bytes_freed) / self.quota.max_total_size)
                    
                    logger.debug(f"Removed expired file: {file_info.path}")
                    
                except Exception as e:
                    error_msg = f"Failed to remove {file_info.path}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            cleanup_duration = time.time() - cleanup_start
            
            # Update cleanup stats
            if hasattr(self, 'stats_history') and self.stats_history:
                self.stats_history[-1].last_cleanup = datetime.now(timezone.utc)
                self.stats_history[-1].cleanup_count += files_removed
            
            result = {
                "files_removed": files_removed,
                "bytes_freed": bytes_freed,
                "cleanup_duration_seconds": round(cleanup_duration, 2),
                "errors": errors,
                "aggressive_mode": aggressive,
                "final_usage_percent": round(current_usage * 100, 2)
            }
            
            if files_removed > 0:
                logger.info(f"Cleanup completed: {files_removed} files removed, "
                           f"{self._format_bytes(bytes_freed)} freed")
            
            return result
            
        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}")
            raise StorageError(f"File cleanup failed: {str(e)}")
    
    async def backup_critical_data(self) -> Dict[str, Any]:
        """
        Create backup of critical data (logs, configuration, metrics).
        
        Returns:
            Dict: Backup operation results
        """
        try:
            backup_start = time.time()
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_name = f"vidnet_backup_{timestamp}"
            backup_path = self.backup_dir / backup_name
            
            # Create backup directory
            backup_path.mkdir(exist_ok=True)
            
            files_backed_up = 0
            total_size = 0
            
            # Backup logs
            logs_backup = backup_path / "logs"
            if self.logs_dir.exists():
                await self._copy_directory(self.logs_dir, logs_backup)
                logs_size = await self._get_directory_size(logs_backup)
                files_backed_up += await self._count_files(logs_backup)
                total_size += logs_size
            
            # Backup configuration files
            config_backup = backup_path / "config"
            config_backup.mkdir(exist_ok=True)
            
            config_files = [
                ".env",
                "docker-compose.yml",
                "requirements.txt"
            ]
            
            for config_file in config_files:
                source_path = Path(config_file)
                if source_path.exists():
                    dest_path = config_backup / config_file
                    await self._copy_file(source_path, dest_path)
                    files_backed_up += 1
                    total_size += source_path.stat().st_size
            
            # Create backup metadata
            metadata = {
                "backup_name": backup_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "files_count": files_backed_up,
                "total_size": total_size,
                "storage_stats": asdict(await self.get_storage_stats())
            }
            
            metadata_path = backup_path / "backup_metadata.json"
            async with aiofiles.open(metadata_path, 'w') as f:
                import json
                await f.write(json.dumps(metadata, indent=2))
            
            backup_duration = time.time() - backup_start
            
            # Clean up old backups (keep last 10)
            await self._cleanup_old_backups(keep_count=10)
            
            result = {
                "backup_name": backup_name,
                "backup_path": str(backup_path),
                "files_backed_up": files_backed_up,
                "total_size": total_size,
                "backup_duration_seconds": round(backup_duration, 2),
                "created_at": metadata["created_at"]
            }
            
            logger.info(f"Backup completed: {backup_name}, {files_backed_up} files, "
                       f"{self._format_bytes(total_size)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Backup operation failed: {e}")
            raise StorageError(f"Backup failed: {str(e)}")
    
    async def restore_from_backup(self, backup_name: str) -> Dict[str, Any]:
        """
        Restore data from a specific backup.
        
        Args:
            backup_name: Name of the backup to restore
            
        Returns:
            Dict: Restore operation results
        """
        try:
            backup_path = self.backup_dir / backup_name
            
            if not backup_path.exists():
                raise StorageError(f"Backup {backup_name} not found")
            
            restore_start = time.time()
            files_restored = 0
            
            # Read backup metadata
            metadata_path = backup_path / "backup_metadata.json"
            if metadata_path.exists():
                async with aiofiles.open(metadata_path, 'r') as f:
                    import json
                    metadata = json.loads(await f.read())
            else:
                metadata = {}
            
            # Restore logs
            logs_backup = backup_path / "logs"
            if logs_backup.exists():
                # Create backup of current logs before restore
                current_logs_backup = self.logs_dir.parent / f"logs_backup_{int(time.time())}"
                if self.logs_dir.exists():
                    await self._copy_directory(self.logs_dir, current_logs_backup)
                
                # Restore logs
                await self._copy_directory(logs_backup, self.logs_dir)
                files_restored += await self._count_files(logs_backup)
            
            # Restore configuration files
            config_backup = backup_path / "config"
            if config_backup.exists():
                for config_file in config_backup.iterdir():
                    if config_file.is_file() and config_file.name != "backup_metadata.json":
                        dest_path = Path(config_file.name)
                        await self._copy_file(config_file, dest_path)
                        files_restored += 1
            
            restore_duration = time.time() - restore_start
            
            result = {
                "backup_name": backup_name,
                "files_restored": files_restored,
                "restore_duration_seconds": round(restore_duration, 2),
                "backup_metadata": metadata,
                "restored_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Restore completed: {backup_name}, {files_restored} files restored")
            
            return result
            
        except Exception as e:
            logger.error(f"Restore operation failed: {e}")
            raise StorageError(f"Restore failed: {str(e)}")
    
    def get_security_headers(self, file_path: Path) -> Dict[str, str]:
        """
        Get security headers for file serving.
        
        Args:
            file_path: Path to the file being served
            
        Returns:
            Dict: Security headers for the response
        """
        headers = self.security_headers.copy()
        
        # Add content-specific headers
        file_ext = file_path.suffix.lower()
        
        if file_ext in ['.mp4', '.webm', '.avi', '.mov', '.mkv']:
            headers["Content-Type"] = f"video/{file_ext[1:]}"
            headers["Accept-Ranges"] = "bytes"
        elif file_ext in ['.mp3', '.m4a', '.wav']:
            headers["Content-Type"] = f"audio/{file_ext[1:]}"
            headers["Accept-Ranges"] = "bytes"
        else:
            headers["Content-Type"] = "application/octet-stream"
        
        # Add content disposition for download
        headers["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
        
        return headers
    
    async def validate_file_access(self, file_path: Path) -> bool:
        """
        Validate that file access is allowed (security check).
        
        Args:
            file_path: Path to validate
            
        Returns:
            bool: True if access is allowed
        """
        try:
            # Resolve path to prevent directory traversal
            resolved_path = file_path.resolve()
            
            # Check if file is within allowed directories
            allowed_dirs = [
                self.downloads_dir.resolve(),
                self.temp_dir.resolve()
            ]
            
            for allowed_dir in allowed_dirs:
                try:
                    resolved_path.relative_to(allowed_dir)
                    return True
                except ValueError:
                    continue
            
            logger.warning(f"File access denied: {file_path} not in allowed directories")
            return False
            
        except Exception as e:
            logger.error(f"File validation error: {e}")
            return False
    
    async def _cleanup_worker(self):
        """Background worker for automated cleanup."""
        while self._running:
            try:
                # Get current storage stats
                stats = await self.get_storage_stats()
                
                # Determine if cleanup is needed
                needs_cleanup = (
                    stats.quota_usage_percent > self.quota.warning_threshold * 100 or
                    stats.oldest_file_age > self.quota.max_file_age
                )
                
                if needs_cleanup:
                    aggressive = stats.quota_usage_percent > self.aggressive_cleanup_threshold * 100
                    await self.cleanup_expired_files(aggressive=aggressive)
                
                # Wait for next cleanup cycle
                await asyncio.sleep(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    async def _monitoring_worker(self):
        """Background worker for storage monitoring and alerting."""
        while self._running:
            try:
                stats = await self.get_storage_stats()
                
                # Log warnings and critical alerts
                if stats.status == "critical":
                    logger.critical(f"Storage critical: {stats.quota_usage_percent}% used, "
                                   f"{stats.file_count} files")
                elif stats.status == "warning":
                    logger.warning(f"Storage warning: {stats.quota_usage_percent}% used, "
                                  f"{stats.file_count} files")
                
                # Trigger backup if needed (daily)
                if self._should_create_backup():
                    try:
                        await self.backup_critical_data()
                    except Exception as e:
                        logger.error(f"Automated backup failed: {e}")
                
                # Wait for next monitoring cycle (every 5 minutes)
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Monitoring worker error: {e}")
                await asyncio.sleep(60)
    
    async def _scan_directory(self, directory: Path):
        """
        Async generator to scan directory for files.
        
        Args:
            directory: Directory to scan
            
        Yields:
            FileInfo: Information about each file
        """
        try:
            for item in directory.rglob('*'):
                if item.is_file():
                    try:
                        stat = item.stat()
                        created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
                        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                        accessed_at = datetime.fromtimestamp(stat.st_atime, tz=timezone.utc)
                        age_seconds = int(time.time() - stat.st_mtime)
                        
                        # Determine file type
                        file_ext = item.suffix.lower()
                        if file_ext in ['.mp4', '.webm', '.avi', '.mov', '.mkv']:
                            file_type = 'video'
                        elif file_ext in ['.mp3', '.m4a', '.wav']:
                            file_type = 'audio'
                        elif file_ext in ['.tmp', '.temp']:
                            file_type = 'temp'
                        else:
                            file_type = 'other'
                        
                        yield FileInfo(
                            path=item,
                            size=stat.st_size,
                            created_at=created_at,
                            modified_at=modified_at,
                            accessed_at=accessed_at,
                            age_seconds=age_seconds,
                            file_type=file_type
                        )
                        
                    except Exception as e:
                        logger.warning(f"Error scanning file {item}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
    
    async def _copy_file(self, source: Path, destination: Path):
        """Copy file asynchronously."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(source, 'rb') as src:
            async with aiofiles.open(destination, 'wb') as dst:
                while True:
                    chunk = await src.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    await dst.write(chunk)
    
    async def _copy_directory(self, source: Path, destination: Path):
        """Copy directory recursively asynchronously."""
        destination.mkdir(parents=True, exist_ok=True)
        
        for item in source.rglob('*'):
            if item.is_file():
                relative_path = item.relative_to(source)
                dest_path = destination / relative_path
                await self._copy_file(item, dest_path)
    
    async def _get_directory_size(self, directory: Path) -> int:
        """Get total size of directory in bytes."""
        total_size = 0
        async for file_info in self._scan_directory(directory):
            total_size += file_info.size
        return total_size
    
    async def _count_files(self, directory: Path) -> int:
        """Count files in directory."""
        count = 0
        async for _ in self._scan_directory(directory):
            count += 1
        return count
    
    async def _cleanup_old_backups(self, keep_count: int = 10):
        """Clean up old backups, keeping only the most recent ones."""
        try:
            backups = []
            for item in self.backup_dir.iterdir():
                if item.is_dir() and item.name.startswith("vidnet_backup_"):
                    backups.append((item.stat().st_mtime, item))
            
            # Sort by modification time (newest first)
            backups.sort(reverse=True)
            
            # Remove old backups
            for _, backup_path in backups[keep_count:]:
                shutil.rmtree(backup_path)
                logger.info(f"Removed old backup: {backup_path.name}")
                
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    def _should_create_backup(self) -> bool:
        """Check if a backup should be created (daily schedule)."""
        try:
            # Check if we have any backups
            backups = list(self.backup_dir.glob("vidnet_backup_*"))
            if not backups:
                return True
            
            # Get the most recent backup
            latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
            backup_age = time.time() - latest_backup.stat().st_mtime
            
            # Create backup if latest is older than 24 hours
            return backup_age > 86400  # 24 hours in seconds
            
        except Exception as e:
            logger.error(f"Error checking backup schedule: {e}")
            return False
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes into human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} PB"


# Global storage manager instance
storage_manager = StorageManager()