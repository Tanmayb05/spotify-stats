# Dagster Ingestion — Phase 12 (Commits 1 & 2)

**Date:** 2026-09-01 22:42:59
**Status:** Partial — Commits 1–2 of 5 landed; Commits 3–5 not started
**Time to complete:** ~1 session
**Branch:** `feat/phase-12-dagster-ingestion` (off `main`)

Commits:
- `2fd02d7` — `feat(db): migration 011 — ingest_state, ingest_run, quarantine, row_fingerprint`
- `b050473` — `feat(ingest): app/ingest pipeline modules + build_star_schema refactor`

Plan of record: `documentation/20260901_204014_phase_12_dagster_ingestion_PLAN.md`.

---

## Overview

Phase 12 replaces the by-hand data load (two Supabase-only loader scripts writing
straight to `public.streaming_history`, plus a one-time `bronze` backfill in
migration 008) with a discover → validate → land (bronze) → dedup (silver) →
dims + fact (gold) → refresh-MVs pipeline that is incremental, idempotent, has a
quarantine lane, and records per-run / per-user metrics.

**Commits 1–2 deliver the schema and the pipeline library** — everything the
pipeline needs to run from a plain `python` process. Commit 3 wraps it in Dagster
assets + a compose service; Commit 4 repoints the last 10 analytics RPCs off
`streaming_history`; Commit 5 is docs + loader deprecation.

Measured outcome of running the new pipeline against the real export files:

| user | bronze (ts ≠ null) | silver / fact | dups dropped |
|---|---:|---:|---:|
| tanmay (primary) | 70,817 | **70,635** | 182 |
| all 11 users | 339,674 | 338,270 | **1,404** |

Primary-user target from the plan was 70,817 → 70,635; hit exactly. Total dedup
delta 1,404 matched the plan's prediction. Video/podcast export files were never
ingested (scope effect), so the two effects stay separate as the plan required.

---

## Files Created

**Commit 1**
- `apps/api/migrations/011_ingest_state_and_runs.sql`

**Commit 2**
- `apps/api/app/ingest/discover.py`
- `apps/api/app/ingest/landing.py`
- `apps/api/app/ingest/schemas.py`
- `apps/api/app/ingest/validate.py`
- `apps/api/app/ingest/dedup.py`
- `apps/api/app/ingest/enrich.py`
- `apps/api/app/ingest/metrics.py`
- `apps/api/tests/test_discover.py`
- `apps/api/tests/test_validate.py`
- `apps/api/tests/test_landing.py`
- `apps/api/tests/test_dedup.py`
- `data/fixtures/malformed_streaming_history.json`
- `data/fixtures/sample_streaming_history_full.json`

## Files Modified

- `apps/api/scripts/build_star_schema.py` — 7 inline stage functions removed;
  now a ~130-line wrapper over `app/ingest/{discover,landing,dedup,enrich}`
  (401 → 133 lines).
