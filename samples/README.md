# Sample Videos for Worker Testing

This directory contains sample video files for testing the Thakii Worker Service video processing pipeline.

## Files

### `quick_test_video.mp4`
- **Size**: ~513 KB
- **Purpose**: Quick testing of worker video processing capabilities
- **Usage**: Test file for worker processing, subtitle generation, and PDF creation

## Usage Examples

### Direct Worker Testing
```bash
# Test worker processing directly
python3 worker.py --video-id TEST_ID --input samples/quick_test_video.mp4

# Test with specific output directory
python3 worker.py --video-id TEST_ID --input samples/quick_test_video.mp4 --output ./output/
```

### Integration Testing
```bash
# Upload via backend API (triggers worker)
curl -X POST \
  -H "Authorization: Bearer thakii-mock-prod-token" \
  -F "file=@samples/quick_test_video.mp4" \
  https://thakii-02.fanusdigital.site/upload

# Monitor worker processing
tail -f worker.log
```

### Local Development
```bash
# Test subtitle generation
python3 -c "
from core.subtitle_generator import SubtitleGenerator
gen = SubtitleGenerator()
gen.generate_subtitles('samples/quick_test_video.mp4', 'output.srt')
"

# Test PDF generation
python3 -c "
from core.pdf_generator import PDFGenerator
gen = PDFGenerator()
gen.create_pdf('samples/quick_test_video.mp4', 'output.srt', 'output.pdf')
"
```

## Worker Pipeline Testing

These sample files are used for:
- ✅ **Video Processing** - Test video download and handling
- ✅ **Subtitle Generation** - Whisper AI transcription testing
- ✅ **PDF Creation** - Video-to-PDF conversion validation
- ✅ **S3 Integration** - Upload/download functionality testing
- ✅ **Firestore Updates** - Status tracking and coordination

## Processing Pipeline

```
Input Video → Subtitle Generation → PDF Creation → S3 Upload → Status Update
     ↓              ↓                    ↓            ↓           ↓
samples/     Whisper AI          lecture2pdf     AWS S3    Firestore
quick_test   transcription       engine          storage   coordination
video.mp4    (.srt file)         (.pdf file)     (cloud)   (database)
```

## Performance Benchmarks

Use these samples to establish performance baselines:
- **Video Duration**: ~X seconds
- **Expected Processing Time**: ~Y seconds
- **Subtitle Generation**: ~Z seconds
- **PDF Creation**: ~W seconds

## File Management

- **Keep files small** - For quick testing and CI/CD
- **Document processing times** - For performance monitoring
- **Update benchmarks** - When optimizing worker performance
- **Add variety** - Different video formats, lengths, content types
