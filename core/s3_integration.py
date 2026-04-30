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
    
    def download_video(self, video_id: str, local_path: str, s3_key: str = None) -> bool:
        if not self.is_available():
            self.last_error = "S3 client not available (boto3 init failed)"
            return False

        # Reset before each attempt so a stale message from a prior task
        # doesn't get attributed to this one.
        self.last_error = None

        # Pre-flight: free disk space at the destination. Most "Download
        # failed" reports are really ENOSPC; surfacing it explicitly saves
        # hours of investigation.
        try:
            parent = os.path.dirname(local_path) or '.'
            usage = __import__('shutil').disk_usage(parent)
            free_gb = usage.free / (1024 ** 3)
            print(f"📦 Free space at {parent}: {free_gb:.2f} GB", flush=True)
            if usage.free < 1024 * 1024 * 1024:  # <1 GB
                self.last_error = f"low disk space at {parent}: {free_gb:.2f} GB free"
                print(f"⚠️ {self.last_error}", flush=True)
        except Exception as space_err:
            print(f"⚠️ Could not check free space: {space_err}", flush=True)

        try:
            if s3_key:
                print(f"🎯 Using exact S3 key from backend: {s3_key}", flush=True)
                self.s3_client.download_file(self.bucket_name, s3_key, local_path)
                print(f"✅ Video downloaded via exact key: {s3_key}", flush=True)
                return True

            print(f"⚠️ No exact S3 key provided, searching in videos/{video_id}/", flush=True)
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"videos/{video_id}/"
            )
            if 'Contents' in response and len(response['Contents']) > 0:
                found_s3_key = response['Contents'][0]['Key']
                self.s3_client.download_file(self.bucket_name, found_s3_key, local_path)
                print(f"✅ Video downloaded via search: {found_s3_key}", flush=True)
                return True

            self.last_error = f"no S3 objects under videos/{video_id}/"
            print(f"❌ {self.last_error}", flush=True)
            return False

        except Exception as e:
            # Capture the full exception type + message so the operator
            # can see "AccessDenied", "EndpointConnectionError",
            # "[Errno 28] No space left on device", etc.
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
