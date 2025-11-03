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

class APITaskClient:
    def __init__(self):
        """Initialize API Task Client"""
        self.backend_url = BACKEND_API_URL
        self.worker_id = WORKER_ID
        self.is_enabled = ENABLE_WORKER_API
        self.max_concurrent_tasks = MAX_CONCURRENT_TASKS
        
        # Create session for connection pooling
        self.session = requests.Session()
        
        # Track active tasks
        self.active_tasks = set()
        
        print(f"🔧 API Task Client initialized")
        print(f"   Backend URL: {self.backend_url}")
        print(f"   Worker ID: {self.worker_id}")
        print(f"   API enabled: {self.is_enabled}")
        print(f"   Max concurrent tasks: {self.max_concurrent_tasks}")
    
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
                response = self.session.post(
                    f"{self.backend_url}/internal/worker/pickup-task",
                    json={
                        'worker_id': self.worker_id,
                        'worker_capacity': self.max_concurrent_tasks
                    },
                    timeout=REQUEST_TIMEOUT
                )
                
                # No content means no tasks available
                if response.status_code == 204:
                    return None
                
                # Check for successful response
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and 'task' in data:
                        task = data['task']
                        video_id = task['video_id']
                        
                        # Track this task
                        self.active_tasks.add(video_id)
                        
                        print(f"✅ Picked up task {video_id} via API")
                        return task
                
                # Handle error
                print(f"❌ Failed to pick up task (attempt {attempt+1}/{MAX_RETRIES})")
                print(f"   Status code: {response.status_code}")
                print(f"   Response: {response.text}")
                
            except Exception as e:
                print(f"❌ Error picking up task (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            
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
                        print(f"✅ Updated task {video_id} to {status} via API")
                        
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
    
    def send_heartbeat(self) -> bool:
        """
        Send heartbeat to backend
        
        Returns:
            bool: Success or failure
        """
        if not self.is_enabled:
            return True  # No need to send heartbeat if API is disabled
        
        if not self.active_tasks:
            return True  # No active tasks to report
        
        try:
            response = self.session.post(
                f"{self.backend_url}/internal/worker/heartbeat",
                json={
                    'worker_id': self.worker_id,
                    'active_tasks': list(self.active_tasks)
                },
                timeout=REQUEST_TIMEOUT
            )
            
            # Check for successful response
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"💓 Heartbeat sent for {len(self.active_tasks)} active tasks")
                    return True
            
            print(f"❌ Failed to send heartbeat")
            print(f"   Status code: {response.status_code}")
            print(f"   Response: {response.text}")
            
        except Exception as e:
            print(f"❌ Error sending heartbeat: {e}")
        
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
