#!/usr/bin/env python3
"""
Enhanced Worker with Firebase Integration
Combines superior PDF generation with backend communication
"""

import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path
import shutil

# Import Firebase integration
from core.postgres_integration import postgres_client
from core.s3_integration import s3_client

class EnhancedWorker:
    def __init__(self):
        self.postgres = postgres_client
        self.s3 = s3_client
        
        # Configure intelligent storage selection
        self.temp_base_dir = self._get_temp_storage_path()
        
        print("🚀 Enhanced Worker with PostgreSQL Integration")
        print(f"   PostgreSQL: {'✅' if self.postgres.is_available() else '❌'}")
        print(f"   S3: {'✅' if self.s3.is_available() else '❌'}")
        print(f"   Temp Storage: {self.temp_base_dir}")
    
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
            print(f"   💾 Using external SSD: {external_ssd}")
            return str(external_ssd)
        
        # Check environment variable
        env_path = os.getenv('TEMP_STORAGE_PATH')
        if env_path:
            env_path = Path(env_path)
            if env_path.exists() and os.access(env_path, os.W_OK):
                print(f"   📁 Using env storage: {env_path}")
                return str(env_path)
        
        # Fallback to system temp
        system_temp = Path(tempfile.gettempdir())
        print(f"   ⚠️  Using system temp (fallback): {system_temp}")
        return str(system_temp)
    
    def process_video(self, video_id: str, s3_key: str = None, filename: str = None) -> bool:
        print(f"\n🎯 Processing: {video_id}")
        if s3_key:
            print(f"   🔑 S3 Key: {s3_key}")
        if filename:
            print(f"   📁 Filename: {filename}")
        
        try:
            # Update to processing
            self.postgres.update_task_status(video_id, "processing")
            
            # Get task details
            task = self.postgres.get_task_details(video_id)
            if not task:
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
                
                print(f"   📁 Using temp directory: {temp_dir}")
                
                # Download video (use exact s3_key if available)
                if not self.s3.download_video(video_id, str(video_path), s3_key=s3_key):
                    self.postgres.update_task_status(video_id, "failed", error_message="Download failed")
                    return False
                
                # Generate PDF with superior algorithms
                if not self._generate_superior_pdf(video_path, pdf_path):
                    self.postgres.update_task_status(video_id, "failed", error_message="PDF generation failed")
                    return False
                
                # Upload PDF
                pdf_url = self.s3.upload_pdf(str(pdf_path), video_id)
                if not pdf_url:
                    self.postgres.update_task_status(video_id, "failed", error_message="Upload failed")
                    return False
                
                # Mark completed
                self.postgres.update_task_status(video_id, "done", pdf_url=pdf_url)
                print(f"🎉 Success: {video_id}")
                return True
                
        except Exception as e:
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
        print("🔄 Starting polling loop...")
        
        while True:
            try:
                pending_tasks = self.postgres.get_pending_tasks()
                
                if pending_tasks:
                    for task in pending_tasks:
                        video_id = task.get('video_id')
                        if video_id:
                            self.process_video(video_id)
                else:
                    print("⏳ No pending tasks...")
                
                time.sleep(10)
            except KeyboardInterrupt:
                print("\n🛑 Worker stopped")
                break
            except Exception as e:
                print(f"💥 Error: {e}")
                time.sleep(30)

def main():
    worker = EnhancedWorker()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--process-all":
            print("🔄 Processing all pending tasks from Firebase...")
            # Run polling loop for all pending tasks
            worker.run_polling_loop()
        elif command == "--health-check":
            print("🏥 Running health check...")
            print(f"   Firestore: {'✅' if worker.firestore.is_available() else '❌'}")
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
