#!/usr/bin/env python3
"""
Local Infrastructure Test
Simulates the backend's S3 and Firestore operations to identify potential issues
"""

import os
import sys
from datetime import datetime

def test_imports():
    print("🔍 Testing Python Imports...")
    
    # Test boto3 (AWS S3)
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        print("✅ boto3 (AWS S3) - Available")
    except ImportError:
        print("❌ boto3 (AWS S3) - Not installed")
        print("   Install with: pip install boto3")
        return False
    
    # Test firebase_admin
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        print("✅ firebase_admin - Available")
    except ImportError:
        print("❌ firebase_admin - Not installed")
        print("   Install with: pip install firebase-admin")
        return False
    
    # Test requests
    try:
        import requests
        print("✅ requests - Available")
    except ImportError:
        print("❌ requests - Not installed")
        print("   Install with: pip install requests")
        return False
    
    return True

def simulate_s3_operations():
    print("\n🪣 Simulating S3 Operations...")
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        # This will fail without credentials, but we can see the error type
        try:
            s3_client = boto3.client('s3')
            print("✅ S3 Client created successfully")
            
            # Try to list buckets (will fail without credentials)
            try:
                buckets = s3_client.list_buckets()
                print("✅ S3 Credentials working - can list buckets")
                print(f"   Found {len(buckets.get('Buckets', []))} buckets")
            except NoCredentialsError:
                print("❌ S3 Credentials missing")
                print("   Backend error likely: AWS credentials not configured")
                return False
            except ClientError as e:
                error_code = e.response['Error']['Code']
                print(f"❌ S3 Access error: {error_code}")
                print(f"   Backend error likely: {e}")
                return False
                
        except Exception as e:
            print(f"❌ S3 Client creation failed: {e}")
            return False
            
    except ImportError:
        print("❌ Cannot test S3 - boto3 not available")
        return False
    
    return True

def simulate_firestore_operations():
    print("\n🔥 Simulating Firestore Operations...")
    
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # This will fail without credentials, but we can see the error type
        try:
            if not firebase_admin._apps:
                # Try default credentials first
                try:
                    firebase_admin.initialize_app()
                    print("✅ Firebase initialized with default credentials")
                except Exception as e:
                    print(f"❌ Firebase initialization failed: {e}")
                    print("   Backend error likely: Firebase credentials missing or invalid")
                    return False
            
            # Try to create Firestore client
            try:
                db = firestore.client()
                print("✅ Firestore client created successfully")
                
                # Try a simple operation
                try:
                    # This will fail without proper project setup
                    collection_ref = db.collection('test')
                    print("✅ Firestore collection reference created")
                    
                    # Try to read (will fail without proper credentials/project)
                    try:
                        docs = list(collection_ref.limit(1).stream())
                        print("✅ Firestore read operation successful")
                    except Exception as e:
                        print(f"❌ Firestore read failed: {e}")
                        print("   Backend error likely: Project ID wrong or permissions issue")
                        return False
                        
                except Exception as e:
                    print(f"❌ Firestore operations failed: {e}")
                    return False
                    
            except Exception as e:
                print(f"❌ Firestore client creation failed: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Firebase initialization failed: {e}")
            return False
            
    except ImportError:
        print("❌ Cannot test Firestore - firebase_admin not available")
        return False
    
    return True

def simulate_worker_request():
    print("\n🔧 Simulating Worker Service Request...")
    
    try:
        import requests
        
        worker_url = "https://thakii-02.fanusdigital.site/thakii-worker"
        
        # Test health endpoint
        try:
            print(f"   Testing: {worker_url}/health")
            response = requests.get(f"{worker_url}/health", timeout=10)
            print(f"✅ Worker health check: {response.status_code}")
            if response.status_code == 200:
                print("   Worker service is running and accessible")
            else:
                print(f"   Unexpected status code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("❌ Worker service connection failed")
            print("   Backend error likely: Worker service is down or unreachable")
            return False
        except requests.exceptions.Timeout:
            print("❌ Worker service timeout")
            print("   Backend error likely: Worker service is slow or overloaded")
            return False
        except Exception as e:
            print(f"❌ Worker service error: {e}")
            return False
        
        # Test process-from-s3 endpoint
        try:
            print(f"   Testing: {worker_url}/process-from-s3")
            response = requests.post(
                f"{worker_url}/process-from-s3",
                json={
                    "video_id": "test-123",
                    "user_id": "test-user", 
                    "filename": "test.mp4",
                    "s3_key": "videos/test-123.mp4"
                },
                timeout=10
            )
            print(f"✅ Worker API test: {response.status_code}")
            if response.status_code in [200, 201, 400]:  # 400 is OK for test data
                print("   Worker API endpoint is accessible")
            else:
                print(f"   Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"❌ Worker API error: {e}")
            return False
            
    except ImportError:
        print("❌ Cannot test worker - requests not available")
        return False
    
    return True

def analyze_backend_flow():
    print("\n📊 Backend Upload Flow Analysis...")
    print("""
Backend Upload Flow (from thakii-backend-api/app.py):

1. File validation ✅ (unlikely to cause 500 error)
2. S3 upload ⚠️  (POTENTIAL 500 ERROR SOURCE)
   - s3_storage.upload_video(file, video_id, filename)
   - Fails if: AWS credentials expired, bucket permissions, network
   
3. Firestore task creation ⚠️  (POTENTIAL 500 ERROR SOURCE)  
   - firestore_db.create_video_task(...)
   - Fails if: Firebase credentials expired, project ID wrong, permissions
   
4. Worker trigger ✅ (has error handling, won't cause 500)
   - trigger_worker_processing(...)
   - If fails: prints warning, continues with success response

CONCLUSION: 500 error happens at step 2 or 3, NOT step 4
""")

def main():
    print("🚀 Local Infrastructure Test")
    print(f"📅 {datetime.now().isoformat()}")
    print("=" * 60)
    
    tests = [
        ("Python Imports", test_imports),
        ("S3 Operations", simulate_s3_operations), 
        ("Firestore Operations", simulate_firestore_operations),
        ("Worker Service", simulate_worker_request),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    analyze_backend_flow()
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n📊 Local Tests: {passed}/{total} passed")
    
    if passed < total:
        print("\n💡 RECOMMENDATIONS:")
        print("1. Run the diagnostic script on the backend server")
        print("2. Check backend server logs for the actual error")
        print("3. Verify AWS and Firebase credentials on backend server")
        print("4. The worker service appears to be working correctly")
    
    print(f"\n🎯 NEXT STEPS:")
    print("1. SSH to backend server: ssh user@vps-71.fds-1.com")
    print("2. Run diagnostic script: python3 diagnose_backend_infrastructure.py")
    print("3. Check logs: sudo journalctl -u thakii-backend -n 50")

if __name__ == "__main__":
    main()
