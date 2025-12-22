#!/usr/bin/env python3
"""
Analyze input_11.mp4 with different approaches and compare with the real sample
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from video_segment_finder import VideoSegmentFinder

def analyze_frame_selection(video_path):
    """Analyze frame selection with different approaches"""
    
    print(f"🔍 Analyzing frame selection for: {video_path}")
    print("=" * 80)
    
    # Test 1: Original approach - detailed analysis
    print("\n📊 ORIGINAL APPROACH ANALYSIS")
    print("-" * 50)
    
    finder_original = VideoSegmentFinder(use_quarter_based_analysis=False)
    frames_original, stats_original = finder_original.get_segment_frames_with_stats(video_path)
    
    print(f"Original approach results:")
    print(f"  - Total frames selected: {len(frames_original)}")
    print(f"  - Frame numbers: {sorted(frames_original.keys())}")
    
    # Show timestamps for each selected frame
    print(f"  - Frame timestamps:")
    for frame_num in sorted(frames_original.keys()):
        timestamp_ms = frames_original[frame_num]['timestamp']
        timestamp_s = timestamp_ms / 1000
        pixels_changed = frames_original[frame_num]['num_pixels_changed']
        print(f"    Frame {frame_num}: {timestamp_s:.1f}s ({pixels_changed:,} pixels changed)")
    
    # Test 2: Center-focused approach - detailed analysis
    print("\n🎯 CENTER-FOCUSED APPROACH ANALYSIS")
    print("-" * 50)
    
    finder_center = VideoSegmentFinder(use_quarter_based_analysis=True)
    frames_center, stats_center = finder_center.get_segment_frames_with_stats(video_path)
    
    print(f"Center-focused approach results:")
    print(f"  - Total frames selected: {len(frames_center)}")
    print(f"  - Frame numbers: {sorted(frames_center.keys())}")
    
    # Show timestamps for each selected frame
    print(f"  - Frame timestamps:")
    for frame_num in sorted(frames_center.keys()):
        timestamp_ms = frames_center[frame_num]['timestamp']
        timestamp_s = timestamp_ms / 1000
        pixels_changed = frames_center[frame_num]['num_pixels_changed']
        print(f"    Frame {frame_num}: {timestamp_s:.1f}s ({pixels_changed:,} pixels changed)")
    
    # Test 3: More aggressive approach - lower thresholds
    print("\n⚡ AGGRESSIVE APPROACH ANALYSIS (Lower Thresholds)")
    print("-" * 50)
    
    finder_aggressive = VideoSegmentFinder(
        use_quarter_based_analysis=False,
        min_change=2000,  # Much lower threshold
        threshold=5       # More sensitive
    )
    frames_aggressive, stats_aggressive = finder_aggressive.get_segment_frames_with_stats(video_path)
    
    print(f"Aggressive approach results:")
    print(f"  - Total frames selected: {len(frames_aggressive)}")
    print(f"  - Frame numbers: {sorted(frames_aggressive.keys())}")
    
    # Show first 10 timestamps
    print(f"  - First 10 frame timestamps:")
    for i, frame_num in enumerate(sorted(frames_aggressive.keys())[:10]):
        timestamp_ms = frames_aggressive[frame_num]['timestamp']
        timestamp_s = timestamp_ms / 1000
        pixels_changed = frames_aggressive[frame_num]['num_pixels_changed']
        print(f"    Frame {frame_num}: {timestamp_s:.1f}s ({pixels_changed:,} pixels changed)")
    
    if len(frames_aggressive) > 10:
        print(f"    ... and {len(frames_aggressive) - 10} more frames")
    
    # Comparison
    print("\n📈 COMPARISON ANALYSIS")
    print("=" * 50)
    
    original_frame_nums = set(frames_original.keys())
    center_frame_nums = set(frames_center.keys())
    aggressive_frame_nums = set(frames_aggressive.keys())
    
    print(f"Frame count comparison:")
    print(f"  - Original: {len(original_frame_nums)} frames")
    print(f"  - Center-focused: {len(center_frame_nums)} frames")
    print(f"  - Aggressive: {len(aggressive_frame_nums)} frames")
    
    # Frame overlap analysis
    common_orig_center = original_frame_nums.intersection(center_frame_nums)
    common_orig_aggressive = original_frame_nums.intersection(aggressive_frame_nums)
    
    print(f"\nFrame overlap analysis:")
    print(f"  - Original ∩ Center-focused: {len(common_orig_center)} frames")
    print(f"  - Original ∩ Aggressive: {len(common_orig_aggressive)} frames")
    
    # Unique frames
    only_original = original_frame_nums - center_frame_nums - aggressive_frame_nums
    only_center = center_frame_nums - original_frame_nums - aggressive_frame_nums
    only_aggressive = aggressive_frame_nums - original_frame_nums - center_frame_nums
    
    print(f"\nUnique frames:")
    print(f"  - Only in Original: {len(only_original)} frames {sorted(only_original)[:5]}{'...' if len(only_original) > 5 else ''}")
    print(f"  - Only in Center-focused: {len(only_center)} frames {sorted(only_center)[:5]}{'...' if len(only_center) > 5 else ''}")
    print(f"  - Only in Aggressive: {len(only_aggressive)} frames {sorted(only_aggressive)[:5]}{'...' if len(only_aggressive) > 5 else ''}")
    
    return {
        'original': frames_original,
        'center': frames_center,
        'aggressive': frames_aggressive
    }

def generate_test_pdfs(video_path):
    """Generate PDFs with different approaches"""
    
    video_name = Path(video_path).stem
    print(f"\n📄 GENERATING TEST PDFs")
    print("=" * 50)
    
    # Generate aggressive approach PDF
    output_aggressive = f"{video_name}_aggressive.pdf"
    
    env_aggressive = os.environ.copy()
    env_aggressive['USE_QUARTER_BASED_ANALYSIS'] = 'false'
    env_aggressive['MIN_CHANGE'] = '2000'  # Lower threshold
    env_aggressive['VIDEO_THRESHOLD'] = '5'  # More sensitive
    
    print(f"Generating aggressive PDF: {output_aggressive}")
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'src.main', 
            video_path, '-o', output_aggressive, '--skip-subtitles'
        ], capture_output=True, text=True, env=env_aggressive)
        
        if result.returncode == 0 and os.path.exists(output_aggressive):
            aggressive_size = os.path.getsize(output_aggressive)
            print(f"✅ Aggressive PDF generated: {aggressive_size:,} bytes")
            return output_aggressive, aggressive_size
        else:
            print(f"❌ Aggressive PDF generation failed: {result.stderr}")
            return None, 0
            
    except Exception as e:
        print(f"❌ Aggressive PDF generation failed: {e}")
        return None, 0

def main():
    """Main analysis function"""
    
    video_path = "tests/videos/input_11.mp4"
    expected_pdf = "tests/videos/input_11_real_sample.pdf"
    
    if not os.path.exists(video_path):
        print(f"❌ Video not found: {video_path}")
        return
    
    if not os.path.exists(expected_pdf):
        print(f"❌ Expected PDF not found: {expected_pdf}")
        return
    
    expected_size = os.path.getsize(expected_pdf)
    print(f"🎯 Expected PDF size: {expected_size:,} bytes ({expected_size/1024/1024:.1f} MB)")
    
    # Analyze frame selection
    frame_analysis = analyze_frame_selection(video_path)
    
    # Generate test PDFs
    aggressive_pdf, aggressive_size = generate_test_pdfs(video_path)
    
    # Final comparison
    print(f"\n🏆 FINAL SIZE COMPARISON")
    print("=" * 50)
    
    existing_pdfs = [
        ("Expected Sample", expected_size),
        ("Original Approach", 2899293),  # From previous test
        ("Center-Focused", 2037780),     # From previous test
    ]
    
    if aggressive_size > 0:
        existing_pdfs.append(("Aggressive Approach", aggressive_size))
    
    # Sort by size descending
    existing_pdfs.sort(key=lambda x: x[1], reverse=True)
    
    for name, size in existing_pdfs:
        percentage = (size / expected_size) * 100
        print(f"  {name:20}: {size:>10,} bytes ({percentage:5.1f}% of expected)")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS")
    print("=" * 50)
    
    if aggressive_size > expected_size:
        print("✅ Aggressive approach captures MORE content than expected")
        print("   → Try reducing thresholds further or use aggressive approach")
    elif aggressive_size > 0.9 * expected_size:
        print("✅ Aggressive approach is close to expected size")
        print("   → Fine-tune aggressive approach parameters")
    else:
        print("⚠️ All approaches generate smaller PDFs than expected")
        print("   → Need even more aggressive detection or different strategy")
    
    print(f"\nNext steps:")
    print(f"1. Compare generated PDFs visually with expected sample")
    print(f"2. Identify missing slides in our approaches")
    print(f"3. Adjust thresholds or detection strategy accordingly")

if __name__ == "__main__":
    main()
