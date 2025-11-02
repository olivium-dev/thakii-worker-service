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
from flask_restx import Api, Resource, fields, Namespace
from flask_cors import CORS
import tempfile
import subprocess
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.main import CommandLineArgRunner
    print("✅ Successfully imported src.main.CommandLineArgRunner")
    main_runner = CommandLineArgRunner()
except ImportError as e:
    print(f"⚠️ Warning: Could not import src.main - {e}")
    main_runner = None

class PrefixMiddleware(object):
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix.rstrip('/')  # Remove trailing slash

    def __call__(self, environ, start_response):
        path_info = environ['PATH_INFO']
        
        if self.prefix:
            # Check if the path starts with our prefix
            if path_info.startswith(self.prefix):
                # Remove the prefix from PATH_INFO
                new_path = path_info[len(self.prefix):]
                # Ensure it starts with /
                if not new_path.startswith('/'):
                    new_path = '/' + new_path
                environ['PATH_INFO'] = new_path
                environ['SCRIPT_NAME'] = self.prefix
                return self.app(environ, start_response)
            else:
                # Path doesn't match prefix, return 404
                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                return [b'This url does not belong to the app.']
        else:
            # No prefix, pass through
            return self.app(environ, start_response)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Apply PATH_PREFIX if defined
path_prefix = os.getenv('PATH_PREFIX', '')
print(f"🔧 PATH_PREFIX environment variable: '{path_prefix}'", flush=True)
if path_prefix:
    print(f"🔗 Applying path prefix middleware: {path_prefix}")
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=path_prefix)
    print(f"✅ PrefixMiddleware applied with prefix: {path_prefix}")
else:
    print("⚠️ No PATH_PREFIX defined, API will be served at root path")

api = Api(
    app,
    version='1.0',
    title='Thakii Worker Service API',
    description='Video processing API for converting lectures to PDF transcripts',
    doc='/swagger/',  # Swagger UI will be available at /swagger/
    prefix='/api/v1'
)

# Import Firebase integration (REQUIRED)
from core.postgres_integration import postgres_client
print("✅ Firebase integration loaded - Local storage disabled")

# Import Queue Manager for Redis integration
from core.queue_manager import queue_manager

# Local task storage for API server (fallback when Firebase unavailable)
tasks_storage = {}

# Create API namespaces
health_ns = Namespace('health', description='Health check operations')
videos_ns = Namespace('videos', description='Video processing operations')
api.add_namespace(health_ns, path='/health')
api.add_namespace(videos_ns, path='/videos')

# Swagger models
video_upload_model = api.model('VideoUpload', {
    'filename': fields.String(required=True, description='Video filename'),
    'user_id': fields.String(required=True, description='User ID'),
    'size': fields.Integer(description='File size in bytes'),
    'content_type': fields.String(description='MIME type', default='video/mp4'),
    'user_email': fields.String(description='User email address')
})

video_response_model = api.model('VideoResponse', {
    'video_id': fields.String(description='Unique video identifier'),
    'status': fields.String(description='Processing status', enum=['uploaded', 'processing', 'completed', 'failed']),
    'filename': fields.String(description='Original filename'),
    'created_at': fields.String(description='Upload timestamp'),
    'message': fields.String(description='Response message'),
    'progress_percentage': fields.Float(description='Processing progress percentage (0-100)')
})

video_status_model = api.model('VideoStatus', {
    'video_id': fields.String(description='Unique video identifier'),
    'status': fields.String(description='Processing status', enum=['uploaded', 'processing', 'completed', 'failed']),
    'filename': fields.String(description='Original filename'),
    'created_at': fields.String(description='Creation timestamp'),
    'updated_at': fields.String(description='Last update timestamp'),
    'size': fields.Integer(description='File size in bytes'),
    'user_id': fields.String(description='User ID'),
    'user_email': fields.String(description='User email'),
    'pdf_ready': fields.Boolean(description='Whether PDF is ready for download'),
    'pdf_url': fields.String(description='PDF download URL (if ready)'),
    'download_url': fields.String(description='Direct download URL (if ready)'),
    'error': fields.String(description='Error message (if failed)'),
    'progress_percentage': fields.Float(description='Processing progress percentage (0-100)')
})

video_detail_model = api.model('Video', {
    'id': fields.String(description='Video ID'),
    'filename': fields.String(description='Filename'),
    'status': fields.String(description='Processing status', enum=['uploaded', 'processing', 'completed', 'failed']),
    'created_at': fields.String(description='Creation date'),
    'updated_at': fields.String(description='Last update'),
    'size': fields.Integer(description='File size in bytes'),
    'user_id': fields.String(description='User ID'),
    'user_email': fields.String(description='User email'),
    'pdf_url': fields.String(description='PDF download URL'),
    'progress_percentage': fields.Float(description='Processing progress percentage (0-100)')
})

