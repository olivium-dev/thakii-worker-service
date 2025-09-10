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
        self.s3_client = self._initialize_s3()
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'thakii-video-storage-1753883631')
    
    def _initialize_s3(self) -> Optional[boto3.client]:
        try:
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-2')
            
            if aws_access_key and aws_secret_key:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
                print(f"✅ S3 client initialized for bucket: {self.bucket_name}")
                return s3_client
            else:
                print("❌ AWS credentials not found")
                return None
        except Exception as e:
            print(f"❌ S3 initialization failed: {e}")
            return None
    
    def is_available(self) -> bool:
        return self.s3_client is not None
    
    def download_video(self, video_id: str, local_path: str) -> bool:
        if not self.is_available():
            return False
        
        try:
            extensions = ['mp4', 'avi', 'mov', 'mkv']
            for ext in extensions:
                s3_key = f"videos/{video_id}/{video_id}.{ext}"
                try:
                    self.s3_client.download_file(self.bucket_name, s3_key, local_path)
                    print(f"✅ Video downloaded: {s3_key}")
                    return True
                except self.s3_client.exceptions.NoSuchKey:
                    continue
            return False
        except Exception as e:
            print(f"❌ S3 download error: {e}")
            return False
    
    def upload_pdf(self, local_pdf_path: str, video_id: str) -> Optional[str]:
        if not self.is_available():
            return None
        
        try:
            s3_key = f"pdfs/{video_id}/{video_id}.pdf"
            self.s3_client.upload_file(local_pdf_path, self.bucket_name, s3_key)
            
            s3_url = f"https://{self.bucket_name}.s3.{os.getenv('AWS_DEFAULT_REGION', 'us-east-2')}.amazonaws.com/{s3_key}"
            print(f"✅ PDF uploaded: {s3_key}")
            return s3_url
        except Exception as e:
            print(f"❌ S3 upload error: {e}")
            return None

s3_client = WorkerS3Client()
