# Roadmap (Trimmed) — 5 Resume Features, 3 Pages

**Date:** 2026-09-01
**Status:** Planned (Phases 9–16)
**Supersedes:** `20260831_231735_roadmap_de_ds_platform.md` (the 13-phase / 12-page version).

## Why this trim

The full roadmap built a 12-page app. A senior DE/DS reviewer does not want 12 dashboard
pages — they want a small number of things that prove: real pipeline (not a notebook),
data modeling, evaluation methodology, honest ML, one clean product surface.

**5 headline features, 3 user-facing pages, 8 phases.** Everything else is cut or folded
into the write-up.

---

## The 5 features

| # | Feature | Discipline | What a senior reviewer looks for | Resume line |
|---|---|---|---|---|
| **1** | **Orchestrated ingestion pipeline** — Dagster asset graph raw → bronze → silver (validate / normalize / dedup) → star schema (`fact_streams` + dims), incremental + idempotent, quarantine lane, per-run ingestion metrics | DE | Watermarks, dedup with no safe conflict target, a lineage graph, "runs twice = no-op" | *"Incremental, idempotent Dagster pipeline over 10 users × ~340k listening events; medallion layering + star schema; per-run data-quality gates."* |
| **2** | **Data-quality suite + Data Health page** — Pandera dataframe schemas + a SQL check runner; 6 categories (uniqueness, referential integrity, range, freshness, completeness, anomaly) run as a pipeline gate; one page shows pass/fail + match rates + per-user freshness | DE | Tests as a first-class artifact; the pipeline fails on blocking violations | *"Pandera + SQL data-quality suite surfaced on a live Data Health dashboard; blocks the pipeline on failure."* |
| **3** | **Behavioral feature store + per-user profiles** — materialized `gold.user_*` + `track_popularity` tables, nightly Dagster refresh; per-user behavioral vector is the DS foundation; heavy compute leaves the request path; the two data loaders collapse to one | DE + DS | On-request compute → materialized features; latency before/after | *"Nightly-refreshed feature store (artist affinity, temporal preferences, behavioral vectors); cut p95 analytics latency ~10s → sub-second."* |
| **4** | **4 recommenders + rigorous offline evaluation** — popularity floor / content / collaborative (implicit ALS) / hybrid `α·content + β·userSim + γ·recency + δ·temporal + ε·novelty`; per-user time-based train/test split; 9 ranking metrics; 5 experiments; ablation table | DS | Time-split (no leakage), honest n=10 framing, ablation quantifying each hybrid term | *"Content / collaborative / hybrid recommenders evaluated with a per-user time-based split on NDCG / MAP / Recall@K + coverage / novelty / serendipity; ablation quantifies each hybrid term."* |
| **5** | **Explainable recommendations + human-evaluation loop** — one page: pick a model, get ranked recs each with a "why this track" sentence + component bars; a blind-rating mode where the 10 real users score 20 recs (1–5, "knew it?", "would save?"), compared to offline metrics | DS + product | Explainability + real human eval is rare in a portfolio; anchors an n=10 study | *"Explainable recommendations ('why this track') with a blind human-evaluation loop (10 raters, ~200 judgements) validating offline metrics against real preference."* |

Feature **3** has **no page** — it is shown by the Dagster lineage graph + a
latency-before/after table in the README.

---

## The 3 pages

| Page | Composed of | Notes |
|---|---|---|
| **1. Insights** | the existing Overview + Listening Patterns + Discovery analytics merged into ONE scrollable page | Table stakes, not a headline. Kept, not expanded. A lightweight explained user-similarity section can live here later or stay write-up-only. |
| **2. Recommendations ⚗️** | feature #4 + feature #5 — model selector, context selector, ranked cards with "why this" + component bars, and a blind-rating mode | The DS conversation surface. |
| **3. Data Health** | feature #1 + feature #2 made visible — pipeline last-run status, raw/valid/dups/invalid/match-rate bars, DQ checks table, per-user freshness, row-count trend | The DE artifact surface. |

**Cut pages:** Milestones, Sessions, Moods, Simulator, Comparison-as-its-own-page,
NotFound stays.

**Simulator (Markov artist-walk):** cut the page. It is a deterministic argmax walk over a
first-order artist Markov chain with no evaluation — reads as a hackathon toy to a senior
reviewer and overlaps feature #4. Keep a one-paragraph "future work" note in the write-up:
*"artist-transition Markov prototype; needs held-out next-item sequence eval and
variable-order backoff before it's more than a demo."*

---

## Decisions locked

| Decision | Choice | Why |
|---|---|---|
| DB direction | **Local Postgres + Docker Compose**, Supabase optional via `DB_BACKEND` switch (default `supabase` until Phase 16) | Reviewer runs `docker compose up` with no account; live demo stays up |
| Orchestrator | **Dagster** | Asset model maps 1:1 to bronze/silver/gold + feature tables; one `dagster dev` process; free lineage graph |
| Collaborative-filtering libs | **implicit (ALS)** for Model 2, **LightFM** for the hybrid warm-start | Cleanest confidence-weighted implicit-feedback baseline; LightFM adds item/user features so the hybrid degrades gracefully at n=10 |
| Data-quality framework | **Pandera** (in-pipeline dataframe schemas) + a thin **SQL check runner** (RI / freshness / anomaly) | Great Expectations = heavy scaffolding for n=10; dbt-tests need adopting dbt now |
| Schema build tool | **Plain SQL migrations** (`apps/api/migrations/00X_*.sql`, existing `_effective_user_id` convention) | A dbt project is a second toolchain for a 6-table schema |
| Data loaders | **Collapse to one** by end of Phase 14 — port salvageable compute out of `data_loader.py`, then delete it; `supabase_data_loader.py` → `data_service.py` | Two 2373/807-line loaders synced by hand is the top maintenance liability |
| EDA notebooks | ~~Cut the 8-notebook set.~~ **REINSTATED 2026-09-01 as Phase 13.5** — 8 notebooks in `apps/api/notebooks/`, run against the DQ-gated star schema, each closing with a `## Decision inputs` cell; 2–3 key charts still fold into `RESEARCH_WRITEUP.md` | Owner will consult them when Phase 14/15 design decisions are in doubt, so their product surface is **decision support**, not the app. Placed after P13 (trusted data) and before P14 (first phase whose choices they inform) |
| Explained user similarity | **Cut the page.** Keep a lightweight cosine-sim over the per-user behavioral vector + a "why similar / why different" explanation as a **section in `RESEARCH_WRITEUP.md` only** | The user-sim result matters; a dedicated page does not |

