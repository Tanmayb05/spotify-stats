# Data quality

**Status:** live as of Phase 13 (branch `feat/phase-13-data-quality`).

The data-quality suite runs over the rebuilt warehouse as the **terminal** Dagster
asset and gates the pipeline:

```
refreshed_views  (MV refresh + V7 freshness gate)
      └─→ data_quality   (app.quality suite; TERMINAL)
            ├─ persists → quality.dq_run + quality.dq_result
            ├─ owns    → bronze.ingest_run.finish_run (success / partial)
            └─ raises  → on any blocking-severity failure
                         (status stays 'running' → run_failure_sensor → 'failed')

/api/health/data  reads public.dq_run / public.dq_result / public.bronze_* (compat
                  views) — works on the local AND the Supabase backend
Data Health page  renders it
```

Code:
- `apps/api/app/quality/checks.py` — the `@check` registry: 21 checks, one
  function each, taking an open read-only `conn`. `THRESHOLDS` dict at the top.
- `apps/api/app/quality/pandera_schemas.py` — 3 sample-based DataFrame contracts
  (see "Why pandera_schemas.py is small").
- `apps/api/app/quality/run.py` — `run_all(engine, ...)` + `summarize()` + the
  `python -m app.quality.run` CLI.
- `apps/api/dagster_project/assets.py` — the `data_quality` asset.
- `apps/api/app/routes/health.py` — `GET /api/health/data`.
- `apps/api/migrations/013_dq_tables.sql` — `quality` schema + the two tables +
  the `public.dq_*` compat views.
- `apps/web/src/pages/DataHealth.tsx` — the page.

---

## Running it

```bash
# Docker (recommended) — as part of the nightly job
docker compose up
docker compose exec dagster \
    dagster job execute -j nightly_ingest_job -m dagster_project.definitions

# just the DQ suite, against the current warehouse
docker compose exec api python -m app.quality.run
docker compose exec api python -m app.quality.run --category range,freshness
docker compose exec api python -m app.quality.run --only fact_track_key_fk --no-persist

# no Docker
python -m app.quality.run            # reads DATABASE_URL / spotify-insights.env
```

Exit code is the contract: `0` = no blocking failure (pass or warn), `1` = a
blocking check failed, `2` = infrastructure error (no DB, migration 013 not
applied).

---

## The checks

21 registered checks; `per_user_fact_freshness` fans out to one result per user,
so a full run on the 10-user dataset yields **31 results**. 12 are **blocking**
(a failure raises and fails the Dagster run); 9 are **warn** (surfaced, never
gating).

| name | category | severity | asserts | invariant source |
|---|---|---|---|---|
| `fact_ingest_id_unique` | uniqueness | blocking | no duplicate `gold.fact_streams._ingest_id` | 009:155 — no FK, no unique constraint |
| `dim_track_uri_unique` | uniqueness | blocking | no `spotify_track_uri` shared across >1 `track_key` | D3 natural-key rule |
| `silver_fingerprint_unique` | uniqueness | blocking | no duplicate `(user_id, row_fingerprint)` in `silver.streams` | 011 header — row idempotency is `dedup.py`, not a constraint |
| `fact_track_key_fk` | referential_integrity | blocking | every `fact_streams.track_key` resolves to `gold.dim_track` | 009 FK (also catches an un-VALIDated FK) |
| `fact_user_id_fk` | referential_integrity | blocking | … `user_id` → `gold.dim_user` | 009 FK |
| `fact_artist_key_fk` | referential_integrity | blocking | … `artist_key` → `gold.dim_artist` | 009 FK |
| `fact_time_key_fk` | referential_integrity | blocking | … `time_key` → `gold.dim_time` | 009 FK |
| `ms_played_range` | range | blocking | every `ms_played` in `[0, 86_400_000]` | `schemas.MS_PER_DAY` |
| `ingest_run_match_rate_range` | range | blocking | every non-null match rate in `[0, 1]` | migration 011 `COMMENT ON TABLE` |
| `release_year_range` | range | warn | `dim_track.release_year` in `[1900, next year]` | — |
| `mood_proxy_range` | range | warn | every non-null `mood_proxy_*` in `[0, 1]` | 009 D1 |
| `silver_schema_contract` | range | warn | a 5k-row sample of `silver.streams` matches the dtype/range contract | Pandera |
| `gold_schema_contract` | range | warn | 5k-row samples of `fact_streams` + `dim_track` match the dtype/enum contract | Pandera |
| `ingest_state_recent` | freshness | warn | latest `bronze.ingest_state.ingested_at` within 45 days (skips on an empty table) | — |
| `latest_ingest_run_terminal` | freshness | warn | the latest *completed* `bronze.ingest_run` is `success`/`partial` | — |
| `per_user_fact_freshness` | freshness | warn | per user, `max(fact ts)` within 2000 days (exports are historical) | — |
| `fact_track_name_rate` | completeness | blocking | ≥ 95% of fact rows have a non-blank `track_name` | measured 99.61% |
| `fact_artist_name_rate` | completeness | blocking | ≥ 95% … `artist_name` | measured 99.61% |
| `fact_time_key_rate` | completeness | blocking | ≥ 99.9% of fact rows have a `time_key` | measured 100% |
| `enrichment_coverage` | completeness | warn | `audio_source='enriched'` coverage — reuses `enrich.match_rates()` | measured 0% artist / 4% track |
| `daily_play_count_anomaly` | anomaly | warn | no per-user daily play count beyond 4σ of the 30-day rolling median (MAD, guards MAD=0) | — |
| `run_over_run_row_delta` | anomaly | warn | `|z| ≤ 3` on the latest run-over-run `rows_fact` delta (skips under 6 runs) | — |

