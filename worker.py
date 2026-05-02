#!/usr/bin/env python3
"""
Optimized Worker for Mac Mini M2 - High Performance Video Processing
- Uses Apple Metal (MPS) GPU acceleration
- Robust queuing with no hanging
- Optimal CPU/RAM utilization
- No fallback code - production ready
"""

import json
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

# ─── Persistent workdir helpers (Phase 1 of Stuck-Task Hardening v3) ────

WORKDIR_BASE = Path(os.getenv(
    'WORKER_WORKDIR_BASE',
    os.path.join(os.path.dirname(__file__), 'workdir'),
))

WORKDIR_RETENTION_HOURS = int(os.getenv('WORKDIR_RETENTION_HOURS', '24'))

STAGES = ('download', 'audio', 'frames', 'transcribe', 'pdf', 'upload')


def _workdir_for(video_id: str) -> Path:
    return WORKDIR_BASE / video_id


def _stage_sentinel(workdir: Path, stage: str) -> Path:
    return workdir / f'.stage.{stage}.done'


def _stage_done(workdir: Path, stage: str) -> bool:
    return _stage_sentinel(workdir, stage).exists()


def _mark_stage_done(workdir: Path, stage: str) -> None:
    sentinel = _stage_sentinel(workdir, stage)
    tmp = sentinel.with_suffix('.tmp')
    tmp.write_text(str(time.time()))
    tmp.rename(sentinel)


def _acquire_task_workdir(video_id: str) -> Path:
    """Create (or re-enter) the persistent workdir for *video_id*.
    Writes a lock.json with this process's PID so the janitor skips it."""
    wd = _workdir_for(video_id)
    wd.mkdir(parents=True, exist_ok=True)

    lock_file = wd / 'lock.json'
    existing = None
    if lock_file.exists():
        try:
            existing = json.loads(lock_file.read_text())
        except Exception:
            pass
    if existing:
        old_pid = existing.get('pid')
        if old_pid and old_pid != os.getpid():
            try:
                os.kill(old_pid, 0)
                print(f"⚠️ workdir {wd} locked by PID {old_pid} — overriding (stale?)", flush=True)
            except OSError:
                pass

    lock_payload = json.dumps({
        'pid': os.getpid(),
        'video_id': video_id,
        'acquired_at': time.time(),
    })
    tmp_lock = lock_file.with_suffix('.tmp')
    tmp_lock.write_text(lock_payload)
    tmp_lock.rename(lock_file)
    return wd


def _release_task_workdir(video_id: str, keep: bool = True) -> None:
    """Remove the lock.  If *keep* is False, delete the entire workdir now."""
    wd = _workdir_for(video_id)
    lock_file = wd / 'lock.json'
    try:
        lock_file.unlink(missing_ok=True)
    except Exception:
        pass
    if not keep and wd.exists():
        try:
            shutil.rmtree(wd, ignore_errors=True)
        except Exception:
            pass


def _workdir_is_locked(wd: Path) -> bool:
    lock = wd / 'lock.json'
    if not lock.exists():
        return False
    try:
        data = json.loads(lock.read_text())
        pid = data.get('pid')
        if pid:
            os.kill(pid, 0)
            return True
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return False

