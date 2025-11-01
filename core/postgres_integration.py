#!/usr/bin/env python3
"""
PostgreSQL Integration for Worker Service
Supports both direct PostgreSQL and HTTP-based backend access
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Check if HTTP mode is enabled
USE_HTTP_MODE = os.getenv('USE_HTTP_DATABASE', 'false').lower() == 'true'

if USE_HTTP_MODE:
    # Use HTTP-based client for remote workers
    from .http_postgres_client import HTTPPostgresClient as WorkerPostgresClient
    print("🌐 Using HTTP-based PostgreSQL client")
else:
    # Use direct PostgreSQL connection for local workers
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from typing import Optional, Dict, Any, List
    import datetime
    
    class WorkerPostgresClient:
        def __init__(self):
            """Initialize PostgreSQL client for worker - Direct connection"""
            self.conn_params = {
                'host': os.getenv('POSTGRES_HOST', 'localhost'),
                'port': os.getenv('POSTGRES_PORT', '5432'),
                'database': os.getenv('POSTGRES_DB', 'thakii_production'),
                'user': os.getenv('POSTGRES_USER', 'thakii_user'),
                'password': os.getenv('POSTGRES_PASSWORD')
            }
            self._test_connection()
        
        def _test_connection(self):
            """Test PostgreSQL connection"""
            try:
                conn = psycopg2.connect(**self.conn_params)
                conn.close()
                print("✅ Direct PostgreSQL connection successful")
            except Exception as e:
                print(f"❌ PostgreSQL connection failed: {e}")
                raise
    
    def is_available(self) -> bool:
        """Check if PostgreSQL is available"""
        try:
            conn = psycopg2.connect(**self.conn_params)
            conn.close()
            return True
        except Exception as e:
            print(f"❌ PostgreSQL not available: {e}")
            return False
    
    def update_task_status(self, video_id: str, status: str, **kwargs) -> bool:
        """
        Update task status in PostgreSQL
        
        Args:
            video_id: ID of the video task
            status: New status
            **kwargs: Additional fields to update
        
        Returns:
            bool: True if successful, False otherwise
        """
        conn = psycopg2.connect(**self.conn_params)
        try:
            with conn.cursor() as cur:
                set_clauses = ['status = %s', 'updated_at = %s']
                values = [status, datetime.datetime.now()]
                
                # Add timing fields based on status
                if status == 'processing':
                    set_clauses.append('processing_start = %s')
                    values.append(datetime.datetime.now())
                elif status in ['completed', 'done', 'failed']:
                    set_clauses.append('processing_end = %s')
                    values.append(datetime.datetime.now())
                
                # Add additional fields
                for key, value in kwargs.items():
                    set_clauses.append(f'{key} = %s')
                    values.append(value)
                
                # Add video_id for WHERE clause
                values.append(video_id)
                
                query = f"""
                    UPDATE video_tasks 
                    SET {', '.join(set_clauses)}
                    WHERE video_id = %s
                """
                
                cur.execute(query, values)
                conn.commit()
                
                print(f"✅ Updated task {video_id} to status: {status}")
                return cur.rowcount > 0
                
        except Exception as e:
            print(f"❌ Failed to update task status: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_task_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task details from PostgreSQL
        
        Args:
            video_id: ID of the video task
        
        Returns:
            dict: Task details or None if not found
        """
        conn = psycopg2.connect(**self.conn_params)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM video_tasks 
                    WHERE video_id = %s
                """, (video_id,))
                
                result = cur.fetchone()
                if result:
                    task = dict(result)
                    # Convert datetime objects to ISO strings
                    for key, value in task.items():
                        if isinstance(value, datetime.datetime):
                            task[key] = value.isoformat()
                    return task
                return None
                
        except Exception as e:
            print(f"❌ Failed to get task details: {e}")
            return None
        finally:
            conn.close()
    
    def get_pending_tasks(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get pending tasks from PostgreSQL
        
        Args:
            limit: Maximum number of tasks to retrieve
        
        Returns:
            list: List of pending tasks
        """
        conn = psycopg2.connect(**self.conn_params)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM video_tasks 
                    WHERE status IN ('in_queue', 'uploaded')
                       OR (status = 'processing' AND processing_start < NOW() - INTERVAL '10 minutes')
                    ORDER BY created_at ASC
                    LIMIT %s
                """, (limit,))
                
                results = cur.fetchall()
                tasks = []
                
                for result in results:
                    task = dict(result)
                    # Convert datetime objects to ISO strings
                    for key, value in task.items():
                        if isinstance(value, datetime.datetime):
                            task[key] = value.isoformat()
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            print(f"❌ Failed to get pending tasks: {e}")
            return []
        finally:
            conn.close()
    
    def create_video_task(self, video_id: str, filename: str, 
                         user_id: str, user_email: str, 
                         status: str = "in_queue", **kwargs) -> Optional[Dict[str, Any]]:
        """
        Create a new video task in PostgreSQL
        
        Args:
            video_id: ID of the video
            filename: Name of the video file
            user_id: User ID
            user_email: User email
            status: Initial status
            **kwargs: Additional fields
        
        Returns:
            dict: Created task or None if failed
        """
        conn = psycopg2.connect(**self.conn_params)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO video_tasks 
                    (video_id, filename, user_id, user_email, status, upload_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (video_id, filename, user_id, user_email, status, 
                      datetime.datetime.now()))
                
                conn.commit()
                result = dict(cur.fetchone())
                
                # Convert datetime objects to ISO strings
                for key, value in result.items():
                    if isinstance(value, datetime.datetime):
                        result[key] = value.isoformat()
                
                print(f"✅ Created task {video_id}")
                return result
                
        except Exception as e:
            print(f"❌ Failed to create task: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all tasks from PostgreSQL
        
        Returns:
            list: List of all tasks
        """
        conn = psycopg2.connect(**self.conn_params)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM video_tasks 
                    ORDER BY created_at DESC
                """)
                
                results = cur.fetchall()
                tasks = []
                
                for result in results:
                    task = dict(result)
                    # Convert datetime objects to ISO strings
                    for key, value in task.items():
                        if isinstance(value, datetime.datetime):
                            task[key] = value.isoformat()
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            print(f"❌ Failed to get all tasks: {e}")
            return []
        finally:
            conn.close()
    
    def notify_backend_update(self, video_id: str, status: str, user_id: str, backend_url: str):
        """
        Notify backend via HTTP for WebSocket broadcast
        
        Args:
            video_id: ID of the video
            status: New status
            user_id: User ID
            backend_url: Backend API URL
        """
        import requests
        try:
            response = requests.post(
                f"{backend_url}/internal/task-update",
                json={
                    'video_id': video_id,
                    'status': status,
                    'user_id': user_id
                },
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✅ Notified backend about task update: {video_id}")
            else:
                print(f"⚠️  Backend notification failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Failed to notify backend: {e}")


# Global instance
postgres_client = WorkerPostgresClient()

