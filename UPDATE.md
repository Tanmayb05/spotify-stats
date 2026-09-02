# UPDATE.md — Roadmap Progress Tracker

**Roadmap:** `documentation/20260901_013603_roadmap_trimmed_5features.md`
(the trimmed 8-phase / 3-page / 5-feature plan — the one to execute).
Superseded: `documentation/20260831_231735_roadmap_de_ds_platform.md` (13-phase version).

This file is the **single source of truth for roadmap status**. When someone asks
"what's remaining", read this. When someone says "start the next phase", find the first
phase below whose status is not `DONE`, read that phase's spec in the roadmap doc, execute
it, then update the row + append to the log here.

---

## Status legend
- `NOT STARTED` — no work done
- `IN PROGRESS` — started, not finished (see the log for where it stopped)
- `BLOCKED` — needs a decision or an external step (say what, in the log)
- `DONE` — implemented, verified per the roadmap's "Verify" step, committed

---

## Phase status

| Phase | Title | Effort | Feature(s) | Status | Branch / PR | Completed |
|---|---|---|---|---|---|---|
| 9  | Repo hygiene & public-safe history | S | — | DONE | `chore/phase-9-repo-hygiene` | 2026-09-01 |
| 10 | Local infra: Docker Compose + migration runner + DB backend switch | M | — | DONE | `feat/phase-10-local-infra` | 2026-09-01 |
| 11 | Star schema + enrichment into Postgres + bronze/silver/gold | L | 1 (schema) | DONE | `feat/phase-11-star-schema` | 2026-09-01 |
| 12 | Dagster ingestion pipeline (incremental / idempotent / quarantine) | XL | 1 | DONE | `feat/phase-12-dagster-ingestion` | 2026-09-02 |
| 13 | DQ suite + Data Health page + cull to 3 pages | M | 2 | DONE | `feat/phase-13-data-quality` | 2026-09-02 |
| 13.5 | Behavioral EDA notebook set (decision-support reference) | M | — (feeds 3,4,5) | NOT STARTED | — | — |
| 14 | Feature store + nightly compute + dual-loader collapse | L | 3 | NOT STARTED | — | — |
| 15 | 4 recommenders + eval harness + explainable recs + human-eval loop | XL | 4 + 5 | NOT STARTED | — | — |
| 16 | Production loop + tests + CI + README/architecture/write-up | L | — | NOT STARTED | — | — |

**Next phase to start:** Phase 13.5.

---

## The 5 target features (for reference)

1. **Orchestrated ingestion pipeline** — Dagster asset graph raw→bronze→silver→star,
   incremental + idempotent, quarantine lane, ingestion metrics. *(Phases 11–12 — DONE)*
2. **Data-quality suite + Data Health page** — Pandera + SQL check runner, 6 categories,
   pipeline gate. *(Phase 13)*
3. **Behavioral feature store + per-user profiles** — materialized `gold.user_*` tables,
   nightly Dagster refresh, dual-loader collapse. *(Phase 14)*
4. **4 recommenders + rigorous offline evaluation** — popularity / content / collaborative
   (implicit ALS) / hybrid; per-user time-based split; 9 metrics; 5 experiments; ablation.
   *(Phase 15)*
5. **Explainable recommendations + human-evaluation loop** — "why this track" + blind
   10-user rating mode, human-vs-offline comparison. *(Phase 15)*

Final app = **3 pages**: Insights, Recommendations, Data Health.

---

## How to update this file (rules for Claude)

**When starting a phase:**
1. Set that phase's row status to `IN PROGRESS`, fill the `Branch / PR` cell once a branch
   exists.
2. Append a log entry: `## Phase <n> — started <date>` with a one-line plan.

**While working:** if you stop mid-phase, update the log entry with exactly what is done
and what remains, so the next session can resume without re-deriving.

**When a phase is verified + committed:**
1. Set the row status to `DONE`, fill `Completed` with the date, `Branch / PR` with the
   PR number.
2. Append to the log: what shipped (files created/modified, migrations applied), the
   verification result, any deviations from the roadmap spec, and any follow-ups.
3. Update **"Next phase to start"** above.
4. Also write the phase's own detailed doc
   `documentation/YYYYMMDD_HHMMSS_phase_<n>_<name>.md` per the CLAUDE.md schema (this is
   the deep record; UPDATE.md is the index).

**When something in the roadmap turns out wrong or infeasible:** note it in the log under
the current phase, and if it changes later phases, add a `> ROADMAP DEVIATION` note to
the affected rows.

---

## Log

_(newest entries at the bottom)_

### Phase 9 — done 2026-09-01 · branch `chore/phase-9-repo-hygiene`

**History rewrite** (`git filter-repo`, `.git` 53 MB → 7.1 MB, 25 → 24 commits — one
became empty and was pruned):

