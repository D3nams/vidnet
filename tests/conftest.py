"""
Pytest configuration and fixtures for VidNet test suite.

This module provides shared fixtures and configuration for all tests.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Import app components for testing
try:
    from app.main import app
    from app.services.platform_detector import PlatformDetector
    from app.services.video_processor import VideoProcessor
    from app.services.download_manager import download_manager
    from app.services.cache_manager import cache_manager
    from app.services.performance_monitor import performance_monitor
    from app.services.metrics_collector import metrics_collector
except ImportError:
    # Handle case where app modules are not available
    app = None
    PlatformDetector = None
    VideoProcessor = None
    download_manager = None
    cache_manager = None
    performance_monitor = None
    metrics_collector = None


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_video_metadata():
    """Mock video metadata for testing."""
    if VideoProcessor is None:
        # Return a simple dict if classes not available
        return {
            'title': 'Test Video',
            'duration': 300,
            'thumbnail': 'https://example.com/thumb.jpg',
            'platform': 'youtube',
            'available_qualities': [
                {'quality': '720p', 'format': 'mp4', 'filesize': 1024000, 'fps': 30},
                {'quality': '1080p', 'format': 'mp4', 'filesize': 2048000, 'fps': 30}
            ],
            'audio_available': True,
            'original_url': 'https://youtube.com/watch?v=test123'
        }
    
    # Return proper VideoMetadata object if available
    from app.models.video import VideoMetadata, VideoQuality
    return VideoMetadata(
        title="Test Video",
        thumbnail="https://example.com/thumb.jpg",
        duration=300,
        platform="youtube",
        available_qualities=[
            VideoQuality(quality="720p", format="mp4", filesize=1024000, fps=30),
            VideoQuality(quality="1080p", format="mp4", filesize=2048000, fps=30)
        ],
        audio_available=True,
        original_url="https://youtube.com/watch?v=test123"
    )


@pytest.fixture
def mock_platform_detector():
    """Mock platform detector for testing."""
    if PlatformDetector is None:
        # Create a simple mock if class not available
        mock = Mock()
        mock.detect_platform = Mock(return_value='youtube')
        mock.validate_url = Mock(return_value={'is_valid': True, 'platform': 'youtube', 'error': None})
        mock.normalize_url = Mock(side_effect=lambda x: x)
        mock.extract_platform_info = Mock(return_value=None)
        mock.get_supported_platforms = Mock(return_value=['youtube', 'tiktok', 'instagram'])
        return mock
    
    return PlatformDetector()


@pytest.fixture
def mock_video_processor():
    """Mock video processor for testing."""
    if VideoProcessor is None:
        # Create a simple mock if class not available
        mock = Mock()
        mock.extract_metadata = AsyncMock(return_value=None)
        mock.download_video = AsyncMock(return_value="test_file.mp4")
        mock.extract_audio = AsyncMock(return_value="test_audio.mp3")
        return mock
    
    return VideoProcessor()


@pytest.fixture
def mock_download_manager():
    """Mock download manager for testing."""
    mock = Mock()
    mock.submit_download = AsyncMock(return_value="test-task-id")
    mock.get_download_status = AsyncMock(return_value={
        'status': 'completed',
        'progress': 100,
        'download_url': '/downloads/test_file.mp4'
    })
    mock.cancel_download = AsyncMock(return_value=True)
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock._running = True
    return mock


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager for testing."""
    mock = Mock()
    mock.get_metadata = AsyncMock(return_value=None)
    mock.cache_metadata = AsyncMock()
    mock.track_download = AsyncMock()
    mock.get_download_status = AsyncMock(return_value=None)
    mock.get_stats = Mock(return_value={'hit_rate': 85.0, 'total_requests': 1000})
    return mock


@pytest.fixture
def mock_performance_monitor():
    """Mock performance monitor for testing."""
    mock = Mock()
    mock.start_monitoring = AsyncMock()
    mock.stop_monitoring = AsyncMock()
    mock.get_endpoint_stats = Mock(return_value={})
    mock.get_system_metrics = Mock(return_value={
        'cpu_percent': 45.0,
        'memory_percent': 60.0,
        'timestamp': 1234567890
    })
    mock.get_performance_summary = Mock(return_value={
        'total_requests': 1000,
        'average_response_time': 1.2,
        'error_rate': 2.5
    })
    mock._monitoring_active = False
    return mock


