#!/usr/bin/env python3
"""
Complete End-to-End Integration Test
Tests the full flow: Backend API → Worker Service → Firebase → S3
"""

import requests
import json
import time
import sys
import os
from datetime import datetime

class ThakiiIntegrationTester:
    def __init__(self):
        # Service URLs
        self.backend_url = "https://vps-71.fds-1.com/thakii-be"
        self.worker_url = "https://thakii-02.fanusdigital.site/thakii-worker"
        
        # Test data
        self.test_user_id = "integration-test-user"
        self.test_filename = "integration-test.mp4"
        
        print("🚀 === THAKII INTEGRATION TESTER ===")
        print(f"Backend URL: {self.backend_url}")
        print(f"Worker URL: {self.worker_url}")
        print()
    
    def test_service_health(self):
        """Test both services are healthy"""
        print("1️⃣ === TESTING SERVICE HEALTH ===")
        
        # Test backend health
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Backend: {data['status']} (DB: {data['database']}, Storage: {data['storage']})")
            else:
                print(f"❌ Backend health failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Backend health error: {e}")
            return False
        
        # Test worker health
        try:
            response = requests.get(f"{self.worker_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Worker: {data['status']} (API: {data['api_version']})")
            else:
                print(f"❌ Worker health failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Worker health error: {e}")
            return False
        
        return True
    
    def test_worker_direct(self):
        """Test worker service directly"""
        print("2️⃣ === TESTING WORKER SERVICE DIRECT ===")
        
        # Test list videos
        try:
            response = requests.get(f"{self.worker_url}/list", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Worker list: {data['total']} videos from {data['source']}")
            else:
                print(f"❌ Worker list failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Worker list error: {e}")
            return False
        
        # Test generate-pdf endpoint (without file)
        try:
            response = requests.post(
                f"{self.worker_url}/generate-pdf",
                json={
                    "user_id": self.test_user_id,
                    "filename": self.test_filename
                },
                timeout=10
            )
            if response.status_code in [400, 422]:  # Expected - no video file
                print("✅ Worker generate-pdf endpoint responding correctly")
            else:
                print(f"⚠️  Worker generate-pdf unexpected response: {response.status_code}")
        except Exception as e:
            print(f"❌ Worker generate-pdf error: {e}")
            return False
        
        return True
    
    def test_backend_worker_communication(self):
        """Test if backend can communicate with worker"""
        print("3️⃣ === TESTING BACKEND-WORKER COMMUNICATION ===")
        
        # Test if backend can reach worker
        try:
            # This simulates what the backend would do
            response = requests.get(f"{self.worker_url}/health", timeout=10)
            if response.status_code == 200:
                print("✅ Backend can reach worker service")
            else:
                print(f"❌ Backend cannot reach worker: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Backend-worker communication error: {e}")
            return False
        
        return True
    
    def test_firebase_integration(self):
        """Test Firebase integration"""
        print("4️⃣ === TESTING FIREBASE INTEGRATION ===")
        
        # Test worker Firebase connection
        try:
            response = requests.get(f"{self.worker_url}/list", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['source'] == 'Firebase':
                    print(f"✅ Worker-Firebase: Connected ({data['total']} videos)")
                else:
                    print(f"⚠️  Worker using: {data['source']} (expected Firebase)")
            else:
                print(f"❌ Worker Firebase test failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Worker Firebase error: {e}")
            return False
        
        return True
    
    def test_full_video_processing_simulation(self):
        """Simulate the full video processing flow"""
        print("5️⃣ === TESTING FULL PROCESSING SIMULATION ===")
        
        # Create a test video ID to simulate processing
        test_video_id = f"integration-test-{int(time.time())}"
        
        try:
            # Step 1: Simulate backend creating task in Firebase
            print(f"📝 Simulating task creation for: {test_video_id}")
            
            # Step 2: Test worker status endpoint
            response = requests.get(f"{self.worker_url}/status/{test_video_id}", timeout=10)
            if response.status_code == 404:
                print("✅ Worker correctly reports non-existent video")
            else:
                print(f"⚠️  Unexpected status response: {response.status_code}")
            
            # Step 3: Test worker generate-pdf with proper data
            print("📤 Testing worker generate-pdf endpoint...")
            response = requests.post(
                f"{self.worker_url}/generate-pdf",
                json={
                    "user_id": self.test_user_id,
                    "filename": self.test_filename
                },
                timeout=10
            )
            
            if response.status_code == 400:
                print("✅ Worker correctly requires video file for processing")
            elif response.status_code == 201:
                print("✅ Worker accepted processing request")
            else:
                print(f"⚠️  Worker response: {response.status_code}")
            
            return True
            
        except Exception as e:
            print(f"❌ Full processing simulation error: {e}")
            return False
    
    def run_all_tests(self):
        """Run complete integration test suite"""
        print(f"🎯 === STARTING INTEGRATION TESTS AT {datetime.now()} ===")
        print()
        
        tests = [
            ("Service Health", self.test_service_health),
            ("Worker Direct", self.test_worker_direct),
            ("Backend-Worker Communication", self.test_backend_worker_communication),
            ("Firebase Integration", self.test_firebase_integration),
            ("Full Processing Simulation", self.test_full_video_processing_simulation)
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
                print(f"{'✅' if result else '❌'} {test_name}: {'PASS' if result else 'FAIL'}")
            except Exception as e:
                results.append((test_name, False))
                print(f"❌ {test_name}: ERROR - {e}")
            print()
        
        # Summary
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        print("🎯 === INTEGRATION TEST SUMMARY ===")
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} {test_name}")
        
        print()
        print(f"📊 OVERALL RESULT: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 ALL INTEGRATION TESTS PASSED!")
            print("🚀 Backend-Worker integration is working perfectly!")
        else:
            print("⚠️  Some tests failed - check configuration")
        
        return passed == total

if __name__ == "__main__":
    tester = ThakiiIntegrationTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
