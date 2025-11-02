# Robust Queueing System Implementation

## Overview

Implement Redis Queue (RQ) system with hybrid approach that maintains 100% backward compatibility. All changes in new branch `feature/robust-queueing` with GitHub Actions for automatic Redis installation on thakii-03.

## Phase 1: Redis Installation Pipeline

### 1.1 Create Redis Installation Script

Create `thakii-worker-service/scripts/install_redis.sh`:

- Check if Redis is already installed
- Install Redis using Homebrew (Mac) or apt (Linux)
- Configure Redis with persistence (AOF enabled)
- Set up Redis as background service
- Test Redis connectivity
- Exit gracefully if installation fails

### 1.2 Update Worker Deployment Workflow

Modify `thakii-worker-service/.github/workflows/deploy-worker-service.yml`:

- Add step to run `install_redis.sh` before deployment
- Verify Redis is running before worker deployment
- Configure REDIS_HOST=localhost and REDIS_PORT=6379 in environment
- Add fallback to continue deployment if Redis fails

## Phase 2: Hybrid Queue Manager (Backend)

### 2.1 Create Hybrid Queue Manager

Create `thakii-backend-api/core/hybrid_queue_manager.py`:

- Feature flag: `ENABLE_REDIS_QUEUE` (default: false)
- Redis connection check on initialization
- When Redis disabled or unavailable: use existing HTTP trigger (no change)
- When Redis enabled: ONLY use Redis queue (no HTTP fallback)
- If Redis fails when enabled: return error to user (fail fast, no silent fallback)

### 2.2 Update Backend Requirements

Add to `thakii-backend-api/requirements.txt`:

- redis==5.0.1
- rq==1.15.1

### 2.3 Update Upload Endpoint

Modify `thakii-backend-api/app.py`:

- Import HybridQueueManager
- Replace direct `trigger_worker_processing()` call with `hybrid_queue.enqueue_video()`
- Keep all existing error handling
- No changes to response format

## Phase 3: Optional RQ Worker

### 3.1 Create RQ Worker Script

Create `thakii-worker-service/rq_worker_optional.py`:

- Import existing EnhancedWorker class (no modifications)
- Define `process_video_job()` function that calls existing worker logic
- Connect to Redis only if available
- Exit gracefully if Redis unavailable (allows legacy polling to continue)

### 3.2 Update Worker Requirements

Add to `thakii-worker-service/requirements.txt`:

- redis==5.0.1
- rq==1.15.1

### 3.3 Update Worker Startup

Modify `thakii-worker-service/.github/workflows/deploy-worker-service.yml`:

- Start legacy polling worker (line 59): `nohup python3 worker.py --process-all`
- Optionally start RQ worker (new): `nohup python3 rq_worker_optional.py`
- Both workers run simultaneously without conflict

## Phase 4: Database Schema (Optional)

### 4.1 Add Job Tracking Column

Create migration `thakii-backend-api/scripts/add_job_id_column.sql`:

```sql
ALTER TABLE video_tasks ADD COLUMN IF NOT EXISTS job_id VARCHAR(255) NULL;
CREATE INDEX IF NOT EXISTS idx_video_tasks_job_id ON video_tasks(job_id);
```

- Nullable column (backward compatible)
- Only populated when Redis is used

## Phase 5: Environment Configuration

### 5.1 Backend Environment Variables

Add to `thakii-backend-api/.env`:

```
ENABLE_REDIS_QUEUE=false  # Start disabled
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_ROLLOUT_PERCENT=0  # Gradual rollout
```

### 5.2 Worker Environment Variables

Add to `thakii-worker-service/.env`:

```
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Phase 6: Testing & Verification

### 6.1 Add Health Check Endpoint

Modify `thakii-backend-api/app.py` `/health` endpoint:

- Add Redis connectivity status
- Show queue statistics if Redis available
- Maintain backward compatibility

### 6.2 Create Test Script

Create `scripts/test_redis_queue.sh`:

- Test Redis connection
- Test enqueue/dequeue operations
- Verify fallback to legacy system
- Test both workers processing simultaneously

## Rollout Strategy

### Week 1: Deploy with Redis Disabled

- Merge to main with `ENABLE_REDIS_QUEUE=false`
- Verify no breaking changes
- Redis installed but not actively used

### Week 2: Test with Single User

- Enable for test user: `REDIS_TEST_USERS=ouday.khaled@gmail.com`
- Monitor both Redis queue and database polling
- Verify both systems working

### Week 3: Gradual Rollout

- `REDIS_ROLLOUT_PERCENT=10` (10% of users)
- Monitor for issues
- Automatic fallback if Redis fails

### Week 4: Full Rollout

- `REDIS_ROLLOUT_PERCENT=100`
- Both workers continue running
- Legacy system as safety net

## Files to Create/Modify

**New Files:**

- `thakii-worker-service/scripts/install_redis.sh`
- `thakii-backend-api/core/hybrid_queue_manager.py`
- `thakii-worker-service/rq_worker_optional.py`
- `thakii-backend-api/scripts/add_job_id_column.sql`
- `scripts/test_redis_queue.sh`

**Modified Files:**

- `thakii-backend-api/requirements.txt`
- `thakii-worker-service/requirements.txt`
- `thakii-backend-api/app.py` (upload endpoint only)
- `thakii-worker-service/.github/workflows/deploy-worker-service.yml`
- `thakii-backend-api/.env` (add Redis config)
- `thakii-worker-service/.env` (add Redis config)

## Safety Guarantees

1. Zero Breaking Changes: All existing code continues to work
2. No HTTP Fallback: When Redis enabled, system uses Redis ONLY - fails fast if Redis unavailable
3. Explicit Control: Feature flag determines which system to use (Redis or HTTP) - no automatic switching
4. Dual Workers: Both polling and RQ workers run simultaneously during migration
5. Feature Flag: Can disable Redis anytime by setting ENABLE_REDIS_QUEUE=false
6. Gradual Rollout: Test with small percentage first using REDIS_ROLLOUT_PERCENT
7. Manual Deployment: PR requires approval before production