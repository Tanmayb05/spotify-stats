# Friend-Group Comparison Dashboard

**Date:** 2026-08-30 07:16:38
**Status:** Completed
**Time to complete:** ~35m

## Overview

Adds a **Comparison** page that stacks the primary user's listening against the 9
imported friends (multi-user Supabase data from
`20260830_070152_multi_user_data_load.md`). Implemented as an **add-on**: a new
`/api/compare/*` route group backed by `SupabaseDataLoader`, a new page with a
multi-select user chip row, and 4 panels. The 7 existing pages and the JSON
`SpotifyDataLoader` they run on are untouched.

## Files Created

- `apps/api/migrations/005_compare_functions.sql` — `get_user_leaderboard()` RPC
- `apps/api/app/routes/compare.py` — `/api/compare/*` endpoints
- `apps/web/src/pages/Comparison.tsx` — the dashboard page
- `documentation/20260830_071638_friend_comparison_dashboard.md`

## Files Modified

- `apps/api/app/services/supabase_data_loader.py` — env now loaded by absolute path
  (walks up from the module, so it works when `start.sh` launches uvicorn from
  `apps/api`); added compare methods: `list_users`, `get_leaderboard`,
  `_artist_vector` (+ per-process cache), `_jaccard`, `get_overlap`,
  `get_similarity_matrix`, `get_top_artists_multi`.
- `apps/api/app/main.py` — import + register `compare.router`.
- `apps/web/src/types/api.ts` — `CompareUser`, `LeaderboardRow`, `OverlapPair`,
  `SharedArtist`, `OverlapResult`, `SimilarityMatrix`, `TopArtistsMulti`.
- `apps/web/src/api/client.ts` — `getCompareUsers`, `getLeaderboard`, `getOverlap`,
  `getSimilarityMatrix`, `getTopArtistsMulti`.
- `apps/web/src/App.tsx` — `/comparison` route.
- `apps/web/src/layout/AppLayout.tsx` — "Comparison" nav item (`Groups` icon).

## Checklist

- [x] Intuitive navigation — new left-drawer item, route highlights
- [x] Consistent design — CLAUDE.md chart spec (Paper `p:5`, hover shadow, brand colors, `Skeleton`)
- [x] Responsive layout — `Grid size={12}` panels, `overflowX: 'auto'` on charts + matrix
- [x] A11y — chips keyboard-toggle, `DataTable` `aria-label`, matrix is a real `<table>`
- [x] Error handling — all fetches route to `useAppStore().setError` → existing `ErrorBanner`
- [x] Performance — heavy cross-user math in Python off the per-user materialized view + per-process cache; only 1 grouped SQL aggregate
- [x] Security — read-only; no PII surfaced (only display names + aggregate counts); `ip_addr` was already dropped at load
- [x] Docs generated

## What Was Implemented

### Purpose

Answer "who listens most / whose taste is closest to mine / what do we share" for
the friend group, using the multi-user DB that previously had no consumer.

### Features

**API — `/api/compare/*`:**

| endpoint | returns |
|---|---|
| `GET /users` | 10 users, `is_primary` flagged, primary first |
| `GET /leaderboard` | per-user streams, hours, unique artists/tracks, skip %, date range |
| `GET /overlap?users=a,b[,c…]&top_n=25` | pairwise `shared / only_a / only_b / jaccard`, plus artists shared by *all* selected users |
| `GET /similarity-matrix` | 10×10 pairwise artist-Jaccard %, diagonal `null` |
| `GET /top-artists?users=a[,b…]&limit=10` | each user's top-N artists, keyed by display name |

`users` = comma-separated `user_id`s; validated against known users (400 if not
2–6, 404 on unknown id). `top-artists` allows 1–6.

**Page — 4 panels + chip selector:**

1. **Leaderboard** — horizontal bar of total streams (all 10) + a `DataTable`
   (reused `components/DataTable.tsx`) with the rest. Not gated by chip selection.
2. **Shared-artist overlap** — pairwise similarity table for the selected users +
   a "shared by all N" artist list. Needs ≥2 chips.
