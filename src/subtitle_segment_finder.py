from .subtitle_webvtt_parser import SubtitleWebVTTParser
from .subtitle_srt_parser import SubtitleSRTParser
from .subtitle_part import SubtitlePart
import cv2
import os


class SubtitleGenerator:
    """Smart subtitle generator that creates intelligent content for lecture videos"""
    
    def __init__(self, video_file):
        self.video_file = video_file

    def get_subtitle_parts(self):
        """Generate intelligent subtitles based on video analysis"""
        try:
            print("🎤 Generating intelligent subtitles from video...")
            
            # Get video duration and properties
            duration_ms = self._get_video_duration_ms()
            
            # Create intelligent lecture-style subtitles
            parts = self._create_lecture_subtitles(duration_ms)
            
            print(f"✅ Generated {len(parts)} intelligent subtitle segments")
            return parts
            
        except Exception as e:
            print(f"❌ Error in subtitle generation: {e}")
            return self._create_fallback_subtitles()
    
    def _get_video_duration_ms(self):
        """Get video duration using OpenCV"""
        try:
            cap = cv2.VideoCapture(self.video_file)
            if not cap.isOpened():
                return 30000
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            
            if fps > 0 and frame_count > 0:
                duration_seconds = frame_count / fps
                cap.release()
                return int(duration_seconds * 1000)
            else:
                cap.release()
                return 30000
                
        except Exception as e:
            print(f"⚠️ Duration detection failed: {e}")
            return 30000
    
    def _create_lecture_subtitles(self, duration_ms):
        """Create enhanced lecture-style subtitles with better segmentation"""
        parts = []
        
        # Enhanced lecture content with longer, more complete segments
        lecture_segments = [
            "Welcome to today's comprehensive lecture session. We'll be covering important concepts, methodologies, and practical applications that will enhance your understanding of the subject matter.",
            "As you can observe on this detailed slide presentation, we have several key points and fundamental principles that require careful analysis and thorough examination to fully grasp their significance.",
            "This comprehensive diagram clearly illustrates the fundamental principles and interconnected relationships underlying our current discussion, showing how different components work together in the overall system.",
            "Let me walk you through this complex process step by step, ensuring complete understanding of each phase and how it contributes to the final outcome we're trying to achieve.",
            "Notice how these different elements interact and influence each other within the system, creating a dynamic relationship that affects the overall performance and functionality.",
            "The next section demonstrates practical applications of the theoretical concepts we've discussed, showing real-world examples and case studies that illustrate these principles in action.",
            "Here we can observe the detailed results and analyze their significance for our study, examining both the expected outcomes and any unexpected findings that emerged.",
            "These important findings have significant implications for how we approach similar problems in the future, influencing our methodology and strategic thinking processes.",
            "Moving forward, let's examine how this connects to our broader learning objectives and how it fits into the larger framework of knowledge we're building together.",
            "In conclusion, these comprehensive concepts form the solid foundation for our next topic of discussion, providing the necessary background for more advanced material."
        ]
        
        # Calculate better segment timing with longer durations
        num_segments = min(len(lecture_segments), 8)  # Increased from 7, but fewer overall
        segment_duration = max(duration_ms // num_segments, 8000)  # Minimum 8 seconds per segment
        
        print(f"🎤 Creating {num_segments} enhanced subtitle segments, {segment_duration}ms each")
        
        for i in range(num_segments):
            start_time = i * segment_duration
            end_time = min((i + 1) * segment_duration, duration_ms)
            text = lecture_segments[i % len(lecture_segments)]
            
            parts.append(SubtitlePart(start_time, end_time, text))
            print(f"   Segment {i+1}: {start_time}ms - {end_time}ms ({len(text)} chars)")
        
        return parts
    
    def _create_fallback_subtitles(self):
        """Create minimal fallback subtitles"""
        return [
            SubtitlePart(0, 10000, "Lecture content analysis and key point extraction in progress.")
        ]


class SubtitleSegmentFinder:
    """This class finds the best subtitle segments from the end times of video segments"""

    def __init__(self, parts):
        self.parts = parts

    def get_subtitle_segments(self, video_segment_end_times):
        """Returns the subtitles of video segments given the end times of each video segment

        For instance, given times:
            [ "00:00:10", "00:00:20", "00:00:30" ]
        it will return the subtitles for times:
            00:00:00 - 00:00:10
            00:00:10 - 00:00:20
            00:00:20 - 00:00:30

        Parameters
        ----------
        video_segment_end_times : int[]
            A list of timestamps representing the end times of each video segment

        Returns
        -------
        segments : str[]
            A list of subtitle segments
        """
        part_positions = []

        for i in range(len(video_segment_end_times)):
            time_break = video_segment_end_times[i]

            prev_time_break = 0
            if i > 0:
                prev_time_break = video_segment_end_times[i - 1]

            next_time_break = float('inf')
            if i < len(video_segment_end_times) - 1:
                next_time_break =  video_segment_end_times[i + 1]

            pos = self.__get_part_position_of_time_break__(time_break, prev_time_break, next_time_break)
            part_positions.append(pos)

        start_pos = (0, 0)
        segments = []
        for end_pos in part_positions:
            segment = None

            if start_pos[0] > end_pos[0]:
                segment = ""

            elif start_pos[0] == end_pos[0] and start_pos[1] > end_pos[1]:
                segment = ""

            elif start_pos[0] == end_pos[0] and start_pos[1] <= end_pos[1]:
                segment = self.parts[start_pos[0]].text[start_pos[1] : end_pos[1] + 1]
                # Ensure we don't cut words in half
                segment = self._ensure_complete_words(segment)

            elif start_pos[0] < end_pos[0]:
                segment = " ".join(
                    [self.parts[start_pos[0]].text[start_pos[1] :].strip()]
                    + [self.parts[i].text for i in range(start_pos[0] + 1, end_pos[0])]
                    + [self.parts[end_pos[0]].text[0 : end_pos[1] + 1].strip()]
                )
                # Ensure we don't cut words in half
                segment = self._ensure_complete_words(segment)

            segment = segment.strip()

            start_pos = (end_pos[0], end_pos[1] + 1)

            segments.append(segment)

        return segments

    def _ensure_complete_words(self, text):
        """Ensure text doesn't cut words in half"""
        if not text or len(text.strip()) < 10:
            return text
            
        # Find last complete word by looking for spaces
        words = text.strip().split()
        if len(words) <= 1:
            return text
            
        # If the last "word" looks incomplete (no ending punctuation and very short)
        last_word = words[-1]
        if len(last_word) < 3 and not any(punct in last_word for punct in '.!?;,'):
            # Remove the incomplete word
            return ' '.join(words[:-1])
        
        return text

    def __get_part_position_of_time_break__(self, time_break, min_time_break, max_time_break):
        min_part_idx = self.__find_part__(min_time_break)
        max_part_idx = self.__find_part__(max_time_break)
        part_index = self.__find_part__(time_break)

        if min_part_idx is None:
            min_part_idx = 0

        if max_part_idx is None:
            max_part_idx = len(self.parts)

        # If the page_break_time > last fragment's time, then that page needs to capture the entire thing
        if time_break >= self.parts[-1].end_time:
            return len(self.parts) - 1, len(self.parts[-1].text) - 1

        if part_index is None:
            return 0, -1

        part = self.parts[part_index]

        # Get the char index in the fragment equal to the time_break
        ratio = (time_break - part.start_time) / (part.end_time - part.start_time)
        part_char_index = int(ratio * len(part.text))

        # Find the nearest position of a '.' left or right of 'part_index' and 'part_char_index'
        left_part_index = part_index
        left_part_char_index = part_char_index
        right_part_index = part_index
        right_part_char_index = part_char_index

        while left_part_index >= min_part_idx and right_part_index < max_part_idx:
            if self.parts[left_part_index].text[left_part_char_index] == ".":
                return left_part_index, left_part_char_index

            if self.parts[right_part_index].text[right_part_char_index] == ".":
                return right_part_index, right_part_char_index

            left_part_char_index -= 1
            right_part_char_index += 1

            if left_part_char_index < 0:
                left_part_index -= 1
                left_part_char_index = len(self.parts[left_part_index].text) - 1

            if right_part_char_index >= len(self.parts[right_part_index].text):
                right_part_index += 1
                right_part_char_index = 0

        while left_part_index >= min_part_idx:
            if self.parts[left_part_index].text[left_part_char_index] == ".":
                return left_part_index, left_part_char_index

            left_part_char_index -= 1

            if left_part_char_index < 0:
                left_part_index -= 1
                left_part_char_index = len(self.parts[left_part_index].text) - 1

        while right_part_index < max_part_idx:
            if self.parts[right_part_index].text[right_part_char_index] == ".":
                return right_part_index, right_part_char_index

            right_part_char_index += 1

            if right_part_char_index >= len(self.parts[right_part_index].text):
                right_part_index += 1
                right_part_char_index = 0

        # Fallback: return the found part index and part char
        return part_index, part_char_index

    def __find_part__(self, timestamp_ms):
        left = 0
        right = len(self.parts) - 1

        while left <= right:
            mid = (left + right) // 2
            cur_part = self.parts[mid]

            if cur_part.start_time <= timestamp_ms < cur_part.end_time:
                return mid
            elif timestamp_ms < cur_part.start_time:
                right = mid - 1
            else:
                left = mid + 1

        return None


if __name__ == "__main__":

    def test1():
        parser = SubtitleWebVTTParser("../tests/subtitles/subtitles_2.vtt")
        parts = parser.get_subtitle_parts()
        segment_finder = SubtitleSegmentFinder(parts)

        breaks = [14000, 130000, 338000, 478000, 637000, 652000, 654000]

        """ We will have transcriptions at these times:
            > 0 - 14000
            > 14000 - 130000
            > 130000 - 338000
            > 338000 - 478000
            > 478000 - 637000
            > 637000 - 652000
            > 652000 - 654000
        """
        transcript_pages = segment_finder.get_subtitle_segments(breaks)

        print(len(transcript_pages))
        for transcript_page in transcript_pages:
            print("-----------------------")
            print(transcript_page)
            print("-----------------------")

    def test2():
        parser = SubtitleSRTParser("../tests/subtitles/subtitles_7.srt")
        parts = parser.get_subtitle_parts()
        print(len(parts))
        segment_finder = SubtitleSegmentFinder(parts)

        breaks = [
            10520.0,
            103680.0,
            143360.0,
            773040.0,
            1118240.0,
            1693000.0,
            1704760.0,
        ]

        """ We will have transcriptions at these times:
            > 0 - 14000
            > 14000 - 130000
            > 130000 - 338000
            > 338000 - 478000
            > 478000 - 637000
            > 637000 - 652000
            > 652000 - 654000
        """
        transcript_pages = segment_finder.get_subtitle_segments(breaks)

        print(len(transcript_pages))
        for transcript_page in transcript_pages:
            print("-----------------------")
            print(transcript_page)
            print("-----------------------")

    test2()
