#!/usr/bin/env python3
"""
API-based Worker for Mac Mini M2 - High Performance Video Processing
- Uses API client instead of direct PostgreSQL access
- Limits to 4 concurrent tasks
- Robust error handling and heartbeat
"""

import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path
import shutil
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import signal
import threading

# Import core integrations
from core.postgres_integration import postgres_client  # Fallback if API disabled
from core.s3_integration import s3_client
from core.api_task_client import api_client

class EnhancedWorkerAPI:
    def __init__(self):
        self.postgres = postgres_client  # Fallback if API disabled
        self.s3 = s3_client
        self.api = api_client
        
        # Fixed at 4 concurrent tasks as per requirements
        self.max_concurrent_tasks = 4
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_tasks)
        
        # Configure intelligent storage selection
        self.temp_base_dir = self._get_temp_storage_path()
        
        # Task processing timeout (30 minutes)
        self.task_timeout = 1800
        
        # Active tasks tracking
        self.active_tasks = {}
        self.active_tasks_lock = threading.Lock()
        
        # Start heartbeat thread
        self.heartbeat_thread = None
        if self.api.is_enabled:
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
        
        print("🚀 API-based Worker (4 concurrent tasks)", flush=True)
        print(f"   API Client: {'✅' if self.api.is_enabled else '❌'}", flush=True)
        print(f"   PostgreSQL: {'✅' if self.postgres.is_available() else '❌'}", flush=True)
        print(f"   S3: {'✅' if self.s3.is_available() else '❌'}", flush=True)
        print(f"   Temp Storage: {self.temp_base_dir}", flush=True)
        print(f"   Max Concurrent Tasks: {self.max_concurrent_tasks}", flush=True)
        print(f"   CPU Cores: {multiprocessing.cpu_count()}", flush=True)
        sys.stdout.flush()
    
    def _get_temp_storage_path(self):
        """
        Intelligently select storage path with automatic fallback
        """
        # Try user-specified path first
        custom_path = os.getenv('TEMP_STORAGE_PATH')
        if custom_path:
            path = Path(custom_path)
            if path.exists() and os.access(path, os.W_OK):
                return path
        
        # Try standard temp directory
        return Path(tempfile.gettempdir()) / "thakii_worker"
    
    def _heartbeat_loop(self):
        """
        Send heartbeat to backend every 60 seconds
        """
        while True:
            try:
                with self.active_tasks_lock:
                    active_video_ids = list(self.active_tasks.keys())
                
                if active_video_ids:
                    self.api.send_heartbeat()
            except Exception as e:
                print(f"❌ Heartbeat error: {e}", flush=True)
            
            time.sleep(60)  # Send heartbeat every minute
    
    def process_video(self, video_id=None, task=None):
        """
        Process a video task
        Can be called with either video_id or task object
        """
        # Get task details if only video_id provided
        if video_id and not task:
            if self.api.is_enabled:
                task = self.api.get_task_details(video_id)
            else:
                task = self.postgres.get_task_details(video_id)
            
            if not task:
                print(f"❌ Task {video_id} not found", flush=True)
                return False
        
        # Extract task details
        video_id = task['video_id']
        s3_key = task.get('s3_key')
        filename = task.get('filename', 'unknown.mp4')
        
        print(f"🎬 Processing video: {video_id}", flush=True)
        print(f"   Filename: {filename}", flush=True)
        print(f"   S3 Key: {s3_key}", flush=True)
        
        # Track this task
        with self.active_tasks_lock:
            self.active_tasks[video_id] = time.time()
        
        # Update status to processing
        if self.api.is_enabled:
            self.api.update_task_status(video_id, 'processing', progress=0)
        else:
            self.postgres.update_task_status(video_id, 'processing')
        
        try:
            # Create temp directory for this task
            task_dir = self.temp_base_dir / video_id
            task_dir.mkdir(parents=True, exist_ok=True)
            
            # Download video from S3
            video_path = task_dir / f"{video_id}.mp4"
            print(f"📥 Downloading video from S3: {s3_key}", flush=True)
            
            if not self.s3.download_video(video_id, str(video_path), s3_key):
                raise Exception(f"Failed to download video from S3: {s3_key}")
            
            # Generate PDF
            pdf_path = task_dir / f"{video_id}.pdf"
            print(f"📄 Generating PDF...", flush=True)
            
            if not self._generate_superior_pdf(video_path, pdf_path):
                raise Exception("Failed to generate PDF")
            
            # Upload PDF to S3
            pdf_s3_key = f"pdfs/{video_id}/{Path(filename).stem}.pdf"
            print(f"📤 Uploading PDF to S3: {pdf_s3_key}", flush=True)
            
            pdf_url = self.s3.upload_file(pdf_path, pdf_s3_key)
            if not pdf_url:
                raise Exception("Failed to upload PDF to S3")
            
            # Update task status to completed
            print(f"✅ Processing completed for {video_id}", flush=True)
            
            if self.api.is_enabled:
                self.api.update_task_status(video_id, 'completed', pdf_url=pdf_url, progress=100)
            else:
                self.postgres.update_task_status(video_id, 'completed', pdf_url=pdf_url)
            
            # Clean up temp files
            shutil.rmtree(task_dir, ignore_errors=True)
            
            # Remove from active tasks
            with self.active_tasks_lock:
                self.active_tasks.pop(video_id, None)
            
            return True
            
        except Exception as e:
            print(f"❌ Processing error for {video_id}: {e}", flush=True)
            
            # Update task status to failed
            if self.api.is_enabled:
                self.api.update_task_status(video_id, 'failed', error_message=str(e))
            else:
                self.postgres.update_task_status(video_id, 'failed', error_message=str(e))
            
            # Remove from active tasks
            with self.active_tasks_lock:
                self.active_tasks.pop(video_id, None)
            
            return False
    
    def _generate_superior_pdf(self, video_path: Path, pdf_path: Path) -> bool:
        """
        Generate PDF from video using superior method
        This is a placeholder for the actual PDF generation code
        """
        try:
            # Simulate PDF generation
            time.sleep(5)
            
            # Create a dummy PDF file
            with open(pdf_path, 'w') as f:
                f.write("This is a dummy PDF file")
            
            return True
        except Exception as e:
            print(f"❌ PDF error: {e}")
            return False
    
    def run_polling_loop(self):
        """API-based polling loop with 4 concurrent task limit"""
        print("🔄 Starting API-based polling loop...", flush=True)
        sys.stdout.flush()
        
        poll_interval = int(os.getenv('WORKER_POLL_INTERVAL', 10))
        last_poll_time = 0
        
        while True:
            try:
                current_time = time.time()
                
                # Check if we have capacity for more tasks
                with self.active_tasks_lock:
                    active_count = len(self.active_tasks)
                
                if active_count < self.max_concurrent_tasks:
                    # Only poll if enough time has passed since last poll
                    if current_time - last_poll_time >= poll_interval:
                        # Try to pick up a task via API
                        if self.api.is_enabled:
                            task = self.api.pickup_task()
                            if task:
                                # Process task in thread pool
                                self.executor.submit(self.process_video, task=task)
                        else:
                            # Fallback to direct PostgreSQL polling
                            pending_tasks = self.postgres.get_pending_tasks(limit=1)
                            if pending_tasks and len(pending_tasks) > 0:
                                task = pending_tasks[0]
                                video_id = task.get('video_id')
                                if video_id:
                                    # Track active task to prevent duplicate processing
                                    with self.active_tasks_lock:
                                        if video_id not in self.active_tasks:
                                            self.active_tasks[video_id] = time.time()
                                            # Process task in thread pool
                                            self.executor.submit(self.process_video, task=task)
                        
                        # Update last poll time
                        last_poll_time = current_time
                
                # Print status periodically
                if int(current_time) % 60 == 0:
                    with self.active_tasks_lock:
                        if self.active_tasks:
                            print(f"📊 Active tasks: {len(self.active_tasks)}/{self.max_concurrent_tasks}", flush=True)
                            for vid, start_time in self.active_tasks.items():
                                elapsed = int(current_time - start_time)
                                print(f"   - {vid}: {elapsed}s", flush=True)
                
                # Small sleep to prevent CPU spinning
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\n🛑 Worker stopping gracefully...", flush=True)
                self.executor.shutdown(wait=True, cancel_futures=False)
                break
            except Exception as e:
                print(f"💥 Polling error (will retry): {e}", flush=True)
                time.sleep(30)  # Back off on errors

def main():
    worker = EnhancedWorkerAPI()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--process-all":
            # Process all pending tasks
            print("Processing all pending tasks...", flush=True)
            pending_tasks = worker.postgres.get_pending_tasks(limit=100)
            for task in pending_tasks:
                worker.process_video(task=task)
        elif command == "--process":
            # Process specific video
            if len(sys.argv) > 2:
                video_id = sys.argv[2]
                worker.process_video(video_id=video_id)
            else:
                print("Missing video_id argument", flush=True)
    else:
        # Start polling loop
        worker.run_polling_loop()

if __name__ == "__main__":
    main()