- Purged from **all history**: `data/other users/` (9 friends' raw `*.zip` Spotify
  exports, introduced in `7d16c08`), `data/Spotify Account Data/` (owner address +
  payments + identity), `data/streaming_*.json` (6 files, each row had `ip_addr`),
  `data/unique_*.csv`, `data/failed_lyrics.csv`, `data/songs_processing_queue.csv`,
  `outputs/data/songs_info.json` (45 MB), `outputs/data/artists_info.json`,
  `outputs/lyrics*` (`lyrics-1.json` + `lyrics/`).
- Redacted two real IPv4 strings that had appeared as example values in design docs /
  the roadmap spec → `REDACTED_IP` (the literals are deliberately not repeated here).
- Full backup mirror kept at
  `/Users/tanmaybhuskute/Documents/spotify-insights-backup-pre-phase9.git` — **do not
  delete until the remote is confirmed clean.**
- Working-tree data files restored from the mirror so the local app still runs; they
  are now `.gitignore`d.

**Files** (commit `e3025c8`): `.gitignore` rewrite (personal-data + env rules were
commented out), new `LICENSE` (MIT, source only), `SECURITY.md`, `data/README.md`,
`data/fixtures/sample_streaming_history.json` (40 synthetic rows, no `ip_addr`);
`apps/api/requirements.txt` now includes `supabase` (was a missing hard runtime dep)
and is `==`-pinned; new `apps/api/requirements-dev.txt` (pytest / httpx / ruff /
pandera / dagster); root `requirements.txt` `==`-pinned; README "Data & privacy"
section.

**Verify:** no PII paths and no real IP literals anywhere in history (exhaustive blob
scan on a **fresh clone of the pushed remote**); `pip install -r apps/api/requirements.txt`
clean + `pip check` OK + `import supabase`/`fastapi`; fixture parses, `ip_addr` absent
from every row; `LICENSE`/`SECURITY.md`/`data/README.md` present; `git ls-files` shows
no PII at HEAD; `.git` 7.3 MB. On the working repo (has `spotify-insights.env`):
`import app.main` OK, `uvicorn app.main:app` boots, `/health` → 200, JSON loader reads
70,817 records. Credential-less boot still fails at import (`SupabaseDataLoader()` at
`supabase_data_loader.py:807`) — pre-existing, fixed by Phase 10, out of scope here.

**Dependency fixes from the fresh-clone test:** `supabase==2.22.0` (the `.venv` version)
is **yanked on PyPI** and breaks on Python 3.14 → pinned `2.31.0`. `pydantic==2.12.0`
has a `FieldInfo` bug breaking `supabase-auth` on 3.14 → pinned `2.12.3`. Both verified
on Python 3.13 + 3.14.

**Remote actions (force-push):** `main` rewritten + force-pushed; stale
`origin/feat/multi-user-analytics-switch` force-deleted (unmerged, carried the purged
blobs). Anyone with a pre-2026-09-01 clone must re-clone. Residual: old blob SHAs may
stay fetchable via direct GitHub URL until GitHub GC — no ref points at them.

**Deviations from spec:** (1) also purged `data/Spotify Account Data/` and the big
`outputs` JSON blobs and `data/streaming_*.json` — the roadmap only named
`data/other users`; owner approved the wider scope this session. (2) filter-repo
removed the tracked data files from the working tree, not just history — restored the
app-needed ones (`data/streaming_*.json`, `outputs/data/{songs,artists}_info.json`)
from the backup mirror. (3) Git LFS not used (`git lfs` absent) — download-step /
`data/README.md` instead.

### Phase 10 — done 2026-09-01 · branch `feat/phase-10-local-infra`

Detail: `documentation/20260901_103036_phase_10_local_infra.md`.

`docker compose up` now brings up Postgres + API + web with **no Supabase account
and no credentials**. `DB_BACKEND=supabase` stays the default, so the deployed demo
is unchanged.

**Shipped:**

- **Backend adapter** `apps/api/app/db/backends.py` — the loader reached the DB
  through only 3 primitives (`.rpc`, `.table().select()`, `.range()` pagination), so
  those became a `DBBackend` protocol with `SupabaseBackend` (PostgREST) and
  `LocalBackend` (SQLAlchemy + psycopg3). The loader's ~800 lines of result-shaping
  are **untouched**; both backends call the same SQL functions from `migrations/`,
  which stays the single source of truth. Sets up the Phase 14 loader collapse.
- **Lazy instantiation** — `supabase_data` is a proxy built on first attribute
  access. Fixes Phase 9's open follow-up: `import app.main` used to raise without
  credentials because every route imported an eagerly-constructed loader.
- **`apps/api/app/config.py`** — first centralised env handling; real env vars beat
  `spotify-insights.env` (how Compose injects). `DB_BACKEND`, `DATABASE_URL`,
  `CORS_ORIGINS` (defaults to the previous four origins).
