# Thakii Worker Service

Background video processing service for the Thakii Lecture2PDF system. Monitors Firestore for queued video tasks and processes them through the complete video-to-PDF conversion pipeline using computer vision and speech recognition.

## 🚀 Features

- **Continuous Processing**: Monitors Firestore for new video tasks
- **Video-to-PDF Pipeline**: Complete conversion from video files to readable PDFs
- **Speech Recognition**: Automatic subtitle generation from video audio
- **Computer Vision**: Key frame extraction and scene change detection
- **Cloud Integration**: Seamless S3 and Firestore operations
- **Error Recovery**: Robust error handling with task status updates
- **Scalability**: Support for multiple concurrent worker instances
- **Cleanup Management**: Automatic temporary file cleanup

## 🛠️ Technology Stack

- **Python 3.10+**: Core runtime environment
- **OpenCV**: Computer vision for frame extraction
- **SpeechRecognition**: Audio-to-text conversion
- **FPDF**: PDF generation and layout
- **Firebase Admin SDK**: Firestore database operations
- **AWS SDK (boto3)**: S3 file operations
- **thakii-pdf-engine**: Core video processing library

## 📁 Project Structure

```
worker-service/
├── worker/
│   └── worker.py             # Main worker process
├── core/
│   ├── s3_storage.py         # AWS S3 operations
│   ├── firestore_db.py       # Firestore database operations
│   └── task_processor.py     # Task processing logic
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Local development setup
├── .env.example             # Environment variables template
└── deployment/
    ├── systemd/
    │   └── thakii-worker.service
    └── docker/
        └── docker-compose.prod.yml
```

## 🔧 Environment Variables

Create a `.env` file in the root directory:

```env
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-2
S3_BUCKET_NAME=thakii-video-storage

# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT_KEY=/path/to/firebase-service-account.json
GOOGLE_APPLICATION_CREDENTIALS=/path/to/firebase-service-account.json

# PDF Engine Configuration
LECTURE2PDF_PATH=/path/to/thakii-pdf-engine

# Worker Configuration
WORKER_POLL_INTERVAL=5        # Seconds between task checks
MAX_CONCURRENT_TASKS=3        # Maximum simultaneous processing
TEMP_DIR=/tmp/thakii-worker   # Temporary file directory

# Optional: Disable Firebase for development
DISABLE_FIREBASE=false
```

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- AWS account with S3 access
- Firebase project with Admin SDK
- thakii-pdf-engine library installed
- FFmpeg (for audio processing)
- System dependencies for OpenCV

### System Dependencies

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install -y python3-dev python3-pip ffmpeg
sudo apt install -y libopencv-dev python3-opencv
sudo apt install -y portaudio19-dev
```

#### macOS
```bash
brew install python@3.10 ffmpeg opencv portaudio
```

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/oudaykhaled/thakii-worker-service.git
   cd thakii-worker-service
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install thakii-pdf-engine  # Core processing library
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the worker**:
   ```bash
   python worker/worker.py
   ```

### Docker Setup

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or with Docker directly
docker build -t thakii-worker-service .
docker run --env-file .env thakii-worker-service
```

## 🔄 Processing Pipeline

### Task Processing Flow
```
1. Monitor Firestore for "in_queue" tasks
2. Update task status to "in_progress"
3. Download video from S3 to temporary storage
4. Generate subtitles using speech recognition
5. Extract key frames using computer vision
6. Create PDF combining frames and subtitles
7. Upload results (PDF + subtitles) to S3
8. Update task status to "done" or "failed"
9. Clean up temporary files
10. Return to monitoring
```

### Detailed Processing Steps

#### 1. Task Detection
```python
# Continuously monitor Firestore
task = firestore_db.get_next_queued_task()
if task:
    video_id = task['video_id']
    firestore_db.update_video_task_status(video_id, "in_progress")
```

#### 2. Video Download
```python
# Download from S3 to temporary file
temp_video_path = s3_storage.download_video_to_temp(
    video_id, 
    task['filename']
)
```

#### 3. Subtitle Generation
```python
# Generate subtitles using speech recognition
subprocess.run([
    python_executable,
    os.path.join(pdf_engine_path, "src", "subtitle_generator.py"),
    temp_video_path
], check=True)
```

#### 4. Frame Extraction
```python
# Extract key frames using computer vision
selected_frames_data = video_segment_finder.get_best_segment_frames(
    temp_video_path
)
```

#### 5. PDF Generation
```python
# Combine frames and subtitles into PDF
subprocess.run([
    python_executable,
    "-m", "src.main",
    temp_video_path,
    "-s", temp_subtitle_path,
    "-o", temp_pdf_path
], check=True, cwd=pdf_engine_path)
```

#### 6. Upload Results
```python
# Upload generated files to S3
pdf_key = s3_storage.upload_pdf(temp_pdf_path, video_id)
subtitle_key = s3_storage.upload_subtitle(subtitle_content, video_id)
```

