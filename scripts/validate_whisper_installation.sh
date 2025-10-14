#!/bin/bash
set -euo pipefail

echo "================================="
echo "Whisper Installation Validation"
echo "================================="
echo ""

EXIT_CODE=0

# Change to worker directory
cd "/home/ec2-user/thakii-worker-service"
source venv/bin/activate

# Check 1: Python module imports
echo "🔍 Check 1: Python module imports"
python3 << 'PYEOF'
import sys

try:
    import whisper
    print("  ✅ whisper imports successfully")
except ImportError as e:
    print(f"  ❌ whisper import failed: {e}")
    sys.exit(1)

try:
    import torch
    print(f"  ✅ torch imports successfully (v{torch.__version__})")
except ImportError as e:
    print(f"  ❌ torch import failed: {e}")
    sys.exit(1)

print("  ✅ All imports successful")
PYEOF

if [ $? -ne 0 ]; then
    echo "  ❌ Import check failed"
    EXIT_CODE=1
fi

# Check 2: Whisper model loading
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "🔍 Check 2: Whisper model loading"
    python3 << 'PYEOF'
import sys
import whisper

try:
    model = whisper.load_model("medium")
    print("  ✅ Whisper medium model loads successfully")
    sys.exit(0)
except Exception as e:
    print(f"  ❌ Model loading failed: {e}")
    sys.exit(2)
PYEOF
    
    if [ $? -ne 0 ]; then
        echo "  ❌ Model loading check failed"
        EXIT_CODE=2
    fi
fi

# Check 3: ffmpeg availability
echo ""
echo "🔍 Check 3: ffmpeg availability"
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1)
    echo "  ✅ ffmpeg is available: $FFMPEG_VERSION"
else
    echo "  ❌ ffmpeg is not available in PATH"
    EXIT_CODE=3
fi

# Check 4: Test transcription (5-second test)
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "🔍 Check 4: Test transcription"
    echo "  Creating 5-second test audio..."
    
    # Generate 5-second test audio with speech
    ffmpeg -f lavfi -i "sine=frequency=1000:duration=5" -ac 1 -ar 16000 /tmp/test_audio.wav -y &>/dev/null
    
    python3 << 'PYEOF'
import sys
import whisper
import warnings
warnings.filterwarnings("ignore")

try:
    print("  🎤 Loading model...")
    model = whisper.load_model("medium")
    
    print("  🎵 Transcribing test audio...")
    result = model.transcribe("/tmp/test_audio.wav", fp16=False)
    
    # Even empty audio should produce a result object
    if result is not None:
        print(f"  ✅ Transcription completed successfully")
        print(f"  📊 Result type: {type(result)}")
        sys.exit(0)
    else:
        print("  ❌ Transcription returned None")
        sys.exit(4)
except Exception as e:
    print(f"  ❌ Transcription failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(4)
PYEOF
    
    if [ $? -ne 0 ]; then
        echo "  ❌ Transcription test failed"
        EXIT_CODE=4
    fi
    
    # Cleanup
    rm -f /tmp/test_audio.wav
fi

# Check 5: Worker service status
echo ""
echo "🔍 Check 5: Worker service status"
if sudo systemctl is-active --quiet thakii-worker.service; then
    echo "  ✅ thakii-worker.service is active"
else
    echo "  ⚠️  thakii-worker.service is not active"
    # Don't fail on this - service might not be started yet
fi

# Final summary
echo ""
echo "================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All validation checks passed"
    echo "================================="
    echo ""
    echo "📋 Validated:"
    echo "  ✅ Python modules (whisper, torch)"
    echo "  ✅ Whisper medium model"
    echo "  ✅ ffmpeg availability"
    echo "  ✅ Transcription capability"
else
    echo "❌ Validation failed with exit code: $EXIT_CODE"
    echo "================================="
    echo ""
    echo "Exit codes:"
    echo "  1 = Dependency import failed"
    echo "  2 = Model loading failed"
    echo "  3 = ffmpeg missing"
    echo "  4 = Transcription test failed"
fi

echo ""
exit $EXIT_CODE

