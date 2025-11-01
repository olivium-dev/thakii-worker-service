#!/usr/bin/env python3
"""
HTTP-based PostgreSQL Client for Worker Service
Uses backend API for database operations instead of direct PostgreSQL connection
"""

import os
import requests
from typing import Optional, Dict, Any, List
import datetime
from dotenv import load_dotenv

load_dotenv()

class HTTPPostgresClient:
    def __init__(self):
        """Initialize HTTP-based PostgreSQL client for worker"""
        self.backend_url = os.getenv('BACKEND_API_URL', 'https://thakii-02.fanusdigital.site/thakii-be')
        self.timeout = 30
        print(f"✅ HTTP PostgreSQL client initialized - Backend: {self.backend_url}")
    
    def is_available(self) -> bool:
        """Check if backend API is available"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('database') == 'PostgreSQL'
            return False
        except Exception as e:
            print(f"❌ Backend API not available: {e}")
            return False
    
    def update_task_status(self, video_id: str, status: str, **kwargs) -> bool:
        """
        Update task status via backend API
        
        Args:
            video_id: ID of the video task
            status: New status
            **kwargs: Additional fields to update
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get task details to extract user_id (required by backend)
            task = self.get_task_details(video_id)
            if not task:
                print(f"❌ Cannot update status: task {video_id} not found")
                return False
            
            user_id = task.get('user_id') or task.get('user_email')
            if not user_id:
                print(f"❌ Cannot update status: user_id missing for task {video_id}")
                return False
            
            # Prepare update data
            update_data = {
                'video_id': video_id,
                'user_id': user_id,
                'status': status,
                'updated_at': datetime.datetime.now().isoformat(),
                **kwargs
            }
            
            # Add timing fields based on status
            if status == 'processing':
                update_data['processing_start'] = datetime.datetime.now().isoformat()
            elif status in ['completed', 'done', 'failed']:
                update_data['processing_end'] = datetime.datetime.now().isoformat()
            
            # Make API call to backend
            response = requests.post(
                f"{self.backend_url}/internal/task-update",
                json=update_data,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"✅ Updated task {video_id} to status: {status}")
                return True
            else:
                print(f"❌ Failed to update task status: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to update task status: {e}")
            return False
    
    def get_task_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task details via backend API
        
        Args:
            video_id: ID of the video task
        
        Returns:
            Dict with task details or None if not found
        """
        try:
            response = requests.get(
                f"{self.backend_url}/internal/get-task/{video_id}",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                print(f"Task {video_id} not found")
                return None
            else:
                print(f"❌ Failed to get task details: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Failed to get task details: {e}")
            return None
    
    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get pending tasks via backend API
        
        Args:
            limit: Maximum number of tasks to return
        
        Returns:
            List of pending tasks
        """
        try:
            response = requests.get(
                f"{self.backend_url}/internal/get-pending-tasks",
                params={'limit': limit},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json().get('tasks', [])
            else:
                print(f"❌ Failed to get pending tasks: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Failed to get pending tasks: {e}")
            return []
    
    def mark_task_processing(self, video_id: str, worker_id: str) -> bool:
        """
        Mark task as being processed by this worker
        
        Args:
            video_id: ID of the video task
            worker_id: Identifier for this worker
        
        Returns:
            bool: True if successfully claimed, False otherwise
        """
        return self.update_task_status(
            video_id, 
            'processing',
            processed_by_worker=worker_id,
            worker_start_time=datetime.datetime.now().isoformat()
        )
    
    def mark_task_completed(self, video_id: str, pdf_s3_key: str = None, **kwargs) -> bool:
        """
        Mark task as completed
        
        Args:
            video_id: ID of the video task
            pdf_s3_key: S3 key for generated PDF
            **kwargs: Additional completion data
        
        Returns:
            bool: True if successful, False otherwise
        """
        completion_data = {
            'processing_end': datetime.datetime.now().isoformat(),
            **kwargs
        }
        
        if pdf_s3_key:
            completion_data['pdf_s3_key'] = pdf_s3_key
            
        return self.update_task_status(video_id, 'completed', **completion_data)
    
    def mark_task_failed(self, video_id: str, error_message: str, **kwargs) -> bool:
        """
        Mark task as failed
        
        Args:
            video_id: ID of the video task
            error_message: Error description
            **kwargs: Additional failure data
        
        Returns:
            bool: True if successful, False otherwise
        """
        failure_data = {
            'error_message': error_message,
            'processing_end': datetime.datetime.now().isoformat(),
            **kwargs
        }
        
        return self.update_task_status(video_id, 'failed', **failure_data)

# Create global instance
http_postgres_client = HTTPPostgresClient()

# For backward compatibility, alias as postgres_client
postgres_client = http_postgres_client

if __name__ == "__main__":
    # Test the client
    print("Testing HTTP PostgreSQL client...")
    
    if http_postgres_client.is_available():
        print("✅ Backend API is available and has PostgreSQL")
        
        # Test getting pending tasks
        tasks = http_postgres_client.get_pending_tasks(limit=5)
        print(f"Found {len(tasks)} pending tasks")
        
    else:
        print("❌ Backend API is not available")
