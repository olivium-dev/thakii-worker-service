# Deployment Setup for Enhanced Worker

## 🔧 CREDENTIALS SETUP

### 1. Firebase Service Account
```bash
# Download service account JSON from Firebase Console
# Place it in secure location
export FIREBASE_SERVICE_ACCOUNT_KEY="/path/to/firebase-service-account.json"
```

### 2. AWS Credentials
```bash
# Set AWS credentials for S3 access
export AWS_ACCESS_KEY_ID="AKIA_YOUR_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="your_secret_access_key_here"
export AWS_DEFAULT_REGION="us-east-2"
export S3_BUCKET_NAME="thakii-video-storage-1753883631"
```

### 3. Environment File (.env)
```bash
# Copy example and configure
cp .env.example .env
# Edit .env with your actual credentials
```

## 🧪 VALIDATION TESTS

### Test 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Test 2: Test Firebase Connection
```bash
python3 -c "from core.firestore_integration import firestore_client; print('Firebase:', firestore_client.is_available())"
```

### Test 3: Test S3 Connection
```bash
python3 -c "from core.s3_integration import s3_client; print('S3:', s3_client.is_available())"
```

### Test 4: Test PDF Generation
```bash
python3 -m src.main test.mp4 -S -o validation.pdf
ls -la validation.pdf  # Should be ~232KB
```

### Test 5: Test Enhanced Worker
```bash
python3 worker.py test-video-id-123
```

## 🚀 DEPLOYMENT

### Production Deployment:
```bash
# 1. Clone repository
git clone https://github.com/olivium-dev/thakii-worker-service.git
cd thakii-worker-service

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials (see above)

# 4. Test connections
python3 test_firebase_integration.py

# 5. Run worker
python3 worker.py  # Polling mode
```

## ✅ SUCCESS CRITERIA

- ✅ Firebase connection established
- ✅ S3 connection established  
- ✅ Superior PDF generation working (232KB files)
- ✅ Worker polls Firestore for tasks
- ✅ Worker updates task status in real-time
- ✅ End-to-end video processing functional