## 🧠 Processing Algorithms

### Scene Change Detection
- **Frame Comparison**: Pixel-level differences between consecutive frames
- **Histogram Analysis**: Color distribution changes
- **Edge Detection**: Structural changes in frame content
- **Threshold-based Filtering**: Remove minor variations

### Key Frame Selection
- **Slide Transitions**: Detect significant content changes
- **Duplicate Removal**: Eliminate similar consecutive frames
- **Quality Assessment**: Select frames with best clarity
- **Temporal Distribution**: Ensure even distribution across video

### Speech Recognition
- **Audio Extraction**: Convert video audio to WAV format
- **Speech-to-Text**: Google Speech Recognition API
- **Timestamp Alignment**: Match text to video timestamps
- **Text Cleaning**: Remove filler words and artifacts

## 📊 Monitoring & Logging

### Task Status Updates
```python
# Status progression
"in_queue" → "in_progress" → "done"/"failed"

# Firestore updates
firestore_db.update_video_task_status(video_id, status)
```

### Comprehensive Logging
```python
print(f"📹 Processing video: {video_id}")
print(f"⬇️ Downloading video from S3...")
print(f"🎤 Generating subtitles...")
print(f"🖼️ Extracting key frames...")
print(f"📄 Generating PDF...")
print(f"⬆️ Uploading results to S3...")
print(f"✅ Video {video_id} processed successfully")
```

### Error Handling
```python
try:
    process_video(video_id)
    firestore_db.update_video_task_status(video_id, "done")
except Exception as e:
    print(f"❌ Error processing video {video_id}: {e}")
    firestore_db.update_video_task_status(video_id, "failed")
```

## 🚀 Deployment

### Systemd Service (Linux)
```ini
[Unit]
Description=Thakii Worker Service
After=network.target

[Service]
Type=simple
User=thakii
WorkingDirectory=/opt/thakii-worker-service
ExecStart=/opt/thakii-worker-service/venv/bin/python worker/worker.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/thakii-worker-service

[Install]
WantedBy=multi-user.target
```

### Docker Production Deployment
```yaml
version: '3.8'
services:
  worker:
    build: .
    restart: unless-stopped
    env_file: .env.production
    volumes:
      - /tmp/thakii-worker:/tmp/thakii-worker
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
```

### AWS ECS Deployment
```json
{
  "family": "thakii-worker-service",
  "networkMode": "awsvpc",
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "worker",
      "image": "your-account.dkr.ecr.region.amazonaws.com/thakii-worker:latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/thakii-worker",
          "awslogs-region": "us-east-2"
        }
      }
    }
  ]
}
```

## 🔧 Configuration

### Worker Tuning
```env
# Performance tuning
WORKER_POLL_INTERVAL=5        # How often to check for new tasks
MAX_CONCURRENT_TASKS=3        # Parallel processing limit
TEMP_DIR_CLEANUP_INTERVAL=3600 # Cleanup interval in seconds

# Processing options
ENABLE_GPU_ACCELERATION=true  # Use GPU for OpenCV operations
SUBTITLE_LANGUAGE=en-US       # Speech recognition language
PDF_QUALITY=high              # Output quality (low/medium/high)
```

### Resource Management
```python
# Memory management
import gc
gc.collect()  # Force garbage collection after processing

# Temporary file cleanup
s3_storage.cleanup_temp_files(
    temp_video_path, 
    temp_subtitle_path, 
    temp_pdf_path
)
```

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-mock

# Run unit tests
pytest tests/

# Test with sample video
python -m pytest tests/test_video_processing.py

# Integration tests (requires AWS/Firebase credentials)
pytest tests/integration/
```

### Test Structure
```
tests/
├── unit/
│   ├── test_worker.py
│   ├── test_s3_storage.py
│   └── test_firestore_db.py
├── integration/
│   ├── test_end_to_end.py
│   └── test_aws_integration.py
└── fixtures/
    ├── sample_video.mp4
    └── expected_output.pdf
```

## 📈 Performance Optimization

### Processing Optimization
- **Parallel Processing**: Multiple worker instances
- **GPU Acceleration**: OpenCV GPU operations
- **Memory Management**: Efficient temporary file handling
- **Batch Processing**: Process multiple tasks when possible

### Resource Monitoring
```python
import psutil
import time

def monitor_resources():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    print(f"CPU: {cpu_percent}%, Memory: {memory_info.percent}%")
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the processing logs
- Contact the development team

## 🔗 Related Repositories

- [thakii-pdf-engine](https://github.com/oudaykhaled/thakii-pdf-engine) - Core processing library
- [thakii-backend-api](https://github.com/oudaykhaled/thakii-backend-api) - Task coordination API
- [thakii-frontend](https://github.com/oudaykhaled/thakii-frontend) - User interface
- [thakii-infrastructure](https://github.com/oudaykhaled/thakii-infrastructure) - Infrastructure as Code
