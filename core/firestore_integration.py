#!/usr/bin/env python3
"""
Minimal Firestore Integration for Worker Status Updates
"""

import os
import datetime
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

class WorkerFirestoreClient:
    def __init__(self):
        self.db = self._initialize_firestore()
        self.collection_name = 'video_tasks'
    
    def _initialize_firestore(self) -> Optional[firestore.Client]:
        try:
            if not firebase_admin._apps:
                service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY')
                if service_account_path and os.path.exists(service_account_path):
                    cred = credentials.Certificate(service_account_path)
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_admin.initialize_app()
            return firestore.client()
        except Exception as e:
            print(f"❌ Firebase initialization failed: {e}")
            return None
    
    def is_available(self) -> bool:
        return self.db is not None
    
    def update_task_status(self, video_id: str, status: str, **kwargs) -> bool:
        if not self.is_available():
            print(f"⚠️  Cannot update status for {video_id}: Firestore not available")
            return False
        
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.datetime.now(),
            }
            
            if status == 'processing':
                update_data['processing_start'] = datetime.datetime.now()
            elif status in ['completed', 'failed']:
                update_data['processing_end'] = datetime.datetime.now()
            
            update_data.update(kwargs)
            
            doc_ref = self.db.collection(self.collection_name).document(video_id)
            doc_ref.update(update_data)
            
            print(f"✅ Status updated: {video_id} → {status}")
            return True
        except Exception as e:
            print(f"❌ Failed to update status for {video_id}: {e}")
            return False
    
    def get_task_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None
        
        try:
            doc_ref = self.db.collection(self.collection_name).document(video_id)
            doc = doc_ref.get()
            
            if doc.exists:
                task_data = doc.to_dict()
                task_data['id'] = doc.id
                return task_data
            else:
                return None
        except Exception as e:
            print(f"❌ Failed to get task details for {video_id}: {e}")
            return None

    def get_pending_tasks(self) -> list:
        if not self.is_available():
            return []
        
        try:
            tasks_ref = self.db.collection(self.collection_name)
            query = tasks_ref.where('status', '==', 'in_queue').limit(5)
            docs = query.get()
            
            tasks = []
            for doc in docs:
                task_data = doc.to_dict()
                task_data['id'] = doc.id
                tasks.append(task_data)
            
            return tasks
        except Exception as e:
            print(f"❌ Failed to get pending tasks: {e}")
            return []

firestore_client = WorkerFirestoreClient()
