# 🔄 Backend-Worker Communication Architecture

## 🏗️ **COMPLETE SYSTEM ARCHITECTURE**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   React Web    │    │   AWS Lambda     │    │   Backend API       │
│   Frontend      │◄──►│   Router         │◄──►│   (Flask)           │
│   (Port 3000)   │    │   (Load Balancer)│    │   (Port 5001)       │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
         │                                                   │
         │              ┌──────────────────┐                │
         └─────────────►│   Firebase       │◄───────────────┘
                        │   (Auth + DB)    │
                        └──────────────────┘
                                 │
                        ┌──────────────────┐    ┌─────────────────────┐
                        │   Worker Service │    │   lecture2pdf       │
                        │   (Processing)   │◄──►│   External Engine   │
                        │   (Port 9000)    │    │   (PDF Generation)  │
                        └──────────────────┘    └─────────────────────┘
                                 │
                        ┌──────────────────┐
                        │   Amazon S3      │
                        │   (File Storage) │
                        └──────────────────┘
```

## 🔄 **COMMUNICATION FLOW**

### **1. Video Upload Flow:**
```python
# Backend API (app.py:242-252)
@app.route("/upload", methods=["POST"])
def upload_video():
    # 1. Upload video to S3
    # 2. Create task in Firestore
    # 3. Trigger worker via subprocess
    subprocess.Popen([
        sys.executable,
        "trigger_worker_clean.py",
        video_id
    ])
```

### **2. Worker Processing Flow:**
```python
# Worker Service (trigger_worker_clean.py)
def process_video(video_id: str, lecture2pdf_path: str):
    # 1. Get task from Firestore
    # 2. Download video from S3
    # 3. Generate subtitles (subtitle_generator.py)
    # 4. Generate PDF (main.py)
    # 5. Upload results to S3
    # 6. Update Firestore status
```

## 🌐 **CURRENT DEPLOYMENT ARCHITECTURE**

### **Backend API Server:**
- **Location**: Same server (`192.168.2.71`)
- **Port**: 5001
- **Domain**: `https://vps-71.fds-1.com/thakii-be/`
- **Function**: User interface, auth, video upload
- **Status**: ✅ Running (main backend service)

### **Worker Service:**
- **Location**: Same server (`192.168.2.71`) 
- **Port**: 9000
- **Domain**: `https://thakii-02.fanusdigital.site/thakii-worker/`
- **Function**: Video processing, PDF generation
- **Status**: ✅ Running (our deployed service)

### **Communication Method:**
```bash
# Backend triggers worker via local subprocess
/home/ec2-user/thakii-backend-api/trigger_worker_clean.py <video_id>

# Worker expects lecture2pdf engine at:
/home/ec2-user/thakii-backend-api/lecture2pdf-external/
```

## ⚠️ **CURRENT ISSUE IDENTIFIED:**

### **🔍 Problem:**
The **backend API** is trying to trigger a **local worker script** (`trigger_worker_clean.py`) that expects the **lecture2pdf engine** to be in the **backend repository**, but our **worker service** is in a **separate repository**.

### **🔧 Integration Paths:**

**Option 1: Shared Engine Path**
```bash
# Backend expects: /home/ec2-user/thakii-backend-api/lecture2pdf-external/
# Worker has: /home/ec2-user/thakii-worker-service/src/
# Solution: Create symlink or copy engine
```

**Option 2: HTTP Communication**
```python
# Backend calls worker via HTTP API
POST https://thakii-02.fanusdigital.site/thakii-worker/generate-pdf
{
    "video_id": "abc123",
    "s3_key": "videos/abc123.mp4"
}
```

**Option 3: Shared Firebase Queue**
```python
# Backend: Creates task in Firebase
# Worker: Polls Firebase for new tasks
# Current: Both already use Firebase!
```

## 🎯 **RECOMMENDED INTEGRATION:**

### **Use HTTP API Communication (Cleanest):**

**Backend API** → **Worker Service** via HTTPS:
```python
# In backend app.py, replace subprocess call:
import requests

# Instead of subprocess.Popen(["trigger_worker_clean.py", video_id])
response = requests.post(
    "https://thakii-02.fanusdigital.site/thakii-worker/generate-pdf",
    json={"video_id": video_id, "user_id": current_user["uid"]}
)
```

**Worker Service** already has the `/generate-pdf` endpoint ready!

## 📊 **CURRENT STATUS:**

✅ **Backend API**: Running on port 5001
✅ **Worker Service**: Running on port 9000  
✅ **HTTP Endpoints**: Both accessible via Cloudflare tunnel
✅ **Firebase**: Shared database for task management
✅ **S3**: Shared storage for files
❌ **Integration**: Backend still uses local subprocess (needs HTTP calls)

## 🚀 **NEXT STEPS:**

1. **Update backend** to use HTTP calls instead of subprocess
2. **Test end-to-end** video processing flow
3. **Verify** both services work together via Cloudflare tunnel

**The infrastructure is perfect - just need to update the communication method!** 🎉
