#!/usr/bin/env python3
"""
Enhanced S3 Authentication with Security Improvements
"""

import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import logging
import datetime

# Load environment variables
load_dotenv()

# Setup secure logging
logger = logging.getLogger(__name__)

class SecureS3Client:
    def __init__(self):
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        self.region = os.getenv('AWS_DEFAULT_REGION', 'us-east-2')
        self.s3_client = self._initialize_s3()
        self._credential_source = None
        self._initialized_at = datetime.datetime.now()
    
    def _initialize_s3(self) -> Optional[boto3.client]:
        """Initialize S3 with enhanced credential handling"""
        try:
            # Method 1: Explicit credentials from environment
            access_key = os.getenv('AWS_ACCESS_KEY_ID')
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            
            if access_key and secret_key:
                # Validate credential format
                if not access_key.startswith('AKIA') and not access_key.startswith('ASIA'):
                    logger.warning("⚠️ AWS Access Key ID format may be invalid")
                
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=self.region
                )
                self._credential_source = "environment_variables"
                logger.info("🔐 S3 initialized with environment credentials")
            else:
                # Method 2: Default credential chain (AWS CLI, IAM roles, etc.)
                s3_client = boto3.client('s3', region_name=self.region)
                self._credential_source = "default_chain"
                logger.info("🔐 S3 initialized with default credential chain")
            
            # Validate credentials and bucket access
            if self._validate_s3_access(s3_client):
                return s3_client
            else:
                return None
                
        except NoCredentialsError:
            logger.error("❌ No AWS credentials found")
            return None
        except Exception as e:
            logger.error(f"❌ S3 initialization failed: {e}")
            return None
    
    def _validate_s3_access(self, s3_client) -> bool:
        """Validate S3 access and bucket permissions"""
        try:
            # Test 1: List buckets (validates credentials)
            response = s3_client.list_buckets()
            logger.info(f"✅ AWS credentials validated - Found {len(response.get('Buckets', []))} buckets")
            
            # Test 2: Check bucket access
            if self.bucket_name:
                try:
                    s3_client.head_bucket(Bucket=self.bucket_name)
                    logger.info(f"✅ Bucket access validated: {self.bucket_name}")
                    
                    # Test 3: Check bucket region
                    try:
                        bucket_region = s3_client.get_bucket_location(Bucket=self.bucket_name)
                        actual_region = bucket_region.get('LocationConstraint') or 'us-east-1'
                        if actual_region != self.region:
                            logger.warning(f"⚠️ Bucket region mismatch: expected {self.region}, actual {actual_region}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not determine bucket region: {e}")
                    
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == '403':
                        logger.error(f"❌ Access denied to bucket: {self.bucket_name}")
                    elif error_code == '404':
                        logger.error(f"❌ Bucket not found: {self.bucket_name}")
                    else:
                        logger.error(f"❌ Bucket validation failed: {e}")
                    return False
            else:
                logger.warning("⚠️ No S3_BUCKET_NAME configured")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ S3 validation failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if S3 is available"""
        return self.s3_client is not None
    
    def get_credential_info(self) -> Dict[str, Any]:
        """Get information about current credential source"""
        info = {
            "available": self.is_available(),
            "credential_source": self._credential_source,
            "bucket": self.bucket_name,
            "region": self.region,
            "initialized_at": self._initialized_at.isoformat(),
            "uptime_seconds": (datetime.datetime.now() - self._initialized_at).total_seconds()
        }
        
        # Add bucket info if available
        if self.is_available() and self.bucket_name:
            try:
                response = self.s3_client.head_bucket(Bucket=self.bucket_name)
                info["bucket_accessible"] = True
                info["bucket_region"] = response.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('x-amz-bucket-region', 'unknown')
            except Exception:
                info["bucket_accessible"] = False
        
        return info
    
    def download_video(self, video_id: str, local_path: str) -> bool:
        """Download video with enhanced error handling and logging"""
        if not self.is_available():
            logger.error(f"❌ Cannot download video {video_id}: S3 not available")
            return False
        
        try:
            logger.info(f"📥 Starting download for video: {video_id}")
            
            # First, try to find the actual file in the video_id folder
            try:
                # List objects in the video folder to find the actual filename
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=f"videos/{video_id}/"
                )
                
                if 'Contents' in response and len(response['Contents']) > 0:
                    # Use the first (and likely only) file in the folder
                    s3_key = response['Contents'][0]['Key']
                    file_size = response['Contents'][0]['Size']
                    
                    logger.info(f"📁 Found video file: {s3_key} ({file_size:,} bytes)")
                    
                    # Download with progress tracking
                    self.s3_client.download_file(self.bucket_name, s3_key, local_path)
                    
                    # Verify download
                    if os.path.exists(local_path):
                        downloaded_size = os.path.getsize(local_path)
                        if downloaded_size == file_size:
                            logger.info(f"✅ Video downloaded successfully: {s3_key} ({downloaded_size:,} bytes)")
                            return True
                        else:
                            logger.error(f"❌ Download size mismatch: expected {file_size}, got {downloaded_size}")
                            return False
                    else:
                        logger.error(f"❌ Downloaded file not found at: {local_path}")
                        return False
                else:
                    logger.error(f"❌ No video files found in videos/{video_id}/")
                    return False
                    
            except Exception as list_error:
                logger.error(f"❌ Error listing S3 objects: {list_error}")
                return False
                
        except Exception as e:
            logger.error(f"❌ S3 download error for {video_id}: {e}")
            return False
    
    def upload_pdf(self, local_pdf_path: str, video_id: str) -> Optional[str]:
        """Upload PDF with enhanced error handling and validation"""
        if not self.is_available():
            logger.error(f"❌ Cannot upload PDF for {video_id}: S3 not available")
            return None
        
        try:
            # Validate local file
            if not os.path.exists(local_pdf_path):
                logger.error(f"❌ PDF file not found: {local_pdf_path}")
                return None
            
            file_size = os.path.getsize(local_pdf_path)
            if file_size == 0:
                logger.error(f"❌ PDF file is empty: {local_pdf_path}")
                return None
            
            logger.info(f"📤 Starting PDF upload: {video_id} ({file_size:,} bytes)")
            
            s3_key = f"pdfs/{video_id}/{video_id}.pdf"
            
            # Upload with metadata
            extra_args = {
                'ContentType': 'application/pdf',
                'Metadata': {
                    'video_id': video_id,
                    'upload_timestamp': datetime.datetime.now().isoformat(),
                    'worker_source': self._credential_source or 'unknown'
                }
            }
            
            self.s3_client.upload_file(
                local_pdf_path, 
                self.bucket_name, 
                s3_key,
                ExtraArgs=extra_args
            )
            
            # Verify upload
            try:
                head_response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                uploaded_size = head_response['ContentLength']
                
                if uploaded_size == file_size:
                    s3_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
                    logger.info(f"✅ PDF uploaded successfully: {s3_key} ({uploaded_size:,} bytes)")
                    return s3_url
                else:
                    logger.error(f"❌ Upload size mismatch: expected {file_size}, got {uploaded_size}")
                    return None
            except Exception as verify_error:
                logger.error(f"❌ Upload verification failed: {verify_error}")
                return None
            
        except Exception as e:
            logger.error(f"❌ S3 upload error for {video_id}: {e}")
            return None
    
    def list_videos(self, prefix: str = "videos/") -> list:
        """List videos in S3 bucket"""
        if not self.is_available():
            logger.error("❌ Cannot list videos: S3 not available")
            return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            videos = []
            for obj in response.get('Contents', []):
                videos.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'video_id': obj['Key'].split('/')[1] if '/' in obj['Key'] else 'unknown'
                })
            
            logger.info(f"✅ Found {len(videos)} video files")
            return videos
            
        except Exception as e:
            logger.error(f"❌ Error listing videos: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive S3 health check"""
        health_info = {
            "timestamp": datetime.datetime.now().isoformat(),
            "s3_available": self.is_available(),
            "credential_info": self.get_credential_info()
        }
        
        if self.is_available():
            try:
                # Test basic operations
                test_key = f"_health_checks/test_{int(datetime.datetime.now().timestamp())}.txt"
                test_content = b"health check test"
                
                # Test upload
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=test_key,
                    Body=test_content
                )
                
                # Test download
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=test_key)
                downloaded_content = response['Body'].read()
                
                # Test delete
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=test_key)
                
                if downloaded_content == test_content:
                    health_info["operations_test"] = "passed"
                    logger.info("✅ S3 health check passed")
                else:
                    health_info["operations_test"] = "failed: content mismatch"
                    
            except Exception as e:
                health_info["operations_test"] = f"failed: {e}"
                logger.error(f"❌ S3 operations test failed: {e}")
        
        return health_info

# Create global instance
secure_s3_client = SecureS3Client()
