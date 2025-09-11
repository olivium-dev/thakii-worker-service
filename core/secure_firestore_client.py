#!/usr/bin/env python3
"""
Enhanced Firebase Authentication with Security Improvements
"""

import os
import json
import base64
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import logging
import datetime

# Load environment variables
load_dotenv()

# Setup secure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SecureFirestoreClient:
    def __init__(self):
        self.db = self._initialize_firestore()
        self.collection_name = 'video_tasks'
        self._credential_source = None
        self._initialized_at = datetime.datetime.now()
    
    def _initialize_firestore(self) -> Optional[firestore.Client]:
        """Initialize Firestore with multiple authentication methods"""
        try:
            if firebase_admin._apps:
                logger.info("🔐 Firebase already initialized, reusing existing app")
                return firestore.client()
            
            # Method 1: Base64 encoded service account (GitHub Actions)
            service_account_b64 = os.getenv('FIREBASE_SERVICE_ACCOUNT_B64')
            if service_account_b64:
                try:
                    service_account_json = base64.b64decode(service_account_b64).decode('utf-8')
                    service_account_dict = json.loads(service_account_json)
                    
                    # Validate required fields
                    required_fields = ['type', 'project_id', 'private_key', 'client_email']
                    for field in required_fields:
                        if field not in service_account_dict:
                            raise ValueError(f"Missing required field: {field}")
                    
                    cred = credentials.Certificate(service_account_dict)
                    firebase_admin.initialize_app(cred)
                    self._credential_source = "base64_encoded"
                    logger.info("🔐 Firebase initialized with base64 service account")
                    return firestore.client()
                except Exception as e:
                    logger.warning(f"Base64 service account failed: {e}")
            
            # Method 2: Service account file path
            service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY')
            if service_account_path and os.path.exists(service_account_path):
                # Validate file permissions
                file_stat = os.stat(service_account_path)
                if file_stat.st_mode & 0o077:
                    logger.warning(f"⚠️ Service account file has overly permissive permissions: {oct(file_stat.st_mode)}")
                
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                self._credential_source = "service_account_file"
                logger.info("🔐 Firebase initialized with service account file")
                return firestore.client()
            
            # Method 3: Default credentials (ADC)
            firebase_admin.initialize_app()
            self._credential_source = "default_credentials"
            logger.info("🔐 Firebase initialized with default credentials")
            return firestore.client()
            
        except Exception as e:
            logger.error(f"❌ Firebase initialization failed: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Firestore is available and test connection"""
        if self.db is None:
            return False
        
        try:
            # Test connection with a simple operation
            self.db.collection('_health_check').limit(1).get()
            return True
        except Exception as e:
            logger.error(f"Firestore connection test failed: {e}")
            return False
    
    def get_credential_info(self) -> Dict[str, Any]:
        """Get information about current credential source"""
        return {
            "available": self.is_available(),
            "credential_source": self._credential_source,
            "collection": self.collection_name,
            "initialized_at": self._initialized_at.isoformat(),
            "uptime_seconds": (datetime.datetime.now() - self._initialized_at).total_seconds()
        }
    
    def update_task_status(self, video_id: str, status: str, **kwargs) -> bool:
        """Update task status with enhanced error handling"""
        if not self.is_available():
            logger.warning(f"⚠️ Cannot update status for {video_id}: Firestore not available")
            return False
        
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.datetime.now(),
                'worker_source': self._credential_source
            }
            
            if status == 'processing':
                update_data['processing_start'] = datetime.datetime.now()
            elif status in ['completed', 'failed']:
                update_data['processing_end'] = datetime.datetime.now()
            
            # Add any additional fields
            update_data.update(kwargs)
            
            doc_ref = self.db.collection(self.collection_name).document(video_id)
            doc_ref.update(update_data)
            
            logger.info(f"✅ Status updated: {video_id} → {status}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update status for {video_id}: {e}")
            return False
    
    def get_task_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get task details with enhanced error handling"""
        if not self.is_available():
            logger.warning(f"⚠️ Cannot get task details for {video_id}: Firestore not available")
            return None
        
        try:
            doc_ref = self.db.collection(self.collection_name).document(video_id)
            doc = doc_ref.get()
            
            if doc.exists:
                task_data = doc.to_dict()
                task_data['id'] = doc.id
                logger.info(f"✅ Task details retrieved: {video_id}")
                return task_data
            else:
                logger.warning(f"⚠️ Task not found: {video_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get task details for {video_id}: {e}")
            return None

    def get_pending_tasks(self, limit: int = 5) -> list:
        """Get pending tasks with enhanced filtering"""
        if not self.is_available():
            logger.warning("⚠️ Cannot get pending tasks: Firestore not available")
            return []
        
        try:
            tasks_ref = self.db.collection(self.collection_name)
            query = tasks_ref.where('status', '==', 'in_queue').limit(limit)
            docs = query.get()
            
            tasks = []
            for doc in docs:
                task_data = doc.to_dict()
                task_data['id'] = doc.id
                tasks.append(task_data)
            
            logger.info(f"✅ Retrieved {len(tasks)} pending tasks")
            return tasks
            
        except Exception as e:
            logger.error(f"❌ Failed to get pending tasks: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        health_info = {
            "timestamp": datetime.datetime.now().isoformat(),
            "firestore_available": self.is_available(),
            "credential_info": self.get_credential_info()
        }
        
        if self.is_available():
            try:
                # Test basic operations
                test_doc = f"health_check_{int(datetime.datetime.now().timestamp())}"
                doc_ref = self.db.collection('_health_checks').document(test_doc)
                doc_ref.set({"test": True, "timestamp": datetime.datetime.now()})
                doc_ref.delete()
                
                health_info["operations_test"] = "passed"
                logger.info("✅ Firestore health check passed")
            except Exception as e:
                health_info["operations_test"] = f"failed: {e}"
                logger.error(f"❌ Firestore operations test failed: {e}")
        
        return health_info

# Create global instance
secure_firestore_client = SecureFirestoreClient()
