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
| 9  | Repo hygiene & public-safe history | S | — | NOT STARTED | — | — |
| 10 | Local infra: Docker Compose + migration runner + DB backend switch | M | — | NOT STARTED | — | — |
| 11 | Star schema + enrichment into Postgres + bronze/silver/gold | L | 1 (schema) | NOT STARTED | — | — |
| 12 | Dagster ingestion pipeline (incremental / idempotent / quarantine) | XL | 1 | NOT STARTED | — | — |
| 13 | DQ suite + Data Health page + cull to 3 pages | M | 2 | NOT STARTED | — | — |
| 14 | Feature store + nightly compute + dual-loader collapse | L | 3 | NOT STARTED | — | — |
| 15 | 4 recommenders + eval harness + explainable recs + human-eval loop | XL | 4 + 5 | NOT STARTED | — | — |
| 16 | Production loop + tests + CI + README/architecture/write-up | L | — | NOT STARTED | — | — |

**Next phase to start:** Phase 9.

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

_(newest entries at the bottom; nothing yet — Phase 9 not started)_
