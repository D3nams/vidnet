"""
Unit tests for platform detection and URL processing system.

This module tests the comprehensive platform detection functionality
for all supported video platforms.
"""

import pytest
from app.services.platform_detector import (
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


class TestPlatformDetector:
    """Test cases for the PlatformDetector class."""
    
    def test_detect_platform_youtube(self):
        """Test YouTube URL detection."""
        youtube_urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtu.be/dQw4w9WgXcQ',
            'https://youtube.com/watch?v=dQw4w9WgXcQ',
            'https://www.youtube.com/embed/dQw4w9WgXcQ',
            'https://www.youtube.com/v/dQw4w9WgXcQ',
            'https://www.youtube.com/shorts/dQw4w9WgXcQ',
            'https://music.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://www.youtube.com/live/dQw4w9WgXcQ',
            'youtube.com/watch?v=dQw4w9WgXcQ',  # Without protocol
            'www.youtube.com/watch?v=dQw4w9WgXcQ',  # Without protocol
        ]
        
        for url in youtube_urls:
            assert PlatformDetector.detect_platform(url) == 'youtube', f"Failed for URL: {url}"
    
    def test_detect_platform_tiktok(self):
        """Test TikTok URL detection."""
        tiktok_urls = [
            'https://www.tiktok.com/@username/video/1234567890123456789',
            'https://tiktok.com/@user.name/video/9876543210987654321',
            'https://vm.tiktok.com/ZMeAbCdEf',
            'https://vt.tiktok.com/ZSAbCdEfG',
            'https://www.tiktok.com/t/ZTAbCdEfH',
            'https://m.tiktok.com/v/1234567890123456789',
            'tiktok.com/@username/video/1234567890123456789',  # Without protocol
        ]
        
        for url in tiktok_urls:
            assert PlatformDetector.detect_platform(url) == 'tiktok', f"Failed for URL: {url}"
    
    def test_detect_platform_instagram(self):
        """Test Instagram URL detection."""
        instagram_urls = [
            'https://www.instagram.com/p/ABC123DEF456/',
            'https://instagram.com/p/XYZ789GHI012/',
            'https://www.instagram.com/reel/DEF456ABC123/',
            'https://www.instagram.com/tv/GHI789DEF456/',
            'https://www.instagram.com/stories/username/1234567890',
            'instagram.com/p/ABC123DEF456/',  # Without protocol
        ]
        
        for url in instagram_urls:
            assert PlatformDetector.detect_platform(url) == 'instagram', f"Failed for URL: {url}"
    
    def test_detect_platform_facebook(self):
        """Test Facebook URL detection."""
        facebook_urls = [
            'https://www.facebook.com/watch/?v=1234567890123456',
            'https://facebook.com/watch?v=9876543210987654',
            'https://www.facebook.com/username/videos/1234567890123456',
            'https://www.facebook.com/video.php?v=1234567890123456',
            'https://fb.watch/AbCdEfGhIj',
            'https://m.facebook.com/watch/?v=1234567890123456',
            'facebook.com/watch/?v=1234567890123456',  # Without protocol
        ]
        
        for url in facebook_urls:
            assert PlatformDetector.detect_platform(url) == 'facebook', f"Failed for URL: {url}"
    
    def test_detect_platform_twitter(self):
        """Test Twitter/X URL detection."""
        twitter_urls = [
            'https://twitter.com/username/status/1234567890123456789',
            'https://www.twitter.com/user_name/status/9876543210987654321',
            'https://x.com/username/status/1234567890123456789',
            'https://www.x.com/user_name/status/9876543210987654321',
            'https://twitter.com/i/web/status/1234567890123456789',
            'https://x.com/i/web/status/9876543210987654321',
            'https://mobile.twitter.com/username/status/1234567890123456789',
            'twitter.com/username/status/1234567890123456789',  # Without protocol
        ]
        
        for url in twitter_urls:
            assert PlatformDetector.detect_platform(url) == 'twitter', f"Failed for URL: {url}"
    
    def test_detect_platform_reddit(self):
        """Test Reddit URL detection."""
        reddit_urls = [
            'https://www.reddit.com/r/videos/comments/abc123/title_here/',
            'https://reddit.com/r/funny/comments/xyz789/another_title/',
            'https://v.redd.it/abcdef123456',
            'https://old.reddit.com/r/videos/comments/abc123/title_here/',
            'https://m.reddit.com/r/videos/comments/abc123/title_here/',
            'reddit.com/r/videos/comments/abc123/title_here/',  # Without protocol
        ]
        
        for url in reddit_urls:
            assert PlatformDetector.detect_platform(url) == 'reddit', f"Failed for URL: {url}"
    
    def test_detect_platform_vimeo(self):
        """Test Vimeo URL detection."""
        vimeo_urls = [
            'https://vimeo.com/123456789',
            'https://www.vimeo.com/987654321',
            'https://player.vimeo.com/video/123456789',
            'https://vimeo.com/ondemand/movie-name/123456789',
            'https://vimeo.com/channels/channel-name/123456789',
            'vimeo.com/123456789',  # Without protocol
        ]
        
        for url in vimeo_urls:
            assert PlatformDetector.detect_platform(url) == 'vimeo', f"Failed for URL: {url}"
    
    def test_detect_platform_direct_video_links(self):
        """Test direct video link detection."""
        direct_urls = [
            'https://example.com/video.mp4',
            'https://cdn.example.com/path/to/video.avi',
            'https://storage.example.com/videos/movie.mov',
            'https://files.example.com/content.mkv',
            'https://media.example.com/stream.webm',
            'https://assets.example.com/clip.flv',
            'https://example.com/video.m4v',
            'https://example.com/video.3gp',
            'https://example.com/video.wmv',
            'https://example.com/video.ogv',
            'https://example.com/video.mpg',
            'https://example.com/video.mpeg',
            'https://example.com/video.ts',
            'https://example.com/video.mp4?param=value',  # With query parameters
            'example.com/video.mp4',  # Without protocol
        ]
        
        for url in direct_urls:
            assert PlatformDetector.detect_platform(url) == 'direct', f"Failed for URL: {url}"
    
    def test_detect_platform_unsupported(self):
        """Test detection of unsupported platforms."""
        unsupported_urls = [
            'https://example.com/page',
            'https://unsupported-platform.com/video/123',
            'https://google.com',
            'not-a-url',
            '',
            None,
        ]
        
        for url in unsupported_urls:
            assert PlatformDetector.detect_platform(url) is None, f"Should be None for URL: {url}"
    
    def test_extract_platform_info_youtube(self):
        """Test extracting platform info for YouTube URLs."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        info = PlatformDetector.extract_platform_info(url)
        
        assert info is not None
        assert info.name == 'youtube'
        assert info.video_id == 'dQw4w9WgXcQ'
        assert info.normalized_url == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        assert info.original_url == url
    
    def test_extract_platform_info_tiktok_with_username(self):
        """Test extracting platform info for TikTok URLs with username."""
        url = 'https://www.tiktok.com/@username/video/1234567890123456789'
        info = PlatformDetector.extract_platform_info(url)
        
        assert info is not None
        assert info.name == 'tiktok'
        assert info.video_id == '1234567890123456789'
        assert 'username' in info.metadata
        assert info.metadata['username'] == 'username'
    
    def test_extract_platform_info_twitter_with_username(self):
        """Test extracting platform info for Twitter URLs with username."""
        url = 'https://twitter.com/username/status/1234567890123456789'
        info = PlatformDetector.extract_platform_info(url)
        
        assert info is not None
        assert info.name == 'twitter'
        assert info.video_id == '1234567890123456789'
        assert 'username' in info.metadata
        assert info.metadata['username'] == 'username'
    
    def test_extract_platform_info_reddit_with_subreddit(self):
        """Test extracting platform info for Reddit URLs with subreddit."""
        url = 'https://www.reddit.com/r/videos/comments/abc123/title_here/'
        info = PlatformDetector.extract_platform_info(url)
        
        assert info is not None
        assert info.name == 'reddit'
        assert info.video_id == 'abc123'
        assert 'subreddit' in info.metadata
        assert info.metadata['subreddit'] == 'videos'
    
    def test_validate_url_valid(self):
        """Test URL validation for valid URLs."""
        valid_urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://www.tiktok.com/@username/video/1234567890123456789',
            'https://example.com/video.mp4',
        ]
        
        for url in valid_urls:
            result = PlatformDetector.validate_url(url)
            assert result['is_valid'] is True, f"Should be valid for URL: {url}"
            assert result['platform'] is not None
            assert result['error'] is None
    
    def test_validate_url_invalid(self):
        """Test URL validation for invalid URLs."""
        invalid_urls = [
            '',
            None,
            'not-a-url',
            'https://unsupported-platform.com/video/123',
        ]
        
        for url in invalid_urls:
            result = PlatformDetector.validate_url(url)
            assert result['is_valid'] is False, f"Should be invalid for URL: {url}"
            assert result['error'] is not None
    
    def test_validate_url_adds_https(self):
        """Test that validation adds https:// to URLs without protocol."""
        url = 'youtube.com/watch?v=dQw4w9WgXcQ'
        result = PlatformDetector.validate_url(url)
        
        assert result['is_valid'] is True
        assert 'Added https:// scheme to URL' in result['warnings']
    
    def test_normalize_url_youtube(self):
        """Test URL normalization for YouTube."""
        test_cases = [
            ('https://youtu.be/dQw4w9WgXcQ', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
            ('https://www.youtube.com/embed/dQw4w9WgXcQ', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
            ('https://www.youtube.com/shorts/dQw4w9WgXcQ', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
        ]
        
        for original, expected in test_cases:
            normalized = PlatformDetector.normalize_url(original)
            assert normalized == expected, f"Failed for {original}: got {normalized}, expected {expected}"
    
    def test_normalize_url_instagram(self):
        """Test URL normalization for Instagram."""
        original = 'https://www.instagram.com/reel/ABC123DEF456/'
        expected = 'https://www.instagram.com/p/ABC123DEF456/'
        normalized = PlatformDetector.normalize_url(original)
        assert normalized == expected
    
    def test_normalize_url_facebook(self):
        """Test URL normalization for Facebook."""
        original = 'https://fb.watch/AbCdEfGhIj'
        expected = 'https://www.facebook.com/watch/?v=AbCdEfGhIj'
        normalized = PlatformDetector.normalize_url(original)
        assert normalized == expected
    
    def test_normalize_url_vimeo(self):
        """Test URL normalization for Vimeo."""
        original = 'https://player.vimeo.com/video/123456789'
        expected = 'https://vimeo.com/123456789'
        normalized = PlatformDetector.normalize_url(original)
        assert normalized == expected
    
    def test_normalize_url_keeps_complex_urls(self):
        """Test that complex URLs (TikTok, Reddit) are kept as-is."""
        complex_urls = [
            'https://www.tiktok.com/@username/video/1234567890123456789',
            'https://www.reddit.com/r/videos/comments/abc123/title_here/',
        ]
        
        for url in complex_urls:
            normalized = PlatformDetector.normalize_url(url)
            assert normalized == url, f"Complex URL should remain unchanged: {url}"
    
    def test_get_supported_platforms(self):
        """Test getting list of supported platforms."""
        platforms = PlatformDetector.get_supported_platforms()
        expected_platforms = ['youtube', 'tiktok', 'instagram', 'facebook', 'twitter', 'reddit', 'vimeo', 'direct']
        
        assert isinstance(platforms, list)
        assert len(platforms) == len(expected_platforms)
        for platform in expected_platforms:
            assert platform in platforms
    
    def test_is_platform_supported(self):
        """Test checking if platforms are supported."""
        supported_platforms = ['youtube', 'tiktok', 'instagram', 'facebook', 'twitter', 'reddit', 'vimeo', 'direct']
        unsupported_platforms = ['dailymotion', 'twitch', 'unknown']
        
        for platform in supported_platforms:
            assert PlatformDetector.is_platform_supported(platform) is True
        
        for platform in unsupported_platforms:
            assert PlatformDetector.is_platform_supported(platform) is False
    
    def test_get_platform_domains(self):
        """Test getting platform domains."""
        youtube_domains = PlatformDetector.get_platform_domains('youtube')
        assert 'youtube.com' in youtube_domains
        assert 'youtu.be' in youtube_domains
        
        tiktok_domains = PlatformDetector.get_platform_domains('tiktok')
        assert 'tiktok.com' in tiktok_domains
        assert 'vm.tiktok.com' in tiktok_domains
    
    def test_is_direct_video_link(self):
        """Test direct video link detection."""
        direct_links = [
            'https://example.com/video.mp4',
            'https://cdn.example.com/movie.avi',
            'https://storage.example.com/clip.mov',
        ]
        
        non_direct_links = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://example.com/page.html',
        ]
        
        for url in direct_links:
            assert PlatformDetector.is_direct_video_link(url) is True, f"Should be direct link: {url}"
        
        for url in non_direct_links:
            assert PlatformDetector.is_direct_video_link(url) is False, f"Should not be direct link: {url}"
    
    def test_get_video_extension(self):
        """Test video extension extraction from direct links."""
        test_cases = [
            ('https://example.com/video.mp4', '.mp4'),
            ('https://example.com/movie.avi', '.avi'),
            ('https://example.com/clip.mov', '.mov'),
            ('https://example.com/video.mkv', '.mkv'),
            ('https://example.com/stream.webm', '.webm'),
            ('https://example.com/video.mp4?param=value', '.mp4'),
            ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', None),  # Not a direct link
        ]
        
        for url, expected_ext in test_cases:
            ext = PlatformDetector.get_video_extension(url)
            assert ext == expected_ext, f"Failed for {url}: got {ext}, expected {expected_ext}"
    
    def test_preprocess_url(self):
        """Test URL preprocessing functionality."""
        # Test tracking parameter removal
        url_with_tracking = 'https://youtube.com/watch?v=dQw4w9WgXcQ&utm_source=test&fbclid=123'
        processed = PlatformDetector._preprocess_url(url_with_tracking)
        assert 'utm_source' not in processed
        assert 'fbclid' not in processed
        assert 'v=dQw4w9WgXcQ' in processed
        
        # Test protocol addition
        url_without_protocol = 'youtube.com/watch?v=dQw4w9WgXcQ'
        processed = PlatformDetector._preprocess_url(url_without_protocol)
        assert processed.startswith('https://')


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_detect_platform_function(self):
        """Test the detect_platform convenience function."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        platform = detect_platform(url)
        assert platform == 'youtube'
    
    def test_validate_video_url_function(self):
        """Test the validate_video_url convenience function."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        result = validate_video_url(url)
        assert result['is_valid'] is True
        assert result['platform'] == 'youtube'
    
    def test_normalize_url_function(self):
        """Test the normalize_url convenience function."""
        url = 'https://youtu.be/dQw4w9WgXcQ'
        normalized = normalize_url(url)
        assert normalized == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    
    def test_get_supported_platforms_function(self):
        """Test the get_supported_platforms convenience function."""
        platforms = get_supported_platforms()
        assert 'youtube' in platforms
        assert 'tiktok' in platforms
        assert isinstance(platforms, list)
    
    def test_is_direct_video_link_function(self):
        """Test the is_direct_video_link convenience function."""
        assert is_direct_video_link('https://example.com/video.mp4') is True
        assert is_direct_video_link('https://youtube.com/watch?v=123') is False
    
    def test_get_video_extension_function(self):
        """Test the get_video_extension convenience function."""
        assert get_video_extension('https://example.com/video.mp4') == '.mp4'
        assert get_video_extension('https://youtube.com/watch?v=123') is None
    
    def test_platform_specific_validators(self):
        """Test platform-specific validation functions."""
        # YouTube
        assert validate_youtube_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is True
        assert validate_youtube_url('https://www.tiktok.com/@user/video/123') is False
        
        # TikTok
        assert validate_tiktok_url('https://www.tiktok.com/@user/video/123') is True
        assert validate_tiktok_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Instagram
        assert validate_instagram_url('https://www.instagram.com/p/ABC123/') is True
        assert validate_instagram_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Facebook
        assert validate_facebook_url('https://www.facebook.com/watch/?v=123') is True
        assert validate_facebook_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Twitter
        assert validate_twitter_url('https://twitter.com/user/status/123') is True
        assert validate_twitter_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Reddit
        assert validate_reddit_url('https://reddit.com/r/videos/comments/abc123/') is True
        assert validate_reddit_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Vimeo
        assert validate_vimeo_url('https://vimeo.com/123456789') is True
        assert validate_vimeo_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False


class TestEdgeCases:
    """Test cases for edge cases and error conditions."""
    
    def test_empty_and_none_inputs(self):
        """Test handling of empty and None inputs."""
        empty_inputs = [None, '', '   ', '\t\n']
        
        for input_val in empty_inputs:
            assert PlatformDetector.detect_platform(input_val) is None
            assert PlatformDetector.extract_platform_info(input_val) is None
            assert PlatformDetector.normalize_url(input_val) is None
            
            result = PlatformDetector.validate_url(input_val)
            assert result['is_valid'] is False
            assert result['error'] is not None
    
    def test_malformed_urls(self):
        """Test handling of malformed URLs."""
        malformed_urls = [
            'not-a-url',
            'http://',
            'https://',
            'ftp://example.com/video.mp4',
            'javascript:alert("test")',
        ]
        
        for url in malformed_urls:
            result = PlatformDetector.validate_url(url)
            # Most should be invalid, but some might be handled gracefully
            if not result['is_valid']:
                assert result['error'] is not None
    
    def test_urls_with_special_characters(self):
        """Test handling of URLs with special characters."""
        special_urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s',
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmRdnEQy6nuLMt9H1mu_0VtqJlyyh',
            'https://example.com/video with spaces.mp4',
            'https://example.com/видео.mp4',  # Cyrillic characters
        ]
        
        for url in special_urls:
            # Should not crash, even if not all are supported
            try:
                platform = PlatformDetector.detect_platform(url)
                # If detection succeeds, validation should also work
                if platform:
                    result = PlatformDetector.validate_url(url)
                    assert isinstance(result, dict)
            except Exception as e:
                pytest.fail(f"Should not raise exception for URL {url}: {e}")
    
    def test_very_long_urls(self):
        """Test handling of very long URLs."""
        base_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        long_params = '&' + '&'.join([f'param{i}=value{i}' for i in range(100)])
        long_url = base_url + long_params
        
        # Should still detect YouTube
        assert PlatformDetector.detect_platform(long_url) == 'youtube'
        
        result = PlatformDetector.validate_url(long_url)
        assert result['is_valid'] is True
        assert result['platform'] == 'youtube'
    
    def test_case_insensitive_detection(self):
        """Test that platform detection is case-insensitive."""
        case_variants = [
            'https://WWW.YOUTUBE.COM/watch?v=dQw4w9WgXcQ',
            'https://YouTube.com/watch?v=dQw4w9WgXcQ',
            'HTTPS://YOUTU.BE/dQw4w9WgXcQ',
        ]
        
        for url in case_variants:
            assert PlatformDetector.detect_platform(url) == 'youtube', f"Failed for: {url}"
    
    def test_international_domains(self):
        """Test handling of international domain variants."""
        # Note: These might not all be real, but testing the robustness
        international_urls = [
            'https://youtube.co.uk/watch?v=dQw4w9WgXcQ',
            'https://youtube.de/watch?v=dQw4w9WgXcQ',
        ]
        
        for url in international_urls:
            # These might not be detected as YouTube (which is correct)
            # but should not cause errors
            try:
                platform = PlatformDetector.detect_platform(url)
                result = PlatformDetector.validate_url(url)
                assert isinstance(result, dict)
            except Exception as e:
                pytest.fail(f"Should not raise exception for URL {url}: {e}")


if __name__ == '__main__':
    pytest.main([__file__])