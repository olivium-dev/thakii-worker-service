#!/usr/bin/env python3
"""
Test Backend Upload with large01.mp4
Tests the complete flow: Backend API → Worker Service → Enhanced PDF Generation
"""

import requests
import json
import time
import os
from pathlib import Path

# Configuration
BACKEND_URL = "https://vps-71.fds-1.com/thakii-be"
WORKER_URL = "https://thakii-02.fanusdigital.site/thakii-worker"
VIDEO_FILE = "large01.mp4"

def get_auth_token():
    """Get authentication token from backend"""
    try:
        print("🔐 Getting authentication token...")
        
        # Use mock user token endpoint
        response = requests.post(f"{BACKEND_URL}/auth/mock-user-token", json={
            "email": "test@example.com",
            "name": "Test User"
        })
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('custom_token')
            print(f"✅ Auth token obtained: {token[:20]}...")
            return token
        else:
            print(f"❌ Auth failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Auth error: {e}")
        return None

def upload_video_chunked(token: str, video_path: str):
    """Upload video using chunked upload (for large files)"""
    try:
        video_file = Path(video_path)
        if not video_file.exists():
            print(f"❌ Video file not found: {video_path}")
            return None
            
        file_size = video_file.stat().st_size
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        file_id = f"test-{int(time.time())}"
        
        print(f"📤 Uploading {video_file.name} ({file_size:,} bytes) in {total_chunks} chunks...")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Upload chunks
        with open(video_file, 'rb') as f:
            for chunk_index in range(total_chunks):
                chunk_data = f.read(chunk_size)
                
                files = {
                    'chunk': (f'chunk_{chunk_index}', chunk_data, 'application/octet-stream')
                }
                data = {
                    'chunk_index': chunk_index,
                    'total_chunks': total_chunks,
                    'file_id': file_id,
                    'original_filename': video_file.name
                }
                
                print(f"   Uploading chunk {chunk_index + 1}/{total_chunks}...")
                
                response = requests.post(
                    f"{BACKEND_URL}/upload-chunk",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=60
                )
                
                if response.status_code != 200:
                    print(f"❌ Chunk upload failed: {response.status_code} - {response.text}")
                    return None
        
        # Assemble file
        print("🔧 Assembling chunks...")
        response = requests.post(
            f"{BACKEND_URL}/assemble-file",
            json={
                'file_id': file_id,
                'total_chunks': total_chunks,
                'original_filename': video_file.name
            },
            headers=headers,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            video_id = data.get('video_id')
            print(f"✅ Video uploaded and processing started: {video_id}")
            return video_id
        else:
            print(f"❌ Assembly failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return None

def monitor_processing(token: str, video_id: str):
    """Monitor video processing status"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        print(f"🔄 Monitoring processing for video: {video_id}")
        
        for attempt in range(60):  # Monitor for up to 10 minutes
            response = requests.get(
                f"{BACKEND_URL}/status/{video_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                
                print(f"   Status: {status}")
                
                if status == 'completed':
                    print(f"✅ Processing completed!")
                    return True
                elif status == 'failed':
                    error = data.get('error_message', 'Unknown error')
                    print(f"❌ Processing failed: {error}")
                    return False
                elif status in ['processing', 'in_queue']:
                    print(f"⏳ Still processing... (attempt {attempt + 1}/60)")
                    time.sleep(10)
                else:
                    print(f"❓ Unknown status: {status}")
                    time.sleep(10)
            else:
                print(f"❌ Status check failed: {response.status_code}")
                time.sleep(10)
        
        print("⏱️ Timeout waiting for processing to complete")
        return False
        
    except Exception as e:
        print(f"❌ Monitoring error: {e}")
        return False

def download_pdf(token: str, video_id: str):
    """Download the generated PDF"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        print(f"📥 Downloading PDF for video: {video_id}")
        
        response = requests.get(
            f"{BACKEND_URL}/download/{video_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            download_url = data.get('download_url')
            
            if download_url:
                # Download the actual PDF
                pdf_response = requests.get(download_url, timeout=60)
                if pdf_response.status_code == 200:
                    output_file = f"backend_test_{video_id}.pdf"
                    with open(output_file, 'wb') as f:
                        f.write(pdf_response.content)
                    
                    print(f"✅ PDF downloaded: {output_file} ({len(pdf_response.content):,} bytes)")
                    return output_file
                else:
                    print(f"❌ PDF download failed: {pdf_response.status_code}")
            else:
                print(f"❌ No download URL in response: {data}")
        else:
            print(f"❌ Download request failed: {response.status_code} - {response.text}")
            
        return None
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        return None

def test_backend_worker_flow():
    """Test the complete backend → worker → enhanced PDF flow"""
    print("🎯 === TESTING BACKEND → WORKER → ENHANCED PDF FLOW ===")
    print(f"📁 Video file: {VIDEO_FILE}")
    print(f"🌐 Backend URL: {BACKEND_URL}")
    print(f"⚙️ Worker URL: {WORKER_URL}")
    print()
    
    # Step 1: Get auth token
    token = get_auth_token()
    if not token:
        print("❌ Failed to get auth token")
        return False
    
    # Step 2: Upload video
    video_id = upload_video_chunked(token, VIDEO_FILE)
    if not video_id:
        print("❌ Failed to upload video")
        return False
    
    # Step 3: Monitor processing
    success = monitor_processing(token, video_id)
    if not success:
        print("❌ Processing failed or timed out")
        return False
    
    # Step 4: Download PDF
    pdf_file = download_pdf(token, video_id)
    if not pdf_file:
        print("❌ Failed to download PDF")
        return False
    
    print()
    print("🎉 === BACKEND UPLOAD TEST SUCCESSFUL! ===")
    print(f"✅ Video uploaded: {video_id}")
    print(f"✅ PDF generated: {pdf_file}")
    print("🚀 Enhanced worker processing is now working via backend!")
    
    return True

if __name__ == "__main__":
    success = test_backend_worker_flow()
    exit(0 if success else 1)