video_list_model = api.model('VideoList', {
    'videos': fields.List(fields.Nested(video_detail_model)),
    'total': fields.Integer(description='Total number of videos'),
    'timestamp': fields.String(description='Response timestamp')
})

health_model = api.model('Health', {
    'service': fields.String(description='Service name'),
    'status': fields.String(description='Service status'),
    'timestamp': fields.String(description='Current timestamp'),
    'api_version': fields.String(description='API version'),
    'database': fields.String(description='Database status'),
    'storage': fields.String(description='Storage status'),
    'redis_queue': fields.String(description='Redis queue status (disabled/available/unavailable)'),
    'endpoints': fields.Raw(description='Available endpoints')
})

# File upload parser for multipart/form-data
from werkzeug.datastructures import FileStorage
upload_parser = api.parser()
upload_parser.add_argument('video', location='files', type=FileStorage, required=True, help='Video file to process')

# Processing response model for generate-pdf endpoint
processing_response_model = api.model('ProcessingResponse', {
    'video_id': fields.String(description='Unique video identifier'),
    'status': fields.String(description='Processing status', enum=['processing']),
    'message': fields.String(description='Processing message'),
    'filename': fields.String(description='Original filename'),
    'created_at': fields.String(description='Upload timestamp'),
    'size': fields.Integer(description='File size in bytes'),
    'progress_percentage': fields.Float(description='Processing progress percentage (0-100)')
})

