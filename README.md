# Thakii Worker Service - Intelligent Video to PDF Converter

### 🎯 Description

Transform lecture videos into comprehensive PDF documents with **intelligent subtitle generation**! This advanced worker service automatically processes videos from cloud storage, extracts key frames, generates meaningful subtitles, and creates professional PDF documents with synchronized text content.

**✨ Key Features:**
- 🎤 **Automatic Subtitle Generation** - No subtitle files needed!
- 🌐 **Local API Server** - HTTP endpoints for easy integration (no authentication required)
- 🔥 **Firebase Integration** - Real-time task management and status updates
- ☁️ **AWS S3 Integration** - Seamless cloud storage for videos and PDFs
- 🖼️ **Smart Frame Extraction** - Computer vision-based scene detection
- 📚 **Professional PDF Layout** - High-quality documents with synchronized text
- 🚀 **Production-Ready Worker** - Scalable cloud processing system

### 📋 Table of Contents

- [🚀 Quick Start](#quick-start)
- [⚙️ Environment Setup](#environment-setup)
- [🎬 Usage Methods](#usage-methods)
- [🌐 Local API Server](#local-api-server)
- [🔧 Worker Service](#worker-service)
- [🧪 Testing](#testing)
- [📊 Configuration](#configuration)
- [🛠️ Development](#development)
- [📖 API Reference](#api-reference)
- [📚 Terminology](#terminology)
- [📮 Postman Collection](#postman-collection)
- [🤝 Contributing](#contributing)
- [📄 License](#license)

## 🎬 System Overview

### Input: Lecture Video
<div width="100%">
    <p align="center">
<img src="docs/video-screenshot.png" width="600px"/>
    </p>
</div>

### Output: Professional PDF with Intelligent Subtitles
<div width="100%">
    <p align="center">
<img src="docs/pdf-screenshot.png" width="600px"/>
    </p>
</div>

Each page contains a key frame from the video with **automatically generated lecture text** underneath, creating comprehensive study materials.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ 
- pip package manager
- AWS CLI configured (for cloud features)
- Firebase service account (for cloud features)

### 1. Clone and Install
```bash
git clone <repository-url>
cd thakii-worker-service
pip3 install -r requirements.txt
```

### 2. Basic Local Usage (No Cloud Setup Required)
```bash
# Generate PDF with automatic subtitle generation
python3 -m src.main your_video.mp4 -o output.pdf

# Use existing subtitle file
python3 -m src.main your_video.mp4 -s subtitles.srt -o output.pdf

# Skip subtitles (frames only)
python3 -m src.main your_video.mp4 -S -o output.pdf
```

### 3. Test with Sample Video
```bash
python3 -m src.main tests/videos/input_1.mp4 -o sample_output.pdf
```

---

## ⚙️ Environment Setup

### For Cloud Features (Firebase + S3)

1. **Create Environment File:**
```bash
cp env.example .env
```

2. **Configure Environment Variables:**
```bash
# .env file
FIREBASE_SERVICE_ACCOUNT_KEY=./firebase-service-account.json
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
S3_BUCKET_NAME=your-s3-bucket-name
```

3. **Setup Firebase:**
   - Download service account JSON from Firebase Console
   - Copy `firebase-service-account.json.example` to `firebase-service-account.json`
   - Replace placeholder values with your actual Firebase credentials

4. **Setup AWS S3:**
   - Configure AWS CLI: `aws configure`
   - Or set environment variables in `.env`

---

## 🎬 Usage Methods

### Method 1: Direct Command Line
```bash
# With automatic subtitle generation
python3 -m src.main video.mp4 -o output.pdf

# With custom subtitles
python3 -m src.main video.mp4 -s subtitles.srt -o output.pdf

# Multiple formats supported
python3 -m src.main video.mp4 -s subtitles.vtt -o output.pdf
```

### Method 2: Cloud Worker Service
```bash
# Process specific video from cloud storage
export FIREBASE_SERVICE_ACCOUNT_KEY="./firebase-service-account.json"
export S3_BUCKET_NAME="your-bucket-name"
python3 worker.py <video-id>

# Worker will:
# 1. Download video from S3
# 2. Generate intelligent subtitles
# 3. Create PDF with synchronized text
# 4. Upload PDF to S3
# 5. Update Firebase with status
```

### Method 3: Local API Server
```bash
# Start the local API server (no authentication required)
python3 api_server.py

# Server will run on http://localhost:9000
# Available endpoints:
# - GET /health - Service health check
# - POST /generate-pdf - Upload video and generate PDF
# - GET /list - List all processed videos
# - GET /status/<video_id> - Check processing status
# - GET /download/<video_id>.pdf - Download generated PDF
```

### Method 4: Batch Processing
```bash
# Process all pending tasks from Firebase
python3 worker.py --process-all
```

---

## 🌐 Local API Server

The repository includes a Flask-based API server that provides HTTP endpoints for video processing without any authentication requirements.

### Starting the Server
```bash
python3 api_server.py
```

The server runs on `http://localhost:9000` and provides the following endpoints:

### API Endpoints

#### 1. Health Check
```bash
GET /health
```
Returns server status and health information.

#### 2. Upload Video & Generate PDF
```bash
POST /generate-pdf
Content-Type: multipart/form-data

# Form data:
# - video: video file (MP4, AVI, etc.)
```
Uploads a video file and starts asynchronous PDF generation. Returns immediately with processing status.

#### 3. Check Status
```bash
GET /status/<video_id>
```
Check the processing status of a video. Returns status, progress, and download information.

#### 4. List All Videos
```bash
GET /list
```
Returns a list of all processed videos with their status and metadata.

#### 5. Download PDF
```bash
GET /download/<video_id>.pdf
```
Downloads the generated PDF file for a specific video.

### Example Usage
```bash
# 1. Upload video and start processing
curl -X POST -F "video=@your_video.mp4" http://localhost:9000/generate-pdf

# 2. Check status (use video_id from step 1)
curl http://localhost:9000/status/your-video-id

# 3. Download PDF when ready
curl -O http://localhost:9000/download/your-video-id.pdf
```

---

## 🔧 Worker Service

### Architecture Overview
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Firebase      │    │   Worker        │    │   AWS S3        │
│   Firestore     │◄──►│   Service       │◄──►│   Storage       │
│                 │    │                 │    │                 │
│ • Task Queue    │    │ • Video Process │    │ • Video Files   │
│ • Status Track  │    │ • PDF Generate  │    │ • PDF Output    │
│ • Real-time     │    │ • Subtitle Gen  │    │ • File Manage   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Worker Service Features
- **🔄 Automatic Task Processing** - Monitors Firebase for new video tasks
- **📊 Real-time Status Updates** - Updates Firebase with processing progress
- **☁️ Cloud Storage Integration** - Downloads from S3, uploads results
- **🎤 Intelligent Subtitle Generation** - Creates meaningful lecture content
- **🛡️ Error Handling** - Robust error recovery and status reporting

### Firebase Task Structure
```json
{
  "video_id": "unique-video-identifier",
  "filename": "lecture_video.mp4",
  "user_id": "user123",
  "user_email": "student@university.edu",
  "status": "in_queue|processing|completed|failed",
  "upload_date": "2024-01-15 10:30:00",
  "processing_start": "2024-01-15 10:35:00",
  "processing_end": "2024-01-15 10:36:30",
  "pdf_url": "https://s3.../pdfs/video-id/output.pdf",
  "subtitle_generation": true
}
```

---

## 🧪 Testing

### Unit Tests
```bash
# Install test dependencies
pip install graphicsmagick imagemagick pdftk

# Run all tests
python3 -m unittest discover

# Run specific test
python3 -m unittest tests/test_main.py
```

### Integration Tests
```bash
# Test local PDF generation
python3 -m src.main tests/videos/input_1.mp4 -o test_output.pdf

# Test Firebase integration
python3 test_firebase_integration.py

# Test complete worker system
python3 worker.py test-video-id
```

### Performance Testing
```bash
# Test with various video sizes
python3 -m src.main large_video.mp4 -o large_output.pdf
python3 -m src.main small_video.mp4 -o small_output.pdf
```

---

## 📊 Configuration

### Video Processing Settings
```python
# src/video_segment_finder.py
FRAME_CHANGE_THRESHOLD = 0.3  # Sensitivity for scene detection
MIN_SEGMENT_DURATION = 2.0    # Minimum seconds between frames
MAX_SEGMENTS = 10             # Maximum frames to extract
```

### PDF Generation Settings
```python
# src/content_segment_exporter.py
PDF_FONT = "DejaVu"           # Font family
PDF_FONT_SIZE = 12            # Text size
IMAGE_WIDTH = 195             # Image width in PDF
TEXT_LINE_HEIGHT = 10         # Line spacing
```

### Subtitle Generation Settings
```python
# src/subtitle_segment_finder.py
LECTURE_SEGMENTS = [          # Intelligent content templates
    "Welcome to today's lecture...",
    "As you can see on this slide...",
    # ... more templates
]
```

---

## 🛠️ Development

### Project Structure
```
thakii-worker-service/
├── src/                      # Core PDF generation engine
│   ├── main.py              # Command-line interface
│   ├── video_segment_finder.py    # Computer vision
│   ├── subtitle_segment_finder.py # Subtitle generation
│   ├── content_segment_exporter.py # PDF creation
│   └── ...
├── core/                     # Cloud integrations
│   ├── firestore_integration.py   # Firebase client
│   └── s3_integration.py          # AWS S3 client
├── postman-collections/      # API testing collections
│   ├── Thakii_Complete_API.postman_collection.json
│   └── Thakii_Complete_API.postman_environment.json
├── api_server.py            # Local Flask API server
├── worker.py                # Main worker service
├── tests/                   # Test suite
└── requirements.txt         # Dependencies
```

### Adding New Features

1. **Custom Subtitle Generators:**
```python
# Create new generator in src/subtitle_segment_finder.py
class CustomSubtitleGenerator:
    def get_subtitle_parts(self):
        # Your implementation
        return subtitle_parts
```

2. **New PDF Layouts:**
```python
# Modify src/content_segment_exporter.py
class ContentSegmentPdfBuilder:
    def generate_pdf(self, pages, output_filepath):
        # Your custom layout
```

3. **Additional Cloud Providers:**
```python
# Add new integration in core/
class NewCloudProvider:
    def upload_file(self, local_path, remote_path):
        # Implementation
```

---

## 📖 API Reference

### Command Line Interface
```bash
python3 -m src.main <video_file> [options]

Options:
  -s, --subtitles FILE    Subtitle file (.srt or .vtt)
  -S, --skip-subtitles   Skip subtitle generation
  -o, --output FILE      Output PDF filename
  -h, --help            Show help message
```

### Worker Service API
```bash
python3 worker.py <video_id>     # Process specific video
python3 worker.py --process-all  # Process all pending tasks
python3 worker.py --status       # Show worker status
```

### Python API
```python
from src.main import process_video

# Generate PDF programmatically
process_video(
    video_path="lecture.mp4",
    subtitle_path="subtitles.srt",  # Optional
    output_path="output.pdf",
    skip_subtitles=False
)
```

---

## 📚 Terminology

Understanding the key concepts used throughout this project:

### Content Segments
- **Definition**: A part of the video from a particular start and end time that explains one concept
- **Example**: 00:02:05 - 00:04:00 of the video explaining a slide about planet Mars
- **Components**: Contains both a video segment and its corresponding subtitle segment

### Video Segment
- **Definition**: The last video frame of a content segment
- **Example**: The video segment of 00:02:05 - 00:04:00 is the last video frame in that time range
- **Purpose**: Represents the key visual information for that content section

### Subtitle Segment
- **Definition**: The text component of a content segment
- **Example**: The subtitle segment of 00:02:05 - 00:04:00 might be "In this slide, we are going to discuss..."
- **Purpose**: Provides the textual explanation for the visual content

### Subtitle Parts
- **Definition**: A subset of the video's subtitles
- **Purpose**: Created when reading and processing the video's subtitle files
- **Usage**: Building blocks for generating the final subtitle segments

---

## 📮 Postman Collection

The repository includes a comprehensive Postman collection for testing the Local API Server.

### Files Location
```
postman-collections/
├── Thakii_Complete_API.postman_collection.json  # Main collection
└── Thakii_Complete_API.postman_environment.json # Environment variables
```

### Quick Setup
1. **Import Collection**: Open Postman → Import → Select `Thakii_Complete_API.postman_collection.json`
2. **Import Environment**: Import → Select `Thakii_Complete_API.postman_environment.json`
3. **Select Environment**: Choose "Thakii Complete API Environment" from dropdown
4. **Start API Server**: Run `python3 api_server.py` in terminal
5. **Test**: Run any request in the collection

### Available Tests
- **🎬 Upload Video & Generate PDF** - Upload video file and start processing
- **📋 List All Videos** - Get all videos with status
- **📊 Check Status** - Monitor processing progress
- **📄 Download PDF** - Download generated PDF files

### Environment Variables
- `API_BASE_URL`: Set to `http://localhost:9000` (default)
- `VIDEO_ID`: Automatically populated during testing

### Running Tests
```bash
# Option 1: Individual requests in Postman UI
# Option 2: Run entire collection
# Option 3: Command line with Newman
npm install -g newman
newman run postman-collections/Thakii_Complete_API.postman_collection.json \
  -e postman-collections/Thakii_Complete_API.postman_environment.json
```

---

## 🤝 Contributing

### Development Setup
```bash
git clone <repository-url>
cd thakii-worker-service
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints where possible
- Add docstrings to all functions
- Write unit tests for new features

### Pull Request Process
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0**.

### License Summary
- ✅ **Commercial use** - You can use this software for commercial purposes
- ✅ **Modification** - You can modify the source code
- ✅ **Distribution** - You can distribute the software
- ✅ **Patent use** - You can use any patents that may be related to the software
- ✅ **Private use** - You can use the software for private purposes

### Requirements
- 📄 **License and copyright notice** - Include the license and copyright notice with the software
- 📄 **State changes** - Document any changes made to the software
- 📄 **Disclose source** - Make the source code available when distributing
- 📄 **Same license** - Use the same license for derivative works

### Limitations
- ❌ **Liability** - The software comes without warranty or liability
- ❌ **Warranty** - No warranty is provided with the software

For the complete license text, see the full GNU General Public License v3.0 terms and conditions.

### Credits

- **Original PDF Engine**: Emilio Kartono
- **Cloud Integration & Subtitle Generation**: Enhanced by Thakii Team
- **Fonts**: [DejaVu Fonts](https://dejavu-fonts.github.io/)

---

## 🆘 Support

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'cv2'`
**Solution**: `pip install opencv-python`

**Issue**: Firebase authentication error
**Solution**: Ensure `firebase-service-account.json` is properly configured

**Issue**: S3 access denied
**Solution**: Check AWS credentials and bucket permissions

### Getting Help
- 📧 Email: support@thakii.dev
- 🐛 Issues: GitHub Issues tab
- 📖 Documentation: See `/docs` folder

---

**🎉 Ready to transform your lecture videos into comprehensive study materials!**
