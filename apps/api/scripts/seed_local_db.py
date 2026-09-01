#!/usr/bin/env python3
"""Seed a local Postgres with streaming history.

Defaults to the committed synthetic fixture, so a fresh clone can bring the whole
stack up with no personal data:

    python scripts/seed_local_db.py                        # fixture, 2 users
    python scripts/seed_local_db.py --from-dir data        # a real export dir
    python scripts/seed_local_db.py --reset                # wipe rows first

Requires migrations to have run (`python db/migrate.py`).

Notes
-----
* Migration 003 already seeds the primary user (`tanmay`). Exactly one row may
  have is_primary = TRUE -- there is a partial unique index enforcing it -- and
  every unscoped endpoint depends on it, because SQL's `_effective_user_id()`
  resolves a NULL p_user_id to that user. Extra users are added non-primary.
* The fixture is split across two users so the comparison page has something to
  compare.
* The final refresh of the three materialized views must be NON-concurrent.
  `refresh_all_views()` (migration 004) uses REFRESH ... CONCURRENTLY, which
  errors on a view that has never been populated.

Phase 11 extracts the row normalization here into app/ingest/normalize.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

def _find_fixture() -> Path:
    """Locate the fixture from either the repo layout or the container layout.

    In the repo it is <root>/data/fixtures/; the API image mounts data at
    /app/data, so walk up from this file and take the first hit.
    """
    rel = Path("data") / "fixtures" / "sample_streaming_history.json"
    parents = Path(__file__).resolve().parents
    for parent in parents:
        candidate = parent / rel
        if candidate.exists():
            return candidate
    # Nothing found: return the repo-layout path if it exists as an index
    # (parents[3] = repo root from apps/api/scripts/), else the nearest
    # ancestor. main() reports this as "not found" with the path it tried.
    # Must not index blindly -- in the container this file is at /app/scripts,
    # which has fewer than four parents.
    return (parents[3] if len(parents) > 3 else parents[-1]) / rel


FIXTURE = _find_fixture()

# Columns copied from each export row. `ip_addr` is deliberately excluded: it is
# third-party PII and Phase 9 purged it from the repo's history.
COLUMNS = [
    "ts",
    "platform",
    "ms_played",
    "conn_country",
    "master_metadata_track_name",
    "master_metadata_album_artist_name",
    "master_metadata_album_album_name",
    "spotify_track_uri",
    "episode_name",
    "episode_show_name",
    "spotify_episode_uri",
    "reason_start",
    "reason_end",
    "shuffle",
    "skipped",
    "offline",
    "incognito_mode",
]

MATERIALIZED_VIEWS = ["monthly_stats", "top_artists", "top_tracks"]


def normalize(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One export row -> one streaming_history row. None if unusable."""
    if not row.get("ts") or row.get("ms_played") is None:
        return None
    out = {col: row.get(col) for col in COLUMNS}
    # Booleans are nullable in some exports but NOT NULL-defaulted in the schema.
    for flag in ("shuffle", "skipped", "offline", "incognito_mode"):
        if out[flag] is None:
            out[flag] = False
    return out


def load_rows(source: Path) -> List[Dict[str, Any]]:
    """Read one JSON file, or every streaming_*.json in a directory."""
    if source.is_dir():
        files = sorted(source.glob("streaming_*.json"))
        if not files:
            raise SystemExit(f"No streaming_*.json files in {source}")
    else:
        files = [source]

    rows: List[Dict[str, Any]] = []
    for path in files:
        with path.open() as fh:
            payload = json.load(fh)
        if not isinstance(payload, list):
            raise SystemExit(f"{path} is not a JSON array")
        rows.extend(payload)
        print(f"  read {len(payload):,} rows from {path.name}")
    return rows


