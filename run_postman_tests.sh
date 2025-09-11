#!/bin/bash

# Thakii Worker Service - Postman E2E Test Runner
# This script runs the Postman collection using Newman CLI

echo "🚀 Thakii Worker Service - Postman E2E Test Runner"
echo "=================================================="

# Check if Newman is installed
if ! command -v newman &> /dev/null; then
    echo "❌ Newman CLI not found. Installing..."
    npm install -g newman
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install Newman. Please install Node.js and npm first."
        exit 1
    fi
fi

echo "✅ Newman CLI found"

# Set file paths
COLLECTION_FILE="Thakii_Worker_Service_E2E_Test.postman_collection.json"
ENVIRONMENT_FILE="Thakii_Production_Environment.postman_environment.json"
RESULTS_DIR="postman_test_results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create results directory
mkdir -p "$RESULTS_DIR"

echo ""
echo "📋 Test Configuration:"
echo "Collection: $COLLECTION_FILE"
echo "Environment: $ENVIRONMENT_FILE"
echo "Results Dir: $RESULTS_DIR"
echo "Timestamp: $TIMESTAMP"

# Check if files exist
if [ ! -f "$COLLECTION_FILE" ]; then
    echo "❌ Collection file not found: $COLLECTION_FILE"
    exit 1
fi

if [ ! -f "$ENVIRONMENT_FILE" ]; then
    echo "❌ Environment file not found: $ENVIRONMENT_FILE"
    exit 1
fi

echo ""
echo "🧪 Running Postman E2E Tests..."
echo "================================"

# Run Newman with comprehensive reporting
newman run "$COLLECTION_FILE" \
    -e "$ENVIRONMENT_FILE" \
    --reporters cli,json,html \
    --reporter-json-export "$RESULTS_DIR/results_$TIMESTAMP.json" \
    --reporter-html-export "$RESULTS_DIR/report_$TIMESTAMP.html" \
    --delay-request 2000 \
    --timeout-request 30000 \
    --timeout-script 10000 \
    --color on \
    --verbose

# Check test results
EXIT_CODE=$?

echo ""
echo "📊 Test Results Summary:"
echo "======================="

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed successfully!"
    echo "📄 HTML Report: $RESULTS_DIR/report_$TIMESTAMP.html"
    echo "📋 JSON Results: $RESULTS_DIR/results_$TIMESTAMP.json"
    echo ""
    echo "🎉 Thakii Worker Service E2E Tests: SUCCESS"
else
    echo "❌ Some tests failed (Exit code: $EXIT_CODE)"
    echo "📄 Check HTML Report: $RESULTS_DIR/report_$TIMESTAMP.html"
    echo "📋 Check JSON Results: $RESULTS_DIR/results_$TIMESTAMP.json"
    echo ""
    echo "🔍 Troubleshooting Tips:"
    echo "1. Verify environment variables in $ENVIRONMENT_FILE"
    echo "2. Check API endpoints are accessible"
    echo "3. Ensure Firebase and AWS credentials are valid"
    echo "4. Review server logs for processing errors"
fi

echo ""
echo "📁 Test artifacts saved in: $RESULTS_DIR/"
echo "🔗 Open HTML report in browser for detailed results"

exit $EXIT_CODE
