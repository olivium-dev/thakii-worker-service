#!/usr/bin/env python3
"""
Enhanced Thakii Worker Service
Uses the superior original repository's PDF generation algorithms
"""

import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# Add pdf_engine to Python path
pdf_engine_path = Path(__file__).parent / "pdf_engine" / "src"
sys.path.insert(0, str(pdf_engine_path))

def test_superior_pdf_generation():
    """Test the superior PDF generation from original repo"""
    print("🧪 Testing Superior PDF Generation")
    print("=" * 40)
    
    try:
        # Import superior modules
        from video_segment_finder import VideoSegmentFinder
        from content_segment_exporter import ContentSegment, ContentSegmentPdfBuilder
        
        print("✅ Superior modules imported successfully")
        
        # Test with our video
        test_video = Path("test.mp4")
        if not test_video.exists():
            print("❌ test.mp4 not found")
            return False
        
        print(f"📹 Processing: {test_video}")
        
        # Use superior frame detection
        video_segment_finder = VideoSegmentFinder()
        selected_frames_data = video_segment_finder.get_best_segment_frames(str(test_video))
        
        if not selected_frames_data:
            print("❌ No frames extracted")
            return False
        
        frame_nums = sorted(selected_frames_data.keys())
        selected_frames = [selected_frames_data[i]["frame"] for i in frame_nums]
        
        print(f"✅ Superior algorithm extracted {len(selected_frames)} frames")
        
        # Create enhanced content segments
        video_subtitle_pages = []
        for i, frame in enumerate(selected_frames):
            timestamp = selected_frames_data[frame_nums[i]].get("timestamp", f"Frame {i+1}")
            content_text = f"ENHANCED FRAME {i+1}\\nTimestamp: {timestamp}\\n\\nGenerated with superior algorithms\\nfrom original repository"
            video_subtitle_pages.append(ContentSegment(frame, content_text))
        
        # Generate superior PDF
        output_pdf = Path("ENHANCED_SUPERIOR_PDF.pdf")
        pdf_builder = ContentSegmentPdfBuilder()
        pdf_builder.generate_pdf(video_subtitle_pages, str(output_pdf))
        
        if output_pdf.exists():
            size = output_pdf.stat().st_size
            print(f"✅ SUCCESS: Enhanced PDF generated!")
            print(f"   File: {output_pdf}")
            print(f"   Size: {size:,} bytes")
            print(f"   Frames: {len(selected_frames)}")
            return True
        else:
            print("❌ PDF not created")
            return False
            
    except Exception as e:
        print(f"💥 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_superior_pdf_generation()
    sys.exit(0 if success else 1)
