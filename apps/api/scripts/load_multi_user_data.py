#!/usr/bin/env python3
"""
Load other users' Spotify Extended Streaming History into Supabase (multi-user).

Reads extracted per-user JSON from `data/other users/<slug>/Streaming_History_Audio*.json`
(produced by the extract step documented in
documentation/20260830_062639_other_users_data_scan.md), creates a `users` row per
person, strips `ip_addr` (third-party PII), keeps `conn_country`, and batch-inserts
into `streaming_history` with the new `user_id` FK.

Prerequisites:
- migrations 003_add_multi_user_support.sql + 004_user_scoped_functions.sql applied
- SUPABASE_URL + SUPABASE_SERVICE_KEY in spotify-insights.env
- `pip install supabase python-dotenv`

Idempotency: NOT an upsert (real Spotify exports contain exact-duplicate rows, so
there is no safe conflict target). Instead, a user that already has rows is skipped
unless --reload is passed, which DELETEs that user's rows first.

Usage:
    python load_multi_user_data.py                # load all 9, skip any already loaded
    python load_multi_user_data.py --only amit,sam
    python load_multi_user_data.py --reload --only sohan
    python load_multi_user_data.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

CURRENT_PATH = Path(__file__).resolve()
PACKAGE_ROOT = CURRENT_PATH.parent.parent          # apps/api
sys.path.append(str(PACKAGE_ROOT))

try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: pip install supabase python-dotenv")
    sys.exit(1)

import os

load_dotenv("spotify-insights.env")


def _find_project_root() -> Path:
    for parent in CURRENT_PATH.parents:
        if (parent / "data").exists():
            return parent
    return PACKAGE_ROOT


PROJECT_ROOT = _find_project_root()
OTHER_USERS_DIR = PROJECT_ROOT / "data" / "other users"
BATCH_SIZE = 1000

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# slug (directory name) -> display name
USERS: Dict[str, str] = {
    "abhiraj": "Abhiraj",
    "amit": "Amit",
    "antara": "Antara",
    "ash": "Ash",
    "nihal": "Nihal",
    "prathamesh": "Prathamesh",
    "sam": "Sam",
    "snehal": "Snehal",
    "sohan": "Sohan",
}


def transform_record(record: Dict[str, Any], user_id: str) -> Dict[str, Any] | None:
    """JSON record -> streaming_history row. Drops ip_addr, injects user_id."""
    if not record.get("ts"):
        return None
    return {
        "user_id": user_id,
        "ts": record["ts"],
        "platform": record.get("platform"),
        "ms_played": record.get("ms_played", 0),
        "conn_country": record.get("conn_country"),
        "ip_addr": None,  # PII: third-party IP addresses are not stored
        "master_metadata_track_name": record.get("master_metadata_track_name"),
        "master_metadata_album_artist_name": record.get("master_metadata_album_artist_name"),
        "master_metadata_album_album_name": record.get("master_metadata_album_album_name"),
        "spotify_track_uri": record.get("spotify_track_uri"),
        "episode_name": record.get("episode_name"),
        "episode_show_name": record.get("episode_show_name"),
        "spotify_episode_uri": record.get("spotify_episode_uri"),
        "audiobook_title": record.get("audiobook_title"),
        "audiobook_uri": record.get("audiobook_uri"),
        "audiobook_chapter_uri": record.get("audiobook_chapter_uri"),
        "audiobook_chapter_title": record.get("audiobook_chapter_title"),
        "reason_start": record.get("reason_start"),
        "reason_end": record.get("reason_end"),
        "shuffle": record.get("shuffle", False),
        "skipped": record.get("skipped", False),
        "offline": record.get("offline", False),
        "offline_timestamp": record.get("offline_timestamp"),
        "incognito_mode": record.get("incognito_mode", False),
    }


class MultiUserLoader:
    def __init__(self, dry_run: bool = False, reload: bool = False):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in spotify-insights.env")
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.dry_run = dry_run
        self.reload = reload

    # -- users -----------------------------------------------------------------
    def get_or_create_user(self, slug: str, display_name: str) -> str:
        resp = self.supabase.table("users").select("id").eq("username", slug).execute()
        if resp.data:
            return resp.data[0]["id"]
        if self.dry_run:
            return "00000000-0000-0000-0000-000000000000"
        resp = self.supabase.table("users").insert(
            {"username": slug, "display_name": display_name, "is_primary": False}
        ).execute()
        return resp.data[0]["id"]

    def existing_row_count(self, user_id: str) -> int:
        resp = (
            self.supabase.table("streaming_history")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return resp.count or 0

    def delete_user_rows(self, user_id: str) -> None:
        # RPC from 004: truncate_streaming_history(p_user_id) -> DELETE WHERE user_id = p_user_id
        self.supabase.rpc("truncate_streaming_history", {"p_user_id": user_id}).execute()

    # -- json ----------------------------------------------------------------
    @staticmethod
    def load_json_for(slug: str) -> List[Dict[str, Any]]:
        user_dir = OTHER_USERS_DIR / slug
        files = sorted(user_dir.glob("Streaming_History_Audio*.json"))
        records: List[Dict[str, Any]] = []
        for fp in files:
            with open(fp, "r", encoding="utf-8") as f:
                records.extend(json.load(f))
        return records

    # -- insert ------------------------------------------------------------
    def insert_rows(self, rows: List[Dict[str, Any]]) -> int:
        inserted = 0
        batches = [rows[i : i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
        for i, batch in enumerate(batches, 1):
            self.supabase.table("streaming_history").insert(batch).execute()
            inserted += len(batch)
            print(f"      [{i}/{len(batches)}] {inserted:,}/{len(rows):,}", end="\r")
        print()
        return inserted

    # -- per user ----------------------------------------------------------
    def load_user(self, slug: str, display_name: str) -> None:
        print(f"\n=== {slug} ({display_name}) ===")
        records = self.load_json_for(slug)
        if not records:
            print(f"  no JSON found in {OTHER_USERS_DIR / slug} - skipping")
            return
        print(f"  {len(records):,} records in JSON")

        user_id = self.get_or_create_user(slug, display_name)
        existing = 0 if self.dry_run else self.existing_row_count(user_id)

        if existing > 0:
            if not self.reload:
                print(f"  user already has {existing:,} rows - skipping (use --reload to replace)")
                return
            print(f"  --reload: deleting {existing:,} existing rows")
            if not self.dry_run:
                self.delete_user_rows(user_id)

        rows = [r for r in (transform_record(rec, user_id) for rec in records) if r]
        music = sum(1 for r in rows if r["spotify_track_uri"])
        print(f"  {len(rows):,} valid rows ({music:,} music / {len(rows) - music:,} podcast/other)")

        if self.dry_run:
            print("  [dry-run] not inserting")
            return

        n = self.insert_rows(rows)
        print(f"  inserted {n:,} rows")
        self._summarize(user_id, slug)

    def _summarize(self, user_id: str, slug: str) -> None:
        rng = self.supabase.rpc("get_date_range", {"p_user_id": user_id}).execute()
        if rng.data:
            d = rng.data[0]
            print(f"  range: {str(d['min_date'])[:10]} -> {str(d['max_date'])[:10]}")

    # -- orchestration ---------------------------------------------------
    def run(self, slugs: List[str]) -> None:
        for slug in slugs:
            self.load_user(slug, USERS[slug])
        if self.dry_run:
            print("\n[dry-run] skipping view refresh")
            return
        print("\nRefreshing materialized views (all users)...")
        try:
            self.supabase.rpc("refresh_all_views").execute()
            print("done.")
        except Exception as e:  # PostgREST statement timeout on large refreshes
            print(f"  view refresh via RPC failed ({e}).")
            print("  Run this instead (no timeout):")
            print('    psql "$SUPABASE_DIRECT_CONN" -c "SELECT refresh_all_views();"')
            print("  or per-view: REFRESH MATERIALIZED VIEW monthly_stats; top_artists; top_tracks;")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma-separated slugs (default: all 9)")
    ap.add_argument("--dry-run", action="store_true", help="parse + report, no writes")
    ap.add_argument("--reload", action="store_true", help="delete a user's rows before reloading")
    args = ap.parse_args()

    if args.only:
        slugs = [s.strip() for s in args.only.split(",")]
        bad = [s for s in slugs if s not in USERS]
        if bad:
            print(f"unknown slug(s): {bad}. valid: {sorted(USERS)}")
            sys.exit(1)
    else:
        slugs = list(USERS)

    print("=" * 60)
    print("Multi-user Spotify data load")
    print(f"  users:   {', '.join(slugs)}")
    print(f"  dry-run: {args.dry_run}   reload: {args.reload}")
    print("=" * 60)

    loader = MultiUserLoader(dry_run=args.dry_run, reload=args.reload)
    try:
        loader.run(slugs)
    except KeyboardInterrupt:
        print("\ninterrupted - partial user data may be present; re-run with --reload --only <slug>")
        sys.exit(1)


if __name__ == "__main__":
    main()