---

## Explicitly INFEASIBLE — scope out / de-risk (state in README + write-up)

1. **Genre-transition analysis / genre-affinity features on current data.** Spotify API
   returns `genres: []` for most modern artists; ~54% artist-level coverage skewed to
   obscure artists; zero track-level genre.
   *De-risk:* Phase 11 adds a one-time MusicBrainz + Last.fm artist-tag backfill into
   `gold.dim_artist.genres_enriched`/`tags`. **Gate at Phase 11 verify:** if coverage
   after backfill is still `< ~80% of plays`, **cut `user_genre_affinity`** and lean on
   artist-affinity + audio-proxy features. Decision recorded in `DATA_MODEL.md`.
2. **"World-class collaborative recommender" — n=10.** Model 2 exists to *measure* how far
   CF gets at n=10 (Experiment E2), not to win. Report a limited/negative result if that's
   what the data shows. Hybrid uses `userSim` only as a light term (β small).
3. **Real Spotify audio features** (valence/energy/danceability/tempo) — `/audio-features`
   deprecated for new apps.
   *De-risk:* keep the existing `_calculate_mood_metrics` **behavioral proxies**, rename
   everywhere to `*_proxy` / `mood_proxy_*` so no reviewer mistakes them for real audio
   features, document the definition in one place.
4. **Statistically significant experiment results — n=10.** Every experiment reports
   effect sizes + per-user breakdown + "directional, not significant" caveat. The human
   eval loop (Phase 15) is the credibility anchor, not p-values.

---

## Scorecard being optimized (spec's own, /100)

problem formulation 10 · data ingestion/arch 10 (DE) · data modeling 10 (DE) ·
data quality 10 (DE) · scale/perf/repro 10 (DE) · behavioral EDA 10 (DS) ·
recommendation methodology 15 (DS) · experimentation/eval 15 (DS) ·
product impact 5 · communication 5.

---

## Phases (9–16)

Continues existing numbering (last shipped = Phase 8). Each phase leaves the app working.

### PHASE 9 — Repo hygiene & public-safe history · **S**
**Goal:** make the repo safe to publish.
**Moves:** communication 5; scale/perf/repro 10 (partial).
- **P0 blocker:** purge from **all git history** `data/other users/*.zip` — 9 friends' raw
  Spotify exports, **git-tracked, containing third-party `ip_addr`** (e.g.
  `REDACTED_IP`), introduced in commit `7d16c08`. Tool: `git filter-repo --path
  'data/other users' --invert-paths` (or BFG). Force-push `main`, re-clone, close/rebase
  `origin/feat/multi-user-analytics-switch`.
- Evaluate purging `data/*.json` (~55 MB) + `outputs/data/songs_info.json` (45 MB) → a
  documented download step or Git LFS. `.git` is currently 53 MB.
- `data/README.md` — how to obtain a Spotify GDPR export, drop it in `data/raw/<user>/`.
- `data/fixtures/sample_streaming_history.json` — tiny synthetic fixture for CI.
- `.gitignore`: add `data/raw/`, `outputs/`; keep env rules. (`*.ipynb` ignore stayed here
  because notebooks were cut at the time — **Phase 13.5 reinstated them and must add
  `!apps/api/notebooks/*.ipynb`**, or new notebooks silently never get committed.)
- Pinned deps: `apps/api/requirements.txt` with exact `==` (note: it is currently
  **missing `supabase`** — a hard runtime dep); split `apps/api/requirements-dev.txt`
  (pytest, pandera, dagster, ruff).
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
  `apps/api`), `web` (build `apps/web`), `dagster` added Phase 12. `.env`-driven.
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
**App still works:** `DB_BACKEND=supabase` (default) unchanged.
**Verify:** `docker compose up` → web :5173, API `/health` 200,
`/api/compare/leaderboard` returns fixture users; `migrate.py` run twice → second a no-op.

### PHASE 11 — Star schema + enrichment loaded INTO Postgres + bronze/silver/gold · **L**
**Goal:** turn the one wide `streaming_history` table into a Medallion-layered star schema
with real dim tables populated from the on-disk enrichment.
**Moves:** data modeling 10; data ingestion/arch 10. — **feature 1 (schema half)**
- **Medallion schemas** — `008_medallion_schemas.sql`: `CREATE SCHEMA bronze; silver; gold;`
  - `bronze.raw_streams` = append-only landing copy + `_ingest_id`, `_source_file`,
    `_ingested_at`, `_raw` jsonb. Existing `streaming_history` copied here.
  - `silver.streams` = validated + normalized + deduped, typed, FK-ready keys.
  - `gold` = star schema + feature tables (Phase 14).
- **Star schema** — `009_star_schema.sql` (in `gold`):
  `dim_user`, `dim_time` (date/hour grain), `dim_artist` (nat key = normalized name; cols
  name, spotify_artist_id, popularity, followers, genres jsonb, tags jsonb,
  genres_enriched jsonb), `dim_track` (nat key = `track_uri` or hash of
  `(track_name, artist)`; cols track_name, artist_key, album, duration_ms, explicit,
  release_year, popularity, `mood_proxy_valence/energy/danceability`, `audio_source` enum),
  `dim_album` (optional), `fact_streams` (grain = one play; FKs to the 4 dims; measures
  ms_played, skipped, shuffle, offline, reason_start/end), `recommendation_events` (empty;
  populated Phase 13-reco / renumbered). Lookups keep `_effective_user_id(p_user_id)`.
- **Enrichment → Postgres** `apps/api/scripts/load_enrichment_to_db.py` —
  `outputs/data/artists_info.json` (4,216 artists), salvageable
  `outputs/data/songs_info.json` (~808 via existing `_salvage_json_array`),
  `outputs/lyrics/lyrics.json` (5,858) → upsert into `gold.dim_artist`, `gold.dim_track`,
  `gold.track_lyrics(track_key, source, has_lyrics, lang, word_count)` (metadata only —
  no lyrics text committed).
- **Artist-tag backfill** (genre de-risk): MusicBrainz + Last.fm tags for `dim_artist` →
  `genres_enriched`/`tags`. Measure **coverage-of-plays** at the verify gate.
