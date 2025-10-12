"""
Storage management API for VidNet MVP.

This module provides endpoints for storage monitoring, cleanup operations,
and backup/recovery management.
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from app.services.storage_manager import storage_manager
from app.core.exceptions import StorageError


# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/v1/storage", tags=["storage"])


@router.get(
    "/stats",
    summary="Get storage statistics",
    description="Get current storage usage statistics and quota information"
)
async def get_storage_stats() -> JSONResponse:
    """
    Get current storage statistics.
    
    Returns:
        JSONResponse with storage statistics including:
        - Total size and file count
        - Quota usage percentage
        - Storage status (healthy/warning/critical)
        - File age statistics
    """
    try:
        stats = await storage_manager.get_storage_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "total_size": stats.total_size,
                    "total_size_human": storage_manager._format_bytes(stats.total_size),
                    "file_count": stats.file_count,
                    "quota_usage_percent": stats.quota_usage_percent,
                    "status": stats.status,
                    "oldest_file_age_seconds": stats.oldest_file_age,
                    "newest_file_age_seconds": stats.newest_file_age,
                    "average_file_size": stats.average_file_size,
                    "average_file_size_human": storage_manager._format_bytes(stats.average_file_size),
                    "last_cleanup": stats.last_cleanup.isoformat() if stats.last_cleanup else None,
                    "cleanup_count": stats.cleanup_count,
                    "quota_config": {
                        "max_total_size": storage_manager.quota.max_total_size,
                        "max_total_size_human": storage_manager._format_bytes(storage_manager.quota.max_total_size),
                        "max_file_age_seconds": storage_manager.quota.max_file_age,
                        "warning_threshold": storage_manager.quota.warning_threshold,
                        "critical_threshold": storage_manager.quota.critical_threshold
                    }
                }
            }
        )
        
    except StorageError as e:
        logger.error(f"Storage stats error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get storage statistics: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting storage stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while getting storage statistics"
        )


@router.post(
    "/cleanup",
    summary="Trigger storage cleanup",
    description="Manually trigger cleanup of expired files"
)
async def trigger_cleanup(
    background_tasks: BackgroundTasks,
    aggressive: bool = Query(False, description="Use aggressive cleanup thresholds")
) -> JSONResponse:
    """
    Manually trigger storage cleanup.
    
    Args:
        background_tasks: FastAPI background tasks
        aggressive: Whether to use aggressive cleanup thresholds
        
    Returns:
        JSONResponse with cleanup operation results
    """
    try:
        # Run cleanup in background
        background_tasks.add_task(
            _background_cleanup,
            aggressive=aggressive
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "success": True,
                "message": "Cleanup operation started in background",
                "aggressive_mode": aggressive
            }
        )
        
    except Exception as e:
        logger.error(f"Error triggering cleanup: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger cleanup operation"
        )


@router.get(
    "/cleanup/status",
    summary="Get cleanup operation results",
    description="Get results of the last cleanup operation"
)
async def get_cleanup_status() -> JSONResponse:
    """
    Get status and results of cleanup operations.
    
    Returns:
        JSONResponse with cleanup status and statistics
    """
    try:
        # Get current stats which include cleanup information
        stats = await storage_manager.get_storage_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "last_cleanup": stats.last_cleanup.isoformat() if stats.last_cleanup else None,
                    "cleanup_count": stats.cleanup_count,
                    "current_status": stats.status,
                    "quota_usage_percent": stats.quota_usage_percent,
                    "cleanup_interval_seconds": storage_manager.cleanup_interval,
                    "next_scheduled_cleanup": "Automatic cleanup runs every 5 minutes"
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting cleanup status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get cleanup status"
        )


@router.post(
    "/backup",
    summary="Create backup",
    description="Create a backup of critical data (logs, configuration, metrics)"
)
async def create_backup(background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Create a backup of critical data.
    
    Args:
        background_tasks: FastAPI background tasks
        
    Returns:
        JSONResponse with backup operation status
    """
    try:
        # Run backup in background
        background_tasks.add_task(_background_backup)
        
        return JSONResponse(
            status_code=202,
            content={
                "success": True,
                "message": "Backup operation started in background"
            }
        )
        
    except Exception as e:
        logger.error(f"Error triggering backup: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger backup operation"
        )


