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
| 10 | Local infra: Docker Compose + migration runner + DB backend switch | M | — | NOT STARTED | — | — |
| 11 | Star schema + enrichment into Postgres + bronze/silver/gold | L | 1 (schema) | NOT STARTED | — | — |
| 12 | Dagster ingestion pipeline (incremental / idempotent / quarantine) | XL | 1 | NOT STARTED | — | — |
| 13 | DQ suite + Data Health page + cull to 3 pages | M | 2 | NOT STARTED | — | — |
| 14 | Feature store + nightly compute + dual-loader collapse | L | 3 | NOT STARTED | — | — |
| 15 | 4 recommenders + eval harness + explainable recs + human-eval loop | XL | 4 + 5 | NOT STARTED | — | — |
| 16 | Production loop + tests + CI + README/architecture/write-up | L | — | NOT STARTED | — | — |

**Next phase to start:** Phase 10.

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
