# Repo hygiene & public-safe history — Phase 9

**Date:** 2026-09-01 09:38:34
**Status:** Completed
**Time to complete:** ~1h

## Overview

Made the public repo (`Tanmayb05/spotify-stats`) safe to publish. Purged all personal
data from the **entire git history** with `git filter-repo`, shrank `.git` from ~53 MB to
~7.1 MB, added a license / security policy / privacy documentation / synthetic CI fixture,
and made the dependency files honest (added the missing `supabase` runtime dep, pinned
everything with `==`, split a dev-requirements file). The app still boots and the local
JSON loader still works.

## Files Created

- `LICENSE` — MIT, scoped to source code only (explicitly not the data)
- `SECURITY.md` — Spotify exports are personal data; never commit; history-rewrite +
  re-clone notice; reporting contact
- `data/README.md` — how to request and place a Spotify "Extended streaming history"
  export; full record-schema table; fixture note
- `data/fixtures/sample_streaming_history.json` — 40 synthetic streaming rows in the real
  export shape, **no `ip_addr` field**, ~23 KB
- `apps/api/requirements-dev.txt` — `pytest`, `pytest-asyncio`, `httpx`, `ruff`,
  `pandera`, `dagster`, `dagster-webserver` (all pinned)
- `documentation/20260901_093834_phase_9_repo_hygiene.md` — this doc

## Files Modified

- `.gitignore` — activated the personal-data rules that were commented out
  (`data/raw/`, `data/other users/`, `data/Spotify Account Data/`, `data/*.json`,
  `data/*.csv` with a `!data/fixtures/` exception, `outputs/data/*.json`,
  `outputs/lyrics/`, `archived/`); tightened env rules to `*.env` + `!*.env.example`
- `apps/api/requirements.txt` — **added `supabase==2.22.0`** (a hard runtime dep of
  `app/services/supabase_data_loader.py`, previously absent from this file); pinned
  fastapi / uvicorn / pydantic / python-dotenv / pandas / numpy / scikit-learn to the
  `.venv` versions with `==`
- `requirements.txt` (root) — pinned every entry with `==`
- `README.md` — new `## Data & privacy` section near the top; rewrote `## Data Structure`
  → points at `data/README.md`; rewrote `## Privacy & Data Source` and `## License`
- `UPDATE.md` — Phase 9 row → `DONE`, next phase → 10, full log entry
- **git history** — see below (not a file change; a history rewrite)

## Checklist

- [x] Intuitive navigation — n/a (no UI change)
- [x] Consistent design — n/a
- [x] Responsive layout — n/a
- [x] A11y labels/roles — n/a
- [x] Error handling & feedback — app still boots, `/health` 200, loader OK
- [x] Performance sanity checks — `.git` 53 MB → 7.1 MB; fresh clone + install works
- [x] Security baseline — **all third-party + owner PII purged from history**; no
  secrets were ever committed (only `*.env.example`); `ip_addr` documented as dropped
- [x] Docs generated — this file + `UPDATE.md` log + `data/README.md` + `SECURITY.md`

## What Was Implemented

### Purpose

Before any further roadmap work, the repo had to stop exposing personal data:
9 friends' raw Spotify exports (`data/other users/*.zip`, with third-party `ip_addr`,
introduced in commit `7d16c08`), the owner's `data/Spotify Account Data/` (home address,
payment records), `ip_addr` on every row of `data/streaming_*.json`, and ~60 MB of
enriched JSON blobs bloating `.git` to 53 MB. It also lacked a `LICENSE`, a security
policy, and an honest `requirements.txt` (missing `supabase`, nothing pinned).

### Features

1. **History purge** — three `git filter-repo` passes:
   - `--invert-paths --paths-from-file <list>` over 17 paths (friends' exports, owner
     account data, streaming JSON, unique CSVs, enriched JSON, lyrics).
   - a second pass for `outputs/lyrics-1.json` (the pre-rename path, missed by the first
     `outputs/lyrics` entry).
   - `--replace-text` to redact `REDACTED_IP` and `REDACTED_IP` (real IPs that
     appeared as example values in design docs) → `REDACTED_IP`.
   Each followed by `git reflog expire --expire=now --all && git gc --prune=now
   --aggressive`.
2. **Backup mirror** — `git clone --mirror` to
   `../spotify-insights-backup-pre-phase9.git` before any rewrite (the only undo).
3. **Working-tree restore** — filter-repo deletes purged paths from the working tree too;
   the files the local app needs (`data/streaming_*.json`,
   `outputs/data/{songs,artists}_info.json`) were copied back from the mirror. They are
   now git-ignored.
4. **`.gitignore`** — the blanket `data/` / `*.json` / `outputs/` rules that were
   commented out are now real, with a `!data/fixtures/` carve-out and a
   `!outputs/data/*.csv` carve-out (the small aggregates the current app reads stay
   tracked).
5. **New docs** — `LICENSE` (MIT), `SECURITY.md`, `data/README.md`, README "Data &
   privacy" section.
