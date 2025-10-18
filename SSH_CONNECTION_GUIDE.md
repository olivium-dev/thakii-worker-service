# SSH Connection Guide for Thakii Worker Service

## Connection Methods

### Method 1: Recommended Approach (Using Cloudflare Tunnel)

```bash
ssh -i thakii-02-developer-key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand="cloudflared access ssh --hostname %h" ec2-user@vps-71.fds-1.com
```

### Method 2: Alternative Approach (Using localhost proxy)

```bash
# Start Cloudflare tunnel in background
cloudflared access ssh --hostname ssh-thakii-3.fanusdigital.site --url ssh://localhost:2222 &

# Wait for tunnel to establish
sleep 5

# Connect via SSH through the tunnel
ssh fanusdigital@localhost -p 2222
```

### Method 3: Using sshpass (For automated scripts)

```bash
# Using the GitHub Actions SSH password
sshpass -p "P@ssw0rd768" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null fanusdigital@localhost -p 2222
```

## Prerequisites

1. **Install Cloudflared**:
   ```bash
   # macOS
   brew install cloudflare/cloudflare/cloudflared
   
   # Linux
   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
   sudo dpkg -i cloudflared.deb
   
   # Windows (PowerShell)
   Invoke-WebRequest -Uri https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe -OutFile cloudflared.exe
   ```

2. **Authenticate Cloudflared** (if not already done):
   ```bash
   cloudflared login
   ```

3. **Ensure SSH Key Permissions**:
   ```bash
   chmod 600 thakii-02-developer-key
   ```

## Running Commands Remotely

### Execute a single command:

```bash
ssh -i thakii-02-developer-key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand="cloudflared access ssh --hostname %h" ec2-user@vps-71.fds-1.com "ls -la"
```

### Execute a script:

```bash
ssh -i thakii-02-developer-key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand="cloudflared access ssh --hostname %h" ec2-user@vps-71.fds-1.com 'bash -s' < ./scripts/install_whisper_dependencies.sh
```

## File Transfer

### Upload files:

```bash
scp -i thakii-02-developer-key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand="cloudflared access ssh --hostname %h" ./local_file.txt ec2-user@vps-71.fds-1.com:/path/on/server/
```

### Download files:

```bash
scp -i thakii-02-developer-key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand="cloudflared access ssh --hostname %h" ec2-user@vps-71.fds-1.com:/path/on/server/remote_file.txt ./
```

## Troubleshooting

1. **Connection Issues**:
   - Ensure Cloudflared is installed and authenticated
   - Check if the hostname is correctly configured in Cloudflare
   - Verify that the SSH key has correct permissions (chmod 600)

2. **Authentication Failures**:
   - Verify the username (ec2-user vs fanusdigital)
   - Check if the SSH key is correctly added to the server's authorized_keys
   - Try using password authentication with sshpass if key authentication fails

3. **Tunnel Issues**:
   - Check Cloudflare tunnel status: `cloudflared tunnel list`
   - Verify tunnel configuration in Cloudflare dashboard
   - Ensure the tunnel service is running on the server: `systemctl status cloudflared`

## Server Details

- **Hostname**: `golden-sample`
- **Local IP**: `192.168.2.71`
- **Public IP**: `81.204.248.240`
- **Public IPv6**: `2a02:a45d:3d16:0:be24:11ff:fee2:a3cc`
- **Users**: `ec2-user` (primary), `fanusdigital` (alternative)

## Notes

- The server is accessible via Cloudflare tunnel using the hostname `vps-71.fds-1.com`
- SSH access is configured through Cloudflare Access for secure remote access
- Both key-based and password-based authentication methods are available
- For automated scripts, consider using sshpass with the stored password