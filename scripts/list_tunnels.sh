#!/bin/bash
# List all Cloudflare tunnels on the system

echo "=== Cloudflared Version ==="
cloudflared --version

echo ""
echo "=== Cloudflare Tunnels ==="
cloudflared tunnel list

echo ""
echo "=== Running Cloudflared Processes ==="
ps aux | grep cloudflared | grep -v grep

echo ""
echo "=== Cloudflared Config Files ==="
find ~/.cloudflared -type f | sort

echo ""
echo "=== Network Connections ==="
lsof -i | grep cloudflared || echo "No active connections found"
