#!/usr/bin/env python3
"""
Thakii Worker Service - Structured Logging System
Logs are organized by year/month/day for easy navigation and retrieval
"""

import os
import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict
import traceback
import threading
import uuid

# Base logs directory
LOGS_BASE_DIR = os.getenv('LOGS_DIR', 'logs')

class DailyDirectoryFileHandler(logging.Handler):
    """
    Custom logging handler that creates directory structure: logs/YYYY/MM/DD/
    and writes logs to daily files within those directories.
    """
    
    def __init__(self, base_dir: str, log_type: str = "api", encoding: str = 'utf-8'):
        """
        Initialize the daily directory file handler.
        
        Args:
            base_dir: Base directory for logs (e.g., 'logs')
            log_type: Type of log (e.g., 'api', 'errors', 'processing')
            encoding: File encoding
        """
        super().__init__()
        self.base_dir = Path(base_dir)
        self.log_type = log_type
        self.encoding = encoding
        self._current_date = None
        self._current_file = None
        self._lock = threading.Lock()
    
    def _get_log_path(self, record_time: datetime) -> Path:
        """Get the log file path for a specific date."""
        year = record_time.strftime('%Y')
        month = record_time.strftime('%m')
        day = record_time.strftime('%d')
        
        # Create directory structure: logs/YYYY/MM/DD/
        log_dir = self.base_dir / year / month / day
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log file: logs/YYYY/MM/DD/api.log (or errors.log, processing.log)
        return log_dir / f"{self.log_type}.log"
    
    def _open_file(self, log_path: Path):
        """Open a new log file."""
        if self._current_file:
            self._current_file.close()
        self._current_file = open(log_path, 'a', encoding=self.encoding)
    
    def emit(self, record):
        """Write log record to the appropriate daily file."""
        try:
            with self._lock:
                record_time = datetime.fromtimestamp(record.created)
                record_date = record_time.date()
                
                # Check if we need to switch to a new file (new day)
                if self._current_date != record_date:
                    log_path = self._get_log_path(record_time)
                    self._open_file(log_path)
                    self._current_date = record_date
                
                # Format and write the log entry
                msg = self.format(record)
                self._current_file.write(msg + '\n')
                self._current_file.flush()
                
        except Exception:
            self.handleError(record)
    
    def close(self):
        """Close the current file."""
        with self._lock:
            if self._current_file:
                self._current_file.close()
                self._current_file = None
        super().close()


class StructuredJSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging with rich context.
    """
    
    def format(self, record) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "local_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread_id": record.thread,
            "process_id": record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info) if record.exc_info[0] else None
            }
        
        # Add all extra fields from the record
        extra_fields = [
            'request_id', 'video_id', 'user_ip', 'endpoint', 'method', 
            'status_code', 'response_time', 'content_length', 'filename',
            'error_type', 'error_message', 'processing_status', 'pdf_size',
            'user_agent', 'video_path', 'subtitle_path', 's3_key'
        ]
        
        for field in extra_fields:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class ReadableFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record) -> str:
        """Format log record for human readability."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build the base message
        msg = f"{timestamp} | {color}{record.levelname:8}{reset} | {record.name} | {record.getMessage()}"
        
        # Add extra context if available
        extras = []
        if hasattr(record, 'video_id'):
            extras.append(f"video_id={record.video_id}")
        if hasattr(record, 'request_id'):
            extras.append(f"req={record.request_id[:12]}")
        if hasattr(record, 'response_time'):
            extras.append(f"time={record.response_time}ms")
        if hasattr(record, 'status_code'):
            extras.append(f"status={record.status_code}")
        
        if extras:
            msg += f" | {' '.join(extras)}"
        
        # Add exception info
        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"
        
        return msg


