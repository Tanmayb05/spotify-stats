# Dagster Ingestion Pipeline — Phase 12
**Date:** 2026-09-02 00:08:18
**Status:** Completed
**Time to complete:** ~3 sessions (Commits 1–2, Commit 3, Commits 4–5)

## Overview

Phase 12 replaces the by-hand data load — two Supabase-only loader scripts
writing straight into `public.streaming_history`, plus a one-time `bronze`
backfill in migration 008 — with a single orchestrated pipeline:
**discover → validate → land (bronze) → dedup (silver) → dims + fact (gold) →
refresh MVs**. It is incremental, idempotent, has a quarantine lane, and records
per-run / per-user metrics. It also finishes the star-schema migration begun in
Phase 11 by repointing the last 10 analytics RPCs off `streaming_history`.

Shipped across 5 commits:

| commit | sha | content |
|---|---|---|
| 1 | `2fd02d7` | migration 011 — `ingest_state`, `ingest_run`, `quarantine`, `row_fingerprint` |
| 2 | `b050473` | `app/ingest/` pipeline modules + `build_star_schema.py` refactor |
| 3 | `6c266a5` | Dagster project + compose `dagster` service |
| 4 | `711a51a` | migration 012 — repoint 10 analytics RPCs at `gold.fact_streams` |
| 5 | *(this)* | docs + legacy loader deprecation + `DISK_FACT_COUNTS` |

Detailed records: `documentation/20260901_204014_phase_12_dagster_ingestion_PLAN.md`
(plan of record + owner decisions), `documentation/20260901_224259_phase_12_dagster_ingestion_commits_1_2.md`
(Commits 1–2), `documentation/INGESTION.md` (the durable pipeline reference).

## Files Created

- `apps/api/migrations/011_ingest_state_and_runs.sql`
- `apps/api/migrations/012_repoint_analytics_functions.sql`
- `apps/api/app/ingest/discover.py`
- `apps/api/app/ingest/landing.py`
- `apps/api/app/ingest/schemas.py`
- `apps/api/app/ingest/validate.py`
- `apps/api/app/ingest/dedup.py`
- `apps/api/app/ingest/enrich.py`
- `apps/api/app/ingest/metrics.py`
- `apps/api/dagster_project/__init__.py`
- `apps/api/dagster_project/definitions.py`
- `apps/api/dagster_project/resources.py`
- `apps/api/dagster_project/assets.py`
- `apps/api/dagster_project/jobs.py`
- `apps/api/dagster_project/schedules.py`
- `apps/api/pyproject.toml`
- `apps/api/dagster_home/dagster.yaml`
- `apps/api/tests/test_discover.py`
- `apps/api/tests/test_validate.py`
- `apps/api/tests/test_landing.py`
- `apps/api/tests/test_dedup.py`
- `apps/api/tests/test_dagster_pipeline.py`
- `data/fixtures/malformed_streaming_history.json`
- `data/fixtures/sample_streaming_history_full.json`
- `documentation/INGESTION.md`
- `documentation/20260901_204014_phase_12_dagster_ingestion_PLAN.md`
- `documentation/20260901_224259_phase_12_dagster_ingestion_commits_1_2.md`
- `documentation/20260902_000818_phase_12_dagster_ingestion.md` (this file)

## Files Modified

- `apps/api/scripts/build_star_schema.py` — 7 inline stage functions removed;
  now a ~130-line wrapper over `app/ingest/{discover,landing,dedup,enrich}`.
- `apps/api/scripts/load_json_to_supabase.py` — **gutted to a deprecation stub**;
  blocking `input()` and the `ip_addr`-retaining `transform_record` deleted.
- `apps/api/scripts/load_multi_user_data.py` — **gutted to a deprecation stub**;
  `USERS` now re-exports `app.ingest.discover.USER_SLUGS`.
- `apps/api/app/ingest/normalize.py` — docstrings only.
- `apps/api/app/ingest/enrich.py` — `DISK_FACT_COUNTS` populated with the 10
  measured per-user constants (V1c now active).
- `apps/api/requirements.txt` — `pandera`, `dagster`, `dagster-webserver`,
  `dagster-postgres==0.29.20` added (all now runtime).
- `apps/api/requirements-dev.txt` — those lines removed.
- `apps/api/Dockerfile` — copies `dagster_project/`, `pyproject.toml`,
  `dagster_home/`; pre-creates `dagster_home/storage` for volume ownership.
- `docker-compose.yml` — `dagster` service (`:3000`), `dagster_storage` volume,
  header/port table.
- `README.md`, `start.sh` — port tables (web 3010, api 3011, dagster 3000).
- `UPDATE.md` — Phase 12 row → DONE + log entry.

## Checklist