def ensure_user(conn, username: str, display_name: str, is_primary: bool) -> str:
    """Get-or-create a user, returning its id."""
    existing = conn.execute(
        text("SELECT id FROM users WHERE username = :u"), {"u": username}
    ).scalar()
    if existing:
        return str(existing)
    new_id = conn.execute(
        text(
            "INSERT INTO users (username, display_name, is_primary) "
            "VALUES (:u, :d, :p) RETURNING id"
        ),
        {"u": username, "d": display_name, "p": is_primary},
    ).scalar()
    print(f"  created user {username} (primary={is_primary})")
    return str(new_id)


def primary_user(conn) -> Optional[str]:
    uid = conn.execute(text("SELECT id FROM users WHERE is_primary LIMIT 1")).scalar()
    return str(uid) if uid else None


def insert_rows(conn, rows: Iterable[Dict[str, Any]], user_id: str) -> int:
    payload = [{**r, "user_id": user_id} for r in rows]
    if not payload:
        return 0
    cols = COLUMNS + ["user_id"]
    stmt = text(
        f"INSERT INTO streaming_history ({', '.join(cols)}) "
        f"VALUES ({', '.join(':' + c for c in cols)})"
    )
    conn.execute(stmt, payload)
    return len(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a local Postgres.")
    parser.add_argument(
        "--from-dir",
        type=Path,
        default=None,
        help="Directory of streaming_*.json, or a single JSON file. "
        "Defaults to the committed fixture.",
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--reset", action="store_true", help="Delete existing streaming_history rows first"
    )
    parser.add_argument(
        "--users",
        type=int,
        default=2,
        help="Split the fixture across N users (default 2, so the "
        "comparison page has data). Ignored with --from-dir.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Seed even if the table already has rows (would duplicate them).",
    )
    args = parser.parse_args()

    from app.db.session import make_engine

    engine = make_engine(args.database_url)

    source = args.from_dir or FIXTURE
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")

    print(f"Loading from {source}")
    raw = load_rows(source)
    rows = [r for r in (normalize(r) for r in raw) if r is not None]
    print(f"  {len(rows):,} usable rows ({len(raw) - len(rows)} skipped)")
    if not rows:
        raise SystemExit("Nothing to seed.")

    with engine.begin() as conn:
        # Guard against seeding a schema that was never migrated.
        has_table = conn.execute(
            text("SELECT to_regclass('public.streaming_history')")
        ).scalar()
        if not has_table:
            raise SystemExit("streaming_history does not exist. Run: python db/migrate.py")

        if args.reset:
            deleted = conn.execute(text("DELETE FROM streaming_history")).rowcount
            print(f"  deleted {deleted:,} existing rows")
        elif not args.force:
            # Docker Compose runs this on every `up`; seeding an already-seeded
            # database would silently duplicate every row.
            existing = conn.execute(
                text("SELECT count(*) FROM streaming_history")
            ).scalar_one()
            if existing:
                print(
                    f"  {existing:,} rows already present; nothing to do. "
                    f"Use --reset to reseed, or --force to append."
                )
                return 0

        # Migration 003 seeds the primary user; fall back to creating one.
        owner = primary_user(conn) or ensure_user(conn, "tanmay", "John Doe", True)

        if args.from_dir:
            total = insert_rows(conn, rows, owner)
            print(f"  inserted {total:,} rows for the primary user")
        else:
            n_users = max(1, args.users)
            chunk = len(rows) // n_users or len(rows)
            total = 0
            for i in range(n_users):
                part = rows[i * chunk:] if i == n_users - 1 else rows[i * chunk:(i + 1) * chunk]
                if i == 0:
                    uid = owner
                else:
                    uid = ensure_user(conn, f"demo_user_{i}", f"Demo User {i}", False)
                inserted = insert_rows(conn, part, uid)
                total += inserted
                print(f"  inserted {inserted:,} rows for user {i + 1}/{n_users}")
            print(f"  {total:,} rows total")

        # Non-concurrent on purpose: CONCURRENTLY fails on a never-populated view.
        for view in MATERIALIZED_VIEWS:
            conn.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
        print(f"  refreshed {len(MATERIALIZED_VIEWS)} materialized views")

    print("\nSeed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
