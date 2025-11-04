#!/bin/bash
# Deploy Worker API service to thakii-03
# This script is intended to be run by GitHub Actions

set -e

# Configuration
WORKER_DIR="/Users/fanusdigital/Desktop/thakii-worker-service"
LAUNCHD_DIR="/Users/fanusdigital/Library/LaunchAgents"
WORKER_API_PLIST="com.thakii.worker_api.plist"
LOGS_DIR="$WORKER_DIR/logs"

echo "🚀 Deploying Worker API service to thakii-03..."

# Create logs directory if it doesn't exist
echo "📁 Creating logs directory..."
mkdir -p "$LOGS_DIR"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt
pip3 install requests==2.31.0  # Ensure requests is installed for API client

# Copy LaunchDaemon plist to LaunchAgents directory
echo "📄 Installing LaunchDaemon plist..."
cp "$WORKER_API_PLIST" "$LAUNCHD_DIR/"

# Set permissions
echo "🔒 Setting permissions..."
chmod 644 "$LAUNCHD_DIR/$WORKER_API_PLIST"

# Unload existing service if it exists
echo "🛑 Unloading existing service..."
launchctl unload "$LAUNCHD_DIR/$WORKER_API_PLIST" || true

# Load new service
echo "🚀 Loading new service..."
launchctl load -w "$LAUNCHD_DIR/$WORKER_API_PLIST"

# Start service
echo "▶️ Starting service..."
launchctl start com.thakii.worker_api

# Verify service is running
echo "✅ Verifying service is running..."
launchctl list | grep com.thakii.worker_api || echo "❌ Service not running!"

echo "✅ Worker API service deployed successfully!"
