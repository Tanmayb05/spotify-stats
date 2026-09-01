-- Migration: Gold star schema -- dims + fact + public compatibility views
-- Date: 2026-09-01
-- Purpose: Phase 11 step 2. Create gold.dim_user/dim_time/dim_artist/dim_track/
--          dim_album, gold.fact_streams, gold.track_lyrics (metadata only, D4),
--          gold.recommendation_events (empty, Phase 15 human-eval loop), plus
--          unqualified compatibility views in `public` so Python callers never
--          need a schema-qualified name (Blocker B1 -- see 008's header and the
--          Phase 11 plan doc). Population (dims + fact rows) happens in
--          scripts/build_star_schema.py, not here; this migration is DDL-only.
--
-- Design decisions applied here (full rationale in the Phase 11 plan doc /
-- documentation/DATA_MODEL.md):
--   D1 -- dim_track.mood_proxy_* ship as columns, defaulting audio_source='none'.
--         No real audio-features data exists in this repo; see the COMMENT ON
--         COLUMN below and DATA_MODEL.md. Live mood numbers still come from
--         _mood_rows' arithmetic (006/010), which this migration does not touch.
--   D3 -- natural keys: artist_key = lower(trim(artist_name)); track_key =
--         spotify_track_uri, else 'hash:' || md5(lower(trim(track))||'|||'||
--         lower(trim(artist))); dim_time grain (date, hour); dim_user reuses
--         existing users.id UUIDs verbatim (no re-keying).
--   D4 -- gold.track_lyrics stores metadata only (has_lyrics/source/lang/
--         word_count). No lyrics text column exists in this schema, ever.
--   D6 -- fact_streams grain = one play event, 1:1 with silver.streams / source.
--         No dedup in this phase (Phase 12 owns row_fingerprint dedup).
--
-- Applies after: 008_medallion_schemas.sql
-- Run: python apps/api/db/migrate.py

BEGIN;

-- ---------------------------------------------------------------------------
-- gold.dim_user -- reuses users.id verbatim (D3). Thin dimension, no re-keying.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_user (
    user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    username      TEXT NOT NULL,
    display_name  TEXT,
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE gold.dim_user IS 'Thin dimension mirroring users; user_id is the same UUID (no re-keying, D3).';

-- ---------------------------------------------------------------------------
-- gold.dim_time -- grain (date, hour); surrogate time_key = date*100 + hour.
-- Generated over the observed streaming_history range only (D3), not a century
-- of empty rows.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_time (
    time_key    INTEGER PRIMARY KEY,        -- YYYYMMDD * 100 + hour
    date        DATE NOT NULL,
    hour        SMALLINT NOT NULL CHECK (hour BETWEEN 0 AND 23),
    year        SMALLINT NOT NULL,
    month       SMALLINT NOT NULL,
    day         SMALLINT NOT NULL,
    iso_dow     SMALLINT NOT NULL,          -- 1=Mon .. 7=Sun (matches EXTRACT(ISODOW))
    is_weekend  BOOLEAN NOT NULL,           -- iso_dow >= 6, matches _mood_rows / 006
    week_start  DATE NOT NULL               -- date_trunc('week', date), Monday
);
COMMENT ON TABLE gold.dim_time IS
    'Grain (date, hour). time_key = YYYYMMDD*100+hour. Generated only over the observed range.';

CREATE INDEX IF NOT EXISTS idx_dim_time_date ON gold.dim_time(date);

-- ---------------------------------------------------------------------------
-- gold.dim_artist -- natural key artist_key = lower(trim(artist_name)) (D3).
-- spotify_artist_id is NOT the natural key: only ~4,216 of ~4,342 artists have
-- one in this dataset (measured in the Phase 11 plan).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_artist (
    artist_key          TEXT PRIMARY KEY,   -- lower(trim(artist_name))
    artist_name         TEXT NOT NULL,      -- display form, first-seen casing
    spotify_artist_id   TEXT,
    genres              TEXT[],             -- from artists_info.json (Spotify-reported)
    genres_enriched     TEXT[],             -- from backfill_artist_tags.py (MusicBrainz/Last.fm, D5)
    popularity          INTEGER,
    followers           BIGINT,
    audio_source        TEXT NOT NULL DEFAULT 'none'
                         CHECK (audio_source IN ('none', 'enriched', 'proxy_heuristic')),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE gold.dim_artist IS
    'Natural key = lower(trim(artist_name)), matching data_loader.py''s existing normalization (D3).';
COMMENT ON COLUMN gold.dim_artist.genres IS
    'Spotify-reported genres from outputs/data/artists_info.json (load_enrichment_to_db.py).';
COMMENT ON COLUMN gold.dim_artist.genres_enriched IS
    'MusicBrainz/Last.fm tags from the opt-in backfill_artist_tags.py script (Decision D5). '
    'NULL until that script is run; the phase completes without it (skippable).';

CREATE INDEX IF NOT EXISTS idx_dim_artist_spotify_id ON gold.dim_artist(spotify_artist_id);

-- ---------------------------------------------------------------------------
-- gold.dim_track -- natural key track_key = spotify_track_uri, else a hash
-- fallback covering URI-less rows (D3), matching the recommender's existing
-- "name|||artist" fallback convention (data_loader.py).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_track (
    track_key           TEXT PRIMARY KEY,
    spotify_track_uri   TEXT,               -- NULL for the hash-fallback rows
    track_name          TEXT NOT NULL,
    artist_key           TEXT REFERENCES gold.dim_artist(artist_key),
    artist_name          TEXT,
    album_name           TEXT,
    duration_ms           INTEGER,
    explicit               BOOLEAN,
    popularity             INTEGER,
    release_year            SMALLINT,

    -- D1: mood_proxy_* are NOT backed by real audio-features data. No such
    -- data exists anywhere in this repo (Spotify's /audio-features endpoint
    -- was deprecated for new apps in Nov 2024). Columns exist for a future
    -- phase to populate from another source; audio_source defaults to 'none'
    -- so a reader can tell they are unpopulated rather than silently zero.
    -- Live mood charts are unaffected: they read _mood_rows' arithmetic
    -- heuristic (derived from hour-of-day/ms_played), not these columns.
    mood_proxy_valence      NUMERIC,
    mood_proxy_energy       NUMERIC,
    mood_proxy_danceability NUMERIC,
    audio_source            TEXT NOT NULL DEFAULT 'none'
                             CHECK (audio_source IN ('none', 'enriched', 'proxy_heuristic')),

    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE gold.dim_track IS
    'Natural key = spotify_track_uri, else ''hash:''||md5(lower(trim(track))||''|||''||lower(trim(artist))) '
    'for the ~139 URI-less rows (D3). audio_source=''enriched'' means row came from songs_info.json.';
COMMENT ON COLUMN gold.dim_track.mood_proxy_valence IS
    'UNPOPULATED (Decision D1): no real Spotify audio-features data exists in this repo. '
    'Do not trust as a real value while audio_source=''none''. See DATA_MODEL.md.';
COMMENT ON COLUMN gold.dim_track.mood_proxy_energy IS
    'UNPOPULATED (Decision D1): see mood_proxy_valence comment and DATA_MODEL.md.';
COMMENT ON COLUMN gold.dim_track.mood_proxy_danceability IS
    'UNPOPULATED (Decision D1): see mood_proxy_valence comment and DATA_MODEL.md.';

CREATE INDEX IF NOT EXISTS idx_dim_track_uri ON gold.dim_track(spotify_track_uri);
CREATE INDEX IF NOT EXISTS idx_dim_track_artist_key ON gold.dim_track(artist_key);
CREATE INDEX IF NOT EXISTS idx_dim_track_audio_source ON gold.dim_track(audio_source);

-- ---------------------------------------------------------------------------
-- gold.dim_album -- thin; mostly for future drill-down, not used by 010's RPCs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_album (
    album_key    TEXT PRIMARY KEY,   -- lower(trim(album_name)) || '|||' || artist_key
    album_name   TEXT NOT NULL,
    artist_key   TEXT REFERENCES gold.dim_artist(artist_key),
    release_year SMALLINT
);
COMMENT ON TABLE gold.dim_album IS 'Thin album dimension keyed on (album_name, artist_key).';

-- ---------------------------------------------------------------------------
-- gold.fact_streams -- grain = one play event (D6). 1:1 with source rows;
-- NOT VALID FKs initially so the bulk load in build_star_schema.py is not
-- slowed by per-row checks, VALIDATEd after.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.fact_streams (
    stream_id       BIGSERIAL PRIMARY KEY,
    _ingest_id      BIGINT,             -- traces back to bronze.raw_streams, for Phase 12/13
    user_id         UUID NOT NULL REFERENCES gold.dim_user(user_id) ON DELETE CASCADE,
    time_key        INTEGER REFERENCES gold.dim_time(time_key),
    artist_key      TEXT REFERENCES gold.dim_artist(artist_key),
    track_key       TEXT REFERENCES gold.dim_track(track_key),
    album_key       TEXT REFERENCES gold.dim_album(album_key),

    -- Denormalized, UN-normalized (raw casing) names, copied verbatim from
    -- silver.streams / the source export row. Deliberate degenerate-dimension
    -- columns: migration 010's rewritten monthly_stats/top_artists/top_tracks
    -- MUST reproduce the exact pre-star COUNT(DISTINCT master_metadata_*_name)
    -- semantics (case-sensitive, e.g. "KALEO" vs "Kaleo" count as different
    -- artists in the source data -- confirmed 4 such rows in this dataset).
    -- Grouping by dim_artist.artist_key (lower/trim-normalized, D3) would
    -- silently merge those and change the numbers, which V4's baseline diff
    -- exists specifically to catch. artist_key/track_key above are still the
    -- FK path for joins; these are for exact-text aggregation only.
    artist_name     TEXT,
    track_name      TEXT,
    album_name      TEXT,

    ts              TIMESTAMPTZ NOT NULL,   -- kept alongside time_key for exact-timestamp queries
    ms_played       INTEGER NOT NULL,
    skipped         BOOLEAN NOT NULL DEFAULT FALSE,
    shuffle         BOOLEAN NOT NULL DEFAULT FALSE,
    offline         BOOLEAN NOT NULL DEFAULT FALSE,
    incognito_mode  BOOLEAN NOT NULL DEFAULT FALSE,
    reason_start    TEXT,
    reason_end      TEXT,
    platform        TEXT,
    conn_country    VARCHAR(2),
    is_music        BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE gold.fact_streams IS
    'Grain = one play event. Row count MUST equal public.streaming_history exactly, per user (V1). '
    'No dedup in Phase 11 (D6) -- Phase 12 owns row_fingerprint-based dedup.';

CREATE INDEX IF NOT EXISTS idx_fact_streams_user_ts ON gold.fact_streams(user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_fact_streams_user_artist ON gold.fact_streams(user_id, artist_key);
CREATE INDEX IF NOT EXISTS idx_fact_streams_user_track ON gold.fact_streams(user_id, track_key);
CREATE INDEX IF NOT EXISTS idx_fact_streams_time_key ON gold.fact_streams(time_key);
CREATE INDEX IF NOT EXISTS idx_fact_streams_ingest_id ON gold.fact_streams(_ingest_id);
CREATE INDEX IF NOT EXISTS idx_fact_streams_user_artist_name ON gold.fact_streams(user_id, artist_name);
CREATE INDEX IF NOT EXISTS idx_fact_streams_user_track_name ON gold.fact_streams(user_id, track_name, artist_name);

-- ---------------------------------------------------------------------------
-- gold.track_lyrics -- METADATA ONLY (Decision D4). No lyrics text column
-- exists here or anywhere in this migration. lyrics.json (14MB, third-party
-- copyrighted text) is read once by load_enrichment_to_db.py to compute
-- word_count/lang, then the text is discarded. source file stays gitignored.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.track_lyrics (
    track_key   TEXT PRIMARY KEY REFERENCES gold.dim_track(track_key),
    has_lyrics  BOOLEAN NOT NULL DEFAULT FALSE,
    source      TEXT,           -- e.g. 'genius' -- provenance only, never the text itself
    lang        TEXT,
    word_count  INTEGER,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE gold.track_lyrics IS
    'METADATA ONLY (Decision D4): has_lyrics/source/lang/word_count. '
    'No lyrics text is stored here or anywhere in this schema -- third-party copyrighted content, '
    'and Phase 9 already spent a phase purging exactly this class of blob from history.';

-- ---------------------------------------------------------------------------
-- gold.recommendation_events -- empty for now; Phase 15's human-eval loop.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.recommendation_events (
    event_id      BIGSERIAL PRIMARY KEY,
    user_id       UUID REFERENCES gold.dim_user(user_id) ON DELETE CASCADE,
    track_key     TEXT REFERENCES gold.dim_track(track_key),
    recommender   TEXT,           -- which algorithm produced this (Phase 15: popularity/content/cf/hybrid)
    score         NUMERIC,
    rating        SMALLINT,       -- human-eval rating, Phase 15
    shown_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    rated_at      TIMESTAMPTZ
);
COMMENT ON TABLE gold.recommendation_events IS
    'Empty as of Phase 11. Phase 15''s human-eval loop (blind rating mode, human-vs-offline comparison) writes here.';

-- ---------------------------------------------------------------------------
-- Compatibility views (Blocker B1): unqualified names in `public` so
-- LocalBackend.select()/rpc() and PostgREST's .table() never need a dotted
-- schema-qualified identifier. backends.py's _IDENT_RE stays untouched.
-- These are read-only conveniences; nothing in Python writes through them.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.gold_fact_streams AS SELECT * FROM gold.fact_streams;
CREATE OR REPLACE VIEW public.gold_dim_user     AS SELECT * FROM gold.dim_user;
CREATE OR REPLACE VIEW public.gold_dim_time     AS SELECT * FROM gold.dim_time;
CREATE OR REPLACE VIEW public.gold_dim_artist   AS SELECT * FROM gold.dim_artist;
CREATE OR REPLACE VIEW public.gold_dim_track    AS SELECT * FROM gold.dim_track;
CREATE OR REPLACE VIEW public.gold_dim_album    AS SELECT * FROM gold.dim_album;
CREATE OR REPLACE VIEW public.gold_track_lyrics AS SELECT * FROM gold.track_lyrics;

COMMENT ON VIEW public.gold_fact_streams IS
    'Unqualified compatibility view over gold.fact_streams (Blocker B1) -- lets '
    'LocalBackend.select()/SupabaseBackend.select() reach it without a dotted schema name.';

COMMIT;
