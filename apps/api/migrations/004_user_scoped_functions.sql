-- Migration: User-scoped helper functions
-- Date: 2026-08-30
-- Purpose: CREATE OR REPLACE every query function from 002_helper_functions.sql so
--          it takes an optional p_user_id and scopes results to that user.
--          When p_user_id is NULL the function falls back to the primary user, so
--          the existing single-user API keeps working with no code change.
-- Applies after: 003_add_multi_user_support.sql
-- Run: psql "<conn>" -v ON_ERROR_STOP=1 -f 004_user_scoped_functions.sql
--
-- 002 is kept as the historical record; this file supersedes its functions.

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Drop the pre-multi-user signatures from 002. The new functions below use
--    UUID DEFAULT NULL params, so a zero-arg / single-int call would otherwise
--    be ambiguous against these and every RPC call from supabase-py would fail
--    with "function ... is not unique".
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS get_overview_stats();
DROP FUNCTION IF EXISTS get_monthly_data();
DROP FUNCTION IF EXISTS get_platform_stats();
DROP FUNCTION IF EXISTS get_hourly_distribution();
DROP FUNCTION IF EXISTS get_daily_distribution();
DROP FUNCTION IF EXISTS get_yearly_comparison();
DROP FUNCTION IF EXISTS get_date_range();
DROP FUNCTION IF EXISTS truncate_streaming_history();
DROP FUNCTION IF EXISTS get_top_artists(integer);
DROP FUNCTION IF EXISTS get_top_tracks(integer);
DROP FUNCTION IF EXISTS get_skip_behavior(integer);
DROP FUNCTION IF EXISTS get_listening_streaks(integer);

-- Helper: resolve the effective user id (arg, or primary user when arg is NULL)
CREATE OR REPLACE FUNCTION _effective_user_id(p_user_id UUID)
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(p_user_id, (SELECT id FROM users WHERE is_primary LIMIT 1));
$$;

-- ---------------------------------------------------------------------------
-- truncate_streaming_history: optional per-user delete
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION truncate_streaming_history(p_user_id UUID DEFAULT NULL)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    IF p_user_id IS NULL THEN
        TRUNCATE TABLE streaming_history RESTART IDENTITY CASCADE;
    ELSE
        DELETE FROM streaming_history WHERE user_id = p_user_id;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- get_date_range
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_date_range(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (min_date TIMESTAMPTZ, max_date TIMESTAMPTZ, total_days INTEGER)
LANGUAGE sql
AS $$
    SELECT
        MIN(ts) AS min_date,
        MAX(ts) AS max_date,
        (EXTRACT(EPOCH FROM (MAX(ts) - MIN(ts))) / 86400)::INTEGER AS total_days
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id);
$$;

-- ---------------------------------------------------------------------------
-- refresh_* : unchanged semantics (views refresh wholesale for all users)
-- Re-declared here so a fresh 004 apply is self-contained.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION refresh_monthly_stats()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_stats; END; $$;

CREATE OR REPLACE FUNCTION refresh_top_artists()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN REFRESH MATERIALIZED VIEW CONCURRENTLY top_artists; END; $$;

CREATE OR REPLACE FUNCTION refresh_top_tracks()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN REFRESH MATERIALIZED VIEW CONCURRENTLY top_tracks; END; $$;

CREATE OR REPLACE FUNCTION refresh_all_views()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    PERFORM refresh_monthly_stats();
    PERFORM refresh_top_artists();
    PERFORM refresh_top_tracks();
END; $$;

-- ---------------------------------------------------------------------------
-- get_overview_stats
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_overview_stats(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    total_streams BIGINT,
    total_hours NUMERIC,
    unique_tracks BIGINT,
    unique_artists BIGINT,
    unique_albums BIGINT,
    avg_daily_streams NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        COUNT(*)::BIGINT,
        ROUND((SUM(ms_played) / 3600000.0)::NUMERIC, 2),
        COUNT(DISTINCT master_metadata_track_name)::BIGINT,
        COUNT(DISTINCT master_metadata_album_artist_name)::BIGINT,
        COUNT(DISTINCT master_metadata_album_album_name)::BIGINT,
        ROUND((COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT ts::date), 0)), 1)
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id)
      AND spotify_track_uri IS NOT NULL;
$$;

-- ---------------------------------------------------------------------------
-- get_top_artists  (reads the per-user materialized view)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_top_artists(limit_count INTEGER DEFAULT 10, p_user_id UUID DEFAULT NULL)
RETURNS TABLE (artist TEXT, streams BIGINT, hours NUMERIC, percentage NUMERIC)
LANGUAGE sql
AS $$
    SELECT
        artist,
        stream_count::BIGINT,
        ROUND(total_hours::NUMERIC, 2),
        percentage_of_total
    FROM top_artists
    WHERE user_id = _effective_user_id(p_user_id)
    ORDER BY stream_count DESC
    LIMIT limit_count;
$$;

-- ---------------------------------------------------------------------------
-- get_top_tracks
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_top_tracks(limit_count INTEGER DEFAULT 10, p_user_id UUID DEFAULT NULL)
RETURNS TABLE (track TEXT, artist TEXT, streams BIGINT, track_uri TEXT)
LANGUAGE sql
AS $$
    SELECT
        track,
        artist,
        stream_count::BIGINT,
        track_uri
    FROM top_tracks
    WHERE user_id = _effective_user_id(p_user_id)
    ORDER BY stream_count DESC
    LIMIT limit_count;