- **Build fact/dim from silver** `apps/api/scripts/build_star_schema.py` (or Dagster
  assets Phase 12): populate dims, then `fact_streams` by joining silver rows to dim
  natural keys; log track/artist match-rate.
- Rewrite the 3 MVs + hottest RPCs from `006` to read `gold.fact_streams` + dims —
  `010_mvs_on_star.sql`. **Keep names + signatures identical** so routes don't change.
- `documentation/DATA_MODEL.md` (ER + medallion flow + genre-coverage decision); update
  `documentation/database_schema_diagram.md` to reality.
**Files:** `apps/api/migrations/008_medallion_schemas.sql`, `009_star_schema.sql`,
`010_mvs_on_star.sql`, `apps/api/scripts/load_enrichment_to_db.py`,
`apps/api/scripts/build_star_schema.py`, `apps/api/app/ingest/normalize.py`,
`apps/api/app/services/supabase_data_loader.py` (point heavy queries at `gold.*`),
`documentation/DATA_MODEL.md`, `documentation/database_schema_diagram.md`.
**App still works:** MVs + RPCs keep names/signatures. Run star build, refresh MVs, smoke
the 3 remaining pages (+ any not-yet-removed).
**Verify:** `SELECT count(*) FROM gold.fact_streams` ≈ 340k;
`SELECT count(*) FROM gold.dim_track WHERE audio_source='enriched'` > 800; numbers on
Insights + Recommendations unchanged vs pre-migration; **genre-coverage-of-plays recorded
→ keep or cut `user_genre_affinity`**.

### PHASE 12 — Dagster ingestion pipeline: raw→validate→normalize→dedup→enrich→quarantine, incremental + idempotent · **XL**
**Goal:** replace the two manual load scripts with one incremental, idempotent, observable
Dagster pipeline with a quarantine lane and ingestion metrics.
**Moves:** data ingestion/arch 10; scale/perf/repro 10; data quality 10 (partial). — **feature 1**
- **`apps/api/app/ingest/`:**
  - `discover.py` — scan `data/raw/<user>/*.json`, per-file content hash.
  - `landing.py` — append new rows to `bronze.raw_streams` + `_source_file`,
    `_ingested_at`, `_raw`. **Watermark** `ingest_state(user_id, source_file, file_hash,
    max_ts, rows_landed, ingested_at)` — skip files whose `(user_id, file_hash)` present ⇒
    idempotent; incremental = land only rows with `ts > watermark_max_ts` on a superset
    re-export.
  - `validate.py` — Pandera schema (`schemas.py`): `ts` present & parseable, `ms_played`
    in `[0, 24h]`, track name non-null for music rows, enum on `reason_start/end`,
    `platform` string. Failing rows → `bronze.quarantine(_ingest_id, rule, detail, _raw,
    quarantined_at)`.
  - `normalize.py` — trim/casefold artist & track keys, UTC timestamps, duration → ms,
    booleans.
  - `dedup.py` — Spotify exports legitimately contain byte-identical rows. Keep all in
    `bronze`; collapse **true byte-identical dupes** in `silver` via a stable
    `row_fingerprint` hash + `ROW_NUMBER`; record `dups_dropped`.
  - `enrich.py` — left-join silver → `gold.dim_artist`/`dim_track`; unmatched rows still
    flow (fact row, null enrichment), counted as `unmatched`.
  - `metrics.py` — per-run `ingest_run(run_id, started_at, finished_at, users, files_new,
    rows_raw, rows_valid, rows_quarantined, dups_dropped, rows_silver, track_match_rate,
    artist_match_rate, status)` + per-user `ingest_run_user`.
- **Dagster project** `apps/api/dagster_project/`:
  `assets.py` (software-defined assets `raw_streams` [partitioned by user/date],
  `quarantine`, `silver_streams`, `dim_artist`, `dim_track`, `dim_time`, `fact_streams` —
  deps wired so the lineage graph tells the DE story), `resources.py` (Postgres from
  `DATABASE_URL`), `jobs.py` (`nightly_ingest_job`), `schedules.py` (cron 03:00),
  `definitions.py`.
- Add `dagster` service to `docker-compose.yml` (`dagster dev`, port 3000).
- Keep `load_json_to_supabase.py` / `load_multi_user_data.py` as thin deprecated wrappers.
- `documentation/INGESTION.md`.
**Files:** `apps/api/app/ingest/{__init__,discover,landing,validate,normalize,dedup,enrich,metrics,schemas}.py`,
`apps/api/migrations/011_ingest_state_and_runs.sql`,
`apps/api/dagster_project/{__init__,definitions,assets,resources,jobs,schedules}.py`,
`docker-compose.yml`, `apps/api/requirements.txt` (dagster, dagster-webserver,
dagster-postgres, pandera), the two legacy loaders, `documentation/INGESTION.md`.
**App still works:** pipeline writes the same `gold.fact_streams`/dims the app reads. Run
the full job once on the real 10 exports, refresh MVs, smoke pages.
**Verify:** `dagster job execute -j nightly_ingest_job` green; immediate re-run ⇒
`files_new=0`, `rows_landed=0` (idempotent); inject a malformed fixture row ⇒ lands in
`bronze.quarantine` with a rule name; latest `ingest_run` shows sane
raw/valid/dups/invalid/match-rate; fact count unchanged vs Phase 11.

### PHASE 13 — Data-quality suite + `/api/health/data` + Data Health page + collapse analytics to one "Insights" page · **M**
**Goal:** automated DQ tests as a pipeline gate, surfaced in the UI; and reduce the app to
its final 3 pages.
**Moves:** data quality 10; product impact 5 (partial); communication 5 (partial). — **feature 2 + page cut**
- **`apps/api/app/quality/`:**
  - `checks.py` — registry; each returns `CheckResult(name, category, severity, passed,
    observed, expected, rows_failed, detail)`. Categories: **uniqueness** (no dup
    `_ingest_id`; `fact_streams` PK; `dim_track` nat key), **referential_integrity**
    (`fact_streams.track_key` ∈ `dim_track`; `user_id` ∈ `dim_user`), **range**
    (`ms_played` 0–24h; `release_year` 1900–next yr; affinity scores 0–1), **freshness**
    (`max(ingested_at)` within N days; per-user `max(fact ts)` not absurdly stale),
    **completeness** (non-null track/artist rate; % plays with enrichment ≥ threshold),
    **anomaly** (per-user daily play count vs 30-day rolling median ± k·MAD; z-score on
    run-over-run row deltas).
  - `pandera_schemas.py` — silver/gold dataframe schemas (shared with `ingest/schemas.py`).
  - `run.py` — run all; write `dq_run(run_id, run_at, passed, failed, warned)` +
    `dq_result(run_id, name, category, severity, passed, observed, expected, detail)`.
