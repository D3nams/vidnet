"""
Unit tests for the validators module (backward compatibility layer).

This module tests the validator functions that provide backward compatibility
with the new platform detection system.
"""

import pytest
from app.models.validators import (
    PlatformValidator,
    validate_video_url,
    detect_platform,
    get_supported_platforms,
    is_direct_video_link,
    normalize_url,
    get_video_extension,
    validate_youtube_url,
    validate_tiktok_url,
    validate_instagram_url,
    validate_facebook_url,
    validate_twitter_url,
    validate_reddit_url,
    validate_vimeo_url,
)


class TestPlatformValidator:
    """Test cases for the PlatformValidator class (backward compatibility)."""
    
    def test_detect_platform_delegates_correctly(self):
        """Test that PlatformValidator.detect_platform delegates to PlatformDetector."""
        test_urls = [
            ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'youtube'),
            ('https://www.tiktok.com/@user/video/123', 'tiktok'),
            ('https://example.com/video.mp4', 'direct'),
            ('https://unsupported.com/video', None),
        ]
        
        for url, expected in test_urls:
            result = PlatformValidator.detect_platform(url)
            assert result == expected, f"Failed for URL: {url}"
    
    def test_validate_url_delegates_correctly(self):
        """Test that PlatformValidator.validate_url delegates to PlatformDetector."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        result = PlatformValidator.validate_url(url)
        
        assert isinstance(result, dict)
        assert result['is_valid'] is True
        assert result['platform'] == 'youtube'
        assert result['video_id'] == 'dQw4w9WgXcQ'
    
    def test_get_supported_platforms_delegates_correctly(self):
        """Test that PlatformValidator.get_supported_platforms delegates correctly."""
        platforms = PlatformValidator.get_supported_platforms()
        
        assert isinstance(platforms, list)
        assert 'youtube' in platforms
        assert 'tiktok' in platforms
        assert 'direct' in platforms
    
    def test_is_platform_supported_delegates_correctly(self):
        """Test that PlatformValidator.is_platform_supported delegates correctly."""
        assert PlatformValidator.is_platform_supported('youtube') is True
        assert PlatformValidator.is_platform_supported('unsupported') is False
    
    def test_extract_video_id_backward_compatibility(self):
        """Test that _extract_video_id works for backward compatibility."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        video_id = PlatformValidator._extract_video_id(url, 'youtube')
        assert video_id == 'dQw4w9WgXcQ'
    
    def test_normalize_url_backward_compatibility(self):
        """Test that _normalize_url works for backward compatibility."""
        url = 'https://youtu.be/dQw4w9WgXcQ'
        normalized = PlatformValidator._normalize_url(url, 'youtube', 'dQw4w9WgXcQ')
        assert normalized == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


