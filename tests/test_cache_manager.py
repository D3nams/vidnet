"""
Unit tests for Redis cache manager.
Tests caching operations, TTL behavior, and performance monitoring.
"""
import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.cache_manager import CacheManager
from app.core.config import settings


class TestCacheManager:
    """Test suite for CacheManager class."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create a fresh CacheManager instance for each test."""
        return CacheManager()
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.get = AsyncMock()
        mock_client.setex = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.keys = AsyncMock(return_value=[])
        mock_client.info = AsyncMock(return_value={
            'redis_version': '7.0.0',
            'used_memory_human': '1.5M',
            'connected_clients': 2
        })
        mock_client.close = AsyncMock()
        return mock_client
    
    @pytest.mark.asyncio
    async def test_cache_manager_initialization(self, cache_manager):
        """Test CacheManager initialization with default values."""
        assert cache_manager.redis_client is None
        assert cache_manager.metadata_ttl == settings.metadata_cache_ttl
        assert cache_manager.download_ttl == settings.download_cache_ttl
        assert cache_manager.stats['hits'] == 0
        assert cache_manager.stats['misses'] == 0
        assert cache_manager.stats['errors'] == 0
        assert cache_manager.stats['total_requests'] == 0
    
    @pytest.mark.asyncio
    async def test_connect_success(self, cache_manager, mock_redis):
        """Test successful Redis connection."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            result = await cache_manager.connect()
            assert result is True
            assert cache_manager.redis_client is not None
            mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, cache_manager):
        """Test Redis connection failure."""
        with patch('redis.asyncio.from_url', side_effect=Exception("Connection failed")):
            with patch('builtins.print'):  # Suppress error output
                result = await cache_manager.connect()
                assert result is False
                assert cache_manager.redis_client is None
    
    @pytest.mark.asyncio
    async def test_disconnect(self, cache_manager, mock_redis):
        """Test Redis disconnection."""
        cache_manager.redis_client = mock_redis
        await cache_manager.disconnect()
        mock_redis.close.assert_called_once()
        assert cache_manager.redis_client is None
    
    def test_generate_cache_key_short_identifier(self, cache_manager):
        """Test cache key generation with short identifier."""
        key = cache_manager._generate_cache_key("metadata:", "short_url")
        assert key == "metadata:short_url"
    
    def test_generate_cache_key_long_identifier(self, cache_manager):
        """Test cache key generation with long identifier (should be hashed)."""
        long_url = "https://example.com/" + "x" * 200
        key = cache_manager._generate_cache_key("metadata:", long_url)
        assert key.startswith("metadata:")
        assert len(key) < len("metadata:" + long_url)  # Should be shorter due to hashing
    
    @pytest.mark.asyncio
    async def test_get_metadata_cache_hit(self, cache_manager, mock_redis):
        """Test successful metadata retrieval from cache."""
        test_metadata = {"title": "Test Video", "duration": 120}
        mock_redis.get.return_value = json.dumps(test_metadata)
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.get_metadata("https://youtube.com/watch?v=test")
        
        assert result == test_metadata
        assert cache_manager.stats['hits'] == 1
        assert cache_manager.stats['misses'] == 0
        assert cache_manager.stats['total_requests'] == 1
    
    @pytest.mark.asyncio
    async def test_get_metadata_cache_miss(self, cache_manager, mock_redis):
        """Test metadata cache miss."""
        mock_redis.get.return_value = None
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.get_metadata("https://youtube.com/watch?v=test")
        
        assert result is None
        assert cache_manager.stats['hits'] == 0
        assert cache_manager.stats['misses'] == 1
        assert cache_manager.stats['total_requests'] == 1
    
    @pytest.mark.asyncio
    async def test_get_metadata_redis_error(self, cache_manager, mock_redis):
        """Test metadata retrieval with Redis error."""
        mock_redis.get.side_effect = Exception("Redis error")
        cache_manager.redis_client = mock_redis
        
        with patch('builtins.print'):  # Suppress error output
            result = await cache_manager.get_metadata("https://youtube.com/watch?v=test")
            
            assert result is None
            assert cache_manager.stats['errors'] == 1
            assert cache_manager.stats['total_requests'] == 1
    
    @pytest.mark.asyncio
    async def test_cache_metadata_success(self, cache_manager, mock_redis):
        """Test successful metadata caching."""
        test_metadata = {"title": "Test Video", "duration": 120}
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.cache_metadata("https://youtube.com/watch?v=test", test_metadata)
        
        assert result is True
        mock_redis.setex.assert_called_once()
        
        # Verify the cached data includes timestamp and TTL
        call_args = mock_redis.setex.call_args
        cached_data = json.loads(call_args[0][2])
        assert cached_data['title'] == test_metadata['title']
        assert cached_data['duration'] == test_metadata['duration']
        assert 'cached_at' in cached_data
        assert cached_data['cache_ttl'] == cache_manager.metadata_ttl
    
    @pytest.mark.asyncio
    async def test_cache_metadata_redis_error(self, cache_manager, mock_redis):
        """Test metadata caching with Redis error."""
        test_metadata = {"title": "Test Video", "duration": 120}
        mock_redis.setex.side_effect = Exception("Redis error")
        cache_manager.redis_client = mock_redis
        
        with patch('builtins.print'):  # Suppress error output
            result = await cache_manager.cache_metadata("https://youtube.com/watch?v=test", test_metadata)
            
            assert result is False
            assert cache_manager.stats['errors'] == 1
    
    @pytest.mark.asyncio
    async def test_track_download_success(self, cache_manager, mock_redis):
        """Test successful download tracking."""
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.track_download("task_123", "processing", {"url": "test"})
        
        assert result is True
        mock_redis.setex.assert_called_once()
        
        # Verify the tracked data structure
        call_args = mock_redis.setex.call_args
        task_data = json.loads(call_args[0][2])
        assert task_data['task_id'] == "task_123"
        assert task_data['status'] == "processing"
        assert 'updated_at' in task_data
        assert task_data['metadata'] == {"url": "test"}
    
    @pytest.mark.asyncio
    async def test_get_download_status_found(self, cache_manager, mock_redis):
        """Test successful download status retrieval."""
        test_status = {"task_id": "task_123", "status": "completed"}
        mock_redis.get.return_value = json.dumps(test_status)
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.get_download_status("task_123")
        
        assert result == test_status
    
    @pytest.mark.asyncio
    async def test_get_download_status_not_found(self, cache_manager, mock_redis):
        """Test download status retrieval when not found."""
        mock_redis.get.return_value = None
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.get_download_status("task_123")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalidate_cache_success(self, cache_manager, mock_redis):
        """Test successful cache invalidation."""
        mock_redis.keys.return_value = ["metadata:key1", "metadata:key2"]
        mock_redis.delete.return_value = 2
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.invalidate_cache("metadata:*")
        
        assert result == 2
        mock_redis.keys.assert_called_once_with("metadata:*")
        mock_redis.delete.assert_called_once_with("metadata:key1", "metadata:key2")
    
    @pytest.mark.asyncio
    async def test_invalidate_cache_no_keys(self, cache_manager, mock_redis):
        """Test cache invalidation when no keys match."""
        mock_redis.keys.return_value = []
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.invalidate_cache("metadata:*")
        
        assert result == 0
        mock_redis.delete.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_clear_expired_downloads(self, cache_manager, mock_redis):
        """Test clearing expired download tasks."""
        mock_redis.keys.return_value = ["task:123", "task:456"]
        mock_redis.delete.return_value = 2
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.clear_expired_downloads()
        
        assert result == 2
        mock_redis.keys.assert_called_once_with("task:*")
    
    def test_get_cache_stats_no_requests(self, cache_manager):
        """Test cache statistics with no requests."""
        stats = cache_manager.get_cache_stats()
        
        assert stats['hit_rate'] == 0.0
        assert stats['miss_rate'] == 0.0
        assert stats['error_rate'] == 0.0
        assert stats['total_requests'] == 0
    
    def test_get_cache_stats_with_data(self, cache_manager):
        """Test cache statistics with sample data."""
        cache_manager.stats = {
            'hits': 80,
            'misses': 15,
            'errors': 5,
            'total_requests': 100
        }
        
        stats = cache_manager.get_cache_stats()
        
        assert stats['hit_rate'] == 80.0
        assert stats['miss_rate'] == 15.0
        assert stats['error_rate'] == 5.0
        assert stats['total_requests'] == 100
        assert stats['hits'] == 80
        assert stats['misses'] == 15
        assert stats['errors'] == 5
    
    @pytest.mark.asyncio
    async def test_reset_stats(self, cache_manager):
        """Test statistics reset."""
        cache_manager.stats = {
            'hits': 10,
            'misses': 5,
            'errors': 2,
            'total_requests': 17
        }
        
        await cache_manager.reset_stats()
        
        assert cache_manager.stats['hits'] == 0
        assert cache_manager.stats['misses'] == 0
        assert cache_manager.stats['errors'] == 0
        assert cache_manager.stats['total_requests'] == 0
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, cache_manager, mock_redis):
        """Test health check when Redis is healthy."""
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.health_check()
        
        assert result['status'] == 'healthy'
        assert result['connected'] is True
        assert 'response_time_ms' in result
        assert result['redis_version'] == '7.0.0'
        assert result['used_memory_human'] == '1.5M'
        assert result['connected_clients'] == 2
        assert 'cache_stats' in result
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy_no_connection(self, cache_manager):
        """Test health check when Redis connection is unavailable."""
        result = await cache_manager.health_check()
        
        assert result['status'] == 'unhealthy'
        assert result['connected'] is False
        assert 'error' in result
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy_redis_error(self, cache_manager, mock_redis):
        """Test health check when Redis throws an error."""
        mock_redis.ping.side_effect = Exception("Redis error")
        cache_manager.redis_client = mock_redis
        
        result = await cache_manager.health_check()
        
        assert result['status'] == 'unhealthy'
        assert result['connected'] is False
        assert result['error'] == "Redis error"


class TestCacheManagerTTL:
    """Test TTL (Time To Live) behavior of cache manager."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create a CacheManager with short TTL for testing."""
        manager = CacheManager()
        manager.metadata_ttl = 1  # 1 second for testing
        manager.download_ttl = 1  # 1 second for testing
        return manager
    
    @pytest.mark.asyncio
    async def test_metadata_ttl_expiration(self, cache_manager):
        """Test that metadata cache expires after TTL."""
        # This test would require a real Redis instance or more complex mocking
        # For now, we'll test that the TTL is set correctly in the setex call
        mock_redis = AsyncMock()
        cache_manager.redis_client = mock_redis
        
        test_metadata = {"title": "Test Video"}
        await cache_manager.cache_metadata("test_url", test_metadata)
        
        # Verify TTL is set correctly
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 1  # TTL should be 1 second
    
    @pytest.mark.asyncio
    async def test_download_task_ttl_expiration(self, cache_manager):
        """Test that download task cache expires after TTL."""
        mock_redis = AsyncMock()
        cache_manager.redis_client = mock_redis
        
        await cache_manager.track_download("task_123", "processing")
        
        # Verify TTL is set correctly
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 1  # TTL should be 1 second


