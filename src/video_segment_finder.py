import numpy as np
import cv2
import os
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
        ''' Returns a list of frames for the best possible video segments (refer to get_best_segment_frames())
        
        It also outputs statistics on all frames, where the statistic on frame i is:
        {
            "timestamp": the timestamp of frame i
            "num_pixels_changed": number of pixel changes from frame i - 1 to frame i
        }

        Returns
        -------
        selected_frames : { a -> b }
            A map of frame number to its frame data
        stats : { a -> c }
            A map of frame number to its statistic
        '''

        video_reader = cv2.VideoCapture(video_file)

        # Get the Default resolutions
        frame_width = int(video_reader.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_reader.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Get the FPS
        fps = int(video_reader.get(cv2.CAP_PROP_FPS))

        frame_num = 0
        frame_num_to_stats = {}
        selected_frames = {}

        prev_timestamp = 0
        prev_frame = 255 * np.ones(
            (frame_height, frame_width, 3), np.uint8
        )  # A blank screen
        prev_video_changes = PastFrameChangesTracker()
        
        # DYNAMIC FRAME SAMPLING: Adjust based on video length and FPS
        total_frames = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = total_frames / fps if fps > 0 else 0
        
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
        
        # CRITICAL FIX: Don't use sample_interval for scene detection!
        # sample_interval is only for PASS 1 sampling
        # For PASS 2 scene detection, use a fixed small interval
        detection_interval = 0.5  # Check every 0.5 seconds for scene changes
        frame_skip = max(1, int(fps * detection_interval))
        print(f"🔍 Scene detection: checking every {frame_skip} frames ({detection_interval}s)")

        # PASS 1: Sample frames to calculate adaptive thresholds
        print("🔍 PASS 1: Sampling frames to calculate optimal thresholds...")
        sample_frames = []
        sample_diffs = []
        
        # Take samples at logarithmic intervals
        for i in range(min(target_samples, 20)):  # Cap samples for performance
            sample_position = int(i * (total_frames / min(target_samples, 20)))
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
            
            # Set min_change to catch changes 1.5 std deviations below mean (more sensitive)
            calculated_min_change = int(max(500, mean_change - (1.5 * std_change)))
            
            # Adjust threshold based on sample variance (more variance = lower threshold)
            if mean_change > 0:
                variance_ratio = std_change / mean_change
                calculated_threshold = int(max(2, 6 - (variance_ratio * 4)))
            else:
                calculated_threshold = 5
            
            print(f"📊 Calculated Adaptive Thresholds:")
            print(f"   Samples analyzed: {len(sample_diffs)}")
            print(f"   Mean change: {mean_change:.0f} pixels")
            print(f"   Std deviation: {std_change:.0f} pixels")
            print(f"   Adaptive min_change: {calculated_min_change} (was {self.min_change})")
            print(f"   Adaptive threshold: {calculated_threshold} (was {self.threshold})")
            
            # Override default thresholds with calculated values
            self.min_change = calculated_min_change
            self.threshold = calculated_threshold
        else:
            print("⚠️ Insufficient samples for threshold calculation, using defaults")
            print(f"   Using min_change: {self.min_change}, threshold: {self.threshold}")
        
        # Reset video to beginning for PASS 2
        video_reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
        print("🔍 PASS 2: Scanning entire video with calculated thresholds...")

        while video_reader.isOpened():
            is_read, cur_frame = video_reader.read()
            timestamp = video_reader.get(cv2.CAP_PROP_POS_MSEC)
            
            # Skip frames for performance
            if frame_num % frame_skip != 0:
                frame_num += 1
                continue

            # Is when the stream is ending
            if not is_read:
                break

            results = self.__compare_frames__(prev_frame, cur_frame)
            results_center = self.__compare_frames_center_focus__(prev_frame, cur_frame)

            # Store the results
            if save_stats_for_all_frames:
                frame_num_to_stats[frame_num] = {
                    "timestamp": timestamp,
                    "num_pixels_changed": results["num_pixels_changed"],
                    "center_pixels_changed": results_center["num_pixels_changed"],
                }

            # Enhanced detection: use both full-frame and center-focused analysis
            # Center threshold is scaled down since we're analyzing a smaller area
            center_threshold = int(self.min_change * 0.4)  # 40% of full threshold for center
            has_changed_full = results["num_pixels_changed"] > self.min_change
            has_changed_center = results_center["num_pixels_changed"] > center_threshold
            
            # Consider it changed if either method detects change
            has_changed = has_changed_full or has_changed_center
            save_frame = False

            if prev_video_changes.are_previous_frames_stable() and has_changed:
                # Additional filter: skip white/blank frames
                if not self.__is_white_or_blank_frame__(prev_frame):
                    save_frame = True

            if save_frame:
                selected_frames[frame_num] = {
                    "timestamp": prev_timestamp,
                    "frame": prev_frame,
                    "next_frame": cur_frame,
                    "mask": results["mask"],
                    "num_pixels_changed": results["num_pixels_changed"],
                }

            prev_video_changes.add_frame_change(has_changed)

            prev_frame = cur_frame
            prev_timestamp = timestamp

            frame_num += 1

        # Add the last frame of the video
        selected_frames[frame_num] = {
            "timestamp": prev_timestamp,
            "frame": prev_frame,
            "next_frame": 255
            * np.ones((frame_height, frame_width, 3), np.uint8),  # A blank screen,
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
                
                # Remove segments that are too short (less than min_segment_duration)
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
        max_segments = int(os.getenv('MAX_SEGMENTS', 10))  # Configurable max segments
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
            
            # Create at least 2 segments from the video
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

        return selected_frames, frame_num_to_stats

    def __compare_frames__(self, prev_frame, cur_frame):
        diff = cv2.absdiff(prev_frame, cur_frame)
        mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        num_pixels_changed = np.sum(mask > self.threshold)

        return {"num_pixels_changed": num_pixels_changed, "mask": mask, "diff": diff}

    def __compare_frames_center_focus__(self, prev_frame, cur_frame):
        """
        Compare frames focusing on center area (slide content) while ignoring corners (speaker areas).
        
        Cropping strategy:
        - Ignore left 20% and right 20% (speaker corners)
        - Ignore top 15% and bottom 15% (headers/footers)
        - Focus on center 60% width x 70% height (main slide content)
        """
        height, width = prev_frame.shape[:2]
        
        # Calculate crop boundaries (focus on center slide area)
        left_crop = int(width * 0.20)
        right_crop = int(width * 0.80)
        top_crop = int(height * 0.15)
        bottom_crop = int(height * 0.85)
        
        # Crop both frames to focus on slide content area
        prev_cropped = prev_frame[top_crop:bottom_crop, left_crop:right_crop]
        cur_cropped = cur_frame[top_crop:bottom_crop, left_crop:right_crop]
        
        # Compare the cropped regions
        diff = cv2.absdiff(prev_cropped, cur_cropped)
        mask = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        num_pixels_changed = np.sum(mask > self.threshold)
        
        return {"num_pixels_changed": num_pixels_changed, "mask": mask, "diff": diff}

    def __is_white_or_blank_frame__(self, frame):
        """Detect white or blank frames that should be filtered out."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)
        
        # Frame is blank if mostly white with little variation
        is_white = mean_brightness > 240 and std_brightness < 20
        is_low_content = std_brightness < 10
        
        return is_white or is_low_content

    def __is_duplicate_frame__(self, frame1, frame2, threshold=5):
        """Check if two frames are duplicates/very similar."""
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        
        diff = cv2.absdiff(gray1, gray2)
        mean_diff = np.mean(diff)
        pixels_changed = np.sum(diff > 10)
        
        similarity_score = mean_diff + (pixels_changed / diff.size) * 100
        return similarity_score < threshold


if __name__ == "__main__":
    splitter = VideoSegmentFinder()
    splitter.get_best_segment_frames("../tests/videos/input_2.mp4")
