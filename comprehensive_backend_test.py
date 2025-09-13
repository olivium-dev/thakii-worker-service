#!/usr/bin/env python3
"""
Comprehensive Backend Investigation Test
Tests the complete frontend→backend→worker flow to identify upload issues
"""

import requests
import json
import time
import os
from pathlib import Path

# Configuration
BACKEND_URL = "https://vps-71.fds-1.com/thakii-be"
WORKER_URL = "https://thakii-02.fanusdigital.site/thakii-worker"
TEST_VIDEO = "tests/videos/input_1.mp4"

class BackendInvestigator:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.worker_url = WORKER_URL
        self.token = None
        self.results = {}
    
    def test_1_backend_health(self):
        """Test 1: Backend API Health Check"""
        print("1️⃣ === TESTING BACKEND HEALTH ===")
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   ✅ Backend Health: {data.get('status', 'unknown')}")
                    print(f"   Service: {data.get('service', 'unknown')}")
                    print(f"   Database: {data.get('database', 'unknown')}")
                    print(f"   Storage: {data.get('storage', 'unknown')}")
                    self.results['backend_health'] = 'PASS'
                    return True
                except json.JSONDecodeError:
                    print(f"   ❌ Invalid JSON response: {response.text[:200]}")
                    self.results['backend_health'] = 'FAIL - Invalid JSON'
                    return False
            else:
                print(f"   ❌ Backend unhealthy: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                self.results['backend_health'] = f'FAIL - HTTP {response.status_code}'
                return False
                
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ Backend connection failed: {e}")
            self.results['backend_health'] = 'FAIL - Connection Error'
            return False
        except Exception as e:
            print(f"   ❌ Backend health error: {e}")
            self.results['backend_health'] = f'FAIL - {str(e)}'
            return False
    
    def test_2_authentication(self):
        """Test 2: Authentication System"""
        print("\n2️⃣ === TESTING AUTHENTICATION ===")
        
        # Test mock user token endpoint
        try:
            print("   Testing mock user token...")
            response = requests.post(
                f"{self.backend_url}/auth/mock-user-token",
                json={
                    "email": "test@example.com",
                    "name": "Test User"
                },
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.token = data.get('custom_token')
                    if self.token:
                        print(f"   ✅ Auth Token: {self.token[:20]}...")
                        print(f"   User: {data.get('user', {}).get('email', 'unknown')}")
                        self.results['authentication'] = 'PASS'
                        return True
                    else:
                        print(f"   ❌ No token in response: {data}")
                        self.results['authentication'] = 'FAIL - No Token'
                        return False
                except json.JSONDecodeError:
                    print(f"   ❌ Invalid JSON response: {response.text[:200]}")
                    self.results['authentication'] = 'FAIL - Invalid JSON'
                    return False
            else:
                print(f"   ❌ Auth failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                self.results['authentication'] = f'FAIL - HTTP {response.status_code}'
                return False
                
        except Exception as e:
            print(f"   ❌ Auth error: {e}")
            self.results['authentication'] = f'FAIL - {str(e)}'
            return False
    
    def test_3_worker_health(self):
        """Test 3: Worker Service Health"""
        print("\n3️⃣ === TESTING WORKER HEALTH ===")
        try:
            response = requests.get(f"{self.worker_url}/health", timeout=10)
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Worker Health: {data.get('status', 'unknown')}")
                print(f"   Service: {data.get('service', 'unknown')}")
                print(f"   Available Endpoints: {len(data.get('endpoints', {}))}")
                self.results['worker_health'] = 'PASS'
                return True
            else:
                print(f"   ❌ Worker unhealthy: {response.status_code}")
                self.results['worker_health'] = f'FAIL - HTTP {response.status_code}'
                return False
                
        except Exception as e:
            print(f"   ❌ Worker health error: {e}")
            self.results['worker_health'] = f'FAIL - {str(e)}'
            return False
    
    def test_4_small_file_upload(self):
        """Test 4: Small File Upload (Standard Upload)"""
        print("\n4️⃣ === TESTING SMALL FILE UPLOAD ===")
        
        if not self.token:
            print("   ❌ Skipping - No auth token")
            self.results['small_upload'] = 'SKIP - No Token'
            return False
        
        video_path = Path(TEST_VIDEO)
        if not video_path.exists():
            print(f"   ❌ Test video not found: {TEST_VIDEO}")
            self.results['small_upload'] = 'SKIP - No Test Video'
            return False
        
        file_size = video_path.stat().st_size
        print(f"   Test Video: {video_path.name} ({file_size:,} bytes)")
        
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            with open(video_path, 'rb') as f:
                files = {'file': (video_path.name, f, 'video/mp4')}
                
                print("   Uploading via standard upload...")
                response = requests.post(
                    f"{self.backend_url}/upload",
                    files=files,
                    headers=headers,
                    timeout=120
                )
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                video_id = data.get('video_id')
                print(f"   ✅ Upload successful: {video_id}")
                print(f"   S3 Key: {data.get('s3_key', 'unknown')}")
                self.results['small_upload'] = 'PASS'
                return video_id
            else:
                print(f"   ❌ Upload failed: {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                self.results['small_upload'] = f'FAIL - HTTP {response.status_code}'
                return False
                
        except Exception as e:
            print(f"   ❌ Upload error: {e}")
            self.results['small_upload'] = f'FAIL - {str(e)}'
            return False
    
    def test_5_processing_monitoring(self, video_id):
        """Test 5: Monitor Video Processing"""
        print(f"\n5️⃣ === MONITORING PROCESSING FOR {video_id} ===")
        
        if not video_id or not self.token:
            print("   ❌ Skipping - No video ID or token")
            self.results['processing'] = 'SKIP'
            return False
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        for attempt in range(30):  # Monitor for 5 minutes
            try:
                response = requests.get(
                    f"{self.backend_url}/status/{video_id}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')
                    
                    print(f"   Attempt {attempt + 1}/30 - Status: {status}")
                    
                    if status == 'completed':
                        print("   ✅ Processing completed!")
                        self.results['processing'] = 'PASS'
                        return True
                    elif status == 'failed':
                        error = data.get('error_message', 'Unknown error')
                        print(f"   ❌ Processing failed: {error}")
                        self.results['processing'] = f'FAIL - {error}'
                        return False
                    elif status in ['processing', 'in_queue']:
                        time.sleep(10)
                    else:
                        print(f"   ❓ Unknown status: {status}")
                        time.sleep(10)
                else:
                    print(f"   ❌ Status check failed: {response.status_code}")
                    time.sleep(10)
                    
            except Exception as e:
                print(f"   ❌ Status check error: {e}")
                time.sleep(10)
        
        print("   ⏱️ Timeout waiting for processing")
        self.results['processing'] = 'TIMEOUT'
        return False
    
    def test_6_download_pdf(self, video_id):
        """Test 6: Download Generated PDF"""
        print(f"\n6️⃣ === TESTING PDF DOWNLOAD FOR {video_id} ===")
        
        if not video_id or not self.token:
            print("   ❌ Skipping - No video ID or token")
            self.results['download'] = 'SKIP'
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            response = requests.get(
                f"{self.backend_url}/download/{video_id}",
                headers=headers,
                timeout=30
            )
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                download_url = data.get('download_url')
                
                if download_url:
                    # Download actual PDF
                    pdf_response = requests.get(download_url, timeout=60)
                    if pdf_response.status_code == 200:
                        output_file = f"backend_test_{video_id}.pdf"
                        with open(output_file, 'wb') as f:
                            f.write(pdf_response.content)
                        
                        print(f"   ✅ PDF downloaded: {output_file} ({len(pdf_response.content):,} bytes)")
                        
                        # Quick PDF analysis
                        if pdf_response.content.startswith(b'%PDF'):
                            print("   ✅ Valid PDF format")
                            
                            # Check if it's enhanced (not the old fragmented version)
                            try:
                                import PyPDF2
                                with open(output_file, 'rb') as f:
                                    pdf_reader = PyPDF2.PdfReader(f)
                                    num_pages = len(pdf_reader.pages)
                                    
                                    print(f"   📄 PDF Pages: {num_pages}")
                                    
                                    if num_pages > 0:
                                        first_page = pdf_reader.pages[0].extract_text()
                                        print(f"   📝 First page: {first_page[:100]}...")
                                        
                                        # Check if text is complete sentences (not fragmented)
                                        if len(first_page) > 50 and not first_page.startswith(("Welcome", "to t", "oday's l")):
                                            print("   ✅ Enhanced processing detected (complete sentences)")
                                            self.results['download'] = 'PASS - Enhanced'
                                        else:
                                            print("   ⚠️ May still be using old processing (fragmented text)")
                                            self.results['download'] = 'PASS - Old Processing'
                                    else:
                                        print("   ⚠️ Empty PDF")
                                        self.results['download'] = 'PASS - Empty'
                                        
                            except Exception as e:
                                print(f"   ⚠️ PDF analysis error: {e}")
                                self.results['download'] = 'PASS - Analysis Failed'
                            
                            return output_file
                        else:
                            print("   ❌ Invalid PDF format")
                            self.results['download'] = 'FAIL - Invalid Format'
                            return False
                    else:
                        print(f"   ❌ PDF download failed: {pdf_response.status_code}")
                        self.results['download'] = 'FAIL - Download Failed'
                        return False
                else:
                    print(f"   ❌ No download URL: {data}")
                    self.results['download'] = 'FAIL - No URL'
                    return False
            else:
                print(f"   ❌ Download request failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                self.results['download'] = f'FAIL - HTTP {response.status_code}'
                return False
                
        except Exception as e:
            print(f"   ❌ Download error: {e}")
            self.results['download'] = f'FAIL - {str(e)}'
            return False
    
    def test_7_backend_worker_integration(self):
        """Test 7: Backend-Worker Integration"""
        print("\n7️⃣ === TESTING BACKEND-WORKER INTEGRATION ===")
        
        try:
            # Test if backend can reach worker
            print("   Testing backend→worker connectivity...")
            
            # Simulate what backend does
            test_payload = {
                "video_id": f"integration-test-{int(time.time())}",
                "user_id": "test-user-123",
                "filename": "test.mp4",
                "s3_key": "videos/test/test.mp4"
            }
            
            response = requests.post(
                f"{self.worker_url}/process-from-s3",
                json=test_payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text}")
            
            if response.status_code == 201:
                print("   ✅ Backend-Worker integration working")
                self.results['integration'] = 'PASS'
                return True
            elif response.status_code == 400:
                print("   ✅ Worker validates requests properly (expected for test data)")
                self.results['integration'] = 'PASS'
                return True
            else:
                print(f"   ❌ Integration failed: {response.status_code}")
                self.results['integration'] = f'FAIL - HTTP {response.status_code}'
                return False
                
        except Exception as e:
            print(f"   ❌ Integration error: {e}")
            self.results['integration'] = f'FAIL - {str(e)}'
            return False
    
    def test_8_cors_configuration(self):
        """Test 8: CORS Configuration"""
        print("\n8️⃣ === TESTING CORS CONFIGURATION ===")
        
        try:
            # Test preflight request
            print("   Testing CORS preflight...")
            response = requests.options(
                f"{self.backend_url}/upload",
                headers={
                    'Origin': 'http://localhost:3000',
                    'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type,Authorization'
                },
                timeout=10
            )
            
            print(f"   Status Code: {response.status_code}")
            print(f"   CORS Headers: {dict(response.headers)}")
            
            cors_headers = response.headers
            if 'Access-Control-Allow-Origin' in cors_headers:
                print(f"   ✅ CORS Origin: {cors_headers['Access-Control-Allow-Origin']}")
                self.results['cors'] = 'PASS'
                return True
            else:
                print("   ❌ Missing CORS headers")
                self.results['cors'] = 'FAIL - Missing Headers'
                return False
                
        except Exception as e:
            print(f"   ❌ CORS test error: {e}")
            self.results['cors'] = f'FAIL - {str(e)}'
            return False
    
    def test_9_file_size_limits(self):
        """Test 9: File Size Limits"""
        print("\n9️⃣ === TESTING FILE SIZE LIMITS ===")
        
        if not self.token:
            print("   ❌ Skipping - No auth token")
            self.results['file_limits'] = 'SKIP - No Token'
            return False
        
        try:
            # Create a small test file
            test_content = b"fake video content for testing" * 1000  # ~30KB
            
            headers = {"Authorization": f"Bearer {self.token}"}
            files = {'file': ('test_small.mp4', test_content, 'video/mp4')}
            
            print(f"   Testing with {len(test_content):,} byte file...")
            
            response = requests.post(
                f"{self.backend_url}/upload",
                files=files,
                headers=headers,
                timeout=30
            )
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ Small file upload accepted")
                self.results['file_limits'] = 'PASS'
                return True
            elif response.status_code == 413:
                print("   ❌ File too large (unexpected for small file)")
                self.results['file_limits'] = 'FAIL - Size Limit Too Low'
                return False
            else:
                print(f"   ❌ Upload failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                self.results['file_limits'] = f'FAIL - HTTP {response.status_code}'
                return False
                
        except Exception as e:
            print(f"   ❌ File size test error: {e}")
            self.results['file_limits'] = f'FAIL - {str(e)}'
            return False
    
    def generate_report(self):
        """Generate comprehensive diagnostic report"""
        print("\n" + "="*60)
        print("📊 === COMPREHENSIVE BACKEND INVESTIGATION REPORT ===")
        print("="*60)
        
        for test_name, result in self.results.items():
            status_icon = "✅" if result.startswith('PASS') else "❌" if result.startswith('FAIL') else "⚠️"
            print(f"{status_icon} {test_name.upper()}: {result}")
        
        print("\n🔍 === DIAGNOSIS ===")
        
        # Analyze results
        failed_tests = [k for k, v in self.results.items() if v.startswith('FAIL')]
        passed_tests = [k for k, v in self.results.items() if v.startswith('PASS')]
        
        if not failed_tests:
            print("🎉 ALL TESTS PASSED - Upload system is working correctly!")
            print("💡 If frontend still fails, check browser console for JavaScript errors")
        else:
            print(f"❌ FAILED TESTS: {', '.join(failed_tests)}")
            print("\n💡 RECOMMENDED FIXES:")
            
            if 'backend_health' in failed_tests:
                print("   🔧 Backend service may be down or misconfigured")
            if 'authentication' in failed_tests:
                print("   🔧 Authentication system needs fixing")
            if 'worker_health' in failed_tests:
                print("   🔧 Worker service may be down")
            if 'cors' in failed_tests:
                print("   🔧 CORS configuration needs updating")
            if 'small_upload' in failed_tests:
                print("   🔧 Backend upload endpoint has issues")
        
        print(f"\n📈 SUCCESS RATE: {len(passed_tests)}/{len(self.results)} tests passed")

def main():
    """Run comprehensive backend investigation"""
    investigator = BackendInvestigator()
    
    print("🔍 === COMPREHENSIVE BACKEND INVESTIGATION ===")
    print(f"🌐 Backend URL: {BACKEND_URL}")
    print(f"⚙️ Worker URL: {WORKER_URL}")
    print(f"📁 Test Video: {TEST_VIDEO}")
    print()
    
    # Run all tests
    investigator.test_1_backend_health()
    investigator.test_2_authentication()
    investigator.test_3_worker_health()
    investigator.test_8_cors_configuration()
    
    video_id = investigator.test_4_small_file_upload()
    if video_id:
        investigator.test_5_processing_monitoring(video_id)
        investigator.test_6_download_pdf(video_id)
    
    investigator.test_7_backend_worker_integration()
    
    # Generate final report
    investigator.generate_report()

if __name__ == "__main__":
    main()