@router.get(
    "/backups",
    summary="List available backups",
    description="List all available backups with their information"
)
async def list_backups() -> JSONResponse:
    """
    List all available backups.
    
    Returns:
        JSONResponse with list of available backups
    """
    try:
        backups = []
        
        if storage_manager.backup_dir.exists():
            for backup_path in storage_manager.backup_dir.iterdir():
                if backup_path.is_dir() and backup_path.name.startswith("vidnet_backup_"):
                    try:
                        stat = backup_path.stat()
                        
                        # Try to read backup metadata
                        metadata_path = backup_path / "backup_metadata.json"
                        metadata = {}
                        if metadata_path.exists():
                            import json
                            with open(metadata_path, 'r') as f:
                                metadata = json.load(f)
                        
                        backup_info = {
                            "name": backup_path.name,
                            "created_at": metadata.get("created_at", stat.st_ctime),
                            "size_bytes": metadata.get("total_size", 0),
                            "size_human": storage_manager._format_bytes(metadata.get("total_size", 0)),
                            "files_count": metadata.get("files_count", 0),
                            "path": str(backup_path)
                        }
                        
                        backups.append(backup_info)
                        
                    except Exception as e:
                        logger.warning(f"Error processing backup {backup_path}: {e}")
                        continue
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "backups": backups,
                    "total_count": len(backups)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list backups"
        )


@router.post(
    "/restore/{backup_name}",
    summary="Restore from backup",
    description="Restore data from a specific backup"
)
async def restore_backup(
    backup_name: str,
    background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Restore data from a specific backup.
    
    Args:
        backup_name: Name of the backup to restore
        background_tasks: FastAPI background tasks
        
    Returns:
        JSONResponse with restore operation status
    """
    try:
        # Validate backup exists
        backup_path = storage_manager.backup_dir / backup_name
        if not backup_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Backup {backup_name} not found"
            )
        
        # Run restore in background
        background_tasks.add_task(_background_restore, backup_name)
        
        return JSONResponse(
            status_code=202,
            content={
                "success": True,
                "message": f"Restore operation for {backup_name} started in background",
                "backup_name": backup_name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering restore: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger restore operation"
        )


@router.get(
    "/health",
    summary="Storage health check",
    description="Get storage system health status and diagnostics"
)
async def storage_health_check() -> JSONResponse:
    """
    Perform storage system health check.
    
    Returns:
        JSONResponse with health status and diagnostics
    """
    try:
        stats = await storage_manager.get_storage_stats()
        
        # Determine overall health
        health_status = "healthy"
        issues = []
        
        if stats.status == "critical":
            health_status = "critical"
            issues.append(f"Storage usage critical: {stats.quota_usage_percent}%")
        elif stats.status == "warning":
            health_status = "warning"
            issues.append(f"Storage usage high: {stats.quota_usage_percent}%")
        
        # Check if cleanup is working
        if stats.oldest_file_age > storage_manager.quota.max_file_age * 2:
            health_status = "warning" if health_status == "healthy" else health_status
            issues.append("Old files detected - cleanup may not be working properly")
        
        # Check directory accessibility
        directories_status = {}
        for dir_name, directory in [
            ("downloads", storage_manager.downloads_dir),
            ("temp", storage_manager.temp_dir),
            ("logs", storage_manager.logs_dir),
            ("backups", storage_manager.backup_dir)
        ]:
            try:
                directories_status[dir_name] = {
                    "exists": directory.exists(),
                    "writable": os.access(directory, os.W_OK) if directory.exists() else False,
                    "path": str(directory)
                }
            except Exception as e:
                directories_status[dir_name] = {
                    "exists": False,
                    "writable": False,
                    "error": str(e),
                    "path": str(directory)
                }
                health_status = "critical"
                issues.append(f"Directory {dir_name} not accessible")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "status": health_status,
                    "issues": issues,
                    "storage_stats": {
                        "usage_percent": stats.quota_usage_percent,
                        "file_count": stats.file_count,
                        "total_size_human": storage_manager._format_bytes(stats.total_size)
                    },
                    "directories": directories_status,
                    "cleanup_status": {
                        "last_cleanup": stats.last_cleanup.isoformat() if stats.last_cleanup else None,
                        "cleanup_interval_seconds": storage_manager.cleanup_interval,
                        "running": storage_manager._running
                    }
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Storage health check failed"
        )


# Background task functions
async def _background_cleanup(aggressive: bool = False):
    """Background task for cleanup operation."""
    try:
        result = await storage_manager.cleanup_expired_files(aggressive=aggressive)
        logger.info(f"Background cleanup completed: {result}")
    except Exception as e:
        logger.error(f"Background cleanup failed: {e}")


async def _background_backup():
    """Background task for backup operation."""
    try:
        result = await storage_manager.backup_critical_data()
        logger.info(f"Background backup completed: {result}")
    except Exception as e:
        logger.error(f"Background backup failed: {e}")


async def _background_restore(backup_name: str):
    """Background task for restore operation."""
    try:
        result = await storage_manager.restore_from_backup(backup_name)
        logger.info(f"Background restore completed: {result}")
    except Exception as e:
        logger.error(f"Background restore failed: {e}")