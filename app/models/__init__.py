"""
Data models package for VidNet MVP.

This package contains Pydantic models and validation functions for video processing.
"""

from .video import VideoQuality, VideoMetadata, DownloadRequest, DownloadResponse
from .validators import (
    PlatformValidator,
    validate_video_url,
    detect_platform,
    get_supported_platforms,
    is_direct_video_link,
    validate_youtube_url,
    validate_tiktok_url,
    validate_instagram_url,
    validate_facebook_url,
    validate_twitter_url,
    validate_reddit_url,
    validate_vimeo_url,
)

__all__ = [
    # Video models
    'VideoQuality',
    'VideoMetadata', 
    'DownloadRequest',
    'DownloadResponse',
    
    # Validators
    'PlatformValidator',
    'validate_video_url',
    'detect_platform',
    'get_supported_platforms',
    'is_direct_video_link',
    'validate_youtube_url',
    'validate_tiktok_url',
    'validate_instagram_url',
    'validate_facebook_url',
    'validate_twitter_url',
    'validate_reddit_url',
    'validate_vimeo_url',
]