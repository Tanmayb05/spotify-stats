# Star Schema + Enrichment into Postgres + Medallion Layers — Phase 11 **PLAN**

**Date:** 2026-09-01 15:23:20
**Status:** PLAN ONLY — no implementation started
**Phase:** 11 (roadmap `documentation/20260901_013603_roadmap_trimmed_5features.md` §PHASE 11)
**Effort:** L
**Feature:** 1 (schema half) — orchestrated ingestion pipeline
**Branch to cut:** `feat/phase-11-star-schema` (off `feat/phase-10-local-infra` once merged, else off `main`)
**Estimated time:** 6–9 h

---

## Overview

Turn the single wide `streaming_history` table into a Medallion-layered star schema
(`bronze` / `silver` / `gold`), populate real dimension tables from the on-disk
enrichment JSON, and repoint the materialized views and hottest RPCs at
`gold.fact_streams` — **without changing a single function name, signature, or API
response**. The app must look byte-identical before and after.

This plan was written after reading the current schema (migrations `001`–`007`), the
backend adapter (`apps/api/app/db/backends.py`), the migration runner
(`apps/api/db/migrate.py`), the loader (`apps/api/app/services/supabase_data_loader.py`,
`data_loader.py`), and after **measuring the actual enrichment files**. Several roadmap
assumptions did not survive that measurement — see
[Reality check](#reality-check-measured-numbers-vs-the-roadmap) and
[Deviations](#planned-deviations-from-the-roadmap-spec). Those measurements change the
verify gates and one design decision, so they are recorded here rather than discovered
mid-implementation.

---

## Reality check: measured numbers vs. the roadmap

All measured on 2026-09-01 against the working tree (primary user's 6 export files +
`outputs/`).

| Quantity | Roadmap assumed | **Measured** | Consequence |
|---|---|---|---|
| `fact_streams` row count | "≈ 340k" | **71,052** (primary user, 6 files) | Verify gate must be rewritten. 340k is wrong for the primary user; ~340k is plausible only as the *all-10-users* total, which is not what the gate says. |
| `dim_track WHERE audio_source='enriched'` | "> 800" | **808 salvageable** of 13,837 distinct URIs | Gate is technically satisfiable but is **7.0 % coverage-of-plays** — see below. |
| `songs_info.json` | "~808 via `_salvage_json_array`" | **Confirmed 808.** File is a truncated write; `json.load` raises `JSONDecodeError` at char 45,059,249 | Salvage path is mandatory, not optional. |
| `artists_info.json` | "4,216 artists" | **Confirmed 4,216**; 2,284 have non-empty `genres` | Matches. |
| `lyrics.json` | "5,858" | **Confirmed 5,858 tracks** | Matches. Contains full lyrics text ⇒ PII/copyright handling required. |
| Spotify **audio features** (valence/energy/danceability) | implied available for `mood_proxy_*` | **ABSENT.** `track_info` keys are `album, artists, available_markets, disc_number, duration_ms, explicit, external_ids, external_urls, href, id, is_local, name, popularity, preview_url, track_number, type, uri` | **Design change.** No real audio features exist anywhere in this repo. See [Decision D1](#d1-mood_proxy_-columns-are-not-backed-by-real-audio-features). |
| Artist match-rate of plays | not stated | **93.7 %** | Healthy. Good `dim_artist` join. |
| Enriched-**track** coverage-of-plays | not stated | **7.0 %** | Track-level enrichment is near-useless for aggregate analytics. Affects Phase 15 content recommender. |
| **Genre coverage-of-plays** (the kill gate) | "record → keep or cut `user_genre_affinity`" | **53.1 %** *before* backfill | Sits right on the boundary. The MusicBrainz/Last.fm backfill is what decides this. See [Decision D2](#d2-the-genre-affinity-kill-gate). |

Cardinalities for sizing: 13,837 distinct `spotify_track_uri`, 4,342 distinct normalized
artist names, 139 rows with no `track_uri` (podcast/video/local rows).

---

## Blockers found in existing code (must be fixed as part of this phase)

These are not hypothetical; each is a concrete failure the phase will hit.

### B1 — `_check_identifier` rejects schema-qualified names

`apps/api/app/db/backends.py:39`

```python
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
```

`LocalBackend.select("gold.fact_streams", ...)` and `SupabaseBackend.select` both break on
a dotted name — the regex rejects it, and PostgREST does not accept `schema.table` in
`.table()` at all (it needs a per-request schema header).

The loader calls `select()` on exactly two tables: `users`
(`supabase_data_loader.py:67`, `:330`, `:386`) and `streaming_history` (`:91`, the
paginated raw-row fetch feeding the recommender / simulator / session clustering).

**Chosen fix:** do **not** qualify names in Python. Keep `select()` calls on bare names and
expose `gold.*` through **unqualified compatibility views in `public`**
(`public.streaming_history` stays readable). This keeps `backends.py` untouched, keeps the
PostgREST path working with no schema-header change, and keeps Supabase and local behaving
identically. Schema qualification lives only inside SQL function bodies, where it is safe.

### B2 — migration `002` is recorded-but-not-executed; `006` redefines from `streaming_history`

`apps/api/db/migrate.py:44` (`SUPERSEDED`). Any new migration that redefines a function
must follow the established `DROP FUNCTION IF EXISTS <name>(<exact signature>);` pattern
from `006` (line 41–53), or Postgres raises
`function ... is not unique` **at call time**, not at apply time. New migrations `008`–`010`
must repeat that discipline for every function they touch.

### B3 — `except`-and-return-empty hides everything

Every loader method swallows exceptions and returns `{}` / `[]` (documented at
`backends.py:21-22`). A wrong column name in a rewritten MV produces a **blank chart, not
an error**. This is why the verify step below compares *values*, not just HTTP 200s.

### B4 — `_mood_rows` is the single mood source and reads `streaming_history` directly

`migrations/006_analytics_functions.sql:59-115`. It derives valence/energy/danceability
arithmetically from `hour`, `is_weekend`, `ms_played`, `skipped` — reproducing
`data_loader._calculate_mood_metrics` exactly (documented at `006:21-30`). Three mood
functions plus the weekend/weekday comparison depend on it. Repointing it at
`gold.fact_streams` must preserve the arithmetic bit-for-bit or every mood number moves.

### B5 — `outputs/` is gitignored (Phase 10 follow-up)

`/api/reco` and `/api/simulate` read `outputs/data/{songs,artists}_info.json` via
`data_loader._load_track_metadata()` (`data_loader.py:1881-1932`), absent on a fresh clone.
Closing this is an explicit deliverable of this phase.

---

## Design decisions

### D1 — `mood_proxy_*` columns are not backed by real audio features

**No audio-features data exists in this repo.** The Spotify API's `/audio-features`
endpoint was deprecated for new apps in Nov 2024, and the cached `songs_info.json` payload
contains only track metadata (popularity, duration, explicit, album, ISRC).

Creating `dim_track.mood_proxy_valence/energy/danceability` as the roadmap specifies would
produce **three permanently-NULL columns**, and — worse — would imply to a reader that the
mood charts are audio-derived when they are arithmetic from hour-of-day and `ms_played`.

**Decision:** create the columns as specified (Phase 14/15 may fill them from another
source) but:
- add `audio_source` as an enum `('none','enriched','proxy_heuristic')` **defaulting to
  `'none'`**, and
- add a `COMMENT ON COLUMN` on each stating the values are unpopulated and that live mood
  numbers come from `_mood_rows`' heuristic, and
- state it plainly in `DATA_MODEL.md`.

`_mood_rows` keeps its current arithmetic. Nothing about the mood charts changes.
Recorded here so Phase 14 does not "discover" empty columns and quietly trust them.

### D2 — the genre-affinity kill gate

Measured **53.1 % genre coverage-of-plays** pre-backfill. The gate decides whether
`user_genre_affinity` (Phase 14 feature) survives.

**Threshold declared in advance, before running the backfill** (so the result cannot be
rationalized after the fact):

| Post-backfill coverage-of-plays | Decision |
|---|---|
| **≥ 75 %** | **KEEP** `user_genre_affinity` as a Phase 14 feature. |
| **60–75 %** | **KEEP, but degraded** — feature must carry a `coverage` field and the UI must show "based on N % of plays". |
| **< 60 %** | **CUT.** Record in `UPDATE.md` as a `> ROADMAP DEVIATION` against Phase 14; Phase 15's content recommender leans on artist/track identity, not genre. |

The measured number goes in `DATA_MODEL.md` under "genre-coverage decision" and in the
Phase 11 completion doc regardless of outcome.

### D3 — natural keys

- `dim_artist.artist_key` — `lower(trim(artist_name))`, matching
  `data_loader.py:1906`'s existing normalization exactly, so the on-disk enrichment joins
  without a second convention. `spotify_artist_id` is *not* the natural key: only 4,216 of
  4,342 artists have one.
- `dim_track.track_key` — `spotify_track_uri` when present; otherwise
  `'hash:' || md5(lower(trim(track_name)) || '|||' || lower(trim(artist_name)))`. Covers
  the 139 URI-less rows. This mirrors the recommender's existing `"name|||artist"` fallback
  (`data_loader.py:1937`) so the two agree.
- `dim_time` — grain `(date, hour)`, surrogate `time_key = date * 100 + hour`. Generated
  over the observed range, not a century of empty rows.
- `dim_user` — reuses existing `users.id` UUIDs verbatim. **No re-keying**;
  `_effective_user_id(p_user_id)` (`004:34`) keeps working unchanged.

### D4 — lyrics: metadata only, never text

`lyrics.json` (14 MB) contains full lyrics text for 5,858 tracks — third-party copyrighted
content, and Phase 9 spent an entire phase purging exactly this class of blob from history.
`gold.track_lyrics` stores **only** `(track_key, source, has_lyrics, lang, word_count)`.
The loader script reads the text to compute `word_count`/`lang` and discards it. No lyrics
column, no lyrics in any migration, no lyrics committed. The source file stays gitignored.

### D5 — backfill is offline and cached, never at request time

MusicBrainz asks for ≤ 1 req/s and a real User-Agent; Last.fm needs an API key. 4,342
artists ⇒ ~75 min at 1 req/s. Therefore:
- the backfill is a **separate opt-in script**, not part of `build_star_schema.py`;
- responses cache to gitignored `outputs/enrichment/artist_tags.json` so a re-run is free
  and the network is hit once;
- it is **fully skippable** (`--skip-backfill`) — the phase must complete with no network
  and no API key, just with lower genre coverage;
- rate limit 1 req/s, `User-Agent: spotify-insights/0.1 (github.com/<repo>)`, resumable,
  `--limit N` for a smoke run;
- no API key is committed; `LASTFM_API_KEY` read via `app/config.py`, documented in
  `.env.example`.

### D6 — `fact_streams` grain and the dedup question

Grain = one play event. Spotify exports legitimately contain byte-identical rows (same
`ts`, same track — genuine repeat plays are indistinguishable from export dupes).
**Phase 11 does not dedup**: it copies rows 1:1 so `fact_streams` count == source count and
every existing aggregate is reproducible. Dedup is Phase 12's `dedup.py`, which owns the
`row_fingerprint` + `ROW_NUMBER` collapse and the `dups_dropped` metric. Splitting it that
way keeps this phase's "numbers unchanged" verification meaningful.

Surrogate PK `fact_streams.stream_id BIGSERIAL`; the bronze `_ingest_id` is carried through
so Phase 12/13 can trace a fact row back to its landed row.

---

## Work plan

### Step 0 — branch + baseline capture *(~30 min)*

Baseline is what makes "numbers unchanged" checkable, so it comes first.

1. `git checkout -b feat/phase-11-star-schema`
2. `docker compose up -d` (ports **3010** web / **3011** api, per Phase 10), seed from the
   real export.
3. `apps/api/scripts/capture_api_baseline.py` — GET all 44 routes for the primary user +
   2 others, write canonical JSON to gitignored `outputs/baseline/pre_phase11/`.
   Floats rounded to 6 dp; key order sorted.
4. Record row counts: `streaming_history` per user, distinct artists, distinct tracks.

### Step 1 — `008_medallion_schemas.sql` *(~1 h)*

- `CREATE SCHEMA IF NOT EXISTS bronze; silver; gold;`
- `bronze.raw_streams` — append-only landing: all `streaming_history` columns plus
  `_ingest_id BIGSERIAL PK`, `_source_file TEXT`, `_ingested_at TIMESTAMPTZ DEFAULT now()`,
  `_raw JSONB`, `user_id UUID`. Seeded by `INSERT … SELECT` from `public.streaming_history`
  with `_source_file = 'phase11_backfill:streaming_history'` and `_raw` reconstructed via
  `to_jsonb(s)`.
- `silver.streams` — typed, normalized, FK-ready: `_ingest_id`, `user_id`, `ts` (UTC),
  `artist_key`, `track_key`, `album_name`, `ms_played`, `platform`, `conn_country`,
  `reason_start/end`, `shuffle`, `skipped`, `offline`, `incognito_mode`,
  `is_music BOOLEAN`. Normalization = `lower(trim())` on the key columns, matching D3.
  **No `ip_addr` column** — Phase 9 purged it; it must not be reintroduced into a new layer.
- Indexes: `silver.streams (user_id, ts DESC)`, `(user_id, artist_key)`,
  `(user_id, track_key)`.

Sizing note: bronze + silver + gold ≈ 3 copies of 71k rows (×10 users if all loaded). Well
within local Postgres; `_raw JSONB` is the bulk. Acceptable — bronze is the audit trail
that makes the pipeline defensible.

### Step 2 — `009_star_schema.sql` *(~1.5 h)*

`gold.dim_user`, `gold.dim_time`, `gold.dim_artist`, `gold.dim_track`, `gold.dim_album`,
`gold.fact_streams`, `gold.track_lyrics`, `gold.recommendation_events` (empty, for the
Phase 15 human-eval loop).

Per the roadmap's column lists, plus D1's `audio_source` enum + comments, plus D3's keys.
`fact_streams` measures: `ms_played`, `skipped`, `shuffle`, `offline`, `incognito_mode`,
`reason_start`, `reason_end`. FKs to all four dims; `NOT VALID` initially then `VALIDATE`
after load, so the bulk insert is not slowed by per-row checks.

Also in this migration: **compatibility views** (per B1) so nothing in Python needs a
dotted name.

### Step 3 — `apps/api/app/ingest/normalize.py` *(~45 min)*

Extract the normalization currently inline in `scripts/seed_local_db.py` (Phase 10's own
note assigns this file to Phase 11). Pure functions, no DB, no I/O:
`normalize_artist_key`, `normalize_track_key`, `to_utc`, `coerce_ms_played`,
`coerce_bool`, `row_fingerprint` (defined here, *used* by Phase 12).
Import it from `seed_local_db.py` so there is exactly one definition.
Unit tests: `apps/api/tests/test_normalize.py`.

### Step 4 — `apps/api/scripts/load_enrichment_to_db.py` *(~1.5 h)*

Idempotent upserts (`ON CONFLICT … DO UPDATE`), `--dry-run`, per-source counts.

- `artists_info.json` → `gold.dim_artist` (4,216) — uses `_salvage_json_array`, which moves
  out of `data_loader.py` into `app/ingest/salvage.py` so both the script and the loader
  share one implementation.
- `songs_info.json` → `gold.dim_track` (808) — sets `audio_source='enriched'`,
  `release_year` parsed from `album.release_date[:4]` exactly as `data_loader.py:1893-1896`.
- `lyrics.json` → `gold.track_lyrics` (5,858) — **metadata only** (D4).
- Missing file ⇒ warn and skip that source, exit 0. Fresh clone must not fail.

### Step 5 — `apps/api/scripts/backfill_artist_tags.py` *(~1.5 h, opt-in)*

Per D5. MusicBrainz first (no key), Last.fm if `LASTFM_API_KEY` set. Writes
`dim_artist.genres_enriched` / `tags`. **Prints coverage-of-plays before and after** — that
printed number is the D2 gate input.

### Step 6 — `apps/api/scripts/build_star_schema.py` *(~1.5 h)*

`public.streaming_history` → bronze → silver → dims → `fact_streams`, in one transaction,
re-runnable (`TRUNCATE … RESTART IDENTITY` on gold + silver, bronze append-only-guarded).
Logs at each stage: rows in/out, **track match-rate, artist match-rate**, unmatched counts.
Unmatched rows **still produce a fact row** with NULL enrichment FKs (never silently
dropped — that is what would move the numbers).

### Step 7 — `010_mvs_on_star.sql` *(~2 h — the risky one)*

Rewrite `monthly_stats`, `top_artists`, `top_tracks` and the hot RPCs to read
`gold.fact_streams` + dims. **Names and signatures identical**; every function preceded by
its exact `DROP FUNCTION IF EXISTS` (B2).

`_mood_rows` gets special care (B4): same arithmetic, same `ISODOW >= 6` weekend rule, same
clamps, only the `FROM` changes. Verified by comparing mood endpoints value-for-value
against baseline.

Scope control: rewrite the **3 MVs + the ~8 hottest RPCs** only. `006`'s long tail
(`get_milestones_list`, `get_flashback`, …) keeps reading `public.streaming_history`, which
still exists and is still populated. Repointing all 30+ functions is high-risk, low-value
churn; Phase 12 moves the remainder once the pipeline owns the write path. **This is a
deliberate, recorded partial** — noted in `UPDATE.md` and `DATA_MODEL.md`.

### Step 8 — close the `outputs/` dependency (B5) *(~1 h)*

Point `_load_track_metadata()` at `gold.dim_track` / `gold.dim_artist` when
`DB_BACKEND=local`, falling back to the files when the tables are empty. `/api/reco` and
`/api/simulate` then work on a fresh clone with zero `outputs/`.

### Step 9 — docs *(~1 h)*

- `documentation/DATA_MODEL.md` — ER diagram (mermaid), medallion flow, natural-key
  rationale, **the genre-coverage number and the D2 verdict**, the D1 caveat, the Step-7
  partial-rewrite scope.
- `documentation/database_schema_diagram.md` — updated to reality (currently pre-star).
- `UPDATE.md` — row → `DONE`, log entry, next phase → 12.
- `documentation/YYYYMMDD_HHMMSS_phase_11_star_schema.md` per the CLAUDE.md schema.

---

## Verify gates (rewritten from measured reality)

Roadmap gates 1 and 2 are replaced; the reasons are in
[Reality check](#reality-check-measured-numbers-vs-the-roadmap).

| # | Gate | Pass condition |
|---|---|---|
| V1 | Fact completeness | `SELECT count(*) FROM gold.fact_streams` **== `count(*) FROM public.streaming_history`, exactly**, per user. (Replaces "≈ 340k" — measured primary-user truth is **71,052**.) An equality against the source is a stronger gate than a remembered constant. |
| V2 | Track enrichment | `count(*) FROM gold.dim_track WHERE audio_source='enriched'` **== 808**, and coverage-of-plays **recorded** (measured 7.0 %). Exact count, not `> 800`. |
| V3 | Artist enrichment | `dim_artist` ≥ 4,216 rows; artist match-rate of plays **≥ 93 %** (measured 93.7 %). |
| V4 | **Numbers unchanged** | `scripts/compare_api_baseline.py` diffs all 44 routes post-migration vs. `pre_phase11/` baseline. **Zero value differences.** This is the gate that catches B3. |
| V5 | Genre gate (D2) | Post-backfill coverage-of-plays recorded; keep/cut verdict written into `DATA_MODEL.md` + `UPDATE.md`. |
| V6 | No ambiguous overloads | Zero rows from the `pg_proc` duplicate-signature query used in Phase 10. |
| V7 | Migration replay | `python db/migrate.py` twice ⇒ second run a no-op; `docker compose down -v && up --build` from scratch ⇒ api healthy, 44/44 routes 200. |
| V8 | Backend parity | `scripts/check_backend_parity.py` — all 34 methods still agree across `supabase` and `local`. |
| V9 | Fresh-clone integrity | No `outputs/`, no `data/`: stack boots, seeds from fixture, `/api/reco` + `/api/simulate` return non-empty (B5 closed). |
| V10 | No PII regression | No `ip_addr` in any new schema; no lyrics text in any table or migration; `git ls-files` clean. |

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A rewritten MV/RPC silently changes a number (B3) | **High** | **High** | V4 baseline diff is non-negotiable and gates the commit. |
| Dotted table names break `select()` (B1) | Certain if unhandled | High | Compatibility views; no Python change. |
| Ambiguous function overloads (B2) | Medium | High — fails at call time | Explicit `DROP FUNCTION` per signature; V6. |
| `_mood_rows` arithmetic drift (B4) | Medium | Medium | Only `FROM` changes; V4 covers mood endpoints. |
| MusicBrainz rate-limit / no key | Medium | Low | D5: opt-in, cached, skippable; phase completes without it. |
| Genre coverage lands < 60 % | **Realistic** (53.1 % now) | Medium | D2 threshold pre-declared; cutting is a legitimate, recorded outcome. |
| Bronze `_raw` JSONB bloat | Low | Low | 71k rows/user; measure and record. |
| Scope creep into rewriting all 30+ RPCs | Medium | Medium | Step 7 caps scope explicitly; remainder is Phase 12. |

---

## Files

**Created**
```
apps/api/migrations/008_medallion_schemas.sql
apps/api/migrations/009_star_schema.sql
apps/api/migrations/010_mvs_on_star.sql
apps/api/app/ingest/__init__.py
apps/api/app/ingest/normalize.py
apps/api/app/ingest/salvage.py
apps/api/scripts/load_enrichment_to_db.py
apps/api/scripts/backfill_artist_tags.py
apps/api/scripts/build_star_schema.py
apps/api/scripts/capture_api_baseline.py
apps/api/scripts/compare_api_baseline.py
apps/api/tests/test_normalize.py
documentation/DATA_MODEL.md
documentation/20260901_HHMMSS_phase_11_star_schema.md
```

**Modified**
```
apps/api/app/services/supabase_data_loader.py   # dim-backed reco/sim metadata (B5)
apps/api/app/services/data_loader.py            # _salvage_json_array -> app/ingest/salvage.py
apps/api/scripts/seed_local_db.py               # import shared normalize.py
apps/api/app/config.py                          # LASTFM_API_KEY
apps/api/.env.example                           # LASTFM_API_KEY
documentation/database_schema_diagram.md
UPDATE.md
```

**Deliberately unmodified:** `apps/api/app/db/backends.py` (B1 solved with views),
`migrations/001`–`007` (history), all `apps/web` (no API shape change ⇒ no frontend work
in this phase).

---

## Planned deviations from the roadmap spec

To be copied into `UPDATE.md` as `> ROADMAP DEVIATION` notes on completion.

1. **Verify gate "≈ 340k" replaced** with an exact source-equality check. Measured
   primary-user total is **71,052**; 340k is not reachable for one user.
2. **`mood_proxy_*` columns ship empty** — no audio-features data exists in this repo and
   the Spotify endpoint is deprecated (D1). Columns + comments created; population deferred.
3. **Only the 3 MVs + ~8 hottest RPCs are repointed** at `gold` (Step 7); `006`'s long tail
   keeps reading `public.streaming_history`. Phase 12 finishes the move.
4. **Dedup deferred to Phase 12** (D6) — required for this phase's "numbers unchanged" gate
   to mean anything.
5. **Artist-tag backfill is opt-in and skippable** (D5), not an inline pipeline step.
6. **`_salvage_json_array` relocates** to `app/ingest/salvage.py` (shared by script +
   loader) rather than being duplicated.

---

## Next steps after this phase

Phase 12 (Dagster ingestion, **XL**) consumes directly: `bronze.raw_streams` +
`_source_file`/`_ingested_at` are its landing target, `normalize.py` and `row_fingerprint`
are written here, and `build_star_schema.py`'s stages map 1:1 onto the planned Dagster
assets.

---

## Conclusion

The phase is well-specified and executable, but three measured facts change it before any
code is written: the fact-count gate is wrong by ~5×, track-level enrichment covers only
7 % of plays, and no audio-features data exists to back the `mood_proxy_*` columns. Genre
coverage at 53.1 % means the `user_genre_affinity` kill gate is a live question, not a
formality — which is why the threshold is declared here, ahead of the backfill. The main
execution risk is silent numeric drift through B3's swallow-and-return-empty pattern, so
the pre/post API baseline diff (V4) is the gate that actually protects the app.
