# 🌐 Cloudflare & Server Access Guide

## 🔑 **Authentication Credentials**

### **Cloudflare API Access:**
```bash
CLOUDFLARE_API_KEY="b6172b23e11b421f38069b4931bdf80bd6ff7"
CLOUDFLARE_EMAIL="ouday.khaled@gmail.com"
CLOUDFLARE_ACCOUNT_ID="58198ae51392a2cc2d391867fb65da7e"
```

### **Server SSH Access:**
```bash
# Via Cloudflare Tunnel (Primary)
ssh -i thakii-02-developer-key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand="cloudflared access ssh --hostname %h" ec2-user@vps-71.fds-1.com

# Via Local Network (Backup)
ssh -i thakii-02-developer-key -o StrictHostKeyChecking=no ec2-user@192.168.2.71
```

### **Namecheap API Access:**
```bash
NAMECHEAP_USERNAME="oudaykhaled"
NAMECHEAP_API_KEY="313475054fc4425f87de865c3e087d6f"
NAMECHEAP_CLIENT_IP="81.204.248.240"
```

## 🌐 **Domain Configuration**

### **Active Domains:**
- **`fanusdigital.site`** (Namecheap → Cloudflare DNS)
- **`fds-1.com`** (Cloudflare managed)
- **`fds-2.space`** (Namecheap → Cloudflare DNS)

### **Current DNS Setup:**
```
thakii-02.fanusdigital.site → 5dc58394-acd4-42d6-8b4e-911903d86374.cfargotunnel.com (CNAME)
vps-71.fds-1.com → 5dc58394-acd4-42d6-8b4e-911903d86374.cfargotunnel.com (CNAME)
```

## 🚇 **Cloudflare Tunnel Configuration**

### **Tunnel Details:**
- **Name**: `ssh-thakii-02`
- **ID**: `5dc58394-acd4-42d6-8b4e-911903d86374`
- **Account**: `58198ae51392a2cc2d391867fb65da7e`

### **Current Ingress Rules:**
```yaml
ingress:
  # HTTP routing
  - hostname: thakii-02.fanusdigital.site
    service: http://localhost:80
    originRequest:
      httpHostHeader: thakii-02.fanusdigital.site
  - hostname: vps-71.fds-1.com
    service: http://localhost:80
    originRequest:
      httpHostHeader: vps-71.fds-1.com
  
  # SSH routing (preserved)
  - hostname: thakii-02.fds-1.com
    service: ssh://192.168.2.71:22
  - hostname: ahmad.fds-1.com
    service: ssh://192.168.2.70:22
  - hostname: dev-creamat.vps.fds-1.com
    service: ssh://192.168.2.69:22
  - hostname: prod-db-rahma.fds-1.com
    service: ssh://192.168.2.73:22
  - hostname: vps-73.fds-1.com
    service: ssh://192.168.2.73:22
    
  # Catch-all
  - service: http_status:404
```

## 🖥️ **Server Configuration**

### **Server Details:**
- **Hostname**: `golden-sample`
- **Local IP**: `192.168.2.71`
- **Public IP**: `81.204.248.240`
- **Public IPv6**: `2a02:a45d:3d16:0:be24:11ff:fee2:a3cc`

### **Running Services:**
- **API Server (Worker)**: Port 9000 (`thakii-api.service`)
- **Backend Service**: Port 5001 (main backend)
- **NGINX**: Ports 80, 443 (reverse proxy)
- **Cloudflare Tunnel**: `cloudflared.service`

### **NGINX Routing:**
```nginx
server_name: thakii-02.fanusdigital.site vps-71.fds-1.com

# Worker Service
location /thakii-worker/ → http://127.0.0.1:9000

# Backend Service  
location /thakii-be/ → http://127.0.0.1:5001

# Default (Backend)
location / → http://127.0.0.1:5001
```

## 🌐 **API Endpoints**

### **Worker Service APIs:**
```
Base URL: https://vps-71.fds-1.com/thakii-worker/

✅ Health: /health
✅ List: /list (6 videos from Firebase)
✅ Status: /status/{video_id}
✅ Generate: /generate-pdf
✅ Download: /download/{video_id}.pdf
```

### **Backend Service APIs:**
```
Base URL: https://vps-71.fds-1.com/thakii-be/

✅ Health: /health (Firestore + S3)
✅ All backend endpoints available
```

## 🔧 **Cloudflare API Management**

### **DNS Record Management:**
```python
# Update DNS A record
headers = {
    'X-Auth-Key': 'b6172b23e11b421f38069b4931bdf80bd6ff7',
    'X-Auth-Email': 'ouday.khaled@gmail.com',
    'Content-Type': 'application/json'
}

# Get Zone ID
GET https://api.cloudflare.com/client/v4/zones?name={domain}

# Update DNS record
PUT https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}
```

### **Tunnel Configuration Management:**
```python
# Get tunnel config
GET https://api.cloudflare.com/client/v4/accounts/58198ae51392a2cc2d391867fb65da7e/cfd_tunnel/5dc58394-acd4-42d6-8b4e-911903d86374/configurations

# Update tunnel config
PUT https://api.cloudflare.com/client/v4/accounts/58198ae51392a2cc2d391867fb65da7e/cfd_tunnel/5dc58394-acd4-42d6-8b4e-911903d86374/configurations
```

## 🚀 **GitHub Actions Integration**

### **Available Secrets:**
- `CLOUDFLARE_SERVICE_TOKEN` (for tunnel access)
- `SSH_PRIVATE_KEY` (thakii-02-developer-key)
- `SSH_PASSWORD` (P@ssw0rd768)
- `FIREBASE_SERVICE_ACCOUNT` (service account JSON)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`

### **Deployment Workflow:**
- **File**: `.github/workflows/deploy-worker-service.yml`
- **Trigger**: Push to main branch
- **SSH Method**: Private key authentication via Cloudflare tunnel
- **Services**: Deploys both worker (port 9000) and backend (port 5001)

## 📊 **Current Status**

### ✅ **Working Perfectly:**
- **SSH Access**: All domains via Cloudflare tunnel
- **HTTP Access**: Both worker and backend via tunnel
- **API Integration**: Firebase + S3 + GitHub Actions
- **DNS Management**: Fully automated via Cloudflare API
- **Tunnel Management**: Fully automated via Cloudflare API

### 🎯 **Key Success Factors:**
1. **Dual Authentication**: API Key + Email for full Cloudflare access
2. **Tunnel + NGINX**: Perfect combination for routing flexibility
3. **Preserved SSH**: All existing SSH access maintained
4. **API Automation**: Complete infrastructure as code

---

**🎉 This configuration provides bulletproof access to both Cloudflare and the server with full API automation capabilities!**

## ✅ **FINAL WORKING CONFIGURATION:**

### **SSH Access (Restored):**
- `vps-71.fds-1.com` → SSH via Cloudflare tunnel ✅

### **HTTP Access (Working):**
- `https://thakii-02.fanusdigital.site/thakii-worker/` → Worker Service ✅
- `https://thakii-02.fanusdigital.site/thakii-be/` → Backend Service ✅

### **Deployment Status:**
- GitHub Actions: Ready for deployment
- SSH Access: Fully functional
- API Endpoints: All working via tunnel
