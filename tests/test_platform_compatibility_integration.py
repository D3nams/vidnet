"""
Platform compatibility integration tests with real URLs.

This module tests the system's ability to handle real URLs from all supported
platforms, ensuring compatibility and proper error handling.
"""

import pytest
import asyncio
import time
from typing import Dict, List, Tuple
from unittest.mock import patch, AsyncMock

from app.services.platform_detector import PlatformDetector
from app.services.video_processor import VideoProcessor
from app.models.video import VideoMetadata, VideoQuality


class TestPlatformCompatibility:
    """Test platform compatibility with real URLs."""
    
    # Real test URLs for each platform (using public, safe content)
    TEST_URLS = {
        'youtube': [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # Rick Roll (safe, well-known)
            'https://youtu.be/dQw4w9WgXcQ',  # Short URL format
            'https://www.youtube.com/watch?v=jNQXAC9IVRw',  # Me at the zoo (first YouTube video)
            'https://www.youtube.com/shorts/abc123',  # YouTube Shorts format
        ],
        'tiktok': [
            'https://www.tiktok.com/@test/video/1234567890123456789',  # Standard format
            'https://vm.tiktok.com/ZMeAbCdEf',  # Mobile share format
            'https://www.tiktok.com/t/ZTAbCdEfH',  # Short format
        ],
        'instagram': [
            'https://www.instagram.com/p/ABC123DEF456/',  # Post format
            'https://www.instagram.com/reel/DEF456ABC123/',  # Reel format
            'https://www.instagram.com/tv/GHI789DEF456/',  # IGTV format
        ],
        'facebook': [
            'https://www.facebook.com/watch/?v=1234567890123456',  # Watch format
            'https://fb.watch/AbCdEfGhIj',  # Short format
            'https://www.facebook.com/username/videos/1234567890123456',  # User video
        ],
        'twitter': [
            'https://twitter.com/username/status/1234567890123456789',  # Standard format
            'https://x.com/username/status/1234567890123456789',  # X.com format
            'https://mobile.twitter.com/username/status/1234567890123456789',  # Mobile format
        ],
        'reddit': [
            'https://www.reddit.com/r/videos/comments/abc123/title_here/',  # Standard format
            'https://v.redd.it/abcdef123456',  # Direct video format
            'https://old.reddit.com/r/videos/comments/abc123/title_here/',  # Old Reddit
        ],
        'vimeo': [
            'https://vimeo.com/123456789',  # Standard format
            'https://player.vimeo.com/video/123456789',  # Player format
            'https://vimeo.com/ondemand/movie-name/123456789',  # On-demand format
        ],
        'direct': [
            'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4',
            'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
            'https://www.learningcontainer.com/wp-content/uploads/2020/05/sample-mp4-file.mp4',
        ]
    }
    
    @pytest.fixture
    def video_processor(self):
        """Create video processor instance."""
        return VideoProcessor()
    
    @pytest.fixture
    def platform_detector(self):
        """Create platform detector instance."""
        return PlatformDetector()
    
    @pytest.mark.asyncio
    async def test_platform_detection_accuracy(self, platform_detector):
        """Test platform detection accuracy for all supported platforms."""
        detection_results = {}
        
        for platform, urls in self.TEST_URLS.items():
            detection_results[platform] = []
            
            for url in urls:
                detected_platform = platform_detector.detect_platform(url)
                detection_results[platform].append({
                    'url': url,
                    'detected': detected_platform,
                    'expected': platform,
                    'correct': detected_platform == platform
                })
        
        # Verify detection accuracy
        for platform, results in detection_results.items():
            correct_detections = sum(1 for r in results if r['correct'])
            total_urls = len(results)
            accuracy = (correct_detections / total_urls) * 100
            
            print(f"{platform.capitalize()} detection accuracy: {accuracy:.1f}% ({correct_detections}/{total_urls})")
            
            # Should have at least 90% accuracy for each platform
            assert accuracy >= 90, f"Low detection accuracy for {platform}: {accuracy:.1f}%"
            
            # Log any failed detections
            failed_detections = [r for r in results if not r['correct']]
            for failure in failed_detections:
                print(f"Failed detection: {failure['url']} -> detected as {failure['detected']}, expected {failure['expected']}")
    
    @pytest.mark.asyncio
    async def test_url_validation_comprehensive(self, platform_detector):
        """Test comprehensive URL validation for all platforms."""
        validation_results = {}
        
        for platform, urls in self.TEST_URLS.items():
            validation_results[platform] = []
            
            for url in urls:
                result = platform_detector.validate_url(url)
                validation_results[platform].append({
                    'url': url,
                    'is_valid': result['is_valid'],
                    'platform': result.get('platform'),
                    'error': result.get('error'),
                    'warnings': result.get('warnings', [])
                })
        
        # Verify validation results
        for platform, results in validation_results.items():
            valid_urls = sum(1 for r in results if r['is_valid'])
            total_urls = len(results)
            validity_rate = (valid_urls / total_urls) * 100
            
            print(f"{platform.capitalize()} URL validity rate: {validity_rate:.1f}% ({valid_urls}/{total_urls})")
            
            # Should have high validity rate (allowing for some test URLs to be invalid)
            assert validity_rate >= 70, f"Low validity rate for {platform}: {validity_rate:.1f}%"
    
    @pytest.mark.asyncio
    async def test_url_normalization_consistency(self, platform_detector):
        """Test URL normalization consistency across platforms."""
        normalization_results = {}
        
        for platform, urls in self.TEST_URLS.items():
            normalization_results[platform] = []
            
            for url in urls:
                normalized = platform_detector.normalize_url(url)
                normalization_results[platform].append({
                    'original': url,
                    'normalized': normalized,
                    'changed': url != normalized
                })
        
        # Verify normalization behavior
        for platform, results in normalization_results.items():
            normalized_count = sum(1 for r in results if r['changed'])
            total_urls = len(results)
            
            print(f"{platform.capitalize()} URLs normalized: {normalized_count}/{total_urls}")
            
            # Log normalization changes
            for result in results:
                if result['changed']:
                    print(f"  {result['original']} -> {result['normalized']}")
            
            # Verify all normalized URLs are still valid
            for result in results:
                if result['normalized']:
                    validation = platform_detector.validate_url(result['normalized'])
                    assert validation['is_valid'], f"Normalized URL invalid: {result['normalized']}"
    
    @pytest.mark.asyncio
    async def test_metadata_extraction_simulation(self, video_processor):
        """Test metadata extraction simulation for all platforms."""
        # Mock yt-dlp to avoid actual network requests in tests
        mock_metadata = {
            'title': 'Test Video Title',
            'duration': 300,
            'thumbnail': 'https://example.com/thumb.jpg',
            'formats': [
                {
                    'format_id': '720p',
                    'ext': 'mp4',
                    'height': 720,
                    'filesize': 1024000,
                    'fps': 30
                },
                {
                    'format_id': '1080p', 
                    'ext': 'mp4',
                    'height': 1080,
                    'filesize': 2048000,
                    'fps': 30
                }
            ]
        }
        
        extraction_results = {}
        
        with patch.object(video_processor, '_extract_with_ytdlp', return_value=mock_metadata):
            for platform, urls in self.TEST_URLS.items():
                extraction_results[platform] = []
                
                for url in urls[:2]:  # Test first 2 URLs per platform to save time
                    try:
                        metadata = await video_processor.extract_metadata(url)
                        extraction_results[platform].append({
                            'url': url,
                            'success': True,
                            'metadata': metadata,
                            'error': None
                        })
                    except Exception as e:
                        extraction_results[platform].append({
                            'url': url,
                            'success': False,
                            'metadata': None,
                            'error': str(e)
                        })
        
        # Verify extraction results
        for platform, results in extraction_results.items():
            successful_extractions = sum(1 for r in results if r['success'])
            total_attempts = len(results)
            success_rate = (successful_extractions / total_attempts) * 100 if total_attempts > 0 else 0
            
            print(f"{platform.capitalize()} metadata extraction success rate: {success_rate:.1f}% ({successful_extractions}/{total_attempts})")
            
            # Should have high success rate with mocked data
            assert success_rate >= 90, f"Low extraction success rate for {platform}: {success_rate:.1f}%"
            
            # Verify metadata structure for successful extractions
            for result in results:
                if result['success'] and result['metadata']:
                    metadata = result['metadata']
                    assert hasattr(metadata, 'title'), "Metadata missing title"
                    assert hasattr(metadata, 'duration'), "Metadata missing duration"
                    assert hasattr(metadata, 'platform'), "Metadata missing platform"
                    assert hasattr(metadata, 'available_qualities'), "Metadata missing available_qualities"
    
    @pytest.mark.asyncio
    async def test_platform_specific_features(self, platform_detector):
        """Test platform-specific feature extraction."""
        feature_tests = {
            'youtube': {
                'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s',
                'expected_features': ['video_id', 'timestamp']
            },
            'tiktok': {
                'url': 'https://www.tiktok.com/@username/video/1234567890123456789',
                'expected_features': ['username', 'video_id']
            },
            'instagram': {
                'url': 'https://www.instagram.com/p/ABC123DEF456/',
                'expected_features': ['post_id']
            },
            'facebook': {
                'url': 'https://www.facebook.com/watch/?v=1234567890123456',
                'expected_features': ['video_id']
            },
            'twitter': {
                'url': 'https://twitter.com/username/status/1234567890123456789',
                'expected_features': ['username', 'tweet_id']
            },
            'reddit': {
                'url': 'https://www.reddit.com/r/videos/comments/abc123/title_here/',
                'expected_features': ['subreddit', 'post_id']
            },
            'vimeo': {
                'url': 'https://vimeo.com/123456789',
                'expected_features': ['video_id']
            }
        }
        
        for platform, test_data in feature_tests.items():
            url = test_data['url']
            expected_features = test_data['expected_features']
            
            platform_info = platform_detector.extract_platform_info(url)
            
            if platform_info:
                print(f"{platform.capitalize()} features extracted: {list(platform_info.metadata.keys())}")
                
                # Verify platform detection
                assert platform_info.name == platform, f"Wrong platform detected for {platform}"
                
                # Verify video ID extraction
                assert platform_info.video_id is not None, f"No video ID extracted for {platform}"
                
                # Check for expected features in metadata
                for feature in expected_features:
                    if feature == 'video_id':
                        assert platform_info.video_id, f"Missing video_id for {platform}"
                    else:
                        assert feature in platform_info.metadata, f"Missing {feature} for {platform}"
            else:
                pytest.fail(f"Failed to extract platform info for {platform}: {url}")
    
    @pytest.mark.asyncio
    async def test_error_handling_robustness(self, platform_detector, video_processor):
        """Test error handling for various problematic URLs."""
        problematic_urls = [
            # Invalid URLs
            'not-a-url',
            'https://',
            'ftp://example.com/video.mp4',
            
            # Malformed platform URLs
            'https://youtube.com/watch',  # Missing video ID
            'https://tiktok.com/@user',  # Missing video ID
            'https://instagram.com/p/',  # Missing post ID
            
            # Non-existent content
            'https://www.youtube.com/watch?v=nonexistent123',
            'https://www.tiktok.com/@fake/video/0000000000000000000',
            
            # Unsupported platforms
            'https://dailymotion.com/video/x123456',
            'https://twitch.tv/videos/123456789',
            
            # Edge cases
            '',
            None,
            'javascript:alert("test")',
        ]
        
        error_handling_results = []
        
        for url in problematic_urls:
            # Test platform detection
            try:
                platform = platform_detector.detect_platform(url)
                detection_error = None
            except Exception as e:
                platform = None
                detection_error = str(e)
            
            # Test URL validation
            try:
                validation = platform_detector.validate_url(url)
                validation_error = None
            except Exception as e:
                validation = {'is_valid': False, 'error': 'validation_exception'}
                validation_error = str(e)
            
            # Test metadata extraction (with mocked yt-dlp)
            extraction_error = None
            if platform:
                with patch.object(video_processor, '_extract_with_ytdlp', side_effect=Exception("Video not found")):
                    try:
                        await video_processor.extract_metadata(url)
                    except Exception as e:
                        extraction_error = str(e)
            
            error_handling_results.append({
                'url': str(url)[:50] + '...' if url and len(str(url)) > 50 else str(url),
                'platform': platform,
                'detection_error': detection_error,
                'validation_valid': validation.get('is_valid', False),
                'validation_error': validation_error,
                'extraction_error': extraction_error
            })
        
        # Verify error handling
        for result in error_handling_results:
            print(f"URL: {result['url']}")
            print(f"  Platform: {result['platform']}")
            print(f"  Detection error: {result['detection_error']}")
            print(f"  Validation valid: {result['validation_valid']}")
            print(f"  Validation error: {result['validation_error']}")
            print(f"  Extraction error: {result['extraction_error']}")
            print()
            
            # Should not crash on any input
            assert result['detection_error'] is None, f"Detection crashed on: {result['url']}"
            assert result['validation_error'] is None, f"Validation crashed on: {result['url']}"
        
        # Most problematic URLs should be detected as invalid
        invalid_count = sum(1 for r in error_handling_results if not r['validation_valid'])
        total_count = len(error_handling_results)
        invalid_rate = (invalid_count / total_count) * 100
        
        print(f"Invalid URL detection rate: {invalid_rate:.1f}% ({invalid_count}/{total_count})")
        assert invalid_rate >= 80, f"Should detect most problematic URLs as invalid: {invalid_rate:.1f}%"
    
    @pytest.mark.asyncio
    async def test_concurrent_platform_processing(self, platform_detector):
        """Test concurrent processing of multiple platform URLs."""
        # Select one URL from each platform
        test_urls = [urls[0] for urls in self.TEST_URLS.values()]
        
        async def process_url(url):
            """Process a single URL and return results."""
            start_time = time.time()
            
            platform = platform_detector.detect_platform(url)
            validation = platform_detector.validate_url(url)
            normalized = platform_detector.normalize_url(url)
            platform_info = platform_detector.extract_platform_info(url)
            
            processing_time = time.time() - start_time
            
            return {
                'url': url,
                'platform': platform,
                'is_valid': validation['is_valid'],
                'normalized': normalized,
                'has_info': platform_info is not None,
                'processing_time': processing_time
            }
        
        # Process all URLs concurrently
        start_time = time.time()
        tasks = [process_url(url) for url in test_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Verify concurrent processing results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        print(f"Concurrent processing: {len(successful_results)}/{len(test_urls)} successful")
        print(f"Total processing time: {total_time:.3f}s")
        print(f"Average time per URL: {total_time/len(test_urls):.3f}s")
        
        # Should have high success rate
        success_rate = (len(successful_results) / len(test_urls)) * 100
        assert success_rate >= 90, f"Low concurrent processing success rate: {success_rate:.1f}%"
        
        # Should be reasonably fast
        assert total_time < 5.0, f"Concurrent processing too slow: {total_time:.3f}s"
        
        # Verify individual results
        for result in successful_results:
            if isinstance(result, dict):
                assert result['platform'] is not None, f"No platform detected for: {result['url']}"
                assert result['processing_time'] < 1.0, f"Individual processing too slow: {result['processing_time']:.3f}s"
        
        # Log any failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Failed to process {test_urls[i]}: {result}")
    
    @pytest.mark.asyncio
    async def test_platform_coverage_completeness(self, platform_detector):
        """Test that all supported platforms have test coverage."""
        supported_platforms = platform_detector.get_supported_platforms()
        tested_platforms = set(self.TEST_URLS.keys())
        
        print(f"Supported platforms: {supported_platforms}")
        print(f"Tested platforms: {list(tested_platforms)}")
        
        # Verify all supported platforms have test URLs
        missing_platforms = set(supported_platforms) - tested_platforms
        assert not missing_platforms, f"Missing test URLs for platforms: {missing_platforms}"
        
        # Verify no extra platforms in tests
        extra_platforms = tested_platforms - set(supported_platforms)
        if extra_platforms:
            print(f"Warning: Test URLs for unsupported platforms: {extra_platforms}")
        
        # Verify minimum number of test URLs per platform
        for platform in supported_platforms:
            url_count = len(self.TEST_URLS.get(platform, []))
            assert url_count >= 2, f"Insufficient test URLs for {platform}: {url_count} (minimum 2)"
            print(f"{platform.capitalize()}: {url_count} test URLs")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])