-- Migration: Friend-group comparison helper function
-- Date: 2026-08-30
-- Purpose: One aggregate over streaming_history grouped by user, for the
--          Comparison dashboard leaderboard. All other comparison math
--          (artist overlap, Jaccard, similarity matrix) is computed in the
--          FastAPI service from the per-user top_artists materialized view to
--          avoid PostgREST statement timeouts on heavy cross-user aggregation.
-- Applies after: 004_user_scoped_functions.sql
-- Run: psql "<conn>" -v ON_ERROR_STOP=1 -f 005_compare_functions.sql

BEGIN;

CREATE OR REPLACE FUNCTION get_user_leaderboard()
RETURNS TABLE (
    user_id        UUID,
    username       TEXT,
    display_name   TEXT,
    is_primary     BOOLEAN,
    total_streams  BIGINT,
    total_hours    NUMERIC,
    unique_artists BIGINT,
    unique_tracks  BIGINT,
    skip_rate      NUMERIC,
    first_stream   DATE,
    last_stream    DATE
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        u.id,
        u.username,
        u.display_name,
        u.is_primary,
        COUNT(*) FILTER (WHERE s.spotify_track_uri IS NOT NULL)::BIGINT       AS total_streams,
        ROUND((SUM(s.ms_played) / 3600000.0)::NUMERIC, 1)                     AS total_hours,
        COUNT(DISTINCT s.master_metadata_album_artist_name)::BIGINT           AS unique_artists,
        COUNT(DISTINCT s.spotify_track_uri)::BIGINT                           AS unique_tracks,
        ROUND((SUM(CASE WHEN s.skipped THEN 1 ELSE 0 END) * 100.0
               / NULLIF(COUNT(*), 0))::NUMERIC, 1)                           AS skip_rate,
        MIN(s.ts)::date                                                      AS first_stream,
        MAX(s.ts)::date                                                      AS last_stream
    FROM users u
    JOIN streaming_history s ON s.user_id = u.id
    GROUP BY u.id, u.username, u.display_name, u.is_primary
    ORDER BY total_streams DESC;
$$;

COMMENT ON FUNCTION get_user_leaderboard IS 'Per-user listening totals for the Comparison dashboard leaderboard';

COMMIT;
