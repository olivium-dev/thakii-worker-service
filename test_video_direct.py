#!/usr/bin/env python3
"""
Direct video test with OpenCV
"""

import cv2
import os
from pathlib import Path

def test_video_opencv():
    """Test if OpenCV can read the video file"""
    print("🎥 TESTING VIDEO WITH OPENCV")
    print("=" * 40)
    
    # Try different video paths
    video_paths = [
        "test.mp4",
        str(Path("test.mp4").absolute()),
        "../test.mp4",
        str(Path("../test.mp4").absolute()),
        "samples/quick_test_video.mp4",
        str(Path("samples/quick_test_video.mp4").absolute())
    ]
    
    for video_path in video_paths:
        print(f"\n📹 Testing: {video_path}")
        
        if not Path(video_path).exists():
            print(f"   ❌ File does not exist")
            continue
        
        # Get file size
        file_size = Path(video_path).stat().st_size
        print(f"   📊 File size: {file_size:,} bytes")
        
        # Try to open with OpenCV
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"   ❌ OpenCV cannot open video")
            cap.release()
            continue
        
        # Get video properties
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        
        print(f"   ✅ OpenCV can read video!")
        print(f"   📊 Properties:")
        print(f"      - Frames: {frame_count}")
        print(f"      - FPS: {fps:.2f}")
        print(f"      - Resolution: {width}x{height}")
        print(f"      - Duration: {duration:.2f}s")
        
        # Try to read first frame
        ret, frame = cap.read()
        if ret:
            print(f"   ✅ Successfully read first frame: {frame.shape}")
            
            # Save first frame as test
            output_frame = Path(f"test_frame_{Path(video_path).stem}.jpg")
            cv2.imwrite(str(output_frame), frame)
            print(f"   💾 Saved first frame: {output_frame}")
            
            cap.release()
            return video_path, True
        else:
            print(f"   ❌ Cannot read frames")
            cap.release()
    
    return None, False

def test_pdf_generation_with_working_video():
    """Test PDF generation with a working video path"""
    working_video, success = test_video_opencv()
    
    if not success:
        print("\n❌ No working video found for PDF generation")
        return False
    
    print(f"\n🎯 TESTING PDF GENERATION WITH: {working_video}")
    print("=" * 60)
    
    import subprocess
    import sys
    
    # Use absolute path for video
    abs_video_path = str(Path(working_video).absolute())
    abs_output_path = str(Path("direct_test_output.pdf").absolute())
    
    lecture2pdf_path = Path("../backend/lecture2pdf-external").absolute()
    
    cmd = [
        sys.executable, "-m", "src.main",
        abs_video_path,
        "--skip-subtitles",
        "-o", abs_output_path
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print(f"Working directory: {lecture2pdf_path}")
    print(f"Video path: {abs_video_path}")
    print(f"Output path: {abs_output_path}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=lecture2pdf_path,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        print(f"\nReturn code: {result.returncode}")
        
        if result.stdout:
            print("Output:")
            print(result.stdout)
        
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        
        if result.returncode == 0 and Path(abs_output_path).exists():
            size = Path(abs_output_path).stat().st_size
            print(f"✅ SUCCESS: Generated PDF!")
            print(f"   File: {abs_output_path}")
            print(f"   Size: {size:,} bytes")
            return True
        else:
            print("❌ FAILED: PDF not generated")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT: Process took too long")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("🚀 DIRECT VIDEO AND PDF GENERATION TEST")
    print("=" * 50)
    
    success = test_pdf_generation_with_working_video()
    
    if success:
        print("\n🎉 PDF generation test PASSED!")
        
        # List all generated files
        print("\n📁 Generated files:")
        for file in Path(".").iterdir():
            if file.suffix.lower() in ['.pdf', '.jpg']:
                size = file.stat().st_size
                print(f"   {file.name:30} ({size:,} bytes)")
    else:
        print("\n💥 PDF generation test FAILED!")
