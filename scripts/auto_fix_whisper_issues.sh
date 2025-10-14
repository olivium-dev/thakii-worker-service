#!/bin/bash
set -euo pipefail

echo "================================="
echo "Auto-Fix Whisper Issues"
echo "================================="
echo ""

VALIDATION_OUTPUT="$1"
FIX_APPLIED=0

# Analyze validation output to detect issue type
detect_issue_type() {
    if echo "$VALIDATION_OUTPUT" | grep -q "whisper import failed"; then
        echo "missing_module"
    elif echo "$VALIDATION_OUTPUT" | grep -q "torch import failed"; then
        echo "missing_torch"
    elif echo "$VALIDATION_OUTPUT" | grep -q "Model loading failed"; then
        echo "model_load_failed"
    elif echo "$VALIDATION_OUTPUT" | grep -q "ffmpeg is not available"; then
        echo "ffmpeg_missing"
    elif echo "$VALIDATION_OUTPUT" | grep -q "Transcription failed"; then
        echo "transcription_failed"
    elif echo "$VALIDATION_OUTPUT" | grep -q "Permission denied"; then
        echo "permission_issue"
    else
        echo "unknown"
    fi
}

# Fix missing Python modules
fix_missing_module() {
    echo "🔧 Fix: Reinstalling Python dependencies..."
    
    cd "/home/ec2-user/thakii-worker-service"
    source venv/bin/activate
    
    pip install --upgrade pip --quiet
    pip install "numpy<2" --quiet
    pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --quiet
    pip install openai-whisper==20231117 --quiet
    
    echo "✅ Python dependencies reinstalled"
    return 0
}

# Fix ffmpeg missing
fix_ffmpeg_missing() {
    echo "🔧 Fix: Reinstalling ffmpeg..."
    
    # Detect package manager
    if command -v yum &> /dev/null; then
        PKG_MGR="yum"
    elif command -v dnf &> /dev/null; then
        PKG_MGR="dnf"
    elif command -v apt-get &> /dev/null; then
        PKG_MGR="apt-get"
    else
        echo "❌ No supported package manager found"
        return 1
    fi
    
    case $PKG_MGR in
        yum|dnf)
            sudo $PKG_MGR install -y epel-release || true
            sudo $PKG_MGR install -y ffmpeg || {
                sudo $PKG_MGR install -y --nogpgcheck \
                    https://download1.rpmfusion.org/free/el/rpmfusion-free-release-$(rpm -E %rhel).noarch.rpm || true
                sudo $PKG_MGR install -y ffmpeg
            }
            ;;
        apt-get)
            sudo apt-get update -qq
            sudo apt-get install -y ffmpeg
            ;;
    esac
    
    echo "✅ ffmpeg reinstalled"
    return 0
}

# Fix model loading issues
fix_model_load() {
    echo "🔧 Fix: Retrying Whisper model download..."
    
    cd "/home/ec2-user/thakii-worker-service"
    source venv/bin/activate
    
    # Clear cached models
    echo "🗑️  Clearing model cache..."
    rm -rf ~/.cache/whisper
    
    # Download model again
    python3 << 'PYEOF'
import whisper
import sys

try:
    print("📥 Downloading Whisper medium model...")
    model = whisper.load_model("medium")
    print("✅ Model downloaded successfully")
    sys.exit(0)
except Exception as e:
    print(f"❌ Model download failed: {e}")
    sys.exit(1)
PYEOF
    
    return $?
}

# Fix permission issues
fix_permissions() {
    echo "🔧 Fix: Fixing venv permissions..."
    
    cd "/home/ec2-user/thakii-worker-service"
    
    # Fix ownership
    sudo chown -R ec2-user:ec2-user venv/
    
    # Fix permissions
    chmod -R u+rwX venv/
    
    echo "✅ Permissions fixed"
    return 0
}

# Main auto-fix logic
main() {
    ISSUE_TYPE=$(detect_issue_type)
    
    echo "🔍 Detected issue type: $ISSUE_TYPE"
    echo ""
    
    case $ISSUE_TYPE in
        missing_module|missing_torch)
            fix_missing_module
            FIX_APPLIED=$?
            ;;
        ffmpeg_missing)
            fix_ffmpeg_missing
            FIX_APPLIED=$?
            ;;
        model_load_failed)
            fix_model_load
            FIX_APPLIED=$?
            ;;
        permission_issue)
            fix_permissions
            FIX_APPLIED=$?
            ;;
        transcription_failed)
            echo "🔧 Attempting comprehensive fix..."
            fix_missing_module
            if [ $? -eq 0 ]; then
                fix_model_load
                FIX_APPLIED=$?
            else
                FIX_APPLIED=1
            fi
            ;;
        unknown)
            echo "❌ Unable to detect specific issue"
            echo "📋 Validation output:"
            echo "$VALIDATION_OUTPUT"
            FIX_APPLIED=1
            ;;
    esac
    
    echo ""
    if [ $FIX_APPLIED -eq 0 ]; then
        echo "✅ Auto-fix applied successfully"
        echo "🔄 Please revalidate installation"
    else
        echo "❌ Auto-fix failed"
        echo "⚠️  Manual intervention may be required"
    fi
    
    exit $FIX_APPLIED
}

# Run main
main

