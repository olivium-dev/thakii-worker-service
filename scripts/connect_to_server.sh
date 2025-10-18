#!/bin/bash

# Script to connect to the Thakii worker server via Cloudflare Access SSH

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "Error: cloudflared is not installed. Please install it first."
    echo "macOS: brew install cloudflare/cloudflare/cloudflared"
    echo "Linux: curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb && sudo dpkg -i cloudflared.deb"
    exit 1
fi

# Set variables
SSH_KEY="thakii-02-developer-key"
HOSTNAME="vps-71.fds-1.com"
USERNAME="ec2-user"
COMMAND=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --alt)
            # Use alternative connection method (localhost proxy)
            echo "Using alternative connection method via localhost proxy..."
            cloudflared access ssh --hostname ssh-thakii-3.fanusdigital.site --url ssh://localhost:2222 &
            TUNNEL_PID=$!
            sleep 5
            ssh fanusdigital@localhost -p 2222
            kill $TUNNEL_PID 2>/dev/null
            exit 0
            ;;
        --password)
            # Use password authentication with sshpass
            if ! command -v sshpass &> /dev/null; then
                echo "Error: sshpass is not installed. Please install it first."
                echo "macOS: brew install hudochenkov/sshpass/sshpass"
                echo "Linux: apt-get install sshpass"
                exit 1
            fi
            echo "Using password authentication..."
            sshpass -p "P@ssw0rd768" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null fanusdigital@localhost -p 2222
            exit 0
            ;;
        --command)
            COMMAND="$2"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --alt         Use alternative connection method via localhost proxy"
            echo "  --password    Use password authentication with sshpass"
            echo "  --command     Run a specific command on the server"
            echo "  --help        Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
    shift
done

# Ensure SSH key has correct permissions
chmod 600 "$SSH_KEY"

# Connect to server
if [ -n "$COMMAND" ]; then
    # Run specific command
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand="cloudflared access ssh --hostname %h" "$USERNAME@$HOSTNAME" "$COMMAND"
else
    # Interactive session
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand="cloudflared access ssh --hostname %h" "$USERNAME@$HOSTNAME"
fi
