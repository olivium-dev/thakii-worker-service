#!/usr/bin/env python3
"""
Generate PDFs using all available Python scripts
Uses the working approach from successful test
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import cv2

def setup_test_environment():
    """Setup test environment and video"""
    print("🔧 SETTING UP TEST ENVIRONMENT")
    print("=" * 50)
    
    # Create output directory
    output_dir = Path("pdf_outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Setup test video
    test_video = output_dir / "test.mp4"
    
    # Copy from parent directory
    parent_test = Path("../test.mp4")
    if parent_test.exists():
        shutil.copy2(parent_test, test_video)
        print(f"✅ Copied test video: {test_video}")
    elif Path("test.mp4").exists():
        shutil.copy2("test.mp4", test_video)
        print(f"✅ Using existing test video: {test_video}")
    else:
        print("❌ No test video found")
        return None, None
    
    # Verify video with OpenCV
    cap = cv2.VideoCapture(str(test_video))
    if not cap.isOpened():
        print("❌ OpenCV cannot read video")
        return None, None
    
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    
    print(f"✅ Video verified: {frame_count} frames, {fps:.1f} fps, {duration:.1f}s")
    
    return output_dir, test_video

def test_main_py_no_subtitles(output_dir, test_video):
    """Test main.py without subtitles"""
    print("\n" + "="*60)
    print("🧪 TEST 1: main.py --skip-subtitles")
    print("="*60)
    
    lecture2pdf_path = Path("../backend/lecture2pdf-external").absolute()
    if not lecture2pdf_path.exists():
        print(f"❌ lecture2pdf-external not found")
        return False
    
    output_pdf = output_dir / "main_py_no_subtitles.pdf"
    
    cmd = [
        sys.executable, "-m", "src.main",
        str(test_video.absolute()),
        "--skip-subtitles",
        "-o", str(output_pdf.absolute())
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, cwd=lecture2pdf_path, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: {output_pdf.name} ({size:,} bytes)")
            return True
        else:
            print(f"❌ FAILED:")
            if result.stdout: print(f"   stdout: {result.stdout}")
            if result.stderr: print(f"   stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_main_py_with_subtitles(output_dir, test_video):
    """Test main.py with subtitle generation"""
    print("\n" + "="*60)
    print("🧪 TEST 2: main.py with subtitles")
    print("="*60)
    
    lecture2pdf_path = Path("../backend/lecture2pdf-external").absolute()
    output_pdf = output_dir / "main_py_with_subtitles.pdf"
    
    cmd = [
        sys.executable, "-m", "src.main",
        str(test_video.absolute()),
        "-o", str(output_pdf.absolute())
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print("⚠️  Note: This may take several minutes for AI transcription...")
    
    try:
        result = subprocess.run(cmd, cwd=lecture2pdf_path, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: {output_pdf.name} ({size:,} bytes)")
            
            # Check for generated subtitle file
            video_stem = test_video.stem
            srt_files = list(output_dir.parent.glob(f"*{video_stem}*.srt"))
            if srt_files:
                for srt_file in srt_files:
                    srt_size = srt_file.stat().st_size
                    print(f"   📝 Generated subtitle: {srt_file.name} ({srt_size:,} bytes)")
            
            return True
        else:
            print(f"❌ FAILED:")
            if result.stdout: print(f"   stdout: {result.stdout}")
            if result.stderr: print(f"   stderr: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT: Subtitle generation took too long")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_content_segment_builder(output_dir, test_video):
    """Test ContentSegmentPdfBuilder directly"""
    print("\n" + "="*60)
    print("🧪 TEST 3: ContentSegmentPdfBuilder (Direct)")
    print("="*60)
    
    try:
        # Add lecture2pdf to path
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src").absolute()
        sys.path.insert(0, str(lecture2pdf_src))
        
        from content_segment_exporter import ContentSegmentPdfBuilder, ContentSegment
        
        # Extract frames from video
        print("📹 Extracting frames...")
        cap = cv2.VideoCapture(str(test_video))
        frames = []
        
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps if fps > 0 else 0
        
        # Extract 5 frames evenly spaced
        for i in range(5):
            frame_pos = int(i * frame_count / 5)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
        
        cap.release()
        
        if not frames:
            print("❌ No frames extracted")
            return False
        
        print(f"✅ Extracted {len(frames)} frames")
        
        # Create content segments
        segments = []
        for i, frame in enumerate(frames):
            timestamp = f"{i*duration/5:.1f}s"
            text = f"Frame {i+1} at {timestamp}\\n\\nTest content for PDF generation\\nThis is a sample lecture slide extracted from test.mp4\\n\\nGenerated using ContentSegmentPdfBuilder"
            segments.append(ContentSegment(frame, text))
        
        # Generate PDF
        output_pdf = output_dir / "content_segment_builder.pdf"
        builder = ContentSegmentPdfBuilder()
        builder.generate_pdf(segments, str(output_pdf))
        
        if output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: {output_pdf.name} ({size:,} bytes)")
            return True
        else:
            print("❌ FAILED: PDF not created")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_video_segment_finder(output_dir, test_video):
    """Test VideoSegmentFinder for frame extraction"""
    print("\n" + "="*60)
    print("🧪 TEST 4: VideoSegmentFinder (Frame Analysis)")
    print("="*60)
    
    try:
        # Add lecture2pdf to path
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src").absolute()
        sys.path.insert(0, str(lecture2pdf_src))
        
        from video_segment_finder import VideoSegmentFinder
        
        print("🔍 Analyzing video for key frames...")
        finder = VideoSegmentFinder()
        frames_data = finder.get_best_segment_frames(str(test_video))
        
        if not frames_data:
            print("❌ No frames extracted")
            return False
        
        print(f"✅ Extracted {len(frames_data)} key frames")
        
        # Save sample frames
        saved_frames = 0
        for i, (frame_num, data) in enumerate(list(frames_data.items())[:5]):
            frame = data["frame"]
            timestamp = data.get("timestamp", f"frame_{frame_num}")
            
            output_image = output_dir / f"video_segment_frame_{i+1}.jpg"
            cv2.imwrite(str(output_image), frame)
            saved_frames += 1
            
            size = output_image.stat().st_size
            print(f"   💾 Frame {i+1}: {output_image.name} ({size:,} bytes) - {timestamp}")
        
        print(f"✅ SUCCESS: Saved {saved_frames} key frames")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_subtitle_generator(output_dir, test_video):
    """Test subtitle generation"""
    print("\n" + "="*60)
    print("🧪 TEST 5: SubtitleGenerator (AI Transcription)")
    print("="*60)
    
    try:
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src").absolute()
        
        # Test subtitle generation script
        subtitle_script = lecture2pdf_src / "subtitle_generator.py"
        if not subtitle_script.exists():
            print(f"❌ Subtitle generator not found: {subtitle_script}")
            return False
        
        print("🎤 Generating subtitles with AI...")
        print("⚠️  Note: This may take several minutes...")
        
        # Change to output directory for subtitle generation
        original_cwd = os.getcwd()
        os.chdir(output_dir)
        
        cmd = [sys.executable, str(subtitle_script), str(test_video.absolute())]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        os.chdir(original_cwd)
        
        # Look for generated subtitle files
        srt_files = list(output_dir.glob("*.srt"))
        vtt_files = list(output_dir.glob("*.vtt"))
        
        if srt_files or vtt_files:
            print("✅ SUCCESS: Subtitle files generated:")
            for srt_file in srt_files:
                size = srt_file.stat().st_size
                print(f"   📝 {srt_file.name} ({size:,} bytes)")
            for vtt_file in vtt_files:
                size = vtt_file.stat().st_size
                print(f"   📝 {vtt_file.name} ({size:,} bytes)")
            
            # Show first few lines of first subtitle file
            if srt_files:
                with open(srt_files[0], 'r') as f:
                    lines = f.readlines()[:6]
                    print("   First few lines:")
                    for line in lines:
                        print(f"   {line.strip()}")
            
            return True
        else:
            print(f"❌ FAILED: No subtitle files generated")
            if result.stdout: print(f"   stdout: {result.stdout}")
            if result.stderr: print(f"   stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT: Subtitle generation took too long")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run all PDF generation tests"""
    print("🚀 COMPREHENSIVE PDF GENERATION TESTS")
    print("=" * 80)
    print("Testing all Python scripts that convert test.mp4 to PDF")
    print("=" * 80)
    
    # Setup
    output_dir, test_video = setup_test_environment()
    if not output_dir or not test_video:
        return False
    
    # Run all tests
    results = {}
    results["main_py_no_subtitles"] = test_main_py_no_subtitles(output_dir, test_video)
    results["main_py_with_subtitles"] = test_main_py_with_subtitles(output_dir, test_video)
    results["content_segment_builder"] = test_content_segment_builder(output_dir, test_video)
    results["video_segment_finder"] = test_video_segment_finder(output_dir, test_video)
    results["subtitle_generator"] = test_subtitle_generator(output_dir, test_video)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 COMPREHENSIVE TEST RESULTS")
    print("=" * 80)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:30} {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    # Show all generated files
    print(f"\n📁 ALL GENERATED FILES in {output_dir}:")
    print("=" * 50)
    
    all_files = []
    for file in sorted(output_dir.iterdir()):
        if file.is_file():
            size = file.stat().st_size
            file_type = "📄 PDF" if file.suffix == '.pdf' else "🖼️  IMG" if file.suffix in ['.jpg', '.png'] else "📝 SUB" if file.suffix in ['.srt', '.vtt'] else "📁 FILE"
            all_files.append((file.name, size, file_type))
    
    for name, size, file_type in all_files:
        print(f"{file_type} {name:35} ({size:,} bytes)")
    
    if passed_tests > 0:
        print(f"\n🎉 SUCCESS: Generated {len([f for f in all_files if 'PDF' in f[2]])} PDF files from test.mp4!")
    
    return passed_tests > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