- **`apps/api/db/migrate.py`** — ordered, tracked in `schema_migrations`,
  `--dry-run` / `--status`. Tracking is required, not cosmetic: `001` uses bare
  `CREATE INDEX` / `CREATE MATERIALIZED VIEW` and is not replay-safe.
- **`apps/api/scripts/seed_local_db.py`** — fixture by default or `--from-dir`;
  refuses to double-seed; keeps exactly one `is_primary` user; non-concurrent MV
  refresh (`refresh_all_views()` uses `CONCURRENTLY`, which errors on a
  never-populated view).
- **`apps/api/scripts/check_backend_parity.py`** — diffs all 34 loader methods
  across backends. Reusable by Phase 16 CI.
- Dockerfiles ×2, `.dockerignore` ×3 (incl. root), `docker-compose.yml`,
  `documentation/LOCAL_DEV.md`. The API image builds from the **repo root** context so
  the committed fixture is baked in at `/app/data/fixtures` — the stack seeds itself
  without depending on a bind mount. Found by testing a real fresh clone, where
  `./data` mounted empty and seeding crashed; the root `.dockerignore` keeps ~800 MB
  (`.git`, `.venv`, `outputs/`, real exports) out of the build context.

**Three landmines found that the roadmap did not anticipate:**

1. **Migration 002 vs 004 ambiguity.** Every function in 002 is redefined by 004
   with an added `p_user_id UUID DEFAULT NULL`; both variants have all-default args,
   so applying both breaks calls at runtime — reproduced on PG16:
   `ERROR: function get_top_artists(limit_count => integer) is not unique`.
   The runner records 002 as applied **without executing it** (`SUPERSEDED` set);
   file kept as history with a header explaining why.
2. **PostgREST vs psycopg type fidelity.** PostgREST serialises over JSON
   (timestamps as ISO strings, numerics as floats); psycopg returns native
   `datetime`/`Decimal`/`UUID`. Added `_jsonify`. Without it `get_monthly_data`
   raised `'datetime.datetime' object is not subscriptable` and 6 delegated methods
   raised `TypeError` — all of which the loader's except-and-return-empty would have
   shipped as **blank charts, not errors**.
3. **`RETURNS jsonb` vs `RETURNS TABLE`.** 4 functions return scalar jsonb consumed
   as the object itself. Verified on PG16 that such a function yields one column
   named after the function; `LocalBackend.rpc` unwraps exactly that case.

**Verify:** credential-less `import app.main` OK (no env file at all); migrate
second run = no-op; zero ambiguous overloads in `pg_proc`; clean
`down -v` + `up --build` → api healthy in 2s, **44/44 routes HTTP 200**, leaderboard
returns fixture users, web 200 and proxies to the API container; **parity: all 34
methods agree** across backends with comparable data, and keys/types identical
field-by-field on 12 representative endpoints; Supabase default path unchanged
(same CORS list, 10 real users, uvicorn smoke all 200); seeder loaded 71,052/71,052
export rows; `ruff --select E9,F` clean.

Seven methods return empty against the 40-row fixture — all are minimum-data
thresholds in SQL (`HAVING COUNT(*) >= 10`, `>= 5`, 3-consecutive-days), and all
populate against the real 71k-row export. Not a regression.

**Deviations:** roadmap's verify says "web :5173"; real ports are **3010** (web) /
**3011** (api) and were used. `app/ingest/normalize.py` is listed in Phase 10's file
list but its own note assigns it to Phase 11 — seeder normalization is inline for
now, Phase 11 extracts it.

**Follow-up for Phase 11:** `/api/reco` + `/api/simulate` still read gitignored
`outputs/data/{songs,artists}_info.json`, absent on a fresh clone. Compose mounts
`./outputs` read-only and the loader now warns explicitly instead of failing
silently; Phase 11's `load_enrichment_to_db.py` removes the file dependency.

### Roadmap change — 2026-09-01 · EDA notebooks reinstated as Phase 13.5

> ROADMAP DEVIATION (scope addition, owner-requested). No phase renumbered.

The roadmap's "Decisions locked" table **cut the 8-notebook behavioral-EDA set** on the
grounds that "notebooks are effort without a product surface". Owner reinstated them: they
*do* have a surface — **decision support**, to be consulted when Phase 14/15 design calls
are in doubt. Cut reversed; roadmap doc updated, not silently diverged.

**New phase 13.5 — Behavioral EDA notebook set · M · read-only.** Full spec now in
`documentation/20260901_013603_roadmap_trimmed_5features.md` under `### PHASE 13.5`.

**Why 13.5 specifically** (both constraints have to hold at once):
- *Data must be trustworthy* → after **13**: star schema exists (11), is incrementally
  populated (12), and is DQ-gated (13). A chart cannot be quietly wrong.
