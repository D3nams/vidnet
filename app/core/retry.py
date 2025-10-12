"""
Retry logic with exponential backoff for VidNet MVP.

This module provides retry mechanisms for failed operations with
configurable backoff strategies and error handling.
"""

import asyncio
import logging
import time
from typing import Callable, Any, Optional, Type, Union, List
from functools import wraps
import random

from app.core.exceptions import VidNetException, NetworkError, ProcessingTimeoutError


logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        timeout: Optional[float] = None
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds before first retry
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff calculation
            jitter: Whether to add random jitter to delays
            timeout: Overall timeout for all retry attempts
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.timeout = timeout
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff: base_delay * (exponential_base ^ attempt)
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter to avoid thundering herd
        if self.jitter:
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class RetryManager:
    """
    Manages retry logic with exponential backoff.
    
    Provides both decorator and direct retry functionality for handling
    transient failures in video processing operations.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry manager.
        
        Args:
            config: Retry configuration, uses defaults if None
        """
        self.config = config or RetryConfig()
    
    async def retry_async(
        self,
        func: Callable,
        *args,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        config: Optional[RetryConfig] = None,
        **kwargs
    ) -> Any:
        """
        Retry an async function with exponential backoff.
        
        Args:
            func: Async function to retry
            *args: Positional arguments for the function
            retryable_exceptions: List of exception types that should trigger retry
            config: Override retry configuration
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Raises:
            Last exception if all retries fail
        """
        retry_config = config or self.config
        retryable_exceptions = retryable_exceptions or [
            NetworkError, ProcessingTimeoutError, ConnectionError, TimeoutError
        ]
        
        start_time = time.time()
        last_exception = None
        
        for attempt in range(retry_config.max_attempts):
            try:
                # Check overall timeout
                if retry_config.timeout:
                    elapsed = time.time() - start_time
                    if elapsed >= retry_config.timeout:
                        raise ProcessingTimeoutError(
                            timeout_seconds=int(retry_config.timeout)
                        )
                
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Log successful retry if this wasn't the first attempt
                if attempt > 0:
                    logger.info(
                        f"Function {func.__name__} succeeded on attempt {attempt + 1}"
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this exception type should trigger a retry
                should_retry = False
                
                # Check if it's a VidNetException with retryable flag
                if isinstance(e, VidNetException):
                    should_retry = e.retryable
                else:
                    # Check if it's in the retryable exceptions list
                    should_retry = any(
                        isinstance(e, exc_type) for exc_type in retryable_exceptions
                    )
                
                # Don't retry if this is the last attempt or exception is not retryable
                if attempt == retry_config.max_attempts - 1 or not should_retry:
                    logger.error(
                        f"Function {func.__name__} failed after {attempt + 1} attempts: {e}"
                    )
                    raise e
                
                # Calculate delay for next attempt
                delay = retry_config.calculate_delay(attempt)
                
                logger.warning(
                    f"Function {func.__name__} failed on attempt {attempt + 1}, "
                    f"retrying in {delay:.2f}s: {e}"
                )
                
                # Wait before next attempt
                await asyncio.sleep(delay)
        
        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
    
    def retry_sync(
        self,
        func: Callable,
        *args,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        config: Optional[RetryConfig] = None,
        **kwargs
    ) -> Any:
        """
        Retry a synchronous function with exponential backoff.
        
        Args:
            func: Synchronous function to retry
            *args: Positional arguments for the function
            retryable_exceptions: List of exception types that should trigger retry
            config: Override retry configuration
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Raises:
            Last exception if all retries fail
        """
        retry_config = config or self.config
        retryable_exceptions = retryable_exceptions or [
            NetworkError, ProcessingTimeoutError, ConnectionError, TimeoutError
        ]
        
        start_time = time.time()
        last_exception = None
        
        for attempt in range(retry_config.max_attempts):
            try:
                # Check overall timeout
                if retry_config.timeout:
                    elapsed = time.time() - start_time
                    if elapsed >= retry_config.timeout:
                        raise ProcessingTimeoutError(
                            timeout_seconds=int(retry_config.timeout)
                        )
                
                # Execute the function
                result = func(*args, **kwargs)
                
                # Log successful retry if this wasn't the first attempt
                if attempt > 0:
                    logger.info(
                        f"Function {func.__name__} succeeded on attempt {attempt + 1}"
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this exception type should trigger a retry
                should_retry = False
                
                # Check if it's a VidNetException with retryable flag
                if isinstance(e, VidNetException):
                    should_retry = e.retryable
                else:
                    # Check if it's in the retryable exceptions list
                    should_retry = any(
                        isinstance(e, exc_type) for exc_type in retryable_exceptions
                    )
                
                # Don't retry if this is the last attempt or exception is not retryable
                if attempt == retry_config.max_attempts - 1 or not should_retry:
                    logger.error(
                        f"Function {func.__name__} failed after {attempt + 1} attempts: {e}"
                    )
                    raise e
                
                # Calculate delay for next attempt
                delay = retry_config.calculate_delay(attempt)
                
                logger.warning(
                    f"Function {func.__name__} failed on attempt {attempt + 1}, "
                    f"retrying in {delay:.2f}s: {e}"
                )
                
                # Wait before next attempt
                time.sleep(delay)
        
        # This should never be reached, but just in case
        if last_exception:
            raise last_exception


# Global retry manager instance
retry_manager = RetryManager()


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    timeout: Optional[float] = None,
    retryable_exceptions: Optional[List[Type[Exception]]] = None
):
    """
    Decorator for async functions with retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds before first retry
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        timeout: Overall timeout for all retry attempts
        retryable_exceptions: List of exception types that should trigger retry
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
                timeout=timeout
            )
            
            return await retry_manager.retry_async(
                func, *args,
                retryable_exceptions=retryable_exceptions,
                config=config,
                **kwargs
            )
        
        return wrapper
    return decorator


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    timeout: Optional[float] = None,
    retryable_exceptions: Optional[List[Type[Exception]]] = None
):
    """
    Decorator for synchronous functions with retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds before first retry
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        timeout: Overall timeout for all retry attempts
        retryable_exceptions: List of exception types that should trigger retry
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
                timeout=timeout
            )
            
            return retry_manager.retry_sync(
                func, *args,
                retryable_exceptions=retryable_exceptions,
                config=config,
                **kwargs
            )
        
        return wrapper
    return decorator