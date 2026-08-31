-- Migration: Add multi-user support
-- Date: 2026-08-30
-- Purpose: Introduce a users table + user_id FK on streaming_history so the DB can
--          hold multiple people's Spotify histories without cross-contamination.
--          Backfills all existing rows to a single primary user ('tanmay').
-- Applies after: 001_create_streaming_table.sql, 002_helper_functions.sql
-- Run: psql "<conn>" -v ON_ERROR_STOP=1 -f 003_add_multi_user_support.sql
--      (or paste into the Supabase SQL Editor)
--
-- NOTE: run 004_user_scoped_functions.sql immediately after this file.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. users table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username     TEXT UNIQUE NOT NULL,
    display_name TEXT,
    is_primary   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_username CHECK (char_length(username) >= 2)
);

-- Only one row may have is_primary = TRUE
CREATE UNIQUE INDEX IF NOT EXISTS one_primary_user
    ON users(is_primary) WHERE is_primary;

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

COMMENT ON TABLE users IS 'Owners of streaming history (primary user + imported friends)';
COMMENT ON COLUMN users.is_primary IS 'TRUE for the single app owner whose data predates multi-user support';

-- ---------------------------------------------------------------------------
-- 2. Seed the primary user and add user_id to streaming_history
-- ---------------------------------------------------------------------------
INSERT INTO users (username, display_name, is_primary)
VALUES ('tanmay', 'Tanmay', TRUE)
ON CONFLICT (username) DO NOTHING;

ALTER TABLE streaming_history
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

-- Backfill every existing row (70,817 as of migration) to the primary user
UPDATE streaming_history
SET user_id = (SELECT id FROM users WHERE username = 'tanmay')
WHERE user_id IS NULL;

ALTER TABLE streaming_history
    ALTER COLUMN user_id SET NOT NULL;

COMMENT ON COLUMN streaming_history.user_id IS 'Owner of this stream (FK -> users.id)';

-- ---------------------------------------------------------------------------
-- 3. Composite indexes for user-scoped queries
--    (non-CONCURRENT: table is ~70k rows and this file is one transaction)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_streaming_user_ts
    ON streaming_history(user_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_streaming_user_artist
    ON streaming_history(user_id, master_metadata_album_artist_name);

CREATE INDEX IF NOT EXISTS idx_streaming_user_track
    ON streaming_history(user_id, spotify_track_uri);

CREATE INDEX IF NOT EXISTS idx_streaming_user_platform
    ON streaming_history(user_id, platform);

CREATE INDEX IF NOT EXISTS idx_streaming_user_artist_ts
    ON streaming_history(user_id, master_metadata_album_artist_name, ts DESC);

-- Music-only partial index (mirrors idx_streaming_music_only from 001, now user-scoped)
CREATE INDEX IF NOT EXISTS idx_streaming_user_music_only
    ON streaming_history(user_id, ts DESC)
    WHERE spotify_track_uri IS NOT NULL
      AND episode_name IS NULL
      AND audiobook_title IS NULL;

-- Lookup index used by the loader's "does this user already have rows?" check
-- and by re-run deletes. NOT unique: real Spotify exports contain exact-duplicate
-- rows (same user_id, ts, track_uri, ms_played), so idempotency is handled by the
-- loader deleting a user's rows before reloading, not by an upsert conflict target.
CREATE INDEX IF NOT EXISTS idx_streaming_user_ts_uri
    ON streaming_history(user_id, ts, spotify_track_uri)
    WHERE spotify_track_uri IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. Rebuild the 3 materialized views with a leading user_id column
--    (originally defined in 001_create_streaming_table.sql)
-- ---------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS monthly_stats CASCADE;
DROP MATERIALIZED VIEW IF EXISTS top_artists   CASCADE;
DROP MATERIALIZED VIEW IF EXISTS top_tracks    CASCADE;

CREATE MATERIALIZED VIEW monthly_stats AS
SELECT
    user_id,
    DATE_TRUNC('month', ts)::date        AS month,
    COUNT(*)                             AS total_streams,
    SUM(ms_played) / 3600000.0           AS total_hours,
    COUNT(DISTINCT master_metadata_album_artist_name) AS unique_artists,
    COUNT(DISTINCT master_metadata_track_name)        AS unique_tracks,
    COUNT(DISTINCT platform)             AS platforms_used,
    ROUND(AVG(ms_played)::numeric, 2)    AS avg_ms_played,
    SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS total_skipped
FROM streaming_history
WHERE master_metadata_track_name IS NOT NULL
GROUP BY user_id, DATE_TRUNC('month', ts)
ORDER BY user_id, month DESC;

CREATE UNIQUE INDEX idx_monthly_stats_user_month ON monthly_stats(user_id, month);

CREATE MATERIALIZED VIEW top_artists AS
SELECT
    user_id,
    master_metadata_album_artist_name   AS artist,
    COUNT(*)                             AS stream_count,
    SUM(ms_played) / 3600000.0          AS total_hours,
    MIN(ts)                              AS first_listen,
    MAX(ts)                              AS last_listen,
    COUNT(DISTINCT ts::date)            AS days_listened,
    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY user_id))::numeric, 2)
                                        AS percentage_of_total
FROM streaming_history
WHERE master_metadata_album_artist_name IS NOT NULL
  AND spotify_track_uri IS NOT NULL
GROUP BY user_id, master_metadata_album_artist_name
ORDER BY user_id, stream_count DESC;

CREATE UNIQUE INDEX idx_top_artists_user_artist ON top_artists(user_id, artist);
CREATE INDEX idx_top_artists_user_streams ON top_artists(user_id, stream_count DESC);

CREATE MATERIALIZED VIEW top_tracks AS
SELECT
    user_id,
    master_metadata_track_name          AS track,
    master_metadata_album_artist_name   AS artist,
    spotify_track_uri                   AS track_uri,
    COUNT(*)                             AS stream_count,
    MIN(ts)                              AS first_listen,
    MAX(ts)                              AS last_listen,
    COUNT(DISTINCT ts::date)            AS days_listened
FROM streaming_history
WHERE master_metadata_track_name IS NOT NULL
  AND master_metadata_album_artist_name IS NOT NULL
  AND spotify_track_uri IS NOT NULL
GROUP BY user_id, master_metadata_track_name, master_metadata_album_artist_name, spotify_track_uri
ORDER BY user_id, stream_count DESC;

CREATE UNIQUE INDEX idx_top_tracks_user_track
    ON top_tracks(user_id, track, artist, track_uri);
CREATE INDEX idx_top_tracks_user_streams ON top_tracks(user_id, stream_count DESC);

COMMENT ON MATERIALIZED VIEW monthly_stats IS 'Per-user pre-aggregated monthly listening statistics';
COMMENT ON MATERIALIZED VIEW top_artists   IS 'Per-user pre-aggregated top artists';
COMMENT ON MATERIALIZED VIEW top_tracks    IS 'Per-user pre-aggregated top tracks';

COMMIT;

-- Populate the freshly-created views (CONCURRENTLY not needed on first fill)
REFRESH MATERIALIZED VIEW monthly_stats;
REFRESH MATERIALIZED VIEW top_artists;
REFRESH MATERIALIZED VIEW top_tracks;