---

## Severity and the pipeline gate

`data_quality` is the terminal asset of `nightly_ingest_job`. `AssetSelection.all()`
picks it up with no job edit; `deps=["refreshed_views"]` (not `fact_streams`) so it
runs strictly after the MV refresh and is unambiguously last.

- **blocking failure** → `raise IngestVerificationError`; `finish_run` is NOT
  called, so `bronze.ingest_run.status` stays `'running'` and the
  `run_failure_sensor` flips it to `'failed'`. The `quality.dq_run` row is still
  written (own-connection rule) with `status='fail'`.
- **warn-only** → `finish_run(status='partial')`.
- **clean** → `finish_run(status='success')`.

`finish_run(detail=…)` overwrites the whole `detail` JSONB, so the asset reads the
existing `detail` (which `gold_star` wrote `{artist_fk_rate, track_fk_rate}` into)
and merges the `dq_*` summary before writing.

`refreshed_views` no longer calls `finish_run` — a narrower job that materializes
it alone would leave the run `'running'` forever, so any custom selection must
include `data_quality`.

---

## Thresholds

One `THRESHOLDS` dict at the top of `checks.py` — greppable, diff-reviewable,
unit-tested. Not `Settings` (env vars for numbers nobody tunes at runtime), not a
DB table (a fresh DB would have no rows and every check would error).

Rate thresholds are set **below the value measured on the real seeded DB**
(2026-09-02, 338,270 fact rows) with headroom, so the suite is green on day one:

| threshold | measured | set to |
|---|---|---|
| `completeness_track_name_rate` | 0.9961 | 0.95 |
| `completeness_artist_name_rate` | 0.9961 | 0.95 |
| `completeness_time_key_rate` | 1.0000 | 0.999 |
| `enrichment_artist_rate` | 0.0000 | 0.0 (WARN) |
| `enrichment_track_rate` | 0.0397 | 0.0 (WARN) |

Audio-features enrichment (`audio_source='enriched'`) does not exist in this repo
— Spotify deprecated the endpoint in Nov 2024 — so `enrichment_coverage` is a
warn-severity informational signal, not a gate. (The 78.2% figure in the Phase 11
docs is *genre* backfill into `dim_artist.genres_enriched`, a different column.)

---

## Why `pandera_schemas.py` is small

The roadmap asked for "silver/gold dataframe schemas shared with
`ingest/schemas.py`". In practice: `ingest/schemas.py`'s `RAW_ROW_SCHEMA`
validates *raw export dicts pre-landing* (`master_metadata_track_name`,
`spotify_track_uri`) — a completely different column set from `gold.fact_streams`.
Nothing meaningful to share but `MS_PER_DAY`. And 19 of 21 checks are SQL
aggregates over 338k rows that would be strictly worse pulled into pandas.

So `pandera_schemas.py` has exactly one job: **schema-contract validation on a
bounded 5,000-row sample**, catching what aggregate SQL cannot — a `ms_played`
that became text, a `ts` that lost its timezone, a column that disappeared under a
migration. Nullable columns use pandas `Int64` + `coerce=True` so `read_sql`
dtype inference (`float64` when a NULL is present, `int64` when not) doesn't flake
the check between runs.

---

## `/api/health/data`

Reads **only** through the unqualified `public.*` compat views (`dq_run`,
`dq_result`, `bronze_ingest_run`, `bronze_ingest_run_user`, `bronze_quarantine`)
via `DBBackend.select()` — `backends.py`'s `_check_identifier` rejects dotted
schema names, so a dotted read would fail anyway. Every one of the 7 reads is
wrapped in `try/except → []`: on a backend where `quality`/`bronze` were never
migrated (the hosted Supabase demo), the endpoint degrades to `has_run: false`,
**HTTP 200** — a state, not an error.

Shape: `{ backend, generated_at, dq{ has_run, status, categories[≥6, each with
nested checks] }, ingest{ …counters, invariants{} }, per_user[], quarantine{},
trend[] }`. `ingest.invariants` computes the migration-011 `COMMENT` invariants;
`rows_silver = rows_landed − dups_dropped` is reported `null` on an idempotent
re-run (`rows_landed = 0` while silver rebuilds in full from bronze).

The old `GET /health` liveness blob is untouched.

---

## Migrations added by Phase 13

| migration | what |
|---|---|
| `013_dq_tables.sql` | `CREATE SCHEMA quality`; `quality.dq_run` (run header + rollup + status) and `quality.dq_result` (one row per check, `UNIQUE(dq_run_id, name, user_id)`); `public.dq_run` / `public.dq_result` compat views. |

---

## Measured outcome (real data, all 10 users)

`python -m app.quality.run` against the 338,270-row warehouse:

```
31 checks: 29 passed, 0 failed (blocking), 2 warned, 0 skipped   ->  WARN
```

The two warns are genuine minor data-quality signals, working as intended:
- `release_year_range` — 28 `dim_track` rows have `release_year = 0` (missing year
  from enrichment).
- `daily_play_count_anomaly` — 1 anomalous user-day at >4σ across 7 judged users.

Neither is blocking, so a clean `nightly_ingest_job` finishes with
`bronze.ingest_run.status = 'partial'`.
