#!/usr/bin/env python3
"""
Thakii Worker Service - Local API Server (No Database Required)
Simplified version for local testing without PostgreSQL or Firebase
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

# Load environment variables from local.env
load_dotenv('local.env')

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.main import CommandLineArgRunner
    print("✅ Successfully imported src.main.CommandLineArgRunner")
    main_runner = CommandLineArgRunner()
except ImportError as e:
    print(f"⚠️ Warning: Could not import src.main - {e}")
    main_runner = None

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Flask-RESTX API with Swagger documentation
api = Api(
    app,
    version='1.0',
    title='Thakii Worker Service API (Local)',
    description='Video processing API for converting lectures to PDF transcripts (Local Development)',
    doc='/swagger/',  # Swagger UI will be available at /swagger/
    prefix='/api/v1'
)

# Local task storage for API server
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
    'message': fields.String(description='Response message')
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
    'error': fields.String(description='Error message (if failed)')
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
    'pdf_url': fields.String(description='PDF download URL')
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
    'endpoints': fields.Raw(description='Available endpoints')
})

error_model = api.model('Error', {
    'error': fields.String(description='Error message'),
    'message': fields.String(description='Detailed error description'),
    'timestamp': fields.String(description='Error timestamp')
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
    'size': fields.Integer(description='File size in bytes')
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
        # Update status in tasks_storage
        if video_id in tasks_storage:
            tasks_storage[video_id]["status"] = "processing"
            tasks_storage[video_id]["updated_at"] = datetime.datetime.now().isoformat()
            print(f"✅ Updated status to processing: {video_id}")
        
        # Method 1: Try to use imported main runner
        if main_runner:
            print(f"📚 Using imported CommandLineArgRunner")
            # Set up arguments for main runner
            output_pdf = f"{video_id}.pdf"
            args = [str(video_path), "-o", output_pdf]
            
            # Parse and run
            print(f"🔧 Args: {args}")
            main_runner.run(args)
            
            pdf_path = Path(output_pdf)
            if not pdf_path.exists():
                raise Exception("PDF was not generated by main runner")
        else:
            # Method 2: Direct subprocess call to src/main.py
            print(f"🔧 Using subprocess call to src/main.py")
            output_pdf = f"{video_id}.pdf"
            result = subprocess.run([
                sys.executable, '-m', 'src.main', str(video_path), '-o', output_pdf
            ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
            
            if result.returncode != 0:
                raise Exception(f"Main process failed: {result.stderr}")
            
            # Look for generated PDF
            pdf_path = Path(output_pdf)
            if not pdf_path.exists():
                raise Exception("PDF was not generated by main process")
        
        # Update status to completed
        if video_id in tasks_storage:
            tasks_storage[video_id]["status"] = "completed"
            tasks_storage[video_id]["updated_at"] = datetime.datetime.now().isoformat()
            tasks_storage[video_id]["pdf_url"] = f"local://{pdf_path}"
            print(f"✅ Updated status to completed: {video_id}")
        
        print(f"✅ REAL processing completed for video {video_id}")
        
    except Exception as e:
        print(f"❌ REAL processing failed for video {video_id}: {str(e)}")
        # Update status to failed
        if video_id in tasks_storage:
            tasks_storage[video_id]["status"] = "failed"
            tasks_storage[video_id]["updated_at"] = datetime.datetime.now().isoformat()
            tasks_storage[video_id]["error"] = str(e)
            print(f"✅ Updated status to failed: {video_id}")

@health_ns.route('/')
class HealthCheck(Resource):
    @health_ns.doc('health_check')
    @health_ns.marshal_with(health_model)
    def get(self):
        """Health check endpoint - returns service status and available endpoints"""
        return {
            "database": "Local",
            "service": "Thakii Lecture2PDF Service (Local)",
            "status": "healthy",
            "storage": "Local",
            "timestamp": datetime.datetime.now().isoformat(),
            "api_version": "1.0",
            "endpoints": {
                "upload": "/api/v1/videos/upload",
                "list": "/api/v1/videos/list", 
                "download": "/api/v1/videos/download/{video_id}.pdf",
                "process": "/api/v1/videos/process/{video_id}",
                "status": "/api/v1/videos/status/{video_id}",
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
            
            return {
                "video_id": video_id,
                "status": "uploaded",
                "message": "Video upload request received successfully",
                "filename": filename,
                "created_at": task["created_at"]
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
            
            # Get all videos from local storage
            for video_id, task in tasks_storage.items():
                videos.append({
                    "id": task.get("id", "unknown"),
                    "filename": task.get("filename", "unknown"),
                    "status": task.get("status", "unknown"),
                    "created_at": task.get("created_at", ""),
                    "updated_at": task.get("updated_at", ""),
                    "size": task.get("size", 0),
                    "user_id": task.get("user_id", ""),
                    "user_email": task.get("user_email", ""),
                    "pdf_url": task.get("pdf_url", "")
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
    @videos_ns.expect(upload_parser)
    @videos_ns.response(201, 'Processing Started', processing_response_model)
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
                "created_at": datetime.datetime.now().isoformat(),
                "updated_at": datetime.datetime.now().isoformat(),
                "size": video_path.stat().st_size,
                "user_id": "direct_upload",
                "user_email": "direct@thakii.dev"
            }
            
            # Store task in memory
            tasks_storage[video_id] = task
            
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
                "size": task["size"]
            }, 201
                    
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.datetime.now().isoformat()}, 500

@videos_ns.route('/status/<string:video_id>')
class VideoStatus(Resource):
    @videos_ns.doc('get_video_status')
    @videos_ns.marshal_with(video_status_model)
    @videos_ns.response(404, 'Video Not Found', error_model)
    @videos_ns.response(500, 'Internal Server Error', error_model)
    def get(self, video_id):
        """Get video processing status"""
        try:
            # Get task from local storage
            task = tasks_storage.get(video_id)
            if not task:
                return {"error": f"Video {video_id} not found", "timestamp": datetime.datetime.now().isoformat()}, 404
            
            status_response = {
                "video_id": video_id,
                "status": task.get("status"),
                "filename": task.get("filename"),
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
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
            
            return status_response
            
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.datetime.now().isoformat()}, 500

@videos_ns.route('/process/<string:video_id>')
class ProcessVideo(Resource):
    @videos_ns.doc('process_video')
    @videos_ns.response(200, 'Processing Started', processing_response_model)
    @videos_ns.response(404, 'Video Not Found', error_model)
    @videos_ns.response(500, 'Internal Server Error', error_model)
    def post(self, video_id):
        """Process video to generate PDF - REAL PROCESSING, NO MOCKS"""
        try:
            # Check if video exists
            task = tasks_storage.get(video_id)
            if not task:
                return {
                    "error": f"Video {video_id} not found",
                    "message": "Video must be uploaded first using POST /upload",
                    "timestamp": datetime.datetime.now().isoformat()
                }, 404
            
            # Check if we have a video file to process
            video_path = Path(f"{video_id}.mp4")
            if not video_path.exists():
                return {
                    "error": "Video file not found",
                    "message": f"Video file {video_id}.mp4 not found. Use POST /generate-pdf to upload video file first.",
                    "suggestion": "Upload video file using /generate-pdf endpoint",
                    "timestamp": datetime.datetime.now().isoformat()
                }, 404
            
            # Start REAL background processing
            print(f"🚀 Starting REAL processing thread for {video_id}")
            processing_thread = threading.Thread(
                target=real_video_processing, 
                args=(video_id, video_path)
            )
            processing_thread.daemon = True
            processing_thread.start()
            
            return {
                "video_id": video_id,
                "status": "processing",
                "message": "REAL video processing started in background",
                "filename": task.get("filename", ""),
                "created_at": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.datetime.now().isoformat()}, 500

@videos_ns.route('/download/<string:video_id>.pdf')
class DownloadPDF(Resource):
    @videos_ns.doc('download_pdf')
    @videos_ns.response(200, 'PDF file download')
    @videos_ns.response(404, 'PDF Not Found', error_model)
    @videos_ns.response(500, 'Internal Server Error', error_model)
    def get(self, video_id):
        """Download generated PDF file"""
        try:
            # Check if video exists in our storage
            task = tasks_storage.get(video_id)
            if not task:
                return {
                    "error": f"Video {video_id} not found",
                    "message": "Video must be uploaded first using POST /upload",
                    "timestamp": datetime.datetime.now().isoformat()
                }, 404
            
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
            return {
                "error": "PDF not ready",
                "message": f"PDF for video {video_id} has not been generated yet",
                "video_id": video_id,
                "status": task.get("status", "unknown"),
                "suggestion": "Use POST /process/{video_id} to generate PDF",
                "timestamp": datetime.datetime.now().isoformat()
            }, 404
            
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.datetime.now().isoformat()}, 500

@app.route('/download/<video_id>.pdf', methods=['GET'])
def download_pdf(video_id):
    """Download PDF endpoint"""
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

@app.route('/status/<video_id>', methods=['GET'])
def get_video_status(video_id):
    """Get video processing status"""
    try:
        # Get task from local storage
        task = tasks_storage.get(video_id)
        if not task:
            return jsonify({"error": f"Video {video_id} not found"}), 404
        
        status_response = {
            "video_id": video_id,
            "status": task.get("status"),
            "filename": task.get("filename"),
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
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

@app.route('/')
def api_root():
    """Root endpoint - redirects to Swagger documentation"""
    from flask import redirect
    return redirect('/swagger/')

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "message": "The requested URL was not found on this server",
        "available_endpoints": [
            "GET /",
            "GET /api/v1/health/",
            "POST /api/v1/videos/upload", 
            "GET /api/v1/videos/list",
            "POST /api/v1/videos/process/<video_id>",
            "GET /api/v1/videos/status/<video_id>",
            "GET /api/v1/videos/download/<video_id>.pdf",
            "POST /api/v1/videos/generate-pdf",
            "GET /swagger/"
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
    parser = argparse.ArgumentParser(description='Thakii Worker Service API Server (Local)')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    args = parser.parse_args()
    
    port = args.port
    
    print("🚀 Starting Thakii Worker Service API Server (Local Development)")
    print("=" * 50)
    print("🔓 No authentication required!")
    print(f"📡 Server will be available at: http://localhost:{port}")
    print(f"🏥 Health check: http://localhost:{port}/api/v1/health")
    print(f"📖 API info: http://localhost:{port}/swagger/")
    print("=" * 50)
    
    # Start the server
    app.run(
        host='127.0.0.1',
        port=port,
        debug=True
    )
