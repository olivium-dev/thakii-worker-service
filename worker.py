import time
import os
import subprocess
import tempfile
import shutil
from dotenv import load_dotenv
from backend.core.s3_storage import S3Storage
from backend.core.firestore_db import firestore_db
from backend.core.server_manager import server_manager

load_dotenv()
LECTURE2PDF_PATH = os.getenv("LECTURE2PDF_PATH", "/lecture2pdf")
s3_storage = S3Storage()

# In Docker, use system python; locally use the venv-py310 if available
if os.path.exists("/lecture2pdf"):  # Docker environment
    PYTHON_EXECUTABLE = "python"
elif os.path.exists(os.path.join(LECTURE2PDF_PATH, "venv-py310", "bin", "python")):  # Local environment
    PYTHON_EXECUTABLE = os.path.join(LECTURE2PDF_PATH, "venv-py310", "bin", "python")
else:
    PYTHON_EXECUTABLE = "python3"

def process_video(video_id):
    """Process video using S3 storage and Firestore database"""
    task = firestore_db.get_video_task(video_id)
    if not task:
        print(f"Task not found for video_id: {video_id}")
        return
    
    temp_video_path = None
    temp_srt_path = None
    temp_pdf_path = None
    
    try:
        print(f"Starting processing for video {video_id}...")
        
        # 1. Download video from S3 to temporary file
        print(f"Downloading video from S3...")
        temp_video_path = s3_storage.download_video_to_temp(video_id, task['filename'])
        
        # 2. Generate subtitles to temporary file
        print(f"Generating subtitles for {video_id}...")
        temp_srt_file = tempfile.NamedTemporaryFile(delete=False, suffix='.srt')
        temp_srt_path = temp_srt_file.name
        temp_srt_file.close()
        
        subprocess.run([
            PYTHON_EXECUTABLE,
            os.path.join(LECTURE2PDF_PATH, "src", "subtitle_generator.py"),
            temp_video_path
        ], check=True, cwd=LECTURE2PDF_PATH)
        
        # The subtitle_generator.py creates .srt file automatically
        video_base_name = temp_video_path.rsplit(".", 1)[0]
        generated_srt_path = video_base_name + ".srt"
        
        # Check if file exists and copy to our expected temp location
        if os.path.exists(generated_srt_path):
            shutil.copy2(generated_srt_path, temp_srt_path)
            print(f"Copied subtitle file from {generated_srt_path} to {temp_srt_path}")
        else:
            print(f"Warning: Expected subtitle file not found at {generated_srt_path}")
            # Create an empty subtitle file to continue processing
            with open(temp_srt_path, 'w') as f:
                f.write("1\n00:00:00,000 --> 00:00:01,000\nNo subtitles generated\n\n")
        
        # 3. Upload subtitles to S3
        print(f"Uploading subtitles to S3...")
        with open(temp_srt_path, 'r') as srt_file:
            subtitle_content = srt_file.read()
        s3_storage.upload_subtitle(subtitle_content, video_id)
        
        # 4. Generate PDF to temporary file
        print(f"Generating PDF for {video_id}...")
        temp_pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_pdf_path = temp_pdf_file.name
        temp_pdf_file.close()
        
        subprocess.run([
            PYTHON_EXECUTABLE,
            "-m", "src.main",
            temp_video_path,
            "-s", temp_srt_path,
            "-o", temp_pdf_path
        ], check=True, cwd=LECTURE2PDF_PATH)
        
        # 5. Upload PDF to S3
        print(f"Uploading PDF to S3...")
        pdf_key = s3_storage.upload_pdf(temp_pdf_path, video_id)
        
        print(f"Processing completed successfully for {video_id}. PDF uploaded as: {pdf_key}")
        
    except Exception as e:
        print(f"Error processing video {video_id}: {e}")
        raise
    
    finally:
        # 6. Clean up all temporary files
        print(f"Cleaning up temporary files for {video_id}...")
        s3_storage.cleanup_temp_files(temp_video_path, temp_srt_path, temp_pdf_path)

def worker_loop():
    print("🚀 Starting Firestore & S3-enabled worker process...")
    
    while True:
        try:
            # Get next queued task from Firestore
            task = firestore_db.get_next_queued_task()
            
            if task:
                video_id = task['video_id']
                print(f"📹 Processing video: {video_id}")
                
                # Update status to in_progress
                firestore_db.update_video_task_status(video_id, "in_progress")
                
                try:
                    process_video(video_id)
                    # Update status to done
                    firestore_db.update_video_task_status(video_id, "done")
                    print(f"✅ Video {video_id} processed successfully")
                    
                except Exception as e:
                    print(f"❌ Error processing video {video_id}: {e}")
                    # Update status to failed
                    firestore_db.update_video_task_status(video_id, "failed")
                
                # Short pause between tasks
                time.sleep(1)
            else:
                # No tasks in queue, wait longer
                print("💤 No tasks in queue, sleeping...")
                time.sleep(5)
                
        except Exception as e:
            print(f"🚨 Worker loop error: {e}")
            time.sleep(10)  # Wait before retrying

if __name__ == "__main__":
    worker_loop()