- [x] Intuitive navigation — Dagster lineage graph at `:3000` mirrors
      bronze → silver → gold; assets grouped `bronze` / `silver` / `gold`.
- [x] Consistent design — SQLAlchemy `text()` + `engine.begin()`, migration
      ledger conventions, `app/ingest/` module-per-concern, reuse of Phase 11's
      `normalize.py` / `salvage.py`.
- [x] Responsive layout — n/a (backend phase).
- [x] A11y labels/roles — n/a (backend phase).
- [x] Error handling & feedback — quarantine lane; metrics on their own
      connection so a failed run records `status='failed'`; `run_failure_sensor`;
      V1/V7 assertions fail the run loudly.
- [x] Performance — set-based SQL for silver/gold; 5,000-row insert batches;
      one indexed anti-join per file for the row watermark; partitioned bronze.
- [x] Security baseline — `ip_addr` popped before every bronze/quarantine write
      (V8, asserted in 2 test modules); the last `ip_addr`-writing code path
      (the legacy loaders) deleted; no secrets added.
- [x] Docs generated — `INGESTION.md`, this file, `UPDATE.md`, plan +
      commits-1-2 docs.

## What Was Implemented

### Purpose

Get data into the warehouse the same way every time: discoverable inputs,
validated rows, an append-only raw layer, a deterministically-rebuilt typed
layer that collapses export duplicates, and a star that is a provable function
of the raw layer — so the "numbers unchanged" API baseline diff stays
meaningful and re-running the pipeline is always safe.

### Features

**Migration 011.** `row_fingerprint CHAR(64)` on `bronze.raw_streams` (+ index)
and `silver.streams`; `bronze.ingest_state` (`UNIQUE(user_id, file_hash)` =
file-level idempotency); `bronze.quarantine` (`_ingest_id` nullable — quarantine
is pre-landing); `bronze.ingest_run` + `bronze.ingest_run_user` (metrics with
the V4 invariants); four `public.bronze_*` compat views (Blocker B1). Terminal
destructive step (Owner Decision 6): `TRUNCATE silver.streams` +
`DELETE FROM bronze.raw_streams WHERE _source_file = 'phase11_backfill:...'` so
bronze has a single writer.

**Pipeline library (`app/ingest/`).**
- `discover.py` — adapts to the repo's `data/` layout as-is (no file moves):
  primary `data/streaming_[0-9]*.json`, others
  `data/other users/<slug>/Streaming_History_Audio_*.json`; excludes `*video*`
  and `Spotify Account Data/`; deterministic sort; `ALL_SLUGS` /
  `USER_SLUGS` are the canonical slug definitions.
- `landing.py` — append-only bronze landing, two-tier watermark (file-hash skip,
  then `ts >= watermark` **and** fingerprint anti-join). `_raw` has `ip_addr`
  popped. 5,000-row batches; `ingest_state` upserted `ON CONFLICT` so a
  mid-file crash converges on re-run.
- `schemas.py` + `validate.py` — Pandera `DataFrameSchema`, `lazy=True`,
  `strict=False`, run pre-landing; rule vocabulary → `bronze.quarantine.rule`;
  `reason_*` enum misses are warn-only.
- `dedup.py` — silver full-rebuild via
  `ROW_NUMBER() OVER (PARTITION BY user_id, row_fingerprint ORDER BY _ingest_id)`,
  keep `rn = 1`.
- `enrich.py` — `stage_dim_*` + `stage_fact_streams` (moved verbatim from the old
  `build_star_schema.py`, one definition); `match_rates()` (enrichment rate, not
  the trivial FK-presence rate); `verify_v1` rewritten for the dedup era
  (V1a `bronze − dups == silver`, V1b `silver == fact`, V1c `fact == DISK_FACT_COUNTS`).
- `metrics.py` — `start_run` / `ensure_run` / `record_user` / `bump_run` /
  `set_run_fields` / `finish_run` / `fail_run_by_dagster_id`; every write on its
  own short-lived connection outside the pipeline transaction.

**Dagster project (`dagster_project/`).**
- `resources.py` — `PostgresResource` wrapping `make_engine` (not the
  `lru_cache`d `get_engine`); `DataRootResource`.
- `assets.py` — `raw_streams` (`StaticPartitionsDefinition` over 10 slugs; an
  unpartitioned job run lands ALL slugs via `_land_slug`), `quarantine`,
  `silver_streams`, `gold_star` (`@multi_asset`, one transaction, 6 named outs),
  `refreshed_views` (terminal; V7 MV-freshness assertion; marks the run
  success). `IngestVerificationError` for V1/V7 failures.
- `jobs.py` — `nightly_ingest_job = define_asset_job(..., AssetSelection.all())`.
- `schedules.py` — `nightly_ingest_schedule`, `0 3 * * *` UTC,
  `default_status=STOPPED`.
