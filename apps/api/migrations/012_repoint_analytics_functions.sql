-- Migration: Repoint the last 10 analytics RPCs at gold.fact_streams
-- Date: 2026-09-02
-- Purpose: Phase 12 step 4. Finishes the star-schema cutover started in Phase 11
--          migration 010. The 10 functions below are the entire long tail from
--          006_analytics_functions.sql that still read public.streaming_history
--          directly:
--
--            get_discovery_timeline        get_most_repeated_tracks
--            get_artist_loyalty            get_monthly_diversity
--            get_artist_obsessions         get_listening_heatmap
--            get_reflective_insights       get_milestones_list
--            get_weekend_weekday_comparison get_flashback
--
--          After this migration `SELECT proname FROM pg_proc WHERE prosrc
--          ILIKE '%streaming_history%'` returns none of them (V10).
--
--          NOT touched here (already repointed via _mood_rows in 010, or never
--          read the table): get_mood_summary / get_mood_contexts /
--          get_mood_monthly, and everything in 004/005.
--
-- MECHANICAL RULE (highest-severity risk R1 -- casing trap). Each body is
-- copied VERBATIM from 006. The only changes:
--     FROM streaming_history            -> FROM gold.fact_streams
--     master_metadata_album_artist_name -> artist_name
--     master_metadata_track_name        -> track_name
--     master_metadata_album_album_name  -> album_name   (none of the 10 use it)
-- Table aliases (s / w / g / f) are kept exactly as 006 had them. NO other
-- edits: no extra WHERE filters, no is_music, and in particular NEVER a map to
-- dim_artist.artist_key -- gold.fact_streams carries artist_name/track_name as
-- denormalised, case-sensitive text precisely so COUNT(DISTINCT
-- master_metadata_*_name) reproduces bit-for-bit (009's comment; this dataset
-- has 4 rows differing only by artist-name casing, e.g. "KALEO"/"Kaleo").
--
-- GRAIN NOTE / ROADMAP DEVIATION (see UPDATE.md Phase 12 log). The plan
-- predicted a byte-clean API baseline diff for this commit. That only holds if
-- the pre-commit baseline was captured with these 10 already on the deduped
-- gold grain. It was not: public.streaming_history was never deduped or
-- video-stripped (Phase 11 left it as-is; Phase 12 migration 011 only removed
-- the one-time bronze backfill). So these 10 endpoints move by exactly the
-- Phase 12 delta already applied to the hot RPCs in Commit 2 -- for the primary
-- user, 71,052 -> 70,635 (video exclusion + row_fingerprint dedup). Every
-- moved value must be explained by that single grain change; anything else
-- blocks the phase. This is the last streaming_history -> gold cutover; after
-- it, streaming_history has zero readers (INGESTION.md marks it frozen legacy).
--
-- Blocker B2: each CREATE is preceded by its exact DROP FUNCTION IF EXISTS
-- (same signatures as 006).
--
-- Applies after: 011_ingest_state_and_runs.sql
-- Run: python apps/api/db/migrate.py

BEGIN;

DROP FUNCTION IF EXISTS get_discovery_timeline(UUID);
DROP FUNCTION IF EXISTS get_artist_loyalty(INTEGER, UUID);
DROP FUNCTION IF EXISTS get_artist_obsessions(INTEGER, UUID);
DROP FUNCTION IF EXISTS get_reflective_insights(UUID);
DROP FUNCTION IF EXISTS get_weekend_weekday_comparison(UUID);
DROP FUNCTION IF EXISTS get_most_repeated_tracks(INTEGER, UUID);
DROP FUNCTION IF EXISTS get_monthly_diversity(UUID);
DROP FUNCTION IF EXISTS get_listening_heatmap(UUID);
DROP FUNCTION IF EXISTS get_milestones_list(UUID);
DROP FUNCTION IF EXISTS get_flashback(DATE, UUID);

