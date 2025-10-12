"""
Performance monitoring API endpoints for VidNet MVP.

This module provides endpoints for accessing performance metrics, system health,
and monitoring data for the VidNet application.
"""

import time
import logging
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.performance_monitor import performance_monitor
from app.services.metrics_collector import metrics_collector
from app.middleware.rate_limiter import rate_limiter


logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get(
    "/health",
    summary="System health check",
    description="Get comprehensive system health status with performance metrics and alerts"
)
async def get_health_status() -> JSONResponse:
    """
    Get comprehensive system health status.
    
    Returns:
        JSONResponse with health status, alerts, and system metrics
    """
    try:
        start_time = time.time()
        
        health_status = performance_monitor.get_health_status()
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200 if health_status['status'] == 'healthy' else 503,
            content={
                "success": True,
                "data": health_status,
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "health_check_error",
                "message": "Failed to retrieve system health status",
                "details": str(e)
            }
        )


@router.get(
    "/metrics",
    summary="Performance metrics",
    description="Get detailed performance metrics for endpoints and system resources"
)
async def get_performance_metrics(
    endpoint: Optional[str] = Query(None, description="Specific endpoint to get metrics for"),
    time_window: int = Query(60, description="Time window in minutes for metrics", ge=1, le=1440)
) -> JSONResponse:
    """
    Get performance metrics.
    
    Args:
        endpoint: Optional specific endpoint to get metrics for
        time_window: Time window in minutes (1-1440)
        
    Returns:
        JSONResponse with performance metrics
    """
    try:
        start_time = time.time()
        
        # Get endpoint statistics
        endpoint_stats = performance_monitor.get_endpoint_stats(endpoint)
        
        # Get performance summary for time window
        performance_summary = performance_monitor.get_performance_summary(time_window)
        
        # Get system metrics
        system_metrics = performance_monitor.get_system_metrics()
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "endpoint_stats": endpoint_stats,
                    "performance_summary": performance_summary,
                    "system_metrics": system_metrics,
                    "time_window_minutes": time_window
                },
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Performance metrics error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "metrics_error",
                "message": "Failed to retrieve performance metrics",
                "details": str(e)
            }
        )


@router.get(
    "/rate-limit-stats",
    summary="Rate limiting statistics",
    description="Get current rate limiting statistics and configuration"
)
async def get_rate_limit_stats() -> JSONResponse:
    """
    Get rate limiting statistics.
    
    Returns:
        JSONResponse with rate limiting metrics and configuration
    """
    try:
        start_time = time.time()
        
        rate_limit_metrics = rate_limiter.get_metrics()
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": rate_limit_metrics,
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Rate limit stats error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "rate_limit_stats_error",
                "message": "Failed to retrieve rate limiting statistics",
                "details": str(e)
            }
        )


@router.get(
    "/system",
    summary="System resource metrics",
    description="Get current system resource usage (CPU, memory, disk, connections)"
)
async def get_system_metrics() -> JSONResponse:
    """
    Get current system resource metrics.
    
    Returns:
        JSONResponse with system resource usage
    """
    try:
        start_time = time.time()
        
        system_metrics = performance_monitor.get_system_metrics()
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": system_metrics,
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"System metrics error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "system_metrics_error",
                "message": "Failed to retrieve system metrics",
                "details": str(e)
            }
        )


@router.get(
    "/endpoints",
    summary="Endpoint performance statistics",
    description="Get performance statistics for all API endpoints"
)
async def get_endpoint_performance() -> JSONResponse:
    """
    Get endpoint performance statistics.
    
    Returns:
        JSONResponse with endpoint performance data
    """
    try:
        start_time = time.time()
        
        endpoint_stats = performance_monitor.get_endpoint_stats()
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "endpoints": endpoint_stats,
                    "total_endpoints": len(endpoint_stats)
                },
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Endpoint performance error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "endpoint_performance_error",
                "message": "Failed to retrieve endpoint performance statistics",
                "details": str(e)
            }
        )


@router.get(
    "/alerts",
    summary="Performance alerts",
    description="Get current performance alerts and thresholds"
)
async def get_performance_alerts() -> JSONResponse:
    """
    Get current performance alerts.
    
    Returns:
        JSONResponse with performance alerts and thresholds
    """
    try:
        start_time = time.time()
        
        health_status = performance_monitor.get_health_status()
        alerts = health_status.get('alerts', [])
        thresholds = health_status.get('thresholds', {})
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "alerts": alerts,
                    "alert_count": len(alerts),
                    "critical_alerts": len([a for a in alerts if a.get('level') == 'critical']),
                    "warning_alerts": len([a for a in alerts if a.get('level') == 'warning']),
                    "thresholds": thresholds
                },
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Performance alerts error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "alerts_error",
                "message": "Failed to retrieve performance alerts",
                "details": str(e)
            }
        )


@router.post(
    "/export",
    summary="Export metrics",
    description="Export performance metrics to file"
)
async def export_metrics(
    time_window_hours: int = Query(24, description="Time window in hours for metrics export", ge=1, le=168)
) -> JSONResponse:
    """
    Export performance metrics to file.
    
    Args:
        time_window_hours: Time window in hours (1-168)
    
    Returns:
        JSONResponse with export status
    """
    try:
        start_time = time.time()
        
        # Generate filename with timestamp
        timestamp = int(time.time())
        filename = f"vidnet_metrics_{timestamp}.json"
        filepath = f"logs/{filename}"
        
        # Export comprehensive metrics from metrics collector
        metrics_collector.export_metrics(filepath, time_window_hours)
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "exported_file": filepath,
                    "timestamp": timestamp,
                    "time_window_hours": time_window_hours
                },
                "message": f"Metrics exported to {filepath}",
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Export metrics error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "export_error",
                "message": "Failed to export performance metrics",
                "details": str(e)
            }
        )


