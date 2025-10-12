"""
Analytics API endpoints for collecting and serving analytics data
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import logging
from collections import defaultdict, Counter

from app.services.cache_manager import cache_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# Pydantic models for analytics data
class AnalyticsEvent(BaseModel):
    event_type: str = Field(..., description="Type of event (page_view, download_start, etc.)")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: int = Field(..., description="Unix timestamp")
    session_id: str = Field(..., description="Session identifier")
    user_agent: Optional[str] = Field(None, description="User agent string")

class AnalyticsEventBatch(BaseModel):
    events: List[AnalyticsEvent] = Field(..., description="List of analytics events")
    client_id: Optional[str] = Field(None, description="Client identifier")

class ConsentData(BaseModel):
    analytics: bool = Field(..., description="Analytics consent given")
    marketing: bool = Field(..., description="Marketing consent given")
    timestamp: int = Field(..., description="Consent timestamp")

class AdPerformanceData(BaseModel):
    performance: Dict[str, Any] = Field(..., description="Ad performance metrics")
    session_id: str = Field(..., description="Session identifier")
    timestamp: int = Field(..., description="Performance data timestamp")

class AnalyticsDashboard(BaseModel):
    total_events: int
    page_views: int
    downloads_total: int
    downloads_by_platform: Dict[str, int]
    downloads_by_quality: Dict[str, int]
    downloads_by_type: Dict[str, int]
    error_events: int
    consent_stats: Dict[str, int]
    time_range: Dict[str, str]

# In-memory analytics storage (in production, use a proper database)
analytics_storage = {
    "events": [],
    "consent_data": [],
    "session_metrics": {},
    "ad_performance": []
}

def get_client_id(request: Request) -> str:
    """Extract client ID from request headers or IP"""
    client_id = request.headers.get("X-Client-ID")
    if not client_id:
        # Fallback to IP address (hashed for privacy)
        import hashlib
        ip = request.client.host
        client_id = hashlib.sha256(f"{ip}_{datetime.now().date()}".encode()).hexdigest()[:16]
    return client_id

@router.post("/events")
async def collect_analytics_events(
    event_batch: AnalyticsEventBatch,
    request: Request
):
    """
    Collect analytics events from the frontend
    """
    try:
        client_id = event_batch.client_id or get_client_id(request)
        
        # Validate and store events
        stored_events = []
        for event in event_batch.events:
            # Add client metadata
            event_data = {
                "event_type": event.event_type,
                "data": event.data,
                "timestamp": event.timestamp,
                "session_id": event.session_id,
                "client_id": client_id,
                "user_agent": event.user_agent or request.headers.get("user-agent", ""),
                "ip_hash": hashlib.sha256(request.client.host.encode()).hexdigest()[:16]
            }
            
            # Store in memory (in production, use database)
            analytics_storage["events"].append(event_data)
            stored_events.append(event_data)
            
            # Cache recent events for quick access
            cache_key = f"analytics:recent_events:{client_id}"
            try:
                recent_events = await cache_manager.get(cache_key) or []
                recent_events.append(event_data)
                # Keep only last 50 events per client
                if len(recent_events) > 50:
                    recent_events = recent_events[-50:]
                await cache_manager.set(cache_key, recent_events, ttl=3600)  # 1 hour
            except Exception as cache_error:
                logger.warning(f"Failed to cache analytics event: {cache_error}")
        
        # Limit total stored events to prevent memory issues
        if len(analytics_storage["events"]) > 10000:
            analytics_storage["events"] = analytics_storage["events"][-5000:]
        
        logger.info(f"Stored {len(stored_events)} analytics events for client {client_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Stored {len(stored_events)} events",
                "events_stored": len(stored_events)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to store analytics events: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "analytics_storage_failed",
                "message": "Failed to store analytics events",
                "suggestion": "Please try again later"
            }
        )

@router.post("/consent")
async def record_consent(
    consent: ConsentData,
    request: Request
):
    """
    Record user consent preferences
    """
    try:
        client_id = get_client_id(request)
        
        consent_record = {
            "client_id": client_id,
            "analytics": consent.analytics,
            "marketing": consent.marketing,
            "timestamp": consent.timestamp,
            "ip_hash": hashlib.sha256(request.client.host.encode()).hexdigest()[:16],
            "user_agent": request.headers.get("user-agent", "")
        }
        
        # Store consent data
        analytics_storage["consent_data"].append(consent_record)
        
        # Cache consent for quick access
        cache_key = f"analytics:consent:{client_id}"
        try:
            await cache_manager.set(cache_key, consent_record, ttl=86400)  # 24 hours
        except Exception as cache_error:
            logger.warning(f"Failed to cache consent data: {cache_error}")
        
        logger.info(f"Recorded consent for client {client_id}: analytics={consent.analytics}, marketing={consent.marketing}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Consent preferences recorded",
                "consent_id": client_id
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to record consent: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "consent_recording_failed",
                "message": "Failed to record consent preferences",
                "suggestion": "Please try again later"
            }
        )

@router.get("/dashboard")
async def get_analytics_dashboard(
    hours: int = 24,
    request: Request = None
) -> AnalyticsDashboard:
    """
    Get analytics dashboard data for the specified time range
    """
    try:
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        start_timestamp = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)
        
        # Filter events by time range
        filtered_events = [
            event for event in analytics_storage["events"]
            if start_timestamp <= event["timestamp"] <= end_timestamp
        ]
        
        # Calculate metrics
        total_events = len(filtered_events)
        page_views = len([e for e in filtered_events if e["event_type"] == "page_view"])
        
        # Download metrics
        download_starts = [e for e in filtered_events if e["event_type"] == "download_start"]
        downloads_total = len(download_starts)
        
        # Platform breakdown
        downloads_by_platform = Counter()
        downloads_by_quality = Counter()
        downloads_by_type = Counter()
        
        for event in download_starts:
            data = event.get("data", {})
            platform = data.get("platform", "unknown")
            quality = data.get("quality", "unknown")
            download_type = data.get("type", "unknown")
            
            downloads_by_platform[platform] += 1
            downloads_by_quality[quality] += 1
            downloads_by_type[download_type] += 1
        
        # Error events
        error_events = len([e for e in filtered_events if "error" in e["event_type"] or "failed" in e["event_type"]])
        
        # Consent statistics
        consent_stats = {
            "total_consents": len(analytics_storage["consent_data"]),
            "analytics_accepted": len([c for c in analytics_storage["consent_data"] if c["analytics"]]),
            "marketing_accepted": len([c for c in analytics_storage["consent_data"] if c["marketing"]]),
            "declined": len([c for c in analytics_storage["consent_data"] if not c["analytics"] and not c["marketing"]])
        }
        
        dashboard_data = AnalyticsDashboard(
            total_events=total_events,
            page_views=page_views,
            downloads_total=downloads_total,
            downloads_by_platform=dict(downloads_by_platform),
            downloads_by_quality=dict(downloads_by_quality),
            downloads_by_type=dict(downloads_by_type),
            error_events=error_events,
            consent_stats=consent_stats,
            time_range={
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": str(hours)
            }
        )
        
        logger.info(f"Generated analytics dashboard for {hours} hours: {total_events} events, {downloads_total} downloads")
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Failed to generate analytics dashboard: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "dashboard_generation_failed",
                "message": "Failed to generate analytics dashboard",
                "suggestion": "Please try again later"
            }
        )

@router.get("/events/{client_id}")
async def get_client_events(
    client_id: str,
    limit: int = 100,
    event_type: Optional[str] = None
):
    """
    Get events for a specific client (for debugging/support)
    """
    try:
        # Filter events by client ID
        client_events = [
            event for event in analytics_storage["events"]
            if event.get("client_id") == client_id
        ]
        
        # Filter by event type if specified
        if event_type:
            client_events = [
                event for event in client_events
                if event["event_type"] == event_type
            ]
        
        # Sort by timestamp (newest first) and limit
        client_events.sort(key=lambda x: x["timestamp"], reverse=True)
        client_events = client_events[:limit]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "client_id": client_id,
                "events": client_events,
                "total_events": len(client_events)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get client events: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "client_events_failed",
                "message": "Failed to retrieve client events",
                "suggestion": "Please check the client ID and try again"
            }
        )

@router.post("/ad-performance")
async def collect_ad_performance(
    performance_data: AdPerformanceData,
    request: Request
):
    """
    Collect ad performance metrics from the frontend
    """
    try:
        client_id = get_client_id(request)
        
        # Add client metadata to performance data
        performance_record = {
            "client_id": client_id,
            "session_id": performance_data.session_id,
            "performance": performance_data.performance,
            "timestamp": performance_data.timestamp,
            "ip_hash": hashlib.sha256(request.client.host.encode()).hexdigest()[:16],
            "user_agent": request.headers.get("user-agent", "")
        }
        
        # Store performance data
        analytics_storage["ad_performance"].append(performance_record)
        
        # Cache recent performance data
        cache_key = f"analytics:ad_performance:{client_id}"
        try:
            recent_performance = await cache_manager.get(cache_key) or []
            recent_performance.append(performance_record)
            # Keep only last 10 performance records per client
            if len(recent_performance) > 10:
                recent_performance = recent_performance[-10:]
            await cache_manager.set(cache_key, recent_performance, ttl=3600)  # 1 hour
        except Exception as cache_error:
            logger.warning(f"Failed to cache ad performance data: {cache_error}")
        
        # Limit total stored performance data to prevent memory issues
        if len(analytics_storage["ad_performance"]) > 1000:
            analytics_storage["ad_performance"] = analytics_storage["ad_performance"][-500:]
        
        logger.info(f"Stored ad performance data for client {client_id}: {performance_data.performance}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Ad performance data stored successfully",
                "client_id": client_id
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to store ad performance data: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ad_performance_storage_failed",
                "message": "Failed to store ad performance data",
                "suggestion": "Please try again later"
            }
        )

@router.get("/ad-performance/summary")
async def get_ad_performance_summary(
    hours: int = 24,
    request: Request = None
):
    """
    Get ad performance summary for the specified time range
    """
    try:
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        start_timestamp = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)
        
        # Filter performance data by time range
        filtered_performance = [
            record for record in analytics_storage["ad_performance"]
            if start_timestamp <= record["timestamp"] <= end_timestamp
        ]
        
        # Calculate aggregate metrics
        total_sessions = len(filtered_performance)
        total_impressions = sum(record["performance"].get("impressions", 0) for record in filtered_performance)
        total_clicks = sum(record["performance"].get("clicks", 0) for record in filtered_performance)
        total_revenue = sum(record["performance"].get("revenue_per_session", 0) for record in filtered_performance)
        
        # Calculate CTR
        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        
        # Revenue per session
        revenue_per_session = total_revenue / total_sessions if total_sessions > 0 else 0
        
        # Slot performance breakdown
        slot_performance = defaultdict(lambda: {"impressions": 0, "clicks": 0, "ctr": 0})
        
        for record in filtered_performance:
            slots = record["performance"].get("slots", {})
            for slot_id, slot_data in slots.items():
                slot_performance[slot_id]["impressions"] += slot_data.get("impressions", 0)
                slot_performance[slot_id]["clicks"] += slot_data.get("clicks", 0)
        
        # Calculate CTR for each slot
        for slot_id, data in slot_performance.items():
            if data["impressions"] > 0:
                data["ctr"] = (data["clicks"] / data["impressions"]) * 100
        
        summary = {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours
            },
            "overall_metrics": {
                "total_sessions": total_sessions,
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "overall_ctr": round(ctr, 2),
                "total_revenue": round(total_revenue, 2),
                "revenue_per_session": round(revenue_per_session, 2)
            },
            "slot_performance": dict(slot_performance)
        }
        
        logger.info(f"Generated ad performance summary for {hours} hours: {total_sessions} sessions, {total_impressions} impressions")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "summary": summary
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to generate ad performance summary: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ad_performance_summary_failed",
                "message": "Failed to generate ad performance summary",
                "suggestion": "Please try again later"
            }
        )

@router.delete("/data")
async def clear_analytics_data(
    confirm: bool = False,
    request: Request = None
):
    """
    Clear all analytics data (admin function)
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "confirmation_required",
                "message": "Please confirm data deletion by setting confirm=true",
                "suggestion": "Add ?confirm=true to the URL to confirm deletion"
            }
        )
    
    try:
        # Clear all analytics data
        events_count = len(analytics_storage["events"])
        consent_count = len(analytics_storage["consent_data"])
        
        analytics_storage["events"].clear()
        analytics_storage["consent_data"].clear()
        analytics_storage["session_metrics"].clear()
        analytics_storage["ad_performance"].clear()
        
        # Clear cache
        try:
            # Note: In a real implementation, you'd want to clear specific cache keys
            # This is a simplified version
            pass
        except Exception as cache_error:
            logger.warning(f"Failed to clear analytics cache: {cache_error}")
        
        logger.warning(f"Analytics data cleared: {events_count} events, {consent_count} consent records")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Analytics data cleared successfully",
                "cleared": {
                    "events": events_count,
                    "consent_records": consent_count
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to clear analytics data: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "data_clearing_failed",
                "message": "Failed to clear analytics data",
                "suggestion": "Please try again later"
            }
        )

@router.get("/health")
async def analytics_health_check():
    """
    Health check for analytics system
    """
    try:
        # Check data storage
        events_count = len(analytics_storage["events"])
        consent_count = len(analytics_storage["consent_data"])
        ad_performance_count = len(analytics_storage["ad_performance"])
        
        # Check cache connectivity
        cache_healthy = True
        try:
            await cache_manager.set("analytics:health_check", "ok", ttl=60)
            cache_result = await cache_manager.get("analytics:health_check")
            cache_healthy = cache_result == "ok"
        except Exception:
            cache_healthy = False
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status": "healthy",
                "storage": {
                    "events_count": events_count,
                    "consent_count": consent_count,
                    "ad_performance_count": ad_performance_count,
                    "cache_healthy": cache_healthy
                },
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Analytics health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# Import hashlib at the top of the file
import hashlib