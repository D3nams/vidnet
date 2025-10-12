"""
Platform detection and URL processing service for VidNet MVP.

This module provides comprehensive platform detection, URL normalization,
and validation for all supported video platforms.
"""

import re
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, parse_qs, unquote
from dataclasses import dataclass


@dataclass
class PlatformInfo:
    """Information about a detected platform."""
    name: str
    video_id: Optional[str]
    normalized_url: str
    original_url: str
    metadata: Dict[str, any]


class PlatformDetector:
    """Advanced platform detection and URL processing service."""
    
    # Enhanced platform patterns with more comprehensive regex
    PLATFORM_PATTERNS = {
        'youtube': {
            'patterns': [
                # Standard YouTube URLs
                r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
                r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)',
                r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
                r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]+)',
                # YouTube Shorts
                r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)',
                # YouTube Music
                r'(?:https?://)?music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
                # YouTube Playlists (extract first video)
                r'(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
                # YouTube live streams
                r'(?:https?://)?(?:www\.)?youtube\.com/live/([a-zA-Z0-9_-]+)',
            ],
            'domain_aliases': ['youtube.com', 'youtu.be', 'music.youtube.com', 'm.youtube.com'],
            'normalize_template': 'https://www.youtube.com/watch?v={video_id}'
        },
        'tiktok': {
            'patterns': [
                # Standard TikTok video URLs
                r'(?:https?://)?(?:www\.)?tiktok\.com/@([\w.-]+)/video/(\d+)',
                # Short TikTok URLs
                r'(?:https?://)?(?:vm\.tiktok\.com|vt\.tiktok\.com)/([a-zA-Z0-9]+)',
                r'(?:https?://)?(?:www\.)?tiktok\.com/t/([a-zA-Z0-9]+)',
                # Mobile TikTok URLs
                r'(?:https?://)?m\.tiktok\.com/v/(\d+)',
                # TikTok with additional parameters
                r'(?:https?://)?(?:www\.)?tiktok\.com/@[\w.-]+/video/(\d+)\?.*',
            ],
            'domain_aliases': ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com', 'm.tiktok.com'],
            'normalize_template': None  # TikTok URLs are kept as-is due to complexity
        },
        'instagram': {
            'patterns': [
                # Instagram posts
                r'(?:https?://)?(?:www\.)?instagram\.com/p/([a-zA-Z0-9_-]+)',
                # Instagram reels
                r'(?:https?://)?(?:www\.)?instagram\.com/reel/([a-zA-Z0-9_-]+)',
                # Instagram TV
                r'(?:https?://)?(?:www\.)?instagram\.com/tv/([a-zA-Z0-9_-]+)',
                # Instagram stories (limited support)
                r'(?:https?://)?(?:www\.)?instagram\.com/stories/[\w.-]+/(\d+)',
            ],
            'domain_aliases': ['instagram.com', 'www.instagram.com'],
            'normalize_template': 'https://www.instagram.com/p/{video_id}/'
        },
        'facebook': {
            'patterns': [
                # Facebook watch URLs
                r'(?:https?://)?(?:www\.)?facebook\.com/watch/?\?v=(\d+)',
                # Facebook video URLs
                r'(?:https?://)?(?:www\.)?facebook\.com/[\w.-]+/videos/(\d+)',
                # Facebook video.php URLs
                r'(?:https?://)?(?:www\.)?facebook\.com/video\.php\?v=(\d+)',
                # Facebook short URLs
                r'(?:https?://)?(?:fb\.watch)/([a-zA-Z0-9_-]+)',
                # Facebook mobile URLs
                r'(?:https?://)?m\.facebook\.com/watch/?\?v=(\d+)',
            ],
            'domain_aliases': ['facebook.com', 'fb.watch', 'm.facebook.com'],
            'normalize_template': 'https://www.facebook.com/watch/?v={video_id}'
        },
        'twitter': {
            'patterns': [
                # Twitter/X status URLs
                r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([\w]+)/status/(\d+)',
                # Twitter/X web status URLs
                r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/i/web/status/(\d+)',
                # Mobile Twitter URLs
                r'(?:https?://)?mobile\.(?:twitter\.com|x\.com)/([\w]+)/status/(\d+)',
            ],
            'domain_aliases': ['twitter.com', 'x.com', 'mobile.twitter.com', 'mobile.x.com'],
            'normalize_template': 'https://twitter.com/i/web/status/{video_id}'
        },
        'reddit': {
            'patterns': [
                # Reddit post URLs
                r'(?:https?://)?(?:www\.)?reddit\.com/r/([\w]+)/comments/([a-zA-Z0-9]+)',
                # Reddit video URLs
                r'(?:https?://)?(?:v\.redd\.it)/([a-zA-Z0-9]+)',
                # Old Reddit URLs
                r'(?:https?://)?old\.reddit\.com/r/([\w]+)/comments/([a-zA-Z0-9]+)',
                # Mobile Reddit URLs
                r'(?:https?://)?m\.reddit\.com/r/([\w]+)/comments/([a-zA-Z0-9]+)',
            ],
            'domain_aliases': ['reddit.com', 'v.redd.it', 'old.reddit.com', 'm.reddit.com'],
            'normalize_template': None  # Reddit URLs are kept as-is
        },
        'vimeo': {
            'patterns': [
                # Standard Vimeo URLs
                r'(?:https?://)?(?:www\.)?vimeo\.com/(\d+)',
                # Vimeo player URLs
                r'(?:https?://)?(?:player\.)?vimeo\.com/video/(\d+)',
                # Vimeo on-demand URLs
                r'(?:https?://)?vimeo\.com/ondemand/[\w-]+/(\d+)',
                # Vimeo channels
                r'(?:https?://)?vimeo\.com/channels/[\w-]+/(\d+)',
            ],
            'domain_aliases': ['vimeo.com', 'player.vimeo.com'],
            'normalize_template': 'https://vimeo.com/{video_id}'
        },
        'direct': {
            'patterns': [
                # Direct video file links with various extensions
                r'.*\.(mp4|avi|mov|mkv|webm|flv|m4v|3gp|wmv|ogv|mpg|mpeg|m2v|divx)(\?.*)?$',
                # Additional video formats
                r'.*\.(ts|mts|m2ts|vob|asf|rm|rmvb|f4v)(\?.*)?$',
            ],
            'domain_aliases': [],
            'normalize_template': None  # Direct links are kept as-is
        }
    }
    
    @classmethod
    def detect_platform(cls, url: str) -> Optional[str]:
        """
        Detect the platform from a given URL.
        
        Args:
            url: The video URL to analyze
            
        Returns:
            Platform name if detected, None otherwise
        """
        if not url or not isinstance(url, str):
            return None
            
        url = url.strip()
        if not url:
            return None
        
        # Normalize URL for detection
        normalized_url = cls._preprocess_url(url)
        
        for platform, config in cls.PLATFORM_PATTERNS.items():
            for pattern in config['patterns']:
                if re.search(pattern, normalized_url, re.IGNORECASE):
                    return platform
        
        return None
    
    @classmethod
    def extract_platform_info(cls, url: str) -> Optional[PlatformInfo]:
        """
        Extract comprehensive platform information from URL.
        
        Args:
            url: The video URL to analyze
            
        Returns:
            PlatformInfo object if successful, None otherwise
        """
        if not url or not isinstance(url, str):
            return None
            
        original_url = url.strip()
        if not original_url:
            return None
        
        # Preprocess URL
        processed_url = cls._preprocess_url(original_url)
        
        # Detect platform
        platform = cls.detect_platform(processed_url)
        if not platform:
            return None
        
        # Extract video ID and metadata
        video_id, metadata = cls._extract_video_info(processed_url, platform)
        
        # Generate normalized URL
        normalized_url = cls._normalize_url(processed_url, platform, video_id, metadata)
        
        return PlatformInfo(
            name=platform,
            video_id=video_id,
            normalized_url=normalized_url,
            original_url=original_url,
            metadata=metadata
        )
    
    @classmethod
    def validate_url(cls, url: str) -> Dict[str, any]:
        """
        Comprehensive URL validation with detailed results.
        
        Args:
            url: The video URL to validate
            
        Returns:
            Dictionary containing validation results and platform info
        """
        result = {
            'is_valid': False,
            'platform': None,
            'video_id': None,
            'normalized_url': None,
            'original_url': url,
            'metadata': {},
            'error': None,
            'warnings': []
        }
        
        if not url or not isinstance(url, str):
            result['error'] = 'URL must be a non-empty string'
            return result
        
        url = url.strip()
        if not url:
            result['error'] = 'URL cannot be empty'
            return result
        
        # Basic URL format validation
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f'https://{url}'
                parsed = urlparse(url)
                result['warnings'].append('Added https:// scheme to URL')
            
            if not parsed.netloc:
                result['error'] = 'Invalid URL format: missing domain'
                return result
                
        except Exception as e:
            result['error'] = f'Invalid URL format: {str(e)}'
            return result
        
        # Extract platform information
        platform_info = cls.extract_platform_info(url)
        if not platform_info:
            result['error'] = 'Unsupported platform or invalid URL format'
            return result
        
        # Update result with platform information
        result.update({
            'is_valid': True,
            'platform': platform_info.name,
            'video_id': platform_info.video_id,
            'normalized_url': platform_info.normalized_url,
            'metadata': platform_info.metadata
        })
        
        return result
    
    @classmethod
    def normalize_url(cls, url: str) -> Optional[str]:
        """
        Normalize URL to standard format for the detected platform.
        
        Args:
            url: The video URL to normalize
            
        Returns:
            Normalized URL if successful, None otherwise
        """
        platform_info = cls.extract_platform_info(url)
        return platform_info.normalized_url if platform_info else None
    
    @classmethod
    def get_supported_platforms(cls) -> List[str]:
        """Get list of all supported platforms."""
        return list(cls.PLATFORM_PATTERNS.keys())
    
    @classmethod
    def is_platform_supported(cls, platform: str) -> bool:
        """Check if a platform is supported."""
        return platform.lower() in cls.PLATFORM_PATTERNS
    
    @classmethod
    def get_platform_domains(cls, platform: str) -> List[str]:
        """Get list of domains for a specific platform."""
        config = cls.PLATFORM_PATTERNS.get(platform.lower(), {})
        return config.get('domain_aliases', [])
    
    @classmethod
    def is_direct_video_link(cls, url: str) -> bool:
        """
        Check if URL is a direct video file link.
        
        Args:
            url: The URL to check
            
        Returns:
            True if it's a direct video link, False otherwise
        """
        return cls.detect_platform(url) == 'direct'
    
    @classmethod
    def get_video_extension(cls, url: str) -> Optional[str]:
        """
        Extract video file extension from direct video links.
        
        Args:
            url: The video URL
            
        Returns:
            File extension if it's a direct link, None otherwise
        """
        if not cls.is_direct_video_link(url):
            return None
        
        # Extract extension from URL
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Common video extensions
        video_extensions = [
            '.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.m4v', 
            '.3gp', '.wmv', '.ogv', '.mpg', '.mpeg', '.m2v', '.divx',
            '.ts', '.mts', '.m2ts', '.vob', '.asf', '.rm', '.rmvb', '.f4v'
        ]
        
        for ext in video_extensions:
            if path.endswith(ext):
                return ext
        
        return None
    
    @classmethod
    def _preprocess_url(cls, url: str) -> str:
        """Preprocess URL for consistent detection."""
        # Remove common tracking parameters
        url = re.sub(r'[?&]utm_[^&]*', '', url)
        url = re.sub(r'[?&]fbclid=[^&]*', '', url)
        url = re.sub(r'[?&]gclid=[^&]*', '', url)
        
        # Decode URL if needed
        url = unquote(url)
        
        # Normalize protocol
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        return url.strip()
    
    @classmethod
    def _extract_video_info(cls, url: str, platform: str) -> Tuple[Optional[str], Dict[str, any]]:
        """Extract video ID and metadata from URL."""
        config = cls.PLATFORM_PATTERNS.get(platform, {})
        patterns = config.get('patterns', [])
        metadata = {}
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Handle different group patterns
                if platform == 'twitter' and len(groups) >= 2:
                    # Twitter has username and tweet ID
                    metadata['username'] = groups[0]
                    return groups[1], metadata
                elif platform == 'reddit' and len(groups) >= 2:
                    # Reddit has subreddit and post ID
                    metadata['subreddit'] = groups[0]
                    return groups[1], metadata
                elif platform == 'tiktok' and 'video' in pattern:
                    # TikTok video pattern has username and video ID
                    if len(groups) >= 2:
                        metadata['username'] = groups[0]
                        return groups[1], metadata
                    else:
                        return groups[0], metadata
                else:
                    # Most platforms just have video ID
                    return groups[0], metadata
        
        return None, metadata
    
    @classmethod
    def _normalize_url(cls, url: str, platform: str, video_id: Optional[str], metadata: Dict[str, any]) -> str:
        """Generate normalized URL for the platform."""
        config = cls.PLATFORM_PATTERNS.get(platform, {})
        template = config.get('normalize_template')
        
        if not template or not video_id:
            return url
        
        try:
            return template.format(video_id=video_id, **metadata)
        except (KeyError, ValueError):
            return url


# Convenience functions for backward compatibility
def detect_platform(url: str) -> Optional[str]:
    """Detect platform from URL."""
    return PlatformDetector.detect_platform(url)


def validate_video_url(url: str) -> Dict[str, any]:
    """Validate video URL."""
    return PlatformDetector.validate_url(url)


def normalize_url(url: str) -> Optional[str]:
    """Normalize URL to standard format."""
    return PlatformDetector.normalize_url(url)


def get_supported_platforms() -> List[str]:
    """Get list of supported platforms."""
    return PlatformDetector.get_supported_platforms()


def is_direct_video_link(url: str) -> bool:
    """Check if URL is a direct video link."""
    return PlatformDetector.is_direct_video_link(url)


def get_video_extension(url: str) -> Optional[str]:
    """Get video file extension from direct links."""
    return PlatformDetector.get_video_extension(url)


# Platform-specific validation functions
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