@router.get(
    "/dashboard",
    summary="Monitoring dashboard data",
    description="Get comprehensive monitoring data for dashboard display"
)
async def get_dashboard_data() -> JSONResponse:
    """
    Get comprehensive monitoring data for dashboard.
    
    Returns:
        JSONResponse with dashboard data
    """
    try:
        start_time = time.time()
        
        # Get comprehensive dashboard data from metrics collector
        dashboard_data = metrics_collector.get_dashboard_data()
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": dashboard_data,
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Dashboard data error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "dashboard_error",
                "message": "Failed to retrieve dashboard data",
                "details": str(e)
            }
        )

@router.get(
    "/business-metrics",
    summary="Business metrics",
    description="Get business-specific metrics including downloads, platforms, and user engagement"
)
async def get_business_metrics() -> JSONResponse:
    """
    Get business-specific metrics.
    
    Returns:
        JSONResponse with business metrics
    """
    try:
        start_time = time.time()
        
        # Get platform metrics
        platform_metrics = metrics_collector.get_platform_metrics()
        
        # Get quality metrics
        quality_metrics = metrics_collector.get_quality_metrics()
        
        # Get user engagement metrics
        user_engagement = metrics_collector.get_user_engagement_metrics()
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "platform_metrics": platform_metrics,
                    "quality_metrics": quality_metrics,
                    "user_engagement": user_engagement,
                    "business_summary": {
                        "total_downloads": metrics_collector.business_metrics.downloads_total,
                        "total_audio_extractions": metrics_collector.business_metrics.audio_extractions_total,
                        "downloads_by_platform": dict(metrics_collector.business_metrics.downloads_by_platform),
                        "downloads_by_quality": dict(metrics_collector.business_metrics.downloads_by_quality)
                    }
                },
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Business metrics error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "business_metrics_error",
                "message": "Failed to retrieve business metrics",
                "details": str(e)
            }
        )


@router.get(
    "/cache-metrics",
    summary="Cache performance metrics",
    description="Get detailed cache performance metrics and optimization alerts"
)
async def get_cache_metrics() -> JSONResponse:
    """
    Get cache performance metrics.
    
    Returns:
        JSONResponse with cache metrics and alerts
    """
    try:
        start_time = time.time()
        
        cache_metrics = metrics_collector.get_cache_metrics()
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": cache_metrics,
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Cache metrics error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "cache_metrics_error",
                "message": "Failed to retrieve cache metrics",
                "details": str(e)
            }
        )


@router.get(
    "/performance-alerts",
    summary="Performance optimization alerts",
    description="Get current performance alerts and optimization recommendations"
)
async def get_performance_optimization_alerts() -> JSONResponse:
    """
    Get performance alerts and optimization recommendations.
    
    Returns:
        JSONResponse with performance alerts
    """
    try:
        start_time = time.time()
        
        alerts = metrics_collector.get_performance_alerts()
        
        # Categorize alerts
        critical_alerts = [a for a in alerts if a.get('level') == 'critical']
        warning_alerts = [a for a in alerts if a.get('level') == 'warning']
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "alerts": alerts,
                    "summary": {
                        "total_alerts": len(alerts),
                        "critical_alerts": len(critical_alerts),
                        "warning_alerts": len(warning_alerts)
                    },
                    "critical_alerts": critical_alerts,
                    "warning_alerts": warning_alerts,
                    "thresholds": metrics_collector.alert_thresholds
                },
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Performance alerts error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "performance_alerts_error",
                "message": "Failed to retrieve performance alerts",
                "details": str(e)
            }
        )


@router.post(
    "/track-event",
    summary="Track custom metric event",
    description="Track a custom metric event for business analytics"
)
async def track_metric_event(
    metric_name: str = Query(..., description="Name of the metric"),
    value: float = Query(..., description="Metric value"),
    metric_type: str = Query(..., description="Metric type (counter, gauge, histogram, timer)"),
    tags: Optional[str] = Query(None, description="JSON string of tags"),
    metadata: Optional[str] = Query(None, description="JSON string of metadata")
) -> JSONResponse:
    """
    Track a custom metric event.
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        metric_type: Type of metric
        tags: Optional JSON string of tags
        metadata: Optional JSON string of metadata
    
    Returns:
        JSONResponse with tracking status
    """
    try:
        start_time = time.time()
        
        # Parse optional JSON parameters
        parsed_tags = {}
        parsed_metadata = {}
        
        if tags:
            try:
                parsed_tags = json.loads(tags)
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "invalid_tags",
                        "message": "Tags must be valid JSON"
                    }
                )
        
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "invalid_metadata",
                        "message": "Metadata must be valid JSON"
                    }
                )
        
        # Validate metric type
        from app.services.metrics_collector import MetricType
        try:
            metric_type_enum = MetricType(metric_type.lower())
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "invalid_metric_type",
                    "message": f"Metric type must be one of: {[t.value for t in MetricType]}"
                }
            )
        
        # Record the metric
        metrics_collector.record_metric(
            name=metric_name,
            value=value,
            metric_type=metric_type_enum,
            tags=parsed_tags,
            metadata=parsed_metadata
        )
        
        response_time = (time.time() - start_time) * 1000
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Metric event tracked successfully",
                "data": {
                    "metric_name": metric_name,
                    "value": value,
                    "metric_type": metric_type,
                    "tags": parsed_tags,
                    "metadata": parsed_metadata
                },
                "response_time_ms": round(response_time, 2)
            }
        )
        
    except Exception as e:
        logger.error(f"Track metric event error: {e}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "track_event_error",
                "message": "Failed to track metric event",
                "details": str(e)
            }
        )