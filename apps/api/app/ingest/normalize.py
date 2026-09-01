"""Pure normalization functions for one streaming-history row.

No DB access, no I/O -- these are unit-testable in isolation (see
apps/api/tests/test_normalize.py). Extracted from what was inline logic in
scripts/seed_local_db.py (Phase 10's own note assigned this file to Phase 11).

Used by:
  * scripts/seed_local_db.py       -- row validity + boolean coercion
  * scripts/build_star_schema.py   -- artist_key/track_key/to_utc for the
                                       bronze -> silver -> gold build
  * app/ingest/salvage.py callers  -- release-year parsing conventions match
                                       data_loader.py's existing normalization

row_fingerprint is defined here now but not yet *used* -- Phase 12's dedup.py
consumes it to collapse genuine export duplicates (Decision D6 in the Phase 11
plan explicitly defers dedup so this phase's "numbers unchanged" gate stays
meaningful: fact_streams must equal streaming_history 1:1 for now).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional


def normalize_artist_key(artist_name: Optional[str]) -> Optional[str]:
    """lower(trim(artist_name)) -- the natural key for gold.dim_artist (D3).

    Matches data_loader.py's existing normalization exactly (the recommender's
    artist-metadata lookup already keys on `name.strip().lower()`), so the
    on-disk enrichment (artists_info.json) joins without a second convention.
    """
    if artist_name is None:
        return None
    key = artist_name.strip().lower()
    return key or None


def normalize_track_key(
    spotify_track_uri: Optional[str],
    track_name: Optional[str],
    artist_name: Optional[str],
) -> Optional[str]:
    """track_key = spotify_track_uri when present, else a hash fallback (D3).

    The hash fallback mirrors the recommender's existing "name|||artist"
    convention (data_loader.py) so the two agree, but is hashed here to give
    every dim_track row a bounded-length, collision-resistant primary key
    ('hash:' || md5(...)) instead of an unbounded concatenated string.

    Returns None only when there is no track_uri AND no usable
    (track_name, artist_name) pair -- e.g. a bare podcast/audiobook row.
    """
    if spotify_track_uri:
        return spotify_track_uri
    if not track_name or not artist_name:
        return None
    basis = f"{track_name.strip().lower()}|||{artist_name.strip().lower()}"
    return "hash:" + hashlib.md5(basis.encode("utf-8")).hexdigest()


def to_utc(ts: Any) -> Optional[datetime]:
    """Parse a Spotify export timestamp (ISO-8601, usually already UTC 'Z')
    into a timezone-aware UTC datetime. Returns None for anything unparsable.

    Accepts a datetime (assumed UTC if naive) or an ISO-8601 string.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if isinstance(ts, str):
        raw = ts.strip()
        if not raw:
            return None
        # Spotify exports use a trailing 'Z'; datetime.fromisoformat wants '+00:00'
        # (Python < 3.11 does not understand 'Z' directly).
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def coerce_ms_played(value: Any) -> int:
    """Spotify's ms_played is sometimes a float, string, or missing. Coerce to
    a non-negative int, defaulting to 0 for anything unusable (never raises).
    """
    if value is None:
        return 0
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, n)


def coerce_bool(value: Any) -> bool:
    """Export booleans are nullable in some files but NOT NULL-defaulted in
    the schema (matches seed_local_db.py's existing per-flag handling).
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "t", "1", "yes")
    return bool(value)


def row_fingerprint(row: dict) -> str:
    """Stable fingerprint of one play event for dedup (Phase 12's dedup.py).

    Not used within Phase 11 (Decision D6: this phase does not dedup so that
    fact_streams count == source count stays an exact, checkable equality).
    Defined here so Phase 12 has one canonical definition to import rather
    than re-deriving the field set.

    Basis: (user_id, ts, spotify_track_uri or track_key fallback, ms_played) --
    the tuple that, if repeated exactly, means either a genuine repeat play or
    an export-level duplicate row (the two are indistinguishable without this
    fingerprint; Phase 12 documents its own tie-breaking rule for which one
    survives).
    """
    user_id = str(row.get("user_id") or "")
    ts = row.get("ts")
    ts_key = to_utc(ts)
    ts_str = ts_key.isoformat() if ts_key else str(ts or "")
    track_key = normalize_track_key(
        row.get("spotify_track_uri"),
        row.get("master_metadata_track_name") or row.get("track_name"),
        row.get("master_metadata_album_artist_name") or row.get("artist_name"),
    ) or ""
    ms_played = coerce_ms_played(row.get("ms_played"))
    basis = f"{user_id}|{ts_str}|{track_key}|{ms_played}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
