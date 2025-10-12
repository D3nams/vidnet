"""
Rate limiting middleware for VidNet API.

This module provides rate limiting functionality to handle 100+ concurrent users
with request queuing and graceful degradation for high load scenarios.
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from collections import defaultdict, deque
from dataclasses import dataclass
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from contextlib import asynccontextmanager

from app.core.config import settings


logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    queue_size: int = 100
    queue_timeout: int = 30
    enable_graceful_degradation: bool = True


class RateLimiter:
    """
    Advanced rate limiter with Redis backend and request queuing.
    
    Features:
    - Per-IP rate limiting with sliding window
    - Request queuing for burst handling
    - Graceful degradation under high load
    - Redis-based distributed rate limiting
    - Performance metrics collection
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        
        # In-memory fallback for when Redis is unavailable
        self.memory_store: Dict[str, deque] = defaultdict(deque)
        self.request_queues: Dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue(maxsize=config.queue_size))
        
        # Performance metrics
        self.metrics = {
            'total_requests': 0,
            'rate_limited_requests': 0,
            'queued_requests': 0,
            'degraded_requests': 0,
            'redis_errors': 0,
            'average_response_time': 0.0,
            'concurrent_requests': 0,
            'peak_concurrent_requests': 0
        }
        
        # Graceful degradation settings
        self.degradation_threshold = 80  # Concurrent requests threshold
        self.degradation_active = False
        
        logger.info(f"Rate limiter initialized with config: {config}")
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
                self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                await self.redis_client.ping()
                logger.info("Rate limiter connected to Redis")
            else:
                logger.warning("Redis not configured, using in-memory rate limiting")
        except Exception as e:
            logger.error(f"Failed to connect to Redis for rate limiting: {e}")
            self.redis_client = None
    
    async def cleanup(self):
        """Cleanup Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
    
    def get_client_id(self, request: Request) -> str:
        """
        Get client identifier for rate limiting.
        
        Args:
            request: FastAPI request object
            
        Returns:
            str: Client identifier (IP address or forwarded IP)
        """
        # Check for forwarded IP (behind proxy/CDN)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # Check for real IP (behind proxy)
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return request.client.host if request.client else 'unknown'
    
    async def is_rate_limited(self, client_id: str) -> tuple[bool, Dict[str, Any]]:
        """
        Check if client is rate limited.
        
        Args:
            client_id: Client identifier
            
        Returns:
            tuple: (is_limited, rate_limit_info)
        """
        current_time = time.time()
        
        try:
            if self.redis_client:
                return await self._check_rate_limit_redis(client_id, current_time)
            else:
                return await self._check_rate_limit_memory(client_id, current_time)
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            self.metrics['redis_errors'] += 1
            # Fall back to memory-based rate limiting
            return await self._check_rate_limit_memory(client_id, current_time)
    
    async def _check_rate_limit_redis(self, client_id: str, current_time: float) -> tuple[bool, Dict[str, Any]]:
        """Redis-based rate limit check with sliding window."""
        minute_key = f"rate_limit:minute:{client_id}"
        hour_key = f"rate_limit:hour:{client_id}"
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis_client.pipeline()
        
        # Sliding window for minute limit
        minute_window = current_time - 60
        pipe.zremrangebyscore(minute_key, 0, minute_window)
        pipe.zcard(minute_key)
        pipe.zadd(minute_key, {str(current_time): current_time})
        pipe.expire(minute_key, 60)
        
        # Sliding window for hour limit
        hour_window = current_time - 3600
        pipe.zremrangebyscore(hour_key, 0, hour_window)
        pipe.zcard(hour_key)
        pipe.zadd(hour_key, {str(current_time): current_time})
        pipe.expire(hour_key, 3600)
        
        results = await pipe.execute()
        
        minute_count = results[1]
        hour_count = results[5]
        
        # Check limits
        minute_limited = minute_count > self.config.requests_per_minute
        hour_limited = hour_count > self.config.requests_per_hour
        
        rate_limit_info = {
            'requests_per_minute': minute_count,
            'requests_per_hour': hour_count,
            'minute_limit': self.config.requests_per_minute,
            'hour_limit': self.config.requests_per_hour,
            'reset_time': int(current_time + 60)
        }
        
        return minute_limited or hour_limited, rate_limit_info
    
    async def _check_rate_limit_memory(self, client_id: str, current_time: float) -> tuple[bool, Dict[str, Any]]:
        """Memory-based rate limit check (fallback)."""
        if client_id not in self.memory_store:
            self.memory_store[client_id] = deque()
        
        requests = self.memory_store[client_id]
        
        # Remove old requests (older than 1 hour)
        while requests and requests[0] < current_time - 3600:
            requests.popleft()
        
        # Add current request
        requests.append(current_time)
        
        # Count requests in last minute and hour
        minute_count = sum(1 for req_time in requests if req_time > current_time - 60)
        hour_count = len(requests)
        
        # Check limits
        minute_limited = minute_count > self.config.requests_per_minute
        hour_limited = hour_count > self.config.requests_per_hour
        
        rate_limit_info = {
            'requests_per_minute': minute_count,
            'requests_per_hour': hour_count,
            'minute_limit': self.config.requests_per_minute,
            'hour_limit': self.config.requests_per_hour,
            'reset_time': int(current_time + 60)
        }
        
        return minute_limited or hour_limited, rate_limit_info
    
    async def queue_request(self, client_id: str, request_handler: Callable) -> Any:
        """
        Queue request for processing with timeout.
        
        Args:
            client_id: Client identifier
            request_handler: Async function to handle the request
            
        Returns:
            Response from request handler
            
        Raises:
            HTTPException: If queue is full or timeout occurs
        """
        queue = self.request_queues[client_id]
        
        try:
            # Check if queue is full
            if queue.full():
                self.metrics['rate_limited_requests'] += 1
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "queue_full",
                        "message": "Request queue is full. Please try again later.",
                        "retry_after": 30
                    }
                )
            
            # Add request to queue
            future = asyncio.Future()
            await queue.put((request_handler, future))
            self.metrics['queued_requests'] += 1
            
            # Wait for processing with timeout
            try:
                result = await asyncio.wait_for(future, timeout=self.config.queue_timeout)
                return result
            except asyncio.TimeoutError:
                self.metrics['rate_limited_requests'] += 1
                raise HTTPException(
                    status_code=408,
                    detail={
                        "error": "queue_timeout",
                        "message": "Request timed out in queue. Please try again.",
                        "retry_after": 10
                    }
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Queue request error: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "queue_error",
                    "message": "Internal error processing queued request"
                }
            )
    
    def should_degrade_service(self) -> bool:
        """
        Check if service should be degraded due to high load.
        
        Returns:
            bool: True if service should be degraded
        """
        if not self.config.enable_graceful_degradation:
            return False
        
        concurrent_requests = self.metrics['concurrent_requests']
        
        # Activate degradation if concurrent requests exceed threshold
        if concurrent_requests > self.degradation_threshold:
            if not self.degradation_active:
                self.degradation_active = True
                logger.warning(f"Activating graceful degradation: {concurrent_requests} concurrent requests")
            return True
        else:
            if self.degradation_active:
                self.degradation_active = False
                logger.info("Deactivating graceful degradation")
            return False
    
    def get_degraded_response(self, request: Request) -> JSONResponse:
        """
        Get degraded service response.
        
        Args:
            request: FastAPI request
            
        Returns:
            JSONResponse with degraded service message
        """
        self.metrics['degraded_requests'] += 1
        
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": "service_degraded",
                "message": "Service is temporarily degraded due to high load",
                "suggestion": "Please try again in a few moments",
                "retry_after": 30,
                "degradation_active": True
            }
        )
    
    def update_metrics(self, response_time: float):
        """
        Update performance metrics.
        
        Args:
            response_time: Request response time in seconds
        """
        self.metrics['total_requests'] += 1
        
        # Update average response time (exponential moving average)
        alpha = 0.1  # Smoothing factor
        if self.metrics['average_response_time'] == 0:
            self.metrics['average_response_time'] = response_time
        else:
            self.metrics['average_response_time'] = (
                alpha * response_time + 
                (1 - alpha) * self.metrics['average_response_time']
            )
    
    @asynccontextmanager
    async def track_concurrent_request(self):
        """Context manager to track concurrent requests."""
        self.metrics['concurrent_requests'] += 1
        self.metrics['peak_concurrent_requests'] = max(
            self.metrics['peak_concurrent_requests'],
            self.metrics['concurrent_requests']
        )
        
        try:
            yield
        finally:
            self.metrics['concurrent_requests'] -= 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current rate limiter metrics."""
        return {
            **self.metrics,
            'degradation_active': self.degradation_active,
            'degradation_threshold': self.degradation_threshold,
            'config': {
                'requests_per_minute': self.config.requests_per_minute,
                'requests_per_hour': self.config.requests_per_hour,
                'burst_limit': self.config.burst_limit,
                'queue_size': self.config.queue_size,
                'queue_timeout': self.config.queue_timeout
            }
        }


