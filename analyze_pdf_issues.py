#!/usr/bin/env python3
"""
Analyze the PDF generation issues:
1. First white page
2. Duplicated pages (5 and 6)
3. Missing final page
"""

import os
import sys
import cv2
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from video_segment_finder import VideoSegmentFinder

def analyze_frame_content(frame):
    """Analyze frame content to detect white/blank frames and similar frames"""
    
    # Convert to grayscale for analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Calculate statistics
    mean_brightness = np.mean(gray)
    std_brightness = np.std(gray)
    
    # Check if frame is mostly white (blank)
    is_white = mean_brightness > 240 and std_brightness < 20
    
    # Check if frame has very low content (mostly uniform)
    is_low_content = std_brightness < 10
    
    return {
        'mean_brightness': mean_brightness,
        'std_brightness': std_brightness,
        'is_white': is_white,
        'is_low_content': is_low_content,
        'content_score': std_brightness  # Higher = more content
    }

def compare_frame_similarity(frame1, frame2):
    """Compare similarity between two frames"""
    
    # Convert to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Calculate absolute difference
    diff = cv2.absdiff(gray1, gray2)
    
    # Calculate similarity metrics
    mean_diff = np.mean(diff)
    max_diff = np.max(diff)
    pixels_changed = np.sum(diff > 10)  # Pixels with noticeable change
    
    # Similarity score (0 = identical, higher = more different)
    similarity_score = mean_diff + (pixels_changed / diff.size) * 100
    
    return {
        'mean_diff': mean_diff,
        'max_diff': max_diff,
        'pixels_changed': pixels_changed,
        'similarity_score': similarity_score,
        'is_duplicate': similarity_score < 5  # Very similar frames
    }

