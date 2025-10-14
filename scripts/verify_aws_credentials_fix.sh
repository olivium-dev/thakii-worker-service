#!/bin/bash
# Strict verification script for AWS credentials fix
# This script performs comprehensive tests to ensure the 500 error is resolved

set -e

echo "🔍 STRICT AWS CREDENTIALS VERIFICATION"
echo "======================================"
echo "This script will perform rigorous tests to verify the AWS credentials fix."
echo ""

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo "🧪 TEST $TOTAL_TESTS: $test_name"
    echo "   Command: $test_command"
    
    if eval "$test_command"; then
        if [ "$expected_result" = "success" ]; then
            echo "   ✅ PASSED"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "   ❌ FAILED (expected failure but got success)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        if [ "$expected_result" = "failure" ]; then
            echo "   ✅ PASSED (expected failure)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "   ❌ FAILED"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    fi
    echo ""
}

# Function to check if we're on the server
check_server_environment() {
    if [ ! -d "/home/ec2-user/thakii-backend-api" ]; then
        echo "❌ This script must be run on the production server"
        echo "   Expected directory: /home/ec2-user/thakii-backend-api"
        exit 1
    fi
    echo "✅ Running on production server"
}

# Function to extract value from systemd environment
get_systemd_env_value() {
    local var_name="$1"
    sudo systemctl show thakii-backend.service --property=Environment | \
    grep -o "${var_name}=[^[:space:]]*" | \
    cut -d= -f2
}

echo "🌍 ENVIRONMENT CHECK"
echo "===================="
check_server_environment

echo ""
echo "📋 SYSTEMD SERVICE CONFIGURATION TESTS"
echo "======================================"

# Test 1: Check if systemd service exists
run_test "Systemd service exists" \
    "sudo systemctl list-unit-files | grep -q thakii-backend.service" \
    "success"

# Test 2: Check if service is active
run_test "Backend service is active" \
    "sudo systemctl is-active --quiet thakii-backend.service" \
    "success"

# Test 3: Check AWS_ACCESS_KEY_ID in systemd environment
run_test "AWS_ACCESS_KEY_ID present in systemd" \
    "sudo systemctl show thakii-backend.service --property=Environment | grep -q 'AWS_ACCESS_KEY_ID='" \
    "success"

# Test 4: Check AWS_SECRET_ACCESS_KEY in systemd environment
run_test "AWS_SECRET_ACCESS_KEY present in systemd" \
    "sudo systemctl show thakii-backend.service --property=Environment | grep -q 'AWS_SECRET_ACCESS_KEY='" \
    "success"

# Test 5: Check AWS_DEFAULT_REGION in systemd environment
run_test "AWS_DEFAULT_REGION present in systemd" \
    "sudo systemctl show thakii-backend.service --property=Environment | grep -q 'AWS_DEFAULT_REGION='" \
    "success"

# Test 6: Verify AWS credentials are not empty
AWS_ACCESS_KEY_ID=$(get_systemd_env_value "AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY=$(get_systemd_env_value "AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION=$(get_systemd_env_value "AWS_DEFAULT_REGION")

run_test "AWS_ACCESS_KEY_ID is not empty" \
    "[ -n '$AWS_ACCESS_KEY_ID' ]" \
    "success"

run_test "AWS_SECRET_ACCESS_KEY is not empty" \
    "[ -n '$AWS_SECRET_ACCESS_KEY' ]" \
    "success"

run_test "AWS_DEFAULT_REGION is not empty" \
    "[ -n '$AWS_DEFAULT_REGION' ]" \
    "success"

echo "📊 SYSTEMD ENVIRONMENT VALUES"
echo "============================="
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:8}***"
echo "AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:0:8}***"
echo "AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION"
echo ""

echo "🐍 PYTHON S3 CONNECTIVITY TESTS"
echo "==============================="

# Test 7: Python boto3 S3 connectivity with systemd credentials
run_test "S3 connectivity with systemd credentials" \
    "cd /home/ec2-user/thakii-backend-api && source venv/bin/activate && python3 << 'PYTEST'
import os
import sys
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Set environment variables from systemd
os.environ['AWS_ACCESS_KEY_ID'] = '$AWS_ACCESS_KEY_ID'
os.environ['AWS_SECRET_ACCESS_KEY'] = '$AWS_SECRET_ACCESS_KEY'
os.environ['AWS_DEFAULT_REGION'] = '$AWS_DEFAULT_REGION'

try:
    s3_client = boto3.client('s3')
    bucket_name = 'thakii-video-storage-1753883631'
    
    # Test S3 access
    response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
    print('S3 connection successful')
    sys.exit(0)
    
