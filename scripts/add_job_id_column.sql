-- Add job_id column for Redis job tracking (nullable for backward compatibility)
ALTER TABLE video_tasks ADD COLUMN IF NOT EXISTS job_id VARCHAR(255) NULL;
CREATE INDEX IF NOT EXISTS idx_video_tasks_job_id ON video_tasks(job_id);

-- Update comment
COMMENT ON COLUMN video_tasks.job_id IS 'Redis RQ job ID (null for legacy database polling)';

