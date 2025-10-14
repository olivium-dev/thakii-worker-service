#!/usr/bin/env python3
"""
Backend Infrastructure Diagnostic Script
Run this on the backend server to diagnose S3 and Firestore issues
"""

import os
import sys
import json
import traceback
from datetime import datetime

def print_header(title):
    print("\n" + "=" * 70)
    print(f"🔍 {title}")
    print("=" * 70)

def print_result(test_name, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {test_name}")
    if details:
        print(f"   {details}")

def test_environment_variables():
    print_header("Environment Variables Check")
    
    required_vars = [
        'S3_BUCKET_NAME',
        'AWS_DEFAULT_REGION', 
        'GOOGLE_CLOUD_PROJECT',
        'FIREBASE_PROJECT_ID',
        'GOOGLE_APPLICATION_CREDENTIALS',
        'FIREBASE_SERVICE_ACCOUNT_KEY',
        'WORKER_SERVICE_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'KEY' in var or 'CREDENTIALS' in var:
                display_value = f"{value[:20]}..." if len(value) > 20 else value
            else:
                display_value = value
            print_result(f"{var}", True, f"= {display_value}")
        else:
            print_result(f"{var}", False, "Not set")
            missing_vars.append(var)
    
    return len(missing_vars) == 0, missing_vars

def test_file_access():
    print_header("File Access Check")
    
    files_to_check = [
        os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
        os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY'),
    ]
    
    all_good = True
    for file_path in files_to_check:
        if file_path:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    if content.strip():
                        print_result(f"File: {file_path}", True, "Exists and readable")
                    else:
                        print_result(f"File: {file_path}", False, "Exists but empty")
                        all_good = False
                except Exception as e:
                    print_result(f"File: {file_path}", False, f"Read error: {e}")
                    all_good = False
            else:
                print_result(f"File: {file_path}", False, "File not found")
                all_good = False
    
    return all_good

def test_s3_connection():
    print_header("S3 Connection Test")
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        # Test S3 client creation
        try:
            s3_client = boto3.client('s3')
            print_result("S3 Client Creation", True)
        except Exception as e:
            print_result("S3 Client Creation", False, str(e))
            return False
        
        # Test credentials
        try:
            s3_client.list_buckets()
            print_result("S3 Credentials", True, "Can list buckets")
        except NoCredentialsError:
            print_result("S3 Credentials", False, "No AWS credentials found")
            return False
        except ClientError as e:
            print_result("S3 Credentials", False, f"AWS error: {e}")
            return False
        
        # Test specific bucket access
        bucket_name = os.getenv('S3_BUCKET_NAME', 'thakii-video-storage-1753883631')
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            print_result(f"Bucket Access: {bucket_name}", True, "Can list objects")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                print_result(f"Bucket Access: {bucket_name}", False, "Bucket does not exist")
            elif error_code == 'AccessDenied':
                print_result(f"Bucket Access: {bucket_name}", False, "Access denied - check permissions")
            else:
                print_result(f"Bucket Access: {bucket_name}", False, f"Error: {error_code}")
            return False
        
        # Test upload capability (dry run)
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(b"test content")
                tmp_file_path = tmp_file.name
            
            test_key = f"test-uploads/diagnostic-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
            
            with open(tmp_file_path, 'rb') as f:
                s3_client.upload_fileobj(f, bucket_name, test_key)
            
            print_result("S3 Upload Test", True, f"Successfully uploaded {test_key}")
            
            # Clean up test file
            s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            os.unlink(tmp_file_path)
            
        except Exception as e:
            print_result("S3 Upload Test", False, str(e))
            return False
        
        return True
        
    except ImportError:
        print_result("S3 Test", False, "boto3 not installed")
        return False
    except Exception as e:
        print_result("S3 Test", False, f"Unexpected error: {e}")
        return False

def test_firestore_connection():
    print_header("Firestore Connection Test")
    
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # Test Firebase initialization
        try:
            if not firebase_admin._apps:
                project_id = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('FIREBASE_PROJECT_ID') or 'thakii-973e3'
                service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                
                if service_account_path and os.path.exists(service_account_path):
                    print_result("Firebase Init Method", True, f"Using service account: {service_account_path}")
                    cred = credentials.Certificate(service_account_path)
                    firebase_admin.initialize_app(cred, {'projectId': project_id})
                else:
                    print_result("Firebase Init Method", True, f"Using default credentials for project: {project_id}")
                    firebase_admin.initialize_app(options={'projectId': project_id})
            
            db = firestore.client()
            print_result("Firestore Client Creation", True)
            
        except Exception as e:
            print_result("Firestore Client Creation", False, str(e))
            return False
        
        # Test Firestore read access
        try:
            # Try to read from a collection (this tests basic connectivity)
            collection_ref = db.collection('video_tasks')
            docs = list(collection_ref.limit(1).stream())
            print_result("Firestore Read Test", True, f"Can read from video_tasks collection")
        except Exception as e:
            print_result("Firestore Read Test", False, str(e))
            return False
        
        # Test Firestore write access
        try:
            test_doc_id = f"diagnostic-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            test_data = {
                'test': True,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'diagnostic_run': datetime.now().isoformat()
            }
            
            doc_ref = db.collection('diagnostic_tests').document(test_doc_id)
            doc_ref.set(test_data)
            print_result("Firestore Write Test", True, f"Successfully wrote document: {test_doc_id}")
            
            # Clean up test document
            doc_ref.delete()
            
        except Exception as e:
            print_result("Firestore Write Test", False, str(e))
            return False
        
        return True
        
    except ImportError:
        print_result("Firestore Test", False, "firebase_admin not installed")
        return False
    except Exception as e:
        print_result("Firestore Test", False, f"Unexpected error: {e}")
        return False

def test_backend_modules():
    print_header("Backend Modules Test")
    
    # Add current directory to Python path
    sys.path.insert(0, os.getcwd())
    
    try:
        from core.s3_storage import S3Storage
        s3_storage = S3Storage()
        print_result("S3Storage Module", True, f"Bucket: {s3_storage.bucket_name}")
    except Exception as e:
        print_result("S3Storage Module", False, str(e))
        return False
    
    try:
        from core.firestore_db import firestore_db
        is_available = firestore_db._is_available()
        print_result("FirestoreDB Module", is_available, f"Available: {is_available}")
        if not is_available:
            return False
    except Exception as e:
        print_result("FirestoreDB Module", False, str(e))
        return False
    
    # Test actual backend operations
    try:
        test_video_id = f"diagnostic-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Test Firestore task creation
        task_data = firestore_db.create_video_task(
            test_video_id,
            "diagnostic-test.mp4", 
            "diagnostic-user",
            "diagnostic@test.com",
            "diagnostic"
        )
        
        if task_data:
            print_result("Backend Task Creation", True, f"Created task: {test_video_id}")
            
            # Clean up
            try:
                firestore_db.db.collection('video_tasks').document(test_video_id).delete()
            except:
                pass
        else:
            print_result("Backend Task Creation", False, "create_video_task returned None")
            return False
            
    except Exception as e:
        print_result("Backend Task Creation", False, str(e))
        return False
    
    return True

def test_worker_connectivity():
    print_header("Worker Service Connectivity Test")
    
    worker_url = os.getenv('WORKER_SERVICE_URL', 'https://thakii-02.fanusdigital.site/thakii-worker')
    
    try:
        import requests
        
        # Test health endpoint
        try:
            response = requests.get(f"{worker_url}/health", timeout=10)
            if response.status_code == 200:
                print_result("Worker Health Check", True, f"Status: {response.status_code}")
            else:
                print_result("Worker Health Check", False, f"Status: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print_result("Worker Health Check", False, "Connection refused - worker service down")
            return False
        except requests.exceptions.Timeout:
            print_result("Worker Health Check", False, "Timeout - worker service unresponsive")
            return False
        
        # Test process-from-s3 endpoint (should return 400 for missing data)
        try:
            response = requests.post(f"{worker_url}/process-from-s3", json={}, timeout=10)
            if response.status_code == 400:
                print_result("Worker API Endpoint", True, "Endpoint accessible (400 expected for empty payload)")
            else:
                print_result("Worker API Endpoint", False, f"Unexpected status: {response.status_code}")
        except Exception as e:
            print_result("Worker API Endpoint", False, str(e))
            return False
        
        return True
        
    except ImportError:
        print_result("Worker Connectivity Test", False, "requests module not available")
        return False
    except Exception as e:
        print_result("Worker Connectivity Test", False, str(e))
        return False

def main():
    print("🚀 Backend Infrastructure Diagnostic Tool")
    print(f"📅 Run Time: {datetime.now().isoformat()}")
    print(f"🐍 Python: {sys.version}")
    print(f"📂 Working Directory: {os.getcwd()}")
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("File Access", test_file_access),
        ("S3 Connection", test_s3_connection),
        ("Firestore Connection", test_firestore_connection),
        ("Backend Modules", test_backend_modules),
        ("Worker Connectivity", test_worker_connectivity),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print_result(f"{test_name} (CRASHED)", False, f"Exception: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            results.append((test_name, False))
    
    # Summary
    print_header("DIAGNOSTIC SUMMARY")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
        if success:
            passed += 1
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Infrastructure is healthy!")
        print("   The 500 error is likely a different issue.")
    else:
        print("💥 SOME TESTS FAILED - Infrastructure issues detected!")
        print("   Fix the failed tests to resolve the 500 error.")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
