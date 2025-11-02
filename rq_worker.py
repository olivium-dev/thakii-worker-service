#!/usr/bin/env python3
"""
Redis Queue Worker for Video Processing
Uses existing EnhancedWorker with RQ job management
"""

import os
import sys
import tempfile
import shutil
from redis import Redis
from rq import Worker, Queue, Connection
from dotenv import load_dotenv

# Fix for macOS fork() issue with objc
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

load_dotenv()

# Import existing worker
from worker import EnhancedWorker

def process_video_job(video_id: str, s3_key: str, filename: str, local_file_path: str = None):
    """
    RQ job function - uses existing EnhancedWorker
    Supports both S3 and local file processing
    """
    print(f"🎬 RQ Worker processing: {video_id}")
    worker = EnhancedWorker()
    
    # Check if we have a local file path
    if local_file_path and os.path.exists(local_file_path):
        print(f"📁 Using local file: {local_file_path}")
        # Process the local file directly
        try:
            # Copy the file to a temporary directory
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, filename)
            shutil.copy(local_file_path, temp_path)
            
            # Process the file
            from src.main import CommandLineArgRunner
            runner = CommandLineArgRunner()
            output_pdf = os.path.join(temp_dir, f"{video_id}.pdf")
            runner.run([temp_path, "-o", output_pdf])
            
            # Update the task status
            worker.postgres.update_task_status(
                video_id, 
                "completed", 
                pdf_url=f"local://{output_pdf}",
                progress_percentage=100.0
            )
            
            print(f"✅ Local file processing completed for {video_id}")
            return {"video_id": video_id, "status": "completed", "pdf_path": output_pdf}
        except Exception as e:
            print(f"❌ Local file processing failed: {e}")
            worker.postgres.update_task_status(video_id, "failed", error_message=str(e))
            raise Exception(f"Local file processing failed: {str(e)}")
    
    # Fall back to S3 processing
    try:
        # Check if we're in a test environment (test AWS credentials)
        is_test_env = os.getenv('AWS_ACCESS_KEY_ID') == 'test' and os.getenv('AWS_SECRET_ACCESS_KEY') == 'test'
        
        # In test environment, we should be more lenient with S3 availability
        if not worker.s3.is_available() and not is_test_env:
            error_msg = "S3 is not available. Cannot download video."
            print(f"❌ {error_msg}")
            worker.postgres.update_task_status(video_id, "failed", error_message=error_msg)
            raise Exception(error_msg)
        
        # Process the video - in test environment, this will likely fail at download
        # but we'll let the worker handle it with proper error messages
        success = worker.process_video(
            video_id=video_id,
            s3_key=s3_key,
            filename=filename
        )
        
        if not success:
            raise Exception(f"Video processing failed: {video_id}")
        
        return {"video_id": video_id, "status": "completed"}
    except Exception as e:
        print(f"❌ S3 processing failed: {e}")
        # Update task status if it hasn't been updated already
        try:
            worker.postgres.update_task_status(video_id, "failed", error_message=str(e))
        except:
            pass
        raise

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

