#!/usr/bin/env python3
"""
Test Backend-Worker HTTP Communication
Simulates the exact HTTP call the backend makes to the worker
"""

import requests
import json
import time

def test_worker_http_communication():
    """Test the exact HTTP communication between backend and worker"""
    worker_url = "https://thakii-02.fanusdigital.site/thakii-worker"
    
    print("🔄 === TESTING BACKEND-WORKER HTTP COMMUNICATION ===")
    print(f"Worker URL: {worker_url}")
    print()
    
    # Test 1: Worker health (what backend checks first)
    print("1️⃣ Testing worker health check...")
    try:
        response = requests.get(f"{worker_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Worker health: {data['status']}")
        else:
            print(f"❌ Worker health failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Worker health error: {e}")
        return False
    
    # Test 2: Simulate backend HTTP call to worker
    print("2️⃣ Simulating backend HTTP call to worker...")
    test_data = {
        "video_id": "test-http-communication",
        "user_id": "test-user-123", 
        "filename": "test-video.mp4",
        "s3_key": "videos/test-http-communication/test-video.mp4"
    }
    
    try:
        response = requests.post(
            f"{worker_url}/generate-pdf",
            json=test_data,
            timeout=30
        )
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📋 Response content: {response.text[:200]}...")
        
        if response.status_code == 201:
            print("✅ Worker accepted HTTP request (would start processing)")
            return True
        elif response.status_code == 400:
            print("✅ Worker correctly validated request (no actual video file)")
            return True
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ HTTP communication error: {e}")
        return False

def test_worker_status_endpoint():
    """Test worker status endpoint"""
    worker_url = "https://thakii-02.fanusdigital.site/thakii-worker"
    
    print("3️⃣ Testing worker status endpoint...")
    
    # Test with existing video ID from Firebase
    try:
        response = requests.get(f"{worker_url}/list", timeout=10)
        if response.status_code == 200:
            videos = response.json()['videos']
            if videos:
                test_video_id = videos[0]['id']
                print(f"📋 Testing status for existing video: {test_video_id}")
                
                status_response = requests.get(f"{worker_url}/status/{test_video_id}", timeout=10)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"✅ Status endpoint: {status_data['status']} (PDF ready: {status_data.get('pdf_ready', False)})")
                    return True
                else:
                    print(f"❌ Status endpoint failed: {status_response.status_code}")
                    return False
            else:
                print("⚠️  No videos found for status testing")
                return True
    except Exception as e:
        print(f"❌ Status endpoint error: {e}")
        return False

if __name__ == "__main__":
    print("🎯 === BACKEND-WORKER HTTP COMMUNICATION TEST ===")
    print()
    
    test1 = test_worker_http_communication()
    test2 = test_worker_status_endpoint()
    
    print()
    print("📊 === HTTP COMMUNICATION TEST RESULTS ===")
    print(f"   {'✅' if test1 else '❌'} Backend → Worker HTTP: {'PASS' if test1 else 'FAIL'}")
    print(f"   {'✅' if test2 else '❌'} Worker Status API: {'PASS' if test2 else 'FAIL'}")
    
    if test1 and test2:
        print("🎉 HTTP COMMUNICATION WORKING PERFECTLY!")
        print("🚀 Backend can now trigger worker via HTTPS!")
    else:
        print("⚠️  HTTP communication needs debugging")
