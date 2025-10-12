from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import time

from app.api.metadata import router as metadata_router
from app.api.downloads import router as downloads_router
from app.api.files import router as files_router
from app.api.monitoring import router as monitoring_router
from app.api.analytics import router as analytics_router
from app.api.storage import router as storage_router
from app.services.download_manager import download_manager
from app.services.performance_monitor import performance_monitor
from app.services.storage_manager import storage_manager
from app.middleware.rate_limiter import rate_limiter, rate_limit_middleware, RateLimitConfig
from app.middleware.error_handler import ErrorHandlingMiddleware
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(
    title="VidNet API",
    description="High-performance video downloader API",
    version="1.0.0"
)

# Error handling middleware (should be first)
app.add_middleware(ErrorHandlingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Validation errors are now handled by ErrorHandlingMiddleware

# Performance monitoring middleware
@app.middleware("http")
async def performance_monitoring_middleware(request: Request, call_next):
    """Performance monitoring and request timing middleware."""
    start_time = time.time()
    request.state.start_time = start_time
    
    # Get client information
    client_id = rate_limiter.get_client_id(request)
    user_agent = request.headers.get('user-agent', '')
    
    # Track request with performance monitor
    async with performance_monitor.track_request(
        endpoint=request.url.path,
        method=request.method,
        client_id=client_id,
        user_agent=user_agent
    ):
        response = await call_next(request)
    
    return response

# Include API routers
app.include_router(metadata_router)
app.include_router(downloads_router)
app.include_router(files_router)
app.include_router(monitoring_router)
app.include_router(analytics_router)
app.include_router(storage_router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger = logging.getLogger(__name__)
    logger.info("Starting VidNet API services")
    
    # Initialize rate limiter
    rate_limiter.config = RateLimitConfig(
        requests_per_minute=settings.rate_limit_requests_per_minute,
        requests_per_hour=settings.rate_limit_requests_per_hour,
        burst_limit=settings.rate_limit_burst_limit,
        queue_size=settings.rate_limit_queue_size,
        queue_timeout=settings.rate_limit_queue_timeout,
        enable_graceful_degradation=settings.rate_limit_enable_graceful_degradation
    )
    await rate_limiter.initialize()
    logger.info("Rate limiter initialized")
    
    # Start performance monitoring
    if settings.performance_monitoring_enabled:
        # Update performance monitor thresholds
        performance_monitor.thresholds.update({
            'response_time_warning': settings.performance_response_time_warning,
            'response_time_critical': settings.performance_response_time_critical,
            'cpu_warning': settings.performance_cpu_warning,
            'cpu_critical': settings.performance_cpu_critical,
            'memory_warning': settings.performance_memory_warning,
            'memory_critical': settings.performance_memory_critical,
            'error_rate_warning': settings.performance_error_rate_warning,
            'error_rate_critical': settings.performance_error_rate_critical
        })
        
        await performance_monitor.start_monitoring()
        logger.info("Performance monitoring started")
    
    # Start download manager
    await download_manager.start()
    logger.info("Download manager started")
    
    # Start storage manager
    await storage_manager.start()
    logger.info("Storage manager started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown."""
    logger = logging.getLogger(__name__)
    logger.info("Shutting down VidNet API services")
    
    # Stop performance monitoring
    if settings.performance_monitoring_enabled:
        await performance_monitor.stop_monitoring()
        logger.info("Performance monitoring stopped")
    
    # Cleanup rate limiter
    await rate_limiter.cleanup()
    logger.info("Rate limiter cleaned up")
    
    # Stop download manager
    await download_manager.stop()
    logger.info("Download manager stopped")
    
    # Stop storage manager
    await storage_manager.stop()
    logger.info("Storage manager stopped")

@app.get("/")
async def root():
    """Serve the main application page"""
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}