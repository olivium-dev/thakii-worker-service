#!/usr/bin/env python3
"""
Flask Logging Middleware for Thakii Worker Service
Automatically logs all requests and responses with the structured logging system
"""

import time
from functools import wraps
from flask import request, g, Response
from typing import Callable

from core.logging_system import (
    get_logger, 
    log_request, 
    log_response, 
    log_error
)


def setup_request_logging(app):
    """
    Setup request/response logging middleware for Flask app.
    
    Args:
        app: Flask application instance
    """
    logger = get_logger()
    
    @app.before_request
    def before_request():
        """Log incoming request and start timer."""
        g.start_time = time.time()
        
        # Log the incoming request
        g.request_id = log_request(
            method=request.method,
            endpoint=request.endpoint or request.path,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent', 'Unknown'),
            content_length=request.content_length or 0,
            content_type=request.content_type
        )
    
    @app.after_request
    def after_request(response: Response) -> Response:
        """Log response with timing information."""
        if hasattr(g, 'start_time') and hasattr(g, 'request_id'):
            response_time = (time.time() - g.start_time) * 1000  # Convert to ms
            
            log_response(
                request_id=g.request_id,
                status_code=response.status_code,
                response_time=response_time,
                content_length=response.content_length or 0,
                content_type=response.content_type
            )
        
        return response
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Log unhandled exceptions."""
        request_id = getattr(g, 'request_id', None)
        
        log_error(
            error,
            endpoint=request.endpoint or request.path,
            request_id=request_id,
            method=request.method,
            user_ip=request.remote_addr
        )
        
        # Re-raise to let Flask handle the response
        raise error
    
    logger.info("Flask request logging middleware initialized")


def log_endpoint(func: Callable) -> Callable:
    """
    Decorator to add endpoint-specific logging.
    
    Usage:
        @app.route('/my-endpoint')
        @log_endpoint
        def my_endpoint():
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger()
        endpoint_name = func.__name__
        
        try:
            logger.info(f"Endpoint called: {endpoint_name}", extra={
                'endpoint': endpoint_name,
                'request_id': getattr(g, 'request_id', None)
            })
            
            result = func(*args, **kwargs)
            
            logger.info(f"Endpoint completed: {endpoint_name}", extra={
                'endpoint': endpoint_name,
                'request_id': getattr(g, 'request_id', None)
            })
            
            return result
            
        except Exception as e:
            log_error(e, endpoint=endpoint_name, 
                     request_id=getattr(g, 'request_id', None))
            raise
    
    return wrapper


class VideoProcessingLogger:
    """
    Context manager for logging video processing operations.
    
    Usage:
        with VideoProcessingLogger(video_id, video_path) as vpl:
            # Process video
            vpl.update_status("extracting frames")
            # More processing
            vpl.set_result(pdf_path, pdf_size)
    """
    
    def __init__(self, video_id: str, video_path: str, **kwargs):
        self.video_id = video_id
        self.video_path = video_path
        self.extra_data = kwargs
        self.logger = get_logger()
        self.start_time = None
        self.result_data = {}
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.log_video_processing_start(
            self.video_id, 
            self.video_path,
            **self.extra_data
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        processing_time = time.time() - self.start_time
        
        if exc_type is not None:
            # An exception occurred
            self.logger.log_video_processing_failed(
                self.video_id,
                str(exc_val),
                processing_time=processing_time,
                error_type=exc_type.__name__,
                **self.extra_data
            )
            return False  # Don't suppress the exception
        else:
            # Processing completed successfully
            self.logger.log_video_processing_complete(
                self.video_id,
                processing_time=processing_time,
                **self.result_data,
                **self.extra_data
            )
            return True
    
    def update_status(self, status: str):
        """Update processing status."""
        self.logger.info(f"Processing status: {status}", extra={
            'video_id': self.video_id,
            'processing_status': status
        })
    
    def set_result(self, pdf_path: str = None, pdf_size: int = None):
        """Set processing result data."""
        if pdf_path:
            self.result_data['pdf_path'] = pdf_path
        if pdf_size:
            self.result_data['pdf_size'] = pdf_size


if __name__ == "__main__":
    # Test the middleware
    from flask import Flask
    
    app = Flask(__name__)
    setup_request_logging(app)
    
    @app.route('/test')
    @log_endpoint
    def test_endpoint():
        return {"message": "Test successful"}
    
    @app.route('/error')
    @log_endpoint
    def error_endpoint():
        raise ValueError("Test error")
    
    print("🧪 Testing Flask Logging Middleware")
    
    with app.test_client() as client:
        # Test normal request
        response = client.get('/test')
        print(f"Test endpoint: {response.status_code}")
        
        # Test error handling
        try:
            response = client.get('/error')
        except:
            pass
    
    print("✅ Middleware test completed!")