- *Must precede the decisions it informs* → before **14**: P14 picks `context_label`
  buckets, `night_share` / `repeat_ratio` cutoffs, affinity half-life, behavior-vector
  dims, and runs the **genre-affinity kill gate**; P15 picks CF weighting and candidate
  pool. After P15 the notebooks would be archaeology; before P11 they would read the
  un-modeled wide table and be invalidated by the star schema.
- Decimal number chosen so **14/15/16 keep their numbers** — no churn in this file's rows,
  branch names, or the Phase 9/10 docs already written.

**Shape:** `apps/api/notebooks/` — `README.md` (incl. a "which notebook answers which
question" map), `_common.py` (shared engine/loader/palette/`save_fig`/`decision`; no
hardcoded DSN — reuses `app/config.py` + `db/session.py`), 8 notebooks
(`01_dataset_overview` → `08_candidate_pool`), and `documentation/EDA_FINDINGS.md` — a
2–4 page digest, one section per notebook, **question → chart → the number a later phase
should quote**. That digest is the fast path when you don't want to boot Jupyter.

Each notebook ends with a **`## Decision inputs`** cell. P14's sequencing note now says its
feature definitions should quote those cells rather than pick thresholds by hand.

**Two things this phase must not get wrong:**
1. **PII.** Notebook outputs embed real listening history for 10 named people. Committed
   with outputs stripped (`nbstripout`); non-primary users aliased `user_02…user_10` by the
   `_common.py` loader; quoted charts go to gitignored `outputs/eda/`, only aggregates to
   `documentation/assets/eda/`. P16 CI gains an `nbstripout --verify` step.
2. **The `.gitignore` trap.** Phase 9 kept a blanket `*.ipynb` ignore *because* notebooks
   were cut — so a new notebook would silently not be committed. 13.5 adds
   `!apps/api/notebooks/*.ipynb`. This also unblocks P15's `evaluation.ipynb`, which had
   the same latent problem: CI would have had no file to execute.

**Other roadmap edits made for consistency:** "Decisions locked" EDA row rewritten
(cut → reinstated, with the placement rationale); "What was cut" row marked UNCUT;
sequencing rationale gained item 3 (later items renumbered); effort roll-up gained the
13.5 row; P16 CI `notebook` job widened from `evaluation.ipynb` alone to all 9 notebooks
plus the stripout check; P16 `RESEARCH_WRITEUP.md` now sources its 2–3 EDA charts from the
13.5 notebooks via `save_fig` instead of rebuilding them, so the two cannot disagree.

**Next phase to start is unchanged: Phase 11.**

### Phase 11 — done 2026-09-01 · branch `feat/phase-11-star-schema`

Detail: `documentation/20260901_174048_phase_11_star_schema.md`. Design/blocker analysis
and pre-declared deviations: `documentation/20260901_152320_phase_11_star_schema_PLAN.md`.
Data model reference: `documentation/DATA_MODEL.md`.

Turned `streaming_history` into a Medallion star schema (`bronze`/`silver`/`gold`),
populated real dimension tables from on-disk enrichment JSON, repointed 3 materialized
views + 8 hottest RPCs at `gold.fact_streams` — **verified numerically unchanged** via a
full pre/post 44-route API baseline diff.

**Shipped:** migrations `008_medallion_schemas.sql` (bronze+silver DDL, one-time bronze
backfill), `009_star_schema.sql` (gold DDL: `dim_user`/`dim_time`/`dim_artist`/
`dim_track`/`dim_album`/`fact_streams`/`track_lyrics`/`recommendation_events` + `public`
compat views for Blocker B1), `010_mvs_on_star.sql` (repoints `monthly_stats`/
`top_artists`/`top_tracks` + `get_overview_stats`/`get_date_range`/`get_platform_stats`/
`get_hourly_distribution`/`get_daily_distribution`/`get_yearly_comparison`/
`get_listening_streaks`/`_mood_rows` at `gold.fact_streams`, exact `DROP FUNCTION IF
EXISTS` before each per Blocker B2). New `app/ingest/` package (`normalize.py`,
`salvage.py` — extracted/shared, 35 unit tests). New scripts:
`load_enrichment_to_db.py` (idempotent JSON→gold upserts), `backfill_artist_tags.py`
(opt-in MusicBrainz/Last.fm genre backfill), `build_star_schema.py` (orchestrates
bronze→silver→gold, re-runnable), `capture_api_baseline.py` +
`compare_api_baseline.py` (the V4 gate tooling). Closed Blocker B5:
`data_loader.py._load_track_metadata()` now reads `gold.dim_track`/`dim_artist` when
`DB_BACKEND=local`, falling back to the JSON files only when those tables are empty.

