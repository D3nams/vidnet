"""
Redis caching layer for VidNet application.
Provides TTL-based metadata caching with performance monitoring.
"""
import json
import hashlib
import time
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta, timezone
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from app.core.config import settings


class CacheManager:
    """
    Redis-based cache manager with TTL support and performance monitoring.
    
    Features:
    - TTL-based metadata caching
    - Cache key generation and invalidation
    - Hit/miss tracking for performance monitoring
    - Async Redis operations
    """
    
    def __init__(self):
        """Initialize Redis connection and performance tracking."""
        self.redis_client: Optional[redis.Redis] = None
        self.metadata_ttl = settings.metadata_cache_ttl
        self.download_ttl = settings.download_cache_ttl
        
        # Performance tracking
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0,
            'total_requests': 0
        }
        
        # Cache key prefixes
        self.METADATA_PREFIX = "metadata:"
        self.DOWNLOAD_PREFIX = "download:"
        self.STATS_PREFIX = "stats:"
        self.TASK_PREFIX = "task:"
    
    async def connect(self) -> bool:
        """
        Establish Redis connection with error handling.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if settings.redis_password:
                self.redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            else:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            # Test connection
            await self.redis_client.ping()
            return True
            
        except Exception as e:
            print(f"Redis connection failed: {e}")
            self.redis_client = None
            return False
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
    
    def _generate_cache_key(self, prefix: str, identifier: str) -> str:
        """
        Generate consistent cache key with hash for long URLs.
        
        Args:
            prefix: Cache key prefix (metadata:, download:, etc.)
            identifier: Unique identifier (usually URL)
            
        Returns:
            str: Generated cache key
        """
        # Hash long identifiers to keep keys manageable
        if len(identifier) > 100:
            identifier = hashlib.md5(identifier.encode()).hexdigest()
        
        return f"{prefix}{identifier}"
    
    async def get_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached video metadata.
        
        Args:
            url: Video URL
            
        Returns:
            Dict containing metadata or None if not cached
        """
        if not self.redis_client:
            await self.connect()
            
        if not self.redis_client:
            self.stats['errors'] += 1
            return None
        
        try:
            self.stats['total_requests'] += 1
            cache_key = self._generate_cache_key(self.METADATA_PREFIX, url)
            
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                self.stats['hits'] += 1
                return json.loads(cached_data)
            else:
                self.stats['misses'] += 1
                return None
                
        except Exception as e:
            print(f"Cache get error: {e}")
            self.stats['errors'] += 1
            return None
    
    async def cache_metadata(self, url: str, metadata: Dict[str, Any]) -> bool:
        """
        Cache video metadata with TTL.
        
        Args:
            url: Video URL
            metadata: Metadata dictionary to cache
            
        Returns:
            bool: True if cached successfully, False otherwise
        """
        if not self.redis_client:
            await self.connect()
            
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_cache_key(self.METADATA_PREFIX, url)
            
            # Add timestamp to metadata
            metadata_with_timestamp = {
                **metadata,
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'cache_ttl': self.metadata_ttl
            }
            
            await self.redis_client.setex(
                cache_key,
                self.metadata_ttl,
                json.dumps(metadata_with_timestamp)
            )
            
            return True
            
        except Exception as e:
            print(f"Cache set error: {e}")
            self.stats['errors'] += 1
            return False
    
    async def track_download(self, task_id: str, status: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Track download progress and status.
        
        Args:
            task_id: Unique task identifier
            status: Download status (pending, processing, completed, failed)
            metadata: Optional additional metadata
            
        Returns:
            bool: True if tracked successfully, False otherwise
        """
        if not self.redis_client:
            await self.connect()
            
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_cache_key(self.TASK_PREFIX, task_id)
            
            task_data = {
                'task_id': task_id,
                'status': status,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'metadata': metadata or {}
            }
            
            await self.redis_client.setex(
                cache_key,
                self.download_ttl,
                json.dumps(task_data)
            )
            
            return True
            
        except Exception as e:
            print(f"Download tracking error: {e}")
            self.stats['errors'] += 1
            return False
    
    async def get_download_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get download task status.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dict containing task status or None if not found
        """
        if not self.redis_client:
            await self.connect()
            
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key(self.TASK_PREFIX, task_id)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
            
        except Exception as e:
            print(f"Download status get error: {e}")
            self.stats['errors'] += 1
            return None
    
    async def invalidate_cache(self, pattern: str) -> int:
        """
        Invalidate cache entries matching pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "metadata:*youtube*")
            
        Returns:
            int: Number of keys deleted
        """
        if not self.redis_client:
            await self.connect()
            
        if not self.redis_client:
            return 0
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                return deleted
            return 0
            
        except Exception as e:
            print(f"Cache invalidation error: {e}")
            self.stats['errors'] += 1
            return 0
    
    async def clear_expired_downloads(self) -> int:
        """
        Clear expired download tasks.
        
        Returns:
            int: Number of expired tasks cleared
        """
        pattern = f"{self.TASK_PREFIX}*"
        return await self.invalidate_cache(pattern)
    
    def get_cache_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get cache performance statistics.
        
        Returns:
            Dict containing cache hit rate, miss rate, and error rate
        """
        total = self.stats['total_requests']
        
        if total == 0:
            return {
                'hit_rate': 0.0,
                'miss_rate': 0.0,
                'error_rate': 0.0,
                'total_requests': 0,
                'hits': 0,
                'misses': 0,
                'errors': 0
            }
        
        return {
            'hit_rate': round((self.stats['hits'] / total) * 100, 2),
            'miss_rate': round((self.stats['misses'] / total) * 100, 2),
            'error_rate': round((self.stats['errors'] / total) * 100, 2),
            'total_requests': total,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'errors': self.stats['errors']
        }
    
    async def reset_stats(self):
        """Reset performance statistics."""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0,
            'total_requests': 0
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform Redis health check.
        
        Returns:
            Dict containing health status and connection info
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            if not self.redis_client:
                return {
                    'status': 'unhealthy',
                    'connected': False,
                    'error': 'No Redis connection'
                }
            
            # Test basic operations
            start_time = time.time()
            await self.redis_client.ping()
            response_time = (time.time() - start_time) * 1000  # ms
            
            info = await self.redis_client.info()
            
            return {
                'status': 'healthy',
                'connected': True,
                'response_time_ms': round(response_time, 2),
                'redis_version': info.get('redis_version', 'unknown'),
                'used_memory_human': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'cache_stats': self.get_cache_stats()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e)
            }


# Global cache manager instance
cache_manager = CacheManager()