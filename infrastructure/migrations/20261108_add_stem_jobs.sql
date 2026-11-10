-- Short-lived AI Stem Mixer jobs. Audio artifacts are kept in a private S3 bucket.
CREATE TABLE IF NOT EXISTS stem_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type VARCHAR(20) NOT NULL,
    source_key TEXT,
    status_key TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    output_keys JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code VARCHAR(40),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_stem_jobs_source_type CHECK (source_type IN ('spotify', 'upload')),
    CONSTRAINT ck_stem_jobs_status CHECK (status IN ('queued', 'processing', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_stem_jobs_user_created ON stem_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stem_jobs_expiry ON stem_jobs(expires_at);
