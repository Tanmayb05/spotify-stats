# Other Users' Spotify Data — Scan Report

**Date:** 2026-08-30 06:26:39
**Status:** Completed
**Time to complete:** ~25m

## Overview

Nine friends supplied Spotify **Extended Streaming History** exports as zip files in
`data/other users/`. This pass extracts them, scans every record, and reports what
the data contains and what can be built with it. No database work was done — that
needs its own go-ahead.

## Files Created

- `data/other users/<user>/Streaming_History_Audio_*.json` — extracted audio history (9 users, gitignored)
- `data/other users/<user>/Streaming_History_Video_*.json` — extracted video history (gitignored)
- `documentation/20260830_062639_other_users_data_scan.md` — this report

## Files Modified

- `.gitignore` — added `data/other users/*/` so extracted third-party listening history + IPs are not committed (the source `.zip` files remain tracked, as they already were)

## Checklist

- [x] All 9 zips extracted (audio + video JSON only; the identical 1.6 MB Spotify boilerplate PDF in each zip was discarded)
- [x] Extracted dirs gitignored — third-party PII not committed
- [x] Per-user scan: record counts, date range, hours, platforms, skip rate, top artists
- [x] Aggregate scan: total volume, artist/track overlap with owner's data, group cohesion matrix
- [x] PII exposure documented
- [x] Options for use enumerated

## What Was Implemented

### Data shape

Every zip is a standard Spotify Extended Streaming History export — identical schema
to the owner's own `data/streaming_*.json`. Per-record fields:

```
ts, platform, ms_played, conn_country, ip_addr,
master_metadata_track_name, master_metadata_album_artist_name,
master_metadata_album_album_name, spotify_track_uri,
episode_name, episode_show_name, spotify_episode_uri,
audiobook_title, audiobook_uri, audiobook_chapter_uri, audiobook_chapter_title,
reason_start, reason_end, shuffle, skipped, offline, offline_timestamp, incognito_mode
```

### Per-user summary (audio history)

| user | records | music | podcast | span | hours | skip% | top artists |
|---|---:|---:|---:|---|---:|---:|---|
| **abhiraj** | 131 | 131 | 0 | 2024-06 → 2024-10 | 6 | 18 | The Weeknd, Travis Scott, Metro Boomin, Arctic Monkeys |
| **amit** | 31,628 | 30,979 | 649 | 2019-02 → 2025-09 | 1,407 | 13 | Linkin Park, Taylor Swift, Eminem, Imagine Dragons, Coldplay |
| **antara** | 38,755 | 38,641 | 114 | 2019-08 → 2025-10 | 1,113 | 55 | Taylor Swift, Pritam, Lana Del Rey, Vishal-Shekhar, A.R. Rahman |
| **ash** | 25,517 | 25,486 | 28 | 2022-07 → 2025-10 | 1,122 | 42 | Taylor Swift, Pritam, A.R. Rahman, Vishal-Shekhar, Arijit Singh |
| **nihal** | 44,595 | 44,575 | 20 | 2019-02 → 2025-10 | 1,372 | 26 | Pritam, The Weeknd, Ritviz, AP Dhillon, Travis Scott |
| **prathamesh** | 12,906 | 12,895 | 11 | 2023-04 → 2025-10 | 505 | 46 | Pritam, Vishal-Shekhar, Arijit Singh, Taylor Swift, Atif Aslam |
| **sam** | 48,679 | 48,594 | 85 | 2019-02 → 2025-10 | 1,560 | 22 | Stray Kids, Taylor Swift, One Direction, Post Malone, BTS |
| **snehal** | 60,334 | 60,026 | 308 | 2019-02 → 2025-10 | 2,673 | 8 | EXO, BTS, SEVENTEEN, BAEKHYUN, DAY6 (heavy K-pop) |
| **sohan** | 6,312 | 6,312 | 0 | 2019-04 → 2021-12 | 262 | 0 | Imagine Dragons, Post Malone, Marshmello, Avicii, Maroon 5 |

**Totals:** 268,857 records across 9 users. abhiraj and sohan are thin/partial
exports; the other 7 are full multi-year histories. Video history exists per user
but is tiny (podcasts/videos are <2% of every export).

### Overlap with owner's data

Owner: 70,817 music streams, 4,341 distinct artists, 13,814 distinct tracks
(2018-10 → 2025-10, 3,225 h).

| user | shared artists | artist Jaccard % | shared tracks | track Jaccard % |
|---|---:|---:|---:|---:|
| amit | 1,487 | 22.9 | 3,192 | 14.3 |
| sam | 1,016 | 18.9 | 2,833 | 14.2 |
| antara | 866 | 16.6 | 2,021 | 11.7 |
| nihal | 1,335 | 16.3 | 2,871 | 11.9 |
| snehal | 836 | 14.7 | 1,854 | 9.1 |
| ash | 641 | 12.4 | 1,303 | 7.5 |
| prathamesh | 569 | 12.1 | 1,235 | 8.0 |
| sohan | 126 | 2.9 | 195 | 1.4 |
| abhiraj | 15 | 0.3 | 25 | 0.2 |