- `definitions.py` — wires it together + a `run_failure_sensor`
  (`mark_ingest_run_failed`) that flips a failed run's `ingest_run` row to
  `'failed'`.
- `dagster_home/dagster.yaml` — run/event-log/schedule storage → same Postgres,
  `schema: dagster`; local artifact + compute-log dirs under a subpath so the
  compose named volume persists just those.

**Compose `dagster` service.** Built from the api image (repo-root context).
`dagster dev -h 0.0.0.0 -p 3000 -m dagster_project.definitions`, port `3000`,
`DATABASE_URL` / `INGEST_DATA_ROOT` / `DAGSTER_HOME` / `DAGSTER_PG_*`, `./data`
+ `./outputs` read-only, named `dagster_storage` volume,
`depends_on: db (healthy) + api (started)`. Command first runs
`CREATE SCHEMA IF NOT EXISTS dagster` (the storage backend does not). No
`migrate.py` here — the api container owns that.

**Migration 012.** The 10 long-tail `006` functions
(`get_discovery_timeline`, `get_artist_loyalty`, `get_artist_obsessions`,
`get_reflective_insights`, `get_weekend_weekday_comparison`,
`get_most_repeated_tracks`, `get_monthly_diversity`, `get_listening_heatmap`,
`get_milestones_list`, `get_flashback`) repointed at `gold.fact_streams`.
Bodies copied verbatim; only `FROM streaming_history` → `FROM gold.fact_streams`
and `master_metadata_album_artist_name` / `master_metadata_track_name` →
`artist_name` / `track_name`. Never mapped to `artist_key`. Exact
`DROP FUNCTION IF EXISTS` before each (Blocker B2).

**Commit 5.** `INGESTION.md`; the two legacy loaders reduced to deprecation
stubs (PII code paths deleted); `DISK_FACT_COUNTS` populated with the 10
measured per-user fact counts; `UPDATE.md` updated; this doc.

### Flow

```
discover_files(root, only)                      # 27 files, sorted
      │  per file, own txn
get_or_create_user → user_watermark → land_file
      │  tier 1: file_hash in ingest_state?  → skip, no parse
      │  read_export → validate_rows → write_quarantine   (pre-landing)
      │  tier 2: ts >= watermark AND fingerprint not in bronze
      │  INSERT bronze.raw_streams (_raw has NO ip_addr)   batches of 5000
      ▼
──────────── one engine.begin() ────────────
TRUNCATE gold.fact_streams
build_silver(conn)        # ROW_NUMBER dedup, keep min _ingest_id
stage_dim_{user,time,artist,track,album}(conn)
stage_fact_streams(conn)
match_rates(conn) ; verify_v1(conn)             # raises on mismatch
────────────────────────────────────────────
      ▼  own txn, AFTER the rebuild commits
SELECT refresh_all_views()                      # + V7 assertion
```

### Usage

```bash
docker compose up                                        # web:3010 api:3011 dagster:3000
docker compose exec dagster \
    dagster job execute -j nightly_ingest_job -m dagster_project.definitions
docker compose exec api python db/migrate.py             # applies 011 + 012

cd apps/api && python scripts/build_star_schema.py       # Dagster-free path
DAGSTER_PIPELINE_TEST_DB=1 DATABASE_URL=... python -m pytest tests/test_dagster_pipeline.py
```

## Verification

| gate | result |
|---|---|
| V1 — full job green, per-user `silver == fact`; `bronze − dups == silver` | **PASS** all 11 users; primary 70,817 → 70,635 (182 dups) |
| V1c — `fact == DISK_FACT_COUNTS[user]` | **PASS** all 10 users with constants |
| V2 — immediate re-run | **PASS** — 27 files SKIP, `files_new=0`, `rows_landed=0`, counts identical |
| V3 — malformed fixture | **PASS** — 6 quarantine rows, 6 distinct rules, 1 landed |
| V4 — metrics invariants | **PASS** — `status=success`, `dups_dropped=1404`, `rows_fact=338270`, `0 ≤ rates ≤ 1` |
| V5 — dedup delta, two numbers | scope −1,082 (video) + dedup −1,404, reported separately in `INGESTION.md` |
| V6 — API baseline | Commit 2/3: non-clean, every diff = −235 video + −182 dedup on primary. Commit 4: 44 routes, 35 identical, 9 changed, **all 9 explained by the same grain cutover** (see below) |
| V7 — MV freshness | **PASS** — `sum(monthly_stats.total_streams) == count(fact_streams WHERE track_name NOT NULL)` = 70,518 for primary |
| V8 — no `ip_addr` in bronze | **PASS** — `_raw ? 'ip_addr'` → 0; legacy loaders' PII paths deleted |
| V9 — migration replay | **PASS** — 011 + 012 apply once, second `migrate.py` a no-op; scratch-DB fresh apply 12/12 |
| V10 — RPC repoint | **PASS** — none of the 10 read `streaming_history` (`get_skip_behavior` / `get_user_leaderboard` / `truncate_streaming_history` still name it — out of Phase 12 scope) |
| pipeline tests | `test_dagster_pipeline.py` V1/V2/V3/V8 pass against a scratch DB |
| ruff | clean on all new code (`E9,F` + default) |