6. **Synthetic fixture** — `data/fixtures/sample_streaming_history.json`, 40 rows,
   generated with a fixed seed, real field shape minus `ip_addr`, mixed
   `platform` / `skipped` / `shuffle` / `reason_end`, spanning 2022–2024.
7. **Requirements** — `apps/api/requirements.txt` gains `supabase` and `==` pins;
   `apps/api/requirements-dev.txt` created; root `requirements.txt` `==`-pinned. Versions
   taken from the project `.venv` / resolved via `pip install --dry-run --report`.

### Implementation

- **filter-repo paths file** (pass 1):
  ```
  data/other users
  data/Spotify Account Data
  data/streaming_2018-2020_0.json
  data/streaming_2020-2022_1.json
  data/streaming_2022-2023_2.json
  data/streaming_2023-2024_3.json
  data/streaming_2024-2025_4.json
  data/streaming_video_2018-2025.json
  data/failed_lyrics.csv
  data/songs_processing_queue.csv
  data/unique_albums.csv
  data/unique_artists.csv
  data/unique_songs.csv
  data/unique_tracks.csv
  outputs/data/songs_info.json
  outputs/data/artists_info.json
  outputs/lyrics
  ```
- **Command:** `git filter-repo --invert-paths --paths-from-file <file> --force`
  (`--force` because the repo is the working checkout with a remote; the backup mirror
  already existed).
- filter-repo removes the `origin` remote by design — re-added:
  `git remote add origin https://github.com/Tanmayb05/spotify-stats.git`.
- **Verification queries** (all after the final gc):
  - PII path scan: `git log --all --name-only --pretty=format: | sort -u | grep -Ei
    'other users|Spotify Account Data|data/streaming_[0-9]|outputs/data/songs_info\.json|
    outputs/data/artists_info\.json|outputs/lyrics/|data/unique_|failed_lyrics|
    songs_processing'` → **no output**.
  - IP-literal scan: dump every blob in `git rev-list --all --objects` through
    `git cat-file --batch`, `grep -aoE` for dotted-quad, strip private/reserved ranges
    → **empty**.
  - largest remaining blob is `outputs/images/artist_timeline_bands.png` (1.7 MB).
- **Base branch:** the roadmap infra (`UPDATE.md`, the roadmap doc) lives only on
  `chore/name-masking-and-roadmap`, not `main`. So this phase branched from
  `chore/name-masking-and-roadmap` (not `main` as the plan first assumed).

### Flow

1. `git checkout -b chore/phase-9-repo-hygiene` off `chore/name-masking-and-roadmap`;
   folded the pending `CLAUDE.md` "Senior DS/DE role" edit into its own commit.
2. `git clone --mirror` backup.
3. filter-repo pass 1 (paths) → gc → verify.
4. filter-repo pass 2 (`outputs/lyrics-1.json`) → gc.
5. filter-repo pass 3 (`--replace-text` IP redaction) → gc → exhaustive verify.
6. Restore working-tree data files from the mirror.
7. Rewrite `.gitignore`; add `LICENSE`, `SECURITY.md`, `data/README.md`, fixture;
   fix requirements; update README.
8. Boot check: `import app.main` / `uvicorn` / `curl /health` / loader reads 70,817 rows.
9. `git add -A && git commit` (file changes).
10. `UPDATE.md` + this doc.
11. Force-push `main`; force-delete `origin/feat/multi-user-analytics-switch`.

### Usage

- **Run with your own data:** follow `data/README.md` → drop the export under
  `data/raw/<name>/` (git-ignored).
- **Run with no data:** `data/fixtures/sample_streaming_history.json` is a committed
  synthetic sample for tests / a quick look.
- **Install:** `pip install -r apps/api/requirements.txt` (runtime) or
  `-r apps/api/requirements-dev.txt` (adds pytest / ruff / pandera / dagster).
- **If you cloned before 2026-09-01:** delete your clone and re-clone — history was
  rewritten, old SHAs are dead.

## Next Steps

- **Phase 10** — Local-first infra: Docker Compose (Postgres + API + web), a migration
  runner, and a `DB_BACKEND` switch so `docker compose up` works with no Supabase
  account.
- Keep the backup mirror (`../spotify-insights-backup-pre-phase9.git`) until the remote
  is confirmed clean; then it can be deleted.
- Optional follow-up: ask GitHub support to GC unreachable objects if direct-SHA blob
  URLs are a concern (no ref points at them now).
- `data/Spotify Account Data/` and `data/streaming_*.json` still sit in the local working
  tree (git-ignored) so the current app runs; the Phase 10+ loader work should move to
  reading `data/raw/<user>/`.

## Conclusion

The repository is now safe to publish: no third-party or owner personal data anywhere in
history, `.git` down ~87%, dependencies pinned and complete, privacy posture documented,
and a synthetic fixture in place for CI. The running app is unaffected. The one
irreversible action (history rewrite + force-push) was taken with explicit owner approval
and a full backup mirror retained.
