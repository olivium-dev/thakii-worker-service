# Redis Queue Implementation

## Overview

This document describes the Redis Queue (RQ) implementation for the Thakii Worker Service. The implementation provides a robust queueing system with **zero breaking changes** and feature flag control.

## Architecture

### Components

1. **Queue Manager** (`core/queue_manager.py`)
   - Manages Redis connection and job enqueueing
   - Feature flag: `ENABLE_REDIS_QUEUE` (default: `false`)
   - Fail-fast behavior when enabled but unavailable

2. **RQ Worker** (`rq_worker.py`)
   - Processes jobs from Redis queue
   - Uses existing `EnhancedWorker` class
   - Runs as separate LaunchDaemon service

3. **Legacy Worker** (`worker.py`)
   - Continues to poll PostgreSQL database
   - Runs simultaneously with RQ worker
   - Unchanged functionality

4. **API Server** (`api_server.py`)
   - `/process-from-s3` endpoint updated to check Redis availability
   - When Redis enabled: enqueues to Redis queue
   - When Redis disabled: updates database for polling worker

## Configuration

### Environment Variables

```env
ENABLE_REDIS_QUEUE=false  # Feature flag (false = legacy mode, true = Redis mode)
REDIS_HOST=localhost      # Redis server host
REDIS_PORT=6379          # Redis server port
```

### Deployment

Redis is automatically installed via GitHub Actions:
- Script: `scripts/install_redis.sh`
- Checks if Redis already installed
- Installs via Homebrew (macOS) or apt (Linux)
- Starts Redis as background service

## Usage

### Current Behavior (ENABLE_REDIS_QUEUE=false)

1. Video uploaded via `/process-from-s3`
2. Task status updated to `in_queue` in PostgreSQL
3. Legacy polling worker picks up task
4. Video processed normally
5. **Zero change from previous behavior**

### Redis Mode (ENABLE_REDIS_QUEUE=true)

1. Video uploaded via `/process-from-s3`
2. Job enqueued to Redis with `job_id`
3. RQ worker picks up job from Redis queue
4. Video processed using `EnhancedWorker`
5. Task status updated in PostgreSQL

## Health Check

The `/api/v1/health/` endpoint now includes Redis status:

```json
{
  "service": "Thakii Lecture2PDF Service",
  "status": "healthy",
  "redis_queue": "disabled|available|unavailable",
  ...
}
```

## Safety Guarantees

1. **Zero Breaking Changes**: Legacy polling continues when Redis disabled
2. **No Fallback Logic**: Redis enabled = Redis required (fail fast)
3. **Dual Workers**: Both polling and RQ workers run simultaneously
4. **Feature Flag**: Instant rollback by setting `ENABLE_REDIS_QUEUE=false`
5. **Manual Control**: All changes require GitHub Actions deployment

## Rollout Plan

### Phase 1: Deploy with Redis Disabled (Current)
- `ENABLE_REDIS_QUEUE=false`
- Redis installed but not used
- All videos processed via legacy database polling
- Zero behavior change

### Phase 2: Enable for Testing
- Change `ENABLE_REDIS_QUEUE=true` in workflow
- Test with real videos
- Monitor both worker logs
- Verify queue processing

### Phase 3: Production Rollout
- Keep `ENABLE_REDIS_QUEUE=true`
- Both workers running (polling + RQ)
- Monitor queue depth and processing times
- Rollback available instantly if needed

## Database Schema

Optional migration for job tracking:

```sql
-- scripts/add_job_id_column.sql
ALTER TABLE video_tasks ADD COLUMN IF NOT EXISTS job_id VARCHAR(255) NULL;
CREATE INDEX IF NOT EXISTS idx_video_tasks_job_id ON video_tasks(job_id);
```

This column is nullable and backward compatible.

## Services

Three LaunchDaemon services now run:

1. **com.thakii.worker** - Legacy polling worker
2. **com.thakii.api_server** - API server
3. **com.thakii.rq_worker** - Redis queue worker (new)

All services are managed via GitHub Actions deployment.

## Monitoring

### Check Services Status
```bash
ps aux | grep -E "python.*(worker|api_server|rq_worker)" | grep -v grep
```

### Check Redis Status
```bash
redis-cli ping
```

### View Logs
```bash
tail -f ~/thakii-worker-service/logs/rq_worker.log
tail -f ~/thakii-worker-service/logs/rq_worker_error.log
```

## Troubleshooting

### RQ Worker Fails to Start
- **Expected if Redis disabled**: RQ worker exits gracefully
- **Check Redis**: `redis-cli ping`
- **Check environment**: Verify `ENABLE_REDIS_QUEUE` and `REDIS_HOST`

### Videos Not Processing
- **Check feature flag**: Verify `ENABLE_REDIS_QUEUE` setting
- **Check workers**: Both legacy and RQ workers should be running
- **Check Redis**: `redis-cli ping` and check queue depth

### Rollback
1. Update workflow: Set `ENABLE_REDIS_QUEUE=false`
2. Commit and push
3. GitHub Actions deploys with Redis disabled
4. System returns to legacy polling mode

## Files Modified/Created

### New Files
- `core/queue_manager.py` - Redis queue management
- `rq_worker.py` - RQ worker implementation
- `scripts/install_redis.sh` - Redis installation script
- `scripts/add_job_id_column.sql` - Database migration (optional)
- `REDIS_QUEUE_IMPLEMENTATION.md` - This documentation

### Modified Files
- `api_server.py` - Added queue manager integration and health check
- `requirements.txt` - Added redis==5.0.1 and rq==1.15.1
- `.github/workflows/deploy-thakii03-production.yml` - Added Redis installation and RQ worker setup

### Unchanged Files
- `worker.py` - No modifications (legacy polling continues)
- All other core processing files remain unchanged