$$;

-- ---------------------------------------------------------------------------
-- get_monthly_data
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_monthly_data(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    month TIMESTAMPTZ,
    streams BIGINT,
    hours NUMERIC,
    unique_artists INTEGER,
    unique_tracks INTEGER
)
LANGUAGE sql
AS $$
    SELECT
        month::timestamptz,
        total_streams::BIGINT,
        ROUND(total_hours::NUMERIC, 2),
        unique_artists::INTEGER,
        unique_tracks::INTEGER
    FROM monthly_stats
    WHERE user_id = _effective_user_id(p_user_id)
    ORDER BY month ASC;
$$;

-- ---------------------------------------------------------------------------
-- get_platform_stats
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_platform_stats(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (platform TEXT, streams BIGINT, hours NUMERIC, percentage NUMERIC)
LANGUAGE sql
AS $$
    SELECT
        COALESCE(platform, 'Unknown'),
        COUNT(*)::BIGINT,
        ROUND((SUM(ms_played) / 3600000.0)::NUMERIC, 2),
        ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ())::NUMERIC, 2)
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id)
      AND spotify_track_uri IS NOT NULL
    GROUP BY platform
    ORDER BY 2 DESC;
$$;

-- ---------------------------------------------------------------------------
-- get_hourly_distribution
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_hourly_distribution(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (hour INTEGER, streams BIGINT, avg_streams_per_hour NUMERIC)
LANGUAGE sql
AS $$
    SELECT
        EXTRACT(HOUR FROM ts)::INTEGER,
        COUNT(*)::BIGINT,
        ROUND((COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT ts::date), 0)), 1)
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id)
      AND spotify_track_uri IS NOT NULL
    GROUP BY EXTRACT(HOUR FROM ts)
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_daily_distribution
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_daily_distribution(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (day_of_week INTEGER, day_name TEXT, streams BIGINT, avg_streams NUMERIC)
LANGUAGE sql
AS $$
    SELECT
        EXTRACT(ISODOW FROM ts)::INTEGER,
        TO_CHAR(ts, 'Day'),
        COUNT(*)::BIGINT,
        ROUND((COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT DATE_TRUNC('week', ts)), 0)), 1)
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id)
      AND spotify_track_uri IS NOT NULL
    GROUP BY EXTRACT(ISODOW FROM ts), TO_CHAR(ts, 'Day')
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_skip_behavior
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_skip_behavior(limit_count INTEGER DEFAULT 20, p_user_id UUID DEFAULT NULL)
RETURNS TABLE (artist TEXT, total_streams BIGINT, skipped_count BIGINT, skip_rate NUMERIC)
LANGUAGE sql
AS $$
    SELECT
        master_metadata_album_artist_name,
        COUNT(*)::BIGINT,
        SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::BIGINT,
        ROUND((SUM(CASE WHEN skipped THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0))::NUMERIC, 2)
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id)
      AND master_metadata_album_artist_name IS NOT NULL
      AND spotify_track_uri IS NOT NULL
    GROUP BY master_metadata_album_artist_name
    HAVING COUNT(*) >= 10
    ORDER BY 2 DESC
    LIMIT limit_count;
$$;

-- ---------------------------------------------------------------------------
-- get_yearly_comparison
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_yearly_comparison(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (year INTEGER, streams BIGINT, hours NUMERIC, unique_artists INTEGER, unique_tracks INTEGER)
LANGUAGE sql
AS $$
    SELECT
        EXTRACT(YEAR FROM ts)::INTEGER,
        COUNT(*)::BIGINT,
        ROUND((SUM(ms_played) / 3600000.0)::NUMERIC, 2),
        COUNT(DISTINCT master_metadata_album_artist_name)::INTEGER,
        COUNT(DISTINCT master_metadata_track_name)::INTEGER
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id)
      AND spotify_track_uri IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM ts)
    ORDER BY 1 ASC;
$$;

-- ---------------------------------------------------------------------------
-- get_listening_streaks
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_listening_streaks(limit_count INTEGER DEFAULT 10, p_user_id UUID DEFAULT NULL)
RETURNS TABLE (start_date DATE, end_date DATE, length_days INTEGER, total_streams BIGINT)
LANGUAGE sql
AS $$
    WITH daily_streams AS (
        SELECT ts::date AS listen_date, COUNT(*) AS streams
        FROM streaming_history
        WHERE user_id = _effective_user_id(p_user_id)
          AND spotify_track_uri IS NOT NULL
        GROUP BY ts::date
    ),
    streaks AS (
        SELECT
            listen_date,
            streams,
            listen_date - (ROW_NUMBER() OVER (ORDER BY listen_date))::INTEGER * INTERVAL '1 day' AS grp
        FROM daily_streams
    ),
    streak_groups AS (
        SELECT
            MIN(listen_date) AS start_date,
            MAX(listen_date) AS end_date,
            (MAX(listen_date) - MIN(listen_date))::INTEGER + 1 AS length_days,
            SUM(streams)::BIGINT AS total_streams
        FROM streaks
        GROUP BY grp
        HAVING (MAX(listen_date) - MIN(listen_date))::INTEGER + 1 >= 3
    )
    SELECT * FROM streak_groups
    ORDER BY length_days DESC, total_streams DESC
    LIMIT limit_count;
$$;

COMMIT;
