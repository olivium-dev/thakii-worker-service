# Whisper AI Installation Pipeline - Deployment Guide

## Overview

This pipeline installs Whisper AI and all required dependencies on the production server, with automated validation and end-to-end testing to ensure real transcription is working.

## Problem Solved

**Before**: Production was generating fake PDFs with mock content like "Welcome to today's comprehensive lecture session..."

**After**: Production generates real PDFs with actual transcribed speech from videos using Whisper AI.

## Components Created

### 1. GitHub Actions Workflow
**File**: `.github/workflows/deploy-whisper-dependencies.yml`

**What it does**:
- Installs Whisper AI, PyTorch, and ffmpeg on production server
- Validates installation at multiple checkpoints (10s, 30s, 90s, 3min intervals)
- Automatically fixes common issues (up to 3 attempts)
- Runs end-to-end test with real video
- Validates PDF output contains real transcription
- Rolls back on failure with detailed logs

**Monitoring checkpoints**:
- T+10s: Basic import checks
- T+30s: Model loading + ffmpeg
- T+90s: Test transcription
- T+3min: Service stability (3 checks)
- T+12min: End-to-end test
- T+15min: Final validation

### 2. Installation Script
**File**: `scripts/install_whisper_dependencies.sh`

**What it does**:
- Auto-detects OS (Amazon Linux, Ubuntu, etc.)
- Installs ffmpeg via yum/dnf/apt
- Installs Python dependencies (torch, whisper)
- Downloads Whisper medium model (~1.5GB)
- Verifies all installations

### 3. Validation Script
**File**: `scripts/validate_whisper_installation.sh`

**What it does**:
- Checks Python module imports (whisper, torch)
- Loads Whisper medium model
- Verifies ffmpeg availability
- Runs test transcription
- Checks worker service status

**Exit codes**:
- 0 = All checks passed
- 1 = Dependency import failed
- 2 = Model loading failed
- 3 = ffmpeg missing
- 4 = Transcription test failed

### 4. Auto-Fix Script
**File**: `scripts/auto_fix_whisper_issues.sh`

**What it does**:
- Analyzes validation output to detect issue type
- Applies targeted fixes:
  - Missing modules → Reinstall requirements
  - ffmpeg missing → Reinstall system package
  - Model failed → Clear cache and redownload
  - Permission issues → Fix venv ownership
- Returns success/failure status

### 5. PDF Validator
**File**: `scripts/compare_pdf_content.py`

**What it does**:
- Analyzes PDF page count (fake content = 2 pages, real = variable)
- Checks file size (fake < 300KB, real > 500KB)
- Detects fake content markers ("Welcome to today's...")
- Verifies real transcription patterns
- Outputs JSON report

### 6. End-to-End Test
**File**: `scripts/e2e_test_video_processing.sh`

**What it does**:
- Uploads test video to backend API
- Monitors processing status
- Downloads generated PDF
- Validates PDF content
- Confirms real transcription is present

## How to Deploy

### Prerequisites

**GitHub Secrets** (already configured):
- `thakii_ssh_private_key` - SSH key for server access
- `FIREBASE_TEST_TOKEN` - Valid Firebase auth token for testing

### Step 1: Trigger Workflow

**Manual trigger** (recommended for first deployment):
1. Go to: https://github.com/olivium-dev/thakii-worker-service/actions/workflows/deploy-whisper-dependencies.yml
2. Click "Run workflow"
3. Select "production"
4. Click "Run workflow"

**Automatic trigger**:
- Push to branch triggers automatic deployment

### Step 2: Monitor Progress

Watch the workflow in GitHub Actions. It will:
1. Install dependencies (~5 min)
2. Validate at intervals (~10 min)
3. Run E2E test (~10 min)
4. Final validation (~2 min)

**Total time**: ~30 minutes (without retries)

### Step 3: Review Results

**Success indicators**:
- ✅ All validation checkpoints pass
- ✅ E2E test uploads and processes video
- ✅ PDF contains real transcription
- ✅ No errors in worker logs

