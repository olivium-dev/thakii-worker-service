#!/usr/bin/env python3
"""
API Task Client for Worker Service
Replaces direct PostgreSQL access with API calls to backend
"""

import os
import time
import uuid
import json
import requests
import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import socket

load_dotenv()

# Feature flag for worker API
ENABLE_WORKER_API = os.getenv('ENABLE_WORKER_API', 'false').lower() == 'true'

# Backend API URL
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'https://thakii-02.fanusdigital.site/thakii-be')

# Worker ID - unique for each worker instance
WORKER_ID = os.getenv('WORKER_ID', f"worker-{socket.gethostname()}-{uuid.uuid4().hex[:8]}")

# Maximum concurrent tasks
MAX_CONCURRENT_TASKS = int(os.getenv('MAX_CONCURRENT_TASKS', '4'))

# API timeouts
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))  # seconds

# Retry configuration
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '2'))  # seconds

# Phase B5/C4: shared secret used by the backend's InternalApiMiddleware to
# authenticate /internal/* calls. Empty value = the backend gate is dormant
# (matches our two-phase rollout default).
INTERNAL_WORKER_SECRET = os.getenv('INTERNAL_WORKER_SECRET', '')


class APITaskClient:
    def __init__(self):
        """Initialize API Task Client"""
        self.backend_url = BACKEND_API_URL
        self.worker_id = WORKER_ID
        self.is_enabled = ENABLE_WORKER_API
        self.max_concurrent_tasks = MAX_CONCURRENT_TASKS

        # Create session for connection pooling.
        self.session = requests.Session()
        # Attach the shared internal secret to every request the session
        # makes so each /internal/* call carries the same auth header.
        if INTERNAL_WORKER_SECRET:
            self.session.headers.update({'X-Internal-Secret': INTERNAL_WORKER_SECRET})

        # Track active tasks
        self.active_tasks = set()

        print(f"🔧 API Task Client initialized")
        print(f"   Backend URL: {self.backend_url}")
        print(f"   Worker ID: {self.worker_id}")
        print(f"   API enabled: {self.is_enabled}")
        print(f"   Max concurrent tasks: {self.max_concurrent_tasks}")
        print(f"   Internal secret: {'configured' if INTERNAL_WORKER_SECRET else 'NOT configured (rollout phase)'}")
    
    def pickup_task(self) -> Optional[Dict[str, Any]]:
        """
        Pick up a task for processing via API
        
        Returns:
            Task object or None if no tasks available or API disabled
        """
        if not self.is_enabled:
            print("⚠️ Worker API is disabled. Cannot pick up tasks via API.")
            return None
        
        # Check if we're at capacity
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            print(f"⚠️ Worker at capacity ({len(self.active_tasks)}/{self.max_concurrent_tasks})")
            return None
        
        # Try to pick up a task with retries
        for attempt in range(MAX_RETRIES):
            try:
                print(f"🔄 Attempting to pickup task via API (attempt {attempt+1}/{MAX_RETRIES})...", flush=True)
                response = self.session.post(
                    f"{self.backend_url}/internal/worker/pickup-task",
                    json={
                        'worker_id': self.worker_id,
                        'worker_capacity': self.max_concurrent_tasks
                    },
                    timeout=REQUEST_TIMEOUT
                )
                
                print(f"📡 API Response: {response.status_code}", flush=True)
                
                # No content means no tasks available
                if response.status_code == 204:
                    print("⏳ No tasks available (204)", flush=True)
                    return None
                
                # Check for successful response
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and 'task' in data:
                        task = data['task']
                        video_id = task['video_id']
                        
                        # Track this task
                        self.active_tasks.add(video_id)
                        
                        print(f"✅ Picked up task {video_id} via API", flush=True)
                        return task
                
                # Handle error
                print(f"❌ Failed to pick up task (attempt {attempt+1}/{MAX_RETRIES})", flush=True)
                print(f"   Status code: {response.status_code}", flush=True)
                print(f"   Response: {response.text}", flush=True)
                
            except Exception as e:
                print(f"❌ Error picking up task (attempt {attempt+1}/{MAX_RETRIES}): {e}", flush=True)
                import traceback
                traceback.print_exc()
            
            # Wait before retry
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        
        return None
    
    def update_task_status(self, video_id: str, status: str, **kwargs) -> bool:
        """
        Update task status via API
        
        Args:
            video_id: ID of the video task
            status: New status
            **kwargs: Additional fields to update
            
        Returns:
            bool: Success or failure
        """
        if not self.is_enabled:
            print("⚠️ Worker API is disabled. Cannot update task status via API.")
            return False
        
        # Prepare update data
        update_data = {
            'video_id': video_id,
            'worker_id': self.worker_id,
            'status': status
        }
        
        # Add optional fields
        if 'progress' in kwargs:
            update_data['progress'] = kwargs['progress']
        
        if 'pdf_url' in kwargs:
            update_data['pdf_url'] = kwargs['pdf_url']
        
        if 'error_message' in kwargs:
            update_data['error_message'] = kwargs['error_message']
        
        # Try to update task with retries
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.post(
                    f"{self.backend_url}/internal/worker/update-task",
                    json=update_data,
                    timeout=REQUEST_TIMEOUT
                )
                
                # Check for successful response
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        progress_msg = f" (progress: {update_data.get('progress', 'N/A')}%)" if 'progress' in update_data else ""
                        print(f"✅ Updated task {video_id} to {status} via API{progress_msg}", flush=True)
                        
                        # Remove from active tasks if completed or failed
                        if status in ['completed', 'done', 'failed']:
                            self.active_tasks.discard(video_id)
                        
                        return True
                
                # Handle error
                print(f"❌ Failed to update task {video_id} (attempt {attempt+1}/{MAX_RETRIES})")
                print(f"   Status code: {response.status_code}")
                print(f"   Response: {response.text}")
                
            except Exception as e:
                print(f"❌ Error updating task {video_id} (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            
            # Wait before retry
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        
        return False
    
    def check_cancellation(self, video_id: str) -> Dict[str, Any]:
        """
        Check if video cancellation is requested
        
        Args:
            video_id: ID of the video to check
            
        Returns:
            Dict with cancellation status information
        """
        if not self.is_enabled:
            print("⚠️ Worker API is disabled. Cannot check cancellation via API.")
            return {"cancelled": False, "cancellation_requested": False}
        
        try:
            response = self.session.get(
                f"{self.backend_url}/internal/worker/check-cancellation/{video_id}",
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "cancelled": data.get("cancelled", False),
                    "cancellation_requested": data.get("cancellation_requested", False),
                    "status": data.get("status"),
                    "cancellation_reason": data.get("cancellation_reason")
                }
            elif response.status_code == 404:
                print(f"⚠️ Video {video_id} not found when checking cancellation")
                return {"cancelled": False, "cancellation_requested": False}
            else:
                print(f"❌ Failed to check cancellation for {video_id}: {response.status_code}")
                return {"cancelled": False, "cancellation_requested": False}
                
        except Exception as e:
            print(f"❌ Error checking cancellation for {video_id}: {e}")
            return {"cancelled": False, "cancellation_requested": False}
    
    def complete_cancellation(self, video_id: str) -> bool:
        """
        Complete video cancellation (called by worker when stopping processing)
        
        Args:
            video_id: ID of the video to complete cancellation for
            
        Returns:
            bool: Success or failure
        """
        if not self.is_enabled:
            print("⚠️ Worker API is disabled. Cannot complete cancellation via API.")
            return False
        
        try:
            response = self.session.post(
                f"{self.backend_url}/internal/worker/complete-cancellation/{video_id}",
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"✅ Completed cancellation for {video_id} via API", flush=True)
                    
                    # Remove from active tasks
                    self.active_tasks.discard(video_id)
                    
                    return True
            
            print(f"❌ Failed to complete cancellation for {video_id}: {response.status_code}")
            return False
                
        except Exception as e:
            print(f"❌ Error completing cancellation for {video_id}: {e}")
            return False
    
    def send_heartbeat(self, active_task_ids: Optional[List[str]] = None) -> bool:
        """
        Send heartbeat to backend so the StaleTaskReaperService can tell
        this worker is alive. Always sends (even with zero active tasks)
        so the backend can age out tasks attributed to this worker.

        Args:
            active_task_ids: optional explicit list. If None, uses the
                client's tracked active_tasks set.

        Returns:
            bool: Success or failure
        """
        if not self.is_enabled:
            return True

        ids = list(active_task_ids) if active_task_ids is not None else list(self.active_tasks)

        try:
            response = self.session.post(
                f"{self.backend_url}/internal/worker/heartbeat",
                json={
                    'worker_id': self.worker_id,
                    # Canonical name expected by the backend DTO. We keep
                    # the legacy alias too so a partial deploy still works.
                    'active_task_ids': ids,
                    'active_tasks': ids,
                },
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return True

            print(f"❌ Failed to send heartbeat: status={response.status_code}, body={response.text[:200]}")

        except Exception as e:
            print(f"❌ Error sending heartbeat: {e}")

        return False
    
    def report_progress(self, video_id: str, phase: str, detail: Optional[Dict] = None) -> bool:
        """Phase 3: report fine-grained progress to /internal/worker/progress."""
        if not self.is_enabled:
            return True
        try:
            payload: Dict[str, Any] = {
                'video_id': video_id,
                'worker_id': self.worker_id,
                'phase': phase,
            }
            if detail is not None:
                payload['progress_detail'] = json.dumps(detail)
            resp = self.session.post(
                f"{self.backend_url}/internal/worker/progress",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"⚠️ report_progress({video_id}, {phase}) error: {e}", flush=True)
            return False

    def get_task_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task details via API
        
        Args:
            video_id: ID of the video task
            
        Returns:
            Task object or None if not found or API disabled
        """
        if not self.is_enabled:
            print("⚠️ Worker API is disabled. Cannot get task details via API.")
            return None
        
        # Try to get task details with retries
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    f"{self.backend_url}/internal/get-task/{video_id}",
                    timeout=REQUEST_TIMEOUT
                )
                
                # Check for successful response
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and 'task' in data:
                        return data['task']
                
                # Handle error
                print(f"❌ Failed to get task details for {video_id} (attempt {attempt+1}/{MAX_RETRIES})")
                print(f"   Status code: {response.status_code}")
                print(f"   Response: {response.text}")
                
            except Exception as e:
                print(f"❌ Error getting task details for {video_id} (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            
            # Wait before retry
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        
        return None
    
    def is_available(self) -> bool:
        """
        Check if the API is available
        
        Returns:
            bool: True if API is enabled and backend is reachable
        """
        if not self.is_enabled:
            return False
        
        try:
            response = self.session.get(
                f"{self.backend_url}/health",
                timeout=REQUEST_TIMEOUT
            )
            return response.status_code == 200
        except Exception:
            return False

# Create singleton instance
api_client = APITaskClient()
