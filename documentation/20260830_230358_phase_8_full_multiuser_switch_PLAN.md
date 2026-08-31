# Full Multi-User Switch — All 7 Analytics Pages

## Context

Multi-user Supabase schema is live: `users` table + `user_id` FK on `streaming_history`
(~340k rows, 10 users), per-user materialized views `monthly_stats` / `top_artists` /
`top_tracks` (migration 003), the `_effective_user_id(p_user_id)` + COALESCE-to-primary
pattern (migration 004), and one working DB-backed feature — the Comparison dashboard
(`compare.py` + `Comparison.tsx` + `SupabaseDataLoader` leaderboard/overlap).

But the 7 other pages (Overview, Discovery, Milestones, Sessions, Listening Patterns,
Recommendations, Simulator) still run on the in-memory JSON `SpotifyDataLoader`
(`data_loader.py`), primary user only. `SupabaseDataLoader` has ~19 methods stubbed as
`# TODO` returning empty. Result: a friend can appear on the leaderboard but you cannot
open any of their per-user analytics.

**Outcome:** every analytics page reads user-scoped data from Postgres, a global
user-switcher in the AppBar drives which user's data is shown, and the JSON loader is no
longer on any request path. Return shapes stay byte-identical so frontend types don't
change.

**Decisions locked (via AskUserQuestion):**
- Migrate **all 7 pages** in this pass.
- Heavy compute (session KMeans, reco sklearn cosine/MMR, Markov simulation) runs as
  **Python in `SupabaseDataLoader`**, fed by a paginated PostgREST fetch of the user's
  raw `streaming_history` rows — reusing the exact numpy/sklearn logic from
  `SpotifyDataLoader`.
- User switcher **defaults to primary user, persists to `localStorage`**.

---

## Part A — Backend: port the 19 stubbed methods

File: `apps/api/app/services/supabase_data_loader.py`. Two porting strategies, one per method group.

### A1. SQL-friendly methods → RPCs in a new `006` migration

New file `apps/api/migrations/006_analytics_functions.sql`, following the 004 conventions
exactly: wrap in `BEGIN; … COMMIT;`, `DROP FUNCTION IF EXISTS` any prior signature first
(avoids supabase-py "function is not unique"), every function ends its param list with
`p_user_id UUID DEFAULT NULL` (limit params first), body filters
`WHERE user_id = _effective_user_id(p_user_id)`. `_effective_user_id` already exists from
004 — do not redefine.

RPCs to add (source logic = the same-named method in `data_loader.py`):

