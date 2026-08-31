# Full Multi-User Switch — Phase 8
**Date:** 2026-08-30 23:25:45
**Status:** Completed
**Time to complete:** ~1h 30m

## Overview
All 7 remaining analytics pages (Overview, Discovery, Milestones, Sessions,
Listening Patterns, Recommendations, Simulator) were moved off the primary-user-only
in-memory JSON `SpotifyDataLoader` and onto the DB-backed `SupabaseDataLoader`, which
now serves any of the 10 users. A global user-switcher in the AppBar drives which
user's data every page shows; the selection persists across reloads. The Comparison
dashboard was already multi-user and is unchanged.

The 19 `# TODO` stubs in `supabase_data_loader.py` are all implemented:
- **13 SQL-friendly** (mood / discovery / loyalty / obsessions / reflect /
  weekend-weekday / repeated-tracks / diversity / heatmap / milestones / flashback)
  as user-scoped Postgres functions in **migration 006**, following the
  `_effective_user_id(p_user_id)` + `p_user_id UUID DEFAULT NULL` convention from 004.
- **The heavy compute** (session KMeans clustering, the sklearn content-based
  recommender, the Markov simulator) runs in Python via a per-user
  `SpotifyDataLoader` delegate whose `_data` is a paginated PostgREST fetch of that
  user's `streaming_history` rows — so the numpy/sklearn logic and the return shapes
  are shared verbatim with the JSON loader.

## Files Created
- apps/api/migrations/006_analytics_functions.sql — 14 user-scoped RPCs
  (`_mood_rows` helper + 13 analytics functions)
- apps/api/scripts/verify_parity.py — throwaway JSON-vs-Supabase parity harness
  (not part of the app)
- apps/web/src/components/UserSwitcher.tsx — AppBar user dropdown
- documentation/20260830_230358_phase_8_full_multiuser_switch_PLAN.md — the approved plan

## Files Modified
- apps/api/app/services/supabase_data_loader.py — imports `SpotifyDataLoader`; adds
  `_resolve_user_id`, `_user_rows`, `_delegate`; all 19 stubs implemented; every
  ported method takes `user_id: Optional[str] = None`
- apps/api/app/routes/stats.py, mood.py, discovery.py, milestones.py, sessions.py,
  patterns.py, reco.py, sim.py — import `supabase_data`; every handler (incl. CSV
  exports) gains `user_id: str | None = Query(None)`, threaded through; the dead
  `spotify_data.load_data()` calls removed
- apps/web/src/store/app.ts — `persist` middleware; `selectedUserId` + `setSelectedUserId`
  (only that key persisted, via `partialize`)
- apps/web/src/layout/AppLayout.tsx — `<UserSwitcher />` mounted in the AppBar
- apps/web/src/api/client.ts — `withUser()` / `qs()` helpers read
  `useAppStore.getState().selectedUserId` and add `user_id` to every analytics call
  and the 5 CSV-export URL builders; `/api/compare/*` left alone
- apps/web/src/pages/Overview.tsx, Discovery.tsx, Milestones.tsx, Sessions.tsx,
  ListeningPatterns.tsx, Recommendations.tsx, Simulator.tsx — read `selectedUserId`
  from the store and add it to the data-loading `useEffect` deps so a user switch
  refetches

## Checklist
- [x] Intuitive navigation — one dropdown in the AppBar, always visible
- [x] Consistent design — MUI `Select`, "You" label for the primary user (matches Comparison)
- [x] Responsive layout — switcher sits in the existing AppBar fl*ex row; build unaffected
- [x] A11y — `aria-label="select user"`, labelled `FormControl`, `Skeleton` while loading
- [x] Error handling & feedback — per-page `setError` paths unchanged; switcher fails closed (renders nothing on error)
- [x] Performance — SQL RPCs are single-pass over `idx_streaming_user_*`; heavy per-user artefacts cached per process; `get_artist_loyalty` fixed from 8.2s → 95ms
- [x] Security baseline — no secrets touched; env walk-up loader left intact; `user_id` is an opaque UUID validated by FK on use
- [x] Docs generated — this file

## What Was Implemented
### Purpose
Let the app show every user's personal analytics, not just the primary user's, now
that the Supabase schema holds 10 users' histories (~340k rows).

### Features
- **Migration 006** — 13 analytics RPCs, each `WHERE user_id = _effective_user_id(p_user_id)`
  so `user_id=NULL` still resolves to the primary user and old single-user callers keep
  working. Mood metrics reproduce `_calculate_mood_metrics` exactly in SQL
  (hour/weekend valence+energy bands, `ms_played` + `skipped` danceability bands).
  `jsonb`-returning functions for the nested shapes (`get_mood_contexts`,
  `get_reflective_insights`, `get_weekend_weekday_comparison`, `get_flashback`).
- **`_user_rows` + `_delegate`** — one paginated fetch of a user's rows (same key names
  as the JSON export, `ts` as an ISO string), fed into a fresh `SpotifyDataLoader`
  with `_loaded = True` so its JSON glob is skipped. Session/reco/sim methods just call
  the delegate.
- **User switcher** — `api.getCompareUsers()` populates the dropdown; picking the
  primary user stores `null` so primary requests carry no `user_id`.
- **`withUser()`** — central helper so no call site has to know about the store.

### Implementation
`SupabaseDataLoader.__init__` gains `_primary_user_id` and `_delegate_by_user`.
Route handlers pass `user_id=user_id` straight through. The frontend store uses
`zustand/middleware` `persist` with `name: 'spotify-insights-user'` and `partialize`
so only `selectedUserId` is written to `localStorage`.

