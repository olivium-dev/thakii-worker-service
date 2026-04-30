#!/usr/bin/env python3
"""
Minimal S3 Integration for Worker File Handling
"""

import os
import boto3
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class WorkerS3Client:
    def __init__(self):
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'thakii-video-storage-1753883631')
        self.s3_client = self._initialize_s3()
        # Last download error, surfaced to the caller so worker.py can ship
        # the real reason (perm denied / no space / timeout / bucket policy)
        # to the backend instead of the generic "Download failed".
        self.last_error: Optional[str] = None
    
    def _initialize_s3(self) -> Optional[boto3.client]:
        try:
            # Try to use AWS CLI default credentials first
            s3_client = boto3.client('s3')
            
            # Test the connection
            s3_client.list_buckets()
            print(f"✅ S3 client initialized using AWS CLI credentials")
            print(f"✅ Target bucket: {self.bucket_name}")
            return s3_client
            
        except Exception as e:
            print(f"❌ S3 initialization failed: {e}")
            print("💡 Make sure AWS CLI is configured: aws configure")
            return None
    
    def is_available(self) -> bool:
        return self.s3_client is not None
    
    def get_object_size(self, s3_key: str) -> Optional[int]:
        """HEAD the object so we know how much disk we'll need before we
        start writing. Returns None if HEAD fails (we'll let download
        proceed and surface the real error if any)."""
        if not self.is_available():
            return None
        try:
            resp = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return int(resp['ContentLength'])
        except Exception as e:
            print(f"⚠️ HEAD failed for {s3_key}: {e}", flush=True)
            return None

    def _resolve_s3_key(self, video_id: str, s3_key: Optional[str]) -> Optional[str]:
        if s3_key:
            return s3_key
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=f"videos/{video_id}/"
            )
            contents = response.get('Contents') or []
            if contents:
                return contents[0]['Key']
        except Exception as e:
            self.last_error = f"list_objects_v2 failed: {type(e).__name__}: {e}"
        return None

    def download_video(self, video_id: str, local_path: str, s3_key: str = None) -> bool:
        """Download an S3 object, but ONLY if there is enough disk space
        for it. The worker frequently fills /tmp before crashing partway
        through `boto3.download_file`, leaving a stale partial file that
        wastes more disk. Pre-flight here:
          1. Resolve the real S3 key.
          2. HEAD it for the exact byte count.
          3. Compare to free space at the destination.
          4. If insufficient, set last_error to a clear message and bail
             so the caller can mark the task failed and move on. boto3 is
             never invoked → no half-written partials."""
        import shutil as _sh

        if not self.is_available():
            self.last_error = "S3 client not available (boto3 init failed)"
            return False

        self.last_error = None

        resolved_key = self._resolve_s3_key(video_id, s3_key)
        if not resolved_key:
            self.last_error = self.last_error or f"no S3 objects under videos/{video_id}/"
            print(f"❌ {self.last_error}", flush=True)
            return False

        # Pre-flight free-space check. Headroom = file size + 256 MB
        # safety + 2x for whisper/ffmpeg intermediates.
        size_bytes = self.get_object_size(resolved_key)
        parent = os.path.dirname(local_path) or '.'
        try:
            free_bytes = _sh.disk_usage(parent).free
        except Exception as e:
            free_bytes = None
            print(f"⚠️ Could not check free space at {parent}: {e}", flush=True)

        if size_bytes is not None and free_bytes is not None:
            needed = (size_bytes * 2) + (256 * 1024 * 1024)
            free_gb = free_bytes / (1024 ** 3)
            need_gb = needed / (1024 ** 3)
            file_gb = size_bytes / (1024 ** 3)
            print(f"📦 disk: free={free_gb:.2f} GB, file={file_gb:.2f} GB, headroom_required={need_gb:.2f} GB", flush=True)
            if free_bytes < needed:
                self.last_error = (
                    f"insufficient disk space: have {free_gb:.2f} GB free, "
                    f"need ~{need_gb:.2f} GB for {file_gb:.2f} GB file at {parent}"
                )
                print(f"❌ {self.last_error}", flush=True)
                return False

        try:
            print(f"🎯 Downloading S3 key: {resolved_key}", flush=True)
            self.s3_client.download_file(self.bucket_name, resolved_key, local_path)
            print(f"✅ Video downloaded: {resolved_key}", flush=True)
            return True
        except Exception as e:
            # Best-effort cleanup of the half-written partial so we don't
            # leak disk on the way out.
            try:
                if os.path.exists(local_path):
                    os.unlink(local_path)
            except Exception:
                pass
            err_type = type(e).__name__
            self.last_error = f"{err_type}: {e}"[:500]
            print(f"❌ S3 download error: {self.last_error}", flush=True)
            return False
    
    def upload_pdf(self, local_pdf_path: str, video_id: str) -> Optional[str]:
        if not self.is_available():
            return None
        
        try:
            # Use correct S3 path structure: pdfs/{video_id}/{video_id}.pdf
            s3_key = f"pdfs/{video_id}/{video_id}.pdf"
            self.s3_client.upload_file(local_pdf_path, self.bucket_name, s3_key)
            
            s3_url = f"https://{self.bucket_name}.s3.{os.getenv('AWS_DEFAULT_REGION', 'us-east-2')}.amazonaws.com/{s3_key}"
            print(f"✅ PDF uploaded: {s3_key}")
            return s3_url
        except Exception as e:
            print(f"❌ S3 upload error: {e}")
            return None

s3_client = WorkerS3Client()

# Deployment trigger - 20251101_194853