| RPC | Ports from | Return columns (match JSON keys) | Notes |
|---|---|---|---|
| `get_mood_summary(p_window_days INT DEFAULT 30, p_user_id UUID DEFAULT NULL)` | `get_mood_summary` | `window_days, avg_valence, avg_energy, avg_danceability, sample_size` | Port `_calculate_mood_metrics` (lines 254–318) into SQL: valence/energy from `EXTRACT(HOUR FROM ts)` + `EXTRACT(ISODOW FROM ts) >= 6`; danceability from `ms_played` thresholds (`>=180000`, `>=60000`) and `skipped`. Cutoff `ts >= NOW() - (p_window_days \|\| ' days')::interval`. Round 3dp; `NULL` when `sample_size = 0`. |
| `get_mood_contexts(p_user_id UUID DEFAULT NULL)` | `get_mood_contexts` | returns a JSON object (`RETURNS jsonb`) `{weekday_vs_weekend:{weekday:{…},weekend:{…}}, by_platform:{<platform>:{…}}}` | Each leaf `{avg_valence, avg_energy, avg_danceability, sample_size}`. `by_platform` only platforms with `sample_size >= 10`. Build with `jsonb_build_object` + `jsonb_object_agg`. |
| `get_mood_monthly(p_user_id UUID DEFAULT NULL)` | `get_mood_monthly` | rows `month TEXT (YYYY-MM), avg_valence, avg_energy, avg_danceability, sample_size` | `GROUP BY to_char(ts,'YYYY-MM')`, order asc. |
| `get_discovery_timeline(p_user_id UUID DEFAULT NULL)` | `get_discovery_timeline` | rows `month TEXT, new_artists_count INT` | `WITH firsts AS (SELECT artist, MIN(ts) … GROUP BY artist)` then count per `to_char(min_ts,'YYYY-MM')`. NOTE JSON version is first-in-iteration-order not chronological; SQL `MIN(ts)` is chronological → **acceptable, more correct**; call out in verification. |
| `get_artist_loyalty(p_limit INT DEFAULT 20, p_user_id UUID DEFAULT NULL)` | `get_artist_loyalty` | rows `artist, return_prob NUMERIC, half_life_days NUMERIC, total_streams INT` | Candidate set = top `p_limit` artists by stream_count (JSON takes `top(limit*2)` then keeps first `limit` — net effect = top `limit`). Require `>= 5` plays. Day-gaps between consecutive sorted plays via `LAG(ts) OVER (PARTITION BY artist ORDER BY ts)`; `return_prob = ROUND(LEAST(100, 100/(1+avg_gap_days)),1)`; `half_life_days = ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY gap_days),1)`. Order by `return_prob DESC` limit `p_limit`. |
| `get_artist_obsessions(p_limit INT DEFAULT 15, p_user_id UUID DEFAULT NULL)` | `get_artist_obsessions` | rows `artist, period_start DATE, period_end DATE, period_share NUMERIC, streams_in_period INT` | Week key `date_trunc('week', ts)::date` (Mon); per (week,artist) `count*100.0/sum(count) over (partition by week)`; week total `>= 10`; emit share `>= 30.0`; order `period_share DESC` limit. `period_end = period_start + 6`. |
| `get_reflective_insights(p_user_id UUID DEFAULT NULL)` | `get_reflective_insights` | `RETURNS jsonb` `{total_streams, longest_streak_days, most_active_hour, most_active_day, top_artist, avg_streams_per_day, insights[4]}` | Reuse the streak CTE shape from 004 `get_listening_streaks` for `longest_streak_days`. `most_active_hour` = argmax `EXTRACT(HOUR)`, `most_active_day` = day-name of argmax `ISODOW`. `top_artist` = top 1 from `top_artists` view. `avg_streams_per_day = total / ((max(ts)::date - min(ts)::date)+1)` 1dp. Build the 4 `insights` sentences with `format()` — copy the templates verbatim from `data_loader.py` lines ~700–743. |
| `get_weekend_weekday_comparison(p_user_id UUID DEFAULT NULL)` | `get_weekend_weekday_comparison` | `RETURNS jsonb` `{weekday:{streams,hours,avg_per_day}, weekend:{…}}` | Partition on `ISODOW >= 6`; `avg_per_day = streams/5` (weekday) or `/2` (weekend), 1dp; hours 2dp. |
| `get_most_repeated_tracks(p_limit INT DEFAULT 20, p_user_id UUID DEFAULT NULL)` | `get_most_repeated_tracks` | rows `track, artist, play_count INT, repeat_score NUMERIC` | Per (track,artist): `count(*)` and `count(distinct ts::date)`; require `count >= 5`; `repeat_score = ROUND(count::numeric / distinct_dates, 2)`; order desc limit. |
| `get_monthly_diversity(p_user_id UUID DEFAULT NULL)` | `get_monthly_diversity` | rows `month TEXT, unique_artists INT, total_streams INT, diversity_ratio NUMERIC` | `GROUP BY to_char(ts,'YYYY-MM')`; `diversity_ratio = ROUND(unique_artists*100.0/nullif(total_streams,0),2)`, `0` when total 0; order asc. |
| `get_listening_heatmap(p_user_id UUID DEFAULT NULL)` | `get_listening_heatmap` | rows `day TEXT, hour INT, stream_count INT` — **exactly 168** | `LEFT JOIN generate_series(1,7) d(dow) CROSS JOIN generate_series(0,23) h(hr)` against grouped counts, `COALESCE(count,0)`. Day order Mon→Sun (outer), hour 0→23 (inner). Map `dow`→day name. |
| `get_milestones_list(p_user_id UUID DEFAULT NULL)` | `get_milestones_list` | rows `date TEXT, year INT, type TEXT, title TEXT, description TEXT, value INT, badge_color TEXT` | 4 `UNION ALL` blocks: **streak** (runs len `>= 3`, top 10, gapless-island trick from 004; `value`=len; color `#2dd881`), **top_day** (top 15 days by count, `count >= 50`; color `#4ea699`), **first_artist** (per-artist `MIN(ts)`, first 20 by date, only if artist in top-20 of `top_artists` view; `value`=0; color `#6fedb7`), **diversity** (top 10 days by distinct-artist count, `>= 20`; `value`=artist count; color `#140d4f`). Final `ORDER BY date DESC`. Copy `title`/`description` `format()` templates verbatim from `data_loader.py` lines ~1607–1744. |
| `get_flashback(p_date DATE, p_user_id UUID DEFAULT NULL)` | `get_flashback` | `RETURNS jsonb` — success shape only (14 keys, see agent report §32) | Filter `ts::date = p_date`. No-data → the route returns `{date, streams:0, message:…}` (handle in Python, not SQL). Invalid-date-format → route-level `try/parse` returns the error dict. Times `to_char(min_ts,'HH12:MI AM')`; `listening_duration` = `round(hours,1) \|\| ' hours'`; `top_artists`/`top_tracks` = `jsonb_agg` of top 5 each. |