**Commit 4 baseline diff — the 9 changed routes, each explained:**
- `/api/discovery/reflect` `total_streams: 71052 → 70635` — the grain delta exactly.
- `/api/patterns/weekend-weekday`, `/api/patterns/heatmap` — total streams −417 exact.
- `/api/patterns/monthly-diversity` — −395 (endpoint filters `artist_name IS NOT
  NULL`; 417 − 22 null-artist rows in the delta).
- `/api/discovery/{loyalty,timeline}`, `/api/milestones/list`,
  `/api/patterns/repeated-tracks` — per-artist / per-day / per-rank counts shift
  as the same dup + video plays collapse.
- `/health.timestamp` — volatile, expected.
No unexplained diff. `outputs/baseline/post_phase12` re-captured;
`pre_phase11` superseded.

## Deviations From the Plan

All Owner Decisions 1–8 were followed. Deviations logged (full detail in
`UPDATE.md` and the two prior phase docs):

| # | deviation | why |
|---|---|---|
| A | migration 011 also `TRUNCATE silver.streams` before the backfill `DELETE` | `silver.streams._ingest_id` is a plain populated FK to bronze; silver is a deterministic full rebuild, so truncating costs nothing |
| B | no clean `pre_phase12` API baseline exists | local DB was already rebuilt; diffed against `pre_phase11`, every diff explained by −235 video + −182 dedup; `post_phase12` captured as the new reference |
| C | `dagster` moved to `requirements.txt` in Commit 3, not Commit 2 | no `app/` code imports it until `dagster_project/` lands in Commit 3 |
| D | `DISK_FACT_COUNTS` empty until Commit 5 | the per-user constants were signed off against the Commit-3 full run, then pinned |
| E | `_ts_parseable` uses an `_is_nan()` helper, not `v == v` | ruff `PLR0124` |
| F | `assets.py` drops `from __future__ import annotations` | Dagster's `_validate_context_type_hint` rejects stringized `AssetExecutionContext` |
| G | `raw_streams` handles an unpartitioned run (lands ALL slugs), not partition-only | `dagster job execute` on a job spanning partitioned + unpartitioned assets runs non-partitioned; `context.has_partition_key` branch keeps per-slug materialization working from the UI |
| H | `gold_star` records fact count + match rates but does **not** finish the run; `refreshed_views` marks `success`; a `run_failure_sensor` marks `failed` | a V7 / infra failure after `gold_star` must not leave a lying `status='success'` |
| I | migration 012 baseline diff is **not** byte-clean | `public.streaming_history` was never deduped/video-stripped; the 10 endpoints move by exactly the grain delta Commit 2 applied to the hot RPCs — the last `streaming_history → gold` cutover |
| J | `test_dagster_pipeline.py` is opt-in via `DAGSTER_PIPELINE_TEST_DB=1` | it TRUNCATEs bronze/silver/gold — must only run against a throwaway DB |

## Next Steps

- **Phase 13 (DQ suite + Data Health page).** `bronze.quarantine`,
  `bronze.ingest_run{,_user}` and the `public.bronze_*` views are the read
  surface for `/api/health/data`. Pandera schemas in `app/ingest/schemas.py` are
  the starting point for the DQ rule set. `public.streaming_history` is still
  available as a cross-check before it is dropped.
- **Phase 16 CI.** Add `dagster job execute -j nightly_ingest_job` (against a
  scratch Postgres) + `pytest tests/test_dagster_pipeline.py` with
  `DAGSTER_PIPELINE_TEST_DB=1` to the pipeline. `check_backend_parity.py` and
  `compare_api_baseline.py` remain the regression gates.
- Consider repointing `get_skip_behavior` / `get_user_leaderboard` and dropping
  `public.streaming_history` once Phase 13 confirms it is no longer needed.

## Conclusion

The warehouse is now built by one idempotent, incremental, observable Dagster
pipeline that is a provable function of an append-only bronze layer; the star is
rebuilt deterministically each run, 1,404 export duplicates are collapsed with a
documented tie-break, video/podcast files are out of scope, and the last code
path that could persist `ip_addr` has been deleted. All 10 remaining analytics
RPCs read `gold.fact_streams`; `public.streaming_history` has effectively no
readers and is frozen pending removal in a later phase.