- `apps/api/app/ingest/normalize.py` — docstrings only (removed the stale "not
  yet used" wording; listed the real production callers).
- `apps/api/requirements.txt` — `pandera==0.33.0` added (app code imports it).
- `apps/api/requirements-dev.txt` — `pandera` removed (moved up); note added
  that `dagster` moves to `requirements.txt` in Commit 3.

Diffstat: 18 files, +2,273 / −325.

---

## Checklist

- [x] Intuitive module boundaries (one concern per file under `app/ingest/`)
- [x] Consistent with existing code (SQLAlchemy `text()`, `engine.begin()`,
      migration ledger conventions, `app/ingest/normalize.py` reuse)
- [x] Idempotent — file-level (`UNIQUE(user_id, file_hash)`) and row-level
      (`row_fingerprint` anti-join + deterministic silver rebuild)
- [x] Error handling — quarantine lane for bad rows; metrics writes on their own
      connection so a failed run still records `status='failed'`
- [x] Performance — set-based SQL for silver/gold; 5,000-row insert batches;
      one indexed anti-join per file for the row watermark
- [x] Security / PII — `ip_addr` popped from `_raw` before every bronze write
      (V8); asserted in `test_landing.py`
- [x] Tests — 24 new (`pytest` 59 passed total); `ruff` clean
- [x] Docs — this file; `UPDATE.md` + `INGESTION.md` + phase doc are Commit 5

---

## What Was Implemented

### Purpose

Get data into the warehouse the same way every time: discoverable inputs,
validated rows, an append-only raw layer, a deterministically-rebuilt typed
layer that collapses export duplicates, and a star that is a provable function
of the raw layer — so the "numbers unchanged" API baseline diff stays meaningful.

### Features

**Migration 011 (Commit 1)**

| object | purpose |
|---|---|
| `bronze.raw_streams.row_fingerprint CHAR(64)` + `(user_id, row_fingerprint)` index | row-level dedup key, written at land time from `normalize.row_fingerprint` |
| `silver.streams.row_fingerprint CHAR(64)` (no unique constraint) | carried from bronze by `dedup.py` |
| `bronze.ingest_state` — `UNIQUE(user_id, file_hash)` | file-level idempotency: a known file is a DB-enforced no-op |
| `bronze.quarantine` — `_ingest_id` **nullable**, `ON DELETE SET NULL` | rows rejected *pre*-landing (an unparseable `ts` has no bronze row to point at) |
| `bronze.ingest_run` | per-run metrics with the V4 invariants; `status CHECK IN ('running','success','failed','partial')` |
| `bronze.ingest_run_user` | per-run per-user breakdown; sums equal the `ingest_run` row |
| `public.bronze_{ingest_run,ingest_run_user,quarantine,ingest_state}` views | Blocker B1: `backends.py`'s `_IDENT_RE` rejects dotted schema names; Phase 13's `/api/health/data` reads these |

Terminal destructive step (Owner Decision 6): `TRUNCATE silver.streams` then
`DELETE FROM bronze.raw_streams WHERE _source_file = 'phase11_backfill:streaming_history'`.
Removes the one-time migration-008 backfill so bronze has a single writer (the
pipeline) and `row_fingerprint` has no legacy rows to backfill from a
second, drift-prone SQL definition. `gold.fact_streams` is untouched — the app
keeps serving the old star until the next build.

**Pipeline modules (Commit 2)**

- **`discover.py`** — adapts to the repo's `data/` layout as it is on disk
  (Owner Decision 1, no file moves):
  - primary → `data/streaming_[0-9]*.json` (the `[0-9]` class already excludes
    `streaming_video_*.json`)
  - 9 others → `data/other users/<slug>/Streaming_History_Audio_*.json`
  - belt-and-braces exclude on `*video*` and `data/Spotify Account Data/`
  - deterministic sort by `(slug, rel_path)`; `USER_SLUGS` moved here verbatim
    from `load_multi_user_data.py`; `only=[...]` restricts to a slug subset
  - result on this repo: 27 files across all 10 slugs, no video

- **`landing.py`** — append-only bronze landing, two-tier watermark:
  1. *file skip* — `SELECT 1 FROM bronze.ingest_state WHERE user_id=? AND file_hash=?`;
     hit → return, no parse. Keying on `file_hash` (not `source_file`): a renamed
     identical file is skipped, a same-named changed file is reprocessed.
  2. *row incremental* — on a superset re-export, land rows with `ts >= watermark`
     whose `row_fingerprint` is not already in bronze for that user (one indexed
     `ANY(:fps)` batch lookup). `>=` **plus** the fingerprint anti-join, not
     strict `>`, so a play sharing the watermark second is not lost and a
     half-failed run resumes without duplication.
  - `_raw` is the row dict **with `ip_addr` popped** (V8) — the single most
    important line; the replaced `load_json_to_supabase.py` kept it.
  - `read_export` falls back to element-by-element salvage on `JSONDecodeError`;
    non-dict array elements are wrapped so `validate.py` quarantines them as
    `row_not_a_dict`.
  - `get_or_create_user` maps the `primary` slug to the existing
    `is_primary=TRUE` row (`tanmay` in this repo) — a partial-unique index
    forbids a second primary, so it never inserts `is_primary=TRUE`.
  - 5,000-row insert batches; `ingest_state` upserted `ON CONFLICT (user_id,
    file_hash) DO UPDATE` so a mid-file crash converges on re-run.

- **`schemas.py` + `validate.py`** — Pandera `DataFrameSchema`, `lazy=True`,
  `strict=False` (real exports have 23 keys, fixture 17 — never reject on column
  set), `coerce=False`. Runs **pre-landing** on the parsed dicts via a pandas
  DataFrame. Rule vocabulary written to `bronze.quarantine.rule`:

  | rule | condition | severity |
  |---|---|---|
  | `ts_missing` | `ts` absent / null / empty | blocking |
  | `ts_unparseable` | present but `to_utc(ts)` is `None` | blocking |
  | `ms_played_range` | `< 0` or `> 86_400_000` | blocking |
  | `music_row_track_name` | `spotify_track_uri` present, track name null/blank | blocking (dataframe-level check) |
  | `platform_type` | `platform` present and not a `str` | blocking |
  | `row_not_a_dict` | array element is not a JSON object | blocking (pre-Pandera) |
  | `reason_start_enum` / `reason_end_enum` | not in the 10 / 11 observed values | **warn** → land, counted in `ingest_run.detail` |

  A null `ts` trips Pandera's implicit `not_nullable` check (column is
  `nullable=False`), which `validate.py` maps to `ts_missing`; a present-but-bad
  `ts` trips the custom `ts_parseable` check → `ts_unparseable`. Missing
  `ms_played` is **not** a reject (coerced to 0 downstream).

