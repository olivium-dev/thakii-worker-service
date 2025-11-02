#!/usr/bin/env python3
"""
Redis Queue Worker for Video Processing
Uses existing EnhancedWorker with RQ job management
"""

import os
import sys
from redis import Redis
from rq import Worker, Queue, Connection
from dotenv import load_dotenv

load_dotenv()

# Import existing worker
from worker import EnhancedWorker

def process_video_job(video_id: str, s3_key: str, filename: str):
    """
    RQ job function - uses existing EnhancedWorker
    No modifications to worker.py needed
    """
    print(f"🎬 RQ Worker processing: {video_id}")
    worker = EnhancedWorker()
    success = worker.process_video(
        video_id=video_id,
        s3_key=s3_key,
        filename=filename
    )
    
    if not success:
        raise Exception(f"Video processing failed: {video_id}")
    
    return {"video_id": video_id, "status": "completed"}

if __name__ == '__main__':
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    
    try:
        redis_conn = Redis(host=redis_host, port=redis_port)
        redis_conn.ping()
        print(f"✅ Connected to Redis at {redis_host}:{redis_port}")
    except Exception as e:
        print(f"❌ Redis not available: {e}")
        print("⚠️  RQ worker cannot start without Redis")
        sys.exit(1)
    
    with Connection(redis_conn):
        worker = Worker(['video_processing'])
        print("🚀 RQ Worker started - listening for jobs")
        worker.work()

