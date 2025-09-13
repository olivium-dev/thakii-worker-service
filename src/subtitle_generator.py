import sys
from moviepy.editor import VideoFileClip
import torch
import whisper
import os
import datetime

class SubtitleGenerator:
    def __init__(self):
        print("Initializing Enhanced SubtitleGenerator...")
        self.device = "cpu"
        
        # Use larger, more accurate model for better transcription
        model_name = "large-v2"  # Much more accurate than "base"
        
        if torch.backends.mps.is_available():
            try:
                print(f"Attempting to load {model_name} model on MPS...")
                # Load on CPU first, then move parts of the model to MPS
                temp_model = whisper.load_model(model_name, device="cpu")
                temp_model.encoder = temp_model.encoder.to("mps")
                temp_model.decoder = temp_model.decoder.to("mps")
                self.model = temp_model
                self.device = "mps"
                print(f"Model {model_name} loaded successfully on MPS.")
            except Exception as e:
                print(f"Could not load {model_name} on MPS. Trying medium model on CPU. Error:\n{e}")
                self.model = whisper.load_model("medium", device="cpu")
        elif torch.cuda.is_available():
            self.device = "cuda"
            print(f"Attempting to load {model_name} model on CUDA...")
            self.model = whisper.load_model(model_name, device=self.device)
            print(f"Model {model_name} loaded successfully on CUDA.")
        else:
            print(f"Loading {model_name} model on CPU (this may take longer)...")
            self.model = whisper.load_model(model_name, device=self.device)
            print(f"Model {model_name} loaded successfully on CPU.")
        print(f"Using device: {self.device}")

    @staticmethod
    def extract_audio(file_path):
        print(f"Extracting audio from {file_path}")
        audio_path = file_path.rsplit(".", 1)[0] + ".wav"
        if not os.path.exists(audio_path):
            print(f"Audio file does not exist, creating new audio file at {audio_path}")
            with VideoFileClip(file_path) as video:
                video.audio.write_audiofile(audio_path, codec='pcm_s16le')
            print(f"Audio file {audio_path} created successfully.")
        else:
            print(f"Audio file {audio_path} already exists.")
        return audio_path

    @staticmethod
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def generate_subtitles(self, file_path):
        start_time = datetime.datetime.now()
        print(f"Start generating enhanced subtitles at {start_time}")

        if file_path.lower().endswith(('.mp4', '.mkv', '.mov', '.avi')):
            audio_path = self.extract_audio(file_path)
        else:
            print(f"Non-video file detected, using {file_path} directly as audio source.")
            audio_path = file_path
        print("Done extracting audio.")

        # Enhanced transcription with better parameters
        print("Starting enhanced transcription with optimized parameters...")
        result = self.model.transcribe(
            audio_path,
            language="en",                           # Specify language for better accuracy
            task="transcribe",                       # Explicit task
            temperature=0.0,                         # Deterministic output
            beam_size=5,                            # Better beam search
            best_of=5,                              # Multiple attempts for best result
            patience=1.0,                           # Wait for better results
            length_penalty=1.0,                     # Penalty for length
            suppress_tokens=[-1],                   # Suppress unwanted tokens
            initial_prompt="This is a lecture or educational content with clear speech.", # Context hint
            condition_on_previous_text=True,        # Use context from previous segments
            fp16=False,                             # Better precision
            compression_ratio_threshold=2.4,        # Quality threshold
            logprob_threshold=-1.0,                 # Confidence threshold
            no_speech_threshold=0.6,                # Speech detection sensitivity
            word_timestamps=True                    # CRUCIAL: Word-level timestamps for better segmentation
        )
        print("Done transcribing with enhanced parameters.")
        end_time = datetime.datetime.now()
        print(f"Finished generating subtitles at {end_time}")
        print(f"Total time taken: {end_time - start_time}")

        total_segments = len(result["segments"])
        print(f"Generated {total_segments} subtitle segments with word-level timestamps")
        
        with open(file_path.rsplit(".", 1)[0] + ".srt", "w", encoding='utf-8') as subtitle_file:
            for i, segment in enumerate(result["segments"]):
                start = self.format_time(segment["start"])
                end = self.format_time(segment["end"])
                text = segment["text"].strip()
                subtitle_file.write(f"{i+1}\n{start} --> {end}\n{text}\n\n")
                progress = (i + 1) / total_segments * 100
                sys.stdout.write(f"\rProgress: {progress:.2f}%")
                sys.stdout.flush()
        
        print(f"\n✅ Enhanced subtitles saved to: {file_path.rsplit('.', 1)[0] + '.srt'}")

def convert_srt_to_vtt(srt_file_path, vtt_file_path):
    try:
        with open(srt_file_path, 'r', encoding='utf-8') as srt_file:
            lines = srt_file.readlines()
        with open(vtt_file_path, 'w', encoding='utf-8') as vtt_file:
            vtt_file.write("WEBVTT\n\n")
            for line in lines:
                if '-->' in line:
                    line = line.replace(',', '.')
                vtt_file.write(line)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("Starting ...")
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        generator = SubtitleGenerator()
        generator.generate_subtitles(file_path)
        srt_path = file_path.rsplit(".", 1)[0] + ".srt"
        vtt_path = file_path.rsplit(".", 1)[0] + ".vtt"
        convert_srt_to_vtt(srt_path, vtt_path)
    else:
        print("Please provide the path to the video or audio file.")