- **`dedup.py`** — silver full-rebuild:
  ```sql
  SELECT d.* FROM (
    SELECT b.*, ROW_NUMBER() OVER (PARTITION BY b.user_id, b.row_fingerprint
                                   ORDER BY b._ingest_id) AS _rn
    FROM bronze.raw_streams b WHERE b.ts IS NOT NULL
  ) d WHERE d._rn = 1
  ```
  Tie-break: **keep the lowest `_ingest_id`** — the first-landed occurrence,
  deterministic because `_ingest_id` is a BIGSERIAL assigned in file order. Not
  a DB unique constraint: bronze must retain dupes verbatim, and a constraint on
  silver would make the rebuild *fail* on a legitimate dupe instead of *counting*
  it. `dedup_report(conn)` is the standalone V5 measurement (per-user
  bronze/silver/fact).

- **`enrich.py`** — `stage_dim_{user,time,artist,artist,track,album}` +
  `stage_fact_streams`, moved verbatim from the old `build_star_schema.py` (one
  definition — Phase 11's V4 gate already caught a stale duplicate copy). The
  `ON CONFLICT DO NOTHING` stub inserts guarantee every silver `artist_key` /
  `track_key` has an FK target, so **no fact row is ever dropped** for a missing
  dimension. `match_rates()` measures against `audio_source='enriched'` — the
  meaningful enrichment rate, not the trivially-~100% FK-presence rate — and
  reports both. `verify_v1()` rewritten for the dedup era:
  - V1a `bronze(ts≠null) − dups_dropped == silver`, per user
  - V1b `silver == gold.fact_streams`, per user, exact
  - V1c `fact_streams == DISK_FACT_COUNTS[user]` when the constant is known
    (left empty pending sign-off on the measured numbers)

- **`metrics.py`** — `start_run` / `record_user` / `bump_run` / `finish_run` /
  `latest_run`. **Every function opens its own short-lived connection from
  `engine` and commits immediately** — these writes are *outside* the pipeline
  transaction, so a failed run does not roll back its own `status='failed'`
  record. `record_user` / `bump_run` do additive `x = x + :x` updates.

- **`build_star_schema.py` refactor** — `discover + land` (own transaction per
  file), then the whole silver → gold rebuild in **one** `engine.begin()` (a
  mid-rebuild failure leaves the previous star serving the app), then MV refresh
  in its **own** transaction after the rebuild commits (a `REFRESH` inside the
  TRUNCATE/INSERT txn would see pre-commit state). Same CLI + exit-code contract
  (0 = V1 pass, 1 = mismatch) and the same stage log, so
  `capture/compare_api_baseline.py` keep working. New flags: `--only <slugs>`,
  `--no-land`.

### Flow

```
discover_files(root, only)                         # 27 DiscoveredFile, sorted
      │
      ▼  per file, own txn
get_or_create_user → user_watermark
land_file(conn, df, user_id, run_id, watermark)
      │  tier 1: file_hash in ingest_state?  → skip, no parse
      │  read_export → validate_rows → write_quarantine   (pre-landing)
      │  tier 2: ts >= watermark AND fingerprint not in bronze
      │  INSERT bronze.raw_streams (_raw has NO ip_addr)   batches of 5000
      │  UPSERT bronze.ingest_state ON CONFLICT (user_id, file_hash)
      ▼
──────────── one engine.begin() ────────────
TRUNCATE gold.fact_streams
build_silver(conn)        # ROW_NUMBER dedup, keep min _ingest_id
stage_dim_user/time/artist/track/album(conn)
stage_fact_streams(conn)
report_match_rates(conn) ; verify_v1(conn)
────────────────────────────────────────────
      ▼  own txn
SELECT refresh_all_views()   # monthly_stats / top_artists / top_tracks
```

### Usage

```bash
# migrations (011 now pending)
cd apps/api && python db/migrate.py            # --dry-run / --status also work

# full pipeline, all users
python scripts/build_star_schema.py

# one or more users
python scripts/build_star_schema.py --only primary amit

# rebuild silver/gold from existing bronze, no landing
python scripts/build_star_schema.py --no-land

# tests (DB-backed tests skip themselves unless DATABASE_URL is set)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/spotify \
  python -m pytest tests -q
```

---

## Verification Performed

| gate | result |
|---|---|
| 011 applies; `--status` shows 011; second `migrate.py` is a no-op | PASS |
| backfill rows gone (`bronze.raw_streams` → 0); `gold.fact_streams` still 71,052 | PASS |
| full pipeline run: primary 70,817 raw → 70,635 silver/fact (182 dups) | PASS — matches plan target |
| total dedup: 1,404 dups dropped across 11 users | PASS — matches plan prediction |
| V1 (a/b/c) per user | PASS all 11 |
| quarantine empty on real data | PASS (0 rows) — as the plan predicted |
| V3 gate: `malformed_streaming_history.json` (7 rows) | 6 quarantined, 6 distinct rules, 1 landed — PASS |
| idempotent re-run: `files_new=0`, `rows_landed=0`, bronze count identical | PASS |
| `--no-land` rebuild: V1 PASS, exit 0 | PASS |
| live API baseline vs `outputs/baseline/pre_phase11` | 25 identical / 19 changed / 0 errored |
| `pytest` | 59 passed (35 pre-existing + 24 new) |
| `ruff check` on new code | clean |

**API baseline diff — every one of the 19 changed routes is row-count-derived:**
`/api/stats/overview` (`total_streams 70913 → 70518`), `/api/time/monthly`,
`/api/stats/{hourly,daily,yearly}`, `/api/top/{artists,tracks}` (a rank swap at
#5–6, 146 vs 145 streams — one dedup), etc. `/api/stats/date-range` did **not**
change → the primary user's video rows were not the global min/max `ts`.
`/health.timestamp` is volatile and expected. This is exactly the non-clean diff
the plan predicts for Commit 2 (the −235 video + −182 dedup on the primary user);
Commit 4's diff, by contrast, must be byte-clean.

`outputs/baseline/post_phase12` was captured as the new reference.

---

## Deviations From the Plan

| # | Deviation | Why |
|---|---|---|
| A | Migration 011 also runs `TRUNCATE silver.streams` before the backfill `DELETE`. | The plan assumed `silver.streams._ingest_id` was a nullable FK / silver was empty. It is a **plain, populated** FK to `bronze.raw_streams` (008:116), so the `DELETE` hit `streams__ingest_id_fkey`. Silver is a deterministic full rebuild from bronze on every run, and the app reads `gold` — so truncating it costs nothing and the next build repopulates it. |
| B | No clean `pre_phase12` API baseline exists. | The local DB was already rebuilt by the time the baseline step was reached. Diffed the live API against `pre_phase11` instead; every diff is fully explained by the −235 video + −182 dedup on the primary user. `post_phase12` captured as the new reference. `pre_phase11` is now superseded (record in `UPDATE.md` at Commit 5). |
| C | `dagster` stays in `requirements-dev.txt`; only `pandera` moved to `requirements.txt` this commit. | No `app/` code imports `dagster` yet — the `dagster_project/` package is Commit 3. `pandera` is imported by `app/ingest/validate.py` now, so it moved. |
| D | `enrich.DISK_FACT_COUNTS` left empty → V1c is skipped per user. | The per-user disk-derived fact-count constants (70,635 primary, plus the 9 others) should be signed off against a real full run before being pinned as an assertion. V1a/V1b still run and pass. |
| E | `_ts_parseable` / NaN checks use an `_is_nan()` helper instead of `v == v`. | `ruff` `PLR0124` ("name compared with itself"); `pd.isna` on a float is equivalent and readable. |

Owner Decisions 1–8 from the plan were all followed as written (decision 6's
destructive step is deviation A's context, not a change to the decision).

---

## Next Steps

**Commit 3 — Dagster project + compose service** (largest remaining piece)
- `apps/api/dagster_project/{__init__,definitions,assets,resources,jobs,schedules}.py`
  - `PostgresResource(ConfigurableResource)` using `make_engine` (not the
    `lru_cache`d `get_engine`); `DataRootResource`
  - `raw_streams` as `StaticPartitionsDefinition` over the 10 slugs
    (`discover.ALL_SLUGS`); `quarantine` + `silver_streams` unpartitioned;
    `gold_star` as a `@multi_asset` (one transaction, six named outs);
    `refreshed_views` terminal asset with the V7 assertion
- `apps/api/pyproject.toml` (`[tool.dagster] module_name`), `dagster_home/dagster.yaml`
  (run/event-log/schedule storage → same Postgres, `schema: dagster`)
- `dagster-postgres==1.13.20` pin; move `dagster` → `requirements.txt`
- `docker-compose.yml` `dagster` service (`dagster dev -h 0.0.0.0 -p 3000`,
  `DAGSTER_HOME`, `INGEST_DATA_ROOT`, `./data:/app/data:ro`, named
  `dagster_home` volume, `depends_on: db(healthy), api(started)` — do **not**
  re-run `migrate.py` here)
- README / `start.sh` port table (web 3010, api 3011, dagster 3000)
- Verify: `dagster job execute -j nightly_ingest_job`; immediate re-run ⇒
  `files_new=0`; malformed-fixture test; `docker compose up` → lineage graph at
  localhost:3000

**Commit 4 — migration 012, RPC repoint** (mechanical, exacting; separate per
Owner Decision 3)
- `apps/api/migrations/012_repoint_analytics_functions.sql` — the 10 functions
  from `006_analytics_functions.sql` still reading `streaming_history`
  (`get_discovery_timeline`, `get_artist_loyalty`, `get_artist_obsessions`,
  `get_reflective_insights`, `get_weekend_weekday_comparison`,
  `get_most_repeated_tracks`, `get_monthly_diversity`, `get_listening_heatmap`,
  `get_milestones_list`, `get_flashback`)
- Copy each body verbatim; change **only** `FROM streaming_history` →
  `FROM gold.fact_streams` and `master_metadata_{track,album_artist,album_album}_name`
  → `fs.{track,artist,album}_name`. **Never** map to `fs.artist_key` (casing
  trap R1 — "KALEO"/"Kaleo" etc.). `DROP FUNCTION IF EXISTS` with exact
  signature before each (Blocker B2).
- Verify: baseline diff against `post_phase12` must be **byte-clean** — zero
  numbers move. `SELECT proname FROM pg_proc WHERE prosrc ILIKE '%streaming_history%'`
  → none of the 10 remain (V10).

**Commit 5 — docs + legacy loader deprecation**
- `documentation/INGESTION.md` (new — explain the TRUNCATE-in-one-txn model, the
  two idempotency keys, `streaming_history` as frozen legacy)
- `UPDATE.md` row → DONE + log entry recording all deviations; note `pre_phase11`
  superseded
- `documentation/<ts>_phase_12_dagster_ingestion.md` per the CLAUDE.md schema
- `load_json_to_supabase.py` + `load_multi_user_data.py` → thin deprecated
  wrappers; **delete** `load_json_to_supabase.py`'s blocking `input()` and its
  `ip_addr`-retaining `transform_record` (the last code path that could write
  `ip_addr` — a PII footgun). Both import `USER_SLUGS` from `discover.py`.
- Populate `enrich.DISK_FACT_COUNTS` once the per-user numbers are signed off.

---

## Conclusion

The ingestion schema and the pipeline library are in place and proven against
the real data: the star is now a deterministic, idempotent, re-runnable function
of an append-only bronze layer, video/podcast files are out of scope, and 1,404
export duplicates are collapsed with a documented tie-break. Every API number
that moved is accounted for by those two effects. What remains (Commits 3–5) is
orchestration wiring, the final RPC repoint, and documentation — no further data
model design.