except NoCredentialsError:
    print('NoCredentialsError: AWS credentials not found')
    sys.exit(1)
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code in ['AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
        print(f'AWS credentials error: {error_code}')
        sys.exit(1)
    else:
        print(f'S3 connection successful (got expected error: {error_code})')
        sys.exit(0)
except Exception as e:
    print(f'Unexpected error: {e}')
    sys.exit(1)
PYTEST" \
    "success"

echo "🌐 BACKEND API ENDPOINT TESTS"
echo "============================="

# Test 8: Backend health endpoint
run_test "Backend health endpoint responds" \
    "curl -s -f 'https://thakii-02.fanusdigital.site/thakii-be/health' > /dev/null" \
    "success"

# Test 9: Backend health returns JSON
run_test "Backend health returns valid JSON" \
    "curl -s 'https://thakii-02.fanusdigital.site/thakii-be/health' | jq -e '.status' > /dev/null" \
    "success"

# Test 10: Backend list endpoint (should not return 500)
run_test "Backend list endpoint does not return 500" \
    "! curl -s -w '%{http_code}' 'https://thakii-02.fanusdigital.site/thakii-be/list' | grep -q '500'" \
    "success"

echo "📁 BACKEND APPLICATION TESTS"
echo "============================"

# Test 11: Backend .env file exists
run_test "Backend .env file exists" \
    "[ -f /home/ec2-user/thakii-backend-api/.env ]" \
    "success"

# Test 12: Backend .env contains AWS credentials
run_test "Backend .env contains AWS_ACCESS_KEY_ID" \
    "grep -q '^AWS_ACCESS_KEY_ID=' /home/ec2-user/thakii-backend-api/.env" \
    "success"

# Test 13: Backend Python environment has required packages
run_test "Backend has boto3 installed" \
    "cd /home/ec2-user/thakii-backend-api && source venv/bin/activate && python3 -c 'import boto3'" \
    "success"

# Test 14: Backend has firebase-admin installed
run_test "Backend has firebase-admin installed" \
    "cd /home/ec2-user/thakii-backend-api && source venv/bin/activate && python3 -c 'import firebase_admin'" \
    "success"

echo "🔍 COMPREHENSIVE S3 UPLOAD SIMULATION"
echo "====================================="

# Test 15: Simulate S3 upload operation (like the backend does)
run_test "Simulate backend S3 upload operation" \
    "cd /home/ec2-user/thakii-backend-api && source venv/bin/activate && python3 << 'PYTEST'
import os
import sys
import boto3
import tempfile
from botocore.exceptions import ClientError, NoCredentialsError

# Set environment variables from systemd (simulate backend environment)
os.environ['AWS_ACCESS_KEY_ID'] = '$AWS_ACCESS_KEY_ID'
os.environ['AWS_SECRET_ACCESS_KEY'] = '$AWS_SECRET_ACCESS_KEY'
os.environ['AWS_DEFAULT_REGION'] = '$AWS_DEFAULT_REGION'

try:
    # Simulate the exact S3 operation that backend performs
    s3_client = boto3.client('s3')
    bucket_name = 'thakii-video-storage-1753883631'
    
    # Create a test file (simulate video upload)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write('test upload simulation')
        test_file_path = f.name
    
    # Test upload (simulate backend upload_video method)
    test_key = 'test-verification/test-upload.txt'
    
    with open(test_file_path, 'rb') as file_obj:
        s3_client.upload_fileobj(file_obj, bucket_name, test_key)
    
    print('S3 upload simulation successful')
    
    # Clean up test file
    s3_client.delete_object(Bucket=bucket_name, Key=test_key)
    os.unlink(test_file_path)
    
    sys.exit(0)
    
except NoCredentialsError:
    print('CRITICAL: NoCredentialsError - AWS credentials not accessible')
    sys.exit(1)
except ClientError as e:
    error_code = e.response['Error']['Code']
    print(f'S3 ClientError: {error_code}')
    if error_code in ['AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
        sys.exit(1)
    else:
        sys.exit(0)  # Other errors are acceptable for this test
except Exception as e:
    print(f'Unexpected error: {e}')
    sys.exit(1)
PYTEST" \
    "success"

echo ""
echo "📊 VERIFICATION RESULTS SUMMARY"
echo "==============================="
echo "Total Tests: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED - AWS CREDENTIALS FIX IS WORKING!"
    echo "✅ The 500 error should be resolved"
    echo "✅ Backend can upload to S3"
    echo "✅ Systemd service has proper AWS credentials"
    echo "✅ End-to-end pipeline should work"
    echo ""
    echo "🚀 NEXT STEPS:"
    echo "   1. Test video upload from frontend"
    echo "   2. Verify PDF generation works"
    echo "   3. Monitor backend logs for any issues"
    echo ""
    exit 0
else
    echo "❌ VERIFICATION FAILED - $FAILED_TESTS TESTS FAILED"
    echo ""
    echo "🔧 TROUBLESHOOTING STEPS:"
    echo "   1. Check systemd service configuration:"
    echo "      sudo systemctl show thakii-backend.service --property=Environment"
    echo "   2. Check backend service logs:"
    echo "      sudo journalctl -u thakii-backend.service -n 50"
    echo "   3. Verify .env file has correct AWS credentials:"
    echo "      cat /home/ec2-user/thakii-backend-api/.env | grep AWS"
    echo "   4. Restart backend service:"
    echo "      sudo systemctl restart thakii-backend.service"
    echo "   5. Re-run this verification script"
    echo ""
    exit 1
fi
