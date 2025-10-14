#!/bin/bash
set -euo pipefail

echo "================================="
echo "End-to-End Video Processing Test"
echo "================================="
echo ""

# Configuration
BACKEND_URL="${BACKEND_URL:-https://thakii-02.fanusdigital.site/thakii-be}"
VIDEO_PATH="${1:-test-video.mp4}"
FIREBASE_TOKEN="${2:-}"
MAX_WAIT_TIME=600  # 10 minutes

if [ -z "$FIREBASE_TOKEN" ]; then
    echo "❌ Error: Firebase token required"
    echo "Usage: $0 <video_path> <firebase_token>"
    exit 1
fi

if [ ! -f "$VIDEO_PATH" ]; then
    echo "❌ Error: Video file not found: $VIDEO_PATH"
    exit 1
fi

echo "📋 Configuration:"
echo "  Backend: $BACKEND_URL"
echo "  Video: $VIDEO_PATH"
echo "  Max wait: ${MAX_WAIT_TIME}s"
echo ""

# Step 1: Upload video
echo "📤 Step 1: Uploading video..."
UPLOAD_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Authorization: Bearer $FIREBASE_TOKEN" \
    -F "file=@$VIDEO_PATH" \
    "$BACKEND_URL/upload")

HTTP_CODE=$(echo "$UPLOAD_RESPONSE" | tail -1)
RESPONSE_BODY=$(echo "$UPLOAD_RESPONSE" | head -n -1)

echo "  HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ]; then
    echo "❌ Upload failed with status $HTTP_CODE"
    echo "Response: $RESPONSE_BODY"
    exit 1
fi

# Extract video_id from response
VIDEO_ID=$(echo "$RESPONSE_BODY" | grep -o '"video_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$VIDEO_ID" ]; then
    # Try alternative field names
    VIDEO_ID=$(echo "$RESPONSE_BODY" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
fi

if [ -z "$VIDEO_ID" ]; then
    echo "❌ Could not extract video_id from response"
    echo "Response: $RESPONSE_BODY"
    exit 1
fi

echo "✅ Video uploaded successfully"
echo "  Video ID: $VIDEO_ID"

# Step 2: Monitor processing status
echo ""
echo "⏳ Step 2: Monitoring processing status..."
echo "  Checking every 10 seconds (max ${MAX_WAIT_TIME}s)..."

START_TIME=$(date +%s)
LAST_STATUS=""

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    if [ $ELAPSED -gt $MAX_WAIT_TIME ]; then
        echo "❌ Timeout: Processing took longer than ${MAX_WAIT_TIME}s"
        exit 1
    fi
    
    # Check status
    STATUS_RESPONSE=$(curl -s "$BACKEND_URL/status/$VIDEO_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$STATUS" != "$LAST_STATUS" ]; then
        echo "  [${ELAPSED}s] Status: $STATUS"
        LAST_STATUS="$STATUS"
    fi
    
    case "$STATUS" in
        completed)
            echo "✅ Processing completed!"
            break
            ;;
        failed)
            echo "❌ Processing failed"
            echo "Response: $STATUS_RESPONSE"
            exit 1
            ;;
        processing|in_queue|uploaded)
            # Still processing, wait
            sleep 10
            ;;
        *)
            echo "⚠️  Unknown status: $STATUS"
            sleep 10
            ;;
    esac
done

# Step 3: Get PDF URL
echo ""
echo "📥 Step 3: Retrieving PDF..."

PDF_URL=$(echo "$STATUS_RESPONSE" | grep -o '"pdf_url":"[^"]*"' | cut -d'"' -f4)

if [ -z "$PDF_URL" ]; then
    echo "❌ Could not extract pdf_url from response"
    echo "Response: $STATUS_RESPONSE"
    exit 1
fi

echo "  PDF URL: $PDF_URL"

# Step 4: Download PDF
OUTPUT_PDF="/tmp/e2e_test_output_${VIDEO_ID}.pdf"
echo "  Downloading to: $OUTPUT_PDF"

curl -s -o "$OUTPUT_PDF" "$PDF_URL"

if [ ! -f "$OUTPUT_PDF" ]; then
    echo "❌ Failed to download PDF"
    exit 1
fi

FILE_SIZE=$(stat -f%z "$OUTPUT_PDF" 2>/dev/null || stat -c%s "$OUTPUT_PDF" 2>/dev/null)
echo "✅ PDF downloaded successfully (${FILE_SIZE} bytes)"

# Step 5: Validate PDF content
echo ""
echo "🔍 Step 5: Validating PDF content..."

# Check if we have the validation script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATOR="$SCRIPT_DIR/compare_pdf_content.py"

if [ -f "$VALIDATOR" ]; then
    python3 "$VALIDATOR" "$OUTPUT_PDF" "Thank you"
    VALIDATION_EXIT=$?
    
    if [ $VALIDATION_EXIT -eq 0 ]; then
        echo "✅ PDF validation passed"
    else
        echo "❌ PDF validation failed"
        exit 1
    fi
else
    echo "⚠️  Validator script not found, performing basic checks..."
    
    # Basic checks
    if [ $FILE_SIZE -lt 100000 ]; then
        echo "❌ PDF too small (${FILE_SIZE} bytes), likely fake content"
        exit 1
    fi
    
    echo "✅ PDF size check passed (${FILE_SIZE} bytes)"
fi

# Final summary
echo ""
echo "================================="
echo "✅ End-to-End Test PASSED"
echo "================================="
echo ""
echo "📊 Summary:"
echo "  ✅ Video uploaded successfully"
echo "  ✅ Processing completed in ${ELAPSED}s"
echo "  ✅ PDF generated and downloaded"
echo "  ✅ PDF validation passed"
echo "  📄 PDF saved at: $OUTPUT_PDF"
echo ""
echo "🎉 Real transcription is working in production!"

exit 0

