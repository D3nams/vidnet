"""
Unit tests for video metadata extraction service.

Tests the VideoProcessor class with various platforms and error scenarios.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from app.services.video_processor import (
    VideoProcessor,
    VideoProcessorError,
    UnsupportedPlatformError,
    VideoNotFoundError,
    ExtractionError,
    extract_video_metadata,
)
from app.models.video import VideoMetadata, VideoQuality


class TestVideoProcessor:
    """Test cases for VideoProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create a VideoProcessor instance for testing."""
        return VideoProcessor()
    
    @pytest.fixture
    def mock_ytdlp_metadata(self):
        """Mock yt-dlp metadata response."""
        return {
            'title': 'Test Video Title',
            'thumbnail': 'https://example.com/thumbnail.jpg',
            'duration': 180,
            'formats': [
                {
                    'format_id': '720p',
                    'ext': 'mp4',
                    'height': 720,
                    'width': 1280,
                    'filesize': 50000000,
                    'fps': 30,
                    'vcodec': 'h264',
                    'acodec': 'aac'
                },
                {
                    'format_id': '1080p',
                    'ext': 'mp4',
                    'height': 1080,
                    'width': 1920,
                    'filesize': 100000000,
                    'fps': 30,
                    'vcodec': 'h264',
                    'acodec': 'aac'
                },
                {
                    'format_id': 'audio_only',
                    'ext': 'mp3',
                    'vcodec': 'none',
                    'acodec': 'mp3'
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_extract_metadata_youtube_success(self, processor, mock_ytdlp_metadata):
        """Test successful metadata extraction from YouTube."""
        youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        with patch.object(processor, '_extract_with_ytdlp', return_value=mock_ytdlp_metadata):
            metadata = await processor.extract_metadata(youtube_url)
            
            assert isinstance(metadata, VideoMetadata)
            assert metadata.title == "Test Video Title"
            assert metadata.platform == "youtube"
            assert metadata.duration == 180
            assert metadata.audio_available is True
            assert len(metadata.available_qualities) == 2  # Should exclude audio-only format
            assert metadata.available_qualities[0].quality == "1080p"  # Sorted highest first
            assert metadata.available_qualities[1].quality == "720p"
    
    @pytest.mark.asyncio
    async def test_extract_metadata_tiktok_success(self, processor, mock_ytdlp_metadata):
        """Test successful metadata extraction from TikTok."""
        tiktok_url = "https://www.tiktok.com/@user/video/1234567890"
        
        with patch.object(processor, '_extract_with_ytdlp', return_value=mock_ytdlp_metadata):
            metadata = await processor.extract_metadata(tiktok_url)
            
            assert isinstance(metadata, VideoMetadata)
            assert metadata.platform == "tiktok"
            assert metadata.title == "Test Video Title"
    
    @pytest.mark.asyncio
    async def test_extract_metadata_instagram_success(self, processor, mock_ytdlp_metadata):
        """Test successful metadata extraction from Instagram."""
        instagram_url = "https://www.instagram.com/p/ABC123/"
        
        with patch.object(processor, '_extract_with_ytdlp', return_value=mock_ytdlp_metadata):
            metadata = await processor.extract_metadata(instagram_url)
            
            assert isinstance(metadata, VideoMetadata)
            assert metadata.platform == "instagram"
            assert metadata.title == "Test Video Title"
    
    @pytest.mark.asyncio
    async def test_extract_metadata_facebook_success(self, processor, mock_ytdlp_metadata):
        """Test successful metadata extraction from Facebook."""
        facebook_url = "https://www.facebook.com/watch/?v=1234567890"
        
        with patch.object(processor, '_extract_with_ytdlp', return_value=mock_ytdlp_metadata):
            metadata = await processor.extract_metadata(facebook_url)
            
            assert isinstance(metadata, VideoMetadata)
            assert metadata.platform == "facebook"
            assert metadata.title == "Test Video Title"
    
    @pytest.mark.asyncio
    async def test_extract_metadata_twitter_success(self, processor, mock_ytdlp_metadata):
        """Test successful metadata extraction from Twitter/X."""
        twitter_url = "https://twitter.com/user/status/1234567890"
        
        with patch.object(processor, '_extract_with_ytdlp', return_value=mock_ytdlp_metadata):
            metadata = await processor.extract_metadata(twitter_url)
            
            assert isinstance(metadata, VideoMetadata)
            assert metadata.platform == "twitter"
            assert metadata.title == "Test Video Title"
    
    @pytest.mark.asyncio
    async def test_extract_metadata_reddit_success(self, processor, mock_ytdlp_metadata):
        """Test successful metadata extraction from Reddit."""
        reddit_url = "https://www.reddit.com/r/videos/comments/abc123/"
        
        with patch.object(processor, '_extract_with_ytdlp', return_value=mock_ytdlp_metadata):
            metadata = await processor.extract_metadata(reddit_url)
            
            assert isinstance(metadata, VideoMetadata)
            assert metadata.platform == "reddit"
            assert metadata.title == "Test Video Title"
    
    @pytest.mark.asyncio
    async def test_extract_metadata_vimeo_success(self, processor, mock_ytdlp_metadata):
        """Test successful metadata extraction from Vimeo."""
        vimeo_url = "https://vimeo.com/123456789"
        
        with patch.object(processor, '_extract_with_ytdlp', return_value=mock_ytdlp_metadata):
            metadata = await processor.extract_metadata(vimeo_url)
            
            assert isinstance(metadata, VideoMetadata)
            assert metadata.platform == "vimeo"
            assert metadata.title == "Test Video Title"
    
    @pytest.mark.asyncio
    async def test_extract_metadata_direct_link_success(self, processor):
        """Test successful metadata extraction from direct video link."""
        direct_url = "https://example.com/video.mp4"
        
        metadata = await processor.extract_metadata(direct_url)
        
        assert isinstance(metadata, VideoMetadata)
        assert metadata.platform == "direct"
        assert metadata.title == "video"
        assert metadata.file_extension == ".mp4"
        assert metadata.duration == 0  # Unknown for direct links
        assert len(metadata.available_qualities) == 1
        assert metadata.available_qualities[0].quality == "720p"
    
    @pytest.mark.asyncio
    async def test_extract_metadata_unsupported_platform(self, processor):
        """Test error handling for unsupported platform."""
        unsupported_url = "https://unsupported-platform.com/video/123"
        
        with pytest.raises(UnsupportedPlatformError):
            await processor.extract_metadata(unsupported_url)
    
    @pytest.mark.asyncio
    async def test_extract_metadata_invalid_url(self, processor):
        """Test error handling for invalid URL."""
        invalid_url = "not-a-valid-url"
        
        with pytest.raises(UnsupportedPlatformError):
            await processor.extract_metadata(invalid_url)
    
    @pytest.mark.asyncio
    async def test_extract_metadata_video_not_found(self, processor):
        """Test error handling when video is not found."""
        youtube_url = "https://www.youtube.com/watch?v=nonexistent"
        
        with patch.object(processor, '_extract_with_ytdlp', side_effect=VideoNotFoundError("Video not found")):
            with pytest.raises(VideoNotFoundError):
                await processor.extract_metadata(youtube_url)
    
    @pytest.mark.asyncio
    async def test_extract_metadata_extraction_error(self, processor):
        """Test error handling for general extraction errors."""
        youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        with patch.object(processor, '_extract_with_ytdlp', side_effect=ExtractionError("Extraction failed")):
            with pytest.raises(ExtractionError):
                await processor.extract_metadata(youtube_url)
    
    @pytest.mark.asyncio
    async def test_extract_with_ytdlp_success(self, processor, mock_ytdlp_metadata):
        """Test successful yt-dlp extraction."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ydl_opts = processor.base_opts
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.return_value = mock_ytdlp_metadata
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            result = await processor._extract_with_ytdlp(url, ydl_opts)
            
            assert result == mock_ytdlp_metadata
            mock_instance.extract_info.assert_called_once_with(url, download=False)
    
    @pytest.mark.asyncio
    async def test_extract_with_ytdlp_download_error(self, processor):
        """Test yt-dlp download error handling."""
        url = "https://www.youtube.com/watch?v=nonexistent"
        ydl_opts = processor.base_opts
        
        import yt_dlp
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = yt_dlp.DownloadError("Video not found")
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with pytest.raises(VideoNotFoundError):
                await processor._extract_with_ytdlp(url, ydl_opts)
    
    @pytest.mark.asyncio
    async def test_extract_with_ytdlp_unsupported_url_error(self, processor):
        """Test yt-dlp unsupported URL error handling."""
        url = "https://unsupported.com/video"
        ydl_opts = processor.base_opts
        
        import yt_dlp
        
        with patch('yt_dlp.YoutubeDL') as mock_ytdl:
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = yt_dlp.DownloadError("Unsupported URL")
            mock_ytdl.return_value.__enter__.return_value = mock_instance
            
            with pytest.raises(UnsupportedPlatformError):
                await processor._extract_with_ytdlp(url, ydl_opts)
    
    def test_get_quality_label(self, processor):
        """Test quality label generation from height."""
        assert processor._get_quality_label(2160) == "4K"
        assert processor._get_quality_label(1440) == "1440p"
        assert processor._get_quality_label(1080) == "1080p"
        assert processor._get_quality_label(720) == "720p"
        assert processor._get_quality_label(480) == "480p"
        assert processor._get_quality_label(360) == "360p"
        assert processor._get_quality_label(240) == "240p"
        assert processor._get_quality_label(144) == "144p"
        assert processor._get_quality_label(100) == "144p"
    
    def test_extract_quality_options(self, processor, mock_ytdlp_metadata):
        """Test quality options extraction from metadata."""
        qualities = processor._extract_quality_options(mock_ytdlp_metadata)
        
        assert len(qualities) == 2  # Should exclude audio-only format
        assert qualities[0].quality == "1080p"  # Sorted highest first
        assert qualities[1].quality == "720p"
        assert all(q.format == "mp4" for q in qualities)
    
    def test_extract_quality_options_no_formats(self, processor):
        """Test quality options extraction with no formats."""
        metadata = {'formats': []}
        
        qualities = processor._extract_quality_options(metadata)
        
        assert len(qualities) == 1
        assert qualities[0].quality == "720p"
        assert qualities[0].format == "mp4"
    
    def test_check_audio_availability_with_audio(self, processor, mock_ytdlp_metadata):
        """Test audio availability check with audio present."""
        assert processor._check_audio_availability(mock_ytdlp_metadata) is True
    
    def test_check_audio_availability_no_audio(self, processor):
        """Test audio availability check with no audio."""
        metadata = {
            'formats': [
                {'vcodec': 'h264', 'acodec': 'none'},
                {'vcodec': 'h264', 'acodec': 'none'}
            ]
        }
        
        assert processor._check_audio_availability(metadata) is False
    
    def test_convert_to_video_metadata(self, processor, mock_ytdlp_metadata):
        """Test conversion from yt-dlp metadata to VideoMetadata."""
        platform = "youtube"
        original_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        metadata = processor._convert_to_video_metadata(mock_ytdlp_metadata, platform, original_url)
        
        assert isinstance(metadata, VideoMetadata)
        assert metadata.title == "Test Video Title"
        assert metadata.platform == "youtube"
        assert metadata.duration == 180
        assert metadata.original_url == original_url
        assert metadata.audio_available is True
        assert len(metadata.available_qualities) == 2
    
    @pytest.mark.asyncio
    async def test_get_supported_platforms(self, processor):
        """Test getting supported platforms list."""
        platforms = await processor.get_supported_platforms()
        
        expected_platforms = ['youtube', 'tiktok', 'instagram', 'facebook', 'twitter', 'reddit', 'vimeo', 'direct']
        assert all(platform in platforms for platform in expected_platforms)
    
    @pytest.mark.asyncio
    async def test_validate_url(self, processor):
        """Test URL validation."""
        valid_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        result = await processor.validate_url(valid_url)
        
        assert result['is_valid'] is True
        assert result['platform'] == 'youtube'
        assert result['video_id'] == 'dQw4w9WgXcQ'


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.mark.asyncio
    async def test_extract_video_metadata_function(self):
        """Test the convenience function for extracting metadata."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        with patch('app.services.video_processor.VideoProcessor') as mock_processor_class:
            mock_processor = Mock()
            mock_processor.extract_metadata = AsyncMock(return_value=Mock(spec=VideoMetadata))
            mock_processor_class.return_value = mock_processor
            
            result = await extract_video_metadata(url)
            
            mock_processor.extract_metadata.assert_called_once_with(url)
            assert result is not None


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_platform_specific_errors(self):
        """Test platform-specific error scenarios."""
        processor = VideoProcessor()
        
        # Test various error scenarios
        error_scenarios = [
            ("https://www.youtube.com/watch?v=private_video", VideoNotFoundError),
            ("https://invalid-platform.com/video", UnsupportedPlatformError),
            ("not-a-url", UnsupportedPlatformError),
        ]
        
        for url, expected_error in error_scenarios:
            with pytest.raises(expected_error):
                await processor.extract_metadata(url)


class TestPlatformSpecificConfigurations:
    """Test platform-specific configurations."""
    
    def test_platform_configs_exist(self):
        """Test that all supported platforms have configurations."""
        processor = VideoProcessor()
        
        expected_platforms = ['youtube', 'tiktok', 'instagram', 'facebook', 'twitter', 'reddit', 'vimeo', 'direct']
        
        for platform in expected_platforms:
            assert platform in processor.platform_configs
            assert isinstance(processor.platform_configs[platform], dict)
    
    def test_youtube_config(self):
        """Test YouTube-specific configuration."""
        processor = VideoProcessor()
        youtube_config = processor.platform_configs['youtube']
        
        assert 'format' in youtube_config
        assert youtube_config['format'] == 'best[height<=?2160]'
        assert 'youtube_include_dash_manifest' in youtube_config
    
    def test_base_opts_configuration(self):
        """Test base yt-dlp options."""
        processor = VideoProcessor()
        
        assert processor.base_opts['simulate'] is True
        assert processor.base_opts['skip_download'] is True
        assert processor.base_opts['quiet'] is True
        assert processor.base_opts['retries'] == 3


if __name__ == "__main__":
    pytest.main([__file__])