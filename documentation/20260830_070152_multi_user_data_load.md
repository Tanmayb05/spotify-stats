# Multi-User Data Load — Migration + Import of 9 Other Users

**Date:** 2026-08-30 07:01:52
**Status:** Completed
**Time to complete:** ~40m

## Overview

The database was single-user: `streaming_history` had no owner column and every
materialized view / RPC aggregated the whole table. This change implements the
multi-user schema from `documentation/multi_user_data_storage_design.md`, backfills
the existing 70,817 rows to a primary user (`tanmay`), and loads the 9 friends'
Spotify Extended Streaming History exports (previously extracted — see
`20260830_062639_other_users_data_scan.md`) into it.

`ip_addr` is dropped for all imported rows (third-party PII); `conn_country` is kept.
The existing single-user API is untouched — the new SQL functions fall back to the
primary user when no `user_id` is supplied.

## Files Created

- `apps/api/migrations/003_add_multi_user_support.sql`
- `apps/api/migrations/004_user_scoped_functions.sql`
- `apps/api/scripts/load_multi_user_data.py`
- `documentation/20260830_070152_multi_user_data_load.md`

## Files Modified

- `apps/api/app/services/supabase_data_loader.py` — added optional `user_id` kwarg
  to the 10 RPC-backed query methods (via `_uid()` helper); default `None` → primary
  user, so no caller change required.
- `apps/api/scripts/README.md` — documented `load_multi_user_data.py`.

## Checklist

- [x] `users` table + `user_id` FK on `streaming_history` (migration `003`)
- [x] Existing 70,817 rows backfilled to primary user; `user_id` set `NOT NULL`
- [x] Composite `(user_id, …)` indexes; 3 materialized views rebuilt per-user
- [x] All `002` helper functions replaced with user-scoped versions (`004`), old
      signatures dropped to avoid overload ambiguity
- [x] All 9 users loaded (339,674 total rows), counts match the scan doc
- [x] `ip_addr` NULL for every imported row; `conn_country` retained (13 countries)
- [x] Primary-user API responses unchanged (verified via RPC + service layer)
- [x] Materialized views refreshed and scoped per user
- [x] Docs generated

## What Was Implemented

### Purpose

Store multiple people's listening histories in one database without cross-
contamination, as the foundation for friend-group comparison and collaborative
recommendation work.

### Features

- `users(id, username, display_name, is_primary, created_at)` with a partial unique
  index enforcing a single primary user.
- `streaming_history.user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`.
- Per-user composite indexes: `(user_id, ts DESC)`, `(user_id, artist)`,
  `(user_id, track_uri)`, `(user_id, platform)`, `(user_id, artist, ts DESC)`, plus
  a user-scoped music-only partial index.
- `monthly_stats`, `top_artists`, `top_tracks` rebuilt with a leading `user_id`
  column, `GROUP BY user_id, …`, `PARTITION BY user_id` windows, and `user_id`-first
  unique indexes (for `REFRESH … CONCURRENTLY`).
- Every query RPC gains `p_user_id UUID DEFAULT NULL`; `_effective_user_id()`
  resolves it to the primary user when NULL. `truncate_streaming_history(p_user_id)`
  does a per-user `DELETE` when an id is passed.
- `load_multi_user_data.py`: reads `data/other users/<slug>/Streaming_History_Audio*.json`,
  creates a non-primary `users` row per slug, strips `ip_addr`, batch-inserts
  (1000/batch), skips already-loaded users unless `--reload`. Flags: `--only`,
  `--dry-run`, `--reload`.

### Implementation

Migrations applied with the local `psql` 14 client against the Supabase direct host
`db.<ref>.supabase.co:5432` (the pooler rejected the tenant string; direct worked).
`003` runs as one `BEGIN…COMMIT` transaction (non-`CONCURRENT` index builds, fine at
this scale) followed by three plain `REFRESH MATERIALIZED VIEW`.

