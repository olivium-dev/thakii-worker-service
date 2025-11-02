#!/usr/bin/env python3
"""
Redis Queue Manager for Video Processing
Provides fail-fast queue management with feature flag control
"""

import os
from typing import Optional, Dict, Any
from redis import Redis
from rq import Queue
from dotenv import load_dotenv

load_dotenv()

class QueueManager:
    def __init__(self):
        self.enabled = os.getenv('ENABLE_REDIS_QUEUE', 'false').lower() == 'true'
        self.redis_conn = None
        self.queue = None
        
        if self.enabled:
            self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection - fail fast if enabled but unavailable"""
        try:
            self.redis_conn = Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=0,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_conn.ping()
            self.queue = Queue('video_processing', connection=self.redis_conn)
            print(f"✅ Redis Queue initialized at {os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}")
        except Exception as e:
            print(f"❌ Redis connection failed (ENABLE_REDIS_QUEUE=true): {e}")
            raise  # Fail fast - no silent fallback
    
    def enqueue_video(self, video_id: str, s3_key: str, filename: str, user_id: str) -> Optional[str]:
        """Enqueue video for processing"""
        if not self.enabled:
            print(f"⏭️  Redis disabled - task {video_id} will be processed via database polling")
            return None
        
        try:
            job = self.queue.enqueue(
                'rq_worker.process_video_job',
                video_id=video_id,
                s3_key=s3_key,
                filename=filename,
                job_timeout=1800,
                result_ttl=86400
            )
            print(f"✅ Video {video_id} enqueued to Redis: {job.id}")
            return job.id
        except Exception as e:
            print(f"❌ Failed to enqueue {video_id}: {e}")
            raise  # Fail fast
    
    def is_available(self) -> bool:
        """Check if Redis queue is enabled and available"""
        if not self.enabled:
            return False
        try:
            return self.redis_conn.ping() if self.redis_conn else False
        except:
            return False

# Global instance
queue_manager = QueueManager()

