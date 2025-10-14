# AWS Credentials Fix for Backend 500 Error

## Problem Summary

The backend API was returning **500 Internal Server Error** on the `/upload` endpoint because:

1. **AWS credentials were NOT available to the systemd service**
2. **The systemd service did NOT load the `.env` file**
3. **S3 operations failed with `NoCredentialsError`**
4. **Upload requests failed before reaching the worker service**

## Root Cause Analysis

### The Systemd Environment Issue

The `thakii-backend.service` systemd service was configured like this:

```ini
[Service]
Environment=FLASK_ENV=production
Environment=FLASK_DEBUG=False
Environment=PORT=5001
Environment=GOOGLE_CLOUD_PROJECT=thakii-973e3
Environment=FIREBASE_PROJECT_ID=thakii-973e3
Environment=ALLOWED_ORIGINS=https://thakii-frontend.netlify.app
ExecStart=/home/ec2-user/thakii-backend-api/venv/bin/python3 /home/ec2-user/thakii-backend-api/app.py
```

**Problem**: AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`) were **missing**.

### Why `.env` File Wasn't Loaded

Systemd services run in an isolated environment and do **NOT** automatically load `.env` files. Even though the backend had AWS credentials in `/home/ec2-user/thakii-backend-api/.env`, they were never read by the service.

### The Error Chain

1. Frontend uploads video → POST `/upload`
2. Backend tries to upload to S3 → `s3_client.upload_fileobj()`
3. boto3 looks for AWS credentials → **NOT FOUND**
4. Raises `NoCredentialsError`
5. Backend returns **500 Internal Server Error**
6. Worker service never gets called

## The Solution

### Fix Script: `scripts/fix_backend_aws_credentials.sh`

This script:

1. ✅ Reads AWS credentials from backend's `.env` file
2. ✅ Updates systemd service file to include AWS environment variables
3. ✅ Reloads systemd daemon
4. ✅ Restarts backend service
5. ✅ Tests S3 connectivity to verify the fix

### GitHub Actions Workflow: `fix-backend-aws-credentials.yml`

A dedicated workflow that:

1. ✅ Connects to production server via SSH
2. ✅ Copies and runs the fix script
3. ✅ Verifies backend health and S3 connectivity
4. ✅ Provides comprehensive test results

## Usage

### Option 1: Run GitHub Actions Workflow (Recommended)

1. Go to **Actions** tab in GitHub
2. Select **"🔧 Fix Backend AWS Credentials"** workflow
3. Click **"Run workflow"**
4. Wait for completion
5. Review the deployment summary

### Option 2: Run Script Manually on Server

```bash
# SSH to server
ssh ec2-user@vps-71.fds-1.com

# Copy script to server
scp scripts/fix_backend_aws_credentials.sh ec2-user@vps-71.fds-1.com:/home/ec2-user/

# Run script
chmod +x fix_backend_aws_credentials.sh
bash fix_backend_aws_credentials.sh
```

## What Gets Fixed

### Before Fix

```ini
[Service]
# AWS credentials MISSING
Environment=FLASK_ENV=production
Environment=PORT=5001
...
```

Result: **500 errors on upload**

### After Fix

```ini
[Service]
Environment=FLASK_ENV=production
Environment=PORT=5001
Environment=AWS_ACCESS_KEY_ID=AKIA****************
Environment=AWS_SECRET_ACCESS_KEY=****************************************
Environment=AWS_DEFAULT_REGION=us-east-2
Environment=S3_BUCKET_NAME=thakii-video-storage-1753883631
...
```

Result: **✅ Upload works correctly**

## Verification Steps

After running the fix, verify:

### 1. Check Systemd Environment

```bash
sudo systemctl show thakii-backend.service --property=Environment
```

Should show:
```
Environment=... AWS_ACCESS_KEY_ID=AKIA**************** AWS_SECRET_ACCESS_KEY=******** AWS_DEFAULT_REGION=us-east-2 ...
```

### 2. Test Backend Health

```bash
curl https://thakii-02.fanusdigital.site/thakii-be/health
```

Should return:
```json
{"status": "ok"}
```

### 3. Test S3 Connectivity (on server)

```bash
cd /home/ec2-user/thakii-backend-api
source venv/bin/activate
python3 -c "
import boto3
s3 = boto3.client('s3')
print(s3.list_objects_v2(Bucket='thakii-video-storage-1753883631', MaxKeys=1))
print('✅ S3 working!')
"
```

### 4. Test Upload Endpoint

```bash
# Upload a test video from frontend
# Should succeed without 500 error
```

## Why This Wasn't Breaking Before

This issue only appeared after deploying the backend because:

1. The systemd service configuration was incomplete
2. Previous deployments may have manually configured AWS CLI (`aws configure`)
3. The service restart cleared any temporary environment variables
4. The `.env` file was never being loaded by systemd

## Impact on Worker Service

**The worker service had NO breaking changes.** The issue was entirely in the backend's infrastructure configuration. The worker service was waiting for jobs from Firestore, but jobs were never created because uploads failed at the backend level.

## Related Files

- **Backend Repository**: `https://github.com/olivium-dev/thakii-backend-api`
- **Backend systemd service**: `/etc/systemd/system/thakii-backend.service`
- **Backend .env file**: `/home/ec2-user/thakii-backend-api/.env`
- **Backend app**: `/home/ec2-user/thakii-backend-api/app.py`
- **S3 storage handler**: `/home/ec2-user/thakii-backend-api/core/s3_storage.py`

## Prevention

To prevent this in the future:

1. ✅ Always include AWS credentials in systemd service files
2. ✅ Use `EnvironmentFile=/path/to/.env` in systemd services
3. ✅ Test S3 connectivity after any service restart
4. ✅ Include infrastructure tests in deployment pipeline
5. ✅ Document required environment variables

## Success Criteria

After applying this fix:

- ✅ Backend `/upload` endpoint returns 200 (not 500)
- ✅ Videos upload successfully to S3
- ✅ Firestore tasks are created
- ✅ Worker service processes videos
- ✅ PDFs are generated and saved
- ✅ End-to-end pipeline works

## Support

If the fix doesn't work:

1. Check backend logs: `sudo journalctl -u thakii-backend.service -f`
2. Verify AWS credentials in `.env` file are correct
3. Test S3 access manually (see verification steps)
4. Ensure systemd daemon was reloaded: `sudo systemctl daemon-reload`
5. Restart service: `sudo systemctl restart thakii-backend.service`

