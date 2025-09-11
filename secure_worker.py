#!/usr/bin/env python3
"""
Secure Enhanced Worker with Comprehensive Authentication
Combines superior PDF generation with enterprise-grade security
"""

import os
import sys
import time
import tempfile
import subprocess
import json
from pathlib import Path
import logging

# Import secure authentication components
from core.secure_firestore_client import secure_firestore_client
from core.secure_s3_client import secure_s3_client
from core.authentication_manager import auth_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SecureEnhancedWorker:
    """Enhanced Worker with comprehensive security and monitoring"""
    
    def __init__(self):
        self.firestore = secure_firestore_client
        self.s3 = secure_s3_client
        self.auth_manager = auth_manager
        
        logger.info("🚀 Secure Enhanced Worker with Enterprise Authentication")
        
        # Perform initial authentication check
        auth_status = self.auth_manager.get_authentication_status()
        logger.info(f"🔐 Authentication Status: {auth_status['overall_status']}")
        logger.info(f"   Firebase: {'✅' if auth_status['firebase']['available'] else '❌'} ({auth_status['firebase']['credential_source']})")
        logger.info(f"   S3: {'✅' if auth_status['s3']['available'] else '❌'} ({auth_status['s3']['credential_source']})")
        
        # Generate security report
        if logger.isEnabledFor(logging.INFO):
            security_report = self.auth_manager.generate_security_report()
            logger.info(f"📊 Security Score: {security_report['summary']['security_score']}/10")
            logger.info(f"📊 Overall Assessment: {security_report['summary']['overall_assessment']}")
            
            # Log high-severity recommendations
            high_severity_recs = [rec for rec in security_report['security_recommendations'] if rec['severity'] == 'high']
            if high_severity_recs:
                logger.warning(f"⚠️ {len(high_severity_recs)} high-severity security issues found")
                for rec in high_severity_recs:
                    logger.warning(f"   • {rec['title']}: {rec['recommendation']}")
    
    def process_video(self, video_id: str) -> bool:
        """Process video with enhanced security and error handling"""
        logger.info(f"\n🎯 Processing video: {video_id}")
        
        try:
            # Pre-flight authentication check
            auth_status = self.auth_manager.get_authentication_status()
            if auth_status['overall_status'] == 'failed':
                logger.error("❌ Authentication failed - cannot process video")
                return False
            elif auth_status['overall_status'] == 'partial':
                logger.warning("⚠️ Partial authentication - some features may not work")
            
            # Update to processing status
            if not self.firestore.update_task_status(video_id, "processing"):
                logger.error("❌ Failed to update task status to processing")
                return False
            
            # Get task details
            task = self.firestore.get_task_details(video_id)
            if not task:
                self.firestore.update_task_status(video_id, "failed", error="Task not found in Firestore")
                return False
            
            filename = task.get('filename', f'{video_id}.mp4')
            logger.info(f"📁 Processing file: {filename}")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                video_path = temp_path / filename
                pdf_path = temp_path / f"{video_id}.pdf"
                
                logger.info(f"📂 Working directory: {temp_path}")
                
                # Download video from S3
                logger.info("📥 Downloading video from S3...")
                if not self.s3.download_video(video_id, str(video_path)):
                    error_msg = "Failed to download video from S3"
                    logger.error(f"❌ {error_msg}")
                    self.firestore.update_task_status(video_id, "failed", error=error_msg)
                    return False
                
                # Verify downloaded video
                if not video_path.exists() or video_path.stat().st_size == 0:
                    error_msg = "Downloaded video file is missing or empty"
                    logger.error(f"❌ {error_msg}")
                    self.firestore.update_task_status(video_id, "failed", error=error_msg)
                    return False
                
                logger.info(f"✅ Video downloaded: {video_path.stat().st_size:,} bytes")
                
                # Generate PDF with superior algorithms
                logger.info("🎨 Generating PDF with superior algorithms...")
                if not self._generate_superior_pdf(video_path, pdf_path):
                    error_msg = "PDF generation failed"
                    logger.error(f"❌ {error_msg}")
                    self.firestore.update_task_status(video_id, "failed", error=error_msg)
                    return False
                
                # Verify generated PDF
                if not pdf_path.exists() or pdf_path.stat().st_size == 0:
                    error_msg = "Generated PDF file is missing or empty"
                    logger.error(f"❌ {error_msg}")
                    self.firestore.update_task_status(video_id, "failed", error=error_msg)
                    return False
                
                pdf_size = pdf_path.stat().st_size
                logger.info(f"✅ PDF generated: {pdf_size:,} bytes")
                
                # Upload PDF to S3
                logger.info("📤 Uploading PDF to S3...")
                pdf_url = self.s3.upload_pdf(str(pdf_path), video_id)
                if not pdf_url:
                    error_msg = "Failed to upload PDF to S3"
                    logger.error(f"❌ {error_msg}")
                    self.firestore.update_task_status(video_id, "failed", error=error_msg)
                    return False
                
                logger.info(f"✅ PDF uploaded: {pdf_url}")
                
                # Mark task as completed
                completion_data = {
                    'pdf_url': pdf_url,
                    'pdf_size': pdf_size,
                    'video_filename': filename,
                    'processing_node': os.uname().nodename if hasattr(os, 'uname') else 'unknown'
                }
                
                if not self.firestore.update_task_status(video_id, "completed", **completion_data):
                    logger.warning("⚠️ Failed to update completion status, but processing succeeded")
                
                logger.info(f"🎉 Successfully processed video: {video_id}")
                return True
                
        except Exception as e:
            error_msg = f"Unexpected error during processing: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.firestore.update_task_status(video_id, "failed", error=error_msg)
            return False
    
    def _generate_superior_pdf(self, video_path: Path, pdf_path: Path) -> bool:
        """Generate PDF using superior algorithms with enhanced error handling"""
        try:
            logger.info(f"🎨 Starting PDF generation for: {video_path.name}")
            
            cmd = [
                sys.executable, "-m", "src.main",
                str(video_path.absolute()),
                "-o", str(pdf_path.absolute())
            ]
            
            logger.info(f"🔧 Running command: {' '.join(cmd)}")
            
            # Run with timeout and capture output
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300,  # 5 minute timeout
                cwd=Path(__file__).parent  # Ensure correct working directory
            )
            
            if result.returncode == 0:
                if pdf_path.exists():
                    size = pdf_path.stat().st_size
                    logger.info(f"✅ Superior PDF generated successfully: {size:,} bytes")
                    return True
                else:
                    logger.error("❌ PDF generation command succeeded but file not found")
                    logger.error(f"Expected path: {pdf_path}")
                    return False
            else:
                logger.error(f"❌ PDF generation failed with return code: {result.returncode}")
                if result.stdout:
                    logger.error(f"STDOUT: {result.stdout}")
                if result.stderr:
                    logger.error(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ PDF generation timed out after 5 minutes")
            return False
        except Exception as e:
            logger.error(f"❌ PDF generation error: {e}")
            return False
    
    def run_polling_loop(self, poll_interval: int = 10):
        """Run polling loop with enhanced monitoring and error handling"""
        logger.info("🔄 Starting secure polling loop...")
        logger.info(f"⏱️ Poll interval: {poll_interval} seconds")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                # Periodic authentication health check
                if consecutive_errors == 0:  # Only when stable
                    auth_status = self.auth_manager.get_authentication_status()
                    if auth_status['overall_status'] == 'failed':
                        logger.error("❌ Authentication system failure detected")
                        consecutive_errors += 1
                        time.sleep(30)  # Wait longer on auth failure
                        continue
                
                # Get pending tasks
                pending_tasks = self.firestore.get_pending_tasks()
                
                if pending_tasks:
                    logger.info(f"📋 Found {len(pending_tasks)} pending tasks")
                    
                    for task in pending_tasks:
                        video_id = task.get('id')
                        if video_id:
                            logger.info(f"🎯 Processing task: {video_id}")
                            success = self.process_video(video_id)
                            
                            if success:
                                consecutive_errors = 0  # Reset error counter on success
                            else:
                                consecutive_errors += 1
                                logger.warning(f"⚠️ Task failed, consecutive errors: {consecutive_errors}")
                        else:
                            logger.warning("⚠️ Task missing video ID, skipping")
                else:
                    if consecutive_errors == 0:
                        logger.info("⏳ No pending tasks, waiting...")
                    consecutive_errors = 0  # Reset error counter when no tasks
                
                # Check if we should stop due to too many errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"❌ Too many consecutive errors ({consecutive_errors}), stopping worker")
                    break
                
                # Dynamic sleep based on error state
                sleep_time = poll_interval if consecutive_errors == 0 else min(poll_interval * 2, 60)
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Worker stopped by user")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"💥 Unexpected error in polling loop: {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"❌ Too many consecutive errors, stopping worker")
                    break
                
                # Exponential backoff on errors
                sleep_time = min(30 * (2 ** min(consecutive_errors, 4)), 300)  # Max 5 minutes
                logger.info(f"⏳ Waiting {sleep_time} seconds before retry...")
                time.sleep(sleep_time)
    
    def run_health_check(self) -> bool:
        """Run comprehensive health check and return status"""
        logger.info("🔍 Running comprehensive health check...")
        
        try:
            health_report = self.auth_manager.perform_health_check()
            
            # Print detailed health information
            logger.info("📊 Health Check Results:")
            logger.info(f"   Overall Health: {health_report['overall_health']}")
            logger.info(f"   Firebase: {'✅' if health_report['firebase']['firestore_available'] else '❌'}")
            logger.info(f"   S3: {'✅' if health_report['s3']['s3_available'] else '❌'}")
            
            # Print security recommendations
            security_report = self.auth_manager.generate_security_report()
            recommendations = security_report['security_recommendations']
            
            if recommendations:
                logger.info(f"📋 Security Recommendations ({len(recommendations)}):")
                for rec in recommendations:
                    severity_emoji = "🔴" if rec['severity'] == 'high' else "🟡" if rec['severity'] == 'medium' else "🟢"
                    logger.info(f"   {severity_emoji} {rec['title']}: {rec['recommendation']}")
            else:
                logger.info("✅ No security recommendations")
            
            return health_report['overall_health'] in ['healthy', 'partial']
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

def main():
    """Main entry point with enhanced command line interface"""
    worker = SecureEnhancedWorker()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--health-check":
            # Run health check
            success = worker.run_health_check()
            sys.exit(0 if success else 1)
            
        elif command == "--security-report":
            # Generate and print security report
            try:
                report = worker.auth_manager.generate_security_report()
                print(json.dumps(report, indent=2, default=str))
                sys.exit(0)
            except Exception as e:
                logger.error(f"❌ Failed to generate security report: {e}")
                sys.exit(1)
                
        elif command.startswith("--poll-interval="):
            # Run polling loop with custom interval
            try:
                interval = int(command.split("=")[1])
                worker.run_polling_loop(interval)
            except ValueError:
                logger.error("❌ Invalid poll interval, must be integer")
                sys.exit(1)
                
        else:
            # Process single video
            video_id = command
            logger.info(f"🎯 Processing single video: {video_id}")
            success = worker.process_video(video_id)
            sys.exit(0 if success else 1)
    else:
        # Run default polling loop
        worker.run_polling_loop()

if __name__ == "__main__":
    main()
