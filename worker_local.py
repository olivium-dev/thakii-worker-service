#!/usr/bin/env python3
"""
Simplified Worker for Local Development
- No database dependencies
- No S3 dependencies
- Direct file processing
"""

import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path
import shutil
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load environment variables from local.env
load_dotenv('local.env')

class LocalWorker:
    def __init__(self):
        # Mac Mini M2 Optimization: Use multiple cores efficiently
        self.max_concurrent_tasks = int(os.getenv('MAX_CONCURRENT_TASKS', min(multiprocessing.cpu_count(), 3)))
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_tasks)
        
        # Configure intelligent storage selection
        self.temp_base_dir = self._get_temp_storage_path()
        
        # Task processing timeout (30 minutes)
        self.task_timeout = 1800
        
        print("🚀 Local Development Worker", flush=True)
        print(f"   Temp Storage: {self.temp_base_dir}", flush=True)
        print(f"   Max Concurrent Tasks: {self.max_concurrent_tasks}", flush=True)
        print(f"   CPU Cores: {multiprocessing.cpu_count()}", flush=True)
        sys.stdout.flush()
    
    def _get_temp_storage_path(self):
        """
        Intelligently select storage path with automatic fallback
        Priority:
        1. Environment variable TEMP_DIR
        2. System temp directory (fallback)
        """
        # Check environment variable
        env_path = os.getenv('TEMP_DIR')
        if env_path:
            env_path = Path(env_path)
            if not env_path.exists():
                os.makedirs(env_path, exist_ok=True)
            if os.access(env_path, os.W_OK):
                print(f"   📁 Using env storage: {env_path}", flush=True)
                return str(env_path)
        
        # Fallback to system temp
        system_temp = Path(tempfile.gettempdir())
        print(f"   ⚠️  Using system temp (fallback): {system_temp}", flush=True)
        return str(system_temp)
    
    def process_video(self, video_id: str, video_path: str) -> bool:
        print(f"\n🎯 Processing: {video_id}", flush=True)
        print(f"   📁 Video path: {video_path}")
        
        try:
            # Use intelligent storage path
            with tempfile.TemporaryDirectory(dir=self.temp_base_dir) as temp_dir:
                temp_path = Path(temp_dir)
                video_copy_path = temp_path / Path(video_path).name
                pdf_path = temp_path / f"{video_id}.pdf"
                
                print(f"   📁 Using temp directory: {temp_dir}", flush=True)
                sys.stdout.flush()
                
                # Copy video to temp directory
                shutil.copy2(video_path, video_copy_path)
                print(f"   📁 Copied video to: {video_copy_path}", flush=True)
                
                # Generate PDF with superior algorithms
                if not self._generate_superior_pdf(video_copy_path, pdf_path):
                    print(f"❌ PDF generation failed for {video_id}")
                    return False
                
                # Copy PDF to output directory
                output_pdf_path = Path(f"{video_id}.pdf")
                shutil.copy2(pdf_path, output_pdf_path)
                print(f"✅ PDF generated: {output_pdf_path.absolute()}")
                return True
                
        except Exception as e:
            print(f"❌ Processing error: {e}")
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

def main():
    worker = LocalWorker()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--health-check":
            print("🏥 Running health check...")
            print("✅ Local worker is healthy")
            sys.exit(0)
        else:
            # Process single video
            video_id = command
            video_path = sys.argv[2] if len(sys.argv) > 2 else f"{video_id}.mp4"
            print(f"🎯 Processing single video: {video_id}")
            print(f"   📁 Video path: {video_path}")
            success = worker.process_video(video_id, video_path)
            sys.exit(0 if success else 1)
    else:
        print("❌ No video ID provided")
        print("Usage: python worker_local.py <video_id> [video_path]")
        print("Example: python worker_local.py test123 ./tests/videos/input_1.mp4")
        sys.exit(1)

if __name__ == "__main__":
    main()