class TestCacheManagerIntegration:
    """Integration tests for cache manager with performance scenarios."""
    
    @pytest.mark.asyncio
    async def test_cache_performance_scenario(self):
        """Test cache performance with multiple operations."""
        cache_manager = CacheManager()
        mock_redis = AsyncMock()
        cache_manager.redis_client = mock_redis
        
        # Simulate cache hits and misses
        mock_redis.get.side_effect = [
            None,  # First call - cache miss
            json.dumps({"title": "Cached Video"}),  # Second call - cache hit
            None,  # Third call - cache miss
        ]
        
        # Perform operations
        await cache_manager.get_metadata("url1")  # Miss
        await cache_manager.get_metadata("url2")  # Hit
        await cache_manager.get_metadata("url3")  # Miss
        
        # Check statistics
        stats = cache_manager.get_cache_stats()
        assert stats['total_requests'] == 3
        assert stats['hits'] == 1
        assert stats['misses'] == 2
        assert stats['hit_rate'] == 33.33
        assert stats['miss_rate'] == 66.67
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test cache manager with concurrent operations."""
        cache_manager = CacheManager()
        mock_redis = AsyncMock()
        cache_manager.redis_client = mock_redis
        
        # Mock responses for concurrent requests
        mock_redis.get.return_value = json.dumps({"title": "Test Video"})
        
        # Simulate concurrent requests
        tasks = []
        for i in range(10):
            task = cache_manager.get_metadata(f"url_{i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All should return the same cached data
        assert len(results) == 10
        assert all(result["title"] == "Test Video" for result in results)
        assert cache_manager.stats['total_requests'] == 10
        assert cache_manager.stats['hits'] == 10