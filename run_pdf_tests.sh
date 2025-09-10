#!/bin/bash

echo "🚀 Setting up PDF Generation Tests"
echo "=================================="

# Create test directory
mkdir -p pdf_generation_tests

# Copy test video
if [ -f "../test.mp4" ]; then
    cp "../test.mp4" pdf_generation_tests/
    echo "✅ Copied test.mp4 to test directory"
else
    echo "❌ test.mp4 not found in parent directory"
    exit 1
fi

# Check if lecture2pdf-external exists
if [ -d "../backend/lecture2pdf-external" ]; then
    echo "✅ Found lecture2pdf-external directory"
else
    echo "❌ lecture2pdf-external not found"
    exit 1
fi

# Install requirements if needed
echo "📦 Installing requirements..."
if [ -f "../backend/lecture2pdf-external/requirements.txt" ]; then
    pip install -r ../backend/lecture2pdf-external/requirements.txt
fi

# Run the comprehensive test
echo ""
echo "🧪 Running PDF Generation Tests"
echo "==============================="
python3 test_pdf_generation.py

echo ""
echo "📋 Test Results:"
echo "==============="
ls -la pdf_generation_tests/
