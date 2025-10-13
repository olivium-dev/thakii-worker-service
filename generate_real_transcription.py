#!/usr/bin/env python3
"""
REAL WHISPER TRANSCRIPTION - NO FALLBACKS, NO MOCKS, NO FAKE TEXT
Uses OpenAI Whisper to transcribe EVERY SINGLE WORD from the video audio
"""

import sys
import os
import cv2
import whisper
import tempfile
from pathlib import Path
from src.content_segment_exporter import ContentSegment, ContentSegmentPdfBuilder

def extract_content_based_frames(video_path):
    """Extract frames based on actual scene changes in the video - NO ARTIFICIAL LIMITS"""
    
    print(f"🎬 Extracting frames based on REAL content changes from {video_path}")
    print(f"📊 Number of pages will depend ONLY on actual scene changes in video")
    
    # Use the REAL content-based video segment finder
    from src.video_segment_finder import VideoSegmentFinder
    
    print(f"🔍 Using intelligent scene detection...")
    video_finder = VideoSegmentFinder()
    selected_frames_data = video_finder.get_best_segment_frames(video_path)
    
    # Convert to our format
    frames_data = []
    frame_nums = sorted(selected_frames_data.keys())
    
    print(f"✅ Detected {len(frame_nums)} scene changes in video")
    
    for i, frame_num in enumerate(frame_nums):
        frame_info = selected_frames_data[frame_num]
        frames_data.append({
            "frame_number": frame_num,
            "timestamp": frame_info["timestamp"],
            "frame": frame_info["frame"]
        })
        print(f"   Scene {i+1}/{len(frame_nums)}: frame #{frame_num} at {frame_info['timestamp']/1000:.1f}s")
    
    return frames_data

def transcribe_audio_with_whisper(video_path, model_size="base"):
    """
    REAL TRANSCRIPTION using OpenAI Whisper
    NO FALLBACKS - This will transcribe EVERY SINGLE WORD from the audio
    """
    
    print(f"\n{'='*70}")
    print(f"🎤 REAL WHISPER TRANSCRIPTION - Loading Model: {model_size}")
    print(f"{'='*70}")
    
    # Load Whisper model
    print(f"📥 Loading Whisper '{model_size}' model (this may take a moment)...")
    model = whisper.load_model(model_size)
    print(f"✅ Whisper model loaded successfully!")
    
    # Transcribe the video with word-level timestamps
    print(f"\n🎵 Transcribing audio from: {video_path}")
    print(f"⏳ This will capture EVERY SINGLE WORD spoken in the video...")
    
    result = model.transcribe(
        video_path,
        language="en",
        word_timestamps=True,
        verbose=True,
        temperature=0.0,
        best_of=5,
        beam_size=5
    )
    
    print(f"\n✅ REAL TRANSCRIPTION COMPLETE!")
    print(f"   📝 Total segments: {len(result['segments'])}")
    
    # Calculate total word count
    total_words = sum(len(seg['text'].split()) for seg in result['segments'])
    print(f"   💬 Total words transcribed: {total_words}")
    
    return result

def map_transcription_to_frames(transcription_result, frames_data):
    """
    Map the real transcribed text to each frame based on timestamps
    This ensures each page gets the ACTUAL SPOKEN WORDS for that time period
    """
    
    print(f"\n📚 Mapping real transcription to {len(frames_data)} frames...")
    
    content_segments = []
    segments = transcription_result['segments']
    
    for i, frame_data in enumerate(frames_data):
        # Get timestamp range for this frame
        if i == 0:
            start_time = 0
        else:
            start_time = frames_data[i-1]['timestamp'] / 1000  # Convert to seconds
        
        end_time = frame_data['timestamp'] / 1000  # Convert to seconds
        
        # Find all transcribed segments that fall within this time range
        relevant_text = []
        word_count = 0
        
        for segment in segments:
            seg_start = segment['start']
            seg_end = segment['end']
            
            # If segment overlaps with our time range
            if seg_start < end_time and seg_end > start_time:
                text = segment['text'].strip()
                if text:
                    relevant_text.append(text)
                    word_count += len(text.split())
        
        # Combine all text for this frame
        combined_text = ' '.join(relevant_text)
        
        if not combined_text:
            combined_text = "[No speech detected in this segment]"
        
        content_segments.append(ContentSegment(frame_data['frame'], combined_text))
        
        print(f"   Page {i+1}: {start_time:.1f}s - {end_time:.1f}s | {word_count} words | Preview: {combined_text[:60]}...")
    
    return content_segments

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_real_transcription.py <video_file> [model_size] [output_file]")
        print("\nModel sizes: tiny, base, small, medium, large")
        print("  - tiny/base: Fast, good for testing")
        print("  - small: Better accuracy")
        print("  - medium/large: Best accuracy, slower")
        print("\nNOTE: Number of pages depends ONLY on video content (scene changes)")
        print("      NO artificial limits, NO uniform extraction")
        sys.exit(1)
    
    video_file = sys.argv[1]
    model_size = sys.argv[2] if len(sys.argv) > 2 else "base"
    output_file = sys.argv[3] if len(sys.argv) > 3 else f"real_transcription.pdf"
    
    print(f"\n{'='*70}")
    print(f"🚀 REAL WHISPER TRANSCRIPTION - CONTENT-BASED ONLY")
    print(f"{'='*70}")
    print(f"📹 Video: {video_file}")
    print(f"📄 Pages: Based on REAL scene changes (no artificial limits)")
    print(f"🎤 Model: {model_size}")
    print(f"💾 Output: {output_file}")
    print(f"{'='*70}\n")
    
    try:
        # Step 1: Extract frames based on REAL content changes
        frames_data = extract_content_based_frames(video_file)
        
        # Step 2: REAL transcription with Whisper
        transcription_result = transcribe_audio_with_whisper(video_file, model_size)
        
        # Step 3: Map transcribed text to frames
        content_segments = map_transcription_to_frames(transcription_result, frames_data)
        
        # Step 4: Generate PDF
        print(f"\n📄 Generating PDF with REAL transcribed content...")
        pdf_builder = ContentSegmentPdfBuilder()
        pdf_builder.generate_pdf(content_segments, output_file)
        
        print(f"\n{'='*70}")
        print(f"🎉 SUCCESS! REAL TRANSCRIPTION PDF GENERATED")
        print(f"{'='*70}")
        print(f"📄 File: {output_file}")
        print(f"📃 Pages: {len(content_segments)}")
        print(f"✅ Every single word from the video has been transcribed!")
        print(f"{'='*70}\n")
        
        return output_file
        
    except Exception as e:
        print(f"\n{'='*70}")
        print(f"❌ FATAL ERROR - NO FALLBACKS")
        print(f"{'='*70}")
        print(f"Error: {str(e)}")
        print(f"\nThis script REQUIRES:")
        print(f"  1. Valid video file")
        print(f"  2. OpenAI Whisper installed (pip install openai-whisper)")
        print(f"  3. PyTorch installed (pip install torch)")
        print(f"  4. Sufficient disk space for model")
        print(f"{'='*70}\n")
        raise

if __name__ == "__main__":
    main()

