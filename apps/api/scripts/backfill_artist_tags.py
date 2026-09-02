#!/usr/bin/env python3
"""Opt-in genre-tag backfill for artists with no Spotify-reported genres.

Decision D5 (Phase 11 plan): this is a SEPARATE, OPT-IN script, never part of
build_star_schema.py or any migration. It is the only network-calling script
in this phase. It is fully skippable -- the phase completes with no network
access and no API key, just with lower genre coverage (recorded, not hidden).

    python scripts/backfill_artist_tags.py                  # MusicBrainz only
    python scripts/backfill_artist_tags.py --limit 20        # smoke run
    python scripts/backfill_artist_tags.py --skip-backfill   # no-op, exit 0
    LASTFM_API_KEY=... python scripts/backfill_artist_tags.py  # + Last.fm

Sources, in order per artist (first hit wins, both are tried if the first is
empty and a Last.fm key is configured):
  1. MusicBrainz (https://musicbrainz.org/ws/2/) -- no API key, tag genres.
  2. Last.fm (http://ws.audioscrobbler.com/2.0/) -- needs LASTFM_API_KEY
     (app/config.py), artist.getTopTags.

Rate limit: 1 request/second (MusicBrainz's documented courtesy limit), a
real User-Agent (MusicBrainz rejects/blocks generic ones), resumable (results
cache to gitignored outputs/enrichment/artist_tags.json; a re-run skips
artists already cached unless --force).

Prints coverage-of-plays BEFORE and AFTER the run -- that printed number is
the input to the Phase 11 plan's Decision D2 genre-affinity kill gate
(>= 75% keep, 60-75% keep-degraded, < 60% cut user_genre_affinity in Phase 14).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402

USER_AGENT = "spotify-insights/0.1 (personal analytics project; contact via GitHub issues)"
MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/artist/"
LASTFM_URL = "http://ws.audioscrobbler.com/2.0/"
RATE_LIMIT_SECONDS = 1.0


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "outputs").exists() or (parent / "data").exists():
            return parent
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _find_project_root()
CACHE_PATH = PROJECT_ROOT / "outputs" / "enrichment" / "artist_tags.json"


def load_cache() -> Dict[str, List[str]]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_cache(cache: Dict[str, List[str]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def fetch_musicbrainz_tags(artist_name: str, session) -> List[str]:
    """Query MusicBrainz for an artist's tags. Returns [] on any failure --
    a network error here must never crash the whole backfill run."""
    try:
        resp = session.get(
            MUSICBRAINZ_URL,
            params={"query": f'artist:"{artist_name}"', "fmt": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        artists = data.get("artists") or []
        if not artists:
            return []
        tags = artists[0].get("tags") or []
        # Sort by MusicBrainz's own "count" (vote weight), most-voted first.
        tags = sorted(tags, key=lambda t: t.get("count", 0), reverse=True)
        return [t["name"] for t in tags if t.get("name")]
    except Exception:
        return []


def fetch_lastfm_tags(artist_name: str, api_key: str, session) -> List[str]:
    try:
        resp = session.get(
            LASTFM_URL,
            params={
                "method": "artist.getTopTags",
                "artist": artist_name,
                "api_key": api_key,
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        tags = (data.get("toptags") or {}).get("tag") or []
        return [t["name"] for t in tags if t.get("name")]
    except Exception:
        return []


def measure_coverage(conn) -> float:
    """Coverage-of-plays: % of plays whose artist has a non-empty genres OR
    genres_enriched array. Matches the pre-backfill measurement in the Phase
    11 plan (53.1%) exactly in formula.
    """
    row = conn.execute(text("""
        WITH plays AS (
            SELECT lower(trim(master_metadata_album_artist_name)) AS artist_key
            FROM streaming_history
            WHERE master_metadata_album_artist_name IS NOT NULL
        )
        SELECT
            count(*) AS total_plays,
            count(*) FILTER (
                WHERE (a.genres IS NOT NULL AND array_length(a.genres, 1) > 0)
                   OR (a.genres_enriched IS NOT NULL AND array_length(a.genres_enriched, 1) > 0)
            ) AS plays_with_genre
        FROM plays p
        LEFT JOIN gold.dim_artist a ON a.artist_key = p.artist_key
    """)).mappings().one()
    total = row["total_plays"] or 0
    covered = row["plays_with_genre"] or 0
    return round(100.0 * covered / total, 1) if total else 0.0


def artists_needing_backfill(conn) -> List[Dict[str, Any]]:
    """Artists with no Spotify-reported genres, ordered by play count desc so
    the highest-impact artists (on coverage-of-plays) are backfilled first --
    important for --limit smoke runs and for a run interrupted partway.
    """
    rows = conn.execute(text("""
        SELECT
            a.artist_key,
            a.artist_name,
            COALESCE(p.play_count, 0) AS play_count
        FROM gold.dim_artist a
        LEFT JOIN (
            SELECT lower(trim(master_metadata_album_artist_name)) AS artist_key,
                   COUNT(*) AS play_count
            FROM streaming_history
            WHERE master_metadata_album_artist_name IS NOT NULL
            GROUP BY 1
        ) p ON p.artist_key = a.artist_key
        WHERE a.genres IS NULL OR array_length(a.genres, 1) IS NULL OR array_length(a.genres, 1) = 0
        ORDER BY play_count DESC NULLS LAST, a.artist_key
    """)).mappings().all()
    return [dict(r) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-backfill", action="store_true",
                         help="No-op; exit 0 immediately. For CI / offline runs.")
    parser.add_argument("--limit", type=int, default=None,
                         help="Only process the top N artists by play count (smoke run).")
    parser.add_argument("--force", action="store_true",
                         help="Re-query artists already present in the cache.")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    if args.skip_backfill:
        print("--skip-backfill set: no-op, exiting 0.")
        return 0

    try:
        import requests
    except ImportError:
        print("The 'requests' package is required for this script "
              "(pip install requests). Skipping backfill; the phase does "
              "not require this script to succeed.")
        return 0

    from app.db.session import make_engine

    engine = make_engine(args.database_url)

    # Each DB touch below is its OWN short transaction (engine.begin() per
    # call), not one transaction wrapping the whole ~30+ minute run. A run
    # that holds a single open transaction for the network-bound duration of
    # 1000+ sequential HTTP calls blocks every other writer (build_star_schema.py,
    # concurrent seeding) for that entire window, and losing the process
    # (Ctrl-C, crash) would roll back every UPDATE done so far even though the
    # on-disk tag cache had already checkpointed. Short-lived per-artist
    # transactions make progress durable and this script a good citizen next
    # to concurrent writers.
    with engine.begin() as conn:
        has_gold = conn.execute(text("SELECT to_regclass('gold.dim_artist')")).scalar()
        if not has_gold:
            print("gold.dim_artist does not exist. Run: python db/migrate.py "
                  "and scripts/load_enrichment_to_db.py first.")
            return 1

    with engine.begin() as conn:
        before = measure_coverage(conn)
    print(f"Genre coverage-of-plays BEFORE backfill: {before}%")

    with engine.begin() as conn:
        targets = artists_needing_backfill(conn)
    if args.limit:
        targets = targets[: args.limit]
    print(f"{len(targets)} artist(s) with no Spotify-reported genres "
          f"({'limited to top ' + str(args.limit) + ' by plays' if args.limit else 'all'})")

    cache = load_cache()
    session = requests.Session()
    lastfm_key = settings.lastfm_api_key

    updated = 0
    for i, artist in enumerate(targets):
        key = artist["artist_key"]
        name = artist["artist_name"]

        if key in cache and not args.force:
            tags = cache[key]
        else:
            tags = fetch_musicbrainz_tags(name, session)
            if not tags and lastfm_key:
                tags = fetch_lastfm_tags(name, lastfm_key, session)
            cache[key] = tags
            time.sleep(RATE_LIMIT_SECONDS)  # MusicBrainz's documented courtesy limit

            if (i + 1) % 25 == 0:
                save_cache(cache)  # checkpoint periodically so a long run is resumable
                print(f"  ... {i + 1}/{len(targets)} ({updated} with tags so far)")

        if tags:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE gold.dim_artist
                        SET genres_enriched = :tags, updated_at = now()
                        WHERE artist_key = :key
                    """),
                    {"tags": tags, "key": key},
                )
            updated += 1

    save_cache(cache)
    with engine.begin() as conn:
        after = measure_coverage(conn)

    print(f"\nBackfilled {updated}/{len(targets)} artists with at least one tag.")
    print(f"Genre coverage-of-plays AFTER backfill: {after}%")
    print(f"Cache: {CACHE_PATH}")

    # Decision D2 verdict, printed so it can be copied into DATA_MODEL.md / UPDATE.md.
    if after >= 75.0:
        verdict = "KEEP user_genre_affinity as a Phase 14 feature."
    elif after >= 60.0:
        verdict = "KEEP, degraded -- surface a `coverage` field and 'based on N% of plays' in the UI."
    else:
        verdict = "CUT -- record as a ROADMAP DEVIATION against Phase 14."
    print(f"D2 verdict at {after}% coverage: {verdict}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
