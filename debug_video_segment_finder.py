import numpy as np
import cv2
import os
import math
from dotenv import load_dotenv

load_dotenv()

class PastFrameChangesTracker:
    """ A class that keeps track of changes from previous frames """

    def __init__(self):
        self.prev_frame_changes = [False, False, False, False, False]

    def are_previous_frames_stable(self):
        """Checks if all previous frames had no changes"""
        return not any(self.prev_frame_changes)

    def add_frame_change(self, has_changed):
        """Adds a frame change to the tracker"""
        self.prev_frame_changes.pop(0)
        self.prev_frame_changes.append(has_changed)

class DebugVideoSegmentFinder:
    """Debug version with comprehensive logging"""

    def __init__(self, threshold=None, min_change=None, min_segment_duration=None):
        # Load from environment variables with fallback defaults
        self.threshold = threshold or int(os.getenv('VIDEO_THRESHOLD', 2000))  # Ultra sensitive
        self.min_change = min_change or int(os.getenv('MIN_CHANGE', 5))       # Ultra sensitive
        self.min_segment_duration = min_segment_duration or int(os.getenv('MIN_SEGMENT_DURATION', 2000))
        
        print(f"🎛️ DEBUG Video Analysis Config:")
        print(f"   Initial threshold: {self.threshold}")
        print(f"   Initial min_change: {self.min_change}")
        print(f"   Min segment duration: {self.min_segment_duration}ms")

    def get_best_segment_frames(self, video_file):
        print(f"\n🔍 DEBUG ANALYSIS: {video_file}")
        print("="*80)
        
        video_reader = cv2.VideoCapture(video_file)
        if not video_reader.isOpened():
            print(f"❌ Cannot open video file: {video_file}")
            return {}

        fps = video_reader.get(cv2.CAP_PROP_FPS)
        total_frames = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = total_frames / fps if fps > 0 else 0
        
        print(f"📊 Video Properties:")
        print(f"   File: {video_file}")
        print(f"   Total frames: {total_frames}")
        print(f"   FPS: {fps}")
        print(f"   Duration: {duration_seconds:.1f} seconds ({duration_seconds/60:.1f} minutes)")

        # Logarithmic/Adaptive Sampling Strategy
        if duration_seconds <= 60:  # 1 minute
            sample_interval = 5.0
            target_samples = int(duration_seconds / sample_interval)
            print(f"🎯 SHORT video ({duration_seconds:.1f}s): {target_samples} samples, every {sample_interval}s")
        elif duration_seconds <= 300:  # 5 minutes
            target_samples = 15
            sample_interval = duration_seconds / target_samples
            print(f"🎯 MEDIUM video ({duration_seconds:.1f}s): {target_samples} samples, every {sample_interval:.1f}s")
        else:
            # Long video: logarithmic scaling
            minutes = duration_seconds / 60
            log_base = math.log(minutes, 2)
            target_samples = int(10 + log_base * 5)
            target_samples = min(target_samples, 50)
            sample_interval = duration_seconds / target_samples
            print(f"🎯 LONG video ({duration_seconds:.1f}s = {minutes:.1f}min): {target_samples} samples, every {sample_interval:.1f}s (log scaling)")
        
        frame_skip = max(1, int(fps * sample_interval))
        print(f"   Frame skip for sampling: {frame_skip}")

        # PASS 1: Sample frames to calculate adaptive thresholds
        print(f"\n🔍 PASS 1: Sampling frames to calculate optimal thresholds")
        print("-" * 60)
        
        sample_frames = []
        sample_diffs = []
        sample_positions = []
        
        num_samples_to_take = min(target_samples, 20)
        print(f"📸 Taking {num_samples_to_take} sample screenshots...")
        
        for i in range(num_samples_to_take):
            sample_position = int(i * (total_frames / num_samples_to_take))
            sample_time = sample_position / fps if fps > 0 else 0
            video_reader.set(cv2.CAP_PROP_POS_FRAMES, sample_position)
            is_read, frame = video_reader.read()
            
            print(f"   Sample {i+1:2d}: Frame {sample_position:6d} (time: {sample_time:6.1f}s) - {'✅' if is_read else '❌'}")
            
            if is_read:
                sample_frames.append(frame)
                sample_positions.append(sample_position)
                if len(sample_frames) > 1:
                    # Compare with previous sample using low threshold
                    diff = cv2.absdiff(sample_frames[-2], sample_frames[-1])
                    mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                    num_changed = np.sum(mask > 5)  # Use low threshold for sampling
                    sample_diffs.append(num_changed)
                    print(f"             Pixel changes vs previous: {num_changed:,}")
        
        print(f"\n📊 Sample Analysis Results:")
        print(f"   Samples collected: {len(sample_frames)}")
        print(f"   Comparisons made: {len(sample_diffs)}")
        
        # Calculate adaptive thresholds from samples
        if sample_diffs and len(sample_diffs) > 2:
            mean_change = np.mean(sample_diffs)
            std_change = np.std(sample_diffs)
            min_diff = min(sample_diffs)
            max_diff = max(sample_diffs)
            
            # Set min_change to catch changes 2 std deviations below mean (very sensitive)
            calculated_min_change = int(max(100, mean_change - (2.0 * std_change)))
            
            # Adjust threshold based on sample variance (more variance = lower threshold)
            if mean_change > 0:
                variance_ratio = std_change / mean_change
                calculated_threshold = int(max(1, 3 - (variance_ratio * 2)))
            else:
                calculated_threshold = 2
            
            print(f"\n📊 Calculated Adaptive Thresholds:")
            print(f"   Samples analyzed: {len(sample_diffs)}")
            print(f"   Mean change: {mean_change:,.0f} pixels")
            print(f"   Std deviation: {std_change:,.0f} pixels")
            print(f"   Min change observed: {min_diff:,}")
            print(f"   Max change observed: {max_diff:,}")
            print(f"   Variance ratio: {variance_ratio:.3f}")
            print(f"   🎯 CALCULATED min_change: {calculated_min_change:,} (was {self.min_change:,})")
            print(f"   🎯 CALCULATED threshold: {calculated_threshold} (was {self.threshold})")
            
            # Override default thresholds with calculated values
            self.min_change = calculated_min_change
            self.threshold = calculated_threshold
        else:
            print(f"\n⚠️ Insufficient samples for threshold calculation, using defaults")
            print(f"   Using min_change: {self.min_change:,}, threshold: {self.threshold}")
        
        # PASS 2: Scan entire video with calculated thresholds
        print(f"\n🔍 PASS 2: Scanning entire video with calculated thresholds")
        print("-" * 60)
        print(f"   Active min_change: {self.min_change:,}")
        print(f"   Active threshold: {self.threshold}")
        print(f"   Will check every {frame_skip} frames for scene changes")
        
        # Reset video to beginning for PASS 2
        video_reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        selected_frames = {}
        frame_num = 0
        prev_frame = None
        prev_timestamp = 0
        prev_video_changes = PastFrameChangesTracker()
        segments_found = 0
        
        while video_reader.isOpened():
            is_read, cur_frame = video_reader.read()
            timestamp = video_reader.get(cv2.CAP_PROP_POS_MSEC)
            
            if not is_read:
                break

            # Skip frames for performance
            if frame_num % frame_skip != 0:
                frame_num += 1
                continue

            if prev_frame is not None:
                results = self.__compare_frames__(prev_frame, cur_frame)
                has_changed = results["num_pixels_changed"] > self.min_change
                
                save_frame = False
                if prev_video_changes.are_previous_frames_stable() and has_changed:
                    save_frame = True
                    segments_found += 1
                    
                    frame_time = prev_timestamp / 1000.0
                    print(f"   Segment {segments_found:2d}: Frame {frame_num-frame_skip:6d} (time: {frame_time:6.1f}s) - {results['num_pixels_changed']:,} pixels changed")

                if save_frame:
                    selected_frames[frame_num - frame_skip] = {
                        "timestamp": prev_timestamp,
                        "frame": prev_frame,
                        "num_pixels_changed": results["num_pixels_changed"]
                    }

                prev_video_changes.add_frame_change(has_changed)

            prev_frame = cur_frame
            prev_timestamp = timestamp
            frame_num += 1

        video_reader.release()
        
        # Final segment reduction if needed
        max_segments = int(os.getenv('MAX_SEGMENTS', 10))
        original_count = len(selected_frames)
        
        if len(selected_frames) > max_segments:
            print(f"\n🔧 Reducing {len(selected_frames)} segments to {max_segments} for better text coherence")
            
            frame_nums = sorted(selected_frames.keys())
            keep_every = len(frame_nums) // max_segments
            
            new_selected_frames = {}
            for i in range(0, len(frame_nums), keep_every):
                if len(new_selected_frames) >= max_segments:
                    break
                frame_num = frame_nums[i]
                new_selected_frames[frame_num] = selected_frames[frame_num]
            
            # Always keep the last frame
            if frame_nums:
                last_frame = frame_nums[-1]
                new_selected_frames[last_frame] = selected_frames[last_frame]
            
            selected_frames = new_selected_frames
            print(f"   Reduced from {original_count} to {len(selected_frames)} segments")

        print(f"\n🎯 FINAL RESULTS:")
        print(f"   Total segments found: {original_count}")
        print(f"   Final segments used: {len(selected_frames)}")
        print(f"   Expected PDF pages: {len(selected_frames)}")
        
        if len(selected_frames) > 7:
            print(f"   ✅ SUCCESS: {len(selected_frames)} pages > 7 pages requirement")
        else:
            print(f"   ⚠️  ISSUE: Only {len(selected_frames)} pages (need > 7)")
        
        print(f"\n📋 SEGMENT DETAILS:")
        for i, (frame_num, data) in enumerate(sorted(selected_frames.items())):
            time_sec = data['timestamp'] / 1000.0
            print(f"   Page {i+1:2d}: Frame {frame_num:6d} (time: {time_sec:6.1f}s) - {data['num_pixels_changed']:,} pixels changed")
        
        return selected_frames

    def __compare_frames__(self, prev_frame, cur_frame):
        diff = cv2.absdiff(prev_frame, cur_frame)
        mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        num_pixels_changed = np.sum(mask > self.threshold)
        return {"num_pixels_changed": num_pixels_changed, "mask": mask, "diff": diff}

if __name__ == "__main__":
    finder = DebugVideoSegmentFinder()
    result = finder.get_best_segment_frames("/path/to/test/video.mp4")