### Flow
1. User picks a name in the AppBar → `setSelectedUserId(id)` (or `null` for the primary).
2. Every page's load `useEffect` depends on `selectedUserId` → refetches.
3. `client.ts` `withUser()` appends `?user_id=<uuid>` (omitted for the primary).
4. FastAPI handler forwards `user_id` to `supabase_data.*`.
5. SQL-friendly method → RPC scoped by `_effective_user_id`; heavy method → per-user
   `SpotifyDataLoader` delegate over `_user_rows`.

### Usage
- Run migrations: `psql "postgresql://postgres:$SUPABASE_DATABASE_PASSWORD@db.daebjkkkjkyejfmxnahw.supabase.co:5432/postgres?sslmode=require" -v ON_ERROR_STOP=1 -f apps/api/migrations/006_analytics_functions.sql`
- Backend: `./start.sh` (uvicorn from `apps/api`) — the env walk-up finder is unchanged.
- Frontend: `npm run build` in `apps/web` passes; `npm run dev` then switch users in the AppBar.

## Verification (all run 2026-08-31)
### Backend
- **Migration applied** to the Supabase direct host; all 14 functions created; re-apply
  is idempotent (`CREATE OR REPLACE` + `DROP FUNCTION IF EXISTS` first).
- **Parity (primary user, JSON loader vs Supabase loader):** 21 exact matches. Known,
  accepted divergences:
  - 8 endpoints (`overview`, `top_tracks`, `monthly`, `platforms`, `hourly`, `daily`,
    `yearly`, `streaks`) differ by exactly the primary user's **117 podcast/audiobook
    rows** (~0.16%). The 004 RPCs and the 003 materialized views filter
    `spotify_track_uri IS NOT NULL`; the JSON loader counts every row. Decision: keep
    the music-only DB numbers (the Comparison dashboard already shipped on this basis).
  - `get_discovery_timeline` / `get_milestones_list` (first-artist ordering): JSON
    records first-seen in iteration order, SQL uses `MIN(ts)` — SQL is the
    chronologically-correct answer; per-month counts match.
  - `get_artist_loyalty` (`3` vs `3.0`) and `get_most_repeated_tracks` (tie-break order
    among equal scores) — cosmetic only; identical values and score ranking.
- **All 10 users × 23 light endpoints + 3 users × 9 heavy endpoints — all respond.**
  Every user's `/api/stats/overview` `total_streams` matches that user's
  `/api/compare/leaderboard` row exactly (You 70700, Abhiraj 131, Amit 30979,
  Antara 38641, Ash 25486, Nihal 44575, Prathamesh 12895, Sam 48594, Snehal 60026,
  Sohan 6312). Small users (Abhiraj/Sohan) get the `<10 sessions` alternate cluster shape.
- **`get_artist_loyalty` performance:** the original CTE had a cartesian `plays` join
  (3.6M rows, 8.2s, PostgREST statement-timeout). Rewritten to a single windowed
  subquery over the candidate artists → 95ms.

### Frontend (headless Chrome over CDP against `vite` on :3010, API on :3011)
- **Build:** `npm run build` (`vite build`) passes. `npm run build:check` (`tsc -b`)
  still reports the same **18 pre-existing** type errors on a clean tree (Moods Grid
  props, Overview/Sessions legend `hidden`, `ErrorBanner` props, unused imports) — this
  change introduces **zero new** type errors.
- **Switcher mounts** in the AppBar; picking "Abhiraj" updates its label to "Abhiraj".
- **`user_id` threading:** after the switch, every call on Overview (9/9) and Discovery
  (4/4) carries `?user_id=fb3d…`; on the primary user no call carries `user_id`.
  Switching back to "You" drops the param again.
- **Per-page refetch:** navigating between the 7 pages after a switch re-fires each
  page's calls with the param. On first load (primary) all 7 pages fire their expected
  endpoint sets and no console exception is thrown. (Dev StrictMode double-fires each
  effect — cosmetic, absent in the production build.)
- **`localStorage` persist:** key `spotify-insights-user` holds
  `{"state":{"selectedUserId":null}}` for the primary and
  `{"state":{"selectedUserId":"fb3d…"}}` after the switch; the value **and** the
  switcher label survive a full page reload; selecting "You" resets it to `null`.
- **CSV exports:** the 5 export-URL builders (`exportTopArtists/TopTracks/MonthlySummary
  /Recommendations/Simulation`) emit **no** `user_id` for the primary and
  `user_id=fb3d…` for a selected friend. A live fetch of
  `/api/export/top-artists?limit=5&user_id=<abhiraj>` returns HTTP 200, `text/csv`,
  with abhiraj's artists (The Weeknd, Travis Scott…), not the primary user's.

## Next Steps
- Fix the 18 pre-existing `tsc` errors so `build:check` can gate CI.
- Consider a 007 to align `get_reflective_insights` (`COUNT(*)`, counts podcasts) with
  the other overview RPCs, or vice-versa, so "total streams" is one number everywhere.
- Warm the per-user `_delegate` cache lazily in the background for the friend list, so
  the first Sessions/Reco/Simulator hit for a heavy user isn't a ~10s wait.
- Surface the active user in each page header (not just the AppBar) for shareable screenshots.

## Conclusion
The JSON loader is off every request path; all 7 pages plus their CSV exports are
user-scoped and driven by one persistent AppBar switcher. Backend parity for the
primary user is exact apart from a deliberate 0.16% music-only difference and two
cosmetic diffs; non-primary users resolve correctly end to end. `npm run build` passes
with no new type errors.
