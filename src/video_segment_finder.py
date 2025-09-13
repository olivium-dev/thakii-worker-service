import numpy as np
import cv2


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

    def __init__(self, threshold=50, min_change=200000, min_segment_duration=15000):
        self.threshold = threshold              # Much higher threshold - very insensitive to changes
        self.min_change = min_change           # Much higher - extremely insensitive  
        self.min_segment_duration = min_segment_duration  # Minimum 15 seconds per segment

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
        
        # PERFORMANCE OPTIMIZATION: Sample frames instead of processing every frame
        frame_skip = max(1, fps // 2)  # Process every 0.5 seconds worth of frames
        print(f"🚀 Optimized processing: sampling every {frame_skip} frames (every ~0.5 seconds)")

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

            # Store the results
            if save_stats_for_all_frames:
                frame_num_to_stats[frame_num] = {
                    "timestamp": timestamp,
                    "num_pixels_changed": results["num_pixels_changed"],
                }

            has_changed = results["num_pixels_changed"] > self.min_change
            save_frame = False

            if prev_video_changes.are_previous_frames_stable() and has_changed:
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
        max_segments = 10  # Maximum 10 segments for better text coherence
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
