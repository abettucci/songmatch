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

-- Comments for documentation
COMMENT ON TABLE users IS 'User accounts';
COMMENT ON TABLE auth_tokens IS 'Authentication tokens for API access';
COMMENT ON TABLE playlists IS 'User-created playlists';
COMMENT ON TABLE recommendation_history IS 'History of recommendation requests and results';
COMMENT ON TABLE track_audio_features IS 'Cached audio feature payloads by Spotify track ID';
