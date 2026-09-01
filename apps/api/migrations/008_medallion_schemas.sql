-- Migration: Medallion schemas -- bronze (raw landing) + silver (typed/normalized)
-- Date: 2026-09-01
-- Purpose: Phase 11 step 1. Introduce bronze/silver/gold schemas and populate the
--          bronze + silver layers from the existing public.streaming_history table.
--          gold (star schema) is 009; MVs/RPCs repointed at gold are 010.
--
--          bronze.raw_streams is an append-only landing table: every column from
--          streaming_history plus an ingest audit trail (_ingest_id, _source_file,
--          _ingested_at, _raw jsonb). Phase 12's Dagster pipeline lands directly
--          here; this migration backfills it once from the existing table so the
--          star schema (009) has something to build from today.
--
--          silver.streams is typed, normalized (lower/trim on join-key columns),
--          FK-ready. NO ip_addr column -- Phase 9 purged it from history and it
--          must not be reintroduced into a new layer (hard constraint, V10).
--
-- Applies after: 007_mask_user_names.sql
-- Run: python apps/api/db/migrate.py   (or psql -f, per prior migrations)

BEGIN;

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

COMMENT ON SCHEMA bronze IS 'Medallion bronze layer: append-only raw landing, audit trail preserved verbatim.';
COMMENT ON SCHEMA silver IS 'Medallion silver layer: typed, normalized, deduplication-ready (dedup itself is Phase 12).';
COMMENT ON SCHEMA gold   IS 'Medallion gold layer: star schema (dims + fact) that the app and analytics read from.';

-- ---------------------------------------------------------------------------
-- bronze.raw_streams -- append-only landing table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.raw_streams (
    _ingest_id     BIGSERIAL PRIMARY KEY,
    _source_file   TEXT NOT NULL,
    _ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    _raw           JSONB NOT NULL,

    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Verbatim columns from streaming_history (source of truth for this backfill).
    -- NO ip_addr: Phase 9 purged it from history; it must not reappear here.
    ts                                  TIMESTAMPTZ,
    platform                            VARCHAR(200),
    ms_played                           INTEGER,
    conn_country                        VARCHAR(2),
    master_metadata_track_name          TEXT,
    master_metadata_album_artist_name   TEXT,
    master_metadata_album_album_name    TEXT,
    spotify_track_uri                   VARCHAR(255),
    episode_name                        TEXT,
    episode_show_name                   TEXT,
    spotify_episode_uri                 VARCHAR(255),
    audiobook_title                     TEXT,
    audiobook_uri                       VARCHAR(255),
    audiobook_chapter_uri               VARCHAR(255),
    audiobook_chapter_title             TEXT,
    reason_start                        VARCHAR(100),
    reason_end                          VARCHAR(100),
    shuffle                             BOOLEAN,
    skipped                             BOOLEAN,
    offline                             BOOLEAN,
    offline_timestamp                   BIGINT,
    incognito_mode                      BOOLEAN
);

COMMENT ON TABLE bronze.raw_streams IS
    'Append-only landing table. Phase 11 backfills it once from public.streaming_history; '
    'Phase 12''s Dagster pipeline lands new export files here directly. Never updated in place.';
COMMENT ON COLUMN bronze.raw_streams._source_file IS
    'Provenance: which export file (or backfill marker) this row came from.';
COMMENT ON COLUMN bronze.raw_streams._raw IS
    'The row as a jsonb object (to_jsonb of the source row), preserved verbatim for audit/replay.';

CREATE INDEX IF NOT EXISTS idx_bronze_raw_streams_user_ts ON bronze.raw_streams(user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_bronze_raw_streams_source ON bronze.raw_streams(_source_file);

-- Backfill bronze from the existing streaming_history, once. Idempotent: only
-- runs when bronze is empty, so a migrate.py re-run (or a fresh clone that
-- reseeds streaming_history) does not duplicate the backfill.
DO $$
BEGIN
    IF (SELECT count(*) FROM bronze.raw_streams) = 0
       AND (SELECT count(*) FROM streaming_history) > 0 THEN
        INSERT INTO bronze.raw_streams (
            _source_file, _raw, user_id,
            ts, platform, ms_played, conn_country,
            master_metadata_track_name, master_metadata_album_artist_name,
            master_metadata_album_album_name, spotify_track_uri,
            episode_name, episode_show_name, spotify_episode_uri,
            audiobook_title, audiobook_uri, audiobook_chapter_uri, audiobook_chapter_title,
            reason_start, reason_end, shuffle, skipped, offline, offline_timestamp,
            incognito_mode
        )
        SELECT
            'phase11_backfill:streaming_history',
            to_jsonb(s) - 'ip_addr',  -- defence in depth: strip if a legacy row still has it
            s.user_id,
            s.ts, s.platform, s.ms_played, s.conn_country,
            s.master_metadata_track_name, s.master_metadata_album_artist_name,
            s.master_metadata_album_album_name, s.spotify_track_uri,
            s.episode_name, s.episode_show_name, s.spotify_episode_uri,
            s.audiobook_title, s.audiobook_uri, s.audiobook_chapter_uri, s.audiobook_chapter_title,
            s.reason_start, s.reason_end, s.shuffle, s.skipped, s.offline, s.offline_timestamp,
            s.incognito_mode
        FROM streaming_history s
        ORDER BY s.id;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- silver.streams -- typed, normalized, FK-ready
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.streams (
    stream_id       BIGSERIAL PRIMARY KEY,
    _ingest_id      BIGINT REFERENCES bronze.raw_streams(_ingest_id),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    ts              TIMESTAMPTZ NOT NULL,
    artist_key      TEXT,               -- lower(trim(artist_name)), NULL for URI-less/podcast rows w/o artist
    track_key       TEXT,               -- spotify_track_uri, or 'hash:' fallback (see app/ingest/normalize.py)
    track_name      TEXT,
    artist_name     TEXT,
    album_name      TEXT,

    ms_played       INTEGER NOT NULL,
    platform        TEXT,
    conn_country    VARCHAR(2),
    reason_start    TEXT,
    reason_end      TEXT,
    shuffle         BOOLEAN NOT NULL DEFAULT FALSE,
    skipped         BOOLEAN NOT NULL DEFAULT FALSE,
    offline         BOOLEAN NOT NULL DEFAULT FALSE,
    incognito_mode  BOOLEAN NOT NULL DEFAULT FALSE,
    is_music        BOOLEAN NOT NULL DEFAULT TRUE  -- FALSE for podcast/audiobook/local rows
);

COMMENT ON TABLE silver.streams IS
    'Typed, normalized streams. NO ip_addr column (Phase 9 purge must not be reintroduced). '
    'Grain = one play event, same as bronze/source (Phase 11 does not dedup -- see Decision D6).';

CREATE INDEX IF NOT EXISTS idx_silver_streams_user_ts ON silver.streams(user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_silver_streams_user_artist ON silver.streams(user_id, artist_key);
CREATE INDEX IF NOT EXISTS idx_silver_streams_user_track ON silver.streams(user_id, track_key);

COMMIT;