def analyze_selected_frames(video_path):
    """Analyze the selected frames from real sample optimized approach"""
    
    print(f"🔍 Analyzing selected frames from: {video_path}")
    print("=" * 80)
    
    # Get frames using real sample optimized approach
    finder = VideoSegmentFinder(use_quarter_based_analysis=False)
    finder.real_sample_mode = True  # Enable real sample mode
    
    frames_data, _ = finder.get_segment_frames_with_stats(video_path)
    
    print(f"📊 Analysis of {len(frames_data)} selected frames:")
    print("-" * 50)
    
    frame_analysis = []
    
    # Analyze each selected frame
    for i, (frame_num, frame_data) in enumerate(sorted(frames_data.items())):
        frame = frame_data['frame']
        timestamp = frame_data['timestamp']
        pixels_changed = frame_data['num_pixels_changed']
        
        # Analyze frame content
        content_analysis = analyze_frame_content(frame)
        
        frame_info = {
            'index': i,
            'frame_num': frame_num,
            'timestamp': timestamp,
            'timestamp_s': timestamp / 1000,
            'pixels_changed': pixels_changed,
            'frame': frame,
            **content_analysis
        }
        
        frame_analysis.append(frame_info)
        
        # Print frame info
        status_flags = []
        if content_analysis['is_white']:
            status_flags.append("WHITE")
        if content_analysis['is_low_content']:
            status_flags.append("LOW_CONTENT")
        
        status = f" [{', '.join(status_flags)}]" if status_flags else ""
        
        print(f"  Frame {i+1:2d}: #{frame_num:5d} at {timestamp/1000:6.1f}s - "
              f"brightness={content_analysis['mean_brightness']:5.1f}, "
              f"content={content_analysis['content_score']:5.1f}, "
              f"changed={pixels_changed:6,}{status}")
    
    # Check for duplicates
    print(f"\n🔍 Checking for duplicate frames:")
    print("-" * 50)
    
    duplicates_found = []
    for i in range(len(frame_analysis)):
        for j in range(i + 1, len(frame_analysis)):
            frame1 = frame_analysis[i]
            frame2 = frame_analysis[j]
            
            similarity = compare_frame_similarity(frame1['frame'], frame2['frame'])
            
            if similarity['is_duplicate']:
                duplicates_found.append((i, j, similarity))
                print(f"  DUPLICATE: Frame {i+1} and Frame {j+1} are very similar "
                      f"(score: {similarity['similarity_score']:.1f})")
    
    if not duplicates_found:
        print("  No obvious duplicates found")
    
    # Check for white/blank frames
    print(f"\n🔍 Checking for white/blank frames:")
    print("-" * 50)
    
    white_frames = [f for f in frame_analysis if f['is_white']]
    low_content_frames = [f for f in frame_analysis if f['is_low_content'] and not f['is_white']]
    
    if white_frames:
        for frame in white_frames:
            print(f"  WHITE FRAME: Frame {frame['index']+1} at {frame['timestamp_s']:.1f}s "
                  f"(brightness: {frame['mean_brightness']:.1f})")
    else:
        print("  No white frames detected")
    
    if low_content_frames:
        print(f"  Low content frames:")
        for frame in low_content_frames:
            print(f"    Frame {frame['index']+1} at {frame['timestamp_s']:.1f}s "
                  f"(content score: {frame['content_score']:.1f})")
    
    # Check video end for missing final page
    print(f"\n🔍 Checking for missing final page:")
    print("-" * 50)
    
    video_reader = cv2.VideoCapture(video_path)
    total_frames = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(video_reader.get(cv2.CAP_PROP_FPS))
    duration_s = total_frames / fps
    
    last_selected_frame = max(frame_analysis, key=lambda x: x['frame_num'])
    time_gap_to_end = duration_s - last_selected_frame['timestamp_s']
    
    print(f"  Video duration: {duration_s:.1f}s ({total_frames} frames)")
    print(f"  Last selected frame: {last_selected_frame['timestamp_s']:.1f}s")
    print(f"  Gap to video end: {time_gap_to_end:.1f}s")
    
    if time_gap_to_end > 10:  # More than 10 seconds gap
        print(f"  ⚠️ POTENTIAL MISSING FINAL PAGE: Large gap to video end")
        
        # Check what's in the final frames
        video_reader.set(cv2.CAP_PROP_POS_FRAMES, total_frames - fps * 5)  # Last 5 seconds
        final_frames_analysis = []
        
        for i in range(fps * 5):  # Check last 5 seconds
            ret, frame = video_reader.read()
            if ret:
                current_frame_num = int(video_reader.get(cv2.CAP_PROP_POS_FRAMES))
                timestamp = video_reader.get(cv2.CAP_PROP_POS_MSEC)
                
                content = analyze_frame_content(frame)
                if content['content_score'] > 20:  # Has significant content
                    final_frames_analysis.append({
                        'frame_num': current_frame_num,
                        'timestamp_s': timestamp / 1000,
                        'content_score': content['content_score']
                    })
        
        if final_frames_analysis:
            best_final_frame = max(final_frames_analysis, key=lambda x: x['content_score'])
            print(f"  📄 Potential final page at {best_final_frame['timestamp_s']:.1f}s "
                  f"(frame #{best_final_frame['frame_num']}, content: {best_final_frame['content_score']:.1f})")
    else:
        print(f"  ✅ Final frame seems appropriate")
    
    video_reader.release()
    
    return {
        'frame_analysis': frame_analysis,
        'duplicates': duplicates_found,
        'white_frames': white_frames,
        'low_content_frames': low_content_frames,
        'time_gap_to_end': time_gap_to_end
    }

def main():
    """Main analysis function"""
    
    video_path = "tests/videos/input_11.mp4"
    
    if not os.path.exists(video_path):
        print(f"❌ Video not found: {video_path}")
        return
    
    # Analyze the current frame selection
    analysis = analyze_selected_frames(video_path)
    
    # Provide recommendations
    print(f"\n💡 RECOMMENDATIONS")
    print("=" * 50)
    
    recommendations = []
    
    if analysis['white_frames']:
        recommendations.append("1. REMOVE WHITE FRAMES: Filter out frames with brightness > 240 and low variation")
    
    if analysis['duplicates']:
        recommendations.append("2. REMOVE DUPLICATES: Add similarity checking to avoid consecutive similar frames")
    
    if analysis['time_gap_to_end'] > 10:
        recommendations.append("3. ADD FINAL PAGE: Extend analysis to capture content near video end")
    
    if not recommendations:
        recommendations.append("✅ Frame selection looks good!")
    
    for rec in recommendations:
        print(f"  {rec}")
    
    print(f"\n🔧 Implementation needed:")
    print(f"  - Add frame content filtering in video_segment_finder.py")
    print(f"  - Add duplicate detection logic")
    print(f"  - Ensure final frames are considered")

if __name__ == "__main__":
    main()
