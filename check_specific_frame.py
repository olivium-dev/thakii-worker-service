#!/usr/bin/env python3
"""
Check specific frame #3 that was identified as white
"""

import os
import sys
import cv2
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from video_segment_finder import VideoSegmentFinder

def check_frame_3():
    """Check frame #3 specifically"""
    
    video_path = "tests/videos/input_11.mp4"
    
    # Create finder with real sample mode
    finder = VideoSegmentFinder()
    finder.real_sample_mode = True
    
    # Open video and go to frame 3
    video_reader = cv2.VideoCapture(video_path)
    video_reader.set(cv2.CAP_PROP_POS_FRAMES, 3)
    
    ret, frame = video_reader.read()
    if ret:
        # Test white frame detection
        is_white = finder.__is_white_or_blank_frame__(frame)
        
        # Calculate manual stats
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)
        
        print(f"Frame #3 analysis:")
        print(f"  Is white detected: {is_white}")
        print(f"  Mean brightness: {mean_brightness:.1f}")
        print(f"  Std brightness: {std_brightness:.1f}")
        print(f"  White criteria: brightness > 240 AND std < 20")
        print(f"  Low content criteria: std < 10")
        
        # Check individual criteria
        is_bright = mean_brightness > 240
        is_low_std = std_brightness < 20
        is_very_low_std = std_brightness < 10
        
        print(f"  Brightness > 240: {is_bright}")
        print(f"  Std < 20: {is_low_std}")
        print(f"  Std < 10: {is_very_low_std}")
        
        # Save frame for inspection
        cv2.imwrite("frame_3_analysis.jpg", frame)
        print(f"  Frame saved as: frame_3_analysis.jpg")
    
    video_reader.release()

if __name__ == "__main__":
    check_frame_3()
