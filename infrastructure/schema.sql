-- SoundMatch Database Schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Auth tokens table
CREATE TABLE IF NOT EXISTS auth_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on token for faster lookups
CREATE INDEX IF NOT EXISTS idx_auth_tokens_token ON auth_tokens(token);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id ON auth_tokens(user_id);

-- Playlists table
CREATE TABLE IF NOT EXISTS playlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    tracks TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on user_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_playlists_user_id ON playlists(user_id);

-- Recommendation history table
CREATE TABLE IF NOT EXISTS recommendation_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    seed_tracks TEXT[] NOT NULL DEFAULT '{}',
    recommendations JSONB,
    algorithm VARCHAR(50),
    preferences JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on user_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_recommendation_history_user_id ON recommendation_history(user_id);

-- Cached audio features table
CREATE TABLE IF NOT EXISTS track_audio_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spotify_id VARCHAR(64) UNIQUE NOT NULL,
    isrc VARCHAR(32),
    provider VARCHAR(50) NOT NULL DEFAULT 'librosa',
    status VARCHAR(50) NOT NULL DEFAULT 'finished',
    features JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_track_audio_features_spotify_id ON track_audio_features(spotify_id);
CREATE INDEX IF NOT EXISTS idx_track_audio_features_isrc ON track_audio_features(isrc);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to automatically update updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_playlists_updated_at BEFORE UPDATE ON playlists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_track_audio_features_updated_at BEFORE UPDATE ON track_audio_features
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Cleanup function for expired tokens
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM auth_tokens WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Spotify OAuth tokens (optional, for users who connect their Spotify account)
ALTER TABLE users ADD COLUMN IF NOT EXISTS spotify_access_token TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS spotify_refresh_token TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS spotify_token_expires_at TIMESTAMP WITH TIME ZONE;

-- Listening history: persisted Spotify "recently played" events, one row per play.
-- Partitioned by HASH(user_id) so per-user reads only ever scan one partition.
-- Populated by the daily sync job (app/jobs/sync_recently_played.py) and,
-- opportunistically, by the live /recently-played endpoint.
CREATE TABLE IF NOT EXISTS listening_history (
    id UUID DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    spotify_track_id VARCHAR(64) NOT NULL,
    track_name VARCHAR(500) NOT NULL,
    artist VARCHAR(500) NOT NULL,
    album VARCHAR(500),
    album_image TEXT,
    external_url TEXT,
    genres TEXT[] NOT NULL DEFAULT '{}',
    played_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, id)
) PARTITION BY HASH (user_id);

CREATE TABLE IF NOT EXISTS listening_history_p0 PARTITION OF listening_history FOR VALUES WITH (MODULUS 8, REMAINDER 0);
CREATE TABLE IF NOT EXISTS listening_history_p1 PARTITION OF listening_history FOR VALUES WITH (MODULUS 8, REMAINDER 1);
CREATE TABLE IF NOT EXISTS listening_history_p2 PARTITION OF listening_history FOR VALUES WITH (MODULUS 8, REMAINDER 2);
CREATE TABLE IF NOT EXISTS listening_history_p3 PARTITION OF listening_history FOR VALUES WITH (MODULUS 8, REMAINDER 3);
CREATE TABLE IF NOT EXISTS listening_history_p4 PARTITION OF listening_history FOR VALUES WITH (MODULUS 8, REMAINDER 4);
CREATE TABLE IF NOT EXISTS listening_history_p5 PARTITION OF listening_history FOR VALUES WITH (MODULUS 8, REMAINDER 5);
CREATE TABLE IF NOT EXISTS listening_history_p6 PARTITION OF listening_history FOR VALUES WITH (MODULUS 8, REMAINDER 6);
CREATE TABLE IF NOT EXISTS listening_history_p7 PARTITION OF listening_history FOR VALUES WITH (MODULUS 8, REMAINDER 7);

-- Dedup key: reused by the sync job's ON CONFLICT DO NOTHING upsert so re-running
-- the job over an overlapping window never creates duplicate plays.
CREATE UNIQUE INDEX IF NOT EXISTS idx_listening_history_dedup
    ON listening_history (user_id, spotify_track_id, played_at);
-- Serves "last N days for this user" reads (partition pruning + range scan on played_at).
CREATE INDEX IF NOT EXISTS idx_listening_history_user_played_at
    ON listening_history (user_id, played_at DESC);

-- Comments for documentation
COMMENT ON TABLE users IS 'User accounts';
COMMENT ON TABLE auth_tokens IS 'Authentication tokens for API access';
COMMENT ON TABLE playlists IS 'User-created playlists';
COMMENT ON TABLE recommendation_history IS 'History of recommendation requests and results';
COMMENT ON TABLE track_audio_features IS 'Cached audio feature payloads by Spotify track ID';
COMMENT ON TABLE listening_history IS 'Per-user Spotify play history, partitioned by user_id, populated by the daily sync job';
