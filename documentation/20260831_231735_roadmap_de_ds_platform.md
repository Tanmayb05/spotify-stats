# Roadmap — Multi-User Analytics → Portfolio-Grade DE + DS System

**Date:** 2026-08-31
**Status:** Planned (Phases 9–21)
**Prompted by:** a spec to evolve this repo from a "Spotify analytics dashboard" into a
*multi-user music intelligence platform that constructs behavioral profiles from
longitudinal listening histories and generates personalized, explainable
recommendations that adapt to preference changes.*

## Context

The repo already has real DE bones (4-stage ETL, Spotify metadata enrichment, Postgres,
materialized views, ~40 RPC functions) and, since Phase 8, **10 users × ~340k
`streaming_history` rows** in Supabase. That changes the opportunity from *"analyze my
Spotify history"* to a **DE + DS system** demonstrable end-to-end.

**Research framing (the spec's own):**
> How well can recommendations work when individual user histories are rich (131–70,700
> plays/user) but the user population is small (n=10)?

That premise — high longitudinal depth, low user breadth — is exactly what this dataset
is, and it justifies exploring content-based, temporal, and hybrid methods rather than
pretending to train a world-class collaborative recommender.

**Do NOT rebuild.** Evolve the existing repo. Keep the ETL, enrichment scripts, Postgres,
MVs, RPCs, the React/FastAPI app, the CLAUDE.md design system.

---

## Decisions locked (via AskUserQuestion)

| Decision | Choice | Why |
|---|---|---|
| Plan scope | Full 13-phase roadmap doc; execute phase-by-phase later | Same model as the original CLAUDE.md phase plan |
| DB direction | **Local Postgres + Docker Compose**, Supabase optional via `DB_BACKEND` switch | Reviewer runs `docker compose up` with no account; live demo stays on Supabase (`DB_BACKEND=supabase` default until Phase 20) |
| Orchestrator | **Dagster** | Asset model maps 1:1 to bronze/silver/gold + feature tables; one `dagster dev` process; free lineage graph for the write-up. Airflow = scheduler+webserver+metadata-DB theatre for a nightly 340k-row batch |
| Collaborative-filtering libs | **implicit (ALS)** for Model 2, **LightFM** for the hybrid warm-start | implicit ALS = cleanest confidence-weighted implicit-feedback baseline, honest about n=10; LightFM adds item/user features so the hybrid degrades gracefully. `surprise` is explicit-rating oriented — wrong tool |
| Data-quality framework | **Pandera** (in-pipeline dataframe schemas) + a thin **SQL check runner** (referential integrity / freshness / anomaly) | Great Expectations = heavy scaffolding for n=10; dbt-tests need adopting dbt now |
| Schema build tool | **Plain SQL migrations** (`apps/api/migrations/00X_*.sql`, existing `_effective_user_id` convention); dbt optional later (Phase 21) for lineage docs | A dbt project is a second toolchain for a 6-table schema |
| Data loaders | **Collapse to one** by end of Phase 14 — port salvageable compute out of `data_loader.py` into named modules, then delete it; `supabase_data_loader.py` → single `data_service.py` | Two 2373/807-line loaders synced by hand is the top maintenance liability |

---

## Explicitly INFEASIBLE — scope out / de-risk (state in README + write-up)

1. **Genre-transition analysis / genre-affinity features on current data.** Spotify API
   returns `genres: []` for most modern artists; ~54% artist-level coverage skewed to
   obscure artists; **zero track-level genre**.
   *De-risk:* Phase 11 adds a one-time **MusicBrainz + Last.fm artist-tag backfill** into
   `gold.dim_artist.genres_enriched`/`tags`. **Gate at Phase 11 verification:** if
   coverage after backfill is still `< ~80% of plays` (not artists), **cut
   `user_genre_affinity` + genre-transition EDA to a documented "future work" box**; lean
   on artist-affinity + audio-proxy features. Decision recorded in `DATA_MODEL.md`.
2. **"World-class collaborative recommender" — n=10.** CF cannot be state-of-the-art here.
   *Frame it as the research question:* Model 2 exists to **measure** how far CF gets at
   n=10 (Experiment E2), not to win. Report a negative/limited result if that's what the
   data shows. Hybrid uses `userSim` only as a light term (β small).
3. **Real Spotify audio features** (valence/energy/danceability/tempo) — `/audio-features`
   deprecated for new apps.
   *De-risk:* keep the existing `_calculate_mood_metrics` **behavioral proxies** but
   (a) rename everywhere to `*_proxy` / `mood_proxy_*` so no reviewer mistakes them for
   real audio features, (b) document the proxy definition in one place, (c) optionally
   enrich from Last.fm tags / MusicBrainz / AcousticBrainz as a nice-to-have; if that
   fails, labelled proxies stand.
4. **Statistically significant experiment results — n=10, one export per person.** Every
   experiment reports effect sizes + per-user breakdown + "directional, not significant"
   caveat. The **human-eval loop (Phase 19)** is the credibility anchor, not p-values.

---

## Scorecard being optimized (spec's own, /100)

problem formulation 10 · data ingestion/arch 10 (DE) · data modeling 10 (DE) ·
data quality 10 (DE) · scale/perf/repro 10 (DE) · behavioral EDA 10 (DS) ·
recommendation methodology 15 (DS) · experimentation/eval 15 (DS) ·
product impact 5 · communication 5.

---

## Phases

Continues existing numbering (last shipped = Phase 8). Each phase leaves the app working.

### PHASE 9 — Repo hygiene & public-safe history · **S**
**Goal:** make the repo safe to publish.
**Moves:** communication 5; scale/perf/repro 10 (partial).
- **P0 blocker:** purge from **all git history** (not just HEAD) `data/other users/*.zip` —
  9 friends' raw Spotify exports, **git-tracked, containing third-party `ip_addr`**
  (e.g. `REDACTED_IP`), introduced in commit `7d16c08`. Tool: `git filter-repo
  --path 'data/other users' --invert-paths` (or BFG). Rewrites history → force-push
  `main`, re-clone, close/rebase `origin/feat/multi-user-analytics-switch`.
- Evaluate also purging `data/*.json` (~55 MB) + `outputs/data/songs_info.json` (45 MB) →
  documented download step or Git LFS. `.git` is currently 53 MB.
- `data/README.md` — how to obtain a Spotify GDPR export, drop it in `data/raw/<user>/`.
- `data/fixtures/sample_streaming_history.json` — tiny synthetic fixture for CI.
- `.gitignore`: add `data/raw/`, `outputs/`; **remove the blanket `*.ipynb` ignore**
  (notebooks are deliverables now); keep env rules.
- Pinned deps: `apps/api/requirements.txt` with exact `==` (or `uv`/`pip-tools` +
  lockfile); split `apps/api/requirements-dev.txt` (pytest, pandera, dagster, jupyter,
  ruff). Note: current `apps/api/requirements.txt` is **missing `supabase`** — a hard
  runtime dep.
- `LICENSE` (MIT), `SECURITY.md` ("exports are personal data, never committed").
**Files:** `data/README.md`, `data/fixtures/sample_streaming_history.json`, `.gitignore`,
`apps/api/requirements.txt`, `apps/api/requirements-dev.txt`, `requirements.txt`,
`LICENSE`, `SECURITY.md`, `README.md` (add "Data & privacy").
**Verify:** `git log --all --name-only | grep -i 'other users'` → nothing; fresh clone +
`pip install -r apps/api/requirements.txt` succeeds; `du -sh .git` materially smaller;
`uvicorn app.main:app` still boots.

### PHASE 10 — Local-first infra: Docker Compose + migration runner + DB backend switch · **M**
**Goal:** `docker compose up` brings Postgres + API + web with no Supabase account.
**Moves:** scale/perf/repro 10; data ingestion/arch 10 (partial).
- `docker-compose.yml`: `db` (postgres:16, volume, healthcheck), `api` (build
  `apps/api`, waits on db), `web` (build `apps/web`), `dagster` added Phase 12. `.env`-driven.
- `apps/api/Dockerfile`, `apps/web/Dockerfile`, two `.dockerignore`.
- **Migration runner** `apps/api/db/migrate.py` — applies `apps/api/migrations/*.sql` in
  filename order, records applied files in `schema_migrations(version pk, applied_at)`,
  idempotent, `--dry-run`. Engine helper `apps/api/db/__init__.py` (SQLAlchemy).
- **DB backend switch** `apps/api/app/config.py` — `DB_BACKEND=local|supabase`,
  `DATABASE_URL` for local. `apps/api/app/db/session.py` (SQLAlchemy engine/Session).
  Supabase path keeps PostgREST; local path uses direct SQL.
- `apps/api/scripts/seed_local_db.py` — loads `data/fixtures/` (CI) or a real export dir,
  reusing normalization extracted into `apps/api/app/ingest/normalize.py` (Phase 11).
- `documentation/LOCAL_DEV.md`.
**Files:** `docker-compose.yml`, `apps/api/Dockerfile`, `apps/web/Dockerfile`,
`.dockerignore` ×2, `apps/api/db/migrate.py`, `apps/api/db/__init__.py`,
`apps/api/app/config.py`, `apps/api/app/db/session.py`,
`apps/api/scripts/seed_local_db.py`, `apps/api/app/services/supabase_data_loader.py`
(route through `db.session` when `DB_BACKEND=local`), `documentation/LOCAL_DEV.md`.
**App still works:** `DB_BACKEND=supabase` (default) unchanged — live deploy untouched.
**Verify:** `docker compose up` → web :5173, API `/health` 200,
`/api/compare/leaderboard` returns fixture users; `migrate.py` run twice → second a no-op.

### PHASE 11 — Star schema + enrichment loaded INTO Postgres + bronze/silver/gold · **L**
**Goal:** turn the one wide `streaming_history` table into a Medallion-layered star schema
with real dim tables populated from the on-disk enrichment.
**Moves:** data modeling 10; data ingestion/arch 10.
- **Medallion schemas** — `008_medallion_schemas.sql`: `CREATE SCHEMA bronze; silver; gold;`
  - `bronze.raw_streams` = append-only landing copy + `_ingest_id`, `_source_file`,
    `_ingested_at`, `_raw` jsonb. Existing `streaming_history` copied here.
  - `silver.streams` = validated + normalized + deduped, typed, FK-ready keys.
  - `gold` = star schema + feature tables (Phase 14).
- **Star schema** — `009_star_schema.sql` (in `gold`):
  `dim_user`, `dim_time` (date/hour grain), `dim_artist` (nat key = normalized name;
  cols name, spotify_artist_id, popularity, followers, genres jsonb, tags jsonb,
  genres_enriched jsonb), `dim_track` (nat key = `track_uri` or hash of
  `(track_name, artist)`; cols track_name, artist_key, album, duration_ms, explicit,
  release_year, popularity, `mood_proxy_valence/energy/danceability`, `audio_source` enum),
  `dim_album` (optional), `fact_streams` (grain = one play; FKs to the 4 dims; measures
  ms_played, skipped, shuffle, offline, reason_start/end), `recommendation_events`
  (empty; populated Phase 17). Lookups keep `_effective_user_id(p_user_id)`.
- **Enrichment → Postgres** `apps/api/scripts/load_enrichment_to_db.py` —
  `outputs/data/artists_info.json` (4,216 artists), salvageable
  `outputs/data/songs_info.json` (~808 via existing `_salvage_json_array`),
  `outputs/lyrics/lyrics.json` (5,858) → upsert into `gold.dim_artist`, `gold.dim_track`,
  `gold.track_lyrics(track_key, source, has_lyrics, lang, word_count)` (metadata only —
  no lyrics text committed).
- **Artist-tag backfill** (genre de-risk): MusicBrainz + Last.fm tags for `dim_artist`
  → `genres_enriched`/`tags`. Measure **coverage-of-plays** at the verify gate.
- **Build fact/dim from silver** `apps/api/scripts/build_star_schema.py` (or Dagster
  assets Phase 12): populate dims (distinct artists/tracks/time), then `fact_streams` by
  joining silver rows to dim natural keys; log track/artist match-rate.
- Rewrite the 3 MVs + hottest RPCs from `006` to read `gold.fact_streams` + dims —
  `010_mvs_on_star.sql`. **Keep names + signatures identical** so routes don't change.
- `documentation/DATA_MODEL.md` (ER + medallion flow + genre-coverage decision); update
  `documentation/database_schema_diagram.md` to reality.
**Files:** `apps/api/migrations/008_medallion_schemas.sql`, `009_star_schema.sql`,
`010_mvs_on_star.sql`, `apps/api/scripts/load_enrichment_to_db.py`,
`apps/api/scripts/build_star_schema.py`, `apps/api/app/ingest/normalize.py` (name
normalization + natural-key hashing, reused by loaders + ingest),
`apps/api/app/services/supabase_data_loader.py` (point heavy queries at `gold.*`),
`documentation/DATA_MODEL.md`, `documentation/database_schema_diagram.md`.
**App still works:** MVs + RPCs keep names/signatures. Run star build, refresh MVs, smoke
every page.
**Verify:** `SELECT count(*) FROM gold.fact_streams` ≈ 340k;
`SELECT count(*) FROM gold.dim_track WHERE audio_source='enriched'` > 800; every frontend
page renders identical numbers vs pre-migration (spot-check Overview totals + Comparison
leaderboard); **genre-coverage-of-plays recorded → keep or cut `user_genre_affinity`**.

### PHASE 12 — Ingestion pipeline: raw→validate→normalize→dedup→enrich→quarantine, incremental+idempotent, Dagster · **XL**
**Goal:** replace the two manual load scripts with one incremental, idempotent, observable
pipeline with a quarantine lane and ingestion metrics.
**Moves:** data ingestion/arch 10; scale/perf/repro 10; data quality 10 (partial).
- **`apps/api/app/ingest/`:**
  - `discover.py` — scan `data/raw/<user>/*.json`, per-file content hash.
  - `landing.py` — append new files' rows to `bronze.raw_streams` + `_source_file`,
    `_ingested_at`, `_raw`. **Watermark** `ingest_state(user_id, source_file, file_hash,
    max_ts, rows_landed, ingested_at)` — skip files whose `(user_id, file_hash)` already
    present ⇒ idempotent; incremental = land only rows with `ts > watermark_max_ts` for
    that user on a superset re-export.
  - `validate.py` — Pandera schema (`schemas.py`): `ts` present & parseable, `ms_played`
    in `[0, 24h]`, track name non-null for music rows, enum on `reason_start/end`,
    `platform` string. Failing rows → `bronze.quarantine(_ingest_id, rule, detail, _raw,
    quarantined_at)`.
  - `normalize.py` (from Phase 11) — trim/casefold artist & track keys, UTC timestamps,
    duration → ms, booleans.
  - `dedup.py` — Spotify exports legitimately contain byte-identical rows. Keep all in
    `bronze`; collapse **true byte-identical dupes** in `silver` via a stable
    `row_fingerprint` hash + `ROW_NUMBER`; record `dups_dropped`. No upsert-conflict
    problem — silver is a rebuild-from-bronze.
  - `enrich.py` — left-join silver → `gold.dim_artist`/`dim_track`; unmatched rows still
    flow (fact row, null enrichment), counted as `unmatched`. Optional rate-limited
    on-demand fetch for new unseen artists/tracks.
  - `metrics.py` — per-run `ingest_run(run_id, started_at, finished_at, users, files_new,
    rows_raw, rows_valid, rows_quarantined, dups_dropped, rows_silver, track_match_rate,
    artist_match_rate, status)` + per-user `ingest_run_user`.
- **Dagster project** `apps/api/dagster_project/`:
  `assets.py` (software-defined assets `raw_streams` [partitioned by user/date],
  `quarantine`, `silver_streams`, `dim_artist`, `dim_track`, `dim_time`, `fact_streams`;
  feature assets added Phase 14 — deps wired so the lineage graph tells the DE story),
  `resources.py` (Postgres from `DATABASE_URL`), `jobs.py` (`nightly_ingest_job`),
  `schedules.py` (cron 03:00), `definitions.py`.
- Add `dagster` service to `docker-compose.yml` (`dagster dev`, port 3000).
- Keep `load_json_to_supabase.py` / `load_multi_user_data.py` as thin deprecated wrappers
  (or move to `apps/api/scripts/legacy/`).
- `documentation/INGESTION.md`.
**Files:** `apps/api/app/ingest/{__init__,discover,landing,validate,normalize,dedup,enrich,metrics,schemas}.py`,
`apps/api/migrations/011_ingest_state_and_runs.sql` (`ingest_state`, `ingest_run`,
`ingest_run_user`, `bronze.quarantine`),
`apps/api/dagster_project/{__init__,definitions,assets,resources,jobs,schedules}.py`,
`docker-compose.yml`, `apps/api/requirements.txt` (dagster, dagster-webserver,
dagster-postgres, pandera), the two legacy loaders, `documentation/INGESTION.md`.
**App still works:** pipeline writes the same `gold.fact_streams`/dims the app reads. Run
the full job once on the real 10 exports, refresh MVs, smoke pages.
**Verify:** `dagster job execute -j nightly_ingest_job` green; immediate re-run ⇒
`files_new=0`, `rows_landed=0` (idempotent); inject a malformed fixture row ⇒ lands in
`bronze.quarantine` with a rule name; latest `ingest_run` shows sane
raw/valid/dups/invalid/match-rate; fact count unchanged vs Phase 11.

### PHASE 13 — Data-quality test suite + `/api/health/data` + Data Health page · **M**
**Goal:** automated DQ tests run in the pipeline and surfaced in the UI.
**Moves:** data quality 10; product impact 5 (partial); communication 5 (partial).
- **`apps/api/app/quality/`:**
  - `checks.py` — registry; each returns `CheckResult(name, category, severity, passed,
    observed, expected, rows_failed, detail)`. Categories: **uniqueness** (no dup
    `_ingest_id`; `fact_streams` PK; `dim_track` nat key), **referential_integrity**
    (every `fact_streams.track_key` in `dim_track`; `user_id` in `dim_user`), **range**
    (`ms_played` 0–24h; `release_year` 1900–next yr; affinity scores 0–1), **freshness**
    (`max(ingested_at)` within N days; per-user `max(fact ts)` not absurdly stale),
    **completeness** (non-null rate track/artist; % plays with enrichment ≥ threshold),
    **anomaly** (per-user daily play count vs 30-day rolling median ± k·MAD;
    artist-cardinality spikes; z-score on run-over-run row deltas).
  - `pandera_schemas.py` — silver/gold dataframe schemas (shared with `ingest/schemas.py`).
  - `run.py` — run all; write `dq_run(run_id, run_at, passed, failed, warned)` +
    `dq_result(run_id, name, category, severity, passed, observed, expected, detail)`.
- Wire as a Dagster **asset check** / final asset `data_quality` downstream of
  `fact_streams` (+ feature tables later); job fails on `severity=blocking`, warns otherwise.
- **API:** extend `apps/api/app/routes/health.py` — `GET /api/health/data` returns latest
  `dq_run` + grouped `dq_result` + latest `ingest_run` metrics + per-user freshness.
  Keep the old `/health` liveness blob.
- **Frontend** `apps/web/src/pages/DataHealth.tsx` — **route it** (fix routing; also fix
  or delete orphan `Moods.tsx` while in the router). Cards: pipeline last-run status;
  raw/valid/dups/invalid/match-rate bars; DQ checks table (green/amber/red by category);
  per-user freshness list; row-count trend sparkline. Existing MUI X Charts + palette
  (`#1c0b19/#140d4f/#4ea699/#2dd881/#6fedb7`, Inter).
- `apps/web/src/api/client.ts` — `getDataHealth()`.
- `documentation/DATA_QUALITY.md`.
**Files:** `apps/api/app/quality/{__init__,checks,pandera_schemas,run}.py`,
`apps/api/migrations/012_dq_tables.sql`, `apps/api/app/routes/health.py`,
`apps/api/dagster_project/assets.py` (add `data_quality`),
`apps/web/src/pages/DataHealth.tsx`, `apps/web/src/App.tsx` / router,
`apps/web/src/api/client.ts`, `apps/web/src/layout/*` nav, `documentation/DATA_QUALITY.md`.
**App still works:** additive endpoint + new page.
**Verify:** `python -m app.quality.run` prints a pass/fail table; `/api/health/data`
returns ≥6 categories; Data Health page renders in `docker compose up`; delete a
`dim_track` row ⇒ referential-integrity check red and the page shows it.

### PHASE 14 — Feature store: `user_*` + `track_popularity` tables + nightly compute + dual-loader collapse · **L**
**Goal:** move heavy per-user compute off the request path into materialized `gold`
feature tables refreshed nightly; collapse to one data loader.
**Moves:** data modeling 10; scale/perf/repro 10; behavioral EDA 10 (partial).
- **Feature tables** — `013_feature_tables.sql` (schema `gold`):
  - `user_daily_features(user_id, day, streams, minutes, distinct_tracks,
    distinct_artists, skip_rate, night_share, weekend_flag, new_artist_count,
    repeat_ratio)`.
  - `user_artist_affinity(user_id, artist_key, plays, minutes, recency_weighted_score,
    first_play, last_play, loyalty_return_prob, loyalty_half_life)` — port from
    `data_loader.py` artist-loyalty + `_artist_vector`.
  - `user_genre_affinity(user_id, genre, score, coverage_flag)` — **gated on the Phase 11
    coverage gate**; if infeasible, create empty + documented, or skip (decision in
    `DATA_MODEL.md`).
  - `user_temporal_preferences(user_id, hour_bucket, dow_bucket, context_label,
    mood_proxy_valence, mood_proxy_energy, mood_proxy_danceability, play_share)` — port
    `_calculate_mood_metrics` + hour/weekday buckets; `context_label` ∈ {morning,
    commute, work, evening, late_night, weekend_day, …}.
  - `user_behavior_vector(user_id, vec float8[], dims_json)` — per-user behavioral vector
    (Phase 16 consumes).
  - `track_popularity(track_key, global_plays, distinct_users, plays_last_90d,
    popularity_rank, popularity_percentile)` — Baseline-0 source.
- **Compute jobs** `apps/api/app/features/{__init__,daily,artist_affinity,genre_affinity,
  temporal,behavior_vector,track_popularity}.py` — pandas-first (340k rows fits in
  memory; **document that volume does not justify PySpark**), each reads
  `gold.fact_streams` + dims, full-refresh-per-run (simple + idempotent). `run_all(users=None)`.
- **Dagster assets** for each feature table, downstream of `fact_streams`, upstream of
  `data_quality`.
- **API switch + loader collapse:** `apps/api/app/services/feature_repo.py` (typed reads
  from `gold.*`). Port remaining unique `data_loader.py` compute into
  `apps/api/app/analytics/{mood,sessions,discovery,simulator}.py` as pure functions
  (`_cluster_sessions`, `_build_artist_transitions` land here) — both the nightly job and
  any residual runtime path call them. Then **delete `data_loader.py`**; rename
  `supabase_data_loader.py` → `data_service.py`; update route imports.
- `documentation/FEATURE_STORE.md`.
**Files:** `apps/api/migrations/013_feature_tables.sql`, `apps/api/app/features/*.py` (7),
`apps/api/app/analytics/{mood,sessions,discovery,simulator}.py`,
`apps/api/app/services/feature_repo.py`,
`apps/api/app/services/supabase_data_loader.py` → `data_service.py`,
`apps/api/app/services/data_loader.py` (**delete** at end of phase),
`apps/api/dagster_project/assets.py`, `apps/api/app/routes/*.py` (imports),
`documentation/FEATURE_STORE.md`.
**App still works:** switch reads endpoint-by-endpoint; delete `data_loader.py` only after
every route is off it and smoke-tested. Numbers match within rounding.
**Verify:** `python -m app.features` populates all 6 tables;
`SELECT count(*) FROM gold.user_daily_features` ≈ 10 users × days-active; p95 latency of
`/api/patterns/*` and `/api/reco/*` drops sharply (`compare_performance.py` before/after);
`grep -r data_loader apps/api/app/routes` empty.

### PHASE 15 — Behavioral EDA notebooks (the DS narrative) · **L**
**Goal:** a reproducible notebook set answering the behavioral questions, reading feature
tables.
**Moves:** behavioral EDA 10; problem formulation 10 (partial); communication 5 (partial).
`apps/api/notebooks/` (`*.ipynb` now un-ignored):
- `00_dataset_overview.ipynb` — n=10, per-user depth (131–70,700 plays), date spans, the
  "rich histories, small population" framing + research question stated.
- `01_temporal_taste_shift.ipynb` — taste vectors per year/quarter, cosine drift, per-user
  trajectories.
- `02_weekday_weekend.ipynb` — from `user_daily_features` + `user_temporal_preferences`.
- `03_exploration_vs_repetition.ipynb` — new-artist rate, repeat ratio, catalog-growth
  curves, per-user "explorer vs loyalist" score.
- `04_artist_loyalty_and_obsessions.ipynb` — return-probability, half-life, obsession
  weeks (port from RPCs / `user_artist_affinity`).
- `05_session_behavior.ipynb` — sessionizer stats, KMeans session archetypes (port
  `_cluster_sessions`), archetype prevalence per user.
- `06_genre_transitions.ipynb` — **conditional**: run only if the Phase 11 gate cleared;
  else a short "why infeasible on Spotify export data" writeup with the coverage numbers.
- `07_context_signatures.ipynb` — morning=acoustic-proxy, gym/high-energy windows,
  late-night patterns from `user_temporal_preferences`.
- `apps/api/notebooks/README.md` — run order + `jupyter nbconvert --execute` for CI.
- Add `jupyter`, `papermill`, `matplotlib`, `seaborn` to `requirements-dev.txt`.
**Files:** `apps/api/notebooks/*.ipynb` (8), `apps/api/notebooks/README.md`,
`apps/api/requirements-dev.txt`.
**Verify:** `jupyter nbconvert --to notebook --execute apps/api/notebooks/0*.ipynb` clean
against a seeded DB; each notebook ends with a stated finding.

### PHASE 16 — Explained user similarity (Jaccard → behavioral cosine + explanations) · **M**
**Goal:** replace artist-set Jaccard with cosine over per-user behavioral vectors, with
human-readable "why similar / why different" explanations.
**Moves:** recommendation methodology 15 (partial); behavioral EDA 10 (partial); product
impact 5 (partial).
- `apps/api/app/reco/user_similarity.py`:
  - user vectors from `gold.user_behavior_vector` (dim blocks: top-artist affinity TF-IDF;
    genre/tag block if available; temporal block (hour/dow shares); discovery-rate;
    skip-rate; session-archetype mix; mood-proxy centroid).
  - `similarity(u, v)` = cosine; also **component contributions** — which dim-blocks
    drive the score up (shared indie-pop affinity, both late-night) and which pull it
    down (different discovery rate). Template: `"{U} and {V} are {pct}% similar, driven by
    {top_pos_1} + {top_pos_2}; they differ most in {top_neg_1}."`
  - keep `_jaccard` from `compare.py` as a named baseline
    (`user_similarity.jaccard_baseline`) for experiment reporting — do not delete.
  - `similarity_matrix()` → N×N with explanations cached.
- **API:** extend `apps/api/app/routes/compare.py` — `/api/compare/overlap` gains an
  `explanations` block; add `/api/compare/similarity-explained`. Keep old fields for the
  existing Comparison page.
- **Frontend:** `apps/web/src/pages/Comparison.tsx` — add an expandable "Why similar"
  panel per pair under the Jaccard heatmap; keep existing heatmap/leaderboard/overlap.
- Persist `gold.user_similarity(user_a, user_b, score, method, explanation_json,
  computed_at)` via a Dagster asset (downstream of `user_behavior_vector`).
**Files:** `apps/api/app/reco/__init__.py`, `apps/api/app/reco/user_similarity.py`,
`apps/api/migrations/014_user_similarity.sql`, `apps/api/app/routes/compare.py`,
`apps/api/dagster_project/assets.py`, `apps/web/src/pages/Comparison.tsx`,
`apps/web/src/api/client.ts`.
**App still works:** Comparison page keeps rendering; new panel additive.
**Verify:** `/api/compare/similarity-explained?users=<a>,<b>` returns a score + a sentence
naming ≥2 positive and ≥1 negative driver; matrix endpoint shape unchanged.

### PHASE 17 — Recommendation models: Baseline 0 + Model 1 + Model 2 + Model 3 (hybrid α..ε) · **XL**
**Goal:** four ranked-recommendation models behind one interface, each with per-item
explanations.
**Moves:** recommendation methodology 15.
`apps/api/app/reco/` package:
- `base.py` — `Recommender` protocol: `recommend(user_id, k, context=None, horizon=None)
  -> list[RecItem]`, `RecItem = {track_key, score, components: dict, explanation: str}`;
  `candidates(user_id)` helper (all tracks minus already-heard, or minus top-25 —
  configurable).
- `popularity.py` — **Baseline 0**: rank by `gold.track_popularity` (global plays /
  recency-decayed), optional per-user artist filter. `"Popular across listeners
  (rank {r})."`
- `content.py` — **Model 1**: port `data_loader.get_recommendations` — cosine on the
  9-dim vector `[valence_proxy, energy_proxy, danceability_proxy, track_popularity,
  artist_popularity, artist_followers_log, duration_min, explicit, release_year_recency]`,
  recency-weighted (exp half-life 180d) × log(play_count) preference vector, MMR (λ=0.7).
  Rename mood dims to `*_proxy`. Reuse existing top-3 standardized-contribution → phrase
  logic. Optional mood steer kept.
- `collaborative.py` — **Model 2**: `implicit.als.AlternatingLeastSquares` on a
  `user × track` confidence matrix (`1 + α·log1p(plays)`). **Document the n=10 ceiling**
  in the module docstring and every result table. `"Listeners with taste like yours
  ({neighbor names}) play this."`
- `hybrid.py` — **Model 3**:
  `score = α·content + β·userSim + γ·recency + δ·temporal + ε·novelty` where
  `content` = Model 1 score; `userSim` = Σ over similar users (Phase 16) of their affinity
  for the track weighted by similarity; `recency` = decay on the track's artist's
  last-played recency for this user (global freshness for cold items); `temporal` = match
  between the track's mood-proxy vector and the user's `user_temporal_preferences` row for
  the request `context`; `novelty` = `1 - track_popularity_percentile` (or unseen-artist
  bonus). Weights in `apps/api/app/reco/config.py` (defaults α=.45 β=.15 γ=.15 δ=.15
  ε=.10), tunable; the ablation harness (Phase 18) zeroes each in turn. Explanation
  composes the top-2 contributing components into a sentence.
- `context.py` — map request timestamp / `context` string ({morning, gym, commute,
  evening, late_night}) to the temporal-preference target vector; also the **long-term vs
  short-term taste weighting** knob: build the user preference vector at 4 horizons
  (lifetime / 12mo / 90d / recency-weighted-exp), `horizon` param, compared in
  Experiment E4.
- `registry.py` — `get_recommender(name)`; import-guard `implicit`/`lightfm` as optional
  extras.
- **Persist:** every served rec → `gold.recommendation_events(event_id, user_id,
  track_key, model, rank, score, components_json, explanation, context, served_at,
  split_tag)`.
- **API:** rewrite `apps/api/app/routes/reco.py` —
  `GET /api/reco?user_id&model=popularity|content|collaborative|hybrid&k&context&horizon`;
  response includes `explanation` + `components` per item. Default `model=content` so the
  existing Recommendations page keeps working.
- **Frontend:** `apps/web/src/pages/Recommendations.tsx` — model selector, context
  selector, explanation string + small component-contribution bar per card. Keep ⚗️.
- Deps: `implicit`, `lightfm` to `apps/api/requirements.txt` (LightFM build fiddly — pin,
  gate behind an extra so core install stays clean).
- `documentation/RECOMMENDERS.md`.
**Files:** `apps/api/app/reco/{base,popularity,content,collaborative,hybrid,context,config,registry}.py`,
`apps/api/migrations/015_recommendation_events.sql` (or extend `009`),
`apps/api/app/routes/reco.py` (rewrite), `apps/api/app/services/data_service.py`
(expose feature reads to reco), `apps/web/src/pages/Recommendations.tsx`,
`apps/web/src/api/client.ts`, `apps/api/requirements.txt`,
`documentation/RECOMMENDERS.md`.
**App still works:** default model = content = current behavior.
**Verify:** `GET /api/reco?user_id=<primary>&model=hybrid&k=10&context=late_night` returns
10 items each with non-empty `explanation` and a `components` dict keyed
{content,userSim,recency,temporal,novelty}; `model=collaborative` returns 10 items and
logs the n=10 caveat; `recommendation_events` rows written.

### PHASE 18 — Evaluation harness: time-based split + 9 metrics + 5 experiments + ablation table · **XL**
**Goal:** a reproducible offline-eval module + notebook producing
Precision/Recall/NDCG/MAP/HitRate @K, Coverage, Diversity, Novelty, Serendipity, plus the
5 named experiments and the ablation table.
**Moves:** experimentation/eval 15; recommendation methodology 15 (partial); communication
5 (partial).
`apps/api/app/eval/`:
- `split.py` — **per-user time-based split**: `T_u` per user (last 20% of timeline, or a
  fixed global date); `train = plays < T_u`, `test = plays > T_u`. Also a k-fold-by-time
  variant. `eval_split(user_id, split_id, cutoff_ts, train_rows, test_rows)`.
- `metrics.py` — `precision_at_k, recall_at_k, ndcg_at_k, map_at_k, hit_rate_at_k`
  (relevance = track in the user's test window, optionally weighted by test play count);
  `coverage` (fraction of catalog ever recommended across users); `diversity` (1 − mean
  pairwise cosine of recommended tracks' proxy vectors); `novelty` (mean
  `−log2 popularity_percentile`); `serendipity` (relevant AND unexpected vs a popularity
  baseline).
- `harness.py` — `evaluate(recommender, split, k_list=[5,10,20]) -> DataFrame`; per-user +
  aggregate; bootstrap CIs over the 10 users; caches candidate sets.
- `experiments/` — one script each, all writing `outputs/eval/<exp>.{csv,json}` + a
  markdown fragment:
  - `e1_content_vs_popularity.py` — Model 1 vs Baseline 0.
  - `e2_collab_with_n10.py` — Model 2 vs Baseline 0 vs Model 1; explicit "does CF help at
    n=10?" verdict + per-user table.
  - `e3_hybrid_vs_components.py` — Model 3 vs best of {1,2} vs Baseline 0.
  - `e4_recency_weighting.py` — hybrid at horizons {lifetime, 12mo, 90d,
    recency-weighted}; long-term vs short-term preference-vector comparison.
  - `e5_contextual.py` — hybrid with vs without the δ·temporal term, evaluated on
    context-tagged test slices (morning/evening/late-night).
- `ablation.py` — full hybrid NDCG@10 vs (−content), (−userSim), (−recency), (−temporal),
  (−novelty); emits `outputs/eval/ablation_table.md`.
- `apps/api/notebooks/10_evaluation.ipynb` — runs the harness, renders all metric tables +
  the 5 experiments + the ablation table + a "headline findings" cell.
- `apps/api/notebooks/README.md` (edit). Optional `Makefile` / Dagster `eval_job`.
**Files:** `apps/api/app/eval/{__init__,split,metrics,harness,ablation}.py`,
`apps/api/app/eval/experiments/e1..e5_*.py` (5),
`apps/api/migrations/016_eval_tables.sql` (`eval_split`, optional `eval_result`),
`apps/api/notebooks/10_evaluation.ipynb`, `outputs/eval/.gitkeep`,
`apps/api/notebooks/README.md`, `Makefile` (optional).
**App still works:** pure offline analysis.
**Verify:** `python -m app.eval.experiments.e1_content_vs_popularity` writes a CSV with
NDCG@10 for both models across all 10 users; `python -m app.eval.ablation` writes
`ablation_table.md` with 6 rows; `10_evaluation.ipynb` executes end-to-end via nbconvert;
every metric function has a unit test (Phase 20).

### PHASE 19 — Human-evaluation loop · **L**
**Goal:** each of the 10 real people rates 20 blind recommendations (1–5, "knew it?",
"would save?"); compare human ratings to offline metrics.
**Moves:** experimentation/eval 15 (partial); product impact 5; communication 5 (partial).
- **Schema** — `017_human_eval.sql`: `gold.eval_session(session_id, user_id, model,
  created_at, status)`, `gold.eval_item(item_id, session_id, track_key, rank, model,
  blind_token)`, `gold.recommendation_ratings(item_id, user_id, rating_1_5, knew_it bool,
  would_save bool, rated_at, free_text)`.
- **Blind sets** `apps/api/app/eval/human_set.py` — per user draw 20 items mixing models
  (5 each popularity/content/collab/hybrid), shuffled, model labels stripped,
  `blind_token`s minted; write `eval_session` + `eval_item`.
- **API** `apps/api/app/routes/eval.py`: `POST /api/eval/session`,
  `GET /api/eval/session/{id}` (20 blind items — track/artist/art only, **no `model`
  field**), `POST /api/eval/rating`.
- **Frontend** `apps/web/src/pages/HumanEval.tsx` (routed) — one-card-at-a-time rater:
  1–5 stars, "already knew this track?" toggle, "would you save it?" toggle, optional
  note, progress bar. Shareable link `/#/eval/<session_id>`.
- **Analysis** `apps/api/app/eval/human_vs_offline.py` +
  `apps/api/notebooks/11_human_eval.ipynb` — per-model mean rating, %knew-it
  (inverse-novelty check), %would-save (precision proxy), correlation of human rating vs
  offline NDCG/precision/serendipity per user; agreement table; caveats (n=10 raters,
  ~200 judgements).
**Files:** `apps/api/migrations/017_human_eval.sql`, `apps/api/app/eval/human_set.py`,
`apps/api/app/eval/human_vs_offline.py`, `apps/api/app/routes/eval.py`,
`apps/api/app/main.py` (register router), `apps/web/src/pages/HumanEval.tsx`,
router/nav files, `apps/web/src/api/client.ts`, `apps/api/notebooks/11_human_eval.ipynb`.
**App still works:** new routes + page.
**Verify:** create a session, fetch it (20 items, no `model` field in payload), submit 20
ratings; `11_human_eval.ipynb` produces a per-model rating table + a human-vs-offline
correlation figure; `blind_token` prevents re-fetch of model identity.

### PHASE 20 — Production loop wiring + monitoring + tests + CI · **L**
**Goal:** close the new-history → ingest → validate → features → model → recs → API →
dashboard → feedback → stored → retrain loop; add tests, CI, basic monitoring.
**Moves:** scale/perf/repro 10; product impact 5; communication 5; experimentation/eval 15
(partial — retrain trigger).
- **Loop wiring:**
  - `apps/api/app/routes/ingest.py` — `POST /api/ingest/user` (multipart export
    zip/json) → drops into `data/raw/<user>/`, kicks the Dagster `nightly_ingest_job`
    (or a `run_pipeline` fn) → returns an `ingest_run` id. Auth-gated.
  - Feedback: `POST /api/reco/feedback` (thumbs / save) → `gold.recommendation_events.feedback`.
  - **Retrain trigger:** Dagster sensor/schedule `retrain_on_new_data` — when an
    `ingest_run` adds rows for a user, mark feature tables + models stale, re-run
    `features` + (cheap) `content`/`popularity`, log `model_run(model, trained_at,
    n_users, n_interactions, notes)`.
  - Dagster asset graph now: `raw → silver → dims/fact → features → user_similarity →
    model_artifacts → data_quality`; `eval_job` separate.
- **Monitoring (basic, no theatre):** `/api/health/data` extended with pipeline SLA (last
  successful run age), DQ pass-rate trend, model freshness. Structured logging (`structlog`
  or stdlib JSON) + request-timing middleware in `apps/api/app/main.py`; optional
  `/metrics` Prometheus-text endpoint (`prometheus-client`). Data Health page gains a
  "Pipeline & Model freshness" section.
- **Auth (minimal — closes "anyone can read any user"):** API key / simple signed token
  per user for write endpoints (`/api/ingest`, `/api/eval/rating`, `/api/reco/feedback`);
  read endpoints stay open for the demo but note it. `X-API-Key` dependency in
  `apps/api/app/deps.py`.
- **Tests** `apps/api/tests/`: `test_ingest_normalize.py`, `test_ingest_dedup.py`,
  `test_pandera_schemas.py`, `test_quality_checks.py`, `test_eval_metrics.py`
  (NDCG/MAP/precision vs hand-computed fixtures), `test_reco_smoke.py` (each model returns
  k items with explanations on a fixture DB), `test_api_health.py`.
  `apps/api/conftest.py` — throwaway Postgres (testcontainers) or the compose `db` +
  `data/fixtures/`.
- **Frontend tests:** `vitest` + a few component tests (DataHealth renders, Recommendations
  model switch); wire `npm run test`.
- **Fix the 16 standing TS errors**; make `npm run build` = `tsc -b && vite build` (fold
  `build:check` in); fix or delete orphan `Moods.tsx`.
- **CI** `.github/workflows/ci.yml`: `lint` (ruff + eslint), `typecheck` (`tsc -b`),
  `pytest` (Postgres service container + migrations + fixtures), `notebooks`
  (`nbconvert --execute` the EDA + eval notebooks on the fixture DB), `docker-build`
  (`docker compose build`).
- Deps: `ruff`, `pytest`, `testcontainers` (or service container), `structlog`, `vitest`
  + testing-library.
**Files:** `apps/api/app/routes/ingest.py`, `apps/api/app/deps.py`,
`apps/api/app/routes/reco.py` (`/feedback`), `apps/api/app/routes/health.py`,
`apps/api/app/main.py` (logging, timing, router regs),
`apps/api/dagster_project/{sensors,jobs,schedules}.py`,
`apps/api/migrations/018_model_runs.sql`, `apps/api/tests/*.py` (~7),
`apps/api/conftest.py`, `apps/web/vitest.config.ts`, `apps/web/src/**/*.test.tsx`,
`apps/web/package.json` (`test`, fold `build:check`), `apps/web/src/pages/Moods.tsx`
(fix or delete), `.github/workflows/ci.yml`, `apps/api/requirements-dev.txt`.
**App still works:** additive except the `build` script change + the TS-error fixes.
**Verify:** push a branch → CI green on all jobs; `POST /api/ingest/user` with a fixture
export → `ingest_run` created, feature tables refresh, `/api/reco` reflects the new data;
`pytest apps/api` all green; `docker compose build` succeeds in CI.

### PHASE 21 — Communication: README / PROJECT_OVERVIEW rewrite + architecture diagram + write-up · **M**
**Goal:** one clear pitch, an architecture diagram, and the research-question write-up
tying DE + DS + human-eval together.
**Moves:** communication 5; problem formulation 10; product impact 5.
- **Rewrite `README.md`** — pitch: *"A multi-user music intelligence platform that builds
  behavioral profiles from longitudinal listening histories and generates personalized,
  explainable recommendations that adapt to preference changes."* Sections: research
  question (rich histories, n=10); architecture (medallion + star + feature store +
  Dagster + FastAPI + React); how to run (`docker compose up`); the 4 models + hybrid
  formula; evaluation (9 metrics + 5 experiments + ablation + human loop); **honest
  limitations** (genre data, n=10 CF, deprecated audio features); results headline.
- **Rewrite `PROJECT_OVERVIEW.md`** — architecture-of-record; retire the stale single-user
  framing.
- **Architecture diagram** — `documentation/architecture.md` with a Mermaid data-flow
  diagram (raw exports → bronze → silver → star → features → models → API → dashboard →
  feedback → retrain) + the Dagster asset-lineage screenshot + the ER diagram.
  `documentation/RESEARCH_WRITEUP.md`: question, method (time-split), results per
  experiment, ablation, human-vs-offline agreement, what worked / what didn't, future work.
- **`CLAUDE.md`** — update the build bible to phases 9–21 and the new architecture; keep
  palette/font/chart specs.
- Update `documentation/` index; mark `database_schema_diagram.md` + stale phase docs
  superseded. `documentation/DEMO_SCRIPT.md` — a 60-second portfolio walkthrough.
- (Optional) adopt a small dbt project here for gold/feature lineage-as-docs if time allows.
**Files:** `README.md` (rewrite), `PROJECT_OVERVIEW.md` (rewrite), `CLAUDE.md`,
`documentation/architecture.md`, `documentation/RESEARCH_WRITEUP.md`,
`documentation/DEMO_SCRIPT.md`, `documentation/database_schema_diagram.md` ("superseded").
**App still works:** docs only.
**Verify:** a fresh reader can `git clone` → `docker compose up` → reach the dashboard +
the Data Health page following only the README; every README claim maps to a
file/endpoint that exists; Mermaid renders on GitHub.

---

## Sequencing rationale (portfolio signal per unit effort)

1. **P9 first (blocker):** can't publish with third-party PII in git history. Cheap,
   unblocks everything.
2. **P10–P13 (DE backbone):** local-runnable infra → star schema → real ingestion
   pipeline → data quality + Data Health page. ~40 points (ingestion 10, modeling 10,
   quality 10, repro 10); every later phase depends on it. Ship the Data Health page
   early — most visible DE artifact.
3. **P14 (feature store):** unlocks DS *and* fixes on-request-compute perf *and* enables
   the dual-loader collapse. Highest leverage single phase.
4. **P15–P18 (DS):** EDA narrative → explained user similarity → 4 models → eval harness +
   5 experiments + ablation. ~40 more points (EDA 10, methodology 15, eval 15). The eval
   harness (P18) is the highest-value DS deliverable — do not cut it.
5. **P19 (human eval):** credibility anchor for an n=10 study; product-impact points + a
   chunk of the eval score. Needs the models and a working frontend.
6. **P20 (loop + CI + tests):** makes it a *system*, not a pile of scripts; repro +
   product-impact points; CI is table stakes for "portfolio-grade".
7. **P21 (communication):** last, because it must describe what actually got built and
   what the experiments actually showed. 20 points ride on the whole thing hanging
   together in one narrative.

## Effort roll-up

| Phase | Title | Effort |
|---|---|---|
| 9  | Repo hygiene & public-safe history | S |
| 10 | Local infra: Docker Compose + migration runner | M |
| 11 | Star schema + enrichment into Postgres + medallion | L |
| 12 | Ingestion pipeline + Dagster + incremental/idempotent | XL |
| 13 | Data-quality suite + /api/health/data + Data Health page | M |
| 14 | Feature store + nightly compute + dual-loader collapse | L |
| 15 | Behavioral EDA notebooks | L |
| 16 | Explained user similarity | M |
| 17 | 4 recommendation models + hybrid | XL |
| 18 | Eval harness + 5 experiments + ablation | XL |
| 19 | Human-evaluation loop | L |
| 20 | Production loop + monitoring + tests + CI | L |
| 21 | Communication: README + diagram + write-up | M |

## Cross-cutting "keep working" rules

- Never change an RPC/MV name or signature without a compatibility shim; the frontend
  talks to ~40 endpoints across 10 route files.
- `DB_BACKEND=supabase` stays the default until Phase 20 so the live demo never breaks.
- Delete `data_loader.py` only at the end of Phase 14, only after
  `grep -r data_loader apps/api/app/routes` is empty.
- Every new model/metric ships with a unit test in the same phase or Phase 20.
- Each phase ends by refreshing MVs + smoke-testing all frontend pages (Overview,
  ListeningPatterns, Discovery, Milestones, Sessions, Recommendations, Simulator,
  Comparison, + new DataHealth/HumanEval).

## Critical existing files to reuse

- `apps/api/migrations/006_analytics_functions.sql` — the RPC/MV pattern +
  `_effective_user_id` convention to preserve across the schema migration.
- `apps/api/app/services/data_loader.py` — logic to port then delete:
  `_calculate_mood_metrics`, `_build_track_vectors`, `_cluster_sessions`,
  `_build_artist_transitions`, `get_recommendations` (~line 2029).
- `apps/api/app/services/supabase_data_loader.py` — becomes the single `data_service.py`.
- `apps/api/scripts/load_json_to_supabase.py` — ingestion + record-normalization logic to
  refactor into `apps/api/app/ingest/`.
- `apps/api/app/routes/compare.py` — Jaccard user-sim baseline to upgrade in Phase 16;
  endpoint contract to keep for the Comparison page.

## Baseline facts (verified 2026-08-31)

- 10 users, ~340k `streaming_history` rows in Supabase. Per-user music-stream counts:
  primary 70,700; others 131 (Abhiraj) to 60,026 (Snehal), most 25k–60k.
- ONE wide table `streaming_history` + `users`; NOT a star schema.
- 3 per-user MVs (`monthly_stats`, `top_artists`, `top_tracks`); ~40 RPCs
  (migrations 002/004/005/006/007), all scoped by `_effective_user_id(p_user_id)`.
- Enrichment (`libraries/analysis/*`) writes JSON/CSV to disk only, never into Postgres.
  `outputs/data/artists_info.json` = 4,216 artists, 54% with genres.
  `outputs/data/songs_info.json` = truncated write, ~808 tracks salvageable.
  `outputs/lyrics/lyrics.json` = 5,858 tracks.
- No feature tables, no DQ framework, no orchestration, no Docker, no tests, no CI.
- 16 standing TypeScript errors; `npm run build` (Netlify) skips `tsc`.
- `Moods.tsx` is an unrouted, broken orphan page.
- Frontend Netlify, API Render (no `render.yaml` in repo), DB Supabase.
- `data/other users/*.zip` (9 friends' raw exports **with third-party IPs**) are
  git-tracked — publish blocker, `.git` is 53 MB.
- `spotify-insights.env` (real secrets) is NOT tracked — only `.example` files are. Fine.
