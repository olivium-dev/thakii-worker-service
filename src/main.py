import sys
import argparse
from .subtitle_segment_finder import SubtitleGenerator, SubtitleSegmentFinder
from .subtitle_webvtt_parser import SubtitleWebVTTParser
from .subtitle_srt_parser import SubtitleSRTParser
from .video_segment_finder import VideoSegmentFinder
from .content_segment_exporter import ContentSegment, ContentSegmentPdfBuilder


class CommandLineArgRunner:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="Generate a readable pdf from lecture videos"
        )
        self.parser.add_argument("video", type=str, help="File path to lecture video")
        self.parser.add_argument(
            "-s",
            "--subtitle",
            type=str,
            default=None,
            help="File path to video subtitle. If omitted, it will generate subtitles",
        )
        self.parser.add_argument(
            "-S",
            "--skip-subtitles",
            action="store_true",
            help="If flag is set, it will ignore setting subtitles to lecture slides",
        )
        self.parser.add_argument(
            "-o",
            "--output",
            type=str,
            default="output.pdf",
            help="Output file to generated pdf",
        )

    def run(self, args):
        opts = self.parser.parse_args(args)

        video_filepath = opts.video
        subtitle_filepath = opts.subtitle
        output_filepath = opts.output
        is_skip_subtitles = opts.skip_subtitles

        if is_skip_subtitles and subtitle_filepath is not None:
            print("Omit the -S / --skip-subtitles flag to add subtitles to pdf")
            raise AssertionError()

        video_segment_finder = VideoSegmentFinder()

        if is_skip_subtitles:
            self.__generate_pdf_without_subtitles__(
                video_segment_finder, video_filepath, output_filepath
            )
        else:
            if subtitle_filepath is None:
                print("🎤 Generating REAL subtitles from actual video audio...")
                # Generate real subtitles using Whisper transcription
                try:
                    import whisper
                    import os
                    import torch
                    
                    # Load Whisper large-v3 model for maximum accuracy
                    model_name = "large-v3"
                    print(f"📥 Loading Whisper {model_name} model (most accurate, may take 2-3 min first time)...")
                    
                    # Detect best device
                    if torch.cuda.is_available():
                        device = "cuda"
                    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                        device = "mps"
                    else:
                        device = "cpu"
                    
                    model = whisper.load_model(model_name, device=device)
                    print(f"✅ Model loaded on {device}")
                    
                    # Transcribe with MAXIMUM ACCURACY settings
                    print("🎵 Transcribing audio with maximum accuracy (large-v3 + optimized params)...")
                    result = model.transcribe(
                        video_filepath,
                        language="en",                           # Specify language
                        task="transcribe",                       # Explicit task
                        temperature=0.0,                         # Deterministic (no randomness)
                        beam_size=5,                            # Search 5 best paths
                        best_of=5,                              # Try 5 times, pick best
                        patience=2.0,                           # Wait longer for better results
                        length_penalty=1.0,                     # Prefer natural length
                        suppress_tokens=[-1],                   # Suppress unwanted tokens
                        initial_prompt="This is a lecture or educational video with clear, professional speech. Please transcribe every word accurately.",
                        condition_on_previous_text=True,        # Use context from previous segments
                        word_timestamps=True,                   # Word-level timing
                        prepend_punctuations="\"'"¿([{-",      # Better punctuation
                        append_punctuations="\"'.。,，!！?？:：")]}、", # Better punctuation
                        compression_ratio_threshold=2.4,        # Quality filter
                        logprob_threshold=-1.0,                # Confidence filter
                        no_speech_threshold=0.6,               # Silence detection
                        fp16=False,                            # Full precision
                        verbose=True                           # Show progress
                    )
                    
                    # Save to SRT file
                    srt_path = video_filepath.rsplit(".", 1)[0] + ".srt"
                    with open(srt_path, "w", encoding='utf-8') as f:
                        for i, segment in enumerate(result["segments"]):
                            start_time = segment["start"]
                            end_time = segment["end"]
                            text = segment["text"].strip()
                            
                            # Format time for SRT
                            def format_time(seconds):
                                h = int(seconds // 3600)
                                m = int((seconds % 3600) // 60)
                                s = int(seconds % 60)
                                ms = int((seconds - int(seconds)) * 1000)
                                return f"{h:02}:{m:02}:{s:02},{ms:03}"
                            
                            f.write(f"{i+1}\n{format_time(start_time)} --> {format_time(end_time)}\n{text}\n\n")
                    
                    print(f"✅ Real transcription saved to: {srt_path}")
                    subtitle_parser = SubtitleSRTParser(srt_path)
                    
                except ImportError as e:
                    print(f"⚠️ Whisper/PyTorch not available: {e}")
                    print("🔄 Using enhanced subtitle generator with improved segmentation...")
                    subtitle_parser = SubtitleGenerator(video_filepath)
                except Exception as e:
                    print(f"⚠️ Whisper transcription failed: {e}")
                    print("🔄 Falling back to enhanced subtitle generator...")
                    subtitle_parser = SubtitleGenerator(video_filepath)
            elif subtitle_filepath.endswith(".srt"):
                subtitle_parser = SubtitleSRTParser(subtitle_filepath)
            else:
                subtitle_parser = SubtitleWebVTTParser(subtitle_filepath)

            self.__generate_pdf_with_subtitles__(
                video_segment_finder, video_filepath, subtitle_parser, output_filepath
            )

    def __generate_pdf_with_subtitles__(
        self, video_segment_finder, video_filepath, subtitle_parser, output_filepath
    ):
        # Get the selected frames
        print("Getting selected frames")
        selected_frames_data = video_segment_finder.get_best_segment_frames(
            video_filepath
        )
        frame_nums = sorted(selected_frames_data.keys())
        selected_frames = [selected_frames_data[i]["frame"] for i in frame_nums]

        print("Number of frames:", len(selected_frames))

        # Get the subtitles for each frame
        print("Getting subtitles for each frame")
        segment_finder = SubtitleSegmentFinder(subtitle_parser.get_subtitle_parts())
        subtitle_breaks = [selected_frames_data[i]["timestamp"] for i in frame_nums]
        segments = segment_finder.get_subtitle_segments(subtitle_breaks)

        # Merge the frame and subtitles for each frame to create a pdf
        print("Merging frames and subtitles")
        video_subtitle_pages = []

        for i in range(0, len(selected_frames)):
            frame = selected_frames[i]
            subtitle_page = segments[i]
            video_subtitle_pages.append(ContentSegment(frame, subtitle_page))

        print("Generating PDF file")
        printer = ContentSegmentPdfBuilder()
        printer.generate_pdf(video_subtitle_pages, output_filepath)

    def __generate_pdf_without_subtitles__(
        self, video_segment_finder, video_filepath, output_filepath
    ):
        # Get the selected frames
        print("Getting selected frames")
        selected_frames_data = video_segment_finder.get_best_segment_frames(
            video_filepath
        )
        frame_nums = sorted(selected_frames_data.keys())
        selected_frames = [selected_frames_data[i]["frame"] for i in frame_nums]

        print("Number of frames:", len(selected_frames))

        # Generating PDF file
        print("Generating PDF file")
        video_subtitle_pages = [
            ContentSegment(frame, None) for frame in selected_frames
        ]
        printer = ContentSegmentPdfBuilder()
        printer.generate_pdf(video_subtitle_pages, output_filepath)


if __name__ == "__main__":
    runner = CommandLineArgRunner()
    runner.run(sys.argv[1:])