Python side for A1: replace each stub body with the same RPC pattern already used by
`get_overview_stats` etc. — `self.supabase.rpc('<name>', self._uid({...}, user_id)).execute()`,
map `response.data` to the exact dict the JSON loader returns, `try/except → {}`/`[]`.
Add `user_id: Optional[str] = None` (and keep existing `limit`/`window_days`/`date_str`
params) to every ported method signature. For the `RETURNS jsonb` RPCs, `response.data`
is already the dict — return `response.data[0]['<col>']` or `response.data` directly per
supabase-py's row wrapping (verify shape on first call).

### A2. Heavy-compute methods → Python off raw DB rows

These cannot be SQL (KMeans, StandardScaler, cosine + MMR, Markov walk). Add to
`SupabaseDataLoader`:

```
def _user_rows(self, user_id: Optional[str], *, music_only: bool = True) -> list[dict]:
    """Paginated PostgREST fetch of one user's streaming_history, newest-irrelevant order.
    Selects only the columns the heavy helpers touch:
      ts, ms_played, master_metadata_track_name, master_metadata_album_artist_name,
      master_metadata_album_album_name, platform, skipped, spotify_track_uri
    music_only -> .not_.is_('spotify_track_uri','null')
    Resolves user_id via _effective_user_id semantics: when None, look up the primary
    user's id once (SELECT id FROM users WHERE is_primary) and cache it.
    Pages at 1000 rows via .range() like _artist_vector already does.
    """
```

Then port these helpers from `data_loader.py` **verbatim** (same numpy/sklearn code,
same module constants — copy `SIM_*`, `RECO_*` consts into the supabase module or a shared
`app/services/_analytics_const.py`), changing only the data source from `self._data` to
`self._user_rows(user_id)`:

