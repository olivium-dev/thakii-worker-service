# Thakii Worker Service - Inputs and Outputs

This document describes the data flow, dependencies, and interfaces for the Thakii Worker Service.

## 📥 INPUTS

### 1. Firestore Task Queue
**Source**: Firebase Firestore (populated by thakii-backend-api)
**Format**: Firestore documents
**Collection**: `video_tasks`

#### Task Document Structure
```javascript
{
  video_id: "550e8400-e29b-41d4-a716-446655440000",
  filename: "lecture_video.mp4",
  user_id: "firebase_user_uid",
  user_email: "user@example.com",
  status: "in_queue",  // Worker looks for this status
  upload_date: "2024-01-01 10:00:00",
  created_at: Timestamp,
  updated_at: Timestamp
}
```

#### Query Pattern
```python
# Worker continuously polls for new tasks
tasks = firestore_db.collection('video_tasks')\
    .where('status', '==', 'in_queue')\
    .order_by('created_at')\
    .limit(1)\
    .get()
```

### 2. Video Files from S3
**Source**: Amazon S3 (uploaded by thakii-backend-api)
**Format**: Binary video files
**Location**: `s3://bucket/videos/{video_id}/{filename}`

#### Supported Video Formats
- **MP4**: H.264/H.265 encoding
- **AVI**: Various codecs supported
- **MOV**: QuickTime format
- **WMV**: Windows Media Video
- **MKV**: Matroska container

#### File Size Range
- **Minimum**: 1MB (practical minimum for processing)
- **Maximum**: 2GB (system limit)
- **Typical**: 100MB - 500MB for lecture videos

### 3. Environment Configuration
**Source**: Environment variables and configuration files
**Format**: Key-value pairs

#### Required Configuration
```env
# AWS S3 Access
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=secret...
AWS_DEFAULT_REGION=us-east-2
S3_BUCKET_NAME=thakii-video-storage

# Firebase Firestore Access
FIREBASE_SERVICE_ACCOUNT_KEY=/path/to/service-account.json
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Processing Configuration
LECTURE2PDF_PATH=/path/to/thakii-pdf-engine
WORKER_POLL_INTERVAL=5
MAX_CONCURRENT_TASKS=3
TEMP_DIR=/tmp/thakii-worker
```

### 4. PDF Engine Dependencies
**Source**: thakii-pdf-engine library
**Format**: Python package with executable modules
**Required Components**:
- `src/subtitle_generator.py` - Speech recognition
- `src/main.py` - Main processing pipeline
- `src/video_segment_finder.py` - Frame extraction
- `src/content_segment_exporter.py` - PDF generation

### 5. System Dependencies
**Source**: Operating system and installed packages
**Required Components**:
- **FFmpeg**: Audio/video processing
- **OpenCV**: Computer vision operations
- **PortAudio**: Audio input/output
- **Python 3.10+**: Runtime environment

## 📤 OUTPUTS

### 1. Firestore Status Updates
**Destination**: Firebase Firestore
**Format**: Document updates
**Collection**: `video_tasks`

#### Status Progression
```javascript
// Initial status (set by backend-api)
{status: "in_queue"}

// Worker starts processing
{
  status: "in_progress",
  updated_at: Timestamp,
  processing_started: Timestamp
}

// Processing completed successfully
{
  status: "done",
  updated_at: Timestamp,
  processing_completed: Timestamp,
  pdf_s3_key: "pdfs/video-id.pdf",
  subtitle_s3_key: "subtitles/video-id.srt"
}

// Processing failed
{
  status: "failed",
  updated_at: Timestamp,
  error_message: "Speech recognition failed: audio quality too low",
  processing_failed: Timestamp
}
```

### 2. Generated PDF Files
**Destination**: Amazon S3
**Format**: PDF documents
**Location**: `s3://bucket/pdfs/{video_id}.pdf`

#### PDF Structure
```
Page Layout:
┌─────────────────────────┐
│     Video Frame         │
│   (Key slide image)     │
│                         │
├─────────────────────────┤
│   Subtitle Text         │
│ "In this lecture we     │
│ will discuss the main   │
│ concepts of..."         │
└─────────────────────────┘

Features:
- High-resolution frame captures
- Readable text transcription
- Consistent formatting
- Page numbering
- Metadata embedded
```

#### PDF Metadata
```python
{
  "Title": f"Lecture PDF - {original_filename}",
  "Author": "Thakii Lecture2PDF Service",
  "Subject": "Auto-generated lecture notes",
  "Creator": "thakii-pdf-engine",
  "Producer": "FPDF Library",
  "CreationDate": datetime.now(),
  "Keywords": "lecture, education, notes, pdf"
}
```

### 3. Subtitle Files (SRT Format)
**Destination**: Amazon S3
**Format**: SubRip Text (.srt)
**Location**: `s3://bucket/subtitles/{video_id}.srt`