class WorkerLogger:
    """
    Main logging class for Thakii Worker Service.
    Provides structured logging with daily directory organization.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern to ensure single logger instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the worker logger if not already initialized."""
        if WorkerLogger._initialized:
            return
        
        self.base_dir = Path(LOGS_BASE_DIR)
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        
        # Create base logs directory
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup loggers
        self._setup_loggers()
        
        WorkerLogger._initialized = True
        
        # Log initialization
        self.info("Logging system initialized", extra={
            "logs_dir": str(self.base_dir.absolute()),
            "log_level": self.log_level,
            "structure": "logs/YYYY/MM/DD/"
        })
    
    def _setup_loggers(self):
        """Setup all loggers with appropriate handlers."""
        
        # Get the root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.log_level))
        
        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler (human-readable)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ReadableFormatter())
        console_handler.setLevel(getattr(logging, self.log_level))
        root_logger.addHandler(console_handler)
        
        # File handlers with daily directory structure
        log_types = ['api', 'errors', 'processing', 'requests']
        
        for log_type in log_types:
            handler = DailyDirectoryFileHandler(str(self.base_dir), log_type)
            handler.setFormatter(StructuredJSONFormatter())
            
            if log_type == 'errors':
                handler.setLevel(logging.ERROR)
            else:
                handler.setLevel(logging.INFO)
            
            root_logger.addHandler(handler)
        
        # Create named loggers for specific components
        self.api_logger = logging.getLogger('thakii.api')
        self.processing_logger = logging.getLogger('thakii.processing')
        self.requests_logger = logging.getLogger('thakii.requests')
        self.errors_logger = logging.getLogger('thakii.errors')
    
    def _log(self, level: int, message: str, extra: Optional[Dict[str, Any]] = None, 
             exc_info: bool = False, logger_name: str = 'thakii.api'):
        """Internal logging method."""
        logger = logging.getLogger(logger_name)
        
        if extra is None:
            extra = {}
        
        # Create a log record adapter to pass extra fields
        logger.log(level, message, extra=extra, exc_info=exc_info)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, kwargs.get('extra'))
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, kwargs.get('extra'))
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, kwargs.get('extra'))
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, kwargs.get('extra'), exc_info, 'thakii.errors')
    
    def critical(self, message: str, exc_info: bool = True, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, message, kwargs.get('extra'), exc_info, 'thakii.errors')
    
    # Specialized logging methods
    
    def log_request(self, method: str, endpoint: str, user_ip: str, 
                    request_id: str = None, **kwargs):
        """Log incoming API request."""
        if request_id is None:
            request_id = f"req_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        extra = {
            'request_id': request_id,
            'method': method,
            'endpoint': endpoint,
            'user_ip': user_ip,
            **kwargs
        }
        
        self._log(logging.INFO, f"Request: {method} {endpoint}", extra, 
                  logger_name='thakii.requests')
        return request_id
    
    def log_response(self, request_id: str, status_code: int, 
                     response_time: float, **kwargs):
        """Log API response."""
        extra = {
            'request_id': request_id,
            'status_code': status_code,
            'response_time': round(response_time, 2),
            **kwargs
        }
        
        self._log(logging.INFO, f"Response: {status_code} ({response_time:.2f}ms)", 
                  extra, logger_name='thakii.requests')
    
    def log_video_processing_start(self, video_id: str, video_path: str, **kwargs):
        """Log video processing start."""
        extra = {
            'video_id': video_id,
            'video_path': video_path,
            'processing_status': 'started',
            **kwargs
        }
        
        self._log(logging.INFO, f"Video processing started: {video_id}", 
                  extra, logger_name='thakii.processing')
    
    def log_video_processing_complete(self, video_id: str, pdf_size: int = None, 
                                       processing_time: float = None, **kwargs):
        """Log video processing completion."""
        extra = {
            'video_id': video_id,
            'processing_status': 'completed',
            **kwargs
        }
        
        if pdf_size:
            extra['pdf_size'] = pdf_size
        if processing_time:
            extra['processing_time'] = round(processing_time, 2)
        
        self._log(logging.INFO, f"Video processing completed: {video_id}", 
                  extra, logger_name='thakii.processing')
    
    def log_video_processing_failed(self, video_id: str, error: str, **kwargs):
        """Log video processing failure."""
        extra = {
            'video_id': video_id,
            'processing_status': 'failed',
            'error_message': error,
            **kwargs
        }
        
        self._log(logging.ERROR, f"Video processing failed: {video_id} - {error}", 
                  extra, logger_name='thakii.processing')
    
    def log_api_error(self, error: Exception, endpoint: str = None, 
                      request_id: str = None, **kwargs):
        """Log API error with full context."""
        extra = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            **kwargs
        }
        
        if endpoint:
            extra['endpoint'] = endpoint
        if request_id:
            extra['request_id'] = request_id
        
        self._log(logging.ERROR, f"API Error: {str(error)}", extra, 
                  exc_info=True, logger_name='thakii.errors')
    
    def get_logs_path(self, date: datetime = None) -> Path:
        """Get the logs directory path for a specific date."""
        if date is None:
            date = datetime.now()
        
        return self.base_dir / date.strftime('%Y') / date.strftime('%m') / date.strftime('%d')
    
    def list_log_dates(self) -> list:
        """List all available log dates."""
        dates = []
        
        if not self.base_dir.exists():
            return dates
        
        for year_dir in sorted(self.base_dir.iterdir()):
            if year_dir.is_dir() and year_dir.name.isdigit():
                for month_dir in sorted(year_dir.iterdir()):
                    if month_dir.is_dir() and month_dir.name.isdigit():
                        for day_dir in sorted(month_dir.iterdir()):
                            if day_dir.is_dir() and day_dir.name.isdigit():
                                dates.append({
                                    'date': f"{year_dir.name}-{month_dir.name}-{day_dir.name}",
                                    'path': str(day_dir),
                                    'files': [f.name for f in day_dir.glob('*.log')]
                                })
        
        return dates


