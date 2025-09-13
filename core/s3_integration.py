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
            return False
        
        try:
            # If backend provided an exact S3 key, use it directly
            if s3_key:
                print(f"🎯 Using exact S3 key from backend: {s3_key}")
                self.s3_client.download_file(self.bucket_name, s3_key, local_path)
                print(f"✅ Video downloaded via exact key: {s3_key}")
                return True

            # Fallback: try to find the actual file in the video_id folder
            print(f"⚠️ No exact S3 key provided, searching in videos/{video_id}/")
            try:
                # List objects in the video folder to find the actual filename
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=f"videos/{video_id}/"
                )
                
                if 'Contents' in response and len(response['Contents']) > 0:
                    # Use the first (and likely only) file in the folder
                    found_s3_key = response['Contents'][0]['Key']
                    self.s3_client.download_file(self.bucket_name, found_s3_key, local_path)
                    print(f"✅ Video downloaded via search: {found_s3_key}")
                    return True
                else:
                    print(f"❌ No video files found in videos/{video_id}/")
                    return False
                    
            except Exception as list_error:
                print(f"❌ Error listing S3 objects: {list_error}")
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
