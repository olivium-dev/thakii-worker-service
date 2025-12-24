import numpy as np
import cv2
import os
import statistics
from dotenv import load_dotenv

load_dotenv()


class PastFrameChangesTracker:
    """ A class that keeps track of changes from previous frames """

    def __init__(self):
        self.prev_frame_changes = [False, False, False, False, False]

    def are_previous_frames_stable(self):
        """Checks if all previous frames had no changes

        Returns
        -------
        is_stable : boolean
            True if all past frames had no changes; else False
        """
        return sum([1 if x else 0 for x in self.prev_frame_changes]) == 0

    def add_frame_change(self, has_changed):
        """Adds a change to the tracker
        If there are more than 5 items in the tracker, it will evict the oldest frame change

        Parameters
        ----------
        has_changed : boolean
            True if there was a change with the current frame vs the past frame; else False

        Returns
        -------
        is_stable : boolean
            True if all past frames had no changes; else False
        """
        self.prev_frame_changes.append(has_changed)

        if len(self.prev_frame_changes) > 5:
            self.prev_frame_changes.pop(0)


class VideoSegmentFinder:
    """A class responsible for finding a list of best possible video segments
    A good video segment (a, t1, t2) is when image a is best explained when watching the video from time t1 to t2

    Enhanced with center-focused analysis to ignore speaker movement and focus on slide content.

    Attributes
    ----------
    threshold : int
        Is the min. difference between the color of two images on one pixel location for it to be distinct
    min_change : int
        Is the min. number of pixel changes between two adjacent video frames for the two to be considered distinct
    """

    def __init__(self, threshold=None, min_change=None, min_segment_duration=None):
        # Load from environment variables with fallback defaults
        self.threshold = threshold or int(os.getenv('VIDEO_THRESHOLD', 15))
        self.min_change = min_change or int(os.getenv('MIN_CHANGE', 10000))
        self.min_segment_duration = min_segment_duration or int(os.getenv('MIN_SEGMENT_DURATION', 2000))
        
        print(f"🎛️ Video Analysis Config: threshold={self.threshold}, min_change={self.min_change}, min_segment_duration={self.min_segment_duration}ms")
        print(f"🎯 Enhanced Slide Detection: Center-focused analysis enabled (ignoring speaker corners)")

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
        '''Enhanced slide detection using center-focused analysis.
        
        Features:
        - Center-focused frame comparison (ignores speaker corners)
        - White/blank frame filtering
        - Duplicate frame detection
        - Dual analysis (full-frame + center-focused) for better accuracy
        - Optimal frame spacing control
        
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

        print(f"📹 Video Analysis Setup:")
        print(f"   Total frames: {total_frames} ({duration_seconds:.1f}s)")
        print(f"   Strategy: Dual analysis (full-frame + center-focused)")
        print(f"   Focus Area: Center 60% width x 70% height (slide content)")
        
        # Initialize tracking variables
        frame_num = 0
        frame_num_to_stats = {}
        selected_frames = {}
        
        # Frame sampling strategy - sample frequently for accurate detection
        frame_skip = max(1, fps // 4)  # Sample ~4 frames per second
        print(f"   Frame skip: {frame_skip} (analyzing every {frame_skip}th frame)")
        
        # PASS 1: Sample frames to calculate adaptive thresholds
        print("🔍 PASS 1: Sampling frames to calculate optimal thresholds...")
        
        sample_frame_skip = max(1, total_frames // 50)  # 50 samples across video
        sample_changes_full = []
        sample_changes_center = []
        
        video_reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
        sample_frame_num = 0
        sample_prev_frame = None
        
        while sample_frame_num < total_frames and len(sample_changes_full) < 50:
            is_read, cur_frame = video_reader.read()
            
            if not is_read:
                break
                
            if sample_frame_num % sample_frame_skip == 0:
                if sample_prev_frame is not None:
                    # Full frame analysis
                    results_full = self.__compare_frames__(sample_prev_frame, cur_frame)
                    sample_changes_full.append(results_full["num_pixels_changed"])
                    
                    # Center-focused analysis
                    results_center = self.__compare_frames_center_focus__(sample_prev_frame, cur_frame)
                    sample_changes_center.append(results_center["num_pixels_changed"])
                    
                sample_prev_frame = cur_frame
                
            sample_frame_num += 1
        
        # Calculate adaptive thresholds
        if len(sample_changes_full) >= 5:
            # Full frame thresholds
            mean_full = statistics.mean(sample_changes_full)
            std_full = statistics.stdev(sample_changes_full) if len(sample_changes_full) > 1 else mean_full * 0.5
            
            # Center-focused thresholds  
            mean_center = statistics.mean(sample_changes_center)
            std_center = statistics.stdev(sample_changes_center) if len(sample_changes_center) > 1 else mean_center * 0.5
            
            # Balanced thresholds for optimal slide detection
            full_threshold = max(500, int(mean_full * 0.35))
            center_threshold = max(400, int(mean_center * 0.40))
            
            print(f"📊 Calculated Adaptive Thresholds:")
            print(f"   Full-frame: samples={len(sample_changes_full)}, mean={mean_full:.0f}, threshold={full_threshold}")
            print(f"   Center-focused: samples={len(sample_changes_center)}, mean={mean_center:.0f}, threshold={center_threshold}")
        else:
            print("⚠️ Insufficient samples for threshold calculation, using defaults")
            full_threshold = 500
            center_threshold = 300
        
        # PASS 2: Dual analysis for enhanced slide detection
        print("🔍 PASS 2: Analyzing frames with dual detection strategy...")
        
        video_reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
        frame_num = 0
        
        prev_frame = 255 * np.ones((frame_height, frame_width, 3), np.uint8)
        prev_timestamp = 0
        prev_video_changes = PastFrameChangesTracker()
        last_selected_frame = -1000  # Track last selected frame for spacing
        min_frame_spacing = fps * 3  # Minimum 3 seconds between selected frames
        last_selected_frame_data = None  # Track last selected frame for duplicate checking
        
        print(f"   Minimum frame spacing: {min_frame_spacing} frames (3 seconds)")

        while video_reader.isOpened() and frame_num < total_frames:
            is_read, cur_frame = video_reader.read()
            timestamp = video_reader.get(cv2.CAP_PROP_POS_MSEC)
            
            # Skip frames for performance
            if frame_num % frame_skip != 0:
                frame_num += 1
                continue

            if not is_read:
                break
            
            # Filter out white/blank frames
            is_white_prev_frame = self.__is_white_or_blank_frame__(prev_frame)
            if is_white_prev_frame:
                prev_frame = cur_frame
                prev_timestamp = timestamp
                frame_num += 1
                continue

            # Dual analysis: both full-frame and center-focused
            results_full = self.__compare_frames__(prev_frame, cur_frame)
            results_center = self.__compare_frames_center_focus__(prev_frame, cur_frame)

            # Store stats if requested
            if save_stats_for_all_frames:
                frame_num_to_stats[frame_num] = {
                    "timestamp": timestamp,
                    "num_pixels_changed": results_full["num_pixels_changed"],
                    "center_pixels_changed": results_center["num_pixels_changed"],
                }

            # Check for changes with either approach (OR logic for better detection)
            full_changed = results_full["num_pixels_changed"] > full_threshold
            center_changed = results_center["num_pixels_changed"] > center_threshold
            
            save_frame = False
            detection_method = ""
            active_results = results_full
            
            # Balanced detection with frame spacing control
            if full_changed and center_changed:
                # Both approaches agree - high confidence detection
                if frame_num - last_selected_frame >= min_frame_spacing:
                    save_frame = True
                    detection_method = "BOTH"
                    active_results = results_full
            elif prev_video_changes.are_previous_frames_stable():
                # Single approach detection, but only if previous frames were stable AND spaced properly
                if frame_num - last_selected_frame >= min_frame_spacing:
                    if full_changed:
                        save_frame = True
                        detection_method = "FULL"
                        active_results = results_full
                    elif center_changed:
                        save_frame = True
                        detection_method = "CENTER"
                        active_results = results_center

            if save_frame:
                # Check for duplicate with last selected frame
                if last_selected_frame_data is not None:
                    is_duplicate = self.__is_duplicate_frame__(prev_frame, last_selected_frame_data, threshold=8)
                    if is_duplicate:
                        save_frame = False
                
                if save_frame:
                    selected_frames[frame_num] = {
                        "timestamp": prev_timestamp,
                        "frame": prev_frame,
                        "next_frame": cur_frame,
                        "mask": active_results["mask"],
                        "num_pixels_changed": active_results["num_pixels_changed"],
                    }
                    
                    last_selected_frame = frame_num
                    last_selected_frame_data = prev_frame.copy()
                    print(f"   ✓ Frame {frame_num}: {detection_method} detection at {prev_timestamp/1000:.1f}s")

            # Update tracking
            prev_video_changes.add_frame_change(results_full["num_pixels_changed"] > full_threshold)
            prev_frame = cur_frame
            prev_timestamp = timestamp
            frame_num += 1

        # Add the last frame of the video
        selected_frames[frame_num] = {
            "timestamp": prev_timestamp,
            "frame": prev_frame,
            "next_frame": 255 * np.ones((frame_height, frame_width, 3), np.uint8),
            "mask": prev_frame,
            "num_pixels_changed": 0,
        }

        # Enhanced segment filtering: ensure minimum segment duration and remove glitches
        selected_frame_nums = sorted(selected_frames.keys())
        frames_to_remove = []
        
        for i in range(len(selected_frame_nums) - 1):
            cur_frame_num = selected_frame_nums[i]
            next_frame_num = selected_frame_nums[i + 1]
            
            if cur_frame_num in selected_frames and next_frame_num in selected_frames:
                cur_frame = selected_frames[cur_frame_num]
                next_frame = selected_frames[next_frame_num]
                
                # Remove segments that are too short
                time_diff = next_frame["timestamp"] - cur_frame["timestamp"]
                if time_diff < self.min_segment_duration:
                    print(f"🔧 Removing short segment: {time_diff}ms < {self.min_segment_duration}ms minimum")
                    frames_to_remove.append(next_frame_num)
        
        # Remove the marked frames
        for frame_num in frames_to_remove:
            if frame_num in selected_frames:
                del selected_frames[frame_num]

        # Edge case: delete the first selected frame since it is just a blank screen
        updated_frame_nums = sorted(selected_frames.keys())
        if updated_frame_nums and updated_frame_nums[0] in selected_frames:
            del selected_frames[updated_frame_nums[0]]

        # CRITICAL: Limit maximum number of segments to prevent fragmentation
        max_segments = int(os.getenv('MAX_SEGMENTS', 15))  # Configurable max segments
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

        # MINIMUM SEGMENT GUARANTEE: Ensure we always have at least 2 segments
        if len(selected_frames) < 2:
            print(f"⚠️ Only {len(selected_frames)} segments found, creating minimum segments...")
            
            video_reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret1, frame1 = video_reader.read()
            timestamp1 = 0
            
            video_reader.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
            ret2, frame2 = video_reader.read()
            timestamp2 = video_reader.get(cv2.CAP_PROP_POS_MSEC)
            
            if ret1 and ret2:
                selected_frames = {
                    0: {"timestamp": timestamp1, "frame": frame1},
                    total_frames // 2: {"timestamp": timestamp2, "frame": frame2}
                }
                print(f"✅ Minimum segments created: {len(selected_frames)}")

        video_reader.release()
        cv2.destroyAllWindows()
        
        print(f"✅ Enhanced analysis complete: {len(selected_frames)} slides detected")

        return selected_frames, frame_num_to_stats

    def __compare_frames__(self, prev_frame, cur_frame):
        """Standard full-frame comparison"""
        diff = cv2.absdiff(prev_frame, cur_frame)
        mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        num_pixels_changed = np.sum(mask > self.threshold)

        return {"num_pixels_changed": num_pixels_changed, "mask": mask, "diff": diff}

    def __compare_frames_center_focus__(self, prev_frame, cur_frame):
        """
        Compare frames focusing on center area (slide content) while ignoring corners (speaker areas)
        
        Cropping strategy:
        - Ignore left 20% and right 20% (speaker corners)
        - Ignore top 15% and bottom 15% (headers/footers)
        - Focus on center 60% width x 70% height (main slide content)
        """
        height, width = prev_frame.shape[:2]
        
        # Calculate crop boundaries (focus on center slide area)
        left_crop = int(width * 0.20)    # Ignore left 20% (speaker area)
        right_crop = int(width * 0.80)   # Ignore right 20% (speaker area)
        top_crop = int(height * 0.15)    # Ignore top 15% (header/title area)
        bottom_crop = int(height * 0.85) # Ignore bottom 15% (footer area)
        
        # Crop both frames to focus on slide content area
        prev_cropped = prev_frame[top_crop:bottom_crop, left_crop:right_crop]
        cur_cropped = cur_frame[top_crop:bottom_crop, left_crop:right_crop]
        
        # Compare the cropped regions
        diff = cv2.absdiff(prev_cropped, cur_cropped)
        mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        num_pixels_changed = np.sum(mask > self.threshold)
        
        return {
            "num_pixels_changed": num_pixels_changed, 
            "mask": mask, 
            "diff": diff,
            "crop_bounds": (left_crop, right_crop, top_crop, bottom_crop)
        }
    
    def __is_white_or_blank_frame__(self, frame):
        """
        Detect white or blank frames that should be filtered out
        """
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate statistics
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)
        
        # Check if frame is mostly white (blank)
        is_white = mean_brightness > 240 and std_brightness < 20
        
        # Check if frame has very low content (mostly uniform)
        is_low_content = std_brightness < 10
        
        return is_white or is_low_content
    
    def __is_duplicate_frame__(self, frame1, frame2, threshold=5):
        """
        Check if two frames are duplicates/very similar
        """
        # Convert to grayscale
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference
        diff = cv2.absdiff(gray1, gray2)
        
        # Calculate similarity metrics
        mean_diff = np.mean(diff)
        pixels_changed = np.sum(diff > 10)  # Pixels with noticeable change
        
        # Similarity score (0 = identical, higher = more different)
        similarity_score = mean_diff + (pixels_changed / diff.size) * 100
        
        return similarity_score < threshold


if __name__ == "__main__":
    splitter = VideoSegmentFinder()
    splitter.get_best_segment_frames("../tests/videos/input_2.mp4")
