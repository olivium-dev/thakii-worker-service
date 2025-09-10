#!/usr/bin/env python3
"""
Test PDF Generation Scripts
Tests each Python script that can generate PDFs from video files
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def setup_test_environment():
    """Create test directory and copy test video"""
    test_dir = Path("pdf_generation_tests")
    test_dir.mkdir(exist_ok=True)
    
    # Copy test.mp4 from parent directory
    test_video_source = Path("../test.mp4")
    test_video_dest = test_dir / "test.mp4"
    
    if test_video_source.exists():
        shutil.copy2(test_video_source, test_video_dest)
        print(f"✅ Copied {test_video_source} to {test_video_dest}")
    else:
        print(f"❌ Test video not found at {test_video_source}")
        return None
    
    return test_dir, test_video_dest

def test_lecture2pdf_main():
    """Test the main lecture2pdf engine"""
    print("\n🧪 Testing lecture2pdf main.py...")
    
    lecture2pdf_path = Path("../backend/lecture2pdf-external")
    if not lecture2pdf_path.exists():
        print(f"❌ lecture2pdf-external not found at {lecture2pdf_path}")
        return False
    
    test_dir, test_video = setup_test_environment()
    if not test_video:
        return False
    
    output_pdf = test_dir / "main_py_output.pdf"
    
    try:
        # Test with skip-subtitles flag first (simpler)
        cmd = [
            sys.executable, "-m", "src.main",
            str(test_video),
            "--skip-subtitles",
            "-o", str(output_pdf)
        ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=lecture2pdf_path,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0 and output_pdf.exists():
            print(f"✅ main.py generated PDF: {output_pdf}")
            print(f"   Size: {output_pdf.stat().st_size} bytes")
            return True
        else:
            print(f"❌ main.py failed:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ main.py timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ main.py error: {e}")
        return False

def test_content_segment_exporter():
    """Test the ContentSegmentPdfBuilder directly"""
    print("\n🧪 Testing ContentSegmentPdfBuilder...")
    
    try:
        # Add lecture2pdf to path
        lecture2pdf_path = Path("../backend/lecture2pdf-external/src")
        sys.path.insert(0, str(lecture2pdf_path))
        
        from content_segment_exporter import ContentSegmentPdfBuilder, ContentSegment
        import cv2
        import numpy as np
        
        test_dir, test_video = setup_test_environment()
        if not test_video:
            return False
        
        # Create a simple test with dummy frames
        output_pdf = test_dir / "content_segment_output.pdf"
        
        # Load video and extract a few frames
        cap = cv2.VideoCapture(str(test_video))
        frames = []
        
        for i in range(3):  # Extract 3 frames
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
            else:
                break
        
        cap.release()
        
        if not frames:
            print("❌ Could not extract frames from video")
            return False
        
        # Create content segments
        segments = []
        for i, frame in enumerate(frames):
            text = f"Frame {i+1}: Test content for PDF generation"
            segments.append(ContentSegment(frame, text))
        
        # Generate PDF
        builder = ContentSegmentPdfBuilder()
        builder.generate_pdf(segments, str(output_pdf))
        
        if output_pdf.exists():
            print(f"✅ ContentSegmentPdfBuilder generated PDF: {output_pdf}")
            print(f"   Size: {output_pdf.stat().st_size} bytes")
            return True
        else:
            print("❌ ContentSegmentPdfBuilder failed to create PDF")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ ContentSegmentPdfBuilder error: {e}")
        return False

def test_worker_script():
    """Test the worker.py script (if possible without full infrastructure)"""
    print("\n🧪 Testing worker.py (dry run)...")
    
    try:
        # Read worker.py to understand its structure
        worker_path = Path("worker.py")
        if not worker_path.exists():
            print("❌ worker.py not found")
            return False
        
        with open(worker_path, 'r') as f:
            content = f.read()
        
        # Check if it has the process_video function
        if "def process_video" in content:
            print("✅ worker.py has process_video function")
            print("   Note: Full test requires Firestore/S3 setup")
            return True
        else:
            print("❌ worker.py missing process_video function")
            return False
            
    except Exception as e:
        print(f"❌ worker.py analysis error: {e}")
        return False

def test_video_segment_finder():
    """Test VideoSegmentFinder for frame extraction"""
    print("\n🧪 Testing VideoSegmentFinder...")
    
    try:
        # Add lecture2pdf to path
        lecture2pdf_path = Path("../backend/lecture2pdf-external/src")
        sys.path.insert(0, str(lecture2pdf_path))
        
        from video_segment_finder import VideoSegmentFinder
        
        test_dir, test_video = setup_test_environment()
        if not test_video:
            return False
        
        # Test frame extraction
        finder = VideoSegmentFinder()
        frames_data = finder.get_best_segment_frames(str(test_video))
        
        if frames_data and len(frames_data) > 0:
            print(f"✅ VideoSegmentFinder extracted {len(frames_data)} frames")
            
            # Save first frame as test
            first_frame_data = list(frames_data.values())[0]
            frame = first_frame_data["frame"]
            
            import cv2
            output_image = test_dir / "video_segment_finder_frame.jpg"
            cv2.imwrite(str(output_image), frame)
            print(f"   Saved sample frame: {output_image}")
            return True
        else:
            print("❌ VideoSegmentFinder failed to extract frames")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ VideoSegmentFinder error: {e}")
        return False

def main():
    """Run all PDF generation tests"""
    print("🚀 Starting PDF Generation Tests")
    print("=" * 50)
    
    results = {}
    
    # Test each script
    results["lecture2pdf_main"] = test_lecture2pdf_main()
    results["content_segment_exporter"] = test_content_segment_exporter()
    results["worker_script"] = test_worker_script()
    results["video_segment_finder"] = test_video_segment_finder()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:25} {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed - check output above")
    
    # Show generated files
    test_dir = Path("pdf_generation_tests")
    if test_dir.exists():
        print(f"\n📁 Generated files in {test_dir}:")
        for file in test_dir.iterdir():
            if file.is_file():
                size = file.stat().st_size
                print(f"   {file.name} ({size} bytes)")

if __name__ == "__main__":
    main()