class EnhancedWorker:
    def __init__(self):
        self.postgres = postgres_client
        self.s3 = s3_client
        self.api = api_client
        
        # Mac Mini M2 Optimization: Use multiple cores efficiently
        self.max_concurrent_tasks = int(os.getenv('MAX_CONCURRENT_TASKS', min(multiprocessing.cpu_count(), 3)))
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_tasks)

        # Phase 1: persistent workdir (feature-flagged for rollback)
        self.use_persistent_workdir = os.getenv('WORKER_USE_PERSISTENT_WORKDIR', 'true').lower() in ('1', 'true', 'yes')
        if self.use_persistent_workdir:
            WORKDIR_BASE.mkdir(parents=True, exist_ok=True)

        # Configure intelligent storage selection
        self.temp_base_dir = self._get_temp_storage_path()

        # Global task timeout ceiling. Phase 2 adaptive timeouts from the
        # backend can lower this per-task; this is the fallback / max.
        self.task_timeout = int(os.getenv('TASK_TIMEOUT_SECONDS', '1800'))
        self.timeout_floor = int(os.getenv('WORKER_TIMEOUT_FLOOR_SECONDS', '900'))
        self.timeout_ceiling = int(os.getenv('WORKER_TIMEOUT_CEILING_SECONDS', str(self.task_timeout)))

        # Heartbeat configuration. The daemon thread wakes every
        # HEARTBEAT_INTERVAL seconds and pings the backend so the reaper
        # knows this worker (and the rows it owns) are alive.
        self.heartbeat_interval = int(os.getenv('WORKER_HEARTBEAT_INTERVAL', '15'))
        self._active_task_ids = set()
        self._active_task_lock = threading.Lock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None

        # Maps video_id -> live subprocess.Popen so the outer timeout /
        # crash handler can terminate the process tree (otherwise an
        # orphan whisper subprocess keeps running and fights the next
        # pickup).
        self._task_subprocesses: dict = {}

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
        print(f"   Persistent Workdir: {'✅ ' + str(WORKDIR_BASE) if self.use_persistent_workdir else '❌ (using tempdir)'}", flush=True)
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
                            if _workdir_is_locked(Path(path)):
                                continue
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

        # Phase 1: prune expired persistent workdirs (> WORKDIR_RETENTION_HOURS)
        if self.use_persistent_workdir and WORKDIR_BASE.is_dir():
            retention_seconds = WORKDIR_RETENTION_HOURS * 3600
            try:
                for wd in WORKDIR_BASE.iterdir():
                    if not wd.is_dir():
                        continue
                    if _workdir_is_locked(wd):
                        continue
                    try:
                        age = now - wd.stat().st_mtime
                    except OSError:
                        continue
                    if age > retention_seconds:
                        try:
                            sz = self._dir_size(str(wd))
                            shutil.rmtree(wd, ignore_errors=True)
                            bytes_freed += sz
                            removed_dirs += 1
                        except Exception:
                            pass
            except Exception as e:
                print(f"⚠️ {label} workdir cleanup error: {e}", flush=True)

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

    # ====== Heartbeat / active-task / progress tracking helpers ======

    def _track_task(self, video_id: str):
        with self._active_task_lock:
            self._active_task_ids.add(video_id)

    def _untrack_task(self, video_id: str):
        with self._active_task_lock:
            self._active_task_ids.discard(video_id)

    def _snapshot_active_tasks(self):
        with self._active_task_lock:
            return list(self._active_task_ids)

    # ── Phase 3: progress reporting thread ──

    def _progress_loop(self):
        """Daemon thread: every 15s reads progress.json from each active
        task's workdir and POSTs to backend /internal/worker/progress."""
        interval = int(os.getenv('WORKER_PROGRESS_INTERVAL', '15'))
        print(f"📊 Progress thread started (interval={interval}s)", flush=True)
        while not self._heartbeat_stop.wait(interval):
            if not self.use_persistent_workdir:
                continue
            for vid in self._snapshot_active_tasks():
                try:
                    pf = _workdir_for(vid) / 'progress.json'
                    if not pf.exists():
                        continue
                    data = json.loads(pf.read_text())
                    phase = data.get('phase', 'unknown')
                    self.api.report_progress(vid, phase, data)
                except Exception:
                    pass
        print("📊 Progress thread stopping", flush=True)

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
        # Phase 3: start progress reporting on the same stop event
        progress_t = threading.Thread(
            target=self._progress_loop, name='worker-progress', daemon=True)
        progress_t.start()

    def stop_heartbeat(self):
        self._heartbeat_stop.set()

    # ====== Public process_video with timeout enforcement (Phase C2) ======

    def process_video(self, video_id: str, s3_key: str = None, filename: str = None, task_details: dict = None) -> bool:
        """Public entry point. Enforces self.task_timeout via a
        single-task ThreadPoolExecutor + try/except BaseException
        crash-to-failed handler.

        Subprocess kill on timeout: _process_video_impl registers any
        Popen it launches into self._task_subprocesses[video_id]. On
        timeout, we look it up and kill it -- otherwise an orphan
        whisper/ffmpeg keeps running and fights the next pickup for
        CPU/GPU."""
        self._track_task(video_id)

        # Phase 2: per-task adaptive timeout from backend hint
        effective_timeout = self.task_timeout
        if task_details:
            hint = task_details.get('timeout_seconds_hint')
            if hint is not None:
                try:
                    effective_timeout = max(self.timeout_floor, min(int(hint), self.timeout_ceiling))
                    print(f"⏱️ {video_id}: adaptive timeout={effective_timeout}s (hint={hint}, floor={self.timeout_floor}, ceil={self.timeout_ceiling})", flush=True)
                except (ValueError, TypeError):
                    pass

        inner = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"task-{video_id}")
        try:
            future = inner.submit(
                self._process_video_impl, video_id, s3_key, filename, task_details)
            try:
                return future.result(timeout=effective_timeout)
            except FuturesTimeoutError:
                msg = f"task timed out after {self.task_timeout}s"
                print(f"⏱️ {video_id}: {msg}", flush=True)
                self._kill_task_subprocess(video_id)
                self._mark_failed(video_id, msg)
                return False
        except BaseException as e:  # noqa: BLE001 — catch *anything*
            tb = traceback.format_exc()
            msg = f"worker crash: {type(e).__name__}: {e}"
            print(f"💥 {video_id}: {msg}\n{tb}", flush=True)
            try:
                self._kill_task_subprocess(video_id)
                self._mark_failed(video_id, msg)
            except Exception as inner_err:
                print(f"⚠️ Failed to mark {video_id} as failed after crash: {inner_err}", flush=True)
            return False
        finally:
            try:
                inner.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                inner.shutdown(wait=False)
            self._untrack_task(video_id)
            self._task_subprocesses.pop(video_id, None)

    def _register_task_subprocess(self, video_id: str, proc):
        """Called by _generate_pdf_with_cancellation_check so the outer
        timeout / crash handler can terminate the process tree."""
        self._task_subprocesses[video_id] = proc

    def _kill_task_subprocess(self, video_id: str):
        proc = self._task_subprocesses.get(video_id)
        if proc is None:
            return
        try:
            if proc.poll() is None:
                print(f"🔪 Killing subprocess pid={proc.pid} for {video_id}", flush=True)
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        except Exception as e:
            print(f"⚠️ Error killing subprocess for {video_id}: {e}", flush=True)

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

        workdir = None
        try:
            if self._is_cancelled(video_id):
                print(f"⚠️ Video {video_id} was cancelled before processing", flush=True)
                self._handle_cancellation(video_id)
                return False

            if self.api.is_enabled:
                self.api.update_task_status(video_id, "processing", progress=0)
            else:
                self.postgres.update_task_status(video_id, "processing")

            if task_details:
                task = task_details
            else:
                task = self.postgres.get_task_details(video_id)
                if not task:
                    self._update_status(video_id, "failed", error_message="Task not found")
                    return False

            filename = filename or task.get('filename', f'{video_id}.mp4')
            s3_key = s3_key or task.get('s3_key') or task.get('s3_path')

            # Phase 1: acquire persistent workdir (or fall back to tempdir)
            if self.use_persistent_workdir:
                workdir = _acquire_task_workdir(video_id)
                print(f"   📁 Persistent workdir: {workdir}", flush=True)
            else:
                workdir = Path(tempfile.mkdtemp(dir=self.temp_base_dir))
                print(f"   📁 Temp workdir: {workdir}", flush=True)
            sys.stdout.flush()

            video_path = workdir / filename
            pdf_path = workdir / f"{video_id}.pdf"

            # ── Stage: download ──
            if not _stage_done(workdir, 'download'):
                if self._is_cancelled(video_id):
                    self._handle_cancellation(video_id)
                    return False

                self._update_status(video_id, "processing", progress=10)

                pre_free_gb = self._get_free_gb(str(workdir))
                if pre_free_gb < self.min_free_gb_to_pickup:
                    print(f"⚠️ Free {pre_free_gb:.2f} GB < threshold {self.min_free_gb_to_pickup} GB; emergency sweep", flush=True)
                    self._cleanup_temp_files(max_age_seconds=60, label='pre-task')

                if not self.s3.download_video(video_id, str(video_path), s3_key=s3_key):
                    detail = getattr(self.s3, 'last_error', None) or 'unknown error'
                    err = f"Download failed (s3_key={s3_key}, file={filename}): {detail}"
                    print(f"❌ {err}", flush=True)
                    self._update_status(video_id, "failed", error_message=err)
                    return False

                _mark_stage_done(workdir, 'download')
                self.api.report_progress(video_id, 'download', {'status': 'done'})
                print(f"   ✅ Stage download complete for {video_id}", flush=True)
            else:
                print(f"   ⏭️  Stage download already done for {video_id} (sentinel present)", flush=True)

            # ── Stage: PDF generation (covers audio + frames + transcribe + pdf) ──
            if not _stage_done(workdir, 'pdf'):
                if self._is_cancelled(video_id):
                    self._handle_cancellation(video_id)
                    return False

                self._update_status(video_id, "processing", progress=30)

                if not self._generate_pdf_with_cancellation_check(video_id, video_path, pdf_path):
                    if self._is_cancelled(video_id):
                        self._handle_cancellation(video_id)
                    else:
                        self._update_status(video_id, "failed", error_message="PDF generation failed")
                    return False

                _mark_stage_done(workdir, 'pdf')
                self.api.report_progress(video_id, 'pdf', {'status': 'done'})
                print(f"   ✅ Stage pdf complete for {video_id}", flush=True)
            else:
                print(f"   ⏭️  Stage pdf already done for {video_id} (sentinel present)", flush=True)

            # ── Stage: upload ──
            if not _stage_done(workdir, 'upload'):
                if self._is_cancelled(video_id):
                    self._handle_cancellation(video_id)
                    return False

                self._update_status(video_id, "processing", progress=80)

                pdf_url = self.s3.upload_pdf(str(pdf_path), video_id)
                if not pdf_url:
                    self._update_status(video_id, "failed", error_message="Upload failed")
                    return False

                _mark_stage_done(workdir, 'upload')
                self.api.report_progress(video_id, 'upload', {'status': 'done'})
                print(f"   ✅ Stage upload complete for {video_id}", flush=True)
            else:
                bucket = self.s3.bucket_name
                region = os.getenv('AWS_DEFAULT_REGION', 'us-east-2')
                pdf_url = f"https://{bucket}.s3.{region}.amazonaws.com/pdfs/{video_id}/{video_id}.pdf"
                print(f"   ⏭️  Stage upload already done for {video_id} (sentinel present)", flush=True)

            if self._is_cancelled(video_id):
                try:
                    self.s3.delete_file(f"pdfs/{video_id}.pdf")
                except Exception:
                    pass
                self._handle_cancellation(video_id)
                return False

            self._update_status(video_id, "done", pdf_url=pdf_url, progress=100)
            print(f"🎉 Success: {video_id}", flush=True)
            return True

        except Exception as e:
            self._update_status(video_id, "failed", error_message=str(e))
            return False
        finally:
            if workdir:
                if self.use_persistent_workdir:
                    _release_task_workdir(video_id, keep=True)
                else:
                    try:
                        shutil.rmtree(workdir, ignore_errors=True)
                    except Exception:
                        pass

    def _update_status(self, video_id: str, status: str, **kwargs):
        """Thin wrapper — routes through API when enabled, else Postgres."""
        try:
            if self.api.is_enabled:
                self.api.update_task_status(video_id, status, **kwargs)
            else:
                self.postgres.update_task_status(video_id, status, **kwargs)
        except Exception as e:
            print(f"⚠️ _update_status({video_id}, {status}) error: {e}", flush=True)
    
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
        """Generate PDF with periodic cancellation checks.

        IMPORTANT: previously this used stdout=PIPE, stderr=PIPE with no
        reader, so the subprocess (whisper transcription) deadlocked the
        moment it produced more than the OS pipe buffer (~64 KB on
        macOS). That's why every >2 GB video stalled at progress=30% for
        hours, regardless of CPU vs MPS or video size: pipe-buffer
        overflow, NOT slow inference.

        Now we redirect both streams to a per-task log file living in
        the same temp dir as the video. No PIPE, no buffer, no deadlock,
        and we still get all the whisper output for forensics."""
        import subprocess
        import sys

        # Per-task log so the kernel never has to buffer subprocess output.
        log_path = Path(str(pdf_path) + '.gen.log')
        try:
            log_fh = open(log_path, 'wb', buffering=0)
        except Exception as e:
            print(f"⚠️ Could not open per-task log {log_path}: {e}; falling back to DEVNULL", flush=True)
            log_fh = subprocess.DEVNULL

        try:
            print(f"🎬 Starting PDF generation. Subprocess log: {log_path}", flush=True)
            process_start = time.time()

            # Phase 5: pass --workdir and --resume so transcription can
            # checkpoint to transcript.partial.json and resume after a kill.
            cmd_args = [
                sys.executable, "-u", "-m", "src.main",
                str(video_path), "-o", str(pdf_path),
            ]
            # Infer workdir from the pdf_path's parent (it lives in the persistent workdir)
            task_workdir = pdf_path.parent if self.use_persistent_workdir else None
            if task_workdir and task_workdir.exists():
                cmd_args.extend(["--workdir", str(task_workdir), "--resume"])

            process = subprocess.Popen(
                cmd_args,
                stdout=log_fh, stderr=subprocess.STDOUT,
                cwd=Path(__file__).parent,
            )

            # Register so the outer task_timeout / crash handler can
            # terminate this process if the inner thread is stuck.
            self._register_task_subprocess(video_id, process)

            # Periodic-progress signal: every 60 s log the current size
            # of the per-task log file. Lets the operator distinguish
            # "subprocess actively writing" (size growing) from
            # "subprocess wedged" (size flat) without SSH access.
            last_log_check = time.time()
            last_log_size = 0

            while process.poll() is None:
                if self._is_cancelled(video_id):
                    print(f"🚫 Cancelling PDF generation for {video_id}", flush=True)
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    return False
                time.sleep(2)

                now = time.time()
                if now - last_log_check >= 60:
                    last_log_check = now
                    try:
                        current_size = log_path.stat().st_size if log_path.exists() else 0
                    except OSError:
                        current_size = 0
                    delta = current_size - last_log_size
                    elapsed = int(now - process_start)
                    print(
                        f"📈 PDF gen progress for {video_id}: elapsed={elapsed}s "
                        f"log_size={current_size} (+{delta} bytes since last check)",
                        flush=True
                    )
                    last_log_size = current_size

            if process.returncode == 0 and pdf_path.exists():
                return True

            # Surface the tail of the subprocess log so failure mode is visible.
            tail = ''
            try:
                if log_path.exists():
                    with open(log_path, 'rb') as f:
                        f.seek(0, 2)
                        size = f.tell()
                        f.seek(max(0, size - 4096))
                        tail = f.read().decode('utf-8', errors='replace')
            except Exception:
                pass
            print(f"❌ PDF generation failed (rc={process.returncode}). Last 4 KB of log:\n{tail}", flush=True)
            return False
        except Exception as e:
            print(f"❌ Error in PDF generation with cancellation check: {e}", flush=True)
            return False
        finally:
            if log_fh not in (None, subprocess.DEVNULL):
                try:
                    log_fh.close()
                except Exception:
                    pass

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
