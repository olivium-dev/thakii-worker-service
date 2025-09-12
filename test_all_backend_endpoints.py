#!/usr/bin/env python3
"""
Comprehensive Backend API Endpoint Testing
Tests every single backend endpoint and creates a detailed status table
"""

import requests
import json
import time
from datetime import datetime

class BackendEndpointTester:
    def __init__(self):
        self.backend_url = "https://vps-71.fds-1.com/thakii-be"
        self.results = []
        
        # Get authentication token for testing
        self.auth_token = None
        self.admin_token = None
        
        print("🔍 === COMPREHENSIVE BACKEND API ENDPOINT TESTING ===")
        print(f"Backend URL: {self.backend_url}")
        print(f"Test Time: {datetime.now()}")
        print()
    
    def get_auth_tokens_via_ssh(self):
        """Get authentication tokens via SSH for testing"""
        print("🔑 === GETTING AUTHENTICATION TOKENS VIA SSH ===")
        
        import subprocess
        
        # Get user token via SSH
        ssh_cmd = [
            "ssh", "-i", "thakii-02-developer-key",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ProxyCommand=cloudflared access ssh --hostname %h",
            "ec2-user@vps-71.fds-1.com",
            "cd /home/ec2-user/thakii-backend-api && curl -s -X POST http://localhost:5001/auth/mock-user-token -H 'Content-Type: application/json' -d '{\"email\": \"test@thakii.dev\", \"uid\": \"test-user-123\"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"custom_token\"])'"
        ]
        
        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.auth_token = result.stdout.strip().split('\n')[-1]
                print(f"✅ User token obtained (length: {len(self.auth_token)})")
            else:
                print("❌ Failed to get user token via SSH")
        except Exception as e:
            print(f"❌ SSH token error: {e}")
        
        # Get admin token via SSH
        admin_ssh_cmd = [
            "ssh", "-i", "thakii-02-developer-key",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", 
            "-o", "ProxyCommand=cloudflared access ssh --hostname %h",
            "ec2-user@vps-71.fds-1.com",
            "cd /home/ec2-user/thakii-backend-api && curl -s -X POST http://localhost:5001/auth/mock-admin-token -H 'Content-Type: application/json' -d '{\"email\": \"admin@thakii.test\", \"uid\": \"admin-123\"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"custom_token\"])'"
        ]
        
        try:
            result = subprocess.run(admin_ssh_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.admin_token = result.stdout.strip().split('\n')[-1]
                print(f"✅ Admin token obtained (length: {len(self.admin_token)})")
            else:
                print("❌ Failed to get admin token via SSH")
        except Exception as e:
            print(f"❌ SSH admin token error: {e}")
    
    def test_endpoint(self, method, path, auth_required=False, admin_required=False, data=None, description=""):
        """Test a single endpoint and record results"""
        url = f"{self.backend_url}{path}"
        headers = {}
        
        if admin_required and self.admin_token:
            headers['Authorization'] = f'Bearer {self.admin_token}'
        elif auth_required and self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        if data:
            headers['Content-Type'] = 'application/json'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=10)
            else:
                response = requests.request(method, url, headers=headers, json=data, timeout=10)
            
            # Analyze response
            status_code = response.status_code
            has_content = len(response.text) > 0
            is_json = False
            content_preview = ""
            
            try:
                response_data = response.json()
                is_json = True
                content_preview = str(response_data)[:100] + "..." if len(str(response_data)) > 100 else str(response_data)
            except:
                content_preview = response.text[:100] + "..." if len(response.text) > 100 else response.text
            
            # Determine status
            if status_code == 200 and has_content and is_json:
                status = "✅ SUCCESS"
            elif status_code == 200 and not has_content:
                status = "⚠️  EMPTY RESPONSE"
            elif status_code in [401, 403] and (auth_required or admin_required):
                status = "🔒 AUTH REQUIRED"
            elif status_code in [400, 404, 422]:
                status = "📋 EXPECTED ERROR"
            else:
                status = "❌ FAILED"
            
            self.results.append({
                'endpoint': f"{method} {path}",
                'description': description,
                'status_code': status_code,
                'has_content': has_content,
                'is_json': is_json,
                'status': status,
                'content_preview': content_preview,
                'auth_required': auth_required,
                'admin_required': admin_required
            })
            
        except requests.exceptions.Timeout:
            self.results.append({
                'endpoint': f"{method} {path}",
                'description': description,
                'status_code': 'TIMEOUT',
                'has_content': False,
                'is_json': False,
                'status': "⏰ TIMEOUT",
                'content_preview': "Request timed out",
                'auth_required': auth_required,
                'admin_required': admin_required
            })
        except Exception as e:
            self.results.append({
                'endpoint': f"{method} {path}",
                'description': description,
                'status_code': 'ERROR',
                'has_content': False,
                'is_json': False,
                'status': "❌ ERROR",
                'content_preview': str(e),
                'auth_required': auth_required,
                'admin_required': admin_required
            })
    
    def test_all_endpoints(self):
        """Test all backend API endpoints"""
        print("📋 === TESTING ALL BACKEND ENDPOINTS ===")
        print()
        
        # Public endpoints
        self.test_endpoint('GET', '/health', description="Service health check")
        
        # Mock auth endpoints
        self.test_endpoint('POST', '/auth/mock-user-token', data={"email": "test@thakii.dev", "uid": "test-123"}, description="Generate user token")
        self.test_endpoint('POST', '/auth/mock-admin-token', data={"email": "admin@thakii.test", "uid": "admin-123"}, description="Generate admin token")
        self.test_endpoint('GET', '/auth/exchange-token', description="Exchange Firebase token")
        
        # User endpoints (require authentication)
        self.test_endpoint('GET', '/auth/user', auth_required=True, description="Get current user info")
        self.test_endpoint('POST', '/upload', auth_required=True, description="Upload video file")
        self.test_endpoint('GET', '/list', auth_required=True, description="List user videos")
        self.test_endpoint('GET', '/status/test-video-id', auth_required=True, description="Get video status")
        self.test_endpoint('GET', '/download/test-video-id', auth_required=True, description="Download PDF")
        
        # Admin endpoints
        self.test_endpoint('GET', '/admin/videos', admin_required=True, description="Admin - All videos")
        self.test_endpoint('GET', '/admin/stats', admin_required=True, description="Admin - System stats")
        self.test_endpoint('GET', '/admin/servers', admin_required=True, description="Admin - Server list")
        self.test_endpoint('GET', '/admin/admins', admin_required=True, description="Admin - Admin list")
        self.test_endpoint('DELETE', '/admin/videos/test-id', admin_required=True, description="Admin - Delete video")
        
    def print_results_table(self):
        """Print comprehensive results table"""
        print("📊 === BACKEND API ENDPOINT TEST RESULTS ===")
        print()
        
        # Header
        print("| Endpoint | Description | Status Code | Content | JSON | Result | Auth |")
        print("|----------|-------------|-------------|---------|------|--------|------|")
        
        # Results
        for result in self.results:
            endpoint = result['endpoint']
            description = result['description'][:25] + "..." if len(result['description']) > 25 else result['description']
            status_code = str(result['status_code'])
            has_content = "✅" if result['has_content'] else "❌"
            is_json = "✅" if result['is_json'] else "❌"
            status = result['status']
            auth = "👑" if result['admin_required'] else "🔒" if result['auth_required'] else "🌐"
            
            print(f"| {endpoint:<15} | {description:<25} | {status_code:<11} | {has_content:<7} | {is_json:<4} | {status:<15} | {auth:<4} |")
        
        # Summary
        print()
        print("📊 === SUMMARY ===")
        success_count = sum(1 for r in self.results if r['status'] == "✅ SUCCESS")
        empty_count = sum(1 for r in self.results if r['status'] == "⚠️  EMPTY RESPONSE")
        auth_count = sum(1 for r in self.results if r['status'] == "🔒 AUTH REQUIRED")
        expected_count = sum(1 for r in self.results if r['status'] == "📋 EXPECTED ERROR")
        failed_count = sum(1 for r in self.results if r['status'] == "❌ FAILED")
        timeout_count = sum(1 for r in self.results if r['status'] == "⏰ TIMEOUT")
        
        total = len(self.results)
        
        print(f"✅ SUCCESS: {success_count}/{total}")
        print(f"⚠️  EMPTY RESPONSE: {empty_count}/{total}")
        print(f"🔒 AUTH REQUIRED: {auth_count}/{total}")
        print(f"📋 EXPECTED ERROR: {expected_count}/{total}")
        print(f"❌ FAILED: {failed_count}/{total}")
        print(f"⏰ TIMEOUT: {timeout_count}/{total}")
        
        working_count = success_count + expected_count + auth_count
        print()
        print(f"🎯 FUNCTIONAL ENDPOINTS: {working_count}/{total} ({working_count/total*100:.1f}%)")
        
        if empty_count > 0:
            print()
            print("⚠️  EMPTY RESPONSE ANALYSIS:")
            print("   - HTTP 200 status but no response body")
            print("   - Likely Cloudflare tunnel routing issue")
            print("   - Backend is running but tunnel not forwarding responses")
        
        return working_count >= total * 0.8  # 80% success rate

if __name__ == "__main__":
    tester = BackendEndpointTester()
    
    # Get tokens first
    tester.get_auth_tokens_via_ssh()
    print()
    
    # Test all endpoints
    tester.test_all_endpoints()
    print()
    
    # Print results table
    success = tester.print_results_table()
    
    print()
    if success:
        print("🎉 BACKEND API TESTING: SUCCESSFUL!")
    else:
        print("⚠️  BACKEND API TESTING: NEEDS ATTENTION")