Two issues hit and fixed during execution:

1. **Unique dedup index failed** — real exports contain exact-duplicate rows
   (`user_id, ts, spotify_track_uri, ms_played` collision, e.g. a track logged twice
   in the same second with `ms_played = 0`). Replaced the `UNIQUE` dedup index with
   a plain lookup index; idempotency is handled by the loader (skip-if-loaded /
   `--reload` delete), not an upsert conflict target.
2. **RPC overload ambiguity** — `CREATE OR REPLACE` of `get_overview_stats(uuid …)`
   left `002`'s zero-arg `get_overview_stats()` in place, so `supabase-py`'s
   no-arg `.rpc()` call became "function is not unique". Added explicit
   `DROP FUNCTION` of every pre-multi-user signature at the top of `004`.

The loader's final `refresh_all_views()` RPC hit the PostgREST statement timeout
(rebuilding 3 views over 340k rows > ~8s); the refresh was completed via `psql`
instead, and the script now catches that error and prints the `psql` fallback.

### Flow

```
psql -f 003_add_multi_user_support.sql     # users table, user_id FK, backfill 70,817,
                                           # per-user indexes, rebuild 3 views
psql -f 004_user_scoped_functions.sql      # drop old fn signatures, create user-scoped fns
python load_multi_user_data.py             # 9 users -> streaming_history (ip_addr dropped)
psql -c "SELECT refresh_all_views();"      # refresh views (RPC timed out at this scale)
```

Runtime query path is unchanged: route → `supabase_data.get_*()` → `rpc('get_*')`
with no `p_user_id` → SQL falls back to primary user.

### Usage

- Existing pages/endpoints: no change, still show the primary user.
- Query another user from Python:
  `supabase_data.get_top_artists(10, user_id="<uuid>")`.
- Query another user in SQL: `SELECT * FROM get_overview_stats('<uuid>');`
- Reload one user: `python apps/api/scripts/load_multi_user_data.py --reload --only sam`

## Verification Results

| check | result |
|---|---|
| `users` rows | 10 (tanmay `is_primary`, + abhiraj amit antara ash nihal prathamesh sam snehal sohan) |
| rows per user | tanmay 70,817 · snehal 60,334 · sam 48,679 · nihal 44,595 · antara 38,755 · amit 31,628 · ash 25,517 · prathamesh 12,906 · sohan 6,312 · abhiraj 131 — **all match scan doc** |
| total rows | 339,674 (70,817 + 268,857) |
| backfill | primary = 70,817; `user_id IS NULL` = 0 |
| third-party PII | friend rows with `ip_addr` = 0; distinct `conn_country` for friends = 13 |
| API fallback | `get_overview_stats()` → 70,700 streams / 3,225.5 h / ZAYN #1 (unchanged) |
| views scoped | 10 distinct `user_id` in `monthly_stats`; `top_artists` for snehal → EXO / BTS / SEVENTEEN |
| service layer | `get_overview_stats(user_id=<snehal>)` → 60,026 streams; default call unchanged |

## Next Steps

- Thread `user_id` through `apps/api/app/routes/*.py` (query param) + auth so
  endpoints can serve any user.
- Web user-switcher: `apps/web/src/store/app.ts` + picker in `AppLayout.tsx`, pass
  `user_id` from `apps/web/src/api/client.ts`.
- Friend-group comparison dashboard / collaborative recommender (options 3 & 4 in
  the scan doc) — data is now in place.
- Implement the many `# TODO: Implement with SQL function` placeholder methods in
  `supabase_data_loader.py` as user-scoped SQL.
- Decide whether the committed `data/other users/*.zip` (contain third-party IPs)
  should be purged from git history.

## Conclusion

The database is now multi-user: 10 people, ~340k streams, one owner column, per-user
indexes and views. The migration was non-destructive to the primary user's data and
API, and the load is repeatable per user. Third-party IPs were excluded on ingest.
