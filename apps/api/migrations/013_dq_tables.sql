-- Migration: Data-quality run + result tables (Phase 13, commit 1)
-- Date: 2026-09-02
-- Purpose: Persist the output of app/quality/run.py. One dq_run per invocation
--          (the Dagster `data_quality` asset or the `python -m app.quality.run`
--          CLI); one dq_result per check.
--
--   * NEW SCHEMA `quality` -- a PEER of bronze/silver/gold, not a child. The DQ
--     checks read all three layers (silver.streams, gold.fact_streams,
--     bronze.ingest_run), so filing them under `bronze` would be a lineage lie.
--     Keeps `public` free of real tables (the 009 / 011 policy).
--   * quality.dq_run    -- run header + rollup counts + overall status.
--   * quality.dq_result -- one row per check. observed/expected are TEXT
--     (checks return counts, rates and dates -- a single numeric column would
--     force lossy casts); observed_numeric carries the value when numeric, for
--     the Data Health trend chart.
--   * public.dq_run / public.dq_result compatibility views -- backends.py's
--     _IDENT_RE rejects dotted schema names (Blocker B1, same pattern as
--     009:241-247 / 011:167-170). /api/health/data reads ONLY through these,
--     so it works on the local AND the Supabase backend.
--
-- quality.dq_run.ingest_run_id is a NULLABLE plain UUID with NO FK to
-- bronze.ingest_run: `python -m app.quality.run` is a valid standalone
-- entrypoint with no pipeline run attached.
--
-- Applies after: 012_repoint_analytics_functions.sql
-- Run: python apps/api/db/migrate.py

BEGIN;

CREATE SCHEMA IF NOT EXISTS quality;
COMMENT ON SCHEMA quality IS
    'Data-quality observations over bronze/silver/gold. Peer schema, not a child: '
    'checks here read all three layers. Added by Phase 13.';

-- ---------------------------------------------------------------------------
-- quality.dq_run -- one row per app.quality.run.run_all() invocation
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quality.dq_run (
    dq_run_id       UUID PRIMARY KEY,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    ingest_run_id   UUID,              -- bronze.ingest_run.run_id; NO FK (see header)
    dagster_run_id  TEXT,
    checks_total    INTEGER NOT NULL DEFAULT 0,
    passed          INTEGER NOT NULL DEFAULT 0,
    failed          INTEGER NOT NULL DEFAULT 0,  -- blocking-severity failures
    warned          INTEGER NOT NULL DEFAULT 0,  -- warn-severity failures
    skipped         INTEGER NOT NULL DEFAULT 0,  -- ran but had no data to judge
    status          TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'pass', 'warn', 'fail', 'error')),
    duration_ms     INTEGER,
    detail          JSONB
);
COMMENT ON TABLE quality.dq_run IS
    'One row per data-quality suite run. Invariants: checks_total = passed + failed '
    '+ warned + skipped; status=''pass'' iff failed=0 AND warned=0; ''warn'' iff '
    'failed=0 AND warned>0; ''fail'' iff failed>0; ''error'' on an infra failure. '
    'Written via a short-lived connection OUTSIDE the caller''s transaction (same '
    'rule as bronze.ingest_run / app.ingest.metrics): a raising blocking check '
    'must still leave its own dq_run row.';

CREATE INDEX IF NOT EXISTS idx_dq_run_run_at     ON quality.dq_run(run_at DESC);
CREATE INDEX IF NOT EXISTS idx_dq_run_ingest_run ON quality.dq_run(ingest_run_id);

-- ---------------------------------------------------------------------------
-- quality.dq_result -- one row per check per run
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quality.dq_result (
    dq_result_id     BIGSERIAL PRIMARY KEY,
    dq_run_id        UUID NOT NULL REFERENCES quality.dq_run(dq_run_id) ON DELETE CASCADE,
    name             TEXT NOT NULL,          -- check slug from app/quality/checks.py
    category         TEXT NOT NULL
                        CHECK (category IN ('uniqueness', 'referential_integrity',
                                            'range', 'freshness', 'completeness',
                                            'anomaly')),
    severity         TEXT NOT NULL CHECK (severity IN ('blocking', 'warn')),
    passed           BOOLEAN NOT NULL,
    skipped          BOOLEAN NOT NULL DEFAULT FALSE,
    observed         TEXT,                   -- human-readable observed value
    observed_numeric NUMERIC,                -- same value when numeric; for charts
    expected         TEXT,                   -- human-readable pass condition
    rows_failed      BIGINT NOT NULL DEFAULT 0,
    user_id          UUID,                   -- set for per-user fan-out checks, else NULL
    detail           JSONB,
    duration_ms      INTEGER,
    checked_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dq_run_id, name, user_id)
);
COMMENT ON TABLE quality.dq_result IS
    'One row per check per dq_run. `name` is the registry slug in '
    'app/quality/checks.py and is the stable identifier the Data Health page '
    'groups on -- renaming one breaks the trend, so treat it as an API. '
    'rows_failed = 0 does NOT imply passed (a rate check fails on a ratio, not a '
    'row count). severity=''blocking'' + passed=FALSE is what fails the Dagster run.';

CREATE INDEX IF NOT EXISTS idx_dq_result_run      ON quality.dq_result(dq_run_id);
CREATE INDEX IF NOT EXISTS idx_dq_result_category ON quality.dq_result(category);
CREATE INDEX IF NOT EXISTS idx_dq_result_failing
    ON quality.dq_result(dq_run_id) WHERE passed = FALSE;

-- ---------------------------------------------------------------------------
-- Compatibility views (Blocker B1) -- same pattern as 009:241 / 011:167.
-- /api/health/data reads ONLY these, so it works on local AND Supabase.
-- Read-only; nothing writes through them.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.dq_run    AS SELECT * FROM quality.dq_run;
CREATE OR REPLACE VIEW public.dq_result AS SELECT * FROM quality.dq_result;

COMMENT ON VIEW public.dq_run IS
    'Unqualified compatibility view over quality.dq_run (Blocker B1). '
    'Read by /api/health/data via DBBackend.select().';
COMMENT ON VIEW public.dq_result IS
    'Unqualified compatibility view over quality.dq_result (Blocker B1). '
    'Read by /api/health/data via DBBackend.select().';

COMMIT;