**Verify gate results (measured, not assumed):**
- V1 (fact completeness): **PASS** — 71,052 == 71,052 (primary user), exact.
- V2 (enriched tracks): **PASS** — exactly 808.
- V3 (artist enrichment): 4,536 `dim_artist` rows; **93.5%** artist match-rate of plays
  (plan measured 93.7% in a slightly different snapshot).
- V4 (numbers unchanged, full baseline diff): **PASS** after catching and fixing 2 real
  bugs mid-implementation (a stale container copy of `build_star_schema.py` missing new
  columns, and MVs left stale after a schema rebuild — both exactly what this gate is
  for). One `/api/reco` floating-point score drift was investigated exhaustively and
  ruled out as pre-existing/non-Phase-11 (see the phase doc's "investigated, ruled-out
  non-issue" section) — the DB-path and JSON-path metadata were proven bit-identical.
- V5 (genre coverage / D2 kill gate): pre-backfill 53.1% (exact match to plan);
  post-backfill **78.2%** (final, completed run — 682/1,886 candidate artists tagged
  via MusicBrainz, no Last.fm key configured). **Verdict: KEEP** `user_genre_affinity`
  as a full Phase 14 feature (cleared ≥75%).
- V6 (no ambiguous overloads): **PASS** — 0 rows.
- V7 (migration replay): **PASS** — idempotent; fresh-clone-equivalent stack applied all
  9 pending migrations cleanly, 44/44 routes 200.
- V8 (backend parity): **PASS** — all 34 methods agree across local/Supabase (Supabase
  credentials were testable in this environment).
- V9 (fresh-clone integrity): **PASS with a caveat** — boots/migrates/seeds/44-routes-200
  from a true git-tracked-files-only tree (no `outputs/`, no real `data/`). `/api/reco`
  and `/api/simulate` return empty (not non-empty) against the 40-row fixture alone —
  pre-existing fixture-size limitation (`RECO_EXCLUDE_TOP_PLAYED=25` > 20 rows/user),
  same class Phase 10 already documented for 7 other methods. B5 itself is proven
  separately against the real 71k-row dataset.
- V10 (no PII regression): **PASS** — no `ip_addr` in any new layer, no lyrics text
  anywhere, `git ls-files` clean.

> ROADMAP DEVIATION (all 6 pre-declared in the plan doc; none new beyond these):
> 1. Verify gate "≈340k" replaced with exact source-equality (measured 71,052 for one
>    user, not 340k).
> 2. `mood_proxy_*` columns ship empty — no real audio-features data exists in this repo
>    (Spotify's endpoint deprecated Nov 2024); `audio_source` defaults `'none'`.
> 3. Only 3 MVs + 8 RPCs repointed at `gold`; migration 006's remaining ~10 functions
>    (`get_milestones_list`, `get_flashback`, etc.) still read `streaming_history`
>    directly — Phase 12 finishes the move.
> 4. Dedup deferred to Phase 12 (`row_fingerprint` defined in `normalize.py`, unused this
>    phase) — required for this phase's "numbers unchanged" gate to mean anything.
> 5. Artist-tag backfill is opt-in/skippable (`backfill_artist_tags.py`), not an inline
>    pipeline step.
> 6. `_salvage_json_array` relocated to `app/ingest/salvage.py`, shared by the loader and
>    the new enrichment script (was duplicated before).

**Deviations beyond the plan's 6 pre-declared ones:** (a) `spotify-insights.env.example`
was updated for `LASTFM_API_KEY`, not `apps/api/.env.example` as the plan's file list
said — the config module actually loads `spotify-insights.env` at the repo root, so
that's the file a real deployer edits. (b) `data_loader.py._load_track_metadata()`
(the actual location of the B5 fix) lives in `app/services/data_loader.py`, not
`supabase_data_loader.py` as the task brief said — `SupabaseDataLoader` delegates heavy
compute to a per-user `SpotifyDataLoader` instance, and that delegate is where this
method has always lived. (c) `gold.fact_streams` gained three denormalized
`artist_name`/`track_name`/`album_name` columns beyond the plan's original column list,
required so migration 010's rewritten MVs could reproduce the pre-Phase-11 grouping
semantics (case-sensitive text, not the normalized `artist_key`) bit-for-bit — see
`DATA_MODEL.md`'s natural-keys section. (d) `requests==2.34.2` added to
`requirements-dev.txt` (not in the plan's file list) — needed by the two new baseline
scripts and the backfill script; not a FastAPI runtime dependency so kept out of
`requirements.txt`.

**Follow-up for Phase 12:** `bronze.raw_streams` + `_source_file`/`_ingested_at` are the
landing target; `app/ingest/normalize.py` (`row_fingerprint` especially) is written for
Phase 12 to consume; `build_star_schema.py`'s 7 stages map 1:1 onto the planned Dagster
asset graph; the ~10 remaining migration-006 functions still reading
`streaming_history` directly are Phase 12's to finish repointing.

**Next phase to start: Phase 12.**

### Phase 12 — done 2026-09-02 · branch `feat/phase-12-dagster-ingestion`

Detail: `documentation/20260902_000818_phase_12_dagster_ingestion.md`. Plan of record +
owner decisions: `documentation/20260901_204014_phase_12_dagster_ingestion_PLAN.md`.
Commits 1–2 record: `documentation/20260901_224259_phase_12_dagster_ingestion_commits_1_2.md`.
Durable pipeline reference: `documentation/INGESTION.md`.

Replaced the by-hand data load (two Supabase-only loader scripts + a one-time
migration-008 bronze backfill) with one **Dagster asset graph**: discover → validate →
land (bronze) → dedup (silver) → dims + fact (gold) → refresh MVs. Incremental,
idempotent, quarantine lane, per-run/per-user metrics. Also finished the Phase 11
star-schema migration by repointing the last 10 analytics RPCs off `streaming_history`.

**Shipped (5 commits):**

- `2fd02d7` **migration 011** — `row_fingerprint` columns; `bronze.ingest_state`
  (`UNIQUE(user_id,file_hash)` = file idempotency) / `quarantine` (nullable
  `_ingest_id`, quarantine is pre-landing) / `ingest_run` / `ingest_run_user`; four
  `public.bronze_*` compat views (Blocker B1). Terminal destructive step: `TRUNCATE
  silver.streams` + delete the migration-008 bronze backfill so bronze has a single
  writer.
- `b050473` **`app/ingest/` pipeline library** — `discover` / `landing` / `schemas` +
  `validate` / `dedup` / `enrich` / `metrics` (+ 24 unit tests). `build_star_schema.py`
  refactored 401 → 133 lines to a wrapper over the same modules — still a valid
  Dagster-free entrypoint and the API-baseline gate's driver.
- `6c266a5` **Dagster project + compose service** — `dagster_project/{__init__,
  definitions,resources,assets,jobs,schedules}.py`, `pyproject.toml`,
  `dagster_home/dagster.yaml` (run/event-log/schedule storage → same Postgres, schema
  `dagster`). Assets: `raw_streams` (10-slug `StaticPartitionsDefinition`; an
  unpartitioned job run lands ALL slugs) → `quarantine` + `silver_streams` →
  `gold_star` (`@multi_asset`, one transaction, 6 named outs) → `refreshed_views`
  (terminal, V7 assertion). `run_failure_sensor` flips a failed run's `ingest_run` row
  to `failed`. Compose `dagster` service on `:3000` (`dagster dev`, `depends_on` db
  healthy + api started, no `migrate.py`). `dagster` + `dagster-webserver` +
  `dagster-postgres==0.29.20` moved to `requirements.txt`.
- `711a51a` **migration 012** — `get_discovery_timeline`, `get_artist_loyalty`,
  `get_artist_obsessions`, `get_reflective_insights`, `get_weekend_weekday_comparison`,
  `get_most_repeated_tracks`, `get_monthly_diversity`, `get_listening_heatmap`,
  `get_milestones_list`, `get_flashback` repointed at `gold.fact_streams`. Bodies
  verbatim; only `FROM` + `master_metadata_*_name` → `artist_name`/`track_name`
  changed; never `artist_key`; exact `DROP FUNCTION IF EXISTS` before each.
- Commit 5 (this) — `INGESTION.md`; legacy loaders (`load_json_to_supabase.py`,
  `load_multi_user_data.py`) reduced to deprecation stubs with the
  **`ip_addr`-retaining code paths deleted** (last DB write path for `ip_addr`);
  `enrich.DISK_FACT_COUNTS` populated with the 10 measured per-user constants (V1c now
  active); this file; phase doc.

**Verify gate results (measured):**

- V1 (per-user `bronze − dups == silver == fact`): **PASS** all 11 users; primary
  70,817 → 70,635 (182 dups), hit the plan target exactly.
- V1c (`fact == DISK_FACT_COUNTS[user]`): **PASS** all 10 users with constants.
- V2 (idempotent re-run): **PASS** — 27 files `SKIP (file_hash_seen)`, `files_new=0`,
  `rows_landed=0`, bronze/silver/fact counts identical.
- V3 (malformed fixture): **PASS** — 6 quarantine rows, 6 distinct rules, 1 landed
  (Dagster-level `test_dagster_pipeline.py` + unit-level `test_validate.py`).
- V4 (metrics invariants): **PASS** — `status=success`, `dups_dropped=1404`,
  `rows_fact=338270`, `0 ≤ rates ≤ 1`.
- V5 (dedup delta, two numbers): scope **−1,082** (video/podcast) + dedup **−1,404**,
  reported separately.
- V6 (API baseline): Commits 2–3 non-clean, every diff = −235 video + −182 dedup on
  the primary user. Commit 4: 44 routes, **35 identical / 9 changed / 0 errored** —
  every changed route explained by the same grain cutover (`/api/discovery/reflect`
  `total_streams 71052 → 70635` exact; weekend-weekday + heatmap totals −417 exact;
  monthly-diversity −395 = 417 − 22 null-artist rows; loyalty/timeline/milestones/
  repeated-tracks per-group counts shift; `/health.timestamp` volatile). No
  unexplained diff. `outputs/baseline/post_phase12` re-captured.
- V7 (MV freshness): **PASS** — `sum(monthly_stats.total_streams) == count(fact_streams
  WHERE track_name IS NOT NULL)` = 70,518 for the primary user; `refreshed_views`
  asserts this and fails the run otherwise.
- V8 (no PII): **PASS** — `bronze.raw_streams._raw ? 'ip_addr'` → 0; the legacy
  loaders' `ip_addr` code paths deleted.
- V9 (migration replay): **PASS** — 011 + 012 apply once, second `migrate.py` a
  no-op; scratch-DB fresh apply 12/12.
- V10 (RPC repoint): **PASS** — none of the 10 read `streaming_history`.
  `get_skip_behavior` / `get_user_leaderboard` / `truncate_streaming_history` still
  name it — outside Phase 12's scope (the plan named exactly these 10).

> ROADMAP DEVIATIONS (full list in the phase doc; the material ones):
> 1. Migration 011 also `TRUNCATE silver.streams` (plain populated FK to bronze;
>    rebuilt every run, so free).
> 2. No clean `pre_phase12` baseline — diffed against `pre_phase11`, every diff
>    explained; `post_phase12` is the new reference, **`pre_phase11` superseded**.
> 3. Migration 012's baseline diff is **not byte-clean** (the plan predicted clean).
>    `public.streaming_history` was never deduped/video-stripped, so the 10 endpoints
>    move by exactly the grain delta Commit 2 applied to the hot RPCs. This is the
>    last `streaming_history → gold` cutover; every moved number is accounted for.
> 4. `assets.py` drops `from __future__ import annotations` (Dagster rejects stringized
>    `AssetExecutionContext`); `raw_streams` handles an unpartitioned job run;
>    `gold_star` doesn't finish the run — `refreshed_views` marks `success`, a
>    `run_failure_sensor` marks `failed`.
> 5. `test_dagster_pipeline.py` is opt-in (`DAGSTER_PIPELINE_TEST_DB=1`) — it
>    TRUNCATEs bronze/silver/gold, so throwaway-DB only.

**`public.streaming_history` is now frozen legacy** — no function reads it except
`truncate_streaming_history` (utility) and `get_skip_behavior` / `get_user_leaderboard`
(out of scope). The pipeline never writes it. Left populated-but-stale for Phase 13's
DQ cross-checks; dropping it is a later phase's job. Carries the old grain (71,052 for
the primary user vs `gold.fact_streams`' 70,635).

**Follow-ups for Phase 13:** `bronze.quarantine` + `bronze.ingest_run{,_user}` + the
`public.bronze_*` views are the read surface for `/api/health/data`;
`app/ingest/schemas.py`'s Pandera schema is the DQ rule-set starting point.
**For Phase 16 CI:** add `dagster job execute -j nightly_ingest_job` + `pytest
tests/test_dagster_pipeline.py` (both against a scratch Postgres) to the pipeline.

**Next phase to start: Phase 13.**

### Phase 13 — done 2026-09-02 · branch `feat/phase-13-data-quality`

Detail: `documentation/20260902_154500_phase_13_data_quality.md`.
Durable reference: `documentation/DATA_QUALITY.md`.

Data-quality suite as a pipeline gate + `/api/health/data` + a Data Health page,
and the web app cut to its final 3 pages.

**Shipped (5 commits):**

- `2332702` **migration 013** — `CREATE SCHEMA quality`; `quality.dq_run` (run
  header + rollup + status) and `quality.dq_result` (one row per check,
  `UNIQUE(dq_run_id, name, user_id)`); `public.dq_run` / `public.dq_result`
  compat views (Blocker B1, so `/api/health/data` works on both backends).
- `1ddbcec` **`app/quality/` library** — `checks.py` (21 checks via a `@check`
  registry, all 6 categories; 12 blocking / 9 warn; `THRESHOLDS` dict set below
  measured values with headroom), `pandera_schemas.py` (3 sample-based DataFrame
  contracts — narrowed, since 19/21 checks are SQL aggregates), `run.py`
  (`run_all` + `summarize` + the `python -m app.quality.run` CLI, exit 0/1/2).
  Own-connection persistence rule (a raising blocking check still leaves its
  `dq_run` row). 13 tests (`tests/test_quality.py`).
- `61b8049` **`data_quality` Dagster asset + `GET /api/health/data`** —
  `refreshed_views` stops owning `finish_run`; the new terminal `data_quality`
  asset (`deps=["refreshed_views"]`) owns it: `success` clean / `partial`
  warn-only / raise on blocking (→ `run_failure_sensor` → `failed`). Merges its
  `dq_*` summary into the `detail` JSONB `gold_star` wrote (R1). `/api/health/data`
  reads only `public.*` compat views via `DBBackend.select()`, each read caught,
  degrades to `has_run:false` HTTP 200 on Supabase. `tests/test_health_data.py`
  — the repo's first FastAPI TestClient test.
- `1c9ecb0` **frontend cull** — router + drawer down to 3: `/` Insights,
  `/recommendations`, `/data-health`. `Insights.tsx` merges Overview +
  ListeningPatterns + Discovery (existing charts, 3 staged `Promise.allSettled`
  waves). `DataHealth.tsx` new. `src/hooks/useTimeRange.ts` (extracted, slider
  re-clamp bug fixed), `src/theme/chartColors.ts`. Deleted 8 pages + routers
  `milestones/sessions/mood/sim`; `compare.py` → just `GET /api/compare/users`
  (UserSwitcher). `client.ts` −15 fns −heatmap; `types/api.ts` −~19 interfaces.
  `supabase_data_loader.py` untouched (Phase 14's collapse).
- Commit 5 (this) — `DATA_QUALITY.md`, `INGESTION.md` edits (graph + terminal
  asset + `streaming_history` note), `UPDATE.md`, phase doc.

**Verify gate results (measured):**

- `python -m app.quality.run` in compose → **31 results** (per-user freshness
  fans out ×10), 29 passed, **0 blocking**, 2 warned (`release_year=0` on 28
  tracks; 1 anomalous user-day), 0 skipped, exit 0.
- `/api/health/data` → 6 categories, `dq.status='warn'`, `ingest.status='partial'`,
  11 per-user rows. Old `/health` liveness blob unchanged.
- **Gate proven both ways:** injected a duplicate `_ingest_id`,
  `dagster asset materialize --select data_quality` → `IngestVerificationError`,
  step + run FAIL, `quality.dq_run.status='fail'` persisted despite the raise.
  `python -m app.quality.run` exited 1. Clean re-run → `RUN_SUCCESS`,
  `bronze.ingest_run.status='partial'`, `detail` carries both `gold_star`'s
  `artist_fk_rate` and the `dq_*` keys (R1 verified).
- 3 pages serve 200 in compose; `/overview` falls through to NotFound; deleted
  API routes 404; drawer = 3 items.
- `npm run lint` + `npm run build:check` clean. `pytest tests/` → **76 passed,
  3 skipped**.

> ROADMAP DEVIATIONS:
> 1. Migration is `013`, not `012` (`012_repoint_analytics_functions.sql` exists).
> 2. `data_quality` is a terminal **`@asset`**, not a Dagster asset check — the
>    repo has zero `@asset_check` and an asset check can't own `finish_run`.
> 3. Roadmap's uniqueness checks on `dim_track` nat key + `fact_streams` PK are
>    DB tautologies (both already PKs) — replaced with `fact_ingest_id_unique`
>    (no FK/unique at 009:155) and `dim_track_uri_unique`.
> 4. `latest_ingest_run_terminal` is **warn**, not blocking: by the time
>    `data_quality` runs, the current run has rebuilt the warehouse, so a stale
>    `failed` from a prior run must not fail today's pipeline. Blocking set = 12.
> 5. `pandera_schemas.py` narrowed to sample-contract validation (the roadmap's
>    "shared with `ingest/schemas.py`" doesn't hold — different column set).
> 6. `enrichment_coverage` is warn-only at threshold 0.0 — `audio_source='enriched'`
>    is 0% (audio-features enrichment doesn't exist in this repo).
> 7. `Insights.tsx` kept as one file (not 13 extracted components) — the merged
>    pages were self-contained, so it's a mechanical move.
> 8. `getListeningHeatmap` client fn dropped (zero callers); `/api/patterns/heatmap`
>    + its RPC stay live server-side.
> 9. API-baseline diff done by eye (`compare_api_baseline.py` has no path filter):
>    Phase 13 deletes endpoints and leaves survivor SQL untouched, so a scoped
>    check (deleted paths 404, no value diffs on survivors) is the useful assertion.

**Follow-ups for Phase 13.5:** `app/quality/` is a read-only consumer pattern the
notebooks can mirror. **For Phase 14:** the `user_*` feature-table checks
(affinity 0–1 range, etc.) are DQ extension points noted in `DATA_QUALITY.md`.
**For Phase 16 CI:** add `python -m app.quality.run` (exit-code gate) +
`pytest tests/test_quality.py tests/test_health_data.py` to the pipeline.

**Next phase to start: Phase 13.5.**
