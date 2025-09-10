#!/usr/bin/env python3
"""
Individual PDF Generation Script Tests
Tests each specific Python script that generates PDFs
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import tempfile

def setup_test_video():
    """Setup test video in current directory"""
    test_video = Path("test.mp4")
    
    # Try to copy from parent directory
    parent_test = Path("../test.mp4")
    if parent_test.exists():
        shutil.copy2(parent_test, test_video)
        print(f"✅ Copied test video: {test_video}")
        return test_video
    
    # Try to use the sample video
    sample_video = Path("samples/quick_test_video.mp4")
    if sample_video.exists():
        shutil.copy2(sample_video, test_video)
        print(f"✅ Using sample video: {test_video}")
        return test_video
    
    print("❌ No test video found")
    return None

def test_main_py_direct():
    """Test main.py directly with different options"""
    print("\n" + "="*60)
    print("🧪 TESTING: main.py (Direct Execution)")
    print("="*60)
    
    test_video = setup_test_video()
    if not test_video:
        return False
    
    lecture2pdf_path = Path("../backend/lecture2pdf-external")
    if not lecture2pdf_path.exists():
        print(f"❌ lecture2pdf-external not found")
        return False
    
    results = []
    
    # Test 1: Skip subtitles (simplest)
    print("\n📝 Test 1: main.py --skip-subtitles")
    try:
        output_pdf = Path("main_py_no_subtitles.pdf")
        cmd = [
            sys.executable, "-m", "src.main",
            str(test_video),
            "--skip-subtitles",
            "-o", str(output_pdf)
        ]
        
        print(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=lecture2pdf_path, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: Generated {output_pdf} ({size} bytes)")
            results.append(True)
        else:
            print(f"❌ FAILED: {result.stderr}")
            results.append(False)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        results.append(False)
    
    # Test 2: With subtitle generation
    print("\n📝 Test 2: main.py with subtitle generation")
    try:
        output_pdf = Path("main_py_with_subtitles.pdf")
        cmd = [
            sys.executable, "-m", "src.main",
            str(test_video),
            "-o", str(output_pdf)
        ]
        
        print(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=lecture2pdf_path, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: Generated {output_pdf} ({size} bytes)")
            results.append(True)
        else:
            print(f"❌ FAILED: {result.stderr}")
            results.append(False)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        results.append(False)
    
    return all(results)

def test_content_segment_builder():
    """Test ContentSegmentPdfBuilder class directly"""
    print("\n" + "="*60)
    print("🧪 TESTING: ContentSegmentPdfBuilder (Direct Class)")
    print("="*60)
    
    test_video = setup_test_video()
    if not test_video:
        return False
    
    try:
        # Add to Python path
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src")
        sys.path.insert(0, str(lecture2pdf_src))
        
        from content_segment_exporter import ContentSegmentPdfBuilder, ContentSegment
        import cv2
        
        # Extract frames from video
        print("📹 Extracting frames from video...")
        cap = cv2.VideoCapture(str(test_video))
        frames = []
        
        # Get frames at different intervals
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps if fps > 0 else 0
        
        print(f"Video info: {frame_count} frames, {fps:.2f} fps, {duration:.2f}s")
        
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
            text = f"Frame {i+1} at {timestamp}\\nTest content for PDF generation\\nThis is a sample lecture slide."
            segments.append(ContentSegment(frame, text))
        
        # Generate PDF
        print("📄 Generating PDF...")
        output_pdf = Path("content_segment_builder.pdf")
        builder = ContentSegmentPdfBuilder()
        builder.generate_pdf(segments, str(output_pdf))
        
        if output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: Generated {output_pdf} ({size} bytes)")
            return True
        else:
            print("❌ FAILED: PDF not created")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_video_segment_finder():
    """Test VideoSegmentFinder for frame extraction"""
    print("\n" + "="*60)
    print("🧪 TESTING: VideoSegmentFinder (Frame Extraction)")
    print("="*60)
    
    test_video = setup_test_video()
    if not test_video:
        return False
    
    try:
        # Add to Python path
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src")
        sys.path.insert(0, str(lecture2pdf_src))
        
        from video_segment_finder import VideoSegmentFinder
        import cv2
        
        print("🔍 Analyzing video for key frames...")
        finder = VideoSegmentFinder()
        frames_data = finder.get_best_segment_frames(str(test_video))
        
        if not frames_data:
            print("❌ No frames extracted")
            return False
        
        print(f"✅ Extracted {len(frames_data)} key frames")
        
        # Save sample frames
        for i, (frame_num, data) in enumerate(list(frames_data.items())[:3]):
            frame = data["frame"]
            timestamp = data.get("timestamp", f"frame_{frame_num}")
            
            output_image = Path(f"video_segment_frame_{i+1}.jpg")
            cv2.imwrite(str(output_image), frame)
            print(f"   Saved frame {i+1}: {output_image} (timestamp: {timestamp})")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_subtitle_generator():
    """Test SubtitleGenerator for transcription"""
    print("\n" + "="*60)
    print("🧪 TESTING: SubtitleGenerator (Transcription)")
    print("="*60)
    
    test_video = setup_test_video()
    if not test_video:
        return False
    
    try:
        # Add to Python path
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src")
        sys.path.insert(0, str(lecture2pdf_src))
        
        # Try to import and test subtitle generation
        print("🎤 Testing subtitle generation...")
        
        # Run subtitle generator script directly
        cmd = [
            sys.executable,
            "../backend/lecture2pdf-external/src/subtitle_generator.py",
            str(test_video)
        ]
        
        print(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        # Check for generated subtitle file
        video_base = test_video.stem
        srt_file = Path(f"{video_base}.srt")
        
        if srt_file.exists():
            size = srt_file.stat().st_size
            print(f"✅ SUCCESS: Generated {srt_file} ({size} bytes)")
            
            # Show first few lines
            with open(srt_file, 'r') as f:
                lines = f.readlines()[:10]
                print("   First few lines:")
                for line in lines:
                    print(f"   {line.strip()}")
            
            return True
        else:
            print(f"❌ FAILED: No subtitle file generated")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all individual script tests"""
    print("🚀 INDIVIDUAL PDF GENERATION SCRIPT TESTS")
    print("=" * 80)
    
    # Create output directory
    output_dir = Path("individual_test_outputs")
    output_dir.mkdir(exist_ok=True)
    os.chdir(output_dir)
    
    results = {}
    
    # Run each test
    results["main_py_direct"] = test_main_py_direct()
    results["content_segment_builder"] = test_content_segment_builder()
    results["video_segment_finder"] = test_video_segment_finder()
    results["subtitle_generator"] = test_subtitle_generator()
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 INDIVIDUAL TEST RESULTS SUMMARY")
    print("=" * 80)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:30} {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    # Show all generated files
    print(f"\n📁 Generated files in {output_dir}:")
    for file in sorted(output_dir.iterdir()):
        if file.is_file():
            size = file.stat().st_size
            print(f"   {file.name:40} ({size:,} bytes)")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
