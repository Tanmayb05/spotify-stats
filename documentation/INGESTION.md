# Ingestion pipeline

**Status:** live as of Phase 12 (branch `feat/phase-12-dagster-ingestion`).
Supersedes the by-hand loader scripts and the one-time migration-008 bronze
backfill.

The warehouse is built by one Dagster asset graph:

```
discover export files
      │
raw_streams  (bronze; per-user-slug partition, or ALL slugs in a job run)
      ├─→ quarantine        (rows rejected by validation; empty on real data)
      └─→ silver_streams    (dedup on row_fingerprint, full rebuild)
            └─→ gold_star  @multi_asset, ONE transaction
                  ├─ dim_user  dim_time  dim_artist  dim_track  dim_album
                  └─ fact_streams
                        └─→ refreshed_views   (monthly_stats / top_artists /
                                               top_tracks + V7 freshness gate)
```

Code:
- `apps/api/app/ingest/` — the pipeline library (pure-ish, unit-tested):
  `discover.py`, `landing.py`, `schemas.py` + `validate.py`, `dedup.py`,
  `enrich.py`, `metrics.py`, `normalize.py`, `salvage.py`.
- `apps/api/dagster_project/` — the orchestration wrapper: `assets.py`,
  `resources.py`, `jobs.py`, `schedules.py`, `definitions.py`.
- `apps/api/scripts/build_star_schema.py` — the same pipeline as a plain script
  (no Dagster needed); kept as a valid entrypoint and as the API-baseline gate's
  driver.

---

## Running it

```bash
# Docker (recommended) — dagster service on :3000
docker compose up
docker compose exec dagster \
    dagster job execute -j nightly_ingest_job -m dagster_project.definitions

# or without Dagster
cd apps/api && python scripts/build_star_schema.py            # all users
cd apps/api && python scripts/build_star_schema.py --only amit sam
cd apps/api && python scripts/build_star_schema.py --no-land  # rebuild silver/gold only
```

`nightly_ingest_schedule` (03:00 UTC) ships **STOPPED** — enable it in the
Dagster UI (Automation tab) if you want it.

---

## Idempotency — two keys, two enforcement points

| level | key | enforced where | prevents |
|---|---|---|---|
| **file** | `(user_id, file_hash)` | DB `UNIQUE` on `bronze.ingest_state` | re-landing a file already landed |
| **row** | `(user_id, row_fingerprint)` | app logic in `dedup.py` (`ROW_NUMBER`), **not** a DB constraint | export-internal byte-identical dupes |

The row key is deliberately not a unique constraint: `bronze.raw_streams` must
retain every duplicate verbatim, and a constraint on `silver.streams` would make
the deterministic rebuild *fail* on a legitimate dupe instead of *counting* it.
Silver gets its idempotency from being a pure function of bronze.

`row_fingerprint` = sha256 of `(user_id, ts, track_key, ms_played)`
(`app.ingest.normalize.row_fingerprint`), written once at land time. There is
no SQL definition of it — the migration-008 backfill rows that predated it were
deleted in migration 011 precisely so a second, drift-prone definition never
had to exist.

Re-running a completed job: every file is `SKIP (file_hash_seen)`,
`files_new = 0`, `rows_landed = 0`, bronze/silver/fact counts unchanged.

---

## Why bronze is incremental but silver/gold are full rebuilds

Bronze landing is append-only and incremental — a two-tier watermark (file-hash
skip, then `ts >= watermark` **and** fingerprint-not-already-present for a
superset re-export). It never updates or deletes a landed row.

Silver and gold are **TRUNCATE + INSERT every run**. Reasons:
- dedup by `ROW_NUMBER() OVER (PARTITION BY user_id, row_fingerprint)` is
  inherently whole-partition;
- `dim_time` / `dim_album` are cheap derived tables;
- a full rebuild is *provably* a deterministic function of bronze — which is
  what makes the "numbers unchanged" API baseline diff meaningful.

**Transaction shape:** the whole silver→gold rebuild runs in one
`engine.begin()`, so a mid-rebuild failure leaves the previous star serving the
app. `refresh_all_views()` runs in its **own** transaction *after* that commits —
a `REFRESH MATERIALIZED VIEW` inside the TRUNCATE/INSERT transaction would see
pre-commit state.

A reviewer seeing `TRUNCATE` in a pipeline should read this section, not assume
an accident.

---

## Dedup tie-break

When `(user_id, row_fingerprint)` collides, silver keeps the row with the
**lowest `_ingest_id`** — the first-landed occurrence. `_ingest_id` is a
`BIGSERIAL` assigned in file order, so this is deterministic and stable across
re-runs.

---

## Quarantine

