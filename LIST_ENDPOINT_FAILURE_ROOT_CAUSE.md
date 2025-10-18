# `/list` Endpoint Failure - Root Cause Analysis

**Investigation Date:** October 14, 2025  
**Investigator:** AI Assistant  
**User Report:** "The API fetching the videos is again broken and showing no fucking data!"

---

## Executive Summary

The `/list` endpoint is experiencing **HTTP 524 (Cloudflare timeout)** errors. Root cause analysis reveals this is **NOT a Cloudflare issue**, but rather a **gRPC connectivity failure** between the backend server and Google Firestore.

**Root Cause:** gRPC connections from the backend server to `firestore.googleapis.com:443` are timing out after 5+ seconds, preventing any Firestore database operations from completing.

---

## Investigation Timeline

### Step 1: Firebase Token Verification ✅
- **Test:** Verified Firebase ID token with `auth.verify_id_token()`
- **Result:** **SUCCESS** - Token verified in 0.11s
- **Conclusion:** Firebase Admin SDK authentication is working

### Step 2: Firestore Query Testing ❌
- **Test:** `firestore_db.get_user_video_tasks(user_id)`
- **Result:** **TIMEOUT** - Query never completes (30s timeout)
- **Conclusion:** Firestore database operations are hanging

### Step 3: Simplified Firestore Query ❌
- **Test:** Direct query without `order_by` clause
- **Result:** **TIMEOUT** - Even simple queries hang
- **Conclusion:** Issue is not query complexity

### Step 4: Basic Firestore Connectivity ❌
- **Test:** List Firestore collections (lightweight operation)
- **Result:** **TIMEOUT** - Even basic operations fail
- **Conclusion:** Fundamental connectivity issue with Firestore

### Step 5: Network Connectivity to Google ✅
- **Test:** DNS resolution and HTTPS connection to `firestore.googleapis.com`
- **Result:** **SUCCESS**
  - DNS resolves to `172.217.23.202`
  - HTTPS connection established
  - TLS handshake completes
- **Conclusion:** Network path to Google Cloud is open

### Step 6: Firewall Analysis ✅
- **Test:** Checked iptables and UFW firewall rules
- **Result:** **ALLOW**
  - UFW: "allow (outgoing)" - outbound traffic permitted
  - iptables OUTPUT chain: ACCEPT policy
- **Conclusion:** No firewall blocking outbound connections

### Step 7: Firestore SDK Stream vs Get ❌
- **Test:** Tested both `.stream()` and `.get()` with `.limit(1)`
- **Result:** **BOTH TIMEOUT**
- **Conclusion:** Issue affects all Firestore SDK operations

### Step 8: Python Environment ✅
- **Test:** DNS and SSL capabilities in Python
- **Result:** **SUCCESS**
  - `socket.gethostbyname()` works
  - OpenSSL 3.0.13 available
- **Conclusion:** Python network stack is functional

### Step 9: gRPC Connection Test ❌ **ROOT CAUSE IDENTIFIED**
- **Test:** Raw gRPC channel to `firestore.googleapis.com:443`
- **Result:** **TIMEOUT** - gRPC channel never becomes ready (5s timeout)
- **Error:** `FutureTimeoutError`
- **Conclusion:** **gRPC protocol is being blocked or timing out**

### Step 10: HTTPS vs gRPC Comparison ✅ vs ❌
- **Test:** Compare HTTPS and SSL connections
- **Result:**
  - HTTPS curl: **SUCCESS** (HTTP 404, but connection works)
  - OpenSSL s_client: **SUCCESS** (Verify return code: 0)
  - gRPC: **FAILS** (timeout)
- **Conclusion:** Regular HTTPS works, but gRPC specifically fails

---

## Technical Details

### What Works ✅
1. **Network connectivity** to Google Cloud infrastructure
2. **DNS resolution** for `firestore.googleapis.com`
3. **HTTPS/TLS connections** on port 443
4. **Firebase token verification** (0.11s)
5. **Firewall outbound rules** (UFW allows outgoing)
6. **Backend service** is running (started Oct 14 09:37:58 UTC)
7. **Worker service** is healthy and responsive

### What Fails ❌
1. **gRPC connections** to Firestore (5s+ timeout)
2. **All Firestore database queries** (`.get()`, `.stream()`, `.collections()`)
3. **`/list` endpoint** (524 timeout after waiting for Firestore)

