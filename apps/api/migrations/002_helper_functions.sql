-- Migration: Helper functions and RPC endpoints
-- Date: 2025-10-19
-- Purpose: Create utility functions for data management and querying
--
-- ⚠️  SUPERSEDED — NOT APPLIED TO NEW DATABASES (since Phase 10).
--
-- Every function below is redefined by 004_user_scoped_functions.sql with an
-- extra `p_user_id UUID DEFAULT NULL` argument. Both variants have all-default
-- arguments, so applying both leaves ambiguous overloads and Postgres rejects
-- calls at runtime:
--
--     ERROR:  function get_top_artists(limit_count => integer) is not unique
--
-- db/migrate.py therefore records this file as applied without executing it
-- (see SUPERSEDED in that script). Kept in the repo as history — it is what
-- the live Supabase database had applied before 004 landed. Do not run it by
-- hand against a database that already has 004.

-- Function to truncate streaming_history (for data reload)
CREATE OR REPLACE FUNCTION truncate_streaming_history()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    TRUNCATE TABLE streaming_history RESTART IDENTITY CASCADE;
END;
$$;

-- Function to get date range
CREATE OR REPLACE FUNCTION get_date_range()
RETURNS TABLE (
    min_date TIMESTAMPTZ,
    max_date TIMESTAMPTZ,
    total_days INTEGER
)
LANGUAGE sql
AS $$
    SELECT
        MIN(ts) as min_date,
        MAX(ts) as max_date,
        (EXTRACT(EPOCH FROM (MAX(ts) - MIN(ts))) / 86400)::INTEGER as total_days
    FROM streaming_history;
$$;

-- Function to refresh monthly_stats materialized view
CREATE OR REPLACE FUNCTION refresh_monthly_stats()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_stats;
END;
$$;

-- Function to refresh top_artists materialized view
CREATE OR REPLACE FUNCTION refresh_top_artists()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY top_artists;
END;
$$;

-- Function to refresh top_tracks materialized view
CREATE OR REPLACE FUNCTION refresh_top_tracks()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY top_tracks;
END;
$$;

-- Function to refresh all materialized views at once
CREATE OR REPLACE FUNCTION refresh_all_views()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM refresh_monthly_stats();
    PERFORM refresh_top_artists();
    PERFORM refresh_top_tracks();
END;
$$;

-- Function to get overview statistics
CREATE OR REPLACE FUNCTION get_overview_stats()
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
        COUNT(*)::BIGINT as total_streams,
        ROUND((SUM(ms_played) / 3600000.0)::NUMERIC, 2) as total_hours,
        COUNT(DISTINCT master_metadata_track_name)::BIGINT as unique_tracks,
        COUNT(DISTINCT master_metadata_album_artist_name)::BIGINT as unique_artists,
        COUNT(DISTINCT master_metadata_album_album_name)::BIGINT as unique_albums,
        ROUND((COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT ts::date), 0)), 1) as avg_daily_streams
    FROM streaming_history
    WHERE spotify_track_uri IS NOT NULL;  -- Only count music tracks
$$;

-- Function to get top artists with limit
CREATE OR REPLACE FUNCTION get_top_artists(limit_count INTEGER DEFAULT 10)
RETURNS TABLE (
    artist TEXT,
    streams BIGINT,
    hours NUMERIC,
    percentage NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        artist,
        stream_count::BIGINT as streams,
        ROUND(total_hours::NUMERIC, 2) as hours,
        percentage_of_total as percentage
    FROM top_artists
    ORDER BY stream_count DESC
    LIMIT limit_count;
$$;

-- Function to get top tracks with limit
CREATE OR REPLACE FUNCTION get_top_tracks(limit_count INTEGER DEFAULT 10)
RETURNS TABLE (
    track TEXT,
    artist TEXT,
    streams BIGINT,
    track_uri TEXT
)
LANGUAGE sql
AS $$
    SELECT
        track,
        artist,
        stream_count::BIGINT as streams,
        track_uri
    FROM top_tracks
    ORDER BY stream_count DESC
    LIMIT limit_count;
$$;

-- Function to get monthly streaming data
CREATE OR REPLACE FUNCTION get_monthly_data()
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
        month,
        total_streams::BIGINT as streams,
        ROUND(total_hours::NUMERIC, 2) as hours,
        unique_artists::INTEGER,
        unique_tracks::INTEGER
    FROM monthly_stats
    ORDER BY month ASC;
$$;

-- Function to get platform distribution
CREATE OR REPLACE FUNCTION get_platform_stats()
RETURNS TABLE (
    platform TEXT,
    streams BIGINT,
    hours NUMERIC,
    percentage NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        COALESCE(platform, 'Unknown') as platform,
        COUNT(*)::BIGINT as streams,
        ROUND((SUM(ms_played) / 3600000.0)::NUMERIC, 2) as hours,
        ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ())::NUMERIC, 2) as percentage
    FROM streaming_history
    WHERE spotify_track_uri IS NOT NULL
    GROUP BY platform
    ORDER BY streams DESC;
$$;

-- Function to get hourly listening distribution
CREATE OR REPLACE FUNCTION get_hourly_distribution()
RETURNS TABLE (
    hour INTEGER,
    streams BIGINT,
    avg_streams_per_hour NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        EXTRACT(HOUR FROM ts)::INTEGER as hour,
        COUNT(*)::BIGINT as streams,
        ROUND((COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT ts::date), 0)), 1) as avg_streams_per_hour
    FROM streaming_history
    WHERE spotify_track_uri IS NOT NULL
    GROUP BY EXTRACT(HOUR FROM ts)
    ORDER BY hour;
$$;

-- Function to get daily distribution (day of week)
CREATE OR REPLACE FUNCTION get_daily_distribution()
RETURNS TABLE (
    day_of_week INTEGER,
    day_name TEXT,
    streams BIGINT,
    avg_streams NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        EXTRACT(ISODOW FROM ts)::INTEGER as day_of_week,
        TO_CHAR(ts, 'Day') as day_name,
        COUNT(*)::BIGINT as streams,
        ROUND((COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT DATE_TRUNC('week', ts)), 0)), 1) as avg_streams
    FROM streaming_history
    WHERE spotify_track_uri IS NOT NULL
    GROUP BY EXTRACT(ISODOW FROM ts), TO_CHAR(ts, 'Day')
    ORDER BY day_of_week;
$$;

-- Function to get listening streaks
CREATE OR REPLACE FUNCTION get_listening_streaks(limit_count INTEGER DEFAULT 10)
RETURNS TABLE (
    start_date DATE,
    end_date DATE,
    length_days INTEGER,
    total_streams BIGINT
)
LANGUAGE sql
AS $$
    WITH daily_streams AS (
        SELECT
            ts::date as listen_date,
            COUNT(*) as streams
        FROM streaming_history
        WHERE spotify_track_uri IS NOT NULL
        GROUP BY ts::date
        ORDER BY listen_date
    ),
    streaks AS (
        SELECT
            listen_date,
            streams,
            listen_date - (ROW_NUMBER() OVER (ORDER BY listen_date))::INTEGER * INTERVAL '1 day' as grp
        FROM daily_streams
    ),
    streak_groups AS (
        SELECT
            MIN(listen_date) as start_date,
            MAX(listen_date) as end_date,
            (MAX(listen_date) - MIN(listen_date))::INTEGER + 1 as length_days,
            SUM(streams)::BIGINT as total_streams
        FROM streaks
        GROUP BY grp
        HAVING (MAX(listen_date) - MIN(listen_date))::INTEGER + 1 >= 3
    )
    SELECT * FROM streak_groups
    ORDER BY length_days DESC, total_streams DESC
    LIMIT limit_count;
$$;

-- Function to get skip behavior by artist
CREATE OR REPLACE FUNCTION get_skip_behavior(limit_count INTEGER DEFAULT 20)
RETURNS TABLE (
    artist TEXT,
    total_streams BIGINT,
    skipped_count BIGINT,
    skip_rate NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        master_metadata_album_artist_name as artist,
        COUNT(*)::BIGINT as total_streams,
        SUM(CASE WHEN skipped THEN 1 ELSE 0 END)::BIGINT as skipped_count,
        ROUND((SUM(CASE WHEN skipped THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0))::NUMERIC, 2) as skip_rate
    FROM streaming_history
    WHERE master_metadata_album_artist_name IS NOT NULL
      AND spotify_track_uri IS NOT NULL
    GROUP BY master_metadata_album_artist_name
    HAVING COUNT(*) >= 10
    ORDER BY total_streams DESC
    LIMIT limit_count;
$$;

-- Function to get yearly comparison
CREATE OR REPLACE FUNCTION get_yearly_comparison()
RETURNS TABLE (
    year INTEGER,
    streams BIGINT,
    hours NUMERIC,
    unique_artists INTEGER,
    unique_tracks INTEGER
)
LANGUAGE sql
AS $$
    SELECT
        EXTRACT(YEAR FROM ts)::INTEGER as year,
        COUNT(*)::BIGINT as streams,
        ROUND((SUM(ms_played) / 3600000.0)::NUMERIC, 2) as hours,
        COUNT(DISTINCT master_metadata_album_artist_name)::INTEGER as unique_artists,
        COUNT(DISTINCT master_metadata_track_name)::INTEGER as unique_tracks
    FROM streaming_history
    WHERE spotify_track_uri IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM ts)
    ORDER BY year ASC;
$$;

-- Add comments
COMMENT ON FUNCTION get_overview_stats IS 'Get overall listening statistics';
COMMENT ON FUNCTION get_top_artists IS 'Get top artists with optional limit';
COMMENT ON FUNCTION get_top_tracks IS 'Get top tracks with optional limit';
COMMENT ON FUNCTION get_monthly_data IS 'Get monthly listening statistics';
COMMENT ON FUNCTION refresh_all_views IS 'Refresh all materialized views for updated statistics';
