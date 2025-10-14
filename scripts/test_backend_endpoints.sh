#!/bin/bash
# Quick local test script to verify backend endpoints are working
# This can be run from anywhere to test if the AWS credentials fix worked

set -e

echo "🧪 BACKEND ENDPOINTS TEST"
echo "========================"
echo "Testing if the AWS credentials fix resolved the 500 errors..."
echo ""

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run endpoint test
test_endpoint() {
    local test_name="$1"
    local url="$2"
    local method="${3:-GET}"
    local expected_not_500="${4:-true}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo "🔍 TEST $TOTAL_TESTS: $test_name"
    echo "   URL: $url"
    echo "   Method: $method"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "%{http_code}" "$url" -o /tmp/response_body.txt)
        http_code="$response"
    else
        response=$(curl -s -w "%{http_code}" -X "$method" "$url" -o /tmp/response_body.txt)
        http_code="$response"
    fi
    
    echo "   Status: $http_code"
    
    # Check response body if it exists
    if [ -f /tmp/response_body.txt ] && [ -s /tmp/response_body.txt ]; then
        body_preview=$(head -c 100 /tmp/response_body.txt)
        echo "   Response: ${body_preview}..."
    fi
    
    if [ "$expected_not_500" = "true" ]; then
        if [ "$http_code" != "500" ]; then
            echo "   ✅ PASSED (not 500)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "   ❌ FAILED (got 500 error)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            # Show error details
            if [ -f /tmp/response_body.txt ]; then
                echo "   Error details:"
                cat /tmp/response_body.txt | head -5 | sed 's/^/      /'
            fi
        fi
    else
        if [ "$http_code" = "500" ]; then
            echo "   ✅ PASSED (expected 500)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo "   ❌ FAILED (expected 500 but got $http_code)"
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    fi
    echo ""
}

# Test JSON parsing helper
test_json_response() {
    local test_name="$1"
    local url="$2"
    local json_field="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo "🔍 TEST $TOTAL_TESTS: $test_name"
    echo "   URL: $url"
    echo "   Expected JSON field: $json_field"
    
    response=$(curl -s "$url")
    echo "   Response: $response"
    
    if echo "$response" | jq -e "$json_field" >/dev/null 2>&1; then
        echo "   ✅ PASSED (valid JSON with expected field)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "   ❌ FAILED (invalid JSON or missing field)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

echo "🏥 HEALTH ENDPOINT TESTS"
echo "======================="

# Test 1: Health endpoint should return 200 with JSON
test_json_response "Health endpoint returns valid JSON" \
    "https://thakii-02.fanusdigital.site/thakii-be/health" \
    ".status"

echo "📋 LIST ENDPOINT TESTS"
echo "====================="

# Test 2: List endpoint should not return 500
test_endpoint "List endpoint does not return 500" \
    "https://thakii-02.fanusdigital.site/thakii-be/list" \
    "GET" \
    "true"

echo "📤 UPLOAD ENDPOINT TESTS"
echo "======================="

# Test 3: Upload endpoint should not return 500 (even with missing data)
# Note: We expect 400 or 422 for missing form data, but NOT 500
test_endpoint "Upload endpoint does not return 500 (missing data is ok)" \
    "https://thakii-02.fanusdigital.site/thakii-be/upload" \
    "POST" \
    "true"

echo "🔍 CORS AND OPTIONS TESTS"
echo "========================"

# Test 4: OPTIONS request should work
test_endpoint "OPTIONS request works" \
    "https://thakii-02.fanusdigital.site/thakii-be/health" \
    "OPTIONS" \
    "true"

echo "🌐 GENERAL CONNECTIVITY TESTS"
echo "============================"

# Test 5: Base URL should be accessible
test_endpoint "Base backend URL accessible" \
    "https://thakii-02.fanusdigital.site/thakii-be/" \
    "GET" \
    "true"

# Clean up temp files
rm -f /tmp/response_body.txt

echo "📊 TEST RESULTS SUMMARY"
echo "======================"
echo "Total Tests: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED!"
    echo "✅ Backend endpoints are working correctly"
    echo "✅ No 500 errors detected"
    echo "✅ AWS credentials fix appears to be successful"
    echo ""
    echo "🚀 NEXT STEPS:"
    echo "   1. Try uploading a video from the frontend"
    echo "   2. Check if PDF generation works end-to-end"
    echo "   3. Monitor backend logs for any issues"
    echo ""
    echo "📋 FRONTEND TEST:"
    echo "   Visit: https://thakii-frontend.netlify.app"
    echo "   Try uploading a video file"
    echo "   Should succeed without 500 errors"
    echo ""
    exit 0
else
    echo "❌ SOME TESTS FAILED!"
    echo "💥 The AWS credentials fix may not be complete"
    echo ""
    echo "🔧 TROUBLESHOOTING:"
    echo "   1. Run the full verification script on the server:"
    echo "      bash /home/ec2-user/verify_aws_credentials_fix.sh"
    echo "   2. Check backend service logs:"
    echo "      sudo journalctl -u thakii-backend.service -f"
    echo "   3. Verify systemd environment:"
    echo "      sudo systemctl show thakii-backend.service --property=Environment"
    echo "   4. Re-run the AWS credentials fix:"
    echo "      bash /home/ec2-user/fix_backend_aws_credentials.sh"
    echo ""
    exit 1
fi
