# PDF Generation Testing Suite

This directory contains comprehensive tests for all Python scripts that can generate PDFs from video files in the Thakii system.

## Test Scripts

### 1. `test_pdf_generation.py`
**Comprehensive test suite** that tests all PDF generation components:
- `lecture2pdf main.py` - Core PDF generation engine
- `ContentSegmentPdfBuilder` - Direct PDF builder class
- `VideoSegmentFinder` - Frame extraction component  
- `worker.py` - Worker orchestration (dry run)

### 2. `test_individual_scripts.py`
**Individual component tests** with detailed output:
- Direct execution of each script
- Frame extraction and analysis
- Subtitle generation testing
- PDF creation with different options

### 3. `run_pdf_tests.sh`
**Shell script** to set up environment and run tests

## Usage

### Quick Test (Recommended)
```bash
# Run comprehensive tests
python3 test_individual_scripts.py
```

### Full Test Suite
```bash
# Run all tests with setup
chmod +x run_pdf_tests.sh
./run_pdf_tests.sh
```

### Manual Testing
```bash
# Test main PDF engine directly
cd ../backend/lecture2pdf-external
python3 -m src.main ../../../thakii-worker-service/samples/quick_test_video.mp4 --skip-subtitles -o test_output.pdf

# Test with subtitle generation
python3 -m src.main ../../../thakii-worker-service/samples/quick_test_video.mp4 -o test_with_subs.pdf
```

## Expected Outputs

### Successful Test Run Should Generate:
- `main_py_no_subtitles.pdf` - PDF without subtitles
- `main_py_with_subtitles.pdf` - PDF with AI-generated subtitles
- `content_segment_builder.pdf` - PDF from direct class usage
- `video_segment_frame_*.jpg` - Extracted key frames
- `*.srt` - Generated subtitle files

### File Sizes (Approximate)
- PDF files: 50KB - 2MB (depending on video length and frames)
- Subtitle files: 1KB - 10KB (depending on speech content)
- Frame images: 50KB - 200KB each

## Test Video Requirements

Tests use `test.mp4` from the parent directory or `samples/quick_test_video.mp4`.

**Video should have:**
- Duration: 10-60 seconds (for quick testing)
- Resolution: Any (will be processed appropriately)
- Content: Preferably with speech for subtitle testing
- Format: MP4, AVI, MOV (supported by OpenCV)

## Dependencies

Required packages (auto-installed by test scripts):
```
opencv-python
fpdf2
whisper
torch
numpy
pillow
```

## Troubleshooting

### Common Issues:

1. **Import Errors**
   ```bash
   # Install missing packages
   pip install opencv-python fpdf2 whisper torch numpy pillow
   ```

2. **Video Not Found**
   ```bash
   # Copy test video to correct location
   cp /path/to/your/video.mp4 test.mp4
   ```

3. **Permission Errors**
   ```bash
   # Make scripts executable
   chmod +x *.py *.sh
   ```

4. **Timeout Errors**
   - Use shorter video files (< 60 seconds)
   - Increase timeout in test scripts if needed

### Debug Mode
```bash
# Run with verbose output
python3 -v test_individual_scripts.py

# Check specific component
python3 -c "
import sys
sys.path.append('../backend/lecture2pdf-external/src')
from video_segment_finder import VideoSegmentFinder
finder = VideoSegmentFinder()
print('VideoSegmentFinder imported successfully')
"
```

## Test Results Interpretation

### ✅ PASS Criteria:
- PDF files generated successfully
- File sizes > 0 bytes
- No Python exceptions
- Expected output files created

### ❌ FAIL Indicators:
- Missing output files
- Zero-byte files
- Python import/execution errors
- Timeout errors

### Performance Benchmarks:
- Frame extraction: < 30 seconds
- Subtitle generation: < 60 seconds  
- PDF creation: < 30 seconds
- Total pipeline: < 2 minutes

## Integration with Worker Service

These tests validate the core components used by:
- `worker.py` - Main worker orchestration
- Backend API trigger system
- Production video processing pipeline

Successful tests indicate the PDF generation pipeline is ready for production use.