-- ---------------------------------------------------------------------------
-- get_discovery_timeline  (was 006:236; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_discovery_timeline(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    month             TEXT,
    new_artists_count INTEGER
)
LANGUAGE sql
STABLE
AS $$
    WITH firsts AS (
        SELECT
            artist_name AS artist,
            MIN(ts) AS first_ts
        FROM gold.fact_streams
        WHERE user_id = _effective_user_id(p_user_id)
          AND ts IS NOT NULL
          AND artist_name IS NOT NULL
        GROUP BY artist_name
    )
    SELECT to_char(first_ts, 'YYYY-MM'), COUNT(*)::INT
    FROM firsts
    GROUP BY to_char(first_ts, 'YYYY-MM')
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_artist_loyalty  (was 006:269; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_artist_loyalty(
    p_limit INTEGER DEFAULT 20,
    p_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    artist         TEXT,
    return_prob    NUMERIC,
    half_life_days NUMERIC,
    total_streams  INTEGER
)
LANGUAGE sql
STABLE
AS $$
    WITH uid AS (SELECT _effective_user_id(p_user_id) AS id),
    candidates AS (
        SELECT artist_name AS artist, COUNT(*) AS plays
        FROM gold.fact_streams, uid
        WHERE user_id = uid.id
          AND artist_name IS NOT NULL
          AND ts IS NOT NULL
        GROUP BY artist_name
        ORDER BY plays DESC
        LIMIT p_limit
    ),
    gaps AS (
        SELECT artist, gap_days
        FROM (
            SELECT
                s.artist_name AS artist,
                FLOOR(EXTRACT(EPOCH FROM (
                    s.ts - LAG(s.ts) OVER (
                        PARTITION BY s.artist_name
                        ORDER BY s.ts
                    )
                )) / 86400)::INT AS gap_days
            FROM gold.fact_streams s
            JOIN candidates c ON c.artist = s.artist_name
            WHERE s.user_id = (SELECT id FROM uid)
              AND s.ts IS NOT NULL
        ) g
        WHERE gap_days IS NOT NULL AND gap_days > 0
    ),
    per_artist AS (
        SELECT
            c.artist,
            c.plays AS total_streams,
            AVG(g.gap_days)::NUMERIC AS avg_gap,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY g.gap_days) AS median_gap
        FROM candidates c
        JOIN gaps g ON g.artist = c.artist
        WHERE c.plays >= 5
        GROUP BY c.artist, c.plays
    )
    SELECT
        artist,
        ROUND(LEAST(100.0, 100.0 / (1 + avg_gap)), 1),
        ROUND(median_gap::NUMERIC, 1),
        total_streams
    FROM per_artist
    ORDER BY 2 DESC
    LIMIT p_limit;
$$;

-- ---------------------------------------------------------------------------
-- get_artist_obsessions  (was 006:338; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_artist_obsessions(
    p_limit INTEGER DEFAULT 15,
    p_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    artist            TEXT,
    period_start      TEXT,
    period_end        TEXT,
    period_share      NUMERIC,
    streams_in_period INTEGER
)
LANGUAGE sql
STABLE
AS $$
    WITH wk AS (
        SELECT
            date_trunc('week', ts)::date        AS week_start,
            artist_name                         AS artist,
            COUNT(*)                             AS cnt
        FROM gold.fact_streams
        WHERE user_id = _effective_user_id(p_user_id)
          AND ts IS NOT NULL
          AND artist_name IS NOT NULL
        GROUP BY 1, 2
    ),
    totals AS (
        SELECT week_start, SUM(cnt) AS total FROM wk GROUP BY week_start
    )
    SELECT
        w.artist,
        to_char(w.week_start, 'YYYY-MM-DD'),
        to_char(w.week_start + 6, 'YYYY-MM-DD'),
        ROUND(w.cnt * 100.0 / t.total, 1),
        w.cnt::INT
    FROM wk w
    JOIN totals t ON t.week_start = w.week_start
    WHERE t.total >= 10
      AND (w.cnt * 100.0 / t.total) >= 30.0
    ORDER BY 4 DESC
    LIMIT p_limit;
$$;

-- ---------------------------------------------------------------------------
-- get_reflective_insights  (was 006:383; now reads gold.fact_streams) -> jsonb
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_reflective_insights(p_user_id UUID DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_uid              UUID := _effective_user_id(p_user_id);
    v_total            BIGINT;
    v_longest          INT := 0;
    v_hour             INT := 0;
    v_dow              INT := 1;
    v_day              TEXT := 'Monday';
    v_top_artist       TEXT := 'Unknown';
    v_avg_per_day      NUMERIC := 0;
    v_span             INT;
    day_names          TEXT[] := ARRAY['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
BEGIN
    SELECT COUNT(*) INTO v_total
    FROM gold.fact_streams WHERE user_id = v_uid;

    IF v_total = 0 THEN
        RETURN jsonb_build_object(
            'total_streams', 0, 'longest_streak_days', 0,
            'most_active_hour', 0, 'most_active_day', 'Monday',
            'top_artist', 'Unknown', 'avg_streams_per_day', 0,
            'insights', jsonb_build_array()
        );
    END IF;

    -- longest consecutive-day streak (gapless-island trick, as in 004)
    SELECT COALESCE(MAX(len), 0) INTO v_longest FROM (
        SELECT COUNT(*) AS len
        FROM (
            SELECT d,
                   d - (ROW_NUMBER() OVER (ORDER BY d))::INT * INTERVAL '1 day' AS grp
            FROM (
                SELECT DISTINCT ts::date AS d
                FROM gold.fact_streams
                WHERE user_id = v_uid AND ts IS NOT NULL
            ) days
        ) g
        GROUP BY grp
    ) runs;

    SELECT EXTRACT(HOUR FROM ts)::INT INTO v_hour
    FROM gold.fact_streams
    WHERE user_id = v_uid AND ts IS NOT NULL
    GROUP BY EXTRACT(HOUR FROM ts)
    ORDER BY COUNT(*) DESC, 1 ASC
    LIMIT 1;

    SELECT EXTRACT(ISODOW FROM ts)::INT INTO v_dow
    FROM gold.fact_streams
    WHERE user_id = v_uid AND ts IS NOT NULL
    GROUP BY EXTRACT(ISODOW FROM ts)
    ORDER BY COUNT(*) DESC, 1 ASC
    LIMIT 1;
    v_day := day_names[v_dow];

    SELECT artist_name INTO v_top_artist
    FROM gold.fact_streams
    WHERE user_id = v_uid AND artist_name IS NOT NULL
    GROUP BY artist_name
    ORDER BY COUNT(*) DESC, 1 ASC
    LIMIT 1;
    v_top_artist := COALESCE(v_top_artist, 'Unknown');

    SELECT (MAX(ts::date) - MIN(ts::date)) + 1 INTO v_span
    FROM gold.fact_streams WHERE user_id = v_uid AND ts IS NOT NULL;
    IF v_span IS NOT NULL AND v_span > 0 THEN
        v_avg_per_day := ROUND(v_total::NUMERIC / v_span, 1);
    END IF;

    RETURN jsonb_build_object(
        'total_streams', v_total,
        'longest_streak_days', v_longest,
        'most_active_hour', v_hour,
        'most_active_day', v_day,
        'top_artist', v_top_artist,
        'avg_streams_per_day', v_avg_per_day,
        'insights', jsonb_build_array(
            format('You''ve maintained a %s-day listening streak!', v_longest),
            format('Your peak listening hour is %s:00', v_hour),
            format('%ss are your most active listening days', v_day),
            format('%s is your most-played artist', v_top_artist)
        )
    );
END;
$$;

-- ---------------------------------------------------------------------------
-- get_weekend_weekday_comparison  (was 006:478; now reads gold.fact_streams) -> jsonb
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_weekend_weekday_comparison(p_user_id UUID DEFAULT NULL)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    WITH agg AS (
        SELECT
            (EXTRACT(ISODOW FROM ts) >= 6) AS is_weekend,
            COUNT(*)                        AS streams,
            SUM(ms_played) / 3600000.0      AS hours
        FROM gold.fact_streams
        WHERE user_id = _effective_user_id(p_user_id)
          AND ts IS NOT NULL
        GROUP BY (EXTRACT(ISODOW FROM ts) >= 6)
    ),
    wd AS (SELECT * FROM agg WHERE is_weekend = FALSE),
    we AS (SELECT * FROM agg WHERE is_weekend = TRUE)
    SELECT jsonb_build_object(
        'weekday', jsonb_build_object(
            'streams', COALESCE((SELECT streams FROM wd), 0),
            'hours',   COALESCE(ROUND((SELECT hours FROM wd)::NUMERIC, 2), 0),
            'avg_per_day', CASE
                WHEN COALESCE((SELECT streams FROM wd), 0) > 0
                THEN ROUND((SELECT streams FROM wd)::NUMERIC / 5, 1) ELSE 0 END
        ),
        'weekend', jsonb_build_object(
            'streams', COALESCE((SELECT streams FROM we), 0),
            'hours',   COALESCE(ROUND((SELECT hours FROM we)::NUMERIC, 2), 0),
            'avg_per_day', CASE
                WHEN COALESCE((SELECT streams FROM we), 0) > 0
                THEN ROUND((SELECT streams FROM we)::NUMERIC / 2, 1) ELSE 0 END
        )
    );
$$;

-- ---------------------------------------------------------------------------
-- get_most_repeated_tracks  (was 006:518; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_most_repeated_tracks(
    p_limit INTEGER DEFAULT 20,
    p_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    track        TEXT,
    artist       TEXT,
    play_count   INTEGER,
    repeat_score NUMERIC
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        track_name,
        artist_name,
        COUNT(*)::INT,
        ROUND(COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT ts::date), 0), 2)
    FROM gold.fact_streams
    WHERE user_id = _effective_user_id(p_user_id)
      AND ts IS NOT NULL
      AND track_name IS NOT NULL
      AND artist_name IS NOT NULL
    GROUP BY track_name, artist_name
    HAVING COUNT(*) >= 5
    ORDER BY 4 DESC
    LIMIT p_limit;
$$;

-- ---------------------------------------------------------------------------
-- get_monthly_diversity  (was 006:550; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_monthly_diversity(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    month           TEXT,
    unique_artists  INTEGER,
    total_streams   INTEGER,
    diversity_ratio NUMERIC
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        to_char(ts, 'YYYY-MM'),
        COUNT(DISTINCT artist_name)::INT,
        COUNT(*)::INT,
        COALESCE(ROUND(
            COUNT(DISTINCT artist_name) * 100.0
            / NULLIF(COUNT(*), 0), 2), 0)
    FROM gold.fact_streams
    WHERE user_id = _effective_user_id(p_user_id)
      AND ts IS NOT NULL
      AND artist_name IS NOT NULL
    GROUP BY to_char(ts, 'YYYY-MM')
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_listening_heatmap  (was 006:579; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_listening_heatmap(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    day          TEXT,
    hour         INTEGER,
    stream_count INTEGER
)
LANGUAGE sql
STABLE
AS $$
    WITH grid AS (
        SELECT d AS dow, h AS hr
        FROM generate_series(1, 7) d
        CROSS JOIN generate_series(0, 23) h
    ),
    counts AS (
        SELECT
            EXTRACT(ISODOW FROM ts)::INT AS dow,
            EXTRACT(HOUR  FROM ts)::INT  AS hr,
            COUNT(*)                     AS c
        FROM gold.fact_streams
        WHERE user_id = _effective_user_id(p_user_id)
          AND ts IS NOT NULL
        GROUP BY 1, 2
    ),
    names AS (
        SELECT * FROM (VALUES
            (1,'Monday'),(2,'Tuesday'),(3,'Wednesday'),(4,'Thursday'),
            (5,'Friday'),(6,'Saturday'),(7,'Sunday')
        ) AS t(dow, name)
    )
    SELECT n.name, g.hr, COALESCE(c.c, 0)::INT
    FROM grid g
    JOIN names n ON n.dow = g.dow
    LEFT JOIN counts c ON c.dow = g.dow AND c.hr = g.hr
    ORDER BY g.dow, g.hr;
$$;

-- ---------------------------------------------------------------------------
-- get_milestones_list  (was 006:622; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_milestones_list(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    date        TEXT,
    year        INTEGER,
    type        TEXT,
    title       TEXT,
    description TEXT,
    value       INTEGER,
    badge_color TEXT
)
LANGUAGE sql
STABLE
AS $$
    WITH uid AS (SELECT _effective_user_id(p_user_id) AS id),
    days AS (
        SELECT
            ts::date                                         AS d,
            COUNT(*)                                          AS streams,
            SUM(ms_played) / 3600000.0                        AS hours,
            COUNT(DISTINCT artist_name)                       AS artists
        FROM gold.fact_streams, uid
        WHERE user_id = uid.id AND ts IS NOT NULL
        GROUP BY ts::date
    ),
    -- streaks: gapless islands of >= 3 consecutive days, top 10 by length
    islands AS (
        SELECT d, streams,
               d - (ROW_NUMBER() OVER (ORDER BY d))::INT * INTERVAL '1 day' AS grp
        FROM days
    ),
    streaks AS (
        SELECT MIN(d) AS start_d, MAX(d) AS end_d,
               (MAX(d) - MIN(d))::INT + 1 AS len
        FROM islands
        GROUP BY grp
        HAVING (MAX(d) - MIN(d))::INT + 1 >= 3
        ORDER BY len DESC
        LIMIT 10
    ),
    streak_ms AS (
        SELECT
            to_char(start_d, 'YYYY-MM-DD')                   AS date,
            EXTRACT(YEAR FROM start_d)::INT                  AS year,
            'streak'                                         AS type,
            format('%s-Day Listening Streak', len)           AS title,
            format('From %s to %s',
                   to_char(start_d, 'Mon DD'),
                   to_char(end_d,   'Mon DD, YYYY'))         AS description,
            len                                             AS value,
            '#2dd881'                                        AS badge_color
        FROM streaks
    ),
    -- top listening days: top 15 by streams, only those with >= 50
    top_days AS (
        SELECT d, streams, hours
        FROM days
        ORDER BY streams DESC
        LIMIT 15
    ),
    top_day_ms AS (
        SELECT
            to_char(d, 'YYYY-MM-DD')                         AS date,
            EXTRACT(YEAR FROM d)::INT                        AS year,
            'top_day'                                        AS type,
            format('%s Streams in One Day', streams)         AS title,
            format('Peak listening day on %s with %s hours',
                   to_char(d, 'Mon DD, YYYY'),
                   ROUND(hours::NUMERIC, 1))                 AS description,
            streams::INT                                     AS value,
            '#4ea699'                                        AS badge_color
        FROM top_days
        WHERE streams >= 50
    ),
    -- first discoveries: per-artist MIN(ts), first 20 by date, only if the
    -- artist is in the user's top-20 by play count
    firsts AS (
        SELECT
            artist_name AS artist,
            MIN(ts)                           AS first_ts
        FROM gold.fact_streams, uid
        WHERE user_id = uid.id
          AND ts IS NOT NULL
          AND artist_name IS NOT NULL
        GROUP BY artist_name
    ),
    top20 AS (
        SELECT artist_name AS artist
        FROM gold.fact_streams, uid
        WHERE user_id = uid.id
          AND artist_name IS NOT NULL
        GROUP BY artist_name
        ORDER BY COUNT(*) DESC
        LIMIT 20
    ),
    -- JSON loader: take the 20 earliest-discovered artists, THEN keep only
    -- those also in the top-20 by play count (so 0..20 rows, usually fewer).
    firsts_20 AS (
        SELECT artist, first_ts
        FROM firsts
        ORDER BY first_ts
        LIMIT 20
    ),
    first_artist_ms AS (
        SELECT
            to_char(f.first_ts::date, 'YYYY-MM-DD')          AS date,
            EXTRACT(YEAR FROM f.first_ts)::INT               AS year,
            'first_artist'                                   AS type,
            format('Discovered %s', f.artist)                AS title,
            format('First listened to %s on %s',
                   f.artist, to_char(f.first_ts, 'Mon DD, YYYY')) AS description,
            0                                               AS value,
            '#6fedb7'                                        AS badge_color
        FROM firsts_20 f
        JOIN top20 t ON t.artist = f.artist
    ),
    -- diversity: top 10 days by distinct-artist count, only those with >= 20
    diverse AS (
        SELECT d, artists
        FROM days
        ORDER BY artists DESC
        LIMIT 10
    ),
    diversity_ms AS (
        SELECT
            to_char(d, 'YYYY-MM-DD')                         AS date,
            EXTRACT(YEAR FROM d)::INT                        AS year,
            'diversity'                                      AS type,
            format('%s Different Artists', artists)          AS title,
            format('Explored %s artists on %s',
                   artists, to_char(d, 'Mon DD, YYYY'))      AS description,
            artists::INT                                     AS value,
            '#140d4f'                                        AS badge_color
        FROM diverse
        WHERE artists >= 20
    )
    SELECT * FROM streak_ms
    UNION ALL SELECT * FROM top_day_ms
    UNION ALL SELECT * FROM first_artist_ms
    UNION ALL SELECT * FROM diversity_ms
    ORDER BY date DESC;
$$;

-- ---------------------------------------------------------------------------
-- get_flashback  (was 006:771; now reads gold.fact_streams)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_flashback(
    p_date DATE,
    p_user_id UUID DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    WITH uid AS (SELECT _effective_user_id(p_user_id) AS id),
    day AS (
        SELECT s.*
        FROM gold.fact_streams s, uid
        WHERE s.user_id = uid.id
          AND s.ts IS NOT NULL
          AND s.ts::date = p_date
    ),
    agg AS (
        SELECT
            COUNT(*)                                              AS streams,
            SUM(ms_played) / 3600000.0                            AS hours,
            COUNT(DISTINCT artist_name)                           AS uniq_artists,
            COUNT(DISTINCT track_name)                            AS uniq_tracks,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)              AS skipped,
            MIN(ts)                                               AS first_ts,
            MAX(ts)                                               AS last_ts
        FROM day
    ),
    top_artists AS (
        SELECT jsonb_agg(jsonb_build_object('artist', artist, 'streams', c)
                         ORDER BY c DESC) AS arr
        FROM (
            SELECT artist_name AS artist, COUNT(*) AS c
            FROM day
            WHERE artist_name IS NOT NULL
            GROUP BY 1 ORDER BY c DESC LIMIT 5
        ) t
    ),
    top_tracks AS (
        SELECT jsonb_agg(jsonb_build_object(
                   'track', track, 'artist', artist, 'plays', c)
                   ORDER BY c DESC) AS arr
        FROM (
            SELECT track_name AS track,
                   artist_name AS artist,
                   COUNT(*) AS c
            FROM day
            WHERE track_name IS NOT NULL
              AND artist_name IS NOT NULL
            GROUP BY 1, 2 ORDER BY c DESC LIMIT 5
        ) t
    )
    SELECT CASE WHEN a.streams = 0 THEN NULL ELSE jsonb_build_object(
        'date', to_char(p_date, 'YYYY-MM-DD'),
        'day_of_week', to_char(p_date, 'FMDay'),
        'streams', a.streams,
        'hours', ROUND(a.hours::NUMERIC, 2),
        'unique_artists', a.uniq_artists,
        'unique_tracks', a.uniq_tracks,
        'skipped', a.skipped,
        'skip_rate', CASE WHEN a.streams > 0
            THEN ROUND(a.skipped * 100.0 / a.streams, 1) ELSE 0 END,
        'first_stream', to_char(a.first_ts, 'HH12:MI AM'),
        'last_stream',  to_char(a.last_ts,  'HH12:MI AM'),
        'listening_duration', CASE WHEN a.first_ts IS NOT NULL AND a.last_ts IS NOT NULL
            THEN to_char(EXTRACT(EPOCH FROM (a.last_ts - a.first_ts)) / 3600.0, 'FM990.0') || ' hours'
            ELSE NULL END,
        'top_artists', COALESCE((SELECT arr FROM top_artists), '[]'::jsonb),
        'top_tracks',  COALESCE((SELECT arr FROM top_tracks),  '[]'::jsonb)
    ) END
    FROM agg a;
$$;

COMMIT;