**Failure handling**:
- Auto-fix attempts up to 3 times
- Detailed logs captured
- Service remains in previous state if rollback occurs

## Validation Checklist

After deployment, verify:

1. **Import checks**:
   ```bash
   ssh ec2-user@vps-71.fds-1.com 'cd /home/ec2-user/thakii-worker-service && source venv/bin/activate && python3 -c "import whisper; print(\"✅ Whisper OK\")"'
   ```

2. **ffmpeg availability**:
   ```bash
   ssh ec2-user@vps-71.fds-1.com 'ffmpeg -version | head -1'
   ```

3. **Worker service**:
   ```bash
   ssh ec2-user@vps-71.fds-1.com 'sudo systemctl status thakii-worker.service'
   ```

4. **Test upload** (via frontend):
   - Upload a video
   - Wait for processing
   - Download PDF
   - Verify it contains real transcription, not "Welcome to today's..."

## Success Criteria

Pipeline passes when ALL conditions met:
1. ✅ `import whisper` succeeds
2. ✅ `import torch` succeeds
3. ✅ `ffmpeg -version` succeeds
4. ✅ Whisper medium model loads
5. ✅ Test transcription produces words
6. ✅ thakii-worker.service is active
7. ✅ E2E test uploads video successfully
8. ✅ PDF generated has >2 pages
9. ✅ PDF contains real transcribed text
10. ✅ No errors in worker logs

## Troubleshooting

### Issue: Import errors after installation
**Solution**: Auto-fix will reinstall requirements. Check venv activation.

### Issue: ffmpeg not found
**Solution**: Auto-fix will reinstall system package. Check package manager.

### Issue: Model download fails
**Solution**: Auto-fix will clear cache and retry. Check disk space and network.

### Issue: E2E test times out
**Solution**: Check worker logs for processing errors. Verify Firebase connectivity.

### Issue: PDF still shows fake content
**Solution**: Verify Whisper is being called in `src/main.py`. Check worker subprocess output.

## Files Modified

- `requirements.txt` - Added Whisper dependencies
- `.github/workflows/deploy-whisper-dependencies.yml` - New workflow
- `scripts/install_whisper_dependencies.sh` - New script
- `scripts/validate_whisper_installation.sh` - New script
- `scripts/auto_fix_whisper_issues.sh` - New script
- `scripts/compare_pdf_content.py` - New script
- `scripts/e2e_test_video_processing.sh` - New script

## Dependencies Added

```
openai-whisper==20231117
torch==2.1.0
torchvision==0.16.0
torchaudio==2.1.0
numpy<2
```

Plus system package:
- `ffmpeg` (via yum/dnf/apt)

## Server Configuration

- **Server**: vps-71.fds-1.com
- **User**: ec2-user
- **Worker path**: /home/ec2-user/thakii-worker-service
- **Service**: thakii-worker.service
- **Venv**: /home/ec2-user/thakii-worker-service/venv

## Notes

- Pipeline uses Cloudflare Access SSH proxy for secure connections
- Medium model is ~1.5GB, download may take 5-10 minutes
- Auto-fix attempts are limited to 3 per checkpoint
- E2E test requires valid Firebase token
- PDF validation checks for both fake markers and real content
- All scripts use `set -euo pipefail` for strict error handling

## Next Steps

After successful deployment:
1. Monitor first few real video uploads
2. Compare PDF quality with expected output
3. Check worker logs for any Whisper errors
4. Verify processing times are acceptable
5. Consider adjusting Whisper model size if needed (base/small/medium/large)

## Support

If deployment fails after all auto-fix attempts:
1. Review workflow logs in GitHub Actions
2. Check server logs: `sudo journalctl -u thakii-worker.service -n 200`
3. Manually run validation: `bash /home/ec2-user/validate_whisper_installation.sh`
4. Contact DevOps team with error logs

---

**Branch**: `feature/whisper-ai-installation-pipeline`
**Status**: Ready to deploy
**Last Updated**: October 14, 2025

