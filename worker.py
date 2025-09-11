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

# Import Firebase integration
from core.firestore_integration import firestore_client
from core.s3_integration import s3_client

class EnhancedWorker:
    def __init__(self):
        self.firestore = firestore_client
        self.s3 = s3_client
        print("🚀 Enhanced Worker with Firebase Integration")
        print(f"   Firestore: {'✅' if self.firestore.is_available() else '❌'}")
        print(f"   S3: {'✅' if self.s3.is_available() else '❌'}")
    
    def process_video(self, video_id: str) -> bool:
        print(f"\n🎯 Processing: {video_id}")
        
        try:
            # Update to processing
            self.firestore.update_task_status(video_id, "processing")
            
            # Get task details
            task = self.firestore.get_task_details(video_id)
            if not task:
                self.firestore.update_task_status(video_id, "failed", error="Task not found")
                return False
            
            filename = task.get('filename', f'{video_id}.mp4')
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                video_path = temp_path / filename
                pdf_path = temp_path / f"{video_id}.pdf"
                
                # Download video
                if not self.s3.download_video(video_id, str(video_path)):
                    self.firestore.update_task_status(video_id, "failed", error="Download failed")
                    return False
                
                # Generate PDF with superior algorithms
                if not self._generate_superior_pdf(video_path, pdf_path):
                    self.firestore.update_task_status(video_id, "failed", error="PDF generation failed")
                    return False
                
                # Upload PDF
                pdf_url = self.s3.upload_pdf(str(pdf_path), video_id)
                if not pdf_url:
                    self.firestore.update_task_status(video_id, "failed", error="Upload failed")
                    return False
                
                # Mark completed
                self.firestore.update_task_status(video_id, "completed", pdf_url=pdf_url)
                print(f"🎉 Success: {video_id}")
                return True
                
        except Exception as e:
            self.firestore.update_task_status(video_id, "failed", error=str(e))
            return False
    
    def _generate_superior_pdf(self, video_path: Path, pdf_path: Path) -> bool:
        try:
            cmd = [
                sys.executable, "-m", "src.main",
                str(video_path.absolute()),
                "-o", str(pdf_path.absolute())
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
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
                pending_tasks = self.firestore.get_pending_tasks()
                
                if pending_tasks:
                    for task in pending_tasks:
                        video_id = task.get('id')
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
        # Process single video
        video_id = sys.argv[1]
        success = worker.process_video(video_id)
        sys.exit(0 if success else 1)
    else:
        # Run polling loop
        worker.run_polling_loop()

if __name__ == "__main__":
    main()
