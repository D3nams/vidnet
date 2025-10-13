#!/usr/bin/env python3
"""
Test script to verify API endpoints are working
"""
import requests
import json

def test_api():
    base_url = "http://localhost:8001"
    
    print("🧪 Testing VidNet API endpoints...")
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✅ Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test metadata endpoint
    try:
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
        response = requests.post(
            f"{base_url}/api/v1/metadata",
            json={"url": test_url},
            timeout=30
        )
        print(f"✅ Metadata endpoint: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Title: {data.get('title', 'N/A')}")
            print(f"   Platform: {data.get('platform', 'N/A')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Metadata endpoint failed: {e}")
    
    # Test download endpoint
    try:
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        response = requests.post(
            f"{base_url}/api/v1/download",
            json={"url": test_url, "quality": "720p", "format": "mp4"},
            timeout=10
        )
        print(f"✅ Download endpoint: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Task ID: {data.get('task_id', 'N/A')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Download endpoint failed: {e}")

if __name__ == "__main__":
    test_api()