Validation (`app/ingest/validate.py`, a Pandera schema) runs **pre-landing**.
Blocking rules send the row to `bronze.quarantine` with a `rule` slug and it is
never landed; `reason_start` / `reason_end` enum misses are **warn-only** (the
row lands, the count goes to `bronze.ingest_run.detail`).

| rule | condition |
|---|---|
| `ts_missing` | `ts` absent / null / empty |
| `ts_unparseable` | present but not parseable to UTC |
| `ms_played_range` | `< 0` or `> 86_400_000` |
| `music_row_track_name` | `spotify_track_uri` present, track name null/blank |
| `platform_type` | `platform` present and not a string |
| `row_not_a_dict` | array element is not a JSON object |
| `reason_start_enum` / `reason_end_enum` | **warn** → lands |

Real exports trip none of the blocking rules, so `bronze.quarantine` is empty in
practice. `data/fixtures/malformed_streaming_history.json` (7 rows → 6
quarantined, 6 distinct rules, 1 landed) is what exercises the lane in tests.

---

## PII

`ip_addr` is popped from the row dict **before** it is written to
`bronze.raw_streams._raw` (`landing._insert_batch`) and before any
`bronze.quarantine._raw` write. Asserted by `tests/test_landing.py` and
`tests/test_dagster_pipeline.py` (`SELECT count(*) FROM bronze.raw_streams WHERE
_raw ? 'ip_addr'` → 0). The deprecated loader scripts had their
`ip_addr`-retaining code paths **deleted** in Phase 12 — they are now
one-line "use the pipeline" stubs.

---

## Run metrics

Every run writes `bronze.ingest_run` (one row) + `bronze.ingest_run_user` (one
per user). Invariants (V4):

- `rows_raw = rows_valid + rows_quarantined`
- `rows_silver = rows_landed − dups_dropped`  *(cumulative across bronze, not per run)*
- `0 ≤ track_match_rate, artist_match_rate ≤ 1`

Metrics are written through **short-lived connections outside the pipeline
transaction** (`metrics.py`), so a failed run still leaves a row. `gold_star`
records the fact count + match rates but does **not** finish the run;
`refreshed_views` (the true terminal asset) sets `status='success'`. A
`run_failure_sensor` flips any run left `'running'` by a failure to `'failed'`.

`public.bronze_ingest_run` / `bronze_ingest_run_user` / `bronze_quarantine` /
`bronze_ingest_state` are unqualified compatibility views (Blocker B1) for
Phase 13's `/api/health/data`.

---

## `public.streaming_history` is frozen legacy

After migration 012 (Phase 12 Commit 4) repointed the last 10 analytics RPCs at
`gold.fact_streams`, **no function reads `public.streaming_history`** except
`truncate_streaming_history` (a utility) and `get_skip_behavior` /
`get_user_leaderboard` (out of Phase 12 scope). The pipeline never writes it.

It is left populated-but-stale for one phase:
- Phase 13's DQ suite may want it as a cross-check;
- dropping a table is not this phase's job.

It carries the *old* grain — video/podcast rows and export-internal duplicates
included (71,052 for the primary user vs `gold.fact_streams`' 70,635). Do not
build anything new against it.

---

## Migrations added by Phase 12

| file | what |
|---|---|
| `011_ingest_state_and_runs.sql` | `row_fingerprint` columns; `bronze.ingest_state` / `quarantine` / `ingest_run` / `ingest_run_user`; `public.bronze_*` views; deletes the migration-008 bronze backfill (and TRUNCATEs `silver.streams`, which is rebuilt every run anyway). |
| `012_repoint_analytics_functions.sql` | repoints `get_discovery_timeline`, `get_artist_loyalty`, `get_artist_obsessions`, `get_reflective_insights`, `get_weekend_weekday_comparison`, `get_most_repeated_tracks`, `get_monthly_diversity`, `get_listening_heatmap`, `get_milestones_list`, `get_flashback` off `streaming_history` onto `gold.fact_streams`. Bodies copied verbatim; only the FROM clause and the `master_metadata_*_name` → `artist_name`/`track_name` columns change (never mapped to `artist_key` — that would merge casing-variant artist names). |

---

## Measured outcome (real data, all 11 users)

| user | bronze (ts ≠ null) | silver / fact | dups dropped |
|---|---:|---:|---:|
| tanmay (primary) | 70,817 | **70,635** | 182 |
| all users | 339,674 | **338,270** | 1,404 |

Video/podcast export files are out of scope by design (`discover.py`'s
`streaming_[0-9]*.json` pattern already excludes `streaming_video_*.json`, plus a
belt-and-braces `*video*` filter). Primary-user total moved 71,052 → 70,635
between the pre-Phase-12 grain and now: **−235 scope** (video no longer ingested;
`seed_local_db.py`'s old glob had included it, the Supabase loader never did) and
**−182 dedup** (`row_fingerprint` collapse, keep-lowest-`_ingest_id`).
