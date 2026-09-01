#!/usr/bin/env python3
"""Apply apps/api/migrations/*.sql in filename order, once each.

Tracked in `schema_migrations(version, applied_at, checksum, note)`. Re-running
is a no-op. Tracking (rather than making the old files idempotent) is required
because 001 uses bare CREATE INDEX / CREATE MATERIALIZED VIEW and is not
replay-safe.

  python db/migrate.py                    # apply what is pending
  python db/migrate.py --dry-run          # show the plan, change nothing
  python db/migrate.py --database-url ... # override DATABASE_URL
  python db/migrate.py --status           # list applied vs pending

Superseded migrations
---------------------
002_helper_functions.sql is recorded as applied WITHOUT being executed. Every
function it defines is redefined by 004 with an extra `p_user_id UUID DEFAULT
NULL` argument. Because both variants have all-default arguments, applying both
makes calls ambiguous and Postgres rejects them at call time:

    ERROR: function get_top_artists(limit_count => integer) is not unique

The file is kept in the repo as history; the skip and its reason are recorded in
the ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import List, Optional

# Allow running this file directly: `python db/migrate.py` from apps/api.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"

# version -> why it is skipped (still recorded, so a rerun stays a no-op).
SUPERSEDED = {
    "002_helper_functions.sql": (
        "skipped: every function superseded by 004_user_scoped_functions.sql, "
        "which adds p_user_id; applying both creates ambiguous overloads"
    )
}

CREATE_LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum   TEXT,
    note       TEXT
)
"""


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def discover() -> List[Path]:
    if not MIGRATIONS_DIR.is_dir():
        raise SystemExit(f"No migrations directory at {MIGRATIONS_DIR}")
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def applied_versions(engine: Engine) -> dict:
    with engine.begin() as conn:
        conn.execute(text(CREATE_LEDGER))
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT version, checksum, note FROM schema_migrations")
        ).mappings().all()
    return {r["version"]: dict(r) for r in rows}


def record(conn, version: str, digest: str, note: Optional[str]) -> None:
    conn.execute(
        text(
            "INSERT INTO schema_migrations (version, checksum, note) "
            "VALUES (:v, :c, :n) ON CONFLICT (version) DO NOTHING"
        ),
        {"v": version, "c": digest, "n": note},
    )


def apply_one(engine: Engine, path: Path) -> None:
    """Run one migration and record it, atomically.

    Files 003/005/007 contain their own BEGIN/COMMIT. SQLAlchemy's engine.begin()
    would nest a transaction around them, so those statements are stripped; the
    surrounding transaction provides the same guarantee.
    """
    sql = path.read_text()
    stripped = "\n".join(
        line
        for line in sql.splitlines()
        if line.strip().upper() not in ("BEGIN;", "COMMIT;")
    )
    with engine.begin() as conn:
        conn.execute(text(stripped))
        record(conn, path.name, checksum(path), None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply SQL migrations in order.")
    parser.add_argument("--database-url", default=None, help="Overrides DATABASE_URL")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan only")
    parser.add_argument("--status", action="store_true", help="Show applied vs pending")
    args = parser.parse_args()

    from app.db.session import make_engine

    engine = make_engine(args.database_url)
    files = discover()

    if args.dry_run:
        # Report the plan without creating the ledger or touching the database.
        print(f"Migrations directory: {MIGRATIONS_DIR}")
        for path in files:
            if path.name in SUPERSEDED:
                print(f"  SKIP   {path.name}  ({SUPERSEDED[path.name]})")
            else:
                print(f"  APPLY  {path.name}")
        print(f"\n{len(files)} file(s). Dry run: nothing was executed.")
        return 0

    done = applied_versions(engine)

    if args.status:
        print(f"{'STATUS':<9} {'VERSION':<36} NOTE")
        for path in files:
            state = "applied" if path.name in done else "pending"
            note = done.get(path.name, {}).get("note") or ""
            print(f"{state:<9} {path.name:<36} {note}")
        return 0

    applied_count = 0
    skipped_count = 0

    for path in files:
        if path.name in done:
            continue

        if path.name in SUPERSEDED:
            with engine.begin() as conn:
                record(conn, path.name, checksum(path), SUPERSEDED[path.name])
            print(f"skip   {path.name}  ({SUPERSEDED[path.name]})")
            skipped_count += 1
            continue

        print(f"apply  {path.name} ...", end=" ", flush=True)
        try:
            apply_one(engine, path)
        except Exception as exc:
            print("FAILED")
            print(f"\n{path.name} failed: {exc}", file=sys.stderr)
            return 1
        print("ok")
        applied_count += 1

    if applied_count == 0 and skipped_count == 0:
        print("Nothing to do; schema is up to date.")
    else:
        print(f"\nApplied {applied_count}, recorded-as-skipped {skipped_count}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