3. **Taste-similarity matrix** — HTML-table heatmap, cell background
   `alpha('#2dd881', value / max)`. Always the full 10×10.
4. **Top artists side by side** — one horizontal bar chart per selected user in a
   responsive 2-col grid.

Chip row: one `Chip` per user ("You" for primary), toggles a `selected: string[]`
(min 1, max 6). Default selection = primary + top-2 friends by streams.

### Implementation

Cross-user Jaccard and an N×N matrix as SQL would blow the PostgREST statement
timeout (as `refresh_all_views` did during the data load). So only the leaderboard
is SQL — one `GROUP BY user_id` over `streaming_history` (10 groups). Everything
else is computed in `SupabaseDataLoader` from the per-user `top_artists`
materialized view (built in migration `003`, indexed on `(user_id, stream_count)`),
which holds *every* artist per user. `_artist_vector` pages through the view
(1000/req) and caches `{artist: count}` per user for the process lifetime;
`get_overlap` / `get_similarity_matrix` / `get_top_artists_multi` are set math over
those dicts.

Env-loading bug found and fixed: `supabase_data_loader.py` called
`load_dotenv('spotify-insights.env')` with a relative path — fine from the repo
root (how the load scripts run) but `start.sh` starts uvicorn from `apps/api`, so
the module raised "Missing Supabase credentials" on import and took the whole API
down. Now it searches upward for the file.

### Flow

```
psql -f 005_compare_functions.sql          # get_user_leaderboard()
uvicorn app.main:app                        # registers /api/compare/*
GET /comparison (web)
  -> getCompareUsers + getLeaderboard + getSimilarityMatrix   (on mount)
  -> getOverlap(selected) + getTopArtistsMulti(selected)      (on chip change)
```

### Usage

- `./start.sh`, open `http://localhost:3010/comparison`.
- Toggle chips to change the overlap + top-artist panels; leaderboard and matrix
  always show all 10.
- API is browsable at `http://localhost:3011/docs` under the "comparison" tag.

## Verification Results

| check | result |
|---|---|
| `get_user_leaderboard()` (psql) | 10 rows; tanmay 70,700 / snehal 60,026 / sam 48,594 …; skip% and date ranges match `20260830_062639_other_users_data_scan.md` |
| `GET /api/compare/users` | 10, `tanmay` `is_primary:true`, listed first |
| `GET /api/compare/overlap?users=tanmay,amit` | `jaccard: 22.9`, `shared: 1487` — matches scan doc |
| `GET /api/compare/overlap` 3 users | pairwise (22.9 / 18.9 / 18.6) + `shared_by_all_count: 708` |
| overlap with 1 user | HTTP 400; unknown id → HTTP 404 |
| `GET /api/compare/similarity-matrix` | 10×10, diagonal `null`; me↔amit 22.9, antara↔prathamesh 27.3, full "me" row identical to scan doc |
| `GET /api/compare/top-artists?users=snehal` | EXO / BTS / SEVENTEEN |
| `GET /api/stats/overview` (regression) | still 70,817 streams (JSON loader, unchanged) |
| `/api/top/artists`, `/api/time/monthly`, `/api/discovery/reflect`, `/api/patterns/*`, `/api/reco`, `/api/simulate/artists` | all HTTP 200 |
| `npm run build` (web) | passes — tsc + vite, no type errors |

## Next Steps

- Optional: cache the similarity matrix in a small table refreshed with the load
  script, instead of computing on every request (fine at 10 users, matters at 50+).
- "Full switch" — repoint the 7 existing pages to Supabase with a global
  user-switcher (needs the ~25 stubbed `supabase_data_loader` methods implemented
  as user-scoped SQL first).
- Collaborative recommender: use the friends' `top_artists` vectors + the
  similarity matrix to recommend artists the primary user hasn't played.
- Purge `data/other users/*.zip` (third-party IPs) from git history.

## Conclusion

The multi-user database now has a real consumer. The comparison feature ships as a
self-contained add-on — new route group, new page, one new SQL function — with the
existing single-user app fully intact and every metric cross-checked against the
earlier data scan.
