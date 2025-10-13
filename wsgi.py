"""
WSGI adapter for VidNet FastAPI application
This allows waitress to serve the FastAPI app
"""
from app.main import app

# For waitress-serve compatibility
application = app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)