#### SRT File Structure
```srt
1
00:00:00,000 --> 00:00:05,240
Welcome to today's lecture on machine learning fundamentals.

2
00:00:05,240 --> 00:00:10,120
We'll start by discussing the basic concepts and terminology.

3
00:00:10,120 --> 00:00:15,360
Machine learning is a subset of artificial intelligence that enables computers to learn.
```

### 4. System Logs
**Destination**: stdout/stderr, log files
**Format**: Structured text messages

#### Log Categories
```python
# Processing Status
print(f"📹 Processing video: {video_id}")
print(f"⬇️ Downloading video from S3...")
print(f"🎤 Generating subtitles for {video_id}...")
print(f"🖼️ Getting selected frames")
print(f"📄 Generating PDF file")
print(f"⬆️ Uploading PDF to S3...")
print(f"✅ Video {video_id} processed successfully")

# Error Logging
print(f"❌ Error processing video {video_id}: {error_message}")
print(f"🚨 Worker loop error: {error_message}")

# Performance Metrics
print(f"📊 Processing time: {duration:.2f} seconds")
print(f"📊 Generated {len(frames)} pages")
print(f"📊 Subtitle duration: {total_duration} seconds")
```

### 5. Temporary File Operations
**Destination**: Local file system (temporary)
**Format**: Various file types
**Lifecycle**: Created → Processed → Cleaned up

#### Temporary Files Created
```python
# Video download
temp_video_path = "/tmp/thakii-worker/video_123.mp4"

# Subtitle generation
temp_srt_path = "/tmp/thakii-worker/subtitles_123.srt"

# PDF generation
temp_pdf_path = "/tmp/thakii-worker/output_123.pdf"

# Frame extraction (multiple files)
temp_frame_dir = "/tmp/thakii-worker/frames_123/"
# Contains: frame_001.jpg, frame_002.jpg, etc.
```

### 6. Resource Cleanup Operations
**Destination**: File system cleanup
**Format**: File deletion operations

#### Cleanup Process
```python
def cleanup_temp_files(*file_paths):
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                print(f"🧹 Cleaned up: {file_path}")
            except Exception as e:
                print(f"⚠️ Failed to cleanup {file_path}: {e}")
```

## 🔄 DATA FLOW PATTERNS

### Task Processing Pipeline
```
Firestore Query → Task Detection → Status Update ("in_progress") → 
S3 Download → Speech Recognition → Frame Extraction → 
PDF Generation → S3 Upload → Status Update ("done"/"failed") → 
Cleanup → Return to Monitoring
```

### Error Handling Flow
```
Exception Caught → Error Logging → Status Update ("failed") → 
Cleanup Temporary Files → Continue Monitoring
```

### Multi-Worker Coordination
```
Worker 1: Queries Firestore → Gets Task A → Processes
Worker 2: Queries Firestore → Gets Task B → Processes  
Worker 3: Queries Firestore → No tasks → Waits

(Firestore handles concurrency through atomic operations)
```

## 🔗 DEPENDENCIES

### External Services
- **Firebase Firestore**: Task queue and status management
- **Amazon S3**: Video storage and result upload
- **Google Speech Recognition**: Audio-to-text conversion (via thakii-pdf-engine)

### Internal Dependencies
- **thakii-pdf-engine**: Core video processing library
- **thakii-backend-api**: Creates tasks that worker processes

### System Dependencies
- **FFmpeg**: Video/audio processing
- **OpenCV**: Computer vision operations
- **Python Libraries**: boto3, firebase-admin, opencv-python, SpeechRecognition

## 🎯 ROLE IN SYSTEM

The Worker Service serves as the **processing engine** for the Thakii system:

1. **Task Consumer**: Monitors and processes queued video tasks
2. **Video Processor**: Converts videos to structured PDF documents
3. **Speech Recognizer**: Extracts text from video audio
4. **Frame Analyzer**: Identifies key visual content from videos
5. **Content Generator**: Creates readable PDF learning materials
6. **Status Reporter**: Updates processing status in real-time
7. **Resource Manager**: Handles temporary files and cleanup

## 🔒 SECURITY CONSIDERATIONS

### File Security
- Temporary files stored in secure directories
- Automatic cleanup prevents data leakage
- S3 operations use IAM roles and policies

### Data Processing
- No permanent storage of user content
- Secure handling of video and audio data
- Processing isolation between tasks

### Access Control
- Firebase service account with minimal permissions
- S3 bucket access limited to specific operations
- No direct user interaction (backend-only service)

## 📊 PERFORMANCE CHARACTERISTICS

### Processing Metrics
- **Average Processing Time**: 2-5 minutes per video (depends on length)
- **Memory Usage**: 1-2GB per concurrent task
- **CPU Usage**: High during video processing, low during monitoring
- **Network Usage**: High during S3 operations

### Scalability Factors
- **Horizontal Scaling**: Multiple worker instances supported
- **Resource Limits**: Configurable concurrent task limits
- **Queue Management**: Firestore handles task distribution
- **Error Recovery**: Failed tasks remain in queue for retry