- Wire as a Dagster **asset check** / final asset `data_quality` downstream of
  `fact_streams` (+ feature tables Phase 14); job fails on `severity=blocking`, warns
  otherwise.
- **API:** extend `apps/api/app/routes/health.py` — `GET /api/health/data` returns latest
  `dq_run` + grouped `dq_result` + latest `ingest_run` metrics + per-user freshness. Keep
  the old `/health` liveness blob.
- **Frontend — the page cull happens here:**
  - New `apps/web/src/pages/Insights.tsx` — merge the content of Overview + Listening
    Patterns + Discovery into one scrollable page (existing charts, kept, not expanded).
  - New `apps/web/src/pages/DataHealth.tsx` — pipeline last-run status; raw/valid/dups/
    invalid/match-rate bars; DQ checks table (green/amber/red by category); per-user
    freshness list; row-count trend sparkline. Existing MUI X Charts + palette
    (`#1c0b19/#140d4f/#4ea699/#2dd881/#6fedb7`, Inter).
  - **Delete** `Overview.tsx`, `ListeningPatterns.tsx`, `Discovery.tsx`, `Milestones.tsx`,
    `Sessions.tsx`, `Moods.tsx`, `Simulator.tsx`, `Comparison.tsx` and their routes/nav
    entries + the now-unused endpoints' client fns.
  - Router = `/` → **Insights**, `/recommendations` → **Recommendations**, `/data-health`
    → **Data Health**, `*` → NotFound. Drawer = 3 items.
  - Prune `apps/api/app/routes/` + `apps/web/src/api/client.ts` to only what the 3 pages
    call. Keep the RPCs the Insights charts still need; drop milestones/sessions/mood/sim
    routes (or leave them dark — decide at implementation, prefer delete).
- `documentation/DATA_QUALITY.md`.
**Files:** `apps/api/app/quality/{__init__,checks,pandera_schemas,run}.py`,
`apps/api/migrations/012_dq_tables.sql`, `apps/api/app/routes/health.py`,
`apps/api/dagster_project/assets.py` (add `data_quality`),
`apps/web/src/pages/Insights.tsx` (new), `apps/web/src/pages/DataHealth.tsx` (new),
`apps/web/src/pages/{Overview,ListeningPatterns,Discovery,Milestones,Sessions,Moods,Simulator,Comparison}.tsx`
(delete), `apps/web/src/App.tsx` / router (rewrite to 3 routes),
`apps/web/src/layout/*` nav (3 items), `apps/web/src/api/client.ts` (prune),
`apps/api/app/routes/{milestones,sessions,mood,sim}.py` (delete),
`apps/api/app/main.py` (drop router regs), `documentation/DATA_QUALITY.md`.
**App still works:** after the cut, the 3 pages render; smoke each in `docker compose up`.
**Verify:** `python -m app.quality.run` prints a pass/fail table; `/api/health/data`
returns ≥6 categories; Data Health + Insights + Recommendations all render; delete a
`dim_track` row ⇒ referential-integrity check red and the page shows it; drawer shows
exactly 3 items.

### PHASE 13.5 — Behavioral EDA notebook set (decision-support reference) · **M**
**Goal:** a small, re-runnable set of EDA notebooks over the quality-gated star schema,
written to be **read later as evidence** when a Phase 14/15/16 design decision is in doubt.
**Moves:** behavioral EDA 10 (the DS-scorecard line P14 only partially covered);
communication 5 (partial).

> **Why here, not earlier or later.** Notebooks must read a *stable, trusted* surface:
> `gold.fact_streams` + dims exist from P11, are incrementally populated from P12, and are
> DQ-gated from P13 — so a chart cannot be quietly wrong. And they must land *upstream of
> the decisions they inform*: P14's feature definitions, P15's model + experiment choices.
> Placed after P15 they would be archaeology; placed before P11 they would read the
> un-modeled wide table and be invalidated by the star schema.
> Numbered **13.5** deliberately: Phases 14/15/16 keep their numbers, so `UPDATE.md` rows,
> branch names, and the already-written Phase 9/10 docs need no renumbering.

**Decisions each notebook is meant to settle** (this is the point of the phase — every
notebook ends with a **`## Decision inputs`** markdown cell stating the numbers a later
phase should quote):

| Notebook | Feeds decision in |
|---|---|
| `01_dataset_overview.ipynb` | P16 write-up "research question / n=10 caveats"; per-user coverage floor for every model |
| `02_temporal_behavior.ipynb` | **P14** `user_temporal_preferences`: the actual `hour_bucket` / `dow_bucket` cut points and `context_label` set — derived, not guessed; `night_share` cutoff |
| `03_artist_loyalty_discovery.ipynb` | **P14** `user_artist_affinity` recency-weight half-life + `repeat_ratio` definition; **P15** explorer-vs-loyalist per-user experiment breakdown |
| `04_genre_coverage.ipynb` | **P14 genre-affinity kill gate** — the `<80% of plays` decision from the P11 backfill, with the evidence attached |
| `05_session_archetypes.ipynb` | **P14** `_cluster_sessions` port (k, gap threshold); **P13** Insights session-archetype chart |
| `06_mood_proxy_validation.ipynb` | **P14** `mood_proxy_*` — shows what the behavioral proxies do and do not track, so P16 can state the limitation honestly |
| `07_cf_feasibility.ipynb` | **P15** the n=10 CF reality check *before* building Model 2: user-item sparsity, item overlap across users, cold-start mass. Decides how much weight the hybrid gives `userSim` (β) |
| `08_candidate_pool.ipynb` | **P15** `candidates(user_id)` — how big the candidate pool actually is per user, and where the popularity baseline saturates |

**Structure — `apps/api/notebooks/`:**
- `README.md` — how to run (local Postgres via `docker compose up`, `DB_BACKEND=local`),
  execution order, and **"read this table to find which notebook answers your question"**
  (the decision map above).
