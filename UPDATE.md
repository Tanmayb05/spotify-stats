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
| 11 | Star schema + enrichment into Postgres + bronze/silver/gold | L | 1 (schema) | NOT STARTED | — | — |
| 12 | Dagster ingestion pipeline (incremental / idempotent / quarantine) | XL | 1 | NOT STARTED | — | — |
| 13 | DQ suite + Data Health page + cull to 3 pages | M | 2 | NOT STARTED | — | — |
| 13.5 | Behavioral EDA notebook set (decision-support reference) | M | — (feeds 3,4,5) | NOT STARTED | — | — |
| 14 | Feature store + nightly compute + dual-loader collapse | L | 3 | NOT STARTED | — | — |
| 15 | 4 recommenders + eval harness + explainable recs + human-eval loop | XL | 4 + 5 | NOT STARTED | — | — |
| 16 | Production loop + tests + CI + README/architecture/write-up | L | — | NOT STARTED | — | — |

**Next phase to start:** Phase 11.

---

## The 5 target features (for reference)

1. **Orchestrated ingestion pipeline** — Dagster asset graph raw→bronze→silver→star,
   incremental + idempotent, quarantine lane, ingestion metrics. *(Phases 11–12)*
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
