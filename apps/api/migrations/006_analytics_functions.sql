-- Migration: User-scoped analytics functions (mood / discovery / patterns / milestones)
-- Date: 2026-08-30
-- Purpose: Port the SQL-friendly methods of the JSON SpotifyDataLoader
--          (apps/api/app/services/data_loader.py) into user-scoped Postgres
--          functions so every analytics page can read per-user data from the DB
--          instead of the primary-user-only in-memory JSON loader.
--
--          Heavy compute (session KMeans clustering, the content-based
--          recommender, the Markov simulator) is NOT here -- it stays in Python
--          in SupabaseDataLoader, fed by a per-user row fetch, because it cannot
--          be expressed as a single SQL statement.
--
-- Conventions (identical to 004_user_scoped_functions.sql):
--   * every function's param list ends with  p_user_id UUID DEFAULT NULL
--     (tuning params such as p_limit come first)
--   * bodies filter  WHERE user_id = _effective_user_id(p_user_id)
--     (_effective_user_id already exists from 004: arg, else primary user)
--   * DROP FUNCTION IF EXISTS first, so a re-apply never hits
--     "function ... is not unique" from supabase-py RPC calls
--
-- Mood metrics (valence / energy / danceability) reproduce
-- SpotifyDataLoader._calculate_mood_metrics exactly:
--   valence   base 0.5; +0.15 weekend; +0.15 if hour 10..20,
--             +0.05 if hour 6..9 or 21..23, -0.10 otherwise; clamp 0..1
--   energy    base 0.5; +0.25 hour 6..12; +0.15 hour 13..18;
--             +0.05 hour 19..22; -0.15 otherwise; clamp 0..1
--   dance     base 0.5; +0.25 if ms_played >= 180000;
--             +0.10 if ms_played >= 60000; -0.15 otherwise;
--             -0.20 if skipped; clamp 0..1
-- weekend = ISODOW >= 6 (Sat=6, Sun=7), matching Python dt.weekday() >= 5.
--
-- Applies after: 005_compare_functions.sql
-- Run: psql "<conn>" -v ON_ERROR_STOP=1 -f 006_analytics_functions.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Drop prior signatures (none shipped before, but keep the pattern so a
--    second apply of a changed signature is safe).
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS get_mood_summary(INTEGER, UUID);
DROP FUNCTION IF EXISTS get_mood_contexts(UUID);
DROP FUNCTION IF EXISTS get_mood_monthly(UUID);
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
-- Shared helper: per-row mood metrics for one user, as a set-returning view.
-- Every mood function selects from this.
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
        FROM streaming_history s
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

-- ---------------------------------------------------------------------------
-- get_mood_summary  (ports get_mood_summary)
--   window: ts >= now() - p_window_days days. Python uses UTC now; so do we.
--   averages rounded 3dp; NULL when sample_size = 0.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_mood_summary(
    p_window_days INTEGER DEFAULT 30,
    p_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    window_days      INTEGER,
    avg_valence      NUMERIC,
    avg_energy       NUMERIC,
    avg_danceability NUMERIC,
    sample_size      INTEGER
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        p_window_days,
        ROUND(AVG(valence), 3),
        ROUND(AVG(energy), 3),
        ROUND(AVG(dance), 3),
        COUNT(*)::INT
    FROM _mood_rows(p_user_id)
    WHERE ts >= (now() AT TIME ZONE 'UTC') - make_interval(days => p_window_days);
$$;

-- ---------------------------------------------------------------------------
-- get_mood_contexts  (ports get_mood_contexts)  -> single jsonb object
--   { weekday_vs_weekend: { weekday: {...}, weekend: {...} },
--     by_platform: { <platform>: {...}, ... } }   leaf = 4 keys
--   by_platform only platforms with sample_size >= 10.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_mood_contexts(p_user_id UUID DEFAULT NULL)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    WITH rows AS (
        SELECT * FROM _mood_rows(p_user_id)
    ),
    wk AS (
        SELECT
            is_weekend,
            ROUND(AVG(valence), 3) AS av,
            ROUND(AVG(energy), 3)  AS ae,
            ROUND(AVG(dance), 3)   AS ad,
            COUNT(*)::INT          AS n
        FROM rows
        GROUP BY is_weekend
    ),
    pf AS (
        SELECT
            platform,
            ROUND(AVG(valence), 3) AS av,
            ROUND(AVG(energy), 3)  AS ae,
            ROUND(AVG(dance), 3)   AS ad,
            COUNT(*)::INT          AS n
        FROM rows
        GROUP BY platform
        HAVING COUNT(*) >= 10
    )
    SELECT jsonb_build_object(
        'weekday_vs_weekend', jsonb_build_object(
            'weekday', (
                SELECT jsonb_build_object(
                    'avg_valence', av, 'avg_energy', ae,
                    'avg_danceability', ad, 'sample_size', n)
                FROM wk WHERE is_weekend = FALSE
            ),
            'weekend', (
                SELECT jsonb_build_object(
                    'avg_valence', av, 'avg_energy', ae,
                    'avg_danceability', ad, 'sample_size', n)
                FROM wk WHERE is_weekend = TRUE
            )
        ),
        'by_platform', COALESCE((
            SELECT jsonb_object_agg(platform, jsonb_build_object(
                'avg_valence', av, 'avg_energy', ae,
                'avg_danceability', ad, 'sample_size', n))
            FROM pf
        ), '{}'::jsonb)
    );
$$;

-- ---------------------------------------------------------------------------
-- get_mood_monthly  (ports get_mood_monthly)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_mood_monthly(p_user_id UUID DEFAULT NULL)
RETURNS TABLE (
    month            TEXT,
    avg_valence      NUMERIC,
    avg_energy       NUMERIC,
    avg_danceability NUMERIC,
    sample_size      INTEGER
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        to_char(ts, 'YYYY-MM'),
        ROUND(AVG(valence), 3),
        ROUND(AVG(energy), 3),
        ROUND(AVG(dance), 3),
        COUNT(*)::INT
    FROM _mood_rows(p_user_id)
    GROUP BY to_char(ts, 'YYYY-MM')
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_discovery_timeline  (ports get_discovery_timeline)
--   NOTE: JSON loader records first-seen in iteration order (not chronological);
--   MIN(ts) here is the chronologically-correct first listen. Counts per month
--   match in practice; this is a deliberate correctness improvement.
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
            master_metadata_album_artist_name AS artist,
            MIN(ts) AS first_ts
        FROM streaming_history
        WHERE user_id = _effective_user_id(p_user_id)
          AND ts IS NOT NULL
          AND master_metadata_album_artist_name IS NOT NULL
        GROUP BY master_metadata_album_artist_name
    )
    SELECT to_char(first_ts, 'YYYY-MM'), COUNT(*)::INT
    FROM firsts
    GROUP BY to_char(first_ts, 'YYYY-MM')
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_artist_loyalty  (ports get_artist_loyalty)
--   candidate set = top p_limit artists by play count (JSON takes top(limit*2)
--   then keeps the first `limit` -> net effect = top `limit`).
--   require >= 5 plays; gaps = positive day-diffs between consecutive plays.
--   return_prob = round(least(100, 100/(1+avg_gap)), 1)
--   half_life_days = round(median(gaps), 1)
--   order by return_prob desc, limit p_limit.
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
        SELECT master_metadata_album_artist_name AS artist, COUNT(*) AS plays
        FROM streaming_history, uid
        WHERE user_id = uid.id
          AND master_metadata_album_artist_name IS NOT NULL
          AND ts IS NOT NULL
        GROUP BY master_metadata_album_artist_name
        ORDER BY plays DESC
        LIMIT p_limit
    ),
    gaps AS (
        SELECT artist, gap_days
        FROM (
            SELECT
                s.master_metadata_album_artist_name AS artist,
                FLOOR(EXTRACT(EPOCH FROM (
                    s.ts - LAG(s.ts) OVER (
                        PARTITION BY s.master_metadata_album_artist_name
                        ORDER BY s.ts
                    )
                )) / 86400)::INT AS gap_days
            FROM streaming_history s
            JOIN candidates c ON c.artist = s.master_metadata_album_artist_name
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
-- get_artist_obsessions  (ports get_artist_obsessions)
--   week key = Monday (date_trunc('week', ts)); per (week, artist) share =
--   count*100/week_total; week_total >= 10; emit share >= 30.0;
--   order by share desc, limit p_limit. period_end = period_start + 6.
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
            master_metadata_album_artist_name   AS artist,
            COUNT(*)                             AS cnt
        FROM streaming_history
        WHERE user_id = _effective_user_id(p_user_id)
          AND ts IS NOT NULL
          AND master_metadata_album_artist_name IS NOT NULL
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
-- get_reflective_insights  (ports get_reflective_insights)  -> jsonb
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
    FROM streaming_history WHERE user_id = v_uid;

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
                FROM streaming_history
                WHERE user_id = v_uid AND ts IS NOT NULL
            ) days
        ) g
        GROUP BY grp
    ) runs;

    SELECT EXTRACT(HOUR FROM ts)::INT INTO v_hour
    FROM streaming_history
    WHERE user_id = v_uid AND ts IS NOT NULL
    GROUP BY EXTRACT(HOUR FROM ts)
    ORDER BY COUNT(*) DESC, 1 ASC
    LIMIT 1;

    SELECT EXTRACT(ISODOW FROM ts)::INT INTO v_dow
    FROM streaming_history
    WHERE user_id = v_uid AND ts IS NOT NULL
    GROUP BY EXTRACT(ISODOW FROM ts)
    ORDER BY COUNT(*) DESC, 1 ASC
    LIMIT 1;
    v_day := day_names[v_dow];

    SELECT master_metadata_album_artist_name INTO v_top_artist
    FROM streaming_history
    WHERE user_id = v_uid AND master_metadata_album_artist_name IS NOT NULL
    GROUP BY master_metadata_album_artist_name
    ORDER BY COUNT(*) DESC, 1 ASC
    LIMIT 1;
    v_top_artist := COALESCE(v_top_artist, 'Unknown');

    SELECT (MAX(ts::date) - MIN(ts::date)) + 1 INTO v_span
    FROM streaming_history WHERE user_id = v_uid AND ts IS NOT NULL;
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
-- get_weekend_weekday_comparison  (ports get_weekend_weekday_comparison) -> jsonb
--   avg_per_day = streams/5 (weekday) or /2 (weekend), 1dp; 0 when streams 0.
--   hours 2dp. weekend = ISODOW >= 6.
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
        FROM streaming_history
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
-- get_most_repeated_tracks  (ports get_most_repeated_tracks)
--   per (track, artist): count(*) and count(distinct ts::date); count >= 5;
--   repeat_score = round(count / distinct_dates, 2); order desc, limit.
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
        master_metadata_track_name,
        master_metadata_album_artist_name,
        COUNT(*)::INT,
        ROUND(COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT ts::date), 0), 2)
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id)
      AND ts IS NOT NULL
      AND master_metadata_track_name IS NOT NULL
      AND master_metadata_album_artist_name IS NOT NULL
    GROUP BY master_metadata_track_name, master_metadata_album_artist_name
    HAVING COUNT(*) >= 5
    ORDER BY 4 DESC
    LIMIT p_limit;
$$;

-- ---------------------------------------------------------------------------
-- get_monthly_diversity  (ports get_monthly_diversity)
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
        COUNT(DISTINCT master_metadata_album_artist_name)::INT,
        COUNT(*)::INT,
        COALESCE(ROUND(
            COUNT(DISTINCT master_metadata_album_artist_name) * 100.0
            / NULLIF(COUNT(*), 0), 2), 0)
    FROM streaming_history
    WHERE user_id = _effective_user_id(p_user_id)
      AND ts IS NOT NULL
      AND master_metadata_album_artist_name IS NOT NULL
    GROUP BY to_char(ts, 'YYYY-MM')
    ORDER BY 1;
$$;

-- ---------------------------------------------------------------------------
-- get_listening_heatmap  (ports get_listening_heatmap)
--   exactly 168 rows: day Mon..Sun (outer), hour 0..23 (inner), missing -> 0.
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
        FROM streaming_history
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
-- get_milestones_list  (ports get_milestones_list)
--   4 UNION ALL blocks (streak / top_day / first_artist / diversity),
--   final ORDER BY date DESC. Titles/descriptions reproduce the Python
--   f-strings; Python's strftime('%b %d, %Y') -> to_char(d,'Mon DD, YYYY').
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
            COUNT(DISTINCT master_metadata_album_artist_name) AS artists
        FROM streaming_history, uid
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
            master_metadata_album_artist_name AS artist,
            MIN(ts)                           AS first_ts
        FROM streaming_history, uid
        WHERE user_id = uid.id
          AND ts IS NOT NULL
          AND master_metadata_album_artist_name IS NOT NULL
        GROUP BY master_metadata_album_artist_name
    ),
    top20 AS (
        SELECT master_metadata_album_artist_name AS artist
        FROM streaming_history, uid
        WHERE user_id = uid.id
          AND master_metadata_album_artist_name IS NOT NULL
        GROUP BY master_metadata_album_artist_name
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
-- get_flashback  (ports get_flashback, success shape only)
--   Route handles the invalid-date and no-data shapes. Here: one jsonb object
--   for a date that has streams; returns NULL when the date has none.
--   Python strftime('%I:%M %p') -> to_char(t,'HH12:MI AM') (upper AM/PM);
--   Python '%A' -> to_char(d,'FMDay').
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
        FROM streaming_history s, uid
        WHERE s.user_id = uid.id
          AND s.ts IS NOT NULL
          AND s.ts::date = p_date
    ),
    agg AS (
        SELECT
            COUNT(*)                                              AS streams,
            SUM(ms_played) / 3600000.0                            AS hours,
            COUNT(DISTINCT master_metadata_album_artist_name)     AS uniq_artists,
            COUNT(DISTINCT master_metadata_track_name)            AS uniq_tracks,
            SUM(CASE WHEN skipped THEN 1 ELSE 0 END)              AS skipped,
            MIN(ts)                                               AS first_ts,
            MAX(ts)                                               AS last_ts
        FROM day
    ),
    top_artists AS (
        SELECT jsonb_agg(jsonb_build_object('artist', artist, 'streams', c)
                         ORDER BY c DESC) AS arr
        FROM (
            SELECT master_metadata_album_artist_name AS artist, COUNT(*) AS c
            FROM day
            WHERE master_metadata_album_artist_name IS NOT NULL
            GROUP BY 1 ORDER BY c DESC LIMIT 5
        ) t
    ),
    top_tracks AS (
        SELECT jsonb_agg(jsonb_build_object(
                   'track', track, 'artist', artist, 'plays', c)
                   ORDER BY c DESC) AS arr
        FROM (
            SELECT master_metadata_track_name AS track,
                   master_metadata_album_artist_name AS artist,
                   COUNT(*) AS c
            FROM day
            WHERE master_metadata_track_name IS NOT NULL
              AND master_metadata_album_artist_name IS NOT NULL
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
