#!/usr/bin/env python3
"""
Thakii Worker Service - Local API Server (No Authentication Required)
Provides HTTP API endpoints for video processing without any authentication
"""

import os
import json
import uuid
import datetime
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_file
import tempfile
import subprocess
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configuration: Real Sample Mode for enhanced slide detection
# API_REAL_SAMPLE_MODE=true (default): Use optimized algorithm with better slide detection
# API_REAL_SAMPLE_MODE=false: Use original algorithm for backward compatibility

try:
    from src.main import CommandLineArgRunner
    print("✅ Successfully imported src.main.CommandLineArgRunner")
    main_runner = CommandLineArgRunner()
except ImportError as e:
    print(f"⚠️ Warning: Could not import src.main - {e}")
    main_runner = None

app = Flask(__name__)

# Initialize structured logging system
try:
    from core.logging_system import get_logger, log_video_start, log_video_complete, log_video_failed, log_error
    from core.flask_logging_middleware import setup_request_logging, VideoProcessingLogger
    
    # Setup request/response logging middleware
    setup_request_logging(app)
    
    # Get the logger instance
    worker_logger = get_logger()
    worker_logger.info("Structured logging system initialized", extra={
        "logs_dir": "logs/YYYY/MM/DD/",
        "log_types": ["api.log", "errors.log", "processing.log", "requests.log"]
    })
    LOGGING_ENABLED = True
except ImportError as e:
    print(f"⚠️ Warning: Structured logging not available - {e}")
    worker_logger = None
    LOGGING_ENABLED = False

# Import Firebase integration (REQUIRED)
from core.postgres_integration import postgres_client
print("✅ Firebase integration loaded - Local storage disabled")

# Local task storage for API server (fallback when Firebase unavailable)
tasks_storage = {}

def cleanup_local_files(video_id):
    """Clean up local video and PDF files for a video_id"""
    try:
        video_path = Path(f"{video_id}.mp4")
        pdf_path = Path(f"{video_id}.pdf")
        
        cleaned_files = []
        for file_path in [video_path, pdf_path]:
            if file_path.exists():
                file_path.unlink()
                cleaned_files.append(str(file_path))
                print(f"🧹 Cleaned up: {file_path}")
        
        if cleaned_files:
            print(f"✅ Storage cleanup completed for {video_id}: {len(cleaned_files)} files removed")
        
    except Exception as e:
        print(f"⚠️ Storage cleanup error for {video_id}: {e}")

