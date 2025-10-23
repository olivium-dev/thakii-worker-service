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

class VideoSegmentFinder:
    """Fixed version with proper logarithmic sampling and sensitive thresholds"""

    def __init__(self, threshold=None, min_change=None, min_segment_duration=None):
        # Load from environment variables with fallback defaults
        self.threshold = threshold or int(os.getenv('VIDEO_THRESHOLD', 8))
        self.min_change = min_change or int(os.getenv('MIN_CHANGE', 5000))
        self.min_segment_duration = min_segment_duration or int(os.getenv('MIN_SEGMENT_DURATION', 2000))
        
        print(f"🎛️ Video Analysis Config: threshold={self.threshold}, min_change={self.min_change}, min_segment_duration={self.min_segment_duration}ms")

    def get_best_segment_frames(self, video_file):
        ''' Finds a list of best possible video segments 
        It returns a map, where the key is the frame number, and the value is the frame data

        The frame data is of this format:
        {
            "timestamp": <the timestamp of the current frame>,
            "frame": <the frame data>
        }
        '''
        
        video_reader = cv2.VideoCapture(video_file)
        if not video_reader.isOpened():
            print(f"❌ Cannot open video file: {video_file}")
            return {}

        fps = video_reader.get(cv2.CAP_PROP_FPS)
        total_frames = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = total_frames / fps if fps > 0 else 0
        
        print(f"📊 Video: {duration_seconds:.1f}s, {total_frames} frames, {fps} fps")

        # Logarithmic/Adaptive Sampling Strategy
        import math
        
        if duration_seconds <= 60:  # 1 minute
            # Short video: 1 shot every 5 seconds = ~12 samples
            sample_interval = 5.0
            target_samples = int(duration_seconds / sample_interval)
            print(f"🎯 Short video ({duration_seconds:.1f}s): {target_samples} samples, every {sample_interval}s")
        elif duration_seconds <= 300:  # 5 minutes
            # Medium video: aim for ~15-20 samples
            target_samples = 15
            sample_interval = duration_seconds / target_samples
            print(f"🎯 Medium video ({duration_seconds:.1f}s): {target_samples} samples, every {sample_interval:.1f}s")
        else:
            # Long video: logarithmic scaling
            # Use log base 2 of minutes to scale samples
            minutes = duration_seconds / 60
            log_base = math.log(minutes, 2)
            target_samples = int(10 + log_base * 5)  # Scale samples logarithmically
            target_samples = min(target_samples, 50)  # Cap at 50 samples for very long videos
            sample_interval = duration_seconds / target_samples
            print(f"🎯 Long video ({duration_seconds:.1f}s = {minutes:.1f}min): {target_samples} samples, every {sample_interval:.1f}s (log scaling)")
        
        # CRITICAL FIX: Use much smaller frame skip for scene detection
        # Don't use sample_interval for frame skip - use a fixed small interval
        detection_interval = 0.5  # Check every 0.5 seconds for scene changes
        frame_skip = max(1, int(fps * detection_interval))
        
        print(f"🔍 Scene detection: checking every {frame_skip} frames ({detection_interval}s intervals)")

        # PASS 1: Sample frames to calculate adaptive thresholds
        print("🔍 PASS 1: Sampling frames to calculate optimal thresholds...")
        sample_frames = []
        sample_diffs = []
        
        # Take samples at logarithmic intervals
        num_samples_to_take = min(target_samples, 20)  # Cap samples for performance
        for i in range(num_samples_to_take):
            sample_position = int(i * (total_frames / num_samples_to_take))
            video_reader.set(cv2.CAP_PROP_POS_FRAMES, sample_position)
            is_read, frame = video_reader.read()
            if is_read:
                sample_frames.append(frame)
                if len(sample_frames) > 1:
                    # Compare with previous sample using low threshold
                    diff = cv2.absdiff(sample_frames[-2], sample_frames[-1])
                    mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                    num_changed = np.sum(mask > 5)  # Use low threshold for sampling
                    sample_diffs.append(num_changed)
        
        # Calculate adaptive thresholds from samples
        if sample_diffs and len(sample_diffs) > 2:
            mean_change = np.mean(sample_diffs)
            std_change = np.std(sample_diffs)
            
            # CRITICAL FIX: Much more aggressive threshold calculation
            # Use 10% of mean change as minimum threshold
            calculated_min_change = int(max(1000, mean_change * 0.1))
            
            # Use a low fixed threshold for color sensitivity
            calculated_threshold = 5
            
            print(f"📊 Calculated Adaptive Thresholds:")
            print(f"   Samples analyzed: {len(sample_diffs)}")
            print(f"   Mean change: {mean_change:.0f} pixels")
            print(f"   Std deviation: {std_change:.0f} pixels")
            print(f"   🎯 CALCULATED min_change: {calculated_min_change} (10% of mean)")
            print(f"   🎯 CALCULATED threshold: {calculated_threshold} (fixed low value)")
            
            # Override default thresholds with calculated values
            self.min_change = calculated_min_change
            self.threshold = calculated_threshold
        else:
            print("⚠️ Insufficient samples for threshold calculation, using sensitive defaults")
            # Use very sensitive defaults
            self.min_change = 2000
            self.threshold = 5
            print(f"   Using min_change: {self.min_change}, threshold: {self.threshold}")
        
        # Reset video to beginning for PASS 2
        video_reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
        print("🔍 PASS 2: Scanning entire video with calculated thresholds...")

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

            # Skip frames for performance - but use much smaller skip
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
                    print(f"   📸 Segment {segments_found}: Frame {frame_num-frame_skip} (time: {frame_time:.1f}s) - {results['num_pixels_changed']:,} pixels changed")

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
        
        # Segment reduction logic
        max_segments = int(os.getenv('MAX_SEGMENTS', 15))  # Increased from 10 to 15
        original_count = len(selected_frames)
        
        if len(selected_frames) > max_segments:
            print(f"🔧 Reducing {len(selected_frames)} segments to {max_segments} for better text coherence")
            
            # Keep evenly distributed segments
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
            print(f"✅ Final segment count: {len(selected_frames)}")
        
        print(f"🎯 FINAL RESULTS: {len(selected_frames)} segments found")
        
        if len(selected_frames) > 7:
            print(f"✅ SUCCESS: {len(selected_frames)} segments > 7 pages requirement")
        else:
            print(f"⚠️ Only {len(selected_frames)} segments (need > 7)")

        return selected_frames

    def __compare_frames__(self, prev_frame, cur_frame):
        diff = cv2.absdiff(prev_frame, cur_frame)
        mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        num_pixels_changed = np.sum(mask > self.threshold)

        return {"num_pixels_changed": num_pixels_changed, "mask": mask, "diff": diff}


if __name__ == "__main__":
    splitter = VideoSegmentFinder()
    splitter.get_best_segment_frames("../tests/videos/input_2.mp4")
