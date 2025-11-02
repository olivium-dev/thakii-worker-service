#!/usr/bin/env python3
"""
Test script to process a local video file using the RQ worker
"""

import os
import sys
import uuid
import time
import redis
from rq import Queue
from dotenv import load_dotenv

# Fix for macOS fork() issue with objc
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

load_dotenv()

def main():
    """Process a local test video file"""
    # Check for test video file
    test_video = "tests/videos/input_1.mp4"
    if not os.path.exists(test_video):
        print(f"❌ Test video not found: {test_video}")
        return False
    
    # Generate a unique video ID
    video_id = f"test-{uuid.uuid4().hex[:8]}"
    filename = f"{video_id}.mp4"
    
    print(f"🎬 Processing local test video: {test_video}")
    print(f"🆔 Video ID: {video_id}")
    
    # Connect to Redis
    try:
        redis_conn = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0
        )
        redis_conn.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    
    # Create queue and enqueue job
    queue = Queue('video_processing', connection=redis_conn)
    job = queue.enqueue(
        'rq_worker.process_video_job',
        video_id=video_id,
        s3_key=f"test/{filename}",  # Dummy S3 key
        filename=filename,
        local_file_path=os.path.abspath(test_video),  # Pass the local file path
        job_timeout=1800,
        result_ttl=86400
    )
    
    print(f"✅ Job enqueued: {job.id}")
    print("⏳ Waiting for job to complete...")
    
    # Wait for job to complete
    max_wait = 60  # seconds
    start_time = time.time()
    while job.result is None and time.time() - start_time < max_wait:
        job.refresh()
        if job.is_failed:
            print(f"❌ Job failed: {job.exc_info}")
            return False
        time.sleep(1)
    
    if job.result:
        print(f"✅ Job completed: {job.result}")
        return True
    else:
        print("⚠️ Job timed out (still processing)")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
