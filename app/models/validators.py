"""
URL validation functions for supported platforms.
"""

import re
from typing import Optional, Dict, List
from urllib.parse import urlparse, parse_qs

# Import the new platform detector
from app.services.platform_detector import PlatformDetector


class PlatformValidator:
    """Legacy validator class for different video platforms."""
    
    PLATFORM_PATTERNS = {
        'youtube': [
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        ],
        'tiktok': [
            r'(?:https?://)?(?:www\.)?tiktok\.com/@[\w.-]+/video/(\d+)',
        ],
        'instagram': [
            r'(?:https?://)?(?:www\.)?instagram\.com/p/([a-zA-Z0-9_-]+)',
        ],
        'facebook': [
            r'(?:https?://)?(?:www\.)?facebook\.com/watch/?\?v=(\d+)',
        ],
        'twitter': [
            r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[\w]+/status/(\d+)',
        ],
        'reddit': [
            r'(?:https?://)?(?:www\.)?reddit\.com/r/[\w]+/comments/([a-zA-Z0-9]+)',
        ],
        'vimeo': [
            r'(?:https?://)?(?:www\.)?vimeo\.com/(\d+)',
        ],
        'direct': [
            r'.*\.(mp4|avi|mov|mkv|webm|flv|m4v|3gp|wmv)(\?.*)?$',
        ]
    }
    
    @classmethod
    def detect_platform(cls, url: str) -> Optional[str]:
        """Detect the platform from a given URL."""
        return PlatformDetector.detect_platform(url)
    
    @classmethod
    def validate_url(cls, url: str) -> Dict[str, any]:
        """Validate a URL and extract platform information."""
        return PlatformDetector.validate_url(url)
    
    @classmethod
    def _extract_video_id(cls, url: str, platform: str) -> Optional[str]:
        """Extract video ID from URL based on platform."""
        platform_info = PlatformDetector.extract_platform_info(url)
        return platform_info.video_id if platform_info else None
    
    @classmethod
    def _normalize_url(cls, url: str, platform: str, video_id: Optional[str]) -> Optional[str]:
        """Normalize URL to standard format for each platform."""
        return PlatformDetector.normalize_url(url)
    
    @classmethod
    def get_supported_platforms(cls) -> List[str]:
        """Get list of all supported platforms."""
        return PlatformDetector.get_supported_platforms()
    
    @classmethod
    def is_platform_supported(cls, platform: str) -> bool:
        """Check if a platform is supported."""
        return PlatformDetector.is_platform_supported(platform)


def validate_video_url(url: str) -> Dict[str, any]:
    """Convenience function to validate a video URL."""
    return PlatformDetector.validate_url(url)


def detect_platform(url: str) -> Optional[str]:
    """Convenience function to detect platform from URL."""
    return PlatformDetector.detect_platform(url)


def get_supported_platforms() -> List[str]:
    """Get list of supported platforms."""
    return PlatformDetector.get_supported_platforms()


def is_direct_video_link(url: str) -> bool:
    """Check if URL is a direct video file link."""
    return PlatformDetector.is_direct_video_link(url)


def normalize_url(url: str) -> Optional[str]:
    """Normalize URL to standard format."""
    return PlatformDetector.normalize_url(url)


def get_video_extension(url: str) -> Optional[str]:
    """Get video file extension from direct video links."""
    return PlatformDetector.get_video_extension(url)


def validate_youtube_url(url: str) -> bool:
    """Validate YouTube URL format."""
    return PlatformDetector.detect_platform(url) == 'youtube'


def validate_tiktok_url(url: str) -> bool:
    """Validate TikTok URL format."""
    return PlatformDetector.detect_platform(url) == 'tiktok'


def validate_instagram_url(url: str) -> bool:
    """Validate Instagram URL format."""
    return PlatformDetector.detect_platform(url) == 'instagram'


def validate_facebook_url(url: str) -> bool:
    """Validate Facebook URL format."""
    return PlatformDetector.detect_platform(url) == 'facebook'


def validate_twitter_url(url: str) -> bool:
    """Validate Twitter/X URL format."""
    return PlatformDetector.detect_platform(url) == 'twitter'


def validate_reddit_url(url: str) -> bool:
    """Validate Reddit URL format."""
    return PlatformDetector.detect_platform(url) == 'reddit'


def validate_vimeo_url(url: str) -> bool:
    """Validate Vimeo URL format."""
    return PlatformDetector.detect_platform(url) == 'vimeo'