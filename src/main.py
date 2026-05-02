import json
import os
import sys
import time
import tempfile
import argparse
from pathlib import Path
from .subtitle_segment_finder import SubtitleSegmentFinder
from .subtitle_webvtt_parser import SubtitleWebVTTParser
from .subtitle_srt_parser import SubtitleSRTParser
from .video_segment_finder import VideoSegmentFinder
from .content_segment_exporter import ContentSegment, ContentSegmentPdfBuilder

# Phase 5: chunk size for resumable transcription.  Each chunk is
# transcribed independently and appended to transcript.partial.json.
# On resume, already-completed chunks are skipped.
TRANSCRIBE_CHUNK_SECONDS = int(os.getenv('TRANSCRIBE_CHUNK_SECONDS', '300'))


def _atomic_json_write(path: Path, data):
    """Write JSON atomically via tmp + rename (same-device guaranteed)."""
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, default=str))
    tmp.rename(path)


def _write_progress(workdir: Path | None, phase: str, detail: dict):
    """Write progress.json sidecar for the progress thread to pick up."""
    if workdir is None:
        return
    try:
        _atomic_json_write(workdir / 'progress.json', {'phase': phase, **detail})
    except Exception:
        pass


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
        self.parser.add_argument(
            "--workdir",
            type=str,
            default=None,
            help="Persistent workdir for sidecars (progress.json, transcript.partial.json)",
        )
        self.parser.add_argument(
            "--resume",
            action="store_true",
            help="Resume transcription from transcript.partial.json if present",
        )

    def run(self, args):
        opts = self.parser.parse_args(args)

        video_filepath = opts.video
        subtitle_filepath = opts.subtitle
        output_filepath = opts.output
        is_skip_subtitles = opts.skip_subtitles
        workdir = Path(opts.workdir) if opts.workdir else None
        resume = opts.resume

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
                srt_path = self._transcribe_with_resume(
                    video_filepath, workdir, resume)
                subtitle_parser = SubtitleSRTParser(srt_path)
            elif subtitle_filepath.endswith(".srt"):
                subtitle_parser = SubtitleSRTParser(subtitle_filepath)
            else:
                subtitle_parser = SubtitleWebVTTParser(subtitle_filepath)

            _write_progress(workdir, 'pdf', {'status': 'building'})
            self.__generate_pdf_with_subtitles__(
                video_segment_finder, video_filepath, subtitle_parser, output_filepath
            )

    # ── Phase 5: resumable chunked transcription ───────────────────────

    def _transcribe_with_resume(self, video_filepath: str,
                                workdir: Path | None, resume: bool) -> str:
        """Transcribe audio in chunks.  Writes transcript.partial.json after
        each chunk so a killed process can resume from the last checkpoint."""
        import whisper
        import torch
        import numpy as np

        model_name = os.getenv("WHISPER_MODEL", "base")
        requested = os.getenv("WHISPER_DEVICE", "cpu").lower()
        if requested == "auto":
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        else:
            device = requested

        partial_path = (workdir / 'transcript.partial.json') if workdir else None
        transcript_path = (workdir / 'transcript.json') if workdir else None

        # If a complete transcript already exists, skip entirely
        if transcript_path and transcript_path.exists():
            print("⏭️  transcript.json already exists — skipping transcription", flush=True)
            data = json.loads(transcript_path.read_text())
            srt_path = self._segments_to_srt(data['segments'], video_filepath)
            return srt_path

        # Load prior partial if resuming
        prior_segments = []
        start_seconds = 0.0
        if resume and partial_path and partial_path.exists():
            try:
                data = json.loads(partial_path.read_text())
                prior_segments = data.get('segments', [])
                if prior_segments:
                    start_seconds = prior_segments[-1]['end']
                    print(f"🔄 Resuming from {start_seconds:.1f}s ({len(prior_segments)} prior segments)", flush=True)
            except Exception as e:
                print(f"⚠️  Could not read partial transcript: {e}", flush=True)
                prior_segments = []
                start_seconds = 0.0

        print(f"🎤 Generating subtitles using Whisper {model_name} on {device}...", flush=True)
        print(f"📥 Loading Whisper {model_name} model...", flush=True)
        model = whisper.load_model(model_name, device=device)
        print(f"✅ Whisper {model_name} model loaded on {device}", flush=True)

        # Load audio once (16kHz mono — whisper standard)
        print("🎵 Loading audio...", flush=True)
        audio = whisper.load_audio(video_filepath)
        total_seconds = len(audio) / 16000.0
        print(f"   Audio length: {total_seconds:.1f}s", flush=True)

        _write_progress(workdir, 'transcribe', {
            'segments_done': len(prior_segments),
            'audio_seconds_done': start_seconds,
            'audio_seconds_total': total_seconds,
        })

        # Already fully transcribed in prior partial?
        if start_seconds >= total_seconds - 1.0:
            print("✅ Transcription already complete from prior run", flush=True)
        else:
            # Chunked transcription loop
            chunk_size = TRANSCRIBE_CHUNK_SECONDS
            current_pos = start_seconds
            all_segments = list(prior_segments)
            t0 = time.time()

            while current_pos < total_seconds:
                chunk_end = min(current_pos + chunk_size, total_seconds)
                start_sample = int(current_pos * 16000)
                end_sample = int(chunk_end * 16000)
                chunk_audio = audio[start_sample:end_sample]

                # Provide context from prior text to maintain coherence
                initial_prompt = "This is a lecture or educational video with clear speech."
                if all_segments:
                    recent_text = ' '.join(s['text'] for s in all_segments[-5:])
                    initial_prompt = recent_text[-200:] if len(recent_text) > 200 else recent_text

                print(f"🎵 Transcribing chunk {current_pos:.0f}s-{chunk_end:.0f}s / {total_seconds:.0f}s ...", flush=True)

                result = model.transcribe(
                    chunk_audio,
                    language="en",
                    task="transcribe",
                    temperature=0.0,
                    beam_size=5,
                    best_of=5,
                    patience=2.0,
                    length_penalty=1.0,
                    suppress_tokens=[-1],
                    initial_prompt=initial_prompt,
                    condition_on_previous_text=True,
                    word_timestamps=False,
                    prepend_punctuations="\"'([{-",
                    append_punctuations="\"'.,!?:)]}",
                    compression_ratio_threshold=2.4,
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    fp16=False,
                    verbose=False
                )

                # Adjust timestamps to absolute position
                for seg in result.get('segments', []):
                    all_segments.append({
                        'start': seg['start'] + current_pos,
                        'end': seg['end'] + current_pos,
                        'text': seg['text'].strip(),
                    })

                current_pos = chunk_end

                # Checkpoint: write partial atomically
                if partial_path:
                    _atomic_json_write(partial_path, {
                        'segments': all_segments,
                        'model': model_name,
                        'device': device,
                        'language': 'en',
                    })

                elapsed = time.time() - t0
                _write_progress(workdir, 'transcribe', {
                    'segments_done': len(all_segments),
                    'audio_seconds_done': current_pos,
                    'audio_seconds_total': total_seconds,
                    'elapsed_seconds': int(elapsed),
                })

                print(f"   ✅ Chunk done: {len(result.get('segments', []))} segments, "
                      f"total {len(all_segments)} segments so far", flush=True)

            prior_segments = all_segments

        print(f"✅ Transcription completed: {len(prior_segments)} segments", flush=True)

        # Write final transcript
        if transcript_path:
            _atomic_json_write(transcript_path, {
                'segments': prior_segments,
                'model': model_name,
                'device': device,
                'language': 'en',
            })

        srt_path = self._segments_to_srt(prior_segments, video_filepath)
        return srt_path

    @staticmethod
    def _segments_to_srt(segments: list, video_filepath: str) -> str:
        """Convert segment list to an SRT file on disk."""
        srt_path = video_filepath.rsplit(".", 1)[0] + ".srt"

        def _fmt(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"

        with open(srt_path, "w", encoding='utf-8') as f:
            for i, seg in enumerate(segments):
                f.write(f"{i+1}\n{_fmt(seg['start'])} --> {_fmt(seg['end'])}\n{seg['text']}\n\n")

        print(f"✅ SRT saved: {srt_path} ({len(segments)} segments)", flush=True)
        return srt_path

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