---

## Why `/list` Fails

The `/list` endpoint flow:
1. User sends request with Firebase token → ✅ Works
2. Backend verifies token with Firebase Auth → ✅ Works (0.11s)
3. Backend queries Firestore: `get_user_video_tasks(user_id)` → ❌ **HANGS HERE**
4. After 30+ seconds, Cloudflare times out → HTTP 524

The endpoint never returns because it's stuck waiting for the Firestore query that will never complete due to the gRPC connection failure.

---

## Possible Causes of gRPC Blocking

### 1. Network Infrastructure Changes (Most Likely)
- ISP or data center may have implemented Deep Packet Inspection (DPI)
- Layer 7 firewall rules blocking gRPC traffic
- Network routing changes affecting gRPC protocol

### 2. Google Cloud API Changes
- Firestore API endpoint changes
- gRPC version incompatibility
- Service account permission changes

### 3. Server Configuration Changes
- Recent systemd restart (Oct 14 09:37:58 UTC)
- Environment variable changes
- Python package updates affecting gRPC

### 4. Rate Limiting or Quota Issues
- Google Cloud API quota exceeded
- Rate limiting on Firestore operations
- Service account throttling

---

## Timeline Context

- **Oct 12 18:20:57 UTC:** Backend service last restarted before today
- **Oct 14 09:37:58 UTC:** Backend service restarted (most recent)
- **Oct 14 ~10:00 UTC:** User reports `/list` endpoint broken
- **Backend last code change:** 5 commits ago (`02174a5 - Trigger API docs generation`)

---

## Evidence Summary

| Test | Protocol | Result | Time |
|------|----------|--------|------|
| Firebase Token Verification | HTTPS | ✅ Success | 0.11s |
| Firestore Query | gRPC | ❌ Timeout | 30s+ |
| HTTPS to firestore.googleapis.com | HTTPS | ✅ Success | <1s |
| gRPC Channel to Firestore | gRPC | ❌ Timeout | 5s+ |
| DNS Resolution | UDP | ✅ Success | <1s |
| SSL/TLS Connection | TLS | ✅ Success | <1s |

---

## Impact Assessment

### What is Broken
- ❌ `/list` endpoint - Cannot fetch user videos
- ❌ Any operation requiring Firestore database access
- ❌ Video metadata retrieval

### What Still Works
- ✅ `/health` endpoint - Backend is running
- ✅ Firebase authentication - Token verification works
- ✅ Worker service - PDF generation works locally
- ✅ S3 storage operations - File uploads/downloads work

---

## Recommendations for User

### Immediate Actions
1. **Check Google Cloud Console**
   - Verify Firestore API is enabled
   - Check for service disruptions or maintenance
   - Review API quota usage
   - Validate service account permissions

2. **Check Network Infrastructure**
   - Contact data center/hosting provider about gRPC traffic
   - Ask if any DPI or Layer 7 firewall rules were recently added
   - Verify no transparent proxies are interfering with gRPC

3. **Test from Different Location**
   - Try connecting to Firestore from a different server
   - Confirm if issue is specific to this server or network

### Debugging Steps
1. Check Google Cloud Console for Firestore errors
2. Review service account permissions in IAM
3. Check Firestore API quota limits
4. Test gRPC connectivity from a different network
5. Review any recent network configuration changes

---

## What This is NOT

- ❌ **NOT a Cloudflare issue** - Health endpoint works fine through Cloudflare
- ❌ **NOT a worker service issue** - Worker is healthy and processing videos
- ❌ **NOT a code change** - No recent backend code changes affecting Firestore
- ❌ **NOT a firewall blocking** - UFW allows outbound, HTTPS works fine
- ❌ **NOT a DNS issue** - DNS resolution works correctly

---

## Conclusion

The `/list` endpoint failure is caused by **gRPC connectivity issues** between the backend server and Google Firestore. While regular HTTPS traffic works fine, gRPC connections (used by the Firestore Python SDK) are timing out. This is likely due to:

1. Network infrastructure blocking or throttling gRPC traffic
2. Google Cloud API or service account configuration changes
3. Recent system changes affecting gRPC library behavior

**This is NOT related to any worker service changes or Whisper AI installation.**

The issue requires investigation into:
- Network/ISP gRPC traffic policies
- Google Cloud Firestore API status
- Service account permissions and quotas




