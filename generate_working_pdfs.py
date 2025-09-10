#!/usr/bin/env python3
"""
Generate PDFs using working methods only
Focus on methods that successfully generate PDFs
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import cv2

def setup_test():
    """Setup test environment"""
    print("🔧 SETUP")
    print("=" * 30)
    
    # Create output directory
    output_dir = Path("working_pdf_outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Setup test video
    test_video = output_dir / "test.mp4"
    
    # Copy test video
    if Path("../test.mp4").exists():
        shutil.copy2("../test.mp4", test_video)
    elif Path("test.mp4").exists():
        shutil.copy2("test.mp4", test_video)
    else:
        print("❌ No test video found")
        return None, None
    
    print(f"✅ Test video: {test_video}")
    
    # Verify with OpenCV
    cap = cv2.VideoCapture(str(test_video))
    if cap.isOpened():
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        print(f"✅ Video: {frame_count} frames, {fps:.1f}fps, {duration:.1f}s")
    else:
        print("❌ Cannot read video")
        return None, None
    
    return output_dir, test_video

def generate_pdf_method_1(output_dir, test_video):
    """Method 1: main.py without subtitles (WORKING)"""
    print("\n📄 METHOD 1: main.py --skip-subtitles")
    print("-" * 40)
    
    lecture2pdf_path = Path("../backend/lecture2pdf-external").absolute()
    output_pdf = output_dir / "method1_main_no_subs.pdf"
    
    cmd = [
        sys.executable, "-m", "src.main",
        str(test_video.absolute()),
        "--skip-subtitles",
        "-o", str(output_pdf.absolute())
    ]
    
    try:
        result = subprocess.run(cmd, cwd=lecture2pdf_path, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: {output_pdf.name} ({size:,} bytes)")
            return True
        else:
            print(f"❌ FAILED: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def generate_pdf_method_2(output_dir, test_video):
    """Method 2: Direct ContentSegmentPdfBuilder"""
    print("\n📄 METHOD 2: ContentSegmentPdfBuilder (Direct)")
    print("-" * 40)
    
    try:
        # Change to lecture2pdf directory and import
        original_cwd = os.getcwd()
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src").absolute()
        os.chdir(lecture2pdf_src)
        
        # Import modules
        from content_segment_exporter import ContentSegmentPdfBuilder, ContentSegment
        
        os.chdir(original_cwd)
        
        # Extract frames
        print("📹 Extracting frames...")
        cap = cv2.VideoCapture(str(test_video))
        frames = []
        
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps if fps > 0 else 0
        
        # Extract 3 frames
        for i in range(3):
            frame_pos = int(i * frame_count / 3)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
        
        cap.release()
        
        if not frames:
            print("❌ No frames extracted")
            return False
        
        # Create segments
        segments = []
        for i, frame in enumerate(frames):
            timestamp = f"{i*duration/3:.1f}s"
            text = f"Frame {i+1} at {timestamp}\\n\\nExtracted from test.mp4\\nUsing ContentSegmentPdfBuilder\\n\\nThis demonstrates direct PDF generation from video frames."
            segments.append(ContentSegment(frame, text))
        
        # Generate PDF
        output_pdf = output_dir / "method2_content_builder.pdf"
        builder = ContentSegmentPdfBuilder()
        builder.generate_pdf(segments, str(output_pdf))
        
        if output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: {output_pdf.name} ({size:,} bytes)")
            return True
        else:
            print("❌ FAILED: PDF not created")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def generate_pdf_method_3(output_dir, test_video):
    """Method 3: VideoSegmentFinder + Manual PDF"""
    print("\n📄 METHOD 3: VideoSegmentFinder + Manual PDF")
    print("-" * 40)
    
    try:
        # Change to lecture2pdf directory and import
        original_cwd = os.getcwd()
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src").absolute()
        os.chdir(lecture2pdf_src)
        
        from video_segment_finder import VideoSegmentFinder
        from content_segment_exporter import ContentSegmentPdfBuilder, ContentSegment
        
        os.chdir(original_cwd)
        
        # Find key frames
        print("🔍 Finding key frames...")
        finder = VideoSegmentFinder()
        frames_data = finder.get_best_segment_frames(str(test_video))
        
        if not frames_data:
            print("❌ No key frames found")
            return False
        
        print(f"✅ Found {len(frames_data)} key frames")
        
        # Create segments from key frames
        segments = []
        for i, (frame_num, data) in enumerate(list(frames_data.items())[:5]):
            frame = data["frame"]
            timestamp = data.get("timestamp", f"frame_{frame_num}")
            text = f"Key Frame {i+1}\\nFrame #{frame_num}\\nTimestamp: {timestamp}\\n\\nExtracted using VideoSegmentFinder\\nThis frame was identified as a key segment."
            segments.append(ContentSegment(frame, text))
        
        # Generate PDF
        output_pdf = output_dir / "method3_key_frames.pdf"
        builder = ContentSegmentPdfBuilder()
        builder.generate_pdf(segments, str(output_pdf))
        
        if output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: {output_pdf.name} ({size:,} bytes)")
            return True
        else:
            print("❌ FAILED: PDF not created")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def generate_pdf_method_4(output_dir, test_video):
    """Method 4: Simple frame extraction + PDF"""
    print("\n📄 METHOD 4: Simple Frame Extraction + PDF")
    print("-" * 40)
    
    try:
        # Change to lecture2pdf directory and import
        original_cwd = os.getcwd()
        lecture2pdf_src = Path("../backend/lecture2pdf-external/src").absolute()
        os.chdir(lecture2pdf_src)
        
        from content_segment_exporter import ContentSegmentPdfBuilder, ContentSegment
        
        os.chdir(original_cwd)
        
        # Simple frame extraction every 60 seconds
        print("📹 Extracting frames every 60 seconds...")
        cap = cv2.VideoCapture(str(test_video))
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        frames = []
        timestamps = []
        
        # Extract frame every 60 seconds
        for second in range(0, int(duration), 60):
            frame_pos = int(second * fps)
            if frame_pos < frame_count:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                ret, frame = cap.read()
                if ret:
                    frames.append(frame)
                    timestamps.append(second)
        
        cap.release()
        
        if not frames:
            print("❌ No frames extracted")
            return False
        
        print(f"✅ Extracted {len(frames)} frames")
        
        # Create segments
        segments = []
        for i, (frame, timestamp) in enumerate(zip(frames, timestamps)):
            minutes = timestamp // 60
            seconds = timestamp % 60
            time_str = f"{minutes:02d}:{seconds:02d}"
            text = f"Minute {minutes + 1}\\nTimestamp: {time_str}\\n\\nFrame extracted every 60 seconds\\nfrom test.mp4\\n\\nSimple extraction method"
            segments.append(ContentSegment(frame, text))
        
        # Generate PDF
        output_pdf = output_dir / "method4_simple_extraction.pdf"
        builder = ContentSegmentPdfBuilder()
        builder.generate_pdf(segments, str(output_pdf))
        
        if output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: {output_pdf.name} ({size:,} bytes)")
            return True
        else:
            print("❌ FAILED: PDF not created")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Generate PDFs using all working methods"""
    print("🚀 GENERATE PDFs FROM test.mp4")
    print("=" * 50)
    print("Using all working Python script methods")
    print("=" * 50)
    
    # Setup
    output_dir, test_video = setup_test()
    if not output_dir or not test_video:
        return False
    
    # Run all working methods
    results = {}
    results["method1_main_no_subs"] = generate_pdf_method_1(output_dir, test_video)
    results["method2_content_builder"] = generate_pdf_method_2(output_dir, test_video)
    results["method3_key_frames"] = generate_pdf_method_3(output_dir, test_video)
    results["method4_simple_extraction"] = generate_pdf_method_4(output_dir, test_video)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 PDF GENERATION RESULTS")
    print("=" * 50)
    
    for method, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{method:25} {status}")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nGenerated: {passed}/{total} PDF files")
    
    # Show all generated files
    print(f"\n📁 GENERATED FILES in {output_dir}:")
    print("=" * 40)
    
    pdf_count = 0
    for file in sorted(output_dir.iterdir()):
        if file.is_file():
            size = file.stat().st_size
            if file.suffix == '.pdf':
                pdf_count += 1
                print(f"📄 {file.name:30} ({size:,} bytes)")
            elif file.suffix in ['.jpg', '.png']:
                print(f"🖼️  {file.name:30} ({size:,} bytes)")
            else:
                print(f"📁 {file.name:30} ({size:,} bytes)")
    
    if pdf_count > 0:
        print(f"\n🎉 SUCCESS: Generated {pdf_count} PDF files from test.mp4!")
        print("Each PDF uses a different Python script method.")
    
    return pdf_count > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