def real_video_processing(video_id, video_path):
    """
    Real video processing function that runs in background
    Integrates with actual src/main.py logic with Real Sample Mode optimization
    """
    output_pdf = None
    start_time = time.time()
    
    # Log video processing start
    if LOGGING_ENABLED:
        log_video_start(video_id, str(video_path))
    print(f"🎬 Starting REAL processing for video {video_id}")
    
    try:
        # Configure Real Sample Mode for enhanced slide detection
        enable_real_sample_mode = os.getenv('API_REAL_SAMPLE_MODE', 'true').lower() == 'true'
        if enable_real_sample_mode:
            os.environ['REAL_SAMPLE_MODE'] = 'true'
            if LOGGING_ENABLED:
                worker_logger.info("Real Sample Mode: ENABLED", extra={'video_id': video_id})
            print(f"🚀 Real Sample Mode: ENABLED for enhanced slide detection")
        else:
            os.environ['REAL_SAMPLE_MODE'] = 'false'
            if LOGGING_ENABLED:
                worker_logger.info("Real Sample Mode: DISABLED", extra={'video_id': video_id})
            print(f"📊 Real Sample Mode: DISABLED (using original algorithm)")
        
        # Update status in Firebase
        try:
            postgres_client.update_task_status(video_id, "processing")
            if LOGGING_ENABLED:
                worker_logger.info("Updated Firebase status to processing", extra={'video_id': video_id})
            print(f"✅ Updated Firebase status to processing: {video_id}")
        except Exception as e:
            if LOGGING_ENABLED:
                worker_logger.warning(f"Failed to update Firebase status: {e}", extra={'video_id': video_id})
            print(f"⚠️ Failed to update Firebase status: {e}")
        
        # Method 1: Try to use imported main runner
        if main_runner:
            if LOGGING_ENABLED:
                worker_logger.info("Using imported CommandLineArgRunner", extra={'video_id': video_id})
            print(f"📚 Using imported CommandLineArgRunner")
            # Set up arguments for main runner
            output_pdf = f"{video_id}.pdf"
            args = [str(video_path), "-o", output_pdf]
            
            # Parse and run
            if LOGGING_ENABLED:
                worker_logger.debug(f"Running with args: {args}", extra={'video_id': video_id})
            print(f"🔧 Args: {args}")
            main_runner.run(args)
            
            pdf_path = Path(output_pdf)
            if not pdf_path.exists():
                raise Exception("PDF was not generated by main runner")
        else:
            # Method 2: Direct subprocess call to src/main.py
            if LOGGING_ENABLED:
                worker_logger.info("Using subprocess call to src/main.py", extra={'video_id': video_id})
            print(f"🔧 Using subprocess call to src/main.py")
            output_pdf = f"{video_id}.pdf"
            # Pass environment variables to subprocess
            env = os.environ.copy()
            result = subprocess.run([
                sys.executable, '-m', 'src.main', str(video_path), '-o', output_pdf
            ], capture_output=True, text=True, cwd=os.path.dirname(__file__), env=env)
            
            if result.returncode != 0:
                if LOGGING_ENABLED:
                    worker_logger.error(f"Subprocess failed: {result.stderr}", extra={
                        'video_id': video_id,
                        'stdout': result.stdout,
                        'stderr': result.stderr
                    })
                raise Exception(f"Main process failed: {result.stderr}")
            
            # Look for generated PDF
            pdf_path = Path(output_pdf)
            if not pdf_path.exists():
                raise Exception("PDF was not generated by main process")
        
        # Calculate processing time
        processing_time = time.time() - start_time
        pdf_size = pdf_path.stat().st_size
        
        # Update status to completed
        # Update status in Firebase
        try:
            postgres_client.update_task_status(video_id, "completed", pdf_url=f"local://{pdf_path}")
            if LOGGING_ENABLED:
                worker_logger.info("Updated Firebase status to completed", extra={'video_id': video_id})
            print(f"✅ Updated Firebase status to completed: {video_id}")
        except Exception as e:
            if LOGGING_ENABLED:
                worker_logger.warning(f"Failed to update Firebase status: {e}", extra={'video_id': video_id})
            print(f"⚠️ Failed to update Firebase status: {e}")
        
        # Log successful completion
        if LOGGING_ENABLED:
            log_video_complete(video_id, pdf_size=pdf_size, processing_time=processing_time)
        print(f"✅ REAL processing completed for video {video_id}")
        
    except Exception as e:
        processing_time = time.time() - start_time
        
        # Log processing failure
        if LOGGING_ENABLED:
            log_video_failed(video_id, str(e), processing_time=processing_time)
        print(f"❌ REAL processing failed for video {video_id}: {str(e)}")
        
        # Update status in Firebase
        try:
            postgres_client.update_task_status(video_id, "failed", error=str(e))
            if LOGGING_ENABLED:
                worker_logger.info("Updated Firebase status to failed", extra={'video_id': video_id})
            print(f"✅ Updated Firebase status to failed: {video_id}")
        except Exception as e2:
            if LOGGING_ENABLED:
                worker_logger.warning(f"Failed to update Firebase status: {e2}", extra={'video_id': video_id})
            print(f"⚠️ Failed to update Firebase status: {e2}")
    finally:
        # Always clean up local files after processing (success or failure)
        cleanup_local_files(video_id)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - no authentication required"""
    real_sample_mode = os.getenv('API_REAL_SAMPLE_MODE', 'true').lower() == 'true'
    
    # Get logging status
    logging_info = {
        "enabled": LOGGING_ENABLED,
        "directory": "logs/YYYY/MM/DD/",
        "log_types": ["api.log", "errors.log", "processing.log", "requests.log"]
    }
    
    if LOGGING_ENABLED:
        try:
            from core.log_viewer import LogViewer
            viewer = LogViewer()
            available_dates = viewer.list_available_dates()
            logging_info["available_dates"] = len(available_dates)
            if available_dates:
                logging_info["latest_date"] = available_dates[0]['date']
        except:
            pass
    
    return jsonify({
        "database": "Local",
        "service": "Thakii Lecture2PDF Service",
        "status": "healthy",
        "storage": "Local",
        "timestamp": datetime.datetime.now().isoformat(),
        "api_version": "1.0",
        "configuration": {
            "real_sample_mode": real_sample_mode,
            "algorithm": "Real Sample Optimized" if real_sample_mode else "Original"
        },
        "logging": logging_info,
        "endpoints": {
            "upload": "/upload",
            "list": "/list", 
            "download": "/download/{video_id}.pdf",
            "process": "/process/{video_id}",
            "generate": "/generate-pdf"
        }
    })

@app.route('/upload', methods=['POST'])
def upload_video():
    """Upload video endpoint - no authentication required"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        filename = data.get('filename')
        user_id = data.get('user_id')
        size = data.get('size', 0)
        content_type = data.get('content_type', 'video/mp4')
        user_email = data.get('user_email', 'anonymous@thakii.dev')
        
        if not filename:
            return jsonify({"error": "filename is required"}), 400
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        # Generate unique video ID
        video_id = f"video-{uuid.uuid4().hex[:8]}"
        
        # Create task record
        task = {
            "id": video_id,
            "filename": filename,
            "size": size,
            "content_type": content_type,
            "user_id": user_id,
            "user_email": user_email,
            "status": "uploaded",
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat()
        }
        
        # Store task in memory
        tasks_storage[video_id] = task
        
        # Store in Firebase if available
        try:
            from core.postgres_integration import postgres_client
            if postgres_client.is_available():
                postgres_client.update_task_status(
                    video_id, "uploaded",
                    filename=filename,
                    size=size,
                    user_id=user_id,
                    user_email=user_email,
                    content_type=content_type
                )
        except Exception as e:
            print(f"Firebase storage failed: {e}")
        
        return jsonify({
            "video_id": video_id,
            "status": "uploaded",
            "message": "Video upload request received successfully",
            "filename": filename,
            "user_id": user_id,
            "size": size,
            "created_at": task["created_at"]
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/list', methods=['GET'])
def list_videos():
    """List all videos endpoint - no authentication required"""
    try:
        videos = []
        
        # Get all videos from Firebase
        all_tasks = postgres_client.get_all_tasks() if hasattr(postgres_client, 'get_all_tasks') else []
        pending_tasks = postgres_client.get_pending_tasks() or []
        
        # If get_all_tasks is not available, try to get tasks by status
        if not all_tasks and hasattr(postgres_client, 'db') and postgres_client.db:
            try:
                # Get all documents from video_tasks collection
                docs = postgres_client.db.collection('video_tasks').stream()
                all_tasks = []
                for doc in docs:
                    task_data = doc.to_dict()
                    task_data['id'] = doc.id
                    all_tasks.append(task_data)
            except Exception as e:
                print(f"Error getting all tasks: {e}")
                all_tasks = pending_tasks  # Fallback to pending tasks
        
        # Convert Firebase tasks to API format
        for task in all_tasks:
            videos.append({
                "id": task.get("id", "unknown"),
                "filename": task.get("filename", "unknown"),
                "status": task.get("status", "unknown"),
                "created_at": task.get("upload_date", task.get("created_at", "")),
                "updated_at": task.get("processing_end", task.get("updated_at", "")),
                "size": task.get("size", 0),
                "user_id": task.get("user_id", ""),
                "user_email": task.get("user_email", ""),
                "pdf_url": task.get("pdf_url", "")
            })
        
        return jsonify({
            "videos": videos,
            "total": len(videos),
            "timestamp": datetime.datetime.now().isoformat(),
            "source": "Firebase"
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "source": "Firebase"}), 500

@app.route('/list/<user_id>', methods=['GET'])
def list_videos_by_user(user_id):
    """List videos for specific user - no authentication required"""
    try:
        videos = []
        
        # Filter videos by user_id from local storage
        for video_id, task in tasks_storage.items():
            if task.get("user_id") == user_id:
                videos.append({
                    "id": task["id"],
                    "filename": task["filename"],
                    "status": task["status"],
                    "created_at": task["created_at"],
                    "updated_at": task["updated_at"],
                    "size": task["size"],
                    "user_id": task["user_id"],
                    "user_email": task["user_email"]
                })
        
        return jsonify({
            "videos": videos,
            "total": len(videos),
            "user_id": user_id,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download/<video_id>.pdf', methods=['GET'])
def download_pdf(video_id):
    """Download PDF endpoint - no authentication required"""
    try:
        # Check if video exists in our storage
        task = tasks_storage.get(video_id)
        if not task:
            return jsonify({
                "error": f"Video {video_id} not found",
                "message": "Video must be uploaded first using POST /upload"
            }), 404
        
        # Look for generated PDF in local directory
        pdf_path = Path(f"{video_id}.pdf")
        if pdf_path.exists():
            return send_file(
                str(pdf_path.absolute()),
                as_attachment=True,
                download_name=f"{video_id}.pdf",
                mimetype='application/pdf'
            )
        
        # If no local PDF, return info about status
        return jsonify({
            "error": "PDF not ready",
            "message": f"PDF for video {video_id} has not been generated yet",
            "video_id": video_id,
            "status": task.get("status", "unknown"),
            "suggestion": "Use POST /process/{video_id} to generate PDF"
        }), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/process/<video_id>', methods=['POST'])
def process_video(video_id):
    """Process video to generate PDF - REAL PROCESSING, NO MOCKS"""
    try:
        # Check if video exists
        task = tasks_storage.get(video_id)
        if not task:
            return jsonify({
                "error": f"Video {video_id} not found",
                "message": "Video must be uploaded first using POST /upload"
            }), 404
        
        # Check if we have a video file to process
        video_path = Path(f"{video_id}.mp4")
        if not video_path.exists():
            return jsonify({
                "error": "Video file not found",
                "message": f"Video file {video_id}.mp4 not found. Use POST /generate-pdf to upload video file first.",
                "suggestion": "Upload video file using /generate-pdf endpoint"
            }), 404
        
        # Start REAL background processing
        print(f"🚀 Starting REAL processing thread for {video_id}")
        processing_thread = threading.Thread(
            target=real_video_processing, 
            args=(video_id, video_path)
        )
        processing_thread.daemon = True
        processing_thread.start()
        
        # Schedule cleanup of the local video file (PDF cleanup handled in processing)
        def delayed_cleanup():
            import time
            time.sleep(60)  # Wait 1 minute for processing to start
            try:
                if video_path.exists():
                    video_path.unlink()
                    print(f"🧹 Cleaned up local video: {video_path}")
            except Exception as e:
                print(f"⚠️ Failed to cleanup local video: {e}")
        
        cleanup_thread = threading.Thread(target=delayed_cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        return jsonify({
            "video_id": video_id,
            "status": "processing",
            "message": "REAL video processing started in background",
            "timestamp": datetime.datetime.now().isoformat(),
            "note": "This is REAL processing - PDF will be generated using actual worker logic",
            "check_status": f"GET /status/{video_id}"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/process-from-s3', methods=['POST'])
def process_video_from_s3():
    """Process video from S3 using metadata (called by backend)"""
    try:
        # Check if JSON metadata was provided
        if not request.is_json:
            return jsonify({"error": "JSON metadata required"}), 400
        
        data = request.get_json()
        video_id = data.get('video_id')
        user_id = data.get('user_id')
        filename = data.get('filename')
        s3_key = data.get('s3_key')
        
        if not all([video_id, user_id, filename, s3_key]):
            return jsonify({"error": "Missing required fields: video_id, user_id, filename, s3_key"}), 400
        
        print(f"📤 Processing S3 video: {video_id} for user: {user_id}")
        
        # Update task status to processing
        try:
            postgres_client.update_task_status(video_id, "processing")
            print(f"✅ Task status updated to processing: {video_id}")
        except Exception as e:
            print(f"⚠️ Failed to update task status: {e}")
        
        # Start background processing
        def background_s3_processing():
            try:
                print(f"🎬 Starting REAL enhanced processing for video {video_id}")
                print(f"   🔑 S3 Key: {s3_key}")
                print(f"   📁 Filename: {filename}")
                
                # Use REAL enhanced worker logic instead of mock
                from worker import EnhancedWorker
                worker = EnhancedWorker()
                success = worker.process_video(video_id, s3_key=s3_key, filename=filename)
                
                if success:
                    print(f"✅ REAL enhanced processing completed: {video_id}")
                else:
                    print(f"❌ REAL processing failed: {video_id}")
                    
            except Exception as e:
                print(f"❌ Real processing failed: {e}")
                postgres_client.update_task_status(video_id, "failed", error=str(e))
        
        import threading
        thread = threading.Thread(target=background_s3_processing)
        thread.start()
        
        return jsonify({
            "video_id": video_id,
            "status": "processing",
            "message": "Video processing started from S3"
        }), 201

    except Exception as e:
        print(f"❌ S3 processing error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf_direct():
    """Upload video file and start REAL PDF generation - no authentication required"""
    try:
        # Check if video file was uploaded
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({"error": "No video file selected"}), 400
        
        # Generate unique ID
        video_id = f"direct-{uuid.uuid4().hex[:8]}"
        
        # Save video file to local directory for processing
        video_path = Path(f"{video_id}.mp4")
        video_file.save(str(video_path))
        
        print(f"📁 Video saved to: {video_path.absolute()}")
        
        # Create task record in Firebase
        task = {
            "id": video_id,
            "filename": video_file.filename,
            "status": "uploaded",
            "upload_date": datetime.datetime.now().isoformat(),
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "size": video_path.stat().st_size,
            "user_id": "direct_upload",
            "user_email": "direct@thakii.dev"
        }
        
        # Save task to Firebase
        try:
            postgres_client.create_task(video_id, task)
            print(f"✅ Task created in Firebase: {video_id}")
        except Exception as e:
            print(f"⚠️ Failed to create task in Firebase: {e}")
            # Continue with local processing even if Firebase fails
        
        # Start REAL background processing immediately
        print(f"🚀 Starting REAL processing thread for uploaded video {video_id}")
        processing_thread = threading.Thread(
            target=real_video_processing, 
            args=(video_id, video_path)
        )
        processing_thread.daemon = True
        processing_thread.start()
        
        # Schedule cleanup of the uploaded video file (PDF cleanup handled in processing)
        def delayed_cleanup():
            import time
            time.sleep(60)  # Wait 1 minute for processing to start
            try:
                if video_path.exists():
                    video_path.unlink()
                    print(f"🧹 Cleaned up uploaded video: {video_path}")
            except Exception as e:
                print(f"⚠️ Failed to cleanup uploaded video: {e}")
        
        cleanup_thread = threading.Thread(target=delayed_cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
        # Return immediate response (async processing started)
        return jsonify({
            "video_id": video_id,
            "status": "processing",
            "message": "REAL PDF generation started in background",
            "filename": video_file.filename,
            "size": task["size"],
            "created_at": task["created_at"],
            "note": "This is REAL processing - check status with GET /status/{video_id}",
            "check_status": f"GET /status/{video_id}"
        }), 201
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download/<user_id>/<video_id>.pdf', methods=['GET'])
def download_pdf_by_user(user_id, video_id):
    """Download PDF for specific user - no authentication required"""
    try:
        # Check if video exists and belongs to user
        task = tasks_storage.get(video_id)
        if not task:
            return jsonify({
                "error": f"Video {video_id} not found",
                "message": "Video must be uploaded first using POST /upload"
            }), 404
        
        # Check if video belongs to the specified user
        if task.get("user_id") != user_id:
            return jsonify({
                "error": f"Video {video_id} not found for user {user_id}",
                "message": "Video does not belong to this user"
            }), 404
        
        # Look for generated PDF in local directory
        pdf_path = Path(f"{video_id}.pdf")
        if pdf_path.exists():
            return send_file(
                str(pdf_path.absolute()),
                as_attachment=True,
                download_name=f"{video_id}.pdf",
                mimetype='application/pdf'
            )
        
        # If no local PDF, return info about status
        return jsonify({
            "error": "PDF not ready",
            "message": f"PDF for video {video_id} has not been generated yet",
            "video_id": video_id,
            "user_id": user_id,
            "status": task.get("status", "unknown"),
            "suggestion": "Use POST /process/{video_id} to generate PDF"
        }), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status/<video_id>', methods=['GET'])
def get_video_status(video_id):
    """Get REAL video processing status from Firebase - no authentication required"""
    try:
        # Get task from Firebase
        task = postgres_client.get_task_details(video_id)
        if not task:
            return jsonify({"error": f"Video {video_id} not found"}), 404
        
        status_response = {
            "video_id": video_id,
            "status": task.get("status"),
            "filename": task.get("filename"),
            "created_at": task.get("upload_date", task.get("created_at")),
            "updated_at": task.get("processing_end", task.get("updated_at")),
            "size": task.get("size", 0),
            "user_id": task.get("user_id", ""),
            "user_email": task.get("user_email", "")
        }
        
        # Add error details if processing failed
        if task.get("status") == "failed" and "error" in task:
            status_response["error"] = task["error"]
        
        # Add PDF details if completed
        if task.get("status") == "completed" and task.get("pdf_url"):
            status_response["pdf_url"] = task["pdf_url"]
            status_response["pdf_ready"] = True
            status_response["download_url"] = f"/download/{video_id}.pdf"
        else:
            status_response["pdf_ready"] = False
        
        return jsonify(status_response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/', methods=['GET'])
def api_info():
    """API information endpoint"""
    return jsonify({
        "service": "Thakii Worker Service API",
        "version": "1.0",
        "endpoints": {
            "GET /health": "Service health check",
            "POST /upload": "Upload video metadata (requires user_id)",
            "GET /list": "List all uploaded videos",
            "GET /list/<user_id>": "List videos for specific user",
            "POST /process/<video_id>": "Process specific video",
            "GET /status/<video_id>": "Get video processing status",
            "GET /download/<video_id>.pdf": "Download any PDF (generic)",
            "GET /download/<user_id>/<video_id>.pdf": "Download PDF for specific user",
            "POST /generate-pdf": "Upload video file and start PDF generation"
        },
        "documentation": "All endpoints work without authentication",
        "timestamp": datetime.datetime.now().isoformat(),
        "total_videos": len(tasks_storage)
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "message": "The requested URL was not found on this server",
        "available_endpoints": [
            "GET /",
            "GET /health",
            "POST /upload", 
            "GET /list",
            "POST /process/<video_id>",
            "GET /download/<video_id>.pdf",
            "POST /generate-pdf"
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred",
        "timestamp": datetime.datetime.now().isoformat()
    }), 500

# =============================================================================
# LOG VIEWING ENDPOINTS
# =============================================================================

@app.route('/logs', methods=['GET'])
def list_logs():
    """List available log dates"""
    if not LOGGING_ENABLED:
        return jsonify({"error": "Logging system not available"}), 503
    
    try:
        from core.log_viewer import LogViewer
        viewer = LogViewer()
        dates = viewer.list_available_dates()
        
        return jsonify({
            "available_dates": dates,
            "total_dates": len(dates),
            "log_directory": "logs/YYYY/MM/DD/",
            "endpoints": {
                "list_dates": "GET /logs",
                "view_logs": "GET /logs/<date>?type=api&limit=100",
                "search_logs": "GET /logs/search?q=<query>&days=7",
                "error_summary": "GET /logs/errors/summary?days=7",
                "request_stats": "GET /logs/stats/<date>"
            }
        })
    except Exception as e:
        if LOGGING_ENABLED:
            log_error(e, endpoint="/logs")
        return jsonify({"error": str(e)}), 500

@app.route('/logs/<date>', methods=['GET'])
def view_logs_for_date(date):
    """View logs for a specific date"""
    if not LOGGING_ENABLED:
        return jsonify({"error": "Logging system not available"}), 503
    
    try:
        from core.log_viewer import LogViewer
        viewer = LogViewer()
        
        # Handle 'today' as a special case
        if date == 'today':
            date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        log_type = request.args.get('type', 'api')
        limit = int(request.args.get('limit', 100))
        level = request.args.get('level', None)
        
        logs = list(viewer.read_logs(date, log_type, limit, level))
        
        return jsonify({
            "date": date,
            "log_type": log_type,
            "count": len(logs),
            "limit": limit,
            "level_filter": level,
            "logs": logs
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        if LOGGING_ENABLED:
            log_error(e, endpoint=f"/logs/{date}")
        return jsonify({"error": str(e)}), 500

@app.route('/logs/search', methods=['GET'])
def search_logs():
    """Search logs for a query"""
    if not LOGGING_ENABLED:
        return jsonify({"error": "Logging system not available"}), 503
    
    try:
        from core.log_viewer import LogViewer
        viewer = LogViewer()
        
        query = request.args.get('q', '')
        if not query:
            return jsonify({"error": "Query parameter 'q' is required"}), 400
        
        date = request.args.get('date', None)
        days_back = int(request.args.get('days', 7))
        
        results = list(viewer.search_logs(query, date, days_back=days_back))[:200]  # Limit results
        
        return jsonify({
            "query": query,
            "date": date,
            "days_searched": days_back,
            "results_count": len(results),
            "results": results
        })
    except Exception as e:
        if LOGGING_ENABLED:
            log_error(e, endpoint="/logs/search")
        return jsonify({"error": str(e)}), 500

@app.route('/logs/errors/summary', methods=['GET'])
def error_summary():
    """Get error summary"""
    if not LOGGING_ENABLED:
        return jsonify({"error": "Logging system not available"}), 503
    
    try:
        from core.log_viewer import LogViewer
        viewer = LogViewer()
        
        date = request.args.get('date', None)
        days = int(request.args.get('days', 7))
        
        summary = viewer.get_error_summary(date, days)
        
        return jsonify(summary)
    except Exception as e:
        if LOGGING_ENABLED:
            log_error(e, endpoint="/logs/errors/summary")
        return jsonify({"error": str(e)}), 500

@app.route('/logs/stats/<date>', methods=['GET'])
def request_stats(date):
    """Get request statistics for a date"""
    if not LOGGING_ENABLED:
        return jsonify({"error": "Logging system not available"}), 503
    
    try:
        from core.log_viewer import LogViewer
        viewer = LogViewer()
        
        # Handle 'today' as a special case
        if date == 'today':
            date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        stats = viewer.get_request_stats(date)
        
        return jsonify(stats)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        if LOGGING_ENABLED:
            log_error(e, endpoint=f"/logs/stats/{date}")
        return jsonify({"error": str(e)}), 500

@app.route('/logs/video/<video_id>', methods=['GET'])
def get_video_logs(video_id):
    """Get all logs for a specific video ID"""
    if not LOGGING_ENABLED:
        return jsonify({"error": "Logging system not available"}), 503
    
    try:
        from core.log_viewer import LogViewer
        viewer = LogViewer()
        
        days_back = int(request.args.get('days', 30))
        logs = viewer.get_video_logs(video_id, days_back)
        
        return jsonify({
            "video_id": video_id,
            "days_searched": days_back,
            "logs_count": len(logs),
            "logs": logs
        })
    except Exception as e:
        if LOGGING_ENABLED:
            log_error(e, endpoint=f"/logs/video/{video_id}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Thakii Worker Service API Server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    args = parser.parse_args()
    
    port = args.port
    
    print("🚀 Starting Thakii Worker Service API Server")
    print("=" * 50)
    print("🔓 No authentication required!")
    print(f"📡 Server will be available at: http://localhost:{port}")
    print(f"🏥 Health check: http://localhost:{port}/health")
    print(f"📖 API info: http://localhost:{port}/")
    print("=" * 50)
    
    # Start the server
    app.run(
        host='127.0.0.1',
        port=port,
        debug=False
    )

@app.route('/deploy', methods=['POST'])
def deploy_webhook():
    """Deployment webhook - triggers git pull and service restart"""
    try:
        import subprocess
        import os
        from pathlib import Path
        
        print("🚀 Deployment webhook triggered")
        
        # Get current directory (should be worker service directory)
        current_dir = Path.cwd()
        print(f"📁 Working directory: {current_dir}")
        
        # Pull latest changes
        print("📥 Pulling latest changes from GitHub...")
        result = subprocess.run(['git', 'pull', 'origin', 'main'], 
                              capture_output=True, text=True, cwd=current_dir)
        
        if result.returncode == 0:
            print(f"✅ Git pull successful: {result.stdout}")
            
            # Kill existing worker processes
            print("🔄 Stopping existing worker processes...")
            subprocess.run(['pkill', '-f', 'python.*worker'], check=False)
            
            # Wait a moment
            import time
            time.sleep(2)
            
            # Start worker service in background
            print("🚀 Starting worker service...")
            subprocess.Popen(['python3', 'worker.py', '--process-all'], 
                           cwd=current_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            return {
                "status": "success", 
                "message": "Deployment completed successfully",
                "git_output": result.stdout,
                "timestamp": time.time()
            }
        else:
            print(f"❌ Git pull failed: {result.stderr}")
            return {
                "status": "error", 
                "message": f"Git pull failed: {result.stderr}"
            }, 500
            
    except Exception as e:
        print(f"💥 Deployment error: {e}")
        return {
            "status": "error", 
            "message": f"Deployment failed: {str(e)}"
        }, 500

@app.route('/status', methods=['GET'])
def deployment_status():
    """Check deployment and service status"""
    try:
        import subprocess
        import os
        from pathlib import Path
        
        current_dir = Path.cwd()
        
        # Get git status
        git_result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, cwd=current_dir)
        
        # Check if worker is running
        worker_check = subprocess.run(['pgrep', '-f', 'python.*worker'], 
                                    capture_output=True, text=True)
        
        return {
            "git_commit": git_result.stdout.strip() if git_result.returncode == 0 else "unknown",
            "worker_running": worker_check.returncode == 0,
            "worker_processes": len(worker_check.stdout.strip().split('\n')) if worker_check.stdout.strip() else 0,
            "directory": str(current_dir),
            "timestamp": time.time()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }, 500
