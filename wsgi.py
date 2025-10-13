"""
WSGI adapter for VidNet FastAPI application
This allows waitress to serve the FastAPI app
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.main import app
    # For waitress-serve compatibility
    application = app
    print("✅ Successfully imported FastAPI app")
except ImportError as e:
    print(f"❌ Import error: {e}")
    # Fallback: create a simple app
    from fastapi import FastAPI
    application = FastAPI()
    
    @application.get("/")
    def read_root():
        return {"error": "Import failed", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(application, host="0.0.0.0", port=8000)