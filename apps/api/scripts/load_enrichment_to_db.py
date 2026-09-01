#!/usr/bin/env python3
"""Load on-disk enrichment JSON into gold dimension tables.

    python scripts/load_enrichment_to_db.py                 # all 3 sources
    python scripts/load_enrichment_to_db.py --dry-run        # counts only, no writes
    python scripts/load_enrichment_to_db.py --only artists   # one source

Sources (all under outputs/, gitignored, absent on a fresh clone -- a missing
file is a warning + skip, never a failure; exit code stays 0):

  outputs/data/artists_info.json  -> gold.dim_artist   (~4,216 artists)
  outputs/data/songs_info.json    -> gold.dim_track     (~808 salvageable --
                                      the file is a confirmed truncated write,
                                      see app/ingest/salvage.salvage_json_array)
  outputs/lyrics/lyrics.json      -> gold.track_lyrics  (~5,858 tracks,
                                      METADATA ONLY -- Decision D4. The lyrics
                                      text is read in-memory to compute
                                      word_count, then discarded. It is never
                                      written to any column, table, or log.)

Idempotent: every write is `ON CONFLICT (...) DO UPDATE`, so re-running after
a source file changes just refreshes the rows. dim_track/dim_artist FKs are
NOT required to pre-exist here -- gold.dim_track.artist_key is only set when
a matching gold.dim_artist row exists (LEFT JOIN semantics via a pre-pass);
build_star_schema.py (step 6) is what actually links fact rows to dims by key.

This script only *populates dimensions*; it does not touch gold.fact_streams.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.ingest.normalize import normalize_artist_key, normalize_track_key  # noqa: E402
from app.ingest.salvage import salvage_json_array  # noqa: E402


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "outputs").exists() or (parent / "data").exists():
            return parent
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _find_project_root()
OUTPUTS_DATA_DIR = PROJECT_ROOT / "outputs" / "data"
OUTPUTS_LYRICS_DIR = PROJECT_ROOT / "outputs" / "lyrics"

ARTISTS_FILE = OUTPUTS_DATA_DIR / "artists_info.json"
SONGS_FILE = OUTPUTS_DATA_DIR / "songs_info.json"
LYRICS_FILE = OUTPUTS_LYRICS_DIR / "lyrics.json"


# ---------------------------------------------------------------------------
# artists_info.json -> gold.dim_artist
# ---------------------------------------------------------------------------

def load_artists(conn, dry_run: bool) -> int:
    if not ARTISTS_FILE.exists():
        print(f"  [artists] SKIP: not found at {ARTISTS_FILE}")
        return 0

    artists = salvage_json_array(ARTISTS_FILE, "artists")
    print(f"  [artists] {len(artists)} records read")

    rows: List[Dict[str, Any]] = []
    for a in artists:
        name = a.get("artist_name")
        key = normalize_artist_key(name)
        if not key:
            continue
        genres = a.get("genres") or []
        rows.append({
            "artist_key": key,
            "artist_name": name,
            "spotify_artist_id": a.get("artist_id"),
            "genres": genres if genres else None,
            "popularity": a.get("popularity"),
            "followers": a.get("followers"),
        })

    print(f"  [artists] {len(rows)} usable after key normalization")
    if dry_run or not rows:
        return len(rows)

    stmt = text("""
        INSERT INTO gold.dim_artist
            (artist_key, artist_name, spotify_artist_id, genres, popularity, followers, updated_at)
        VALUES
            (:artist_key, :artist_name, :spotify_artist_id, :genres, :popularity, :followers, now())
        ON CONFLICT (artist_key) DO UPDATE SET
            artist_name        = EXCLUDED.artist_name,
            spotify_artist_id  = COALESCE(EXCLUDED.spotify_artist_id, gold.dim_artist.spotify_artist_id),
            genres              = COALESCE(EXCLUDED.genres, gold.dim_artist.genres),
            popularity          = COALESCE(EXCLUDED.popularity, gold.dim_artist.popularity),
            followers           = COALESCE(EXCLUDED.followers, gold.dim_artist.followers),
            updated_at          = now()
    """)
    for row in rows:
        conn.execute(stmt, row)
    return len(rows)


# ---------------------------------------------------------------------------
# songs_info.json -> gold.dim_track (audio_source='enriched')
# ---------------------------------------------------------------------------

def load_songs(conn, dry_run: bool) -> int:
    if not SONGS_FILE.exists():
        print(f"  [songs] SKIP: not found at {SONGS_FILE}")
        return 0

    songs = salvage_json_array(SONGS_FILE, "songs")
    print(f"  [songs] {len(songs)} records salvaged (file is a known truncated write)")

    rows: List[Dict[str, Any]] = []
    for s in songs:
        uri = s.get("track_uri") or s.get("track_id")
        track_name = s.get("track_name")
        artist_name = s.get("artist_name")
        track_key = normalize_track_key(uri, track_name, artist_name)
        if not track_key:
            continue

        ti = s.get("track_info") if isinstance(s.get("track_info"), dict) else {}
        album = ti.get("album") if isinstance(ti.get("album"), dict) else {}
        release_date = album.get("release_date") or ""
        release_year: Optional[int] = None
        if release_date[:4].isdigit():
            release_year = int(release_date[:4])

        artist_key = normalize_artist_key(artist_name)

        rows.append({
            "track_key": track_key,
            "spotify_track_uri": uri,
            "track_name": track_name or (ti.get("name") or "Unknown"),
            "artist_key": artist_key,
            "artist_name": artist_name,
            "album_name": s.get("album_name") or album.get("name"),
            "duration_ms": ti.get("duration_ms"),
            "explicit": bool(ti.get("explicit")) if ti.get("explicit") is not None else None,
            "popularity": ti.get("popularity"),
            "release_year": release_year,
        })

    print(f"  [songs] {len(rows)} usable after key normalization")
    if dry_run or not rows:
        return len(rows)

    stmt = text("""
        INSERT INTO gold.dim_track
            (track_key, spotify_track_uri, track_name, artist_key, artist_name,
             album_name, duration_ms, explicit, popularity, release_year,
             audio_source, updated_at)
        VALUES
            (:track_key, :spotify_track_uri, :track_name, :artist_key, :artist_name,
             :album_name, :duration_ms, :explicit, :popularity, :release_year,
             'enriched', now())
        ON CONFLICT (track_key) DO UPDATE SET
            spotify_track_uri = COALESCE(EXCLUDED.spotify_track_uri, gold.dim_track.spotify_track_uri),
            track_name        = EXCLUDED.track_name,
            artist_key        = COALESCE(EXCLUDED.artist_key, gold.dim_track.artist_key),
            artist_name       = EXCLUDED.artist_name,
            album_name        = EXCLUDED.album_name,
            duration_ms       = COALESCE(EXCLUDED.duration_ms, gold.dim_track.duration_ms),
            explicit          = COALESCE(EXCLUDED.explicit, gold.dim_track.explicit),
            popularity        = COALESCE(EXCLUDED.popularity, gold.dim_track.popularity),
            release_year      = COALESCE(EXCLUDED.release_year, gold.dim_track.release_year),
            audio_source      = 'enriched',
            updated_at        = now()
    """)
    # dim_track.artist_key has a FK to dim_artist; skip rows whose artist_key
    # is not (yet) in dim_artist rather than failing the whole batch -- the
    # loader may run artists before songs, but robustness matters if not.
    known_artist_keys = set(
        r[0] for r in conn.execute(text("SELECT artist_key FROM gold.dim_artist")).fetchall()
    )
    for row in rows:
        if row["artist_key"] and row["artist_key"] not in known_artist_keys:
            row["artist_key"] = None
        conn.execute(stmt, row)
    return len(rows)


# ---------------------------------------------------------------------------
# lyrics.json -> gold.track_lyrics (METADATA ONLY -- Decision D4)
# ---------------------------------------------------------------------------

def load_lyrics(conn, dry_run: bool) -> int:
    """Read lyrics.json, compute has_lyrics/word_count, DISCARD the text.

    D4: no lyrics text is ever written to a variable that outlives this
    function's loop body, logged, or persisted. `lang` ships NULL -- no
    language-detection library is a dependency of this repo, and a wrong
    guess is worse than an honest unknown.
    """
    if not LYRICS_FILE.exists():
        print(f"  [lyrics] SKIP: not found at {LYRICS_FILE}")
        return 0

    import json
    try:
        payload = json.loads(LYRICS_FILE.read_text(encoding="utf-8"))
        tracks = payload.get("tracks", []) if isinstance(payload, dict) else []
    except Exception as exc:
        print(f"  [lyrics] SKIP: could not parse {LYRICS_FILE}: {exc}")
        return 0

    print(f"  [lyrics] {len(tracks)} records read")

    rows: List[Dict[str, Any]] = []
    for t in tracks:
        uri = t.get("track_uri") or t.get("track_id")
        track_key = normalize_track_key(uri, t.get("track_name"), t.get("artist_name"))
        if not track_key:
            continue
        lyrics_obj = t.get("lyrics") if isinstance(t.get("lyrics"), dict) else {}
        body = lyrics_obj.get("lyrics_body") or ""
        word_count = len(body.split()) if body else 0
        has_lyrics = bool(body)
        source = t.get("lyrics_source")
        rows.append({
            "track_key": track_key,
            "has_lyrics": has_lyrics,
            "source": source,
            "lang": None,  # no detector dependency in this repo; honest unknown
            "word_count": word_count,
        })
        # `body` goes out of scope at the next loop iteration; never appended
        # to `rows` or any other structure that survives this function.

    print(f"  [lyrics] {len(rows)} usable after key normalization")
    if dry_run or not rows:
        return len(rows)

    known_track_keys = set(
        r[0] for r in conn.execute(text("SELECT track_key FROM gold.dim_track")).fetchall()
    )
    stmt = text("""
        INSERT INTO gold.track_lyrics (track_key, has_lyrics, source, lang, word_count, updated_at)
        VALUES (:track_key, :has_lyrics, :source, :lang, :word_count, now())
        ON CONFLICT (track_key) DO UPDATE SET
            has_lyrics = EXCLUDED.has_lyrics,
            source     = EXCLUDED.source,
            lang       = EXCLUDED.lang,
            word_count = EXCLUDED.word_count,
            updated_at = now()
    """)
    inserted = 0
    for row in rows:
        if row["track_key"] not in known_track_keys:
            # track_lyrics.track_key FKs to dim_track; skip tracks not enriched
            # via songs_info.json (dim_track is enrichment-only in Phase 11,
            # not every play has a dim_track row yet -- build_star_schema.py
            # step 6 creates the rest from streaming history).
            continue
        conn.execute(stmt, row)
        inserted += 1
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report counts, write nothing")
    parser.add_argument(
        "--only", choices=["artists", "songs", "lyrics"], default=None,
        help="Load only one source",
    )
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    from app.db.session import make_engine

    engine = make_engine(args.database_url)

    sources = [args.only] if args.only else ["artists", "songs", "lyrics"]
    print(f"Loading enrichment sources: {sources}{' (dry-run)' if args.dry_run else ''}")

    counts: Dict[str, int] = {}
    conn = engine.connect()
    trans = conn.begin()
    try:
        has_gold = conn.execute(text("SELECT to_regclass('gold.dim_artist')")).scalar()
        if not has_gold:
            print("gold.dim_artist does not exist. Run: python db/migrate.py")
            trans.rollback()
            return 1

        if "artists" in sources:
            counts["artists"] = load_artists(conn, args.dry_run)
        if "songs" in sources:
            counts["songs"] = load_songs(conn, args.dry_run)
        if "lyrics" in sources:
            counts["lyrics"] = load_lyrics(conn, args.dry_run)

        if args.dry_run:
            trans.rollback()  # dry-run must write nothing
        else:
            trans.commit()
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()

    print("\nDone." if not args.dry_run else "\nDry run complete (no writes).")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
