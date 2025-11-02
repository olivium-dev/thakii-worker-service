#!/bin/bash
# Check if Redis is already installed
if command -v redis-server &> /dev/null; then
    echo "Redis already installed: $(redis-server --version)"
    exit 0
fi

# Install Redis using Homebrew (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install redis
    brew services start redis
else
    # Linux fallback
    sudo apt-get update && sudo apt-get install -y redis-server
    sudo systemctl enable redis-server
    sudo systemctl start redis-server
fi

# Verify Redis is running
redis-cli ping || exit 1
echo "Redis installation successful"

