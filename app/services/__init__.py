"""
Services package for VidNet MVP.

This package contains business logic services for video processing,
platform detection, and other core functionality.
"""

from .platform_detector import (
    PlatformDetector,
    PlatformInfo,
    detect_platform,
    validate_video_url,
    normalize_url,
    get_supported_platforms,
    is_direct_video_link,
    get_video_extension,
    validate_youtube_url,
    validate_tiktok_url,
    validate_instagram_url,
    validate_facebook_url,
    validate_twitter_url,
    validate_reddit_url,
    validate_vimeo_url,
)

from .video_processor import (
    VideoProcessor,
    VideoProcessorError,
    UnsupportedPlatformError,
    VideoNotFoundError,
    ExtractionError,
    extract_video_metadata,
)

from .cache_manager import (
    CacheManager,
    cache_manager,
)

__all__ = [
    # Platform detection
    'PlatformDetector',
    'PlatformInfo',
    'detect_platform',
    'validate_video_url',
    'normalize_url',
    'get_supported_platforms',
    'is_direct_video_link',
    'get_video_extension',
    'validate_youtube_url',
    'validate_tiktok_url',
    'validate_instagram_url',
    'validate_facebook_url',
    'validate_twitter_url',
    'validate_reddit_url',
    'validate_vimeo_url',
    # Video processing
    'VideoProcessor',
    'VideoProcessorError',
    'UnsupportedPlatformError',
    'VideoNotFoundError',
    'ExtractionError',
    'extract_video_metadata',
    # Cache management
    'CacheManager',
    'cache_manager',
]