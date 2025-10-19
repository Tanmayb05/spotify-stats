-- Migration: Create Spotify streaming data table (FIXED VERSION v2)
-- Date: 2025-10-19
-- Purpose: Store all Spotify streaming history data from JSON files
-- Note: Fixed VARCHAR sizes and immutability issues for Supabase

-- Create streaming_history table
CREATE TABLE IF NOT EXISTS streaming_history (
    id BIGSERIAL PRIMARY KEY,

    -- Timestamp and platform
    ts TIMESTAMPTZ NOT NULL,
    platform VARCHAR(200),  -- FIXED: Increased from 50 to 200 (found values up to 78 chars)

    -- Playback metrics
    ms_played INTEGER NOT NULL,

    -- Location
    conn_country VARCHAR(2),
    ip_addr INET,

    -- Track metadata
    master_metadata_track_name TEXT,
    master_metadata_album_artist_name TEXT,
    master_metadata_album_album_name TEXT,
    spotify_track_uri VARCHAR(255),

    -- Podcast metadata (nullable)
    episode_name TEXT,
    episode_show_name TEXT,
    spotify_episode_uri VARCHAR(255),

    -- Audiobook metadata (nullable)
    audiobook_title TEXT,
    audiobook_uri VARCHAR(255),
    audiobook_chapter_uri VARCHAR(255),
    audiobook_chapter_title TEXT,

    -- Playback context
    reason_start VARCHAR(100),  -- FIXED: Increased from 50 to 100
    reason_end VARCHAR(100),    -- FIXED: Increased from 50 to 100
    shuffle BOOLEAN DEFAULT FALSE,
    skipped BOOLEAN DEFAULT FALSE,
    offline BOOLEAN DEFAULT FALSE,
    offline_timestamp BIGINT,
    incognito_mode BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common query patterns
CREATE INDEX idx_streaming_ts ON streaming_history(ts DESC);
CREATE INDEX idx_streaming_artist ON streaming_history(master_metadata_album_artist_name);
CREATE INDEX idx_streaming_track ON streaming_history(master_metadata_track_name);
CREATE INDEX idx_streaming_track_uri ON streaming_history(spotify_track_uri);
CREATE INDEX idx_streaming_platform ON streaming_history(platform);
CREATE INDEX idx_streaming_artist_ts ON streaming_history(master_metadata_album_artist_name, ts DESC);

-- Create composite index for artist + track queries
CREATE INDEX idx_streaming_artist_track ON streaming_history(
    master_metadata_album_artist_name,
    master_metadata_track_name
);

-- Create partial index for only music (exclude podcasts/audiobooks)
CREATE INDEX idx_streaming_music_only ON streaming_history(ts DESC)
WHERE spotify_track_uri IS NOT NULL
  AND episode_name IS NULL
  AND audiobook_title IS NULL;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
CREATE TRIGGER update_streaming_history_updated_at
    BEFORE UPDATE ON streaming_history
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create materialized view for monthly statistics (for performance)
CREATE MATERIALIZED VIEW monthly_stats AS
SELECT
    DATE_TRUNC('month', ts)::date as month,
    COUNT(*) as total_streams,
    SUM(ms_played) / 3600000.0 as total_hours,
    COUNT(DISTINCT master_metadata_album_artist_name) as unique_artists,
    COUNT(DISTINCT master_metadata_track_name) as unique_tracks,
    COUNT(DISTINCT platform) as platforms_used,
    ROUND(AVG(ms_played)::numeric, 2) as avg_ms_played,
    SUM(CASE WHEN skipped THEN 1 ELSE 0 END) as total_skipped
FROM streaming_history
WHERE master_metadata_track_name IS NOT NULL
GROUP BY DATE_TRUNC('month', ts)
ORDER BY month DESC;

-- Create index on materialized view
CREATE INDEX idx_monthly_stats_month ON monthly_stats(month DESC);

-- Create view for top artists (refreshable)
CREATE MATERIALIZED VIEW top_artists AS
SELECT
    master_metadata_album_artist_name as artist,
    COUNT(*) as stream_count,
    SUM(ms_played) / 3600000.0 as total_hours,
    MIN(ts) as first_listen,
    MAX(ts) as last_listen,
    COUNT(DISTINCT ts::date) as days_listened,
    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ())::numeric, 2) as percentage_of_total
FROM streaming_history
WHERE master_metadata_album_artist_name IS NOT NULL
  AND spotify_track_uri IS NOT NULL
GROUP BY master_metadata_album_artist_name
ORDER BY stream_count DESC;

-- Create index on top artists view
CREATE INDEX idx_top_artists_streams ON top_artists(stream_count DESC);
CREATE INDEX idx_top_artists_name ON top_artists(artist);

-- Create view for top tracks
CREATE MATERIALIZED VIEW top_tracks AS
SELECT
    master_metadata_track_name as track,
    master_metadata_album_artist_name as artist,
    spotify_track_uri as track_uri,
    COUNT(*) as stream_count,
    MIN(ts) as first_listen,
    MAX(ts) as last_listen,
    COUNT(DISTINCT ts::date) as days_listened
FROM streaming_history
WHERE master_metadata_track_name IS NOT NULL
  AND master_metadata_album_artist_name IS NOT NULL
  AND spotify_track_uri IS NOT NULL
GROUP BY
    master_metadata_track_name,
    master_metadata_album_artist_name,
    spotify_track_uri
ORDER BY stream_count DESC;

-- Create index on top tracks view
CREATE INDEX idx_top_tracks_streams ON top_tracks(stream_count DESC);
CREATE INDEX idx_top_tracks_artist ON top_tracks(artist);

-- Comments for documentation
COMMENT ON TABLE streaming_history IS 'Complete Spotify streaming history from JSON exports';
COMMENT ON COLUMN streaming_history.ts IS 'Timestamp when the track was played (UTC)';
COMMENT ON COLUMN streaming_history.ms_played IS 'Milliseconds the track was played';
COMMENT ON COLUMN streaming_history.spotify_track_uri IS 'Unique Spotify track identifier';
COMMENT ON COLUMN streaming_history.skipped IS 'Whether the track was skipped before finishing';
COMMENT ON COLUMN streaming_history.platform IS 'Platform identifier (android, ios, partner platforms, etc.)';
COMMENT ON MATERIALIZED VIEW monthly_stats IS 'Pre-aggregated monthly listening statistics for performance';
COMMENT ON MATERIALIZED VIEW top_artists IS 'Pre-aggregated top artists statistics';
COMMENT ON MATERIALIZED VIEW top_tracks IS 'Pre-aggregated top tracks statistics';
