import numpy as np
import cv2
import os
import math
from dotenv import load_dotenv

load_dotenv()


class VideoSegmentFinder:
    """A class responsible for finding a list of best possible video segments using intelligent scene detection.
    
    The minimum change threshold is calculated logarithmically based on video duration:
    min_change_percentage = 15 * log10(duration_seconds)
    
    This percentage determines how much of the frame must change to be considered a new scene.
    For a 100-second video: 30% of pixels must change to count as a new scene.
    
    Examples:
    - 10 seconds: 15% threshold
    - 100 seconds: 30% threshold  
    - 1000 seconds: 45% threshold
    - 10000 seconds: 60% threshold
    """

    def __init__(self, threshold=None, min_change=None, min_segment_duration=None, max_segments=None):
        """
        Initialize VideoSegmentFinder with logarithmic threshold algorithm.
        
        Parameters
        ----------
        threshold : int, optional
            Pixel difference threshold for scene detection (default: 15)
        min_change : int, optional
            DEPRECATED: This parameter is ignored. Kept for backward compatibility.
            The algorithm now uses logarithmic threshold automatically.
        min_segment_duration : int, optional
            Minimum duration between segments in milliseconds (default: 2000)
        max_segments : int, optional
            Maximum number of segments to return (default: None = unlimited)
        """
        # Pixel difference threshold
        self.threshold = threshold or int(os.getenv('VIDEO_THRESHOLD', 15))
        
        # DEPRECATED: min_change parameter kept for backward compatibility but not used
        # Algorithm always uses logarithmic threshold
        if min_change is not None or os.getenv('MIN_CHANGE'):
            print("⚠️  Warning: MIN_CHANGE is deprecated and ignored. Using logarithmic threshold.")
        
        # Minimum segment duration in milliseconds
        self.min_segment_duration = min_segment_duration or int(os.getenv('MIN_SEGMENT_DURATION', 2000))
        
        # Maximum segments for output limiting (optional safety limit)
        self.max_segments = max_segments
        if self.max_segments is None and os.getenv('MAX_SEGMENTS'):
            self.max_segments = int(os.getenv('MAX_SEGMENTS'))
        
        # Log configuration
        config_parts = [f"pixel_threshold={self.threshold}"]
        config_parts.append(f"min_segment_duration={self.min_segment_duration}ms")
        if self.max_segments:
            config_parts.append(f"max_segments={self.max_segments}")
        
        print(f"🎛️ Video Analysis Config: {', '.join(config_parts)}")

    def get_best_segment_frames(self, video_file):
        ''' Finds a list of best possible video segments 
        It returns a map, where the key is the frame number, and the value is the frame data

        The frame data is of this format:
        {
            "timestamp": <the timestamp of the current frame>,
            "frame": <the current frame>,
            "next_frame": <the next frame>,
            "mask": <difference between current and next frame>,
            "num_pixels_changed": <number of pixel changes>,
        }

        The video segment can be obtained by two adjacent frame data, f1, f2 where:
            a = f2.frame
            t1 = f1.timestamp
            t2 = f2.timestamp

        Returns
        -------
        selected_frames : { a -> b }
            A map of frame number a to the frame data b
        '''
        selected_frames, _ = self.get_segment_frames_with_stats(
            video_file, save_stats_for_all_frames=False
        )
        return selected_frames

    def get_segment_frames_with_stats(self, video_file, save_stats_for_all_frames=True):
        ''' Returns frames detected via intelligent scene detection with dynamic thresholding.
        
        Uses logarithmic formula to calculate minimum change threshold:
        min_change_percentage = 15 * log10(duration_seconds)
        - 100 seconds → 30% of pixels must change to count as new scene
        
        Enhanced with:
        - Rolling window change detection (not just stable frames)
        - Dynamic frame sampling based on video length
        - Adaptive thresholding
        - Minimum segment duration filtering

        Returns
        -------
        selected_frames : { a -> b }
            A map of frame number to its frame data
        stats : { a -> c }
            A map of frame number to its statistic
        '''

        video_reader = cv2.VideoCapture(video_file)

        # Get video properties
        frame_width = int(video_reader.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(video_reader.get(cv2.CAP_PROP_FPS))
        total_frames = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = total_frames / fps if fps > 0 else 0
        total_pixels = frame_width * frame_height
        
        # LOGARITHMIC THRESHOLD CALCULATION
        # For 100 seconds: 30% of pixels must change
        if duration_seconds < 1:
            min_change_percentage = 15.0
        else:
            min_change_percentage = 15 * math.log10(duration_seconds)
            min_change_percentage = max(5.0, min(min_change_percentage, 50.0))  # Clamp between 5-50%
        
        min_change_pixels = int(total_pixels * (min_change_percentage / 100.0))
        
        print(f"📊 Video Duration: {duration_seconds:.1f}s ({frame_width}x{frame_height}, {fps} fps)")
        print(f"🎯 Logarithmic threshold: {min_change_percentage:.1f}% of pixels = {min_change_pixels:,} pixels")
        print(f"   Formula: 15 * log10({duration_seconds:.1f}) = {min_change_percentage:.1f}%")
        
        # DYNAMIC FRAME SAMPLING: Adjust based on video length
        if duration_seconds < 60:
            frame_skip = max(1, fps // 4)  # Every 0.25 seconds
            print(f"⚡ Short video: checking every {frame_skip} frames (~0.25s)")
        elif duration_seconds > 1800:  # 30+ minutes
            frame_skip = max(1, fps)  # Every 1 second
            print(f"⚡ Long video: checking every {frame_skip} frames (~1s)")
        else:
            frame_skip = max(1, fps // 2)  # Every 0.5 seconds
            print(f"⚡ Medium video: checking every {frame_skip} frames (~0.5s)")

        frame_num = 0
        frame_num_to_stats = {}
        selected_frames = {}
        
        prev_timestamp = 0
        prev_frame = 255 * np.ones((frame_height, frame_width, 3), np.uint8)  # Blank screen
        
        # ENHANCED: Rolling window of recent changes (not just stable/unstable)
        recent_changes = []  # Store recent pixel change counts
        window_size = 5
        
        detected_scenes = []

        while video_reader.isOpened():
            is_read, cur_frame = video_reader.read()
            timestamp = video_reader.get(cv2.CAP_PROP_POS_MSEC)
            
            # Skip frames for performance
            if frame_num % frame_skip != 0:
                frame_num += 1
                continue

            if not is_read:
                break

            results = self.__compare_frames__(prev_frame, cur_frame)
            num_pixels_changed = results["num_pixels_changed"]

            # Store stats
            if save_stats_for_all_frames:
                frame_num_to_stats[frame_num] = {
                    "timestamp": timestamp,
                    "num_pixels_changed": num_pixels_changed,
                }

            # ENHANCED DETECTION: Check if this is a significant scene change
            is_significant_change = num_pixels_changed > min_change_pixels
            
            # Update rolling window
            recent_changes.append(num_pixels_changed)
            if len(recent_changes) > window_size:
                recent_changes.pop(0)
            
            # ENHANCED: Detect scene change when:
            # 1. Current frame has significant change
            # 2. This change is notably higher than recent average (spike detection)
            if is_significant_change and len(recent_changes) >= 3:
                avg_recent = sum(recent_changes[:-1]) / len(recent_changes[:-1])
                is_spike = num_pixels_changed > (avg_recent * 1.5)  # 50% higher than recent average
                
                if is_spike:
                    selected_frames[frame_num] = {
                        "timestamp": prev_timestamp,
                        "frame": prev_frame,
                        "next_frame": cur_frame,
                        "mask": results["mask"],
                        "num_pixels_changed": num_pixels_changed,
                    }
                    detected_scenes.append((frame_num, timestamp, num_pixels_changed))

            prev_frame = cur_frame
            prev_timestamp = timestamp
            frame_num += 1

        # Add the last frame
        selected_frames[frame_num] = {
            "timestamp": prev_timestamp,
            "frame": prev_frame,
            "next_frame": 255 * np.ones((frame_height, frame_width, 3), np.uint8),
            "mask": prev_frame,
            "num_pixels_changed": 0,
        }

        print(f"🔍 Initial detection: {len(selected_frames)} scene changes")

        # FILTER: Remove segments that are too short
        selected_frame_nums = sorted(selected_frames.keys())
        frames_to_remove = []
        
        for i in range(len(selected_frame_nums) - 1):
            cur_frame_num = selected_frame_nums[i]
            next_frame_num = selected_frame_nums[i + 1]
            
            if cur_frame_num in selected_frames and next_frame_num in selected_frames:
                cur_frame = selected_frames[cur_frame_num]
                next_frame = selected_frames[next_frame_num]
                
                time_diff = next_frame["timestamp"] - cur_frame["timestamp"]
                if time_diff < self.min_segment_duration:
                    frames_to_remove.append(next_frame_num)
        
        for frame_num in frames_to_remove:
            if frame_num in selected_frames:
                del selected_frames[frame_num]

        # Remove first frame (blank screen)
        updated_frame_nums = sorted(selected_frames.keys())
        if updated_frame_nums and updated_frame_nums[0] in selected_frames:
            del selected_frames[updated_frame_nums[0]]

        print(f"🔍 Scenes after filtering: {len(selected_frames)} screenshots")

        # BACKWARD COMPATIBLE: Limit maximum number of segments
        if self.max_segments and len(selected_frames) > self.max_segments:
            print(f"🔧 Reducing {len(selected_frames)} segments to {self.max_segments} (MAX_SEGMENTS limit)")
            
            # Keep evenly distributed segments
            frame_nums = sorted(selected_frames.keys())
            keep_every = max(1, len(frame_nums) // self.max_segments)
            
            new_selected_frames = {}
            kept_count = 0
            for i in range(0, len(frame_nums), keep_every):
                if kept_count >= self.max_segments:
                    break
                frame_num = frame_nums[i]
                new_selected_frames[frame_num] = selected_frames[frame_num]
                kept_count += 1
            
            # Always keep the last frame if not already included
            if frame_nums and frame_nums[-1] not in new_selected_frames:
                new_selected_frames[frame_nums[-1]] = selected_frames[frame_nums[-1]]
            
            selected_frames = new_selected_frames
            print(f"✅ Reduced to {len(selected_frames)} segments")

        # BACKWARD COMPATIBLE: Ensure minimum segments for reliability
        MIN_SEGMENTS_GUARANTEE = 2
        if len(selected_frames) < MIN_SEGMENTS_GUARANTEE:
            print(f"⚠️ Only {len(selected_frames)} segments detected, creating minimum segments...")
            
            # Create at least 2 segments from the video
            video_reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret1, frame1 = video_reader.read()
            timestamp1 = 0
            
            video_reader.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
            ret2, frame2 = video_reader.read()
            timestamp2 = video_reader.get(cv2.CAP_PROP_POS_MSEC)
            
            if ret1 and ret2:
                selected_frames = {
                    0: {
                        "timestamp": timestamp1,
                        "frame": frame1,
                        "next_frame": frame2,
                        "mask": frame1,
                        "num_pixels_changed": 0
                    },
                    total_frames // 2: {
                        "timestamp": timestamp2,
                        "frame": frame2,
                        "next_frame": 255 * np.ones((frame_height, frame_width, 3), np.uint8),
                        "mask": frame2,
                        "num_pixels_changed": 0
                    }
                }
                print(f"✅ Minimum segments created: {len(selected_frames)}")

        print(f"✅ Final scenes after filtering: {len(selected_frames)} screenshots")
        print(f"📄 Expected PDF pages: {len(selected_frames)}")

        video_reader.release()
        cv2.destroyAllWindows()

        return selected_frames, frame_num_to_stats

    def __compare_frames__(self, prev_frame, cur_frame):
        diff = cv2.absdiff(prev_frame, cur_frame)
        mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        num_pixels_changed = np.sum(mask > self.threshold)

        return {"num_pixels_changed": num_pixels_changed, "mask": mask, "diff": diff}


if __name__ == "__main__":
    splitter = VideoSegmentFinder()
    splitter.get_best_segment_frames("../tests/videos/input_2.mp4")
