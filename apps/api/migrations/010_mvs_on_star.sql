-- Migration: Repoint the 3 core MVs + ~8 hottest RPCs at gold.fact_streams
-- Date: 2026-09-01
-- Purpose: Phase 11 step 7. monthly_stats / top_artists / top_tracks and the
--          7 hottest streaming_history-reading RPCs (+ _mood_rows, the shared
--          mood helper -- 8 total) now read gold.fact_streams instead of
--          public.streaming_history. Names and signatures are IDENTICAL to
--          004/006 -- every function is preceded by its exact
--          DROP FUNCTION IF EXISTS (Blocker B2 discipline).
--
--          SCOPE, DELIBERATE (pre-declared deviation #3 in the Phase 11
--          plan): only these 3 MVs + 8 RPCs move. 006's long tail
--          (get_milestones_list, get_flashback, get_artist_loyalty,
--          get_artist_obsessions, get_discovery_timeline,
--          get_reflective_insights, get_weekend_weekday_comparison,
--          get_most_repeated_tracks, get_monthly_diversity,
--          get_listening_heatmap) keeps reading public.streaming_history,
--          which still exists and is still populated (Phase 11 does not
--          remove it). Phase 12 finishes the move once the pipeline owns the
--          write path end-to-end. Repointing all 30+ functions here would be
--          high-risk, low-value churn for this phase.
--
--          Correctness constraint: monthly_stats/top_artists/top_tracks used
--          COUNT(DISTINCT master_metadata_album_artist_name) -- i.e. exact,
--          case-sensitive text grouping, NOT the lower/trim-normalized
--          dim_artist.artist_key (D3). gold.fact_streams carries
--          artist_name/track_name/album_name as denormalized, unnormalized
--          text specifically so this migration can reproduce that grouping
--          bit-for-bit (see 009's comment on those columns). Confirmed in
--          this dataset: 4 rows differ only by artist-name casing
--          ("KALEO" vs "Kaleo", "LEN" vs "Len") -- grouping by artist_key
--          would have silently merged them and moved get_top_artists'
--          numbers, which is exactly what V4's baseline diff exists to catch.
--
--          _mood_rows (Blocker B4): same arithmetic, same ISODOW >= 6
--          weekend rule, same clamps as 006 -- only the FROM clause changes,
--          from streaming_history to gold.fact_streams.
--
-- Applies after: 009_star_schema.sql (and after scripts/build_star_schema.py
--                has populated gold.fact_streams at least once -- the MVs
--                below will simply be empty/zero until then, not broken).
-- Run: python apps/api/db/migrate.py

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Materialized views: DROP + recreate, reading gold.fact_streams.
--    Same columns, same indexes, same names as 003's versions.
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
    COUNT(DISTINCT artist_name)          AS unique_artists,
    COUNT(DISTINCT track_name)           AS unique_tracks,
    COUNT(DISTINCT platform)             AS platforms_used,
    ROUND(AVG(ms_played)::numeric, 2)    AS avg_ms_played,
    SUM(CASE WHEN skipped THEN 1 ELSE 0 END) AS total_skipped
FROM gold.fact_streams
WHERE track_name IS NOT NULL
GROUP BY user_id, DATE_TRUNC('month', ts)
ORDER BY user_id, month DESC;

CREATE UNIQUE INDEX idx_monthly_stats_user_month ON monthly_stats(user_id, month);

CREATE MATERIALIZED VIEW top_artists AS
SELECT
    user_id,
    artist_name                          AS artist,
    COUNT(*)                             AS stream_count,
    SUM(ms_played) / 3600000.0          AS total_hours,
    MIN(ts)                              AS first_listen,
    MAX(ts)                              AS last_listen,
    COUNT(DISTINCT ts::date)            AS days_listened,
    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY user_id))::numeric, 2)
                                        AS percentage_of_total
FROM gold.fact_streams
WHERE artist_name IS NOT NULL
  AND track_key IS NOT NULL AND track_key NOT LIKE 'hash:%'
GROUP BY user_id, artist_name
ORDER BY user_id, stream_count DESC;

CREATE UNIQUE INDEX idx_top_artists_user_artist ON top_artists(user_id, artist);
CREATE INDEX idx_top_artists_user_streams ON top_artists(user_id, stream_count DESC);