| Method | Ports helpers | Extra file reads |
|---|---|---|
| `get_session_durations` / `get_binge_sessions` / `get_session_statistics` | 30-min-gap sessionizer (`data_loader.py` ~880–1072) | none |
| `get_session_clusters` / `get_session_centroids` / `get_session_assignments` | `_build_sessions`, `_extract_session_features`, `_cluster_sessions` (1305–1603) | none. Keep the `< 10 sessions` alternate-shape branch and the `error` dict branch. |
| `get_recommendations` / `get_recommendations_csv_rows` | `_load_track_metadata`, `_build_track_vectors`, `_why_summary`, MMR loop (1849–2157) | reads `outputs/data/songs_info.json` + `artists_info.json` — **path via the existing repo-root walk**; add an `OUTPUTS_DATA_DIR` resolved from the same `Path(__file__).parents` scan already in the module (the `spotify-insights.env` finder). These JSON files are NOT per-user (they're a global track/artist metadata cache) — fine to keep as-is. |
| `get_sim_artists` / `get_simulation` / `get_simulation_csv_rows` | `_build_artist_transitions` (2162–2369) | none |

Cache heavy per-user artefacts on a dict keyed by `user_id`
(`self._sessions_by_user`, `self._reco_vecs_by_user`, `self._markov_by_user`) so repeated
calls in one process don't refetch — mirror the existing `self._artist_vecs` pattern.

Add `user_id: Optional[str] = None` to every A2 method signature too.

### Env-loading constraint

Do **not** touch the `for _parent in Path(__file__).resolve().parents` block
(lines 27–38) — it's what makes `spotify-insights.env` load under both
`uvicorn` (CWD `apps/api`) and repo-root scripts. Reuse that same resolved parent to
locate `outputs/data/` for the reco JSON.

---

## Part B — Backend: repoint the 8 route files

Files: `apps/api/app/routes/{stats,mood,discovery,milestones,sessions,patterns,reco,sim}.py`
(leave `health.py`, `compare.py`).

Per file, mechanical change:
1. `from app.services.data_loader import spotify_data`
   → `from app.services.supabase_data_loader import supabase_data`
2. Every `spotify_data.X(...)` → `supabase_data.X(...)`.
3. Add `user_id: str | None = Query(None)` to each route handler's signature and pass
   `user_id=user_id` through. For CSV-export handlers too (so a friend's export works).
4. Delete the now-defunct `spotify_data.load_data()` calls in
   `discovery.py` / `milestones.py` / `sessions.py` (DB needs no load step).
5. `mood.py`: keep the `window` → `window_days` parsing, pass
   `supabase_data.get_mood_summary(window_days=window_days, user_id=user_id)`.
6. `milestones.py` flashback: wrap `datetime.fromisoformat(date)` in `try/except` →
   return `{'error': 'Invalid date format. Use YYYY-MM-DD', 'date': date}`; on empty RPC
   result return `{'date': date, 'streams': 0, 'message': 'No listening data found for this date'}`.

No change to `main.py` (routers already registered) beyond nothing.

---

## Part C — Frontend: global user switcher + user_id threading

### C1. Store — `apps/web/src/store/app.ts`

Add `persist` middleware (zustand/middleware) scoped to just the user selection
(use `partialize` so theme/error/loading stay non-persisted):

```
selectedUserId: string | null   // null = primary / not yet loaded
setSelectedUserId: (id: string | null) => void
```

`persist(..., { name: 'spotify-insights-user', partialize: (s) => ({ selectedUserId: s.selectedUserId }) })`.

### C2. Switcher component — new `apps/web/src/components/UserSwitcher.tsx`

- On mount: `api.getCompareUsers()` → `CompareUser[]`.
- MUI `Select` (small, `variant="standard"`, `color="inherit"` styling for the AppBar),
  `aria-label="select user"`.
- Value = `selectedUserId ?? <primary user_id>`. Label shows `display_name`
  ("You" for `is_primary`, matching Comparison.tsx).
- `onChange` → `setSelectedUserId(id)`. When the chosen id === primary's id, store
  `null` (so calls omit `user_id` and hit the SQL fallback — matches the
  "omit when primary" decision).
- Render a `Skeleton` while the user list loads.

### C3. Mount in `AppLayout.tsx`

Between the flex-grow `<Typography>` (line 111) and the theme `<IconButton>` (line 112):
```
<UserSwitcher />
```
Nothing else in AppLayout changes.

### C4. Thread `user_id` through `apps/web/src/api/client.ts`

- Read the current selection **outside React**: `useAppStore.getState().selectedUserId`
  inside a small helper:
  ```
  function withUser(params: URLSearchParams) {
    const uid = useAppStore.getState().selectedUserId;
    if (uid) params.set('user_id', uid);
    return params;
  }
  ```
  (import `useAppStore` into client.ts — it's a plain store, safe outside components.)
- Every analytics function that currently builds a query string or hits a bare path:
  add `user_id` when set. Pattern for the bare-path ones:
  ```
  getOverviewStats: async (): Promise<OverviewStats> => {
    const q = withUser(new URLSearchParams());
    const qs = q.toString();
    const r = await apiClient.get<OverviewStats>(`/api/stats/overview${qs ? `?${qs}` : ''}`);
    return r.data;
  },
  ```
- Functions to update: `getOverviewStats, getTopArtists, getTopTracks, getMonthlyData,
  getPlatformStats, getMoodSummary, getMoodContexts, getMoodMonthly,
  getDiscoveryTimeline, getArtistLoyalty, getArtistObsessions, getReflectiveInsights,
  getHourlyDistribution, getDailyDistribution, getSkipBehavior, getYearlyComparison,
  getSessionDurations, getBingeSessions, getSessionStatistics,
  getWeekendWeekdayComparison, getListeningStreaks, getRepeatedTracks,
  getMonthlyDiversity, getListeningHeatmap, getMilestones, getFlashback,
  getSessionClusters, getSessionCentroids, getSessionAssignments, getRecommendations,
  getSimulation, getSimulationArtists`.
- CSV export URL builders (`exportTopArtists, exportTopTracks, exportMonthlySummary,
  exportRecommendations, exportSimulation`): append `user_id` too.
- **Do not** touch the `/api/compare/*` functions — they use `users` (plural) and are
  already multi-user.
- Pages re-fetch on user switch: add `selectedUserId` from `useAppStore` to each page's
  data-loading `useEffect` dependency array (Overview, Discovery, Milestones, Sessions,
  ListeningPatterns, Recommendations, Simulator). Small edit per page file.

### C5. Types — `apps/web/src/types/api.ts`

No shape changes (that's the whole point). Only add nothing unless a `jsonb` RPC returns
a subtly different key — verify in Part D and fix the loader, not the type.

---

## Part D — Apply migration + verify

### Apply 006

```
psql "postgresql://postgres:$SUPABASE_DATABASE_PASSWORD@db.daebjkkkjkyejfmxnahw.supabase.co:5432/postgres?sslmode=require" \
  -v ON_ERROR_STOP=1 -f apps/api/migrations/006_analytics_functions.sql
```
(direct host — the pooler rejects the tenant string). `SUPABASE_DATABASE_PASSWORD` is in
`spotify-insights.env`.

### Parity check (primary user: JSON loader == Supabase loader)

Write a throwaway `apps/api/scripts/verify_parity.py` (not committed) that, for the
primary user, calls each method on both `spotify_data` and `supabase_data` and diffs the
JSON (`json.dumps(sort_keys=True)`), with tolerances:
- Floats: compare rounded to the loader's own precision (2–3dp).
- `get_discovery_timeline`, `get_milestones_list` first_artist: **expected to differ**
  where the JSON version used iteration-order first-seen vs SQL `MIN(ts)` — eyeball that
  SQL is the more-correct chronological answer, don't require exact equality.
- Reco / simulation: deterministic (fixed `random_state=42`, most-probable walk) → should
  match exactly if `_user_rows` returns the same row set. If off, check the
  `music_only` filter and the `songs_info.json` path resolution.
- `get_session_clusters`: KMeans `random_state=42` is deterministic given identical input
  ordering — sort `_user_rows` by `ts` before sessionizing (JSON loader sorts too).

Run one endpoint end-to-end per page against a **non-primary** user to confirm scoping:
```
curl 'localhost:3011/api/stats/overview?user_id=<friend-uuid>'
curl 'localhost:3011/api/discovery/timeline?user_id=<friend-uuid>'
# … one per router
```
Values must differ from the primary user's and be internally consistent
(`total_streams` matches that user's leaderboard row from `/api/compare/leaderboard`).

### Frontend

```
cd apps/web && npm run build          # must pass (tsc + vite)
npm run dev                            # switch user in AppBar, watch every page refetch
```
Manual: pick a friend in the switcher → each of the 7 pages shows that user's numbers;
switch back to "You" → numbers return to the primary set and the `user_id` param drops
from requests (check devtools network).

### Docs

Write `documentation/<YYYYMMDD_HHMMSS>_phase_8_full_multiuser_switch.md` using the
CLAUDE.md schema (date, status, files created/modified, checklist, what-was-implemented,
next steps, conclusion).

---

## Critical files

**Backend**
- `apps/api/migrations/006_analytics_functions.sql` — new; ~13 RPCs, 004 conventions
- `apps/api/app/services/supabase_data_loader.py` — 19 stubs → real; add `_user_rows`,
  port heavy helpers, per-user caches
- `apps/api/app/services/_analytics_const.py` — new (optional); shared `SIM_*` / `RECO_*`
- `apps/api/app/routes/{stats,mood,discovery,milestones,sessions,patterns,reco,sim}.py`
  — swap import, add `user_id` Query param, drop `load_data()`

**Frontend**
- `apps/web/src/store/app.ts` — `selectedUserId` + `persist`
- `apps/web/src/components/UserSwitcher.tsx` — new
- `apps/web/src/layout/AppLayout.tsx` — mount `<UserSwitcher/>` in AppBar
- `apps/web/src/api/client.ts` — `withUser()` helper, thread into ~32 functions + 5 export URLs
- `apps/web/src/pages/*.tsx` (7) — add `selectedUserId` to the load `useEffect` deps

**Reuse (already exists — do not rebuild)**
- `_effective_user_id(p_user_id)` (migration 004) — every 006 RPC calls it
- `SupabaseDataLoader._uid()` / `._artist_vector()` pagination pattern — copy for `_user_rows`
- `api.getCompareUsers()` + `CompareUser` type — feed the switcher
- Per-user views `monthly_stats` / `top_artists` / `top_tracks` — loyalty, reflect,
  milestones first_artist read `top_artists` directly instead of re-aggregating

## Risks / call-outs
- `RETURNS jsonb` RPCs: supabase-py wraps rows; confirm whether `response.data` is the
  dict or `[{...}]` on the first call and unwrap consistently.
- Reco `songs_info.json` (~3MB) + `artists_info.json` load once per process — keep the
  `self._reco_meta_loaded` guard; it's global, not per-user.
- PostgREST ~8s statement timeout: the A1 RPCs are single-user aggregates over an indexed
  `user_id` — fine. `_user_rows` for a heavy user could be ~40k rows × 8 cols over
  pagination — acceptable (Comparison's `_artist_vector` already does this). If a heavy
  user times out, add `.order('ts')` server-side and rely on the `idx_streaming_user_ts`
  index.
- `get_discovery_timeline` / milestones `first_artist` semantic shift (iteration-order →
  chronological `MIN(ts)`) is a deliberate correctness improvement; note it in the phase doc.
