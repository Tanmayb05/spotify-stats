#!/usr/bin/env python3
"""Build the star schema end to end: discover export files -> land bronze ->
dedup to silver -> dims + fact (gold) -> refresh MVs.

    python scripts/build_star_schema.py                 # all users
    python scripts/build_star_schema.py --only primary  # one/some slugs
    python scripts/build_star_schema.py --no-land        # skip landing, rebuild
                                                         # silver/gold from bronze

Phase 12: this used to hold seven inline stage functions and build only from a
one-time migration-008 bronze backfill. Those rows are gone (migration 011) and
the stage functions moved to app/ingest/{dedup,enrich}.py -- one definition,
shared with the Dagster gold_star asset. This script is now a ~90-line wrapper
that preserves the old CLI + exit-code contract (0 = V1 pass, 1 = mismatch) and
the same stage log, so capture/compare_api_baseline.py keep working unchanged.

The whole silver->gold rebuild runs in ONE engine.begin(): a mid-rebuild failure
leaves the previous star serving the app. Landing runs in its own transaction
per file first; MV refresh runs in its own transaction after the rebuild commits
(a REFRESH inside the TRUNCATE/INSERT txn would see pre-commit state).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.ingest import dedup, enrich
from app.ingest.discover import discover_files
from app.ingest.landing import (
    get_or_create_user,
    land_file,
    user_watermark,
)


def log(msg: str) -> None:
    print(msg, flush=True)


def do_landing(engine, only) -> dict:
    files = discover_files(only=only)
    log(f"\n[land] {len(files)} export file(s) discovered")
    totals = {"files": len(files), "new": 0, "landed": 0, "quarantined": 0, "skipped": 0}
    # Resolve users + watermarks once, in their own txn.
    with engine.begin() as conn:
        uid = {
            df.slug: get_or_create_user(conn, df.slug, df.display_name, df.is_primary)
            for df in files
        }
        wm = {slug: user_watermark(conn, u) for slug, u in uid.items()}
    for df in files:
        with engine.begin() as conn:
            res = land_file(conn, df, uid[df.slug], None, wm.get(df.slug))
        if res.skipped_reason:
            totals["skipped"] += 1
            continue
        totals["new"] += 1
        totals["landed"] += res.rows_landed
        totals["quarantined"] += res.rows_quarantined
        log(f"  {df.slug:<12} {df.rel_path:<55} "
            f"landed={res.rows_landed:>7,} quarantined={res.rows_quarantined}")
    log(f"[land] files_new={totals['new']} rows_landed={totals['landed']:,} "
        f"rows_quarantined={totals['quarantined']} skipped={totals['skipped']}")
    return totals


def rebuild_star(engine) -> bool:
    with engine.begin() as conn:
        if not conn.execute(text("SELECT to_regclass('bronze.raw_streams')")).scalar():
            log("bronze.raw_streams does not exist. Run: python db/migrate.py")
            return False

        conn.execute(text("TRUNCATE TABLE gold.fact_streams RESTART IDENTITY"))

        log("\n[1/7] silver.streams <- bronze.raw_streams (dedup on row_fingerprint)")
        ds = dedup.build_silver(conn)
        log(f"  {ds.rows_in:,} bronze -> {ds.rows_out:,} silver "
            f"({ds.dups_dropped:,} dups dropped)")

        log("\n[2/7] gold.dim_user   <- users")
        log(f"  {enrich.stage_dim_user(conn)} rows")
        log("\n[3/7] gold.dim_time   <- distinct (date, hour) in silver")
        log(f"  {enrich.stage_dim_time(conn):,} rows")
        log("\n[4/7] gold.dim_artist <- silver artist_keys (stub-fill)")
        a = enrich.stage_dim_artist(conn)
        log(f"  {a['before']} -> {a['after']} ({a['stubs_added']} stubs)")
        log("\n[5/7] gold.dim_track  <- silver track_keys (stub-fill)")
        t = enrich.stage_dim_track(conn)
        log(f"  {t['before']} -> {t['after']} ({t['stubs_added']} stubs)")
        log("\n[6/7] gold.dim_album  <- distinct (album, artist_key) in silver")
        log(f"  {enrich.stage_dim_album(conn):,} rows")
        log("\n[7/7] gold.fact_streams <- silver.streams")
        log(f"  {enrich.stage_fact_streams(conn):,} rows")

        enrich.report_match_rates(conn)
        v1_ok = enrich.verify_v1(conn)

    log("\nRefreshing monthly_stats / top_artists / top_tracks ...")
    with engine.begin() as conn:
        conn.execute(text("SELECT refresh_all_views()"))
    log("  done")
    return v1_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the gold star schema.")
    parser.add_argument("--only", nargs="*", default=None,
                        help="Restrict to these user slugs (e.g. --only primary amit)")
    parser.add_argument("--no-land", action="store_true",
                        help="Skip landing; rebuild silver/gold from existing bronze")
    args = parser.parse_args()

    from app.db.session import make_engine
    engine = make_engine()

    if not args.no_land:
        do_landing(engine, args.only)

    v1_ok = rebuild_star(engine)
    print("\nBuild complete." if v1_ok
          else "\nBuild complete WITH V1 MISMATCH -- investigate before proceeding.")
    return 0 if v1_ok else 1


if __name__ == "__main__":
    sys.exit(main())