# Global logger instance
worker_logger = WorkerLogger()


# Convenience functions for direct import
def get_logger() -> WorkerLogger:
    """Get the global worker logger instance."""
    return worker_logger

def log_request(method: str, endpoint: str, user_ip: str, **kwargs) -> str:
    """Log an incoming request and return the request ID."""
    return worker_logger.log_request(method, endpoint, user_ip, **kwargs)

def log_response(request_id: str, status_code: int, response_time: float, **kwargs):
    """Log a response."""
    worker_logger.log_response(request_id, status_code, response_time, **kwargs)

def log_video_start(video_id: str, video_path: str, **kwargs):
    """Log video processing start."""
    worker_logger.log_video_processing_start(video_id, video_path, **kwargs)

def log_video_complete(video_id: str, **kwargs):
    """Log video processing completion."""
    worker_logger.log_video_processing_complete(video_id, **kwargs)

def log_video_failed(video_id: str, error: str, **kwargs):
    """Log video processing failure."""
    worker_logger.log_video_processing_failed(video_id, error, **kwargs)

def log_error(error: Exception, **kwargs):
    """Log an error."""
    worker_logger.log_api_error(error, **kwargs)


if __name__ == "__main__":
    # Test the logging system
    print("🧪 Testing Logging System")
    print("=" * 50)
    
    logger = get_logger()
    
    # Test basic logging
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test request logging
    req_id = log_request("POST", "/generate-pdf", "127.0.0.1", content_length=22012940)
    print(f"Request ID: {req_id}")
    
    # Simulate some processing time
    import time
    time.sleep(0.1)
    
    # Log response
    log_response(req_id, 201, 105.5)
    
    # Test video processing logging
    log_video_start("direct-test123", "/path/to/video.mp4")
    log_video_complete("direct-test123", pdf_size=2048576, processing_time=45.2)
    
    # Test error logging
    try:
        raise ValueError("Test error for logging")
    except Exception as e:
        log_error(e, endpoint="/test", request_id=req_id)
    
    # Show log directory structure
    print("\n📁 Log Directory Structure:")
    print(f"   Base: {logger.base_dir.absolute()}")
    
    logs_path = logger.get_logs_path()
    print(f"   Today: {logs_path}")
    
    if logs_path.exists():
        print("   Files:")
        for log_file in logs_path.glob("*.log"):
            print(f"      - {log_file.name}")
    
    print("\n✅ Logging system test completed!")
    print(f"📁 Check the logs directory: {logger.base_dir.absolute()}")