class TestValidatorConvenienceFunctions:
    """Test cases for validator convenience functions."""
    
    def test_validate_video_url_function(self):
        """Test the validate_video_url convenience function."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        result = validate_video_url(url)
        
        assert isinstance(result, dict)
        assert result['is_valid'] is True
        assert result['platform'] == 'youtube'
    
    def test_detect_platform_function(self):
        """Test the detect_platform convenience function."""
        assert detect_platform('https://www.youtube.com/watch?v=dQw4w9WgXcQ') == 'youtube'
        assert detect_platform('https://www.tiktok.com/@user/video/123') == 'tiktok'
        assert detect_platform('https://example.com/video.mp4') == 'direct'
        assert detect_platform('https://unsupported.com/video') is None
    
    def test_get_supported_platforms_function(self):
        """Test the get_supported_platforms convenience function."""
        platforms = get_supported_platforms()
        
        assert isinstance(platforms, list)
        assert len(platforms) > 0
        assert 'youtube' in platforms
        assert 'tiktok' in platforms
    
    def test_is_direct_video_link_function(self):
        """Test the is_direct_video_link convenience function."""
        assert is_direct_video_link('https://example.com/video.mp4') is True
        assert is_direct_video_link('https://example.com/movie.avi') is True
        assert is_direct_video_link('https://www.youtube.com/watch?v=123') is False
        assert is_direct_video_link('https://example.com/page.html') is False
    
    def test_normalize_url_function(self):
        """Test the normalize_url convenience function."""
        test_cases = [
            ('https://youtu.be/dQw4w9WgXcQ', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
            ('https://www.youtube.com/embed/dQw4w9WgXcQ', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
        ]
        
        for original, expected in test_cases:
            normalized = normalize_url(original)
            assert normalized == expected, f"Failed for {original}"
    
    def test_get_video_extension_function(self):
        """Test the get_video_extension convenience function."""
        test_cases = [
            ('https://example.com/video.mp4', '.mp4'),
            ('https://example.com/movie.avi', '.avi'),
            ('https://example.com/clip.mov', '.mov'),
            ('https://www.youtube.com/watch?v=123', None),
        ]
        
        for url, expected in test_cases:
            ext = get_video_extension(url)
            assert ext == expected, f"Failed for {url}"
    
    def test_platform_specific_validators(self):
        """Test platform-specific validation functions."""
        # Test YouTube validator
        assert validate_youtube_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is True
        assert validate_youtube_url('https://youtu.be/dQw4w9WgXcQ') is True
        assert validate_youtube_url('https://www.tiktok.com/@user/video/123') is False
        
        # Test TikTok validator
        assert validate_tiktok_url('https://www.tiktok.com/@user/video/123') is True
        assert validate_tiktok_url('https://vm.tiktok.com/abc123') is True
        assert validate_tiktok_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Test Instagram validator
        assert validate_instagram_url('https://www.instagram.com/p/ABC123/') is True
        assert validate_instagram_url('https://www.instagram.com/reel/XYZ789/') is True
        assert validate_instagram_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Test Facebook validator
        assert validate_facebook_url('https://www.facebook.com/watch/?v=123456') is True
        assert validate_facebook_url('https://fb.watch/abc123') is True
        assert validate_facebook_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Test Twitter validator
        assert validate_twitter_url('https://twitter.com/user/status/123456') is True
        assert validate_twitter_url('https://x.com/user/status/123456') is True
        assert validate_twitter_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Test Reddit validator
        assert validate_reddit_url('https://reddit.com/r/videos/comments/abc123/') is True
        assert validate_reddit_url('https://v.redd.it/abc123') is True
        assert validate_reddit_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False
        
        # Test Vimeo validator
        assert validate_vimeo_url('https://vimeo.com/123456789') is True
        assert validate_vimeo_url('https://player.vimeo.com/video/123456789') is True
        assert validate_vimeo_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is False


class TestBackwardCompatibility:
    """Test cases to ensure backward compatibility is maintained."""
    
    def test_legacy_platform_patterns_exist(self):
        """Test that legacy PLATFORM_PATTERNS still exist for reference."""
        assert hasattr(PlatformValidator, 'PLATFORM_PATTERNS')
        assert isinstance(PlatformValidator.PLATFORM_PATTERNS, dict)
        assert 'youtube' in PlatformValidator.PLATFORM_PATTERNS
        assert 'tiktok' in PlatformValidator.PLATFORM_PATTERNS
    
    def test_all_legacy_methods_work(self):
        """Test that all legacy methods still work without errors."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        
        # Test all class methods
        assert PlatformValidator.detect_platform(url) == 'youtube'
        
        result = PlatformValidator.validate_url(url)
        assert result['is_valid'] is True
        
        platforms = PlatformValidator.get_supported_platforms()
        assert isinstance(platforms, list)
        
        assert PlatformValidator.is_platform_supported('youtube') is True
        
        video_id = PlatformValidator._extract_video_id(url, 'youtube')
        assert video_id == 'dQw4w9WgXcQ'
        
        normalized = PlatformValidator._normalize_url(url, 'youtube', video_id)
        assert normalized is not None
    
    def test_function_signatures_unchanged(self):
        """Test that function signatures remain unchanged for backward compatibility."""
        # Test that functions can be called with the same parameters as before
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        
        # These should all work without errors
        validate_video_url(url)
        detect_platform(url)
        get_supported_platforms()
        is_direct_video_link(url)
        normalize_url(url)
        get_video_extension(url)
        
        # Platform-specific validators
        validate_youtube_url(url)
        validate_tiktok_url(url)
        validate_instagram_url(url)
        validate_facebook_url(url)
        validate_twitter_url(url)
        validate_reddit_url(url)
        validate_vimeo_url(url)


if __name__ == '__main__':
    pytest.main([__file__])