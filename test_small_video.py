#!/usr/bin/env python3
"""
Test Direct Worker Upload with test_video_small.mp4
Tests the enhanced worker processing directly
"""

import requests
import json
import time
import os
from pathlib import Path

# Configuration
WORKER_URL = "https://thakii-02.fanusdigital.site/thakii-worker"
VIDEO_FILE = "test_video_small.mp4"

def test_direct_worker_upload():
    """Test uploading directly to worker service"""
    print("🎯 === TESTING DIRECT WORKER UPLOAD ===")
    print(f"📁 Video file: {VIDEO_FILE}")
    print(f"⚙️ Worker URL: {WORKER_URL}")
    print()
    
    # Check if video file exists
    video_path = Path(VIDEO_FILE)
    if not video_path.exists():
        print(f"❌ Video file not found: {VIDEO_FILE}")
        return False
    
    file_size = video_path.stat().st_size
    print(f"📊 File size: {file_size:,} bytes ({file_size / (1024*1024):.1f} MB)")
    
    # Step 1: Test worker health
    print("1️⃣ Testing worker health...")
    try:
        response = requests.get(f"{WORKER_URL}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Worker health: {health_data['status']}")
        else:
            print(f"❌ Worker health failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Worker health error: {e}")
        return False
    
    # Step 2: Upload video to worker
    print("2️⃣ Uploading video to worker...")
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (video_path.name, f, 'video/mp4')}
            
            response = requests.post(
                f"{WORKER_URL}/upload",
                files=files,
                timeout=300  # 5 minutes for upload
            )
        
        if response.status_code == 201:
            data = response.json()
            video_id = data.get('video_id')
            print(f"✅ Video uploaded: {video_id}")
        else:
            print(f"❌ Upload failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False
    
    # Step 3: Trigger processing
    print("3️⃣ Triggering enhanced processing...")
    try:
        response = requests.post(
            f"{WORKER_URL}/process/{video_id}",
            timeout=30
        )
        
        if response.status_code == 200:
            process_data = response.json()
            print(f"✅ Processing started: {process_data['status']}")
        else:
            print(f"❌ Processing trigger failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Processing trigger error: {e}")
        return False
    
    # Step 4: Monitor processing
    print("4️⃣ Monitoring enhanced processing...")
    for attempt in range(60):  # Monitor for 10 minutes
        try:
            response = requests.get(f"{WORKER_URL}/status/{video_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                
                print(f"   Status: {status} (attempt {attempt + 1}/60)")
                
                if status == 'completed':
                    print("✅ Enhanced processing completed!")
                    break
                elif status == 'failed':
                    error = data.get('error_message', 'Unknown error')
                    print(f"❌ Processing failed: {error}")
                    return False
                elif status in ['processing', 'in_queue']:
                    time.sleep(10)
                else:
                    print(f"❓ Unknown status: {status}")
                    time.sleep(10)
            else:
                print(f"❌ Status check failed: {response.status_code}")
                time.sleep(10)
                
        except Exception as e:
            print(f"❌ Status check error: {e}")
            time.sleep(10)
    else:
        print("⏱️ Timeout waiting for processing")
        return False
    
    # Step 5: Download enhanced PDF
    print("5️⃣ Downloading enhanced PDF...")
    try:
        response = requests.get(f"{WORKER_URL}/download/{video_id}.pdf", timeout=60)
        
        if response.status_code == 200:
            output_file = f"enhanced_worker_test_{video_id}.pdf"
            with open(output_file, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Enhanced PDF downloaded: {output_file} ({len(response.content):,} bytes)")
            
            # Quick validation - check if it's a real PDF
            if response.content.startswith(b'%PDF'):
                print("✅ Valid PDF format confirmed")
                return output_file
            else:
                print("❌ Invalid PDF format")
                return False
        else:
            print(f"❌ PDF download failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

if __name__ == "__main__":
    result = test_direct_worker_upload()
    
    if result:
        print()
        print("🎉 === DIRECT WORKER TEST SUCCESSFUL! ===")
        print(f"✅ Enhanced PDF generated: {result}")
        print("🚀 Enhanced worker processing is working!")
        
        # Quick analysis of the PDF
        try:
            import PyPDF2
            with open(result, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                num_pages = len(pdf_reader.pages)
                
                print(f"📄 PDF Analysis: {num_pages} pages")
                
                # Check first page text
                if num_pages > 0:
                    first_page_text = pdf_reader.pages[0].extract_text()
                    if len(first_page_text) > 50:
                        print(f"📝 First page preview: {first_page_text[:100]}...")
                    else:
                        print(f"📝 First page text: {first_page_text}")
                        
        except Exception as e:
            print(f"📄 PDF analysis error: {e}")
        
        exit(0)
    else:
        print()
        print("❌ === DIRECT WORKER TEST FAILED ===")
        exit(1)
