#!/bin/bash
# Script to fix AWS credentials in backend systemd service
# This script addresses the root cause of 500 errors in the backend

set -e

echo "🔧 Fixing Backend AWS Credentials Configuration"
echo "================================================"

# Define paths
BACKEND_DIR="/home/ec2-user/thakii-backend-api"
SERVICE_FILE="/etc/systemd/system/thakii-backend.service"

# Check if backend directory exists
if [ ! -d "$BACKEND_DIR" ]; then
    echo "❌ Backend directory not found: $BACKEND_DIR"
    exit 1
fi

# Check if .env file exists
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "❌ .env file not found in backend directory"
    exit 1
fi

echo "📁 Backend directory: $BACKEND_DIR"
echo "📝 Loading AWS credentials from .env file..."

# Extract AWS credentials from .env file
AWS_ACCESS_KEY_ID=$(grep '^AWS_ACCESS_KEY_ID=' "$BACKEND_DIR/.env" | cut -d= -f2)
AWS_SECRET_ACCESS_KEY=$(grep '^AWS_SECRET_ACCESS_KEY=' "$BACKEND_DIR/.env" | cut -d= -f2)
AWS_DEFAULT_REGION=$(grep '^AWS_DEFAULT_REGION=' "$BACKEND_DIR/.env" | cut -d= -f2)
FIREBASE_SERVICE_ACCOUNT_KEY=$(grep '^FIREBASE_SERVICE_ACCOUNT_KEY=' "$BACKEND_DIR/.env" | cut -d= -f2)

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "❌ AWS credentials not found in .env file"
    exit 1
fi

echo "✅ AWS credentials loaded from .env"
echo "   Region: $AWS_DEFAULT_REGION"

# Backup existing service file
echo "💾 Creating backup of systemd service file..."
sudo cp "$SERVICE_FILE" "${SERVICE_FILE}.backup.$(date +%Y%m%d-%H%M%S)"

# Create updated systemd service file with AWS credentials
echo "📝 Updating systemd service configuration..."
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Thakii Backend API Service
After=network.target

[Service]
User=ec2-user
WorkingDirectory=$BACKEND_DIR
Environment=FLASK_ENV=production
Environment=FLASK_DEBUG=False
Environment=PORT=5001
Environment=GOOGLE_CLOUD_PROJECT=thakii-973e3
Environment=FIREBASE_PROJECT_ID=thakii-973e3
Environment=ALLOWED_ORIGINS=https://thakii-frontend.netlify.app
Environment=AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
Environment=AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
Environment=AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION
Environment=S3_BUCKET_NAME=thakii-video-storage-1753883631
Environment=FIREBASE_SERVICE_ACCOUNT_KEY=$FIREBASE_SERVICE_ACCOUNT_KEY
ExecStart=$BACKEND_DIR/venv/bin/python3 $BACKEND_DIR/app.py
Restart=always
RestartSec=5
StandardOutput=append:$BACKEND_DIR/systemd.log
StandardError=append:$BACKEND_DIR/systemd.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Systemd service configuration updated"

# Reload systemd daemon
echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

# Restart backend service
echo "🔄 Restarting backend service..."
sudo systemctl restart thakii-backend.service

# Wait for service to start
echo "⏳ Waiting for service to start..."
sleep 5

# Check service status
echo "🔍 Checking service status..."
if sudo systemctl is-active --quiet thakii-backend.service; then
    echo "✅ Backend service is running"
else
    echo "❌ Backend service failed to start"
    echo "📋 Service logs:"
    sudo journalctl -u thakii-backend.service -n 50 --no-pager
    exit 1
fi

# Test AWS S3 connectivity
echo "🧪 Testing AWS S3 connectivity..."
cd "$BACKEND_DIR"
source venv/bin/activate

python3 << 'PYTEST'
import os
import sys

# Set environment variables from systemd
os.environ['AWS_ACCESS_KEY_ID'] = '${AWS_ACCESS_KEY_ID}'
os.environ['AWS_SECRET_ACCESS_KEY'] = '${AWS_SECRET_ACCESS_KEY}'
os.environ['AWS_DEFAULT_REGION'] = '${AWS_DEFAULT_REGION}'

try:
    import boto3
    from botocore.exceptions import ClientError
    
    s3_client = boto3.client('s3')
    bucket_name = 'thakii-video-storage-1753883631'
    
    # Test S3 access
    response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
    print(f"✅ S3 connection successful!")
    print(f"   Bucket: {bucket_name}")
    print(f"   Region: ${AWS_DEFAULT_REGION}")
    sys.exit(0)
    
except ClientError as e:
    print(f"❌ S3 connection failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
PYTEST

if [ $? -eq 0 ]; then
    echo "✅ AWS S3 is working correctly"
else
    echo "❌ AWS S3 connection test failed"
    exit 1
fi

echo ""
echo "🎉 Backend AWS Credentials Configuration Complete!"
echo "================================================"
echo "✅ AWS credentials added to systemd service"
echo "✅ Backend service restarted"
echo "✅ S3 connectivity verified"
echo ""
echo "🔍 Updated systemd service configuration:"
sudo systemctl show thakii-backend.service --property=Environment

echo ""
echo "📊 Next steps:"
echo "   1. Test backend upload endpoint: curl -X POST https://thakii-02.fanusdigital.site/thakii-be/upload"
echo "   2. Monitor logs: sudo journalctl -u thakii-backend.service -f"
echo "   3. Check service status: sudo systemctl status thakii-backend.service"

