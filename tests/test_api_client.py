#!/usr/bin/env python3
"""
Tests for API Task Client
"""

import unittest
import os
import sys
import json
import time
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the API client
from core.api_task_client import APITaskClient

class MockResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
    
    def json(self):
        return self._json_data

class TestAPITaskClient(unittest.TestCase):
    def setUp(self):
        # Create test client with known values
        self.client = APITaskClient()
        self.client.backend_url = "https://test-backend.example.com"
        self.client.worker_id = "test-worker-id"
        self.client.is_enabled = True
        self.client.max_concurrent_tasks = 4
        
        # Reset active tasks
        self.client.active_tasks = set()
    
    @patch('requests.Session.post')
    def test_pickup_task_success(self, mock_post):
        # Mock successful response
        mock_response = MockResponse(200, {
            'success': True,
            'task': {
                'video_id': 'test-video-id',
                'filename': 'test.mp4',
                's3_key': 'videos/test-video-id.mp4',
                'status': 'processing'
            }
        })
        mock_post.return_value = mock_response
        
        # Call pickup_task
        task = self.client.pickup_task()
        
        # Verify request
        mock_post.assert_called_once_with(
            "https://test-backend.example.com/internal/worker/pickup-task",
            json={
                'worker_id': 'test-worker-id',
                'worker_capacity': 4
            },
            timeout=10
        )
        
        # Verify response
        self.assertIsNotNone(task)
        self.assertEqual(task['video_id'], 'test-video-id')
        self.assertEqual(task['filename'], 'test.mp4')
        
        # Verify active tasks
        self.assertIn('test-video-id', self.client.active_tasks)
    
    @patch('requests.Session.post')
    def test_pickup_task_no_tasks(self, mock_post):
        # Mock 204 No Content response
        mock_post.return_value = MockResponse(204)
        
        # Call pickup_task
        task = self.client.pickup_task()
        
        # Verify request
        mock_post.assert_called_once()
        
        # Verify response
        self.assertIsNone(task)
        
        # Verify active tasks
        self.assertEqual(len(self.client.active_tasks), 0)
    
    @patch('requests.Session.post')
    def test_pickup_task_error(self, mock_post):
        # Mock error response
        mock_post.return_value = MockResponse(500, {'error': 'Server error'}, 'Server error')
        
        # Call pickup_task
        task = self.client.pickup_task()
        
        # Verify request
        mock_post.assert_called()
        
        # Verify response
        self.assertIsNone(task)
        
        # Verify active tasks
        self.assertEqual(len(self.client.active_tasks), 0)
    
    @patch('requests.Session.post')
    def test_update_task_status_success(self, mock_post):
        # Add task to active tasks
        self.client.active_tasks.add('test-video-id')
        
        # Mock successful response
        mock_post.return_value = MockResponse(200, {
            'success': True,
            'message': 'Task updated'
        })
        
        # Call update_task_status
        result = self.client.update_task_status(
            'test-video-id', 
            'completed', 
            progress=100, 
            pdf_url='https://example.com/test.pdf'
        )
        
        # Verify request
        mock_post.assert_called_once_with(
            "https://test-backend.example.com/internal/worker/update-task",
            json={
                'video_id': 'test-video-id',
                'worker_id': 'test-worker-id',
                'status': 'completed',
                'progress': 100,
                'pdf_url': 'https://example.com/test.pdf'
            },
            timeout=10
        )
        
        # Verify result
        self.assertTrue(result)
        
        # Verify task removed from active tasks
        self.assertNotIn('test-video-id', self.client.active_tasks)
    
    @patch('requests.Session.post')
    def test_update_task_status_error(self, mock_post):
        # Add task to active tasks
        self.client.active_tasks.add('test-video-id')
        
        # Mock error response
        mock_post.return_value = MockResponse(400, {'error': 'Bad request'}, 'Bad request')
        
        # Call update_task_status
        result = self.client.update_task_status('test-video-id', 'failed', error_message='Test error')
        
        # Verify request
        mock_post.assert_called()
        
        # Verify result
        self.assertFalse(result)
        
        # Verify task still in active tasks (only removed on success)
        self.assertIn('test-video-id', self.client.active_tasks)
    
    @patch('requests.Session.post')
    def test_send_heartbeat_success(self, mock_post):
        # Add tasks to active tasks
        self.client.active_tasks.add('test-video-id-1')
        self.client.active_tasks.add('test-video-id-2')
        
        # Mock successful response
        mock_post.return_value = MockResponse(200, {
            'success': True,
            'message': 'Heartbeat received'
        })
        
        # Call send_heartbeat
        result = self.client.send_heartbeat()
        
        # Verify request
        mock_post.assert_called_once_with(
            "https://test-backend.example.com/internal/worker/heartbeat",
            json={
                'worker_id': 'test-worker-id',
                'active_tasks': ['test-video-id-1', 'test-video-id-2']
            },
            timeout=10
        )
        
        # Verify result
        self.assertTrue(result)
    
    @patch('requests.Session.post')
    def test_send_heartbeat_no_tasks(self, mock_post):
        # No active tasks
        
        # Call send_heartbeat
        result = self.client.send_heartbeat()
        
        # Verify request not made
        mock_post.assert_not_called()
        
        # Verify result
        self.assertTrue(result)
    
    @patch('requests.Session.get')
    def test_get_task_details_success(self, mock_get):
        # Mock successful response
        mock_get.return_value = MockResponse(200, {
            'success': True,
            'task': {
                'video_id': 'test-video-id',
                'filename': 'test.mp4',
                's3_key': 'videos/test-video-id.mp4',
                'status': 'processing'
            }
        })
        
        # Call get_task_details
        task = self.client.get_task_details('test-video-id')
        
        # Verify request
        mock_get.assert_called_once_with(
            "https://test-backend.example.com/internal/get-task/test-video-id",
            timeout=10
        )
        
        # Verify response
        self.assertIsNotNone(task)
        self.assertEqual(task['video_id'], 'test-video-id')
        self.assertEqual(task['filename'], 'test.mp4')
    
    @patch('requests.Session.get')
    def test_get_task_details_not_found(self, mock_get):
        # Mock not found response
        mock_get.return_value = MockResponse(404, {'error': 'Task not found'}, 'Task not found')
        
        # Call get_task_details
        task = self.client.get_task_details('nonexistent-video-id')
        
        # Verify request
        mock_get.assert_called()
        
        # Verify response
        self.assertIsNone(task)
    
    @patch('requests.Session.get')
    def test_is_available_success(self, mock_get):
        # Mock successful response
        mock_get.return_value = MockResponse(200)
        
        # Call is_available
        result = self.client.is_available()
        
        # Verify request
        mock_get.assert_called_once_with(
            "https://test-backend.example.com/health",
            timeout=10
        )
        
        # Verify result
        self.assertTrue(result)
    
    @patch('requests.Session.get')
    def test_is_available_error(self, mock_get):
        # Mock error response
        mock_get.side_effect = Exception("Connection error")
        
        # Call is_available
        result = self.client.is_available()
        
        # Verify request
        mock_get.assert_called_once()
        
        # Verify result
        self.assertFalse(result)
    
    def test_is_available_disabled(self):
        # Disable API
        self.client.is_enabled = False
        
        # Call is_available
        result = self.client.is_available()
        
        # Verify result
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
