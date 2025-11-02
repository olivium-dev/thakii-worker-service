#!/usr/bin/env python3
"""
Direct test of video processing without Redis or Worker
"""

import os
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def main():
    """Process a local test video file directly using src.main"""
    # Check for test video file
    test_video = "tests/videos/input_1.mp4"
    if not os.path.exists(test_video):
        print(f"❌ Test video not found: {test_video}")
        return False
    
    # Generate a unique video ID
    video_id = f"test-{uuid.uuid4().hex[:8]}"
    filename = os.path.basename(test_video)
    
    print(f"🎬 Processing local test video: {test_video}")
    print(f"🆔 Video ID: {video_id}")
    
    # Create a temporary directory and copy the test video
    import tempfile
    import shutil
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy the test video to the temp directory
        temp_video = os.path.join(temp_dir, filename)
        shutil.copy(test_video, temp_video)
        
        print(f"📁 Copied test video to: {temp_video}")
        
        # Create a PDF output path
        pdf_path = os.path.join(temp_dir, f"{video_id}.pdf")
        
        # Generate PDF directly
        try:
            # Import here to avoid worker initialization issues
            from src.main import CommandLineArgRunner
            runner = CommandLineArgRunner()
            
            print(f"🔄 Generating PDF from video...")
            runner.run([temp_video, "-o", pdf_path])
            
            if os.path.exists(pdf_path):
                print(f"✅ PDF generated successfully: {pdf_path}")
                # Copy the PDF to a more permanent location
                output_dir = "output"
                os.makedirs(output_dir, exist_ok=True)
                output_pdf = os.path.join(output_dir, f"{video_id}.pdf")
                shutil.copy(pdf_path, output_pdf)
                print(f"✅ PDF copied to: {output_pdf}")
                return True
            else:
                print(f"❌ PDF generation failed: {pdf_path} not found")
                return False
        except Exception as e:
            print(f"❌ PDF generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)