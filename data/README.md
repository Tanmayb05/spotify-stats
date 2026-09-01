# `data/` — how to get listening data in

**No real data is committed to this repo.** Everything in this directory except this
file and `fixtures/` is `.gitignore`d. See `../SECURITY.md`.

There are two ways to run the project:

| You want | Use |
|---|---|
| A zero-setup look / CI | `data/fixtures/sample_streaming_history.json` (synthetic, tiny) |
| Real analysis on your own history | request a Spotify export (below) |

---

## 1. Request your Spotify export

1. Go to <https://www.spotify.com/account/privacy/>.
2. Request **"Extended streaming history"** (not the small "Account data" one — that
   only has ~1 year). Spotify emails a `.zip` in up to ~30 days.
3. The zip contains `Streaming_History_Audio_<range>_<n>.json` files (and
   `Streaming_History_Video_*.json` for podcasts).

## 2. Place it

```
data/
  raw/
    <your-name>/
      Streaming_History_Audio_2018-2020_0.json
      Streaming_History_Audio_2020-2022_1.json
      ...
```

`data/raw/` is git-ignored. Never commit an export — it contains your `ip_addr` on
every row, and (in the full "Account data" package) your address and payment records.

> The current loader (`apps/api/app/services/data_loader.py`) still globs the older
> flat layout `data/streaming_[0-9]*.json`. Until the Phase 10+ loader work lands you
> can also drop the per-year files directly in `data/` with that naming. Either way
> they stay untracked.

## 3. Record schema

Each element of the JSON array is one listening event. Fields the app relies on:

| Field | Type | Notes |
|---|---|---|
| `ts` | string (ISO-8601, `Z`) | when the track **stopped** playing |
| `ms_played` | int | milliseconds actually played |
| `master_metadata_track_name` | string \| null | null for podcasts / local files |
| `master_metadata_album_artist_name` | string \| null | |
| `master_metadata_album_album_name` | string \| null | |
| `spotify_track_uri` | string \| null | `spotify:track:<id>` |
| `platform` | string | e.g. `ios`, `android`, `web player`, `os x` |
| `conn_country` | string | 2-letter country code |
| `reason_start` | string | `trackdone`, `fwdbtn`, `clickrow`, … |
| `reason_end` | string | `trackdone`, `fwdbtn`, `endplay`, … |
| `shuffle` | bool | |
| `skipped` | bool \| null | |
| `offline` | bool | |
| `incognito_mode` | bool | |
| `episode_name`, `episode_show_name`, `spotify_episode_uri` | podcast fields |

**`ip_addr`** also appears in every real export row. **The loader drops it; it is
never stored.** It is intentionally absent from `fixtures/sample_streaming_history.json`.

## 4. Fixture

`fixtures/sample_streaming_history.json` — ~40 fully synthetic rows in the exact shape
above (minus `ip_addr`), spanning ~2 years, with a mix of `platform`, `skipped`,
`shuffle` and `reason_end` values. Safe to commit, used by tests.
