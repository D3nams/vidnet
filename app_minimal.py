#!/usr/bin/env python3
"""
Minimal VidNet Application for Local Testing
Runs without Redis and complex services for basic functionality testing
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import logging
import asyncio
import uuid
import time
from typing import List, Optional, Dict, Any
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data models
class VideoQuality(BaseModel):
    quality: str
    format: str
    filesize: Optional[int] = None
    fps: Optional[int] = None

class VideoMetadata(BaseModel):
    title: str
    thumbnail: str
    duration: int
    platform: str
    available_qualities: List[VideoQuality]
    audio_available: bool
    original_url: str

class DownloadRequest(BaseModel):
    url: str
    quality: str
    format: str = "mp4"

class AudioRequest(BaseModel):
    url: str
    quality: str = "128kbps"

class DownloadResponse(BaseModel):
    task_id: str
    status: str
    download_url: Optional[str] = None
    error_message: Optional[str] = None

# Create FastAPI app
app = FastAPI(
    title="VidNet API (Minimal)",
    description="Minimal VidNet API for local testing",
    version="1.0.0-minimal"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo
tasks_storage: Dict[str, Dict[str, Any]] = {}

# Mock video processor
class MockVideoProcessor:
    def detect_platform(self, url: str) -> str:
        """Detect platform from URL"""
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        elif "tiktok.com" in url:
            return "tiktok"
        elif "instagram.com" in url:
            return "instagram"
        elif "facebook.com" in url:
            return "facebook"
        elif "twitter.com" in url or "x.com" in url:
            return "twitter"
        elif "reddit.com" in url:
            return "reddit"
        elif "vimeo.com" in url:
            return "vimeo"
        else:
            return "unknown"
    
    def extract_metadata(self, url: str) -> VideoMetadata:
        """Extract mock metadata"""
        platform = self.detect_platform(url)
        
        if platform == "unknown":
            raise HTTPException(status_code=400, detail="Unsupported platform")
        
        # Mock metadata based on platform
        mock_data = {
            "youtube": {
                "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
                "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
                "duration": 212
            },
            "tiktok": {
                "title": "Funny TikTok Video",
                "thumbnail": "https://via.placeholder.com/480x640/ff0050/ffffff?text=TikTok",
                "duration": 15
            },
            "instagram": {
                "title": "Instagram Reel",
                "thumbnail": "https://via.placeholder.com/480x480/e4405f/ffffff?text=Instagram",
                "duration": 30
            }
        }
        
        data = mock_data.get(platform, mock_data["youtube"])
        
        return VideoMetadata(
            title=data["title"],
            thumbnail=data["thumbnail"],
            duration=data["duration"],
            platform=platform,
            available_qualities=[
                VideoQuality(quality="720p", format="mp4", filesize=50000000),
                VideoQuality(quality="1080p", format="mp4", filesize=100000000),
                VideoQuality(quality="480p", format="mp4", filesize=25000000)
            ],
            audio_available=True,
            original_url=url
        )

# Initialize mock processor
video_processor = MockVideoProcessor()

# Routes
@app.get("/")
async def root():
    """Serve the main application page"""
    return FileResponse("static/index.html")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "mode": "minimal"}

@app.post("/api/v1/metadata")
async def get_metadata(request: dict):
    """Get video metadata"""
    try:
        url = request.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        logger.info(f"Extracting metadata for: {url}")
        
        # Simulate processing delay
        await asyncio.sleep(1)
        
        metadata = video_processor.extract_metadata(url)
        
        logger.info(f"Metadata extracted for: {metadata.title}")
        return metadata
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/download")
async def download_video(request: DownloadRequest):
    """Initiate video download"""
    try:
        task_id = str(uuid.uuid4())
        
        # Store task
        tasks_storage[task_id] = {
            "status": "pending",
            "url": request.url,
            "quality": request.quality,
            "format": request.format,
            "type": "video",
            "created_at": time.time()
        }
        
        logger.info(f"Download initiated: {task_id}")
        
        # Start background processing
        asyncio.create_task(process_download(task_id))
        
        return DownloadResponse(task_id=task_id, status="pending")
        
    except Exception as e:
        logger.error(f"Download initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/extract-audio")
async def extract_audio(request: AudioRequest):
    """Initiate audio extraction"""
    try:
        task_id = str(uuid.uuid4())
        
        # Store task
        tasks_storage[task_id] = {
            "status": "pending",
            "url": request.url,
            "quality": request.quality,
            "format": "mp3",
            "type": "audio",
            "created_at": time.time()
        }
        
        logger.info(f"Audio extraction initiated: {task_id}")
        
        # Start background processing
        asyncio.create_task(process_download(task_id))
        
        return DownloadResponse(task_id=task_id, status="pending")
        
    except Exception as e:
        logger.error(f"Audio extraction initiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/status/{task_id}")
async def get_status(task_id: str):
    """Get download status"""
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks_storage[task_id]
    
    response = DownloadResponse(
        task_id=task_id,
        status=task["status"],
        download_url=task.get("download_url"),
        error_message=task.get("error_message")
    )
    
    return response

@app.get("/api/v1/monitoring/status")
async def monitoring_status():
    """System status endpoint"""
    return {
        "status": "healthy",
        "mode": "minimal",
        "redis": {"status": "disabled", "message": "Running in minimal mode"},
        "performance": {"status": "basic", "message": "Basic monitoring only"},
        "tasks": {"active": len([t for t in tasks_storage.values() if t["status"] in ["pending", "processing"]]),
                 "total": len(tasks_storage)}
    }

@app.get("/api/v1/monitoring/metrics")
async def get_metrics():
    """Basic metrics endpoint"""
    return {
        "requests": {"total": len(tasks_storage)},
        "response_times": {"average": 1.5},
        "errors": {"count": 0},
        "cache": {"status": "disabled"}
    }

@app.post("/api/v1/analytics/events")
async def track_events(request: dict):
    """Analytics events endpoint (mock)"""
    logger.info(f"Analytics event tracked: {request}")
    return {"status": "tracked"}

@app.post("/api/v1/analytics/consent")
async def track_consent(request: dict):
    """Consent tracking endpoint (mock)"""
    logger.info(f"Consent tracked: {request}")
    return {"status": "recorded"}

# Background task processing
async def process_download(task_id: str):
    """Simulate download processing"""
    try:
        task = tasks_storage[task_id]
        
        # Update to processing
        task["status"] = "processing"
        await asyncio.sleep(2)
        
        # Simulate conversion for audio
        if task["type"] == "audio":
            task["status"] = "converting"
            await asyncio.sleep(3)
        
        # Complete
        task["status"] = "completed"
        task["download_url"] = f"/downloads/mock_{task_id}.{task['format']}"
        
        logger.info(f"Task completed: {task_id}")
        
    except Exception as e:
        logger.error(f"Task processing failed: {task_id} - {e}")
        task["status"] = "failed"
        task["error_message"] = str(e)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Static files mounted")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# Add test integration page route
@app.get("/test_frontend_integration.html")
async def test_page():
    """Serve the test integration page"""
    try:
        return FileResponse("test_frontend_integration.html")
    except Exception:
        return JSONResponse(
            content={"message": "Test page not found. Create test_frontend_integration.html in the root directory."},
            status_code=404
        )

if __name__ == "__main__":
    import uvicorn
    print("🎬 Starting VidNet Minimal Server")
    print("=" * 40)
    print("📱 App: http://127.0.0.1:8000")
    print("📚 Docs: http://127.0.0.1:8000/docs")
    print("🧪 Test: http://127.0.0.1:8000/test_frontend_integration.html")
    print("=" * 40)
    
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")