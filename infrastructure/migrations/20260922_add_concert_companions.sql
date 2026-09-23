-- Apply once to existing SongMatch PostgreSQL databases.
-- New local databases also receive these tables through infrastructure/schema.sql.

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name VARCHAR(50) NOT NULL,
    bio VARCHAR(280) NOT NULL DEFAULT '',
    city VARCHAR(80) NOT NULL,
    public_interests TEXT[] NOT NULL DEFAULT '{}',
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    music_affinity_consent BOOLEAN NOT NULL DEFAULT FALSE,
    adult_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    artist VARCHAR(160) NOT NULL,
    venue VARCHAR(160) NOT NULL,
    city VARCHAR(80) NOT NULL,
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'cancelled', 'completed')),
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concert_attendance_intents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    concert_id UUID NOT NULL REFERENCES concerts(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'withdrawn')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, concert_id)
);

CREATE TABLE IF NOT EXISTS companion_swipes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    concert_id UUID NOT NULL REFERENCES concerts(id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL CHECK (action IN ('pass', 'interested')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CHECK (actor_user_id <> target_user_id),
    UNIQUE (actor_user_id, target_user_id, concert_id)
);

CREATE TABLE IF NOT EXISTS companion_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    concert_id UUID NOT NULL REFERENCES concerts(id) ON DELETE CASCADE,
    user_low_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_high_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CHECK (user_low_id < user_high_id),
    UNIQUE (concert_id, user_low_id, user_high_id)
);

CREATE TABLE IF NOT EXISTS user_blocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    blocker_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CHECK (blocker_user_id <> blocked_user_id),
    UNIQUE (blocker_user_id, blocked_user_id)
);

CREATE TABLE IF NOT EXISTS user_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reporter_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason VARCHAR(40) NOT NULL,
    note VARCHAR(500) NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CHECK (reporter_user_id <> reported_user_id)
);

CREATE INDEX IF NOT EXISTS idx_concerts_starts_at ON concerts(starts_at);
CREATE INDEX IF NOT EXISTS idx_concert_attendance_active ON concert_attendance_intents(concert_id, status);
CREATE INDEX IF NOT EXISTS idx_user_reports_reported ON user_reports(reported_user_id, created_at);

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_concerts_updated_at BEFORE UPDATE ON concerts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_concert_attendance_updated_at BEFORE UPDATE ON concert_attendance_intents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_companion_swipes_updated_at BEFORE UPDATE ON companion_swipes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
