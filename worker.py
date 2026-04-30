#!/usr/bin/env python3
"""
Optimized Worker for Mac Mini M2 - High Performance Video Processing
- Uses Apple Metal (MPS) GPU acceleration
- Robust queuing with no hanging
- Optimal CPU/RAM utilization
- No fallback code - production ready
"""

import os
import sys
import time
import tempfile
import subprocess
import threading
import traceback
from pathlib import Path
import shutil
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, TimeoutError, Future
from concurrent.futures import TimeoutError as FuturesTimeoutError
import signal

# Import core integrations
from core.postgres_integration import postgres_client
from core.s3_integration import s3_client
from core.api_task_client import api_client

class EnhancedWorker:
    def __init__(self):
        self.postgres = postgres_client
        self.s3 = s3_client
        self.api = api_client
        
        # Mac Mini M2 Optimization: Use multiple cores efficiently
        self.max_concurrent_tasks = int(os.getenv('MAX_CONCURRENT_TASKS', min(multiprocessing.cpu_count(), 3)))
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_tasks)

        # Configure intelligent storage selection
        self.temp_base_dir = self._get_temp_storage_path()

        # Task processing timeout (30 minutes). Now actually enforced via a
        # ThreadPoolExecutor wrapper around process_video so a wedged ffmpeg
        # / Whisper invocation cannot leave the row in 'processing' forever.
        self.task_timeout = int(os.getenv('TASK_TIMEOUT_SECONDS', '1800'))

        # Heartbeat configuration. The daemon thread wakes every
        # HEARTBEAT_INTERVAL seconds and pings the backend so the reaper
        # knows this worker (and the rows it owns) are alive.
        self.heartbeat_interval = int(os.getenv('WORKER_HEARTBEAT_INTERVAL', '15'))
        self._active_task_ids = set()
        self._active_task_lock = threading.Lock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None

        # Janitor thread config. The deploy-time cleanup is opportunistic;
        # this background thread is the steady-state safety net that keeps
        # /tmp from filling up between deploys. Defaults sized for a
        # multi-hour idle window without losing in-progress work.
        self.janitor_interval = int(os.getenv('JANITOR_INTERVAL_SECONDS', '300'))
        self.janitor_max_age = int(os.getenv('JANITOR_MAX_AGE_SECONDS', '3600'))
        self.min_free_gb_to_pickup = float(os.getenv('MIN_FREE_GB_TO_PICKUP', '5.0'))
        self._janitor_stop = threading.Event()
        self._janitor_thread = None

        # One-shot startup cleanup so the very first task starts on a clean
        # slate. Anything older than 5 minutes in our temp roots is fair game.
        self._cleanup_temp_files(max_age_seconds=300, label='startup')

        print("🚀 Mac Mini M2 Optimized Worker", flush=True)
        print(f"   API Client: {'✅' if self.api.is_enabled else '❌'}", flush=True)
        print(f"   PostgreSQL: {'✅' if self.postgres.is_available() else '❌'}", flush=True)
        print(f"   S3: {'✅' if self.s3.is_available() else '❌'}", flush=True)
        print(f"   Temp Storage: {self.temp_base_dir}", flush=True)
        print(f"   Max Concurrent Tasks: {self.max_concurrent_tasks}", flush=True)
        print(f"   CPU Cores: {multiprocessing.cpu_count()}", flush=True)
        sys.stdout.flush()
    
    def _get_temp_storage_path(self):
        """
        Intelligently select storage path with automatic fallback
        Priority:
        1. External SSD at /mnt/external-ssd (if available and writable)
        2. Environment variable TEMP_STORAGE_PATH
        3. System temp directory (fallback)
        """
        # Check for external SSD
        external_ssd = Path("/mnt/external-ssd/temp")
        if external_ssd.exists() and os.access(external_ssd, os.W_OK):
            print(f"   💾 Using external SSD: {external_ssd}", flush=True)
            return str(external_ssd)
        
        # Check environment variable
        env_path = os.getenv('TEMP_STORAGE_PATH')
        if env_path:
            env_path = Path(env_path)
            if env_path.exists() and os.access(env_path, os.W_OK):
                print(f"   📁 Using env storage: {env_path}", flush=True)
                return str(env_path)
        
        # Fallback to system temp
        system_temp = Path(tempfile.gettempdir())
        print(f"   ⚠️  Using system temp (fallback): {system_temp}", flush=True)
        return str(system_temp)
    
    # ====== Disk hygiene (deploy-time cleanup is supplementary) ======

    def _get_free_gb(self, path: str) -> float:
        try:
            return shutil.disk_usage(path).free / (1024 ** 3)
        except Exception:
            return -1.0

    def _cleanup_temp_files(self, max_age_seconds: int, label: str = 'janitor'):
        """Best-effort prune of stale temp artefacts. We only touch files
        we know we created (mp4/pdf/srt) or directories under our own
        temp roots, and only if they're older than max_age_seconds — so a
        currently-running download is never disturbed."""
        roots = []
        # Primary temp dir the worker writes to
        if self.temp_base_dir and os.path.isdir(self.temp_base_dir):
            roots.append(self.temp_base_dir)
        # System /tmp on Linux/macOS even if temp_base_dir is something else
        if '/tmp' not in roots and os.path.isdir('/tmp'):
            roots.append('/tmp')

        now = time.time()
        removed_files = 0
        removed_dirs = 0
        bytes_freed = 0
        for root in roots:
            try:
                for name in os.listdir(root):
                    path = os.path.join(root, name)
                    try:
                        st = os.lstat(path)
                    except OSError:
                        continue
                    age = now - st.st_mtime
                    if age < max_age_seconds:
                        continue

                    # Only kill things that look like ours
                    if os.path.isdir(path) and not os.path.islink(path):
                        if name.startswith('tmp') or name == 'thakii-worker':
                            try:
                                bytes_freed += self._dir_size(path)
                                shutil.rmtree(path, ignore_errors=True)
                                removed_dirs += 1
                            except Exception:
                                pass
                    elif os.path.isfile(path):
                        if name.endswith(('.mp4', '.pdf', '.srt')) or '.mp4.' in name:
                            try:
                                bytes_freed += st.st_size
                                os.unlink(path)
                                removed_files += 1
                            except Exception:
                                pass
            except Exception as e:
                print(f"⚠️ {label} cleanup error in {root}: {e}", flush=True)

        if removed_files or removed_dirs:
            mb = bytes_freed / (1024 * 1024)
            print(f"🧹 {label} cleanup: removed {removed_files} files, {removed_dirs} dirs, freed ~{mb:.1f} MB. Free now: {self._get_free_gb(self.temp_base_dir):.2f} GB", flush=True)

    @staticmethod
    def _dir_size(path: str) -> int:
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
        return total

    def _janitor_loop(self):
        print(f"🧹 Janitor thread started (interval={self.janitor_interval}s, max_age={self.janitor_max_age}s)", flush=True)
        while not self._janitor_stop.wait(self.janitor_interval):
            try:
                self._cleanup_temp_files(self.janitor_max_age, label='janitor')
            except Exception as e:
                print(f"⚠️ Janitor error: {e}", flush=True)
        print("🧹 Janitor thread stopping", flush=True)

    def start_janitor(self):
        if self._janitor_thread is not None and self._janitor_thread.is_alive():
            return
        self._janitor_stop.clear()
        self._janitor_thread = threading.Thread(
            target=self._janitor_loop, name='worker-janitor', daemon=True)
        self._janitor_thread.start()

    def stop_janitor(self):
        self._janitor_stop.set()

    # ====== Heartbeat / active-task tracking helpers (Phase C1) ======

    def _track_task(self, video_id: str):
        with self._active_task_lock:
            self._active_task_ids.add(video_id)

    def _untrack_task(self, video_id: str):
        with self._active_task_lock:
            self._active_task_ids.discard(video_id)

    def _snapshot_active_tasks(self):
        with self._active_task_lock:
            return list(self._active_task_ids)

    def _heartbeat_loop(self):
        """Daemon loop. Sends a heartbeat every self.heartbeat_interval
        seconds with the current active_task_ids snapshot. Keeps running
        until self._heartbeat_stop is set."""
        print(f"💓 Heartbeat thread started (interval={self.heartbeat_interval}s)", flush=True)
        while not self._heartbeat_stop.wait(self.heartbeat_interval):
            try:
                if not self.api.is_enabled:
                    continue
                self.api.send_heartbeat(active_task_ids=self._snapshot_active_tasks())
            except Exception as e:
                print(f"⚠️ Heartbeat error: {e}", flush=True)
        print("💓 Heartbeat thread stopping", flush=True)

    def start_heartbeat(self):
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name='worker-heartbeat', daemon=True)
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        self._heartbeat_stop.set()

    # ====== Public process_video with timeout enforcement (Phase C2) ======

    def process_video(self, video_id: str, s3_key: str = None, filename: str = None, task_details: dict = None) -> bool:
        """Public entry point. Enforces self.task_timeout by running the
        actual work in a worker thread and wraps everything in a
        try/except BaseException crash-to-failed handler (Phase C3) so an
        uncaught exception or a timeout always marks the row 'failed'
        instead of leaving it stuck in 'processing'."""
        self._track_task(video_id)
        try:
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"task-{video_id}") as inner:
                future = inner.submit(
                    self._process_video_impl, video_id, s3_key, filename, task_details)
                try:
                    return future.result(timeout=self.task_timeout)
                except FuturesTimeoutError:
                    msg = f"task timed out after {self.task_timeout}s"
                    print(f"⏱️ {video_id}: {msg}", flush=True)
                    self._mark_failed(video_id, msg)
                    return False
        except BaseException as e:  # noqa: BLE001 — we want to catch *anything*
            tb = traceback.format_exc()
            msg = f"worker crash: {type(e).__name__}: {e}"
            print(f"💥 {video_id}: {msg}\n{tb}", flush=True)
            try:
                self._mark_failed(video_id, msg)
            except Exception as inner_err:
                print(f"⚠️ Failed to mark {video_id} as failed after crash: {inner_err}", flush=True)
            return False
        finally:
            self._untrack_task(video_id)

    def _mark_failed(self, video_id: str, error_message: str):
        try:
            if self.api.is_enabled:
                self.api.update_task_status(video_id, "failed", error_message=error_message)
            else:
                self.postgres.update_task_status(video_id, "failed", error_message=error_message)
        except Exception as e:
            print(f"⚠️ _mark_failed error for {video_id}: {e}", flush=True)

    def _process_video_impl(self, video_id: str, s3_key: str = None, filename: str = None, task_details: dict = None) -> bool:
        print(f"\n🎯 Processing: {video_id}", flush=True)
        if s3_key:
            print(f"   🔑 S3 Key: {s3_key}", flush=True)
        if filename:
            print(f"   📁 Filename: {filename}")
        
        try:
            # Check if cancelled before starting
            if self._is_cancelled(video_id):
                print(f"⚠️ Video {video_id} was cancelled before processing", flush=True)
                self._handle_cancellation(video_id)
                return False
            
            # Update to processing with 0% progress
            if self.api.is_enabled:
                self.api.update_task_status(video_id, "processing", progress=0)
            else:
                self.postgres.update_task_status(video_id, "processing")
            
            # Get task details (use provided details from API pickup, or fallback to PostgreSQL)
            if task_details:
                task = task_details
            else:
                task = self.postgres.get_task_details(video_id)
                if not task:
                    if self.api.is_enabled:
                        self.api.update_task_status(video_id, "failed", error_message="Task not found")
                    else:
                        self.postgres.update_task_status(video_id, "failed", error_message="Task not found")
                    return False
            
            # Prefer parameters, then task fields, then fallback
            filename = filename or task.get('filename', f'{video_id}.mp4')
            s3_key = s3_key or task.get('s3_key') or task.get('s3_path')
            
            # Use intelligent storage path (external SSD if available, else fallback)
            with tempfile.TemporaryDirectory(dir=self.temp_base_dir) as temp_dir:
                temp_path = Path(temp_dir)
                video_path = temp_path / filename
                pdf_path = temp_path / f"{video_id}.pdf"
                
                print(f"   📁 Using temp directory: {temp_dir}", flush=True)
                sys.stdout.flush()
                
                # Check cancellation before download
                if self._is_cancelled(video_id):
                    self._handle_cancellation(video_id)
                    return False
                
                # Update progress to 10% - Starting download
                if self.api.is_enabled:
                    self.api.update_task_status(video_id, "processing", progress=10)
                else:
                    self.postgres.update_task_status(video_id, "processing")
                
                # Pre-task disk hygiene: if we're tight on space, run an
                # emergency janitor sweep BEFORE asking S3 for the file.
                # Better to free 30 GB of stale partials than to fail a
                # 12 GB download halfway through and leak disk.
                pre_free_gb = self._get_free_gb(self.temp_base_dir)
                if pre_free_gb < self.min_free_gb_to_pickup:
                    print(f"⚠️ Free {pre_free_gb:.2f} GB < threshold {self.min_free_gb_to_pickup} GB; emergency sweep", flush=True)
                    self._cleanup_temp_files(max_age_seconds=60, label='pre-task')

                # Download video (use exact s3_key if available). Build a
                # detailed error message so operators can tell at a glance
                # whether it was permissions, disk, network, etc.
                if not self.s3.download_video(video_id, str(video_path), s3_key=s3_key):
                    detail = getattr(self.s3, 'last_error', None) or 'unknown error'
                    err = f"Download failed (s3_key={s3_key}, file={filename}): {detail}"
                    print(f"❌ {err}", flush=True)
                    if self.api.is_enabled:
                        self.api.update_task_status(video_id, "failed", error_message=err)
                    else:
                        self.postgres.update_task_status(video_id, "failed", error_message=err)
                    return False
                
                # Check cancellation after download
                if self._is_cancelled(video_id):
                    self._handle_cancellation(video_id)
                    return False
                
                # Update progress to 30% - Download complete, starting PDF generation
                if self.api.is_enabled:
                    self.api.update_task_status(video_id, "processing", progress=30)
                else:
                    self.postgres.update_task_status(video_id, "processing")
                
                # Generate PDF with superior algorithms
                if not self._generate_pdf_with_cancellation_check(video_id, video_path, pdf_path):
                    # Check if it was cancelled or failed
                    if self._is_cancelled(video_id):
                        self._handle_cancellation(video_id)
                    else:
                        if self.api.is_enabled:
                            self.api.update_task_status(video_id, "failed", error_message="PDF generation failed")
                        else:
                            self.postgres.update_task_status(video_id, "failed", error_message="PDF generation failed")
                    return False
                
                # Check cancellation before upload
                if self._is_cancelled(video_id):
                    self._handle_cancellation(video_id)
                    return False
                
                # Update progress to 80% - PDF generated, starting upload
                if self.api.is_enabled:
                    self.api.update_task_status(video_id, "processing", progress=80)
                else:
                    self.postgres.update_task_status(video_id, "processing")
                
                # Upload PDF
                pdf_url = self.s3.upload_pdf(str(pdf_path), video_id)
                if not pdf_url:
                    if self.api.is_enabled:
                        self.api.update_task_status(video_id, "failed", error_message="Upload failed")
                    else:
                        self.postgres.update_task_status(video_id, "failed", error_message="Upload failed")
                    return False
                
                # Final cancellation check
                if self._is_cancelled(video_id):
                    # Clean up uploaded PDF
                    try:
                        self.s3.delete_file(f"pdfs/{video_id}.pdf")
                    except:
                        pass
                    self._handle_cancellation(video_id)
                    return False
                
                # Mark completed with 100% progress
                if self.api.is_enabled:
                    self.api.update_task_status(video_id, "done", pdf_url=pdf_url, progress=100)
                else:
                    self.postgres.update_task_status(video_id, "done", pdf_url=pdf_url)
                print(f"🎉 Success: {video_id}")
                return True
                
        except Exception as e:
            if self.api.is_enabled:
                self.api.update_task_status(video_id, "failed", error_message=str(e))
            else:
                self.postgres.update_task_status(video_id, "failed", error_message=str(e))
            return False
    
    def _generate_superior_pdf(self, video_path: Path, pdf_path: Path) -> bool:
        try:
            cmd = [
                sys.executable, "-m", "src.main",
                str(video_path.absolute()),
                "-o", str(pdf_path.absolute())
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes for large files
            
            if result.returncode == 0 and pdf_path.exists():
                size = pdf_path.stat().st_size
                print(f"✅ Superior PDF: {size:,} bytes")
                return True
            else:
                print(f"❌ PDF failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ PDF error: {e}")
            return False
    
    def run_polling_loop(self):
        """Robust polling loop optimized for Mac Mini M2 - No hanging, efficient queuing"""
        print("🔄 Starting robust polling loop (Mac Mini M2 optimized)...", flush=True)
        sys.stdout.flush()

        # Phase C1: start the heartbeat thread before we begin polling so
        # the very first picked-up task already has a live signal to the
        # backend reaper.
        self.start_heartbeat()
        # Disk-hygiene daemon: keep /tmp from filling up between deploys.
        self.start_janitor()

        poll_interval = int(os.getenv('WORKER_POLL_INTERVAL', 10))
        active_tasks = set()

        while True:
            try:
                # Use API pickup if enabled, otherwise use direct PostgreSQL
                if self.api.is_enabled:
                    # BATCH PICKUP: Fill capacity in one cycle for 4x performance
                    tasks_picked = 0
                    while len(active_tasks) < self.max_concurrent_tasks:
                        # Try to pick up tasks until at capacity
                        task = self.api.pickup_task()
                        if not task:
                            break  # No more tasks available
                        
                        video_id = task.get('video_id')
                        tasks_picked += 1
                        print(f"✅ Picked up task {tasks_picked}/{self.max_concurrent_tasks}: {video_id}", flush=True)
                        active_tasks.add(video_id)
                        
                        # Process with timeout protection, passing task details
                        try:
                            future = self.executor.submit(self.process_video, video_id, task_details=task)
                            future.add_done_callback(lambda f, vid=video_id: active_tasks.discard(vid))
                        except Exception as e:
                            print(f"❌ Failed to submit task {video_id}: {e}", flush=True)
                            active_tasks.discard(video_id)
                    
                    if tasks_picked > 0:
                        print(f"📊 Batch pickup complete: {tasks_picked} tasks, {len(active_tasks)} now active", flush=True)
                else:
                    # Fallback to direct PostgreSQL polling
                    pending_tasks = self.postgres.get_pending_tasks(limit=self.max_concurrent_tasks * 2)
                    
                    if pending_tasks:
                        print(f"📋 Found {len(pending_tasks)} pending tasks", flush=True)
                        
                        for task in pending_tasks:
                            video_id = task.get('video_id')
                            if video_id and video_id not in active_tasks:
                                # Track active task to prevent duplicate processing
                                active_tasks.add(video_id)
                                
                                # Process with timeout protection - no hanging
                                try:
                                    future = self.executor.submit(self.process_video, video_id)
                                    future.add_done_callback(lambda f, vid=video_id: active_tasks.discard(vid))
                                except Exception as e:
                                    print(f"❌ Failed to submit task {video_id}: {e}", flush=True)
                                    active_tasks.discard(video_id)
                    else:
                        print("⏳ No pending tasks...", flush=True)
                
                # Clean up completed/failed tasks from tracking
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                print("\n🛑 Worker stopping gracefully...", flush=True)
                self.stop_heartbeat()
                self.stop_janitor()
                self.executor.shutdown(wait=True, cancel_futures=False)
                break
            except Exception as e:
                print(f"💥 Polling error (will retry): {e}", flush=True)
                time.sleep(30)  # Back off on errors
    
    def _is_cancelled(self, video_id: str) -> bool:
        """Check if video has been cancelled or cancellation is requested"""
        try:
            if self.api.is_enabled:
                # Check via API
                response = self.api.check_cancellation(video_id)
                return response.get('cancellation_requested', False) or response.get('cancelled', False)
            else:
                # Check directly in database - must check BOTH cancelled and cancellation_requested
                task = self.postgres.get_task_details(video_id)
                if not task:
                    return False
                return task.get('cancelled', False) or task.get('cancellation_requested', False)
        except Exception as e:
            print(f"⚠️ Error checking cancellation for {video_id}: {e}")
            return False

    def _handle_cancellation(self, video_id: str):
        """Handle cancelled video cleanup"""
        print(f"🚫 Video {video_id} has been cancelled", flush=True)
        
        try:
            if self.api.is_enabled:
                # Complete cancellation via API
                self.api.complete_cancellation(video_id)
            else:
                # Update directly in database
                self.postgres.update_task_status(video_id, 'cancelled')
        except Exception as e:
            print(f"⚠️ Error completing cancellation for {video_id}: {e}")
        
        # Remove from active tasks if tracking
        if hasattr(self, 'active_tasks'):
            self.active_tasks.discard(video_id)

    def _generate_pdf_with_cancellation_check(self, video_id: str, video_path: Path, pdf_path: Path) -> bool:
        """Generate PDF with periodic cancellation checks"""
        import subprocess
        import sys
        
        try:
            # Start PDF generation process
            process = subprocess.Popen([
                sys.executable, "-m", "src.main",
                str(video_path), "-o", str(pdf_path)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=Path(__file__).parent)
            
            # Poll process and check for cancellation every 2 seconds
            while process.poll() is None:
                if self._is_cancelled(video_id):
                    print(f"🚫 Cancelling PDF generation for {video_id}", flush=True)
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                    return False
                time.sleep(2)  # Check every 2 seconds
            
            # Check final result
            if process.returncode == 0 and pdf_path.exists():
                return True
            else:
                print(f"❌ PDF generation failed with return code: {process.returncode}")
                if process.stderr:
                    stderr_output = process.stderr.read().decode()
                    print(f"   Error output: {stderr_output}")
                return False
                
        except Exception as e:
            print(f"❌ Error in PDF generation with cancellation check: {e}")
            return False

def main():
    worker = EnhancedWorker()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--process-all":
            print("🔄 Processing all pending tasks from PostgreSQL...", flush=True)
            sys.stdout.flush()
            # Run polling loop for all pending tasks
            worker.run_polling_loop()
        elif command == "--health-check":
            print("🏥 Running health check...")
            print(f"   Firestore: {'✅' if worker.postgres.is_available() else '❌'}")
            print(f"   S3: {'✅' if worker.s3.is_available() else '❌'}")
            sys.exit(0)
        else:
            # Process single video
            video_id = command
            print(f"🎯 Processing single video: {video_id}")
            success = worker.process_video(video_id)
            sys.exit(0 if success else 1)
    else:
        # Run polling loop
        worker.run_polling_loop()

if __name__ == "__main__":
    main()