# Global rate limiter instance
rate_limiter = RateLimiter(RateLimitConfig())


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """
    Rate limiting middleware for FastAPI.
    
    Args:
        request: FastAPI request
        call_next: Next middleware/endpoint
        
    Returns:
        Response with rate limiting applied
    """
    start_time = time.time()
    
    # Skip rate limiting for health checks and static files
    if request.url.path in ['/health', '/'] or request.url.path.startswith('/static'):
        response = await call_next(request)
        return response
    
    client_id = rate_limiter.get_client_id(request)
    
    try:
        async with rate_limiter.track_concurrent_request():
            # Check for service degradation
            if rate_limiter.should_degrade_service():
                # Only degrade non-essential endpoints
                if request.url.path.startswith('/api/v1/download') or request.url.path.startswith('/api/v1/extract-audio'):
                    return rate_limiter.get_degraded_response(request)
            
            # Check rate limits
            is_limited, rate_info = await rate_limiter.is_rate_limited(client_id)
            
            if is_limited:
                rate_limiter.metrics['rate_limited_requests'] += 1
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "rate_limit_exceeded",
                        "message": "Rate limit exceeded. Please slow down your requests.",
                        "rate_limit_info": rate_info,
                        "retry_after": 60
                    },
                    headers={
                        "X-RateLimit-Limit": str(rate_limiter.config.requests_per_minute),
                        "X-RateLimit-Remaining": str(max(0, rate_limiter.config.requests_per_minute - rate_info['requests_per_minute'])),
                        "X-RateLimit-Reset": str(rate_info['reset_time']),
                        "Retry-After": "60"
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to response
            response.headers["X-RateLimit-Limit"] = str(rate_limiter.config.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(max(0, rate_limiter.config.requests_per_minute - rate_info['requests_per_minute']))
            response.headers["X-RateLimit-Reset"] = str(rate_info['reset_time'])
            
            return response
            
    except Exception as e:
        logger.error(f"Rate limiting middleware error: {e}")
        # Continue without rate limiting on error
        response = await call_next(request)
        return response
    
    finally:
        # Update metrics
        response_time = time.time() - start_time
        rate_limiter.update_metrics(response_time)