# Local development

Two ways to run the stack. Docker Compose needs no Spotify or Supabase account.

---

## 1. Docker Compose (local Postgres, no accounts needed)

```bash
docker compose up --build
```

| Service | URL | Notes |
|---|---|---|
| web | http://localhost:3010 | Vite dev server |
| api | http://localhost:3011 | `/health`, `/docs` |
| db  | localhost:5433 | Postgres 16 (5432 inside the network) |

On start the api container runs migrations and seeds the committed synthetic
fixture. Both are idempotent, so `docker compose up` is safe to repeat.

Teardown, discarding the database volume:

```bash
docker compose down -v
```

### Loading a real Spotify export

Put your extended streaming history (`streaming_*.json`) in `./data`, which is
mounted read-only into the api container, then:

```bash
docker compose exec api python scripts/seed_local_db.py --from-dir /app/data --reset
```

`data/` and `outputs/` are gitignored — see `data/README.md` for how to request
an export from Spotify.

### Recommendations and the simulator

`/api/reco` and `/api/simulate/next` read enrichment blobs from
`outputs/data/{songs,artists}_info.json`. Those files are gitignored and absent
from a fresh clone, so on a clean checkout both endpoints return empty results
and the api logs:

```
⚠️  Reco metadata unavailable: no readable songs_info.json / artists_info.json
```

Everything else works. Compose mounts `./outputs` read-only, so the endpoints
populate as soon as the files exist locally. Phase 11 loads this data into
Postgres and removes the file dependency.

---

## 2. Native (against Supabase — the default)

```bash
./start.sh          # api on :3011, web on :3010
```

Requires `spotify-insights.env` at the repo root with `SUPABASE_URL` and
`SUPABASE_SERVICE_KEY`. This is the path the deployed demo uses.

---

## Configuration

All backend config goes through `apps/api/app/config.py`. Real environment
variables win over `spotify-insights.env`, which is how Compose injects values.

| Variable | Default | Purpose |
|---|---|---|
| `DB_BACKEND` | `supabase` | `local` or `supabase` |
| `DATABASE_URL` | — | Postgres DSN; required when `DB_BACKEND=local` |
| `SUPABASE_URL` | — | Required when `DB_BACKEND=supabase` |
| `SUPABASE_SERVICE_KEY` | — | Falls back to `SUPABASE_ANON_KEY` |
| `CORS_ORIGINS` | the four dev/prod origins | Comma-separated |
| `VITE_API_PROXY_TARGET` | `http://localhost:3011` | Vite dev-server proxy target |

Both backends call the *same* SQL functions from `apps/api/migrations/`, so
results are identical; only the transport differs (PostgREST vs direct SQL).

---

## Migrations

```bash
cd apps/api
python db/migrate.py              # apply anything pending
python db/migrate.py --dry-run    # show the plan, change nothing
python db/migrate.py --status     # applied vs pending
```

Applied files are recorded in `schema_migrations`, so re-running is a no-op.
Tracking is required rather than optional: `001` uses bare `CREATE INDEX` and
`CREATE MATERIALIZED VIEW`, so it is not replay-safe.

### Why 002 is skipped

`002_helper_functions.sql` is recorded as applied **without being executed**.
Every function in it is redefined by `004_user_scoped_functions.sql` with an
extra `p_user_id UUID DEFAULT NULL`. Both variants have all-default arguments,
so applying both makes calls ambiguous and Postgres rejects them at call time:

```
ERROR:  function get_top_artists(limit_count => integer) is not unique
```

The file is kept as history. The skip and its reason are recorded in the ledger.

---

## Verifying backend parity

The loader catches exceptions and returns `{}` / `[]`, so a broken query shows
up as a blank chart rather than an error. This script diffs every loader method
across both backends and is the guard against that:

```bash
cd apps/api
python scripts/check_backend_parity.py --tolerant   # structure + types
python scripts/check_backend_parity.py              # exact values
```

Use `--tolerant` when the two databases hold different data — it compares
shapes and types instead of values.