error_model = api.model('Error', {
    'error': fields.String(description='Error message'),
    'message': fields.String(description='Detailed error description'),
    'timestamp': fields.String(description='Error timestamp')
})

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
    Integrates with actual src/main.py logic
    """
    output_pdf = None
    try:
        print(f"🎬 Starting REAL processing for video {video_id}")
        # Update status in Firebase with 0% progress
        try:
            postgres_client.update_task_status(video_id, "processing", progress_percentage=0.0)
            print(f"✅ Updated Firebase status to processing: {video_id}")
        except Exception as e:
            print(f"⚠️ Failed to update Firebase status: {e}")
        
        # Update progress to 10% - Starting processing
        try:
            postgres_client.update_task_status(video_id, "processing", progress_percentage=10.0)
        except Exception as e:
            print(f"⚠️ Failed to update progress: {e}")
            
        # Method 1: Try to use imported main runner
        if main_runner:
            print(f"📚 Using imported CommandLineArgRunner")
            # Set up arguments for main runner
            output_pdf = f"{video_id}.pdf"
            args = [str(video_path), "-o", output_pdf]
            
            # Update progress to 20% - Starting subtitle generation
            try:
                postgres_client.update_task_status(video_id, "processing", progress_percentage=20.0)
            except Exception as e:
                print(f"⚠️ Failed to update progress: {e}")
                
            # Parse and run
            print(f"🔧 Args: {args}")
            main_runner.run(args)
            
            # Update progress to 80% - PDF generation completed
            try:
                postgres_client.update_task_status(video_id, "processing", progress_percentage=80.0)
            except Exception as e:
                print(f"⚠️ Failed to update progress: {e}")
            
            pdf_path = Path(output_pdf)
            if not pdf_path.exists():
                raise Exception("PDF was not generated by main runner")
        else:
            # Method 2: Direct subprocess call to src/main.py
            print(f"🔧 Using subprocess call to src/main.py")
            output_pdf = f"{video_id}.pdf"
            
            # Update progress to 20% - Starting subtitle generation
            try:
                postgres_client.update_task_status(video_id, "processing", progress_percentage=20.0)
            except Exception as e:
                print(f"⚠️ Failed to update progress: {e}")
                
            result = subprocess.run([
                sys.executable, '-m', 'src.main', str(video_path), '-o', output_pdf
            ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
            
            # Update progress to 80% - PDF generation completed
            try:
                postgres_client.update_task_status(video_id, "processing", progress_percentage=80.0)
            except Exception as e:
                print(f"⚠️ Failed to update progress: {e}")
                
            if result.returncode != 0:
                raise Exception(f"Main process failed: {result.stderr}")
            
            # Look for generated PDF
            pdf_path = Path(output_pdf)
            if not pdf_path.exists():
                raise Exception("PDF was not generated by main process")
        
        # Update progress to 90% - Finalizing
        try:
            postgres_client.update_task_status(video_id, "processing", progress_percentage=90.0)
        except Exception as e:
            print(f"⚠️ Failed to update progress: {e}")
            
        # Update status to completed with 100% progress
        try:
            postgres_client.update_task_status(video_id, "completed", pdf_url=f"local://{pdf_path}", progress_percentage=100.0)
            print(f"✅ Updated Firebase status to completed: {video_id}")
        except Exception as e:
            print(f"⚠️ Failed to update Firebase status: {e}")
        
        print(f"✅ REAL processing completed for video {video_id}")
        
    except Exception as e:
        print(f"❌ REAL processing failed for video {video_id}: {str(e)}")
        # Update status in Firebase
        try:
            postgres_client.update_task_status(video_id, "failed", error=str(e))
            print(f"✅ Updated Firebase status to failed: {video_id}")
        except Exception as e2:
            print(f"⚠️ Failed to update Firebase status: {e2}")
    finally:
        # Always clean up local files after processing (success or failure)
        cleanup_local_files(video_id)

@health_ns.route('/')
class HealthCheck(Resource):
    @health_ns.doc('health_check')
    @health_ns.marshal_with(health_model)
    def get(self):
        """Health check endpoint - returns service status and available endpoints"""
        redis_status = "disabled"
        if queue_manager.enabled:
            redis_status = "available" if queue_manager.is_available() else "unavailable"
        
        return {
            "database": "Local",
            "service": "Thakii Lecture2PDF Service",
            "status": "healthy",
            "storage": "Local",
            "timestamp": datetime.datetime.now().isoformat(),
            "api_version": "1.0",
            "redis_queue": redis_status,
            "endpoints": {
                "upload": "/api/v1/videos/upload",
                "list": "/api/v1/videos/list", 
                "download": "/api/v1/videos/download/{video_id}.pdf",
                "process": "/api/v1/videos/process/{video_id}",
                "generate": "/api/v1/videos/generate-pdf",
                "swagger": "/swagger/"
            }
        }

@videos_ns.route('/upload')
class VideoUpload(Resource):
    @videos_ns.doc('upload_video')
    @videos_ns.expect(video_upload_model)
    @videos_ns.marshal_with(video_response_model, code=201)
    @videos_ns.response(400, 'Bad Request', error_model)
    @videos_ns.response(500, 'Internal Server Error', error_model)
    def post(self):
        """Upload video metadata - creates a new video processing task"""
        try:
            data = request.get_json()
            
            if not data:
                return {"error": "No JSON data provided", "timestamp": datetime.datetime.now().isoformat()}, 400
            
            filename = data.get('filename')
            user_id = data.get('user_id')
            size = data.get('size', 0)
            content_type = data.get('content_type', 'video/mp4')
            user_email = data.get('user_email', 'anonymous@thakii.dev')
            
            if not filename:
                return {"error": "filename is required", "timestamp": datetime.datetime.now().isoformat()}, 400
            
            if not user_id:
                return {"error": "user_id is required", "timestamp": datetime.datetime.now().isoformat()}, 400
            
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
            
            return {
                "video_id": video_id,
                "status": "uploaded",
                "message": "Video upload request received successfully",
                "filename": filename,
                "created_at": task["created_at"],
                "progress_percentage": 0.0
            }, 201
            
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.datetime.now().isoformat()}, 500

@videos_ns.route('/list')
class VideoList(Resource):
    @videos_ns.doc('list_videos')
    @videos_ns.marshal_with(video_list_model)
    @videos_ns.response(500, 'Internal Server Error', error_model)
    def get(self):
        """List all videos - returns all video processing tasks"""
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
                progress = task.get("progress_percentage", 0.0)
                # Set progress to 100% if completed
                if task.get("status") == "completed":
                    progress = 100.0
                    
                videos.append({
                    "id": task.get("id", "unknown"),
                    "filename": task.get("filename", "unknown"),
                    "status": task.get("status", "unknown"),
                    "created_at": task.get("upload_date", task.get("created_at", "")),
                    "updated_at": task.get("processing_end", task.get("updated_at", "")),
                    "size": task.get("size", 0),
                    "user_id": task.get("user_id", ""),
                    "user_email": task.get("user_email", ""),
                    "pdf_url": task.get("pdf_url", ""),
                    "progress_percentage": progress
                })
            
            return {
                "videos": videos,
                "total": len(videos),
                "timestamp": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.datetime.now().isoformat()}, 500

@videos_ns.route('/generate-pdf')
class GeneratePDF(Resource):
    @videos_ns.doc('generate_pdf')
    @videos_ns.response(201, 'Processing Started', video_response_model)
    @videos_ns.response(400, 'Bad Request', error_model)
    @videos_ns.response(500, 'Internal Server Error', error_model)
    def post(self):
        """Upload video file and start PDF generation - accepts multipart/form-data with video file"""
        try:
            # Check if video file was uploaded
            if 'video' not in request.files:
                return {"error": "No video file provided", "timestamp": datetime.datetime.now().isoformat()}, 400
            
            video_file = request.files['video']
            if video_file.filename == '':
                return {"error": "No video file selected", "timestamp": datetime.datetime.now().isoformat()}, 400
            
            # Generate unique ID
            video_id = f"direct-{uuid.uuid4().hex[:8]}"
            
            # Save video file to local directory for processing
            video_path = Path(f"{video_id}.mp4")
            video_file.save(str(video_path))
            
            print(f"📁 Video saved to: {video_path.absolute()}")
            
            # Create task record
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
            
            # Start REAL background processing immediately
            print(f"🚀 Starting REAL processing thread for uploaded video {video_id}")
            processing_thread = threading.Thread(
                target=real_video_processing, 
                args=(video_id, video_path)
            )
            processing_thread.daemon = True
            processing_thread.start()
            
            return {
                "video_id": video_id,
                "status": "processing",
                "message": "PDF generation started in background",
                "filename": video_file.filename,
                "created_at": task["created_at"],
                "progress_percentage": 0.0
            }, 201
                    
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.datetime.now().isoformat()}, 500

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
        
        # Check if Redis queue is enabled
        if queue_manager.is_available():
            try:
                job_id = queue_manager.enqueue_video(
                    video_id=video_id,
                    s3_key=s3_key,
                    filename=filename,
                    user_id=user_id
                )
                return jsonify({
                    "video_id": video_id,
                    "status": "in_queue",
                    "message": "Video enqueued for processing",
                    "job_id": job_id
                }), 202
            except Exception as e:
                return jsonify({"error": f"Failed to enqueue: {str(e)}"}), 500
        else:
            # Legacy: Update database, let polling worker handle it
            print(f"📋 Redis disabled - {video_id} will be processed via polling")
            try:
                postgres_client.update_task_status(video_id, "in_queue")
                print(f"✅ Task status updated to in_queue: {video_id}")
            except Exception as e:
                print(f"⚠️ Failed to update task status: {e}")
            
            return jsonify({
                "video_id": video_id,
                "status": "in_queue",
                "message": "Video queued for processing (database polling)"
            }), 202

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
            "user_email": task.get("user_email", ""),
            "progress_percentage": task.get("progress_percentage", 0.0)
        }
        
        # Add error details if processing failed
        if task.get("status") == "failed" and "error" in task:
            status_response["error"] = task["error"]
        
        # Add PDF details if completed
        if task.get("status") == "completed" and task.get("pdf_url"):
            status_response["pdf_url"] = task["pdf_url"]
            status_response["pdf_ready"] = True
            status_response["download_url"] = f"/download/{video_id}.pdf"
            status_response["progress_percentage"] = 100.0
        else:
            status_response["pdf_ready"] = False
        
        return jsonify(status_response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def api_root():
    """Root endpoint - redirects to Swagger documentation"""
    from flask import redirect
    return redirect('/swagger/')

@api.route('/info')
class APIInfo(Resource):
    @api.doc('api_info')
    def get(self):
        """API information and statistics"""
        return {
            "service": "Thakii Worker Service API",
            "version": "1.0",
            "description": "Video processing API for converting lectures to PDF transcripts",
            "swagger_ui": "/swagger/",
            "endpoints": {
                "GET /api/v1/health/": "Service health check",
                "POST /api/v1/videos/upload": "Upload video metadata (requires user_id)",
                "GET /api/v1/videos/list": "List all uploaded videos",
                "POST /api/v1/videos/generate-pdf": "Upload video file and start PDF generation",
                "GET /swagger/": "Interactive API documentation"
            },
            "documentation": "All endpoints work without authentication",
            "timestamp": datetime.datetime.now().isoformat(),
            "total_videos": len(tasks_storage),
            "features": [
                "Real-time video processing",
                "Whisper AI speech recognition",
                "PDF transcript generation",
                "S3 cloud storage integration",
                "RESTful API with Swagger documentation"
            ]
        }

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
    
    # PATH_PREFIX middleware is already applied at app initialization
    
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