@pytest.fixture
def mock_metrics_collector():
    """Mock metrics collector for testing."""
    mock = Mock()
    mock.track_download = Mock()
    mock.track_cache_operation = Mock()
    mock.record_metric = Mock()
    mock.get_dashboard_data = Mock(return_value={
        'overview': {'total_downloads': 1000},
        'performance': {'system_metrics': {}},
        'business_metrics': {'platform_metrics': {}},
        'cache_performance': {'hit_rate': 85.0},
        'alerts': [],
        'timestamp': 1234567890
    })
    mock.get_platform_metrics = Mock(return_value={})
    mock.get_quality_metrics = Mock(return_value={})
    mock.get_user_engagement_metrics = Mock(return_value={})
    mock.get_cache_metrics = Mock(return_value={'hit_rate': 85.0})
    mock.get_performance_alerts = Mock(return_value=[])
    mock.export_metrics = Mock(return_value="exported_file.json")
    return mock


@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock external services to avoid network calls during tests."""
    with patch('httpx.AsyncClient') as mock_client:
        # Mock HTTP client responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_response.content = b'test content'
        mock_response.headers = {'content-type': 'application/json'}
        
        mock_client_instance = Mock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.aclose = AsyncMock()
        
        mock_client.return_value = mock_client_instance
        yield mock_client


@pytest.fixture
def test_urls():
    """Provide test URLs for different platforms."""
    return {
        'youtube': [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtu.be/dQw4w9WgXcQ'
        ],
        'tiktok': [
            'https://www.tiktok.com/@test/video/1234567890123456789',
            'https://vm.tiktok.com/ZMeAbCdEf'
        ],
        'instagram': [
            'https://www.instagram.com/p/ABC123DEF456/',
            'https://www.instagram.com/reel/DEF456ABC123/'
        ],
        'facebook': [
            'https://www.facebook.com/watch/?v=1234567890123456',
            'https://fb.watch/AbCdEfGhIj'
        ],
        'twitter': [
            'https://twitter.com/username/status/1234567890123456789',
            'https://x.com/username/status/1234567890123456789'
        ],
        'reddit': [
            'https://www.reddit.com/r/videos/comments/abc123/title_here/',
            'https://v.redd.it/abcdef123456'
        ],
        'vimeo': [
            'https://vimeo.com/123456789',
            'https://player.vimeo.com/video/123456789'
        ],
        'direct': [
            'https://example.com/video.mp4',
            'https://cdn.example.com/movie.avi'
        ]
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "platform: mark test as platform compatibility test"
    )
    config.addinivalue_line(
        "markers", "load: mark test as load test"
    )
    config.addinivalue_line(
        "markers", "uptime: mark test as uptime monitoring test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file names."""
    for item in items:
        # Add markers based on test file names
        if "integration" in item.fspath.basename:
            item.add_marker(pytest.mark.integration)
        elif "performance" in item.fspath.basename or "load" in item.fspath.basename:
            item.add_marker(pytest.mark.performance)
        elif "platform" in item.fspath.basename:
            item.add_marker(pytest.mark.platform)
        elif "uptime" in item.fspath.basename:
            item.add_marker(pytest.mark.uptime)


# Test utilities
class TestUtils:
    """Utility functions for tests."""
    
    @staticmethod
    def create_mock_response(status_code=200, json_data=None, content=b''):
        """Create a mock HTTP response."""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {'success': True}
        mock_response.content = content
        mock_response.headers = {'content-type': 'application/json'}
        return mock_response
    
    @staticmethod
    def assert_response_format(response_data, required_fields=None):
        """Assert that response has expected format."""
        if required_fields is None:
            required_fields = ['success']
        
        assert isinstance(response_data, dict), "Response should be a dictionary"
        
        for field in required_fields:
            assert field in response_data, f"Response missing required field: {field}"
    
    @staticmethod
    def assert_performance_metrics(metrics, max_response_time=5.0, min_success_rate=80.0):
        """Assert that performance metrics meet requirements."""
        if 'average_response_time' in metrics:
            assert metrics['average_response_time'] <= max_response_time, \
                f"Response time too high: {metrics['average_response_time']:.3f}s"
        
        if 'success_rate' in metrics:
            assert metrics['success_rate'] >= min_success_rate, \
                f"Success rate too low: {metrics['success_rate']:.1f}%"


# Make test utilities available as fixture
@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtils