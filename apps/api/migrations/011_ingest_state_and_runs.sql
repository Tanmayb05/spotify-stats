-- Migration: Ingestion state, run metrics, quarantine + row_fingerprint columns
-- Date: 2026-09-01
-- Purpose: Phase 12 step 1. Add the DDL the Dagster ingestion pipeline needs:
--
--   * row_fingerprint columns on bronze.raw_streams and silver.streams
--     (CHAR(64) sha256 hex from app.ingest.normalize.row_fingerprint). NO SQL
--     backfill expression -- under Owner Decision 6 the legacy migration-008
--     backfill rows are DELETEd at the end of this file, so there is never a
--     second, drift-prone definition of the fingerprint in SQL.
--   * bronze.ingest_state  -- one row per (user, landed file); UNIQUE(user_id,
--     file_hash) is the FILE-level idempotency key (re-landing a known file is
--     a no-op, enforced by the DB).
--   * bronze.quarantine    -- rows rejected by validation. _ingest_id is
--     NULLABLE: rows are quarantined PRE-landing (an unparseable ts has no
--     bronze row to point at), so ON DELETE SET NULL, not a required FK.
--   * bronze.ingest_run / bronze.ingest_run_user -- per-run and per-run-per-user
--     metrics (rows raw/valid/quarantined/landed, dedup drop, match rates).
--   * public.bronze_* compatibility views -- backends.py's _IDENT_RE rejects
--     dotted schema names (Blocker B1), same pattern as 009:241-247. Phase 13's
--     /api/health/data reads these.
--
-- ROW-level idempotency (export-internal byte-identical dupes) is deliberately
-- NOT a DB constraint here -- it lives in app logic in dedup.py (ROW_NUMBER
-- over (user_id, row_fingerprint)). bronze must retain dupes verbatim; a unique
-- constraint on silver would make the deterministic rebuild FAIL on a legit
-- dupe instead of COUNTING it. See documentation/INGESTION.md.
--
-- TERMINAL DESTRUCTIVE STEP (Owner Decision 6): this file ends by TRUNCATEing
-- silver.streams and deleting the migration-008 bronze backfill rows
-- (_source_file = 'phase11_backfill:...'). silver.streams._ingest_id is a plain
-- FK to bronze (008:116) so silver must be cleared before the DELETE; silver is
-- a deterministic full rebuild from bronze on every pipeline run, so this costs
-- nothing. gold.fact_streams._ingest_id is a plain BIGINT with NO FK (009:155)
-- and gold is untouched here -- the app keeps serving the old gold tables with
-- no downtime until the first Dagster / build_star_schema.py run rebuilds.
--
-- Applies after: 010_mvs_on_star.sql
-- Run: python apps/api/db/migrate.py

BEGIN;

-- ---------------------------------------------------------------------------
-- row_fingerprint columns (no backfill -- see header, Decision 6)
-- ---------------------------------------------------------------------------
ALTER TABLE bronze.raw_streams
    ADD COLUMN IF NOT EXISTS row_fingerprint CHAR(64);
COMMENT ON COLUMN bronze.raw_streams.row_fingerprint IS
    'sha256 hex of (user_id, ts, track_key, ms_played) -- app.ingest.normalize.row_fingerprint. '
    'Written by app.ingest.landing at land time. NULL only for pre-Phase-12 rows (all deleted by this migration).';

CREATE INDEX IF NOT EXISTS idx_bronze_raw_streams_user_fingerprint
    ON bronze.raw_streams(user_id, row_fingerprint);

ALTER TABLE silver.streams
    ADD COLUMN IF NOT EXISTS row_fingerprint CHAR(64);
COMMENT ON COLUMN silver.streams.row_fingerprint IS
    'Carried from bronze.raw_streams by dedup.py. NOT unique-constrained: silver is a '
    'deterministic full rebuild from bronze and gets its idempotency from that, not a constraint.';

-- ---------------------------------------------------------------------------
-- bronze.ingest_state -- FILE-level idempotency (Decision: (user_id, file_hash))
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.ingest_state (
    state_id      BIGSERIAL PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_file   TEXT NOT NULL,            -- rel path at land time (informational; hash is the key)
    file_hash     CHAR(64) NOT NULL,        -- sha256 hex of the file bytes
    max_ts        TIMESTAMPTZ,
    min_ts        TIMESTAMPTZ,
    rows_in_file  INTEGER NOT NULL DEFAULT 0,
    rows_landed   INTEGER NOT NULL DEFAULT 0,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_id        UUID,
    UNIQUE (user_id, file_hash)
);
COMMENT ON TABLE bronze.ingest_state IS
    'One row per landed export file. UNIQUE(user_id, file_hash) is the file-level '
    'idempotency key: a re-run of an already-landed file is a DB-enforced no-op. '
    'Keying on file_hash (not source_file) means a renamed-but-identical file is skipped '
    'and a same-named-but-changed file is reprocessed.';

CREATE INDEX IF NOT EXISTS idx_ingest_state_user ON bronze.ingest_state(user_id);
CREATE INDEX IF NOT EXISTS idx_ingest_state_run  ON bronze.ingest_state(run_id);

-- ---------------------------------------------------------------------------
-- bronze.quarantine -- rows rejected by validation (PRE-landing, so nullable FK)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.quarantine (
    quarantine_id   BIGSERIAL PRIMARY KEY,
    _ingest_id      BIGINT REFERENCES bronze.raw_streams(_ingest_id) ON DELETE SET NULL,
    run_id          UUID,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    source_file     TEXT,
    source_index    INTEGER,              -- 0-based position of the row within the source file array
    rule            TEXT NOT NULL,        -- rule vocabulary: ts_missing, ts_unparseable, ms_played_range, ...
    detail          TEXT,
    _raw            JSONB NOT NULL,       -- the offending row, verbatim (ip_addr already popped upstream)
    quarantined_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE bronze.quarantine IS
    'Rows that failed a blocking validation rule and were NOT landed. _ingest_id is '
    'nullable because quarantine happens pre-landing (an unparseable ts has no bronze row). '
    'On real data this table stays empty -- the malformed fixture is what exercises it.';

CREATE INDEX IF NOT EXISTS idx_quarantine_run  ON bronze.quarantine(run_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_rule ON bronze.quarantine(rule);
CREATE INDEX IF NOT EXISTS idx_quarantine_user ON bronze.quarantine(user_id);

-- ---------------------------------------------------------------------------
-- bronze.ingest_run -- one row per pipeline run
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.ingest_run (
    run_id             UUID PRIMARY KEY,
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at        TIMESTAMPTZ,
    users              INTEGER NOT NULL DEFAULT 0,
    files_seen         INTEGER NOT NULL DEFAULT 0,
    files_new          INTEGER NOT NULL DEFAULT 0,
    rows_raw           BIGINT NOT NULL DEFAULT 0,
    rows_valid         BIGINT NOT NULL DEFAULT 0,
    rows_quarantined   BIGINT NOT NULL DEFAULT 0,
    rows_landed        BIGINT NOT NULL DEFAULT 0,
    dups_dropped       BIGINT NOT NULL DEFAULT 0,
    rows_silver        BIGINT NOT NULL DEFAULT 0,
    rows_fact          BIGINT NOT NULL DEFAULT 0,
    track_match_rate   NUMERIC(5,4),
    artist_match_rate  NUMERIC(5,4),
    unmatched_tracks   BIGINT,
    unmatched_artists  BIGINT,
    status             TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'success', 'failed', 'partial')),
    dagster_run_id     TEXT,
    detail             JSONB
);
COMMENT ON TABLE bronze.ingest_run IS
    'One row per Dagster ingestion run. Invariants (V4): rows_raw = rows_valid + rows_quarantined; '
    'rows_silver = rows_landed - dups_dropped; 0 <= match_rate <= 1. Written via a short-lived '
    'connection OUTSIDE the pipeline transaction so a failed run still leaves a status=failed row.';

CREATE INDEX IF NOT EXISTS idx_ingest_run_started ON bronze.ingest_run(started_at DESC);

-- ---------------------------------------------------------------------------
-- bronze.ingest_run_user -- per-run, per-user breakdown
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.ingest_run_user (
    run_id            UUID NOT NULL REFERENCES bronze.ingest_run(run_id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    files_seen        INTEGER NOT NULL DEFAULT 0,
    files_new         INTEGER NOT NULL DEFAULT 0,
    rows_raw          BIGINT NOT NULL DEFAULT 0,
    rows_valid        BIGINT NOT NULL DEFAULT 0,
    rows_quarantined  BIGINT NOT NULL DEFAULT 0,
    rows_landed       BIGINT NOT NULL DEFAULT 0,
    dups_dropped      BIGINT NOT NULL DEFAULT 0,
    rows_silver       BIGINT NOT NULL DEFAULT 0,
    max_ts            TIMESTAMPTZ,
    PRIMARY KEY (run_id, user_id)
);
COMMENT ON TABLE bronze.ingest_run_user IS
    'Per-run per-user ingestion counters. Sums over a run_id equal the bronze.ingest_run row.';

-- ---------------------------------------------------------------------------
-- Compatibility views (Blocker B1): unqualified names in public so
-- backends.py's LocalBackend.select() reaches them without a dotted name.
-- Same pattern as 009:241-247. Read-only; nothing writes through them.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.bronze_ingest_run      AS SELECT * FROM bronze.ingest_run;
CREATE OR REPLACE VIEW public.bronze_ingest_run_user AS SELECT * FROM bronze.ingest_run_user;
CREATE OR REPLACE VIEW public.bronze_quarantine      AS SELECT * FROM bronze.quarantine;
CREATE OR REPLACE VIEW public.bronze_ingest_state    AS SELECT * FROM bronze.ingest_state;

COMMENT ON VIEW public.bronze_ingest_run IS
    'Unqualified compatibility view over bronze.ingest_run (Blocker B1). Phase 13 /api/health/data.';

-- ---------------------------------------------------------------------------
-- TERMINAL DESTRUCTIVE STEP (Owner Decision 6). See header.
-- Deletes the one-time migration-008 backfill so bronze has a single source of
-- truth (the Dagster pipeline) and row_fingerprint has no legacy rows to
-- backfill. Idempotent: a second run matches zero rows.
--
-- silver.streams._ingest_id is a plain FK to bronze.raw_streams (008:116, no
-- ON DELETE action) and silver is currently populated by build_star_schema.py,
-- so the DELETE below would hit that constraint. TRUNCATE silver first: it is a
-- deterministic full rebuild from bronze on every pipeline run anyway, and the
-- app reads gold.fact_streams (untouched here), so this is a no-op for served
-- traffic. The very next `build_star_schema.py` / Dagster run repopulates it.
-- ---------------------------------------------------------------------------
TRUNCATE TABLE silver.streams RESTART IDENTITY;
DELETE FROM bronze.raw_streams WHERE _source_file = 'phase11_backfill:streaming_history';

COMMIT;
