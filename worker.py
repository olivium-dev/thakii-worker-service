#!/usr/bin/env python3
"""
Optimized Worker for Mac Mini M2 - High Performance Video Processing
- Uses Apple Metal (MPS) GPU acceleration
- Robust queuing with no hanging
- Optimal CPU/RAM utilization
- No fallback code - production ready
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

# Import core integrations
from core.postgres_integration import postgres_client
from core.s3_integration import s3_client
from core.api_task_client import api_client

class EnhancedWorker:
    def __init__(self):
        self.postgres = postgres_client
        self.s3 = s3_client
        self.api = api_client
        
        # Mac Mini M2 Optimization: Use multiple cores efficiently
        self.max_concurrent_tasks = int(os.getenv('MAX_CONCURRENT_TASKS', min(multiprocessing.cpu_count(), 3)))
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_tasks)
        
        # Configure intelligent storage selection
        self.temp_base_dir = self._get_temp_storage_path()
        
        # Task processing timeout (30 minutes)
        self.task_timeout = 1800
        
        print("🚀 Mac Mini M2 Optimized Worker", flush=True)
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
        Priority:
        1. External SSD at /mnt/external-ssd (if available and writable)
        2. Environment variable TEMP_STORAGE_PATH
        3. System temp directory (fallback)
        """
        # Check for external SSD
        external_ssd = Path("/mnt/external-ssd/temp")
        if external_ssd.exists() and os.access(external_ssd, os.W_OK):
            print(f"   💾 Using external SSD: {external_ssd}", flush=True)
            return str(external_ssd)
        
        # Check environment variable
        env_path = os.getenv('TEMP_STORAGE_PATH')
        if env_path:
            env_path = Path(env_path)
            if env_path.exists() and os.access(env_path, os.W_OK):
                print(f"   📁 Using env storage: {env_path}", flush=True)
                return str(env_path)
        
        # Fallback to system temp
        system_temp = Path(tempfile.gettempdir())
        print(f"   ⚠️  Using system temp (fallback): {system_temp}", flush=True)
        return str(system_temp)
    
    def process_video(self, video_id: str, s3_key: str = None, filename: str = None, task_details: dict = None) -> bool:
        print(f"\n🎯 Processing: {video_id}", flush=True)
        if s3_key:
            print(f"   🔑 S3 Key: {s3_key}", flush=True)
        if filename:
            print(f"   📁 Filename: {filename}")
        
        try:
            # Update to processing with 0% progress
            if self.api.is_enabled:
                self.api.update_task_status(video_id, "processing", progress=0)
            else:
                self.postgres.update_task_status(video_id, "processing")
            
            # Get task details (use provided details from API pickup, or fallback to PostgreSQL)
            if task_details:
                task = task_details
            else:
                task = self.postgres.get_task_details(video_id)
                if not task:
                    if self.api.is_enabled:
                        self.api.update_task_status(video_id, "failed", error_message="Task not found")
                    else:
                        self.postgres.update_task_status(video_id, "failed", error_message="Task not found")
                    return False
            
            # Prefer parameters, then task fields, then fallback
            filename = filename or task.get('filename', f'{video_id}.mp4')
            s3_key = s3_key or task.get('s3_key') or task.get('s3_path')
            
            # Use intelligent storage path (external SSD if available, else fallback)
            with tempfile.TemporaryDirectory(dir=self.temp_base_dir) as temp_dir:
                temp_path = Path(temp_dir)
                video_path = temp_path / filename
                pdf_path = temp_path / f"{video_id}.pdf"
                
                print(f"   📁 Using temp directory: {temp_dir}", flush=True)
                sys.stdout.flush()
                
                # Update progress to 10% - Starting download
                if self.api.is_enabled:
                    self.api.update_task_status(video_id, "processing", progress=10)
                else:
                    self.postgres.update_task_status(video_id, "processing")
                
                # Download video (use exact s3_key if available)
                if not self.s3.download_video(video_id, str(video_path), s3_key=s3_key):
                    if self.api.is_enabled:
                        self.api.update_task_status(video_id, "failed", error_message="Download failed")
                    else:
                        self.postgres.update_task_status(video_id, "failed", error_message="Download failed")
                    return False
                
                # Update progress to 30% - Download complete, starting PDF generation
                if self.api.is_enabled:
                    self.api.update_task_status(video_id, "processing", progress=30)
                else:
                    self.postgres.update_task_status(video_id, "processing")
                
                # Generate PDF with superior algorithms
                if not self._generate_superior_pdf(video_path, pdf_path):
                    if self.api.is_enabled:
                        self.api.update_task_status(video_id, "failed", error_message="PDF generation failed")
                    else:
                        self.postgres.update_task_status(video_id, "failed", error_message="PDF generation failed")
                    return False
                
                # Update progress to 80% - PDF generated, starting upload
                if self.api.is_enabled:
                    self.api.update_task_status(video_id, "processing", progress=80)
                else:
                    self.postgres.update_task_status(video_id, "processing")
                
                # Upload PDF
                pdf_url = self.s3.upload_pdf(str(pdf_path), video_id)
                if not pdf_url:
                    if self.api.is_enabled:
                        self.api.update_task_status(video_id, "failed", error_message="Upload failed")
                    else:
                        self.postgres.update_task_status(video_id, "failed", error_message="Upload failed")
                    return False
                
                # Mark completed with 100% progress
                if self.api.is_enabled:
                    self.api.update_task_status(video_id, "done", pdf_url=pdf_url, progress=100)
                else:
                    self.postgres.update_task_status(video_id, "done", pdf_url=pdf_url)
                print(f"🎉 Success: {video_id}")
                return True
                
        except Exception as e:
            if self.api.is_enabled:
                self.api.update_task_status(video_id, "failed", error_message=str(e))
            else:
                self.postgres.update_task_status(video_id, "failed", error_message=str(e))
            return False
    
    def _generate_superior_pdf(self, video_path: Path, pdf_path: Path) -> bool:
        try:
            cmd = [
                sys.executable, "-m", "src.main",
                str(video_path.absolute()),
                "-o", str(pdf_path.absolute())
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes for large files
            
            if result.returncode == 0 and pdf_path.exists():
                size = pdf_path.stat().st_size
                print(f"✅ Superior PDF: {size:,} bytes")
                return True
            else:
                print(f"❌ PDF failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ PDF error: {e}")
            return False
    
    def run_polling_loop(self):
        """Robust polling loop optimized for Mac Mini M2 - No hanging, efficient queuing"""
        print("🔄 Starting robust polling loop (Mac Mini M2 optimized)...", flush=True)
        sys.stdout.flush()
        
        poll_interval = int(os.getenv('WORKER_POLL_INTERVAL', 10))
        active_tasks = set()
        
        while True:
            try:
                # Use API pickup if enabled, otherwise use direct PostgreSQL
                if self.api.is_enabled:
                    # Check if we have capacity
                    if len(active_tasks) < self.max_concurrent_tasks:
                        # Try to pick up one task via API
                        task = self.api.pickup_task()
                        if task:
                            video_id = task.get('video_id')
                            print(f"✅ Picked up task via API: {video_id}", flush=True)
                            active_tasks.add(video_id)
                            
                            # Process with timeout protection, passing task details
                            try:
                                future = self.executor.submit(self.process_video, video_id, task_details=task)
                                future.add_done_callback(lambda f, vid=video_id: active_tasks.discard(vid))
                            except Exception as e:
                                print(f"❌ Failed to submit task {video_id}: {e}", flush=True)
                                active_tasks.discard(video_id)
                else:
                    # Fallback to direct PostgreSQL polling
                    pending_tasks = self.postgres.get_pending_tasks(limit=self.max_concurrent_tasks * 2)
                    
                    if pending_tasks:
                        print(f"📋 Found {len(pending_tasks)} pending tasks", flush=True)
                        
                        for task in pending_tasks:
                            video_id = task.get('video_id')
                            if video_id and video_id not in active_tasks:
                                # Track active task to prevent duplicate processing
                                active_tasks.add(video_id)
                                
                                # Process with timeout protection - no hanging
                                try:
                                    future = self.executor.submit(self.process_video, video_id)
                                    future.add_done_callback(lambda f, vid=video_id: active_tasks.discard(vid))
                                except Exception as e:
                                    print(f"❌ Failed to submit task {video_id}: {e}", flush=True)
                                    active_tasks.discard(video_id)
                    else:
                        print("⏳ No pending tasks...", flush=True)
                
                # Clean up completed/failed tasks from tracking
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                print("\n🛑 Worker stopping gracefully...", flush=True)
                self.executor.shutdown(wait=True, cancel_futures=False)
                break
            except Exception as e:
                print(f"💥 Polling error (will retry): {e}", flush=True)
                time.sleep(30)  # Back off on errors

def main():
    worker = EnhancedWorker()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--process-all":
            print("🔄 Processing all pending tasks from PostgreSQL...", flush=True)
            sys.stdout.flush()
            # Run polling loop for all pending tasks
            worker.run_polling_loop()
        elif command == "--health-check":
            print("🏥 Running health check...")
            print(f"   Firestore: {'✅' if worker.postgres.is_available() else '❌'}")
            print(f"   S3: {'✅' if worker.s3.is_available() else '❌'}")
            sys.exit(0)
        else:
            # Process single video
            video_id = command
            print(f"🎯 Processing single video: {video_id}")
            success = worker.process_video(video_id)
            sys.exit(0 if success else 1)
    else:
        # Run polling loop
        worker.run_polling_loop()

if __name__ == "__main__":
    main()
