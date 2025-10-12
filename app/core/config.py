"""
Configuration management for VidNet application.
"""
import os
from typing import Optional


class Settings:
    """Application settings with environment variable support."""
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD")
    
    # Cache TTL settings (in seconds)
    metadata_cache_ttl: int = int(os.getenv("METADATA_CACHE_TTL", "3600"))  # 1 hour
    download_cache_ttl: int = int(os.getenv("DOWNLOAD_CACHE_TTL", "1800"))  # 30 minutes
    
    # Rate Limiting Configuration
    rate_limit_requests_per_minute: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
    rate_limit_requests_per_hour: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_HOUR", "1000"))
    rate_limit_burst_limit: int = int(os.getenv("RATE_LIMIT_BURST_LIMIT", "10"))
    rate_limit_queue_size: int = int(os.getenv("RATE_LIMIT_QUEUE_SIZE", "100"))
    rate_limit_queue_timeout: int = int(os.getenv("RATE_LIMIT_QUEUE_TIMEOUT", "30"))
    rate_limit_enable_graceful_degradation: bool = os.getenv("RATE_LIMIT_ENABLE_GRACEFUL_DEGRADATION", "true").lower() == "true"
    
    # Performance Monitoring Configuration
    performance_monitoring_enabled: bool = os.getenv("PERFORMANCE_MONITORING_ENABLED", "true").lower() == "true"
    performance_max_metrics_history: int = int(os.getenv("PERFORMANCE_MAX_METRICS_HISTORY", "10000"))
    performance_response_time_warning: float = float(os.getenv("PERFORMANCE_RESPONSE_TIME_WARNING", "3.0"))
    performance_response_time_critical: float = float(os.getenv("PERFORMANCE_RESPONSE_TIME_CRITICAL", "10.0"))
    performance_cpu_warning: float = float(os.getenv("PERFORMANCE_CPU_WARNING", "80.0"))
    performance_cpu_critical: float = float(os.getenv("PERFORMANCE_CPU_CRITICAL", "95.0"))
    performance_memory_warning: float = float(os.getenv("PERFORMANCE_MEMORY_WARNING", "80.0"))
    performance_memory_critical: float = float(os.getenv("PERFORMANCE_MEMORY_CRITICAL", "95.0"))
    performance_error_rate_warning: float = float(os.getenv("PERFORMANCE_ERROR_RATE_WARNING", "5.0"))
    performance_error_rate_critical: float = float(os.getenv("PERFORMANCE_ERROR_RATE_CRITICAL", "15.0"))
    
    # Graceful Degradation Configuration
    degradation_concurrent_threshold: int = int(os.getenv("DEGRADATION_CONCURRENT_THRESHOLD", "80"))
    
    # Application settings
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    def __init__(self):
        """Initialize settings from environment variables."""
        pass


# Global settings instance
settings = Settings()