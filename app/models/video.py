"""
Video-related data models for VidNet MVP.

This module contains Pydantic models for video metadata, quality options,
download requests, and responses.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Literal
from datetime import datetime, timezone
import re


class VideoQuality(BaseModel):
    """Model representing a video quality option."""
    
    quality: str = Field(..., description="Quality label (e.g., '720p', '1080p', '4K')")
    format: str = Field(..., description="Video format (e.g., 'mp4', 'webm')")
    filesize: Optional[int] = Field(None, description="Estimated file size in bytes")
    fps: Optional[int] = Field(None, description="Frames per second")
    
    @field_validator('quality')
    @classmethod
    def validate_quality(cls, v):
        """Validate quality format."""
        valid_qualities = ['144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p', '4K']
        if v not in valid_qualities:
            raise ValueError(f'Quality must be one of: {", ".join(valid_qualities)}')
        return v
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        """Validate video format."""
        valid_formats = ['mp4', 'webm', 'avi', 'mov', 'mkv', 'flv']
        if v.lower() not in valid_formats:
            raise ValueError(f'Format must be one of: {", ".join(valid_formats)}')
        return v.lower()
    
    @field_validator('fps')
    @classmethod
    def validate_fps(cls, v):
        """Validate frames per second."""
        if v is not None and (v <= 0 or v > 120):
            raise ValueError('FPS must be between 1 and 120')
        return v


class VideoMetadata(BaseModel):
    """Model representing video metadata."""
    
    title: str = Field(..., description="Video title")
    thumbnail: str = Field(..., description="Thumbnail URL")
    duration: int = Field(..., description="Duration in seconds")
    platform: Literal['youtube', 'tiktok', 'instagram', 'facebook', 'twitter', 'reddit', 'vimeo', 'direct'] = Field(
        ..., description="Source platform"
    )
    available_qualities: List[VideoQuality] = Field(..., description="Available quality options")
    audio_available: bool = Field(True, description="Whether audio track is available")
    file_extension: Optional[str] = Field(None, description="File extension for direct links")
    original_url: str = Field(..., description="Original video URL")
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        """Validate video title."""
        if not v or len(v.strip()) == 0:
            raise ValueError('Title cannot be empty')
        if len(v) > 500:
            raise ValueError('Title cannot exceed 500 characters')
        return v.strip()
    
    @field_validator('thumbnail')
    @classmethod
    def validate_thumbnail(cls, v):
        """Validate thumbnail URL."""
        if not v:
            raise ValueError('Thumbnail URL is required')
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)', re.IGNORECASE)
        if not url_pattern.match(v):
            raise ValueError('Invalid thumbnail URL format')
        return v
    
    @field_validator('duration')
    @classmethod
    def validate_duration(cls, v):
        """Validate video duration."""
        if v < 0:
            raise ValueError('Duration cannot be negative')
        if v > 86400:  # 24 hours
            raise ValueError('Duration cannot exceed 24 hours')
        return v
    
    @field_validator('available_qualities')
    @classmethod
    def validate_qualities(cls, v):
        """Validate available qualities list."""
        if not v:
            raise ValueError('At least one quality option must be available')
        return v
    
    @field_validator('file_extension')
    @classmethod
    def validate_file_extension(cls, v, info):
        """Validate file extension for direct links."""
        if info.data.get('platform') == 'direct' and not v:
            raise ValueError('File extension is required for direct links')
        if v and not v.startswith('.'):
            v = f'.{v}'
        return v


class DownloadRequest(BaseModel):
    """Model representing a download request."""
    
    url: str = Field(..., description="Video URL to download")
    quality: str = Field(..., description="Requested quality (e.g., '1080p')")
    format: Literal['video', 'audio'] = Field('video', description="Download format type")
    audio_quality: Optional[Literal['128kbps', '320kbps']] = Field(
        None, description="Audio quality for audio extraction"
    )
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate video URL."""
        if not v or len(v.strip()) == 0:
            raise ValueError('URL cannot be empty')
        
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)', re.IGNORECASE)
        
        if not url_pattern.match(v):
            raise ValueError('Invalid URL format')
        
        return v.strip()
    
    @field_validator('quality')
    @classmethod
    def validate_quality(cls, v):
        """Validate requested quality."""
        valid_qualities = ['144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p', '4K']
        if v not in valid_qualities:
            raise ValueError(f'Quality must be one of: {", ".join(valid_qualities)}')
        return v
    
    @field_validator('audio_quality')
    @classmethod
    def validate_audio_quality(cls, v, info):
        """Validate audio quality for audio extraction."""
        if info.data.get('format') == 'audio' and not v:
            raise ValueError('Audio quality is required for audio extraction')
        return v


class DownloadResponse(BaseModel):
    """Model representing a download response."""
    
    task_id: str = Field(..., description="Unique task identifier")
    status: Literal['pending', 'processing', 'completed', 'failed'] = Field(
        ..., description="Download status"
    )
    download_url: Optional[str] = Field(None, description="Download URL when completed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    progress: Optional[int] = Field(None, description="Download progress percentage (0-100)")
    estimated_time: Optional[int] = Field(None, description="Estimated completion time in seconds")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Task creation time")
    
    @field_validator('task_id')
    @classmethod
    def validate_task_id(cls, v):
        """Validate task ID format."""
        if not v or len(v.strip()) == 0:
            raise ValueError('Task ID cannot be empty')
        # Task ID should be alphanumeric with hyphens/underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Task ID must contain only alphanumeric characters, hyphens, and underscores')
        return v
    
    @field_validator('progress')
    @classmethod
    def validate_progress(cls, v):
        """Validate progress percentage."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Progress must be between 0 and 100')
        return v
    
    @field_validator('estimated_time')
    @classmethod
    def validate_estimated_time(cls, v):
        """Validate estimated time."""
        if v is not None and v < 0:
            raise ValueError('Estimated time cannot be negative')
        return v
    
    @field_validator('download_url')
    @classmethod
    def validate_download_url(cls, v, info):
        """Validate download URL when status is completed."""
        if info.data.get('status') == 'completed' and not v:
            raise ValueError('Download URL is required when status is completed')
        return v
    
    @field_validator('error_message')
    @classmethod
    def validate_error_message(cls, v, info):
        """Validate error message when status is failed."""
        if info.data.get('status') == 'failed' and not v:
            raise ValueError('Error message is required when status is failed')
        return v