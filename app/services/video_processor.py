"""
Video metadata extraction service for VidNet MVP.

This module provides video metadata extraction using yt-dlp with platform-specific
configurations and comprehensive error handling.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import yt_dlp
import re
from urllib.parse import urlparse

from app.services.platform_detector import PlatformDetector
from app.models.video import VideoMetadata, VideoQuality
from app.core.exceptions import (
    VidNetException, UnsupportedPlatformError, VideoNotFoundError, 
    ExtractionError, NetworkError, ProcessingTimeoutError, classify_yt_dlp_error
)
from app.core.retry import retry_async


# Configure logging
logger = logging.getLogger(__name__)


# Keep backward compatibility with old exception names
class VideoProcessorError(VidNetException):
    """Base exception for video processing errors - deprecated, use VidNetException."""
    pass


class VideoProcessor:
    """
    Video metadata extraction service using yt-dlp.
    
    Handles metadata extraction from multiple platforms without downloading videos.
    Includes platform-specific configurations and comprehensive error handling.
    """
    
    def __init__(self):
        """Initialize the video processor with platform-specific configurations."""
        self.platform_detector = PlatformDetector()
        
        # Base yt-dlp options for metadata extraction only
        self.base_opts = {
            'quiet': True,
            'no_warnings': False,
            'extractaudio': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'writedescription': False,
            'writeinfojson': False,
            'writethumbnail': False,
            'simulate': True,  # Don't download, just extract info
            'skip_download': True,
            'format': 'best',
            'socket_timeout': 30,
            'retries': 3,
        }
        
        # Platform-specific configurations
        self.platform_configs = {
            'youtube': {
                'format': 'best[height<=?2160]',
                'extract_flat': False,
                'youtube_include_dash_manifest': True,
                'writesubtitles': False,
                'writeautomaticsub': False,
            },
            'tiktok': {
                'format': 'best',
                'extract_flat': False,
            },
            'instagram': {
                'format': 'best',
                'extract_flat': False,
            },
            'facebook': {
                'format': 'best',
                'extract_flat': False,
            },
            'twitter': {
                'format': 'best',
                'extract_flat': False,
            },
            'reddit': {
                'format': 'best',
                'extract_flat': False,
            },
            'vimeo': {
                'format': 'best[height<=?2160]',
                'extract_flat': False,
            },
            'direct': {
                'format': 'best',
                'extract_flat': False,
            }
        }
    
    @retry_async(max_attempts=3, base_delay=1.0, retryable_exceptions=[NetworkError, ProcessingTimeoutError])
    async def extract_metadata(self, url: str) -> VideoMetadata:
        """
        Extract video metadata from URL without downloading.
        
        Args:
            url: Video URL to extract metadata from
            
        Returns:
            VideoMetadata object with extracted information
            
        Raises:
            UnsupportedPlatformError: If platform is not supported
            VideoNotFoundError: If video cannot be found
            ExtractionError: If metadata extraction fails
        """
        try:
            # Validate and detect platform
            platform_info = self.platform_detector.extract_platform_info(url)
            if not platform_info:
                raise UnsupportedPlatformError(platform="unknown")
            
            platform = platform_info.name
            logger.info(f"Extracting metadata for {platform} video: {url}")
            
            # Get platform-specific configuration
            platform_config = self.platform_configs.get(platform, {})
            
            # Merge base options with platform-specific options
            ydl_opts = {**self.base_opts, **platform_config}
            
            # Handle direct video links differently
            if platform == 'direct':
                return await self._handle_direct_link(url, platform_info)
            
            # Extract metadata using yt-dlp
            metadata = await self._extract_with_ytdlp(url, ydl_opts)
            
            # Convert to our VideoMetadata model
            return self._convert_to_video_metadata(metadata, platform, url)
            
        except (UnsupportedPlatformError, VideoNotFoundError, ExtractionError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error extracting metadata from {url}: {str(e)}")
            raise ExtractionError(reason=str(e))
    
    async def _extract_with_ytdlp(self, url: str, ydl_opts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata using yt-dlp in a separate thread.
        
        Args:
            url: Video URL
            ydl_opts: yt-dlp options
            
        Returns:
            Raw metadata dictionary from yt-dlp
            
        Raises:
            VideoNotFoundError: If video cannot be found
            ExtractionError: If extraction fails
        """
        def _extract():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            except yt_dlp.DownloadError as e:
                # Use the new error classification system
                raise classify_yt_dlp_error(str(e))
            except Exception as e:
                raise ExtractionError(reason=f"Unexpected yt-dlp error: {str(e)}")
        
        try:
            # Run yt-dlp in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Add timeout to prevent hanging
            metadata = await asyncio.wait_for(
                loop.run_in_executor(None, _extract),
                timeout=30.0  # 30 second timeout
            )
            
            if not metadata:
                raise ExtractionError(reason="No metadata returned from yt-dlp")
            
            return metadata
            
        except asyncio.TimeoutError:
            raise ProcessingTimeoutError(timeout_seconds=30)
        except (VideoNotFoundError, UnsupportedPlatformError, ExtractionError):
            raise
        except Exception as e:
            logger.error(f"Error running yt-dlp extraction: {str(e)}")
            raise ExtractionError(reason=f"Failed to extract metadata: {str(e)}")
    
    async def _handle_direct_link(self, url: str, platform_info) -> VideoMetadata:
        """
        Handle direct video file links.
        
        Args:
            url: Direct video URL
            platform_info: Platform information from detector
            
        Returns:
            VideoMetadata for direct link
        """
        try:
            # For direct links, we have limited metadata
            parsed_url = urlparse(url)
            filename = parsed_url.path.split('/')[-1]
            title = filename.rsplit('.', 1)[0] if '.' in filename else filename
            
            # Get file extension
            extension = self.platform_detector.get_video_extension(url)
            if not extension:
                extension = '.mp4'  # Default fallback
            
            # Create basic quality info (we can't know actual quality without downloading)
            available_qualities = [
                VideoQuality(
                    quality="720p",  # Default assumption for direct links
                    format=extension.lstrip('.'),
                    filesize=None,
                    fps=None
                )
            ]
            
            return VideoMetadata(
                title=title or "Direct Video Link",
                thumbnail="https://via.placeholder.com/320x180/000000/FFFFFF?text=Video",  # Placeholder for direct links
                duration=0,  # Unknown duration
                platform="direct",
                available_qualities=available_qualities,
                audio_available=True,  # Assume audio is available
                file_extension=extension,
                original_url=url
            )
            
        except Exception as e:
            logger.error(f"Error handling direct link {url}: {str(e)}")
            raise ExtractionError(reason=f"Failed to process direct link: {str(e)}")
    
    def _convert_to_video_metadata(self, metadata: Dict[str, Any], platform: str, original_url: str) -> VideoMetadata:
        """
        Convert yt-dlp metadata to VideoMetadata model.
        
        Args:
            metadata: Raw metadata from yt-dlp
            platform: Detected platform name
            original_url: Original video URL
            
        Returns:
            VideoMetadata object
        """
        try:
            # Extract basic information
            title = metadata.get('title', 'Unknown Title')
            thumbnail = metadata.get('thumbnail', '')
            duration = metadata.get('duration', 0) or 0
            
            # Extract available formats and qualities
            available_qualities = self._extract_quality_options(metadata)
            
            # Check if audio is available
            audio_available = self._check_audio_availability(metadata)
            
            return VideoMetadata(
                title=title,
                thumbnail=thumbnail,
                duration=int(duration),
                platform=platform,
                available_qualities=available_qualities,
                audio_available=audio_available,
                file_extension=None,
                original_url=original_url
            )
            
        except Exception as e:
            logger.error(f"Error converting metadata: {str(e)}")
            raise ExtractionError(reason=f"Failed to convert metadata: {str(e)}")
    
    def _extract_quality_options(self, metadata: Dict[str, Any]) -> List[VideoQuality]:
        """
        Extract available quality options from yt-dlp metadata.
        
        Args:
            metadata: Raw metadata from yt-dlp
            
        Returns:
            List of VideoQuality objects
        """
        qualities = []
        formats = metadata.get('formats', [])
        
        if not formats:
            # Fallback if no formats available
            return [VideoQuality(quality="720p", format="mp4", filesize=None, fps=None)]
        
        # Group formats by quality and select best for each
        quality_map = {}
        
        for fmt in formats:
            if not fmt.get('vcodec') or fmt.get('vcodec') == 'none':
                continue  # Skip audio-only formats
            
            height = fmt.get('height')
            if not height:
                continue
            
            # Determine quality label
            quality_label = self._get_quality_label(height)
            
            # Get format info
            ext = fmt.get('ext', 'mp4')
            filesize = fmt.get('filesize')
            fps = fmt.get('fps')
            
            # Keep the best format for each quality
            if quality_label not in quality_map or (filesize and filesize > quality_map[quality_label].filesize):
                quality_map[quality_label] = VideoQuality(
                    quality=quality_label,
                    format=ext,
                    filesize=filesize,
                    fps=fps
                )
        
        # Convert to list and sort by quality
        qualities = list(quality_map.values())
        
        # Sort by quality (highest first)
        quality_order = {'4K': 0, '2160p': 0, '1440p': 1, '1080p': 2, '720p': 3, '480p': 4, '360p': 5, '240p': 6, '144p': 7}
        qualities.sort(key=lambda q: quality_order.get(q.quality, 999))
        
        return qualities if qualities else [VideoQuality(quality="720p", format="mp4", filesize=None, fps=None)]
    
    def _get_quality_label(self, height: int) -> str:
        """
        Convert height to quality label.
        
        Args:
            height: Video height in pixels
            
        Returns:
            Quality label string
        """
        if height >= 2160:
            return '4K'
        elif height >= 1440:
            return '1440p'
        elif height >= 1080:
            return '1080p'
        elif height >= 720:
            return '720p'
        elif height >= 480:
            return '480p'
        elif height >= 360:
            return '360p'
        elif height >= 240:
            return '240p'
        else:
            return '144p'
    
    def _check_audio_availability(self, metadata: Dict[str, Any]) -> bool:
        """
        Check if audio track is available in the video.
        
        Args:
            metadata: Raw metadata from yt-dlp
            
        Returns:
            True if audio is available, False otherwise
        """
        formats = metadata.get('formats', [])
        
        # Check if any format has audio
        for fmt in formats:
            if fmt.get('acodec') and fmt.get('acodec') != 'none':
                return True
        
        # Also check the main format
        if metadata.get('acodec') and metadata.get('acodec') != 'none':
            return True
        
        return False
    
    async def get_supported_platforms(self) -> List[str]:
        """
        Get list of all supported platforms.
        
        Returns:
            List of supported platform names
        """
        return self.platform_detector.get_supported_platforms()
    
    async def validate_url(self, url: str) -> Dict[str, Any]:
        """
        Validate URL and return platform information.
        
        Args:
            url: URL to validate
            
        Returns:
            Validation result dictionary
        """
        return self.platform_detector.validate_url(url)


# Convenience functions for backward compatibility
async def extract_video_metadata(url: str) -> VideoMetadata:
    """
    Extract video metadata from URL.
    
    Args:
        url: Video URL
        
    Returns:
        VideoMetadata object
    """
    processor = VideoProcessor()
    return await processor.extract_metadata(url)


async def get_supported_platforms() -> List[str]:
    """Get list of supported platforms."""
    processor = VideoProcessor()
    return await processor.get_supported_platforms()


async def validate_video_url(url: str) -> Dict[str, Any]:
    """Validate video URL."""
    processor = VideoProcessor()
    return await processor.validate_url(url)