CREATE MATERIALIZED VIEW top_tracks AS
SELECT
    user_id,
    track_name                           AS track,
    artist_name                          AS artist,
    (SELECT dt.spotify_track_uri FROM gold.dim_track dt WHERE dt.track_key = fs.track_key)
                                        AS track_uri,
    COUNT(*)                             AS stream_count,
    MIN(ts)                              AS first_listen,
    MAX(ts)                              AS last_listen,
    COUNT(DISTINCT ts::date)            AS days_listened
FROM gold.fact_streams fs
WHERE track_name IS NOT NULL
  AND artist_name IS NOT NULL
  AND track_key IS NOT NULL AND track_key NOT LIKE 'hash:%'
GROUP BY user_id, track_name, artist_name, fs.track_key
ORDER BY user_id, stream_count DESC;

CREATE UNIQUE INDEX idx_top_tracks_user_track
    ON top_tracks(user_id, track, artist, track_uri);
CREATE INDEX idx_top_tracks_user_streams ON top_tracks(user_id, stream_count DESC);

COMMENT ON MATERIALIZED VIEW monthly_stats IS 'Per-user pre-aggregated monthly listening statistics (Phase 11: reads gold.fact_streams)';
COMMENT ON MATERIALIZED VIEW top_artists   IS 'Per-user pre-aggregated top artists (Phase 11: reads gold.fact_streams)';
COMMENT ON MATERIALIZED VIEW top_tracks    IS 'Per-user pre-aggregated top tracks (Phase 11: reads gold.fact_streams)';

-- Populate immediately (non-CONCURRENTLY: fine inside this migration's own
-- transaction; refresh_all_views()/CONCURRENTLY is for later runtime refreshes).
REFRESH MATERIALIZED VIEW monthly_stats;
REFRESH MATERIALIZED VIEW top_artists;
REFRESH MATERIALIZED VIEW top_tracks;

-- ---------------------------------------------------------------------------
-- 2. RPCs -- exact DROP FUNCTION IF EXISTS before each CREATE OR REPLACE
--    (Blocker B2). Signatures identical to 004/006.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS get_overview_stats(UUID);
DROP FUNCTION IF EXISTS get_date_range(UUID);
DROP FUNCTION IF EXISTS get_platform_stats(UUID);
DROP FUNCTION IF EXISTS get_hourly_distribution(UUID);
DROP FUNCTION IF EXISTS get_daily_distribution(UUID);
DROP FUNCTION IF EXISTS get_yearly_comparison(UUID);
DROP FUNCTION IF EXISTS get_listening_streaks(INTEGER, UUID);
DROP FUNCTION IF EXISTS _mood_rows(UUID);

-- ---------------------------------------------------------------------------
-- get_overview_stats  (was 004; now reads gold.fact_streams)
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
        COUNT(DISTINCT track_name)::BIGINT,
        COUNT(DISTINCT artist_name)::BIGINT,
        COUNT(DISTINCT album_name)::BIGINT,
        ROUND((COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT ts::date), 0)), 1)
    FROM gold.fact_streams
    WHERE user_id = _effective_user_id(p_user_id)
      AND track_key IS NOT NULL AND track_key NOT LIKE 'hash:%';
$$;

-- ---------------------------------------------------------------------------
-- get_date_range  (was 004; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_date_range(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (min_date TIMESTAMPTZ, max_date TIMESTAMPTZ, total_days INTEGER)
LANGUAGE sql
AS $$
    SELECT
        MIN(ts) AS min_date,
        MAX(ts) AS max_date,
        (EXTRACT(EPOCH FROM (MAX(ts) - MIN(ts))) / 86400)::INTEGER AS total_days
    FROM gold.fact_streams
    WHERE user_id = _effective_user_id(p_user_id);
$$;

-- ---------------------------------------------------------------------------
-- get_platform_stats  (was 004; now reads gold.fact_streams)
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
    FROM gold.fact_streams
    WHERE user_id = _effective_user_id(p_user_id)
      AND track_key IS NOT NULL AND track_key NOT LIKE 'hash:%'
    GROUP BY platform
    ORDER BY 2 DESC;
$$;

-- ---------------------------------------------------------------------------
-- get_hourly_distribution  (was 004; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_hourly_distribution(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (hour INTEGER, streams BIGINT, avg_streams_per_hour NUMERIC)
LANGUAGE sql
AS $$
    SELECT
        EXTRACT(HOUR FROM ts)::INTEGER,
        COUNT(*)::BIGINT,
        ROUND((COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT ts::date), 0)), 1)
    FROM gold.fact_streams
    WHERE user_id = _effective_user_id(p_user_id)
      AND track_key IS NOT NULL AND track_key NOT LIKE 'hash:%'
    GROUP BY EXTRACT(HOUR FROM ts)
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_daily_distribution  (was 004; now reads gold.fact_streams)
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
    FROM gold.fact_streams
    WHERE user_id = _effective_user_id(p_user_id)
      AND track_key IS NOT NULL AND track_key NOT LIKE 'hash:%'
    GROUP BY EXTRACT(ISODOW FROM ts), TO_CHAR(ts, 'Day')
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_yearly_comparison  (was 004; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_yearly_comparison(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (year INTEGER, streams BIGINT, hours NUMERIC, unique_artists INTEGER, unique_tracks INTEGER)
LANGUAGE sql
AS $$
    SELECT
        EXTRACT(YEAR FROM ts)::INTEGER,
        COUNT(*)::BIGINT,
        ROUND((SUM(ms_played) / 3600000.0)::NUMERIC, 2),
        COUNT(DISTINCT artist_name)::INTEGER,
        COUNT(DISTINCT track_name)::INTEGER
    FROM gold.fact_streams
    WHERE user_id = _effective_user_id(p_user_id)
      AND track_key IS NOT NULL AND track_key NOT LIKE 'hash:%'
    GROUP BY EXTRACT(YEAR FROM ts)
    ORDER BY 1 ASC;
$$;

-- ---------------------------------------------------------------------------
-- get_listening_streaks  (was 004; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_listening_streaks(limit_count INTEGER DEFAULT 10, p_user_id UUID DEFAULT NULL)
RETURNS TABLE (start_date DATE, end_date DATE, length_days INTEGER, total_streams BIGINT)
LANGUAGE sql
AS $$
    WITH daily_streams AS (
        SELECT ts::date AS listen_date, COUNT(*) AS streams
        FROM gold.fact_streams
        WHERE user_id = _effective_user_id(p_user_id)
          AND track_key IS NOT NULL AND track_key NOT LIKE 'hash:%'
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

-- ---------------------------------------------------------------------------
-- _mood_rows  (Blocker B4: was 006; SAME arithmetic, SAME ISODOW >= 6 rule,
--   SAME clamps -- only the FROM clause changes, streaming_history ->
--   gold.fact_streams). get_mood_summary / get_mood_contexts / get_mood_monthly
--   (006) all SELECT FROM this function unchanged, so repointing it here
--   repoints all three mood endpoints without touching their own bodies.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION _mood_rows(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    ts         TIMESTAMPTZ,
    platform   TEXT,
    is_weekend BOOLEAN,
    valence    NUMERIC,
    energy     NUMERIC,
    dance      NUMERIC
)
LANGUAGE sql
STABLE
AS $$
    WITH base AS (
        SELECT
            s.ts,
            COALESCE(s.platform, 'unknown')      AS platform,
            EXTRACT(HOUR FROM s.ts)::INT         AS hr,
            (EXTRACT(ISODOW FROM s.ts) >= 6)     AS is_weekend,
            s.ms_played,
            COALESCE(s.skipped, FALSE)           AS skipped
        FROM gold.fact_streams s
        WHERE s.user_id = _effective_user_id(p_user_id)
          AND s.ts IS NOT NULL
    )
    SELECT
        ts,
        platform,
        is_weekend,
        GREATEST(0.0, LEAST(1.0,
            0.5
            + CASE WHEN is_weekend THEN 0.15 ELSE 0.0 END
            + CASE
                WHEN hr BETWEEN 10 AND 20 THEN 0.15
                WHEN hr BETWEEN 6 AND 9 OR hr BETWEEN 21 AND 23 THEN 0.05
                ELSE -0.10
              END
        ))::NUMERIC AS valence,
        GREATEST(0.0, LEAST(1.0,
            0.5
            + CASE
                WHEN hr BETWEEN 6 AND 12 THEN 0.25
                WHEN hr BETWEEN 13 AND 18 THEN 0.15
                WHEN hr BETWEEN 19 AND 22 THEN 0.05
                ELSE -0.15
              END
        ))::NUMERIC AS energy,
        GREATEST(0.0, LEAST(1.0,
            0.5
            + CASE
                WHEN ms_played >= 180000 THEN 0.25
                WHEN ms_played >= 60000 THEN 0.10
                ELSE -0.15
              END
            + CASE WHEN skipped THEN -0.20 ELSE 0.0 END
        ))::NUMERIC AS dance
    FROM base;
$$;

COMMIT;
