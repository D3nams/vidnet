#!/usr/bin/env python3
"""
Example script demonstrating Redis cache manager functionality.
This script shows how to use the CacheManager for video metadata caching.
"""
import asyncio
import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cache_manager import CacheManager


async def main():
    """Demonstrate cache manager functionality."""
    print("🚀 VidNet Cache Manager Demo")
    print("=" * 40)
    
    # Create cache manager instance
    cache = CacheManager()
    
    # Test connection
    print("\n1. Testing Redis connection...")
    connected = await cache.connect()
    if connected:
        print("✅ Connected to Redis successfully!")
    else:
        print("❌ Failed to connect to Redis. Make sure Redis is running.")
        return
    
    # Test health check
    print("\n2. Performing health check...")
    health = await cache.health_check()
    print(f"Status: {health['status']}")
    if health['connected']:
        print(f"Redis Version: {health.get('redis_version', 'unknown')}")
        print(f"Response Time: {health.get('response_time_ms', 0):.2f}ms")
    
    # Test metadata caching
    print("\n3. Testing metadata caching...")
    test_url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
    test_metadata = {
        "title": "Rick Astley - Never Gonna Give You Up",
        "duration": 212,
        "platform": "youtube",
        "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        "available_qualities": [
            {"quality": "720p", "format": "mp4", "filesize": 50000000},
            {"quality": "1080p", "format": "mp4", "filesize": 100000000}
        ]
    }
    
    # Cache the metadata
    cached = await cache.cache_metadata(test_url, test_metadata)
    if cached:
        print("✅ Metadata cached successfully!")
    else:
        print("❌ Failed to cache metadata")
        return
    
    # Retrieve from cache
    print("\n4. Testing cache retrieval...")
    retrieved = await cache.get_metadata(test_url)
    if retrieved:
        print("✅ Metadata retrieved from cache!")
        print(f"Title: {retrieved['title']}")
        print(f"Duration: {retrieved['duration']} seconds")
        print(f"Cached at: {retrieved['cached_at']}")
    else:
        print("❌ Failed to retrieve metadata from cache")
    
    # Test download tracking
    print("\n5. Testing download tracking...")
    task_id = "test_task_123"
    tracked = await cache.track_download(task_id, "processing", {"url": test_url})
    if tracked:
        print("✅ Download task tracked successfully!")
    
    # Get download status
    status = await cache.get_download_status(task_id)
    if status:
        print(f"Task Status: {status['status']}")
        print(f"Updated at: {status['updated_at']}")
    
    # Test cache statistics
    print("\n6. Cache performance statistics:")
    stats = cache.get_cache_stats()
    print(f"Total Requests: {stats['total_requests']}")
    print(f"Cache Hits: {stats['hits']} ({stats['hit_rate']}%)")
    print(f"Cache Misses: {stats['misses']} ({stats['miss_rate']}%)")
    print(f"Errors: {stats['errors']} ({stats['error_rate']}%)")
    
    # Test cache invalidation
    print("\n7. Testing cache invalidation...")
    invalidated = await cache.invalidate_cache("metadata:*youtube*")
    print(f"✅ Invalidated {invalidated} cache entries")
    
    # Verify invalidation worked
    retrieved_after = await cache.get_metadata(test_url)
    if retrieved_after is None:
        print("✅ Cache invalidation successful - metadata no longer cached")
    else:
        print("❌ Cache invalidation failed - metadata still cached")
    
    # Final statistics
    print("\n8. Final cache statistics:")
    final_stats = cache.get_cache_stats()
    print(f"Total Requests: {final_stats['total_requests']}")
    print(f"Cache Hit Rate: {final_stats['hit_rate']}%")
    
    # Cleanup
    await cache.disconnect()
    print("\n✅ Cache manager demo completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        sys.exit(1)