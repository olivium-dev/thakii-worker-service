#!/bin/bash
set -euo pipefail

echo "================================="
echo "Whisper AI Installation Script"
echo "================================="
echo ""

# Detect OS and package manager
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        echo "❌ Cannot detect OS"
        exit 1
    fi
    
    echo "📋 Detected OS: $OS $VERSION"
    
    if command -v yum &> /dev/null; then
        PKG_MGR="yum"
    elif command -v dnf &> /dev/null; then
        PKG_MGR="dnf"
    elif command -v apt-get &> /dev/null; then
        PKG_MGR="apt-get"
    else
        echo "❌ No supported package manager found"
        exit 1
    fi
    
    echo "📦 Package manager: $PKG_MGR"
}

# Install ffmpeg
install_ffmpeg() {
    echo ""
    echo "📥 Installing ffmpeg..."
    
    if command -v ffmpeg &> /dev/null; then
        echo "✅ ffmpeg already installed: $(ffmpeg -version | head -1)"
        return 0
    fi
    
    case $PKG_MGR in
        yum|dnf)
            # Amazon Linux / CentOS / RHEL
            echo "Installing EPEL repository..."
            sudo $PKG_MGR install -y epel-release || true
            
            echo "Installing ffmpeg..."
            sudo $PKG_MGR install -y ffmpeg || {
                echo "⚠️  Standard repo failed, trying RPM Fusion..."
                sudo $PKG_MGR install -y --nogpgcheck \
                    https://download1.rpmfusion.org/free/el/rpmfusion-free-release-$(rpm -E %rhel).noarch.rpm || true
                sudo $PKG_MGR install -y ffmpeg
            }
            ;;
        apt-get)
            # Ubuntu / Debian
            sudo apt-get update -qq
            sudo apt-get install -y ffmpeg
            ;;
        *)
            echo "❌ Unsupported package manager: $PKG_MGR"
            exit 1
            ;;
    esac
    
    if command -v ffmpeg &> /dev/null; then
        echo "✅ ffmpeg installed successfully: $(ffmpeg -version | head -1)"
    else
        echo "❌ ffmpeg installation failed"
        exit 3
    fi
}

# Install Python dependencies
install_python_dependencies() {
    echo ""
    echo "🐍 Installing Python dependencies..."
    
    WORKER_PATH="/home/ec2-user/thakii-worker-service"
    
    if [ ! -d "$WORKER_PATH" ]; then
        echo "❌ Worker directory not found: $WORKER_PATH"
        exit 1
    fi
    
    cd "$WORKER_PATH"
    
    # Check if venv exists
    if [ ! -d "venv" ]; then
        echo "❌ Virtual environment not found at $WORKER_PATH/venv"
        exit 1
    fi
    
    echo "📁 Working directory: $WORKER_PATH"
    echo "🔧 Activating virtual environment..."
    source venv/bin/activate
    
    # Verify activation
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "❌ Failed to activate virtual environment"
        exit 1
    fi
    
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
    
    # Upgrade pip
    echo "⬆️  Upgrading pip..."
    pip install --upgrade pip --quiet
    
    # Install Whisper and dependencies
    echo "📦 Installing Whisper AI and dependencies..."
    echo "   This will download ~2GB of packages including PyTorch..."
    
    # Install in specific order to avoid conflicts
    pip install "numpy<2" --quiet
    pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --quiet
    pip install openai-whisper==20231117 --quiet
    
    echo "✅ Python dependencies installed"
}

# Download Whisper model
download_whisper_model() {
    echo ""
    echo "📥 Downloading Whisper medium model..."
    echo "   Model size: ~1.5GB (this may take a few minutes)"
    
    cd "/home/ec2-user/thakii-worker-service"
    source venv/bin/activate
    
    python3 << 'PYEOF'
import whisper
import sys

try:
    print("🔽 Loading Whisper medium model...")
    model = whisper.load_model("medium")
    print("✅ Whisper medium model downloaded and cached successfully")
    sys.exit(0)
except Exception as e:
    print(f"❌ Failed to download Whisper model: {e}")
    sys.exit(2)
PYEOF
    
    if [ $? -ne 0 ]; then
        echo "❌ Model download failed"
        exit 2
    fi
}

# Verify installation
verify_installation() {
    echo ""
    echo "🔍 Verifying installation..."
    
    cd "/home/ec2-user/thakii-worker-service"
    source venv/bin/activate
    
    python3 << 'PYEOF'
import sys

checks_passed = 0
checks_total = 0

# Check 1: Import whisper
checks_total += 1
try:
    import whisper
    print("✅ whisper module imports successfully")
    checks_passed += 1
except ImportError as e:
    print(f"❌ whisper import failed: {e}")

# Check 2: Import torch
checks_total += 1
try:
    import torch
    print(f"✅ torch module imports successfully (version {torch.__version__})")
    checks_passed += 1
except ImportError as e:
    print(f"❌ torch import failed: {e}")

# Check 3: Load model
checks_total += 1
try:
    import whisper
    model = whisper.load_model("medium")
    print("✅ Whisper medium model loads successfully")
    checks_passed += 1
except Exception as e:
    print(f"❌ Model loading failed: {e}")

print(f"\n📊 Verification: {checks_passed}/{checks_total} checks passed")

if checks_passed == checks_total:
    print("✅ All checks passed!")
    sys.exit(0)
else:
    print("❌ Some checks failed")
    sys.exit(1)
PYEOF
    
    VERIFY_EXIT=$?
    
    # Check ffmpeg
    if command -v ffmpeg &> /dev/null; then
        echo "✅ ffmpeg is available: $(which ffmpeg)"
    else
        echo "❌ ffmpeg is not available"
        VERIFY_EXIT=1
    fi
    
    return $VERIFY_EXIT
}

# Main execution
main() {
    echo "🚀 Starting Whisper AI installation..."
    echo ""
    
    detect_os
    install_ffmpeg
    install_python_dependencies
    download_whisper_model
    verify_installation
    
    echo ""
    echo "================================="
    echo "✅ Installation Complete!"
    echo "================================="
    echo ""
    echo "📋 Summary:"
    echo "  ✅ ffmpeg installed"
    echo "  ✅ Python dependencies installed"
    echo "  ✅ Whisper medium model downloaded"
    echo "  ✅ All verifications passed"
    echo ""
    echo "🔄 Ready to restart thakii-worker.service"
}

# Run main function
main

