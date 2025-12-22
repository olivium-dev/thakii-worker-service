#!/usr/bin/env python3
"""
Enhanced Logging Configuration for Thakii Worker Service API
Provides structured logging with request/response tracking and error handling
"""

import os
import logging
import logging.handlers
import json
import time
from datetime import datetime
from pathlib import Path
from flask import request, g
import functools

# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        if hasattr(record, 'video_id'):
            log_entry["video_id"] = record.video_id
        if hasattr(record, 'user_ip'):
            log_entry["user_ip"] = record.user_ip
        if hasattr(record, 'endpoint'):
            log_entry["endpoint"] = record.endpoint
        if hasattr(record, 'method'):
            log_entry["method"] = record.method
        if hasattr(record, 'status_code'):
            log_entry["status_code"] = record.status_code
        if hasattr(record, 'response_time'):
            log_entry["response_time_ms"] = record.response_time
            
        return json.dumps(log_entry)

def setup_logging(app, log_level=None):
    """
    Setup enhanced logging for Flask application
    
    Args:
        app: Flask application instance
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    
    # Determine log level
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console Handler (for development)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(getattr(logging, log_level))
    
    # File Handler (JSON format)
    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / 'api_server.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(logging.INFO)
    
    # Error File Handler
    error_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / 'api_errors.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    error_handler.setFormatter(JSONFormatter())
    error_handler.setLevel(logging.ERROR)
    
    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    # Configure Flask app logger
    app.logger.setLevel(getattr(logging, log_level))
    
    # Disable Flask's default logging to avoid duplicates
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    print(f"✅ Enhanced logging configured - Level: {log_level}")
    print(f"📁 Log files: {LOGS_DIR.absolute()}")

def log_requests(app):
    """Add request/response logging middleware"""
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
        g.request_id = f"req_{int(time.time() * 1000)}_{os.getpid()}"
        
        # Log incoming request
        app.logger.info(
            "Incoming request",
            extra={
                "request_id": g.request_id,
                "method": request.method,
                "endpoint": request.endpoint or request.path,
                "user_ip": request.remote_addr,
                "user_agent": request.headers.get('User-Agent', ''),
                "content_length": request.content_length or 0
            }
        )
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            response_time = (time.time() - g.start_time) * 1000  # ms
            
            # Log response
            app.logger.info(
                "Request completed",
                extra={
                    "request_id": getattr(g, 'request_id', 'unknown'),
                    "method": request.method,
                    "endpoint": request.endpoint or request.path,
                    "status_code": response.status_code,
                    "response_time": round(response_time, 2),
                    "content_length": response.content_length or 0
                }
            )
        
        return response

def log_video_processing(video_id, status, **kwargs):
    """Log video processing events"""
    logger = logging.getLogger('video_processing')
    
    extra = {
        "video_id": video_id,
        "processing_status": status,
        **kwargs
    }
    
    if status == "started":
        logger.info(f"Video processing started: {video_id}", extra=extra)
    elif status == "completed":
        logger.info(f"Video processing completed: {video_id}", extra=extra)
    elif status == "failed":
        logger.error(f"Video processing failed: {video_id}", extra=extra)
    else:
        logger.info(f"Video processing {status}: {video_id}", extra=extra)

def log_api_error(error, endpoint=None, video_id=None, **kwargs):
    """Log API errors with context"""
    logger = logging.getLogger('api_errors')
    
    extra = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        **kwargs
    }
    
    if endpoint:
        extra["endpoint"] = endpoint
    if video_id:
        extra["video_id"] = video_id
    if hasattr(g, 'request_id'):
        extra["request_id"] = g.request_id
    
    logger.error(f"API Error: {str(error)}", extra=extra, exc_info=True)

# Decorator for endpoint logging
def log_endpoint(func):
    """Decorator to add endpoint-specific logging"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(f'endpoint.{func.__name__}')
        
        try:
            logger.info(f"Endpoint {func.__name__} called")
            result = func(*args, **kwargs)
            logger.info(f"Endpoint {func.__name__} completed successfully")
            return result
        except Exception as e:
            log_api_error(e, endpoint=func.__name__)
            raise
    
    return wrapper

if __name__ == "__main__":
    # Test logging configuration
    from flask import Flask
    
    app = Flask(__name__)
    setup_logging(app, 'DEBUG')
    log_requests(app)
    
    @app.route('/test')
    @log_endpoint
    def test_endpoint():
        app.logger.info("Test endpoint called")
        return {"message": "Test successful"}
    
    print("🧪 Test logging setup complete")
    print("📁 Check logs/ directory for output files")