- `_common.py` — shared, imported by every notebook, so notebooks stay thin and no chart
  logic is duplicated: `get_engine()` (reuses `apps/api/app/config.py` + `db/session.py`,
  **never** a hardcoded DSN), `load_fact(users=None, cols=None)`, `PALETTE` (the project
  hex list `#1c0b19/#140d4f/#4ea699/#2dd881/#6fedb7`), `save_fig(name)` →
  `outputs/eda/<name>.png`, `decision(**kwargs)` helper that renders the closing
  Decision-inputs block consistently.
- The 8 notebooks above. Each: params cell at top (`USERS`, `SINCE`), pandas + matplotlib,
  every chart titled + axis-labeled, and the closing `## Decision inputs` cell.
- **Anonymization rule:** notebooks are committed **with outputs stripped by default**
  (`nbstripout` / `--ClearOutputPreprocessor`) — outputs embed real listening history for
  10 named people. Charts that are quoted in the write-up get exported to `outputs/eda/`
  (gitignored) and only the *aggregate* ones are committed under
  `documentation/assets/eda/`. Non-primary users appear as `user_02…user_10`, never by
  name — the `_common.py` loader applies the alias map.

**`.gitignore` change (reverses a Phase 9 line):** Phase 9 kept the blanket `*.ipynb`
ignore because notebooks were cut. Un-ignore the notebook dir now:
```gitignore
!apps/api/notebooks/*.ipynb
outputs/eda/
```
Verify with `git check-ignore -v apps/api/notebooks/01_dataset_overview.ipynb` → no match.
(P15's `evaluation.ipynb` lands in the same dir and inherits this fix.)

**Files:** `apps/api/notebooks/README.md`, `apps/api/notebooks/_common.py`,
`apps/api/notebooks/0{1..8}_*.ipynb`, `apps/api/requirements-dev.txt` (add `jupyter`,
`matplotlib`, `seaborn`, `nbstripout`, `nbconvert`), `.gitignore`,
`documentation/assets/eda/.gitkeep`, `documentation/EDA_FINDINGS.md` (2–4 page digest:
one section per notebook = question asked → chart → **the number a later phase should
use**; this is the fast path when you do not want to boot Jupyter).
**App still works:** notebooks are read-only consumers — zero writes, no app/API/schema
change in this phase.
**Verify:** `docker compose up` then
`jupyter nbconvert --to notebook --execute apps/api/notebooks/*.ipynb --stdout > /dev/null`
runs all 8 clean against the **fixture** DB (so this phase is CI-able in P16 — the fixture
is 40 rows, so notebooks must degrade to "insufficient data" rather than raise);
re-execute against the real 71k-row DB and confirm every notebook renders; every notebook
has a `## Decision inputs` cell; committed `.ipynb` files have empty `outputs`
(`grep -c '"output_type"' *.ipynb` → 0); no real non-primary username in any committed
notebook or in `EDA_FINDINGS.md`; `EDA_FINDINGS.md` has 8 sections.

### PHASE 14 — Feature store: `user_*` + `track_popularity` tables + nightly compute + dual-loader collapse · **L**
**Goal:** move heavy per-user compute off the request path into materialized `gold`
feature tables refreshed nightly; collapse to one data loader.
**Moves:** data modeling 10; scale/perf/repro 10; behavioral EDA 10 (partial). — **feature 3**
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
    (feature #4 hybrid + the write-up's user-sim section consume this).
  - `track_popularity(track_key, global_plays, distinct_users, plays_last_90d,
    popularity_rank, popularity_percentile)` — Baseline-0 source.
- **Compute jobs** `apps/api/app/features/{__init__,daily,artist_affinity,genre_affinity,
  temporal,behavior_vector,track_popularity}.py` — pandas-first (340k rows fits in memory;
  **document that volume does not justify PySpark**), each reads `gold.fact_streams` +
  dims, full-refresh-per-run (simple + idempotent). `run_all(users=None)`.
- **Dagster assets** for each feature table, downstream of `fact_streams`, upstream of
  `data_quality`.
- **API switch + loader collapse:** `apps/api/app/services/feature_repo.py` (typed reads
  from `gold.*`). Port remaining unique `data_loader.py` compute into
  `apps/api/app/analytics/{sessions,discovery}.py` as pure functions (`_cluster_sessions`
  lands here — still used by the Insights session-archetype chart). Then **delete
  `data_loader.py`**; rename `supabase_data_loader.py` → `data_service.py`; update route
  imports.
- `documentation/FEATURE_STORE.md`.
**Files:** `apps/api/migrations/013_feature_tables.sql`, `apps/api/app/features/*.py` (7),
`apps/api/app/analytics/{sessions,discovery}.py`,
`apps/api/app/services/feature_repo.py`,
`apps/api/app/services/supabase_data_loader.py` → `data_service.py`,
`apps/api/app/services/data_loader.py` (**delete** at end of phase),
`apps/api/dagster_project/assets.py`, `apps/api/app/routes/*.py` (imports),
`documentation/FEATURE_STORE.md`.
**App still works:** switch reads endpoint-by-endpoint; delete `data_loader.py` only after
every route is off it and smoke-tested.
**Verify:** `python -m app.features` populates all 6 tables;
`SELECT count(*) FROM gold.user_daily_features` ≈ 10 users × days-active; p95 latency of
the Insights + `/api/reco/*` endpoints drops sharply (before/after in the README);
`grep -r data_loader apps/api/app/routes` empty.

### PHASE 15 — Recommenders + offline evaluation + explainable recs + human-eval loop · **XL**
**Goal:** the 4 models, the eval harness with 9 metrics + 5 experiments + ablation, the
explainable Recommendations page, and the blind human-rating mode — features #4 and #5, in
one phase because they share the `reco/` and `eval/` packages and one page.
**Moves:** recommendation methodology 15; experimentation/eval 15; product impact 5;
communication 5 (partial). — **features 4 + 5**

**4A · Models** `apps/api/app/reco/`:
- `base.py` — `Recommender` protocol: `recommend(user_id, k, context=None, horizon=None)
  -> list[RecItem]`, `RecItem = {track_key, score, components: dict, explanation: str}`;
  `candidates(user_id)` helper.
- `popularity.py` — **Baseline 0**: rank by `gold.track_popularity`. `"Popular across
  listeners (rank {r})."`
- `content.py` — **Model 1**: port `data_loader.get_recommendations` — cosine on the 9-dim
  vector `[valence_proxy, energy_proxy, danceability_proxy, track_popularity,
  artist_popularity, artist_followers_log, duration_min, explicit, release_year_recency]`,
  recency-weighted (exp half-life 180d) × log(play_count) preference vector, MMR (λ=0.7).
  Rename mood dims `*_proxy`. Reuse the existing top-3 standardized-contribution → phrase
  logic. Optional mood steer kept.
- `collaborative.py` — **Model 2**: `implicit.als.AlternatingLeastSquares` on a
  `user × track` confidence matrix (`1 + α·log1p(plays)`). **Document the n=10 ceiling**
  in the module docstring and every result table. `"Listeners with taste like yours
  ({neighbor names}) play this."`
- `hybrid.py` — **Model 3**:
  `score = α·content + β·userSim + γ·recency + δ·temporal + ε·novelty`, where `userSim`
  uses a cosine over `gold.user_behavior_vector` (the lightweight user-sim; no dedicated
  page); weights in `apps/api/app/reco/config.py` (defaults α=.45 β=.15 γ=.15 δ=.15
  ε=.10), tunable; ablation zeroes each in turn. Explanation composes the top-2
  contributing components into a sentence.
- `context.py` — map request timestamp / `context` string ({morning, gym, commute,
  evening, late_night}) to the temporal-preference target vector; the **long-term vs
  short-term** knob: build the preference vector at 4 horizons (lifetime / 12mo / 90d /
  recency-weighted-exp), `horizon` param, compared in E4.
- `user_similarity.py` — cosine over `user_behavior_vector` + component contributions
  ("driven by shared indie-pop affinity + both late-night; differ most in discovery
  rate"). Consumed by `hybrid.py`; results go in `RESEARCH_WRITEUP.md`, **no route, no
  page** (keeps `_jaccard` from `compare.py` as a named baseline for the write-up).
- `registry.py` — `get_recommender(name)`; import-guard `implicit`/`lightfm` as optional
  extras.
- **Persist:** every served rec → `gold.recommendation_events(event_id, user_id,
  track_key, model, rank, score, components_json, explanation, context, served_at,
  split_tag)`.

**4B · Evaluation** `apps/api/app/eval/`:
- `split.py` — **per-user time-based split**: `T_u` per user (last 20% of timeline);
  `train = plays < T_u`, `test = plays > T_u`. `eval_split(user_id, split_id, cutoff_ts,
  train_rows, test_rows)`.
- `metrics.py` — `precision_at_k, recall_at_k, ndcg_at_k, map_at_k, hit_rate_at_k`
  (relevance = track in the user's test window); `coverage` (fraction of catalog ever
  recommended); `diversity` (1 − mean pairwise cosine of recommended tracks' proxy
  vectors); `novelty` (mean `−log2 popularity_percentile`); `serendipity` (relevant AND
  unexpected vs a popularity baseline).
- `harness.py` — `evaluate(recommender, split, k_list=[5,10,20]) -> DataFrame`; per-user +
  aggregate; bootstrap CIs over the 10 users.
- `experiments/e1..e5_*.py` — each writes `outputs/eval/<exp>.{csv,json}` + a markdown
  fragment:
  - E1 `content_vs_popularity` — Model 1 vs Baseline 0.
  - E2 `collab_with_n10` — Model 2 vs Baseline 0 vs Model 1; explicit "does CF help at
    n=10?" verdict + per-user table.
  - E3 `hybrid_vs_components` — Model 3 vs best of {1,2} vs Baseline 0.
  - E4 `recency_weighting` — hybrid at horizons {lifetime, 12mo, 90d, recency-weighted}.
  - E5 `contextual` — hybrid with vs without the δ·temporal term on context-tagged test
    slices.
- `ablation.py` — full hybrid NDCG@10 vs (−content), (−userSim), (−recency), (−temporal),
  (−novelty); emits `outputs/eval/ablation_table.md`.
- **One notebook** `apps/api/notebooks/evaluation.ipynb` — runs the harness, renders all
  metric tables + the 5 experiments + the ablation table + a "headline findings" cell.
  (Lives alongside the 8 Phase-13.5 EDA notebooks in `apps/api/notebooks/` and reuses their
  `_common.py` engine/palette/`save_fig` helpers; same outputs-stripped + alias rules.)

**4C · Human-eval loop** (feature #5):
- **Schema** `014_human_eval.sql`: `gold.eval_session(session_id, user_id, model,
  created_at, status)`, `gold.eval_item(item_id, session_id, track_key, rank, model,
  blind_token)`, `gold.recommendation_ratings(item_id, user_id, rating_1_5, knew_it bool,
  would_save bool, rated_at, free_text)`.
- `apps/api/app/eval/human_set.py` — per user draw 20 items mixing models (5 each), model
  labels stripped, `blind_token`s minted.
- `apps/api/app/eval/human_vs_offline.py` — per-model mean rating, %knew-it, %would-save,
  correlation of human rating vs offline NDCG/precision/serendipity per user; feeds a
  section of `evaluation.ipynb` and the write-up.

**4D · API + page:**
- Rewrite `apps/api/app/routes/reco.py` —
  `GET /api/reco?user_id&model=popularity|content|collaborative|hybrid&k&context&horizon`
  (items include `explanation` + `components`); `POST /api/reco/feedback` (thumbs/save →
  `recommendation_events.feedback`).
- `apps/api/app/routes/eval.py` — `POST /api/eval/session`, `GET /api/eval/session/{id}`
  (20 blind items — **no `model` field** in the payload), `POST /api/eval/rating`.
- `apps/web/src/pages/Recommendations.tsx` — model selector, context selector, ranked
  cards with the "why this" sentence + a component-contribution bar per card; a **"Rate
  blind" mode** toggling into the one-card-at-a-time rater (1–5 stars, "knew it?" /
  "would save?" toggles, progress bar). Shareable link `/#/recommendations?eval=<session>`.
- `apps/web/src/api/client.ts` — `getReco()`, `postRecoFeedback()`, `createEvalSession()`,
  `getEvalSession()`, `postEvalRating()`.
- Deps: `implicit`, `lightfm` in `apps/api/requirements.txt` (LightFM build fiddly — pin,
  gate behind an extra).
- `documentation/RECOMMENDERS.md` (four models + hybrid formula + n=10 caveat +
  explanation templates), `apps/api/notebooks/README.md` (how to run `evaluation.ipynb`).
**Files:** `apps/api/app/reco/{base,popularity,content,collaborative,hybrid,context,config,registry,user_similarity}.py`,
`apps/api/app/eval/{__init__,split,metrics,harness,ablation,human_set,human_vs_offline}.py`,
`apps/api/app/eval/experiments/e1..e5_*.py`,
`apps/api/migrations/{015_recommendation_events.sql,016_eval_split.sql,014_human_eval.sql}`
(numbering finalized at implementation),
`apps/api/app/routes/reco.py` (rewrite), `apps/api/app/routes/eval.py` (new),
`apps/api/app/main.py` (register `eval` router),
`apps/web/src/pages/Recommendations.tsx` (rewrite),
`apps/web/src/api/client.ts`, `apps/api/notebooks/evaluation.ipynb`,
`apps/api/notebooks/README.md`, `outputs/eval/.gitkeep`,
`documentation/RECOMMENDERS.md`, `apps/api/requirements.txt`.
**App still works:** default `model=content` = current behavior; blind mode is a toggle.
**Verify:** `GET /api/reco?user_id=<primary>&model=hybrid&k=10&context=late_night` → 10
items each with non-empty `explanation` + a `components` dict keyed
{content,userSim,recency,temporal,novelty}; `model=collaborative` → 10 items + logged
n=10 caveat; `python -m app.eval.experiments.e1_content_vs_popularity` writes a CSV with
NDCG@10 for both models across all 10 users; `python -m app.eval.ablation` writes
`ablation_table.md` with 6 rows; `evaluation.ipynb` executes end-to-end via nbconvert;
create an eval session → fetch it (20 items, no `model` field) → submit 20 ratings;
Recommendations page renders all four models + the blind rater.

### PHASE 16 — Production loop + tests + CI + communication · **L**
**Goal:** close the new-history → ingest → validate → features → model → recs loop; add
tests + CI; rewrite the docs to one clear pitch.
**Moves:** scale/perf/repro 10; product impact 5; communication 5; problem formulation 10.
- **Loop wiring:**
  - `apps/api/app/routes/ingest.py` — `POST /api/ingest/user` (multipart export
    zip/json) → drops into `data/raw/<user>/`, kicks the Dagster `nightly_ingest_job`
    (or a `run_pipeline` fn) → returns an `ingest_run` id. Minimal auth (`X-API-Key`
    dependency in `apps/api/app/deps.py`) on write endpoints (`/api/ingest`,
    `/api/eval/rating`, `/api/reco/feedback`); read endpoints stay open for the demo but
    note it.
  - **Retrain trigger:** Dagster sensor `retrain_on_new_data` — when an `ingest_run` adds
    rows for a user, mark feature tables + models stale, re-run `features` + (cheap)
    `content`/`popularity`, log `model_run(model, trained_at, n_users, n_interactions,
    notes)`.
  - Dagster asset graph: `raw → silver → dims/fact → features → user_behavior_vector →
    data_quality`; `eval` runs on demand.
- **Monitoring (light):** `/api/health/data` extended with pipeline SLA (last successful
  run age), DQ pass-rate trend, model freshness; the Data Health page gains a "Pipeline &
  Model freshness" section. Structured logging + request-timing middleware in
  `apps/api/app/main.py`. (No Prometheus.)
- **Tests** `apps/api/tests/`: `test_ingest_normalize.py`, `test_ingest_dedup.py`,
  `test_pandera_schemas.py`, `test_quality_checks.py`, `test_eval_metrics.py`
  (NDCG/MAP/precision vs hand-computed fixtures), `test_reco_smoke.py` (each model returns
  k items with explanations on a fixture DB). `apps/api/conftest.py` — the compose `db` +
  `data/fixtures/` (or testcontainers).
- **Frontend:** `vitest` + 2–3 component tests (DataHealth renders, Recommendations model
  switch); wire `npm run test`. **Fix the 16 standing TS errors** (fewer now — the 8
  deleted pages carried most of them); make `npm run build` = `tsc -b && vite build`.
- **CI** `.github/workflows/ci.yml`: `lint` (ruff + eslint), `typecheck` (`tsc -b`),
  `pytest` (Postgres service container + migrations + fixtures), `notebook`
  (`nbconvert --execute` on the fixture DB over **`evaluation.ipynb` + the 8 Phase-13.5
  EDA notebooks** — catches an EDA notebook silently rotting after a schema change), plus
  an `nbstripout --verify` step so no notebook lands with real listening data in its
  outputs; `docker-build` (`docker compose build`).
- **Communication:**
  - **Rewrite `README.md`** — pitch: *"A multi-user music intelligence platform that
    builds behavioral profiles from longitudinal listening histories and generates
    personalized, explainable recommendations that adapt to preference changes."*
    Sections: research question (rich histories, n=10); architecture (medallion + star +
    feature store + Dagster + FastAPI + React); how to run (`docker compose up`); the 4
    models + hybrid formula; evaluation (9 metrics + 5 experiments + ablation + human
    loop); **honest limitations** (genre data, n=10 CF, deprecated audio features);
    results headline; latency before/after.
  - **Rewrite `PROJECT_OVERVIEW.md`** — architecture-of-record; retire the single-user
    framing.
  - `documentation/architecture.md` — Mermaid data-flow (raw exports → bronze → silver →
    star → features → models → API → 3 pages → feedback → retrain) + the Dagster
    asset-lineage screenshot + the ER diagram.
  - `documentation/RESEARCH_WRITEUP.md` — question, method (time-split), results per
    experiment, ablation, human-vs-offline agreement, the **user-similarity section**
    (cosine over behavior vectors + explanation), 2–3 EDA charts folded in (taste drift,
    explorer-vs-loyalist, session archetypes) — **exported from the Phase 13.5 notebooks
    via `save_fig`, not rebuilt**, so the write-up and the notebooks cannot disagree — the
    **Simulator "future work" paragraph**, what worked / what didn't.
  - `documentation/DEMO_SCRIPT.md` — a 60-second walkthrough.
  - `CLAUDE.md` — update to phases 9–16 + the new architecture; keep palette/font/chart
    specs. Mark `database_schema_diagram.md` + stale phase docs superseded.
**Files:** `apps/api/app/routes/ingest.py`, `apps/api/app/deps.py`,
`apps/api/app/routes/reco.py` (`/feedback`), `apps/api/app/routes/health.py`,
`apps/api/app/main.py`, `apps/api/dagster_project/{sensors,jobs,schedules}.py`,
`apps/api/migrations/017_model_runs.sql`, `apps/api/tests/*.py` (~6),
`apps/api/conftest.py`, `apps/web/vitest.config.ts`, `apps/web/src/**/*.test.tsx`,
`apps/web/package.json`, `.github/workflows/ci.yml`, `apps/api/requirements-dev.txt`,
`README.md` (rewrite), `PROJECT_OVERVIEW.md` (rewrite), `CLAUDE.md`,
`documentation/{architecture,RESEARCH_WRITEUP,DEMO_SCRIPT}.md`,
`documentation/database_schema_diagram.md` ("superseded").
**App still works:** additive except the `build` script change + the TS fixes.
**Verify:** push a branch → CI green on all jobs; `POST /api/ingest/user` with a fixture
export → `ingest_run` created, feature tables refresh, `/api/reco` reflects the new data;
`pytest apps/api` green; `docker compose build` succeeds; a fresh reader can `git clone` →
`docker compose up` → reach all 3 pages following only the README; Mermaid renders on
GitHub.

---

## Sequencing rationale

1. **P9 (blocker):** can't publish with third-party PII in git history. Cheap.
2. **P10–P13 (DE backbone + page cull):** local infra → star schema → Dagster pipeline →
   DQ suite + Data Health page, and the app drops from 12 pages to 3. Features #1 and #2
   land. Every later phase depends on the schema + pipeline.
3. **P13.5 (EDA notebooks):** the last cheap moment to *look at the data before committing
   to feature definitions*. Runs on a schema that is populated (P12) and quality-gated
   (P13), and lands immediately upstream of every phase whose choices it informs — P14's
   bucket cut points and genre-affinity gate, P15's CF-feasibility and candidate-pool
   sizing. Read-only, so it cannot destabilize the app.
4. **P14 (feature store):** feature #3 — unlocks the DS work, fixes on-request-compute
   perf, enables the dual-loader collapse. Highest-leverage single phase. Its feature
   definitions should **quote P13.5's Decision-inputs cells** rather than pick thresholds
   by hand.
5. **P15 (models + eval + human loop):** features #4 and #5 in one phase — they share the
   `reco/` + `eval/` packages and the one page. The eval harness is the highest-value DS
   deliverable; do not cut it.
6. **P16 (loop + tests + CI + docs):** makes it a *system*, not a pile of scripts; CI is
   table stakes; the write-up ties DE + DS + human eval into one narrative.

## Effort roll-up

| Phase | Title | Effort | Feature |
|---|---|---|---|
| 9  | Repo hygiene & public-safe history | S | — |
| 10 | Local infra: Docker Compose + migration runner | M | — |
| 11 | Star schema + enrichment into Postgres + medallion | L | 1 (schema) |
| 12 | Dagster ingestion pipeline (incremental / idempotent / quarantine) | XL | 1 |
| 13 | DQ suite + Data Health page + cull to 3 pages | M | 2 |
| 13.5 | Behavioral EDA notebook set (decision-support reference) | M | — (feeds 3, 4, 5) |
| 14 | Feature store + nightly compute + dual-loader collapse | L | 3 |
| 15 | 4 recommenders + eval harness + explainable recs + human-eval loop | XL | 4 + 5 |
| 16 | Production loop + tests + CI + README/architecture/write-up | L | — |

Roughly half the work of the 13-phase version. Two XL phases instead of four; 3 pages
instead of 12.

## What was cut (and where it went)

| Cut | Disposition |
|---|---|
| Milestones, Sessions, Moods, Simulator, Comparison pages | deleted in Phase 13 (Sessions clustering logic kept as a chart on Insights; Simulator → "future work" paragraph in `RESEARCH_WRITEUP.md`) |
| ~~8-notebook behavioral-EDA set~~ | **UNCUT — now Phase 13.5** (see Decisions locked). `evaluation.ipynb` still ships separately in P15; 2–3 EDA charts still fold into `RESEARCH_WRITEUP.md`, now sourced from the notebooks rather than rebuilt |
| Explained-user-similarity page | cut; `user_similarity.py` still built and consumed by the hybrid recommender; the result is a **section in `RESEARCH_WRITEUP.md`**, no route |
| Prometheus `/metrics`, per-user auth tokens beyond a write-endpoint API key | cut; light structured logging + SLA fields on `/api/health/data` instead |
| dbt project | cut; plain SQL migrations; note as optional future lineage-docs |

## Cross-cutting "keep working" rules

- Never change a surviving RPC/MV name or signature without a compatibility shim.
- `DB_BACKEND=supabase` stays the default until Phase 16.
- Delete `data_loader.py` only at the end of Phase 14, only after
  `grep -r data_loader apps/api/app/routes` is empty.
- Every new model/metric ships with a unit test in Phase 15 or Phase 16.
- Each phase ends by refreshing MVs + smoke-testing the (shrinking) set of pages.

## Baseline facts (verified 2026-08-31)

- 10 users, ~340k `streaming_history` rows in Supabase. Per-user music-stream counts:
  primary 70,700; others 131 (Abhiraj) to 60,026 (Snehal), most 25k–60k.
- ONE wide table `streaming_history` + `users`; NOT a star schema.
- 3 per-user MVs; ~40 RPCs (migrations 002/004/005/006/007), all scoped by
  `_effective_user_id(p_user_id)`.
- Enrichment writes JSON/CSV to disk only. `artists_info.json` = 4,216 artists, 54% with
  genres. `songs_info.json` = truncated write, ~808 tracks salvageable.
  `lyrics.json` = 5,858 tracks.
- No feature tables, no DQ framework, no orchestration, no Docker, no tests, no CI.
- 16 standing TypeScript errors (most in pages that get deleted in Phase 13).
- `data/other users/*.zip` (9 friends' raw exports **with third-party IPs**) are
  git-tracked — publish blocker, `.git` is 53 MB.
- `spotify-insights.env` (real secrets) is NOT tracked — only `.example` files are. Fine.