Across all 9 friends: **10,538 distinct artists**, of which **8,251 are ones the
owner has never played** — a large candidate pool for recommendations.

### Group cohesion (pairwise artist Jaccard %)

```
            me abhira   amit antara    ash  nihal pratha    sam snehal  sohan
me           —    0.3   22.9   16.6   12.4   16.3   12.1   18.9   14.7    2.9
amit      22.9    0.5      —   16.2   12.3   16.9   11.9   18.6   15.3    3.1
antara    16.6    0.9   16.2      —   23.8   15.7   27.3   25.5   17.9    5.2
ash       12.4    0.7   12.3   23.8      —   11.9   23.7   18.8   14.9    4.5
nihal     16.3    0.4   16.9   15.7   11.9      —   11.8   17.7   14.4    2.5
pratham   12.1    1.0   11.9   27.3   23.7   11.8      —   21.7   16.7    7.5
sam       18.9    0.7   18.6   25.5   18.8   17.7   21.7      —   25.7    5.4
snehal    14.7    0.7   15.3   17.9   14.9   14.4   16.7   25.7      —    5.1
sohan      2.9    1.8    3.1    5.2    4.5    2.5    7.5    5.4    5.1      —
```

Clusters: **antara–prathamesh–ash–sam** are the tightest sub-group (Bollywood-heavy,
~24-27%). amit is the owner's closest match (22.9%). snehal is a K-pop outlier;
abhiraj/sohan are too sparse to cluster.

### PII exposure

Every record carries `ip_addr` (e.g. sam's export alone has 1,729 distinct IPs) and
`conn_country`. This is **other people's location data**.

- The source `.zip` archives were **already committed** to this repo before this
  session — that's a pre-existing state, not changed here.
- Newly extracted per-user JSON is now gitignored so the plaintext copies don't get
  added.
- Any ingest pipeline **must drop `ip_addr`** (and probably `conn_country` unless a
  geo feature genuinely needs it).

## What you can do with this data

### 1. Nothing further — keep as scanned archive
Safe default. Data is extracted, documented, gitignored.

### 2. Multi-user analytics (design already written)
`documentation/multi_user_data_storage_design.md` + `multi_user_summary.md` fully
spec this and it is **not built yet**. Work:
- migration `003_add_multi_user_support.sql` — `users` table, `user_id` FK on
  `streaming_history`, backfill existing rows as one user, composite `(user_id, ts)` indexes
- `apps/api/scripts/load_multi_user_data.py` — batch-load all 9 exports, **strip `ip_addr`**
- thread `user_id` through `apps/api/app/services/supabase_data_loader.py`, the
  routes, and a user-switcher in the web app
- doc estimate: migrations ~1 h, loading ~2-3 h, full API/UI threading ~1 week

### 3. Friend-group comparison dashboard
A scoped subset of #2 — no auth/RLS needed since it's a fixed private group:
- "who listened most" leaderboard (snehal 2,673 h vs sohan 262 h)
- shared-artist / shared-track overlap already computed above
- taste-similarity graph from the cohesion matrix (force-directed, edge = Jaccard)
- group top-100 artists/tracks, "only-you" picks per person
- listening-personality contrasts (snehal 8% skip / completionist vs antara 55% skip / sampler)

### 4. Upgrade the Phase 6 recommender to real collaborative filtering
Phase 6 today is content-based only. With 9 real neighbours:
- recommend from taste-similar friends' history (amit, sam, antara are nearest)
- 8,251 artists the owner has never played, weighted by neighbour similarity ×
  neighbour play count
- needs #2's data loaded first

### 5. Demo / cold-start profiles for the deployed app
Load 2-3 as alternate demo users so the public deployment isn't a single person's data.

## Next Steps

- Owner picks one of the options above (2-5 each need explicit go-ahead — they touch Supabase / API / web).
- If #3 or #4: start with `003` migration + `load_multi_user_data.py` (shared prerequisite).
- Decide `conn_country` retention (drop entirely vs keep for a geo chart).
- Consider whether the committed `.zip`s should be removed from git history (separate call).

## Conclusion

All 9 exports are clean, standard Spotify histories totalling ~269k plays; 7 are
full multi-year and analytically rich. Overlap and cohesion metrics show a genuine
friend-group signal (amit/sam/antara nearest the owner; a Bollywood sub-cluster;
snehal a K-pop outlier), making a group-comparison dashboard or a collaborative
recommender the highest-value uses. Main caution is third-party IP PII, which any
ingest must strip.
