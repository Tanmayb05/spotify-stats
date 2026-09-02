"""Unit tests for app/ingest/normalize.py -- pure functions, no DB/network.

Run:
    cd apps/api && python -m pytest tests/test_normalize.py -v
"""

from datetime import datetime, timezone

import pytest

from app.ingest.normalize import (
    coerce_bool,
    coerce_ms_played,
    normalize_artist_key,
    normalize_track_key,
    row_fingerprint,
    to_utc,
)


# ---------------------------------------------------------------------------
# normalize_artist_key
# ---------------------------------------------------------------------------

def test_normalize_artist_key_lowercases_and_trims():
    assert normalize_artist_key("  Justin Bieber  ") == "justin bieber"


def test_normalize_artist_key_none():
    assert normalize_artist_key(None) is None


def test_normalize_artist_key_empty_after_trim():
    assert normalize_artist_key("   ") is None


def test_normalize_artist_key_matches_case_variants():
    assert normalize_artist_key("Björk") == normalize_artist_key("BJÖRK".lower())


# ---------------------------------------------------------------------------
# normalize_track_key
# ---------------------------------------------------------------------------

def test_normalize_track_key_prefers_uri():
    key = normalize_track_key("spotify:track:abc123", "Song", "Artist")
    assert key == "spotify:track:abc123"


def test_normalize_track_key_hash_fallback_when_uri_missing():
    key = normalize_track_key(None, "My Song", "My Artist")
    assert key is not None
    assert key.startswith("hash:")
    assert len(key) == len("hash:") + 32  # md5 hex digest length


def test_normalize_track_key_fallback_is_case_insensitive_and_deterministic():
    a = normalize_track_key(None, "My Song", "My Artist")
    b = normalize_track_key(None, "  MY SONG  ", "  my artist  ")
    assert a == b


def test_normalize_track_key_none_when_nothing_usable():
    assert normalize_track_key(None, None, "Artist") is None
    assert normalize_track_key(None, "Song", None) is None
    assert normalize_track_key(None, None, None) is None


def test_normalize_track_key_empty_uri_falls_back():
    key = normalize_track_key("", "Song", "Artist")
    assert key is not None
    assert key.startswith("hash:")


# ---------------------------------------------------------------------------
# to_utc
# ---------------------------------------------------------------------------

def test_to_utc_parses_z_suffix():
    dt = to_utc("2023-06-15T10:30:00Z")
    assert dt == datetime(2023, 6, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_to_utc_parses_offset_form():
    dt = to_utc("2023-06-15T10:30:00+00:00")
    assert dt == datetime(2023, 6, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_to_utc_naive_datetime_assumed_utc():
    naive = datetime(2023, 1, 1, 12, 0, 0)
    dt = to_utc(naive)
    assert dt.tzinfo == timezone.utc


def test_to_utc_aware_datetime_passthrough():
    aware = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert to_utc(aware) is aware


def test_to_utc_none_and_garbage():
    assert to_utc(None) is None
    assert to_utc("") is None
    assert to_utc("not-a-date") is None
    assert to_utc(12345) is None


# ---------------------------------------------------------------------------
# coerce_ms_played
# ---------------------------------------------------------------------------

def test_coerce_ms_played_int():
    assert coerce_ms_played(1000) == 1000


def test_coerce_ms_played_float_string():
    assert coerce_ms_played("1500.7") == 1500


def test_coerce_ms_played_negative_clamped_to_zero():
    assert coerce_ms_played(-500) == 0


def test_coerce_ms_played_none_and_garbage():
    assert coerce_ms_played(None) == 0
    assert coerce_ms_played("not-a-number") == 0
    assert coerce_ms_played([1, 2, 3]) == 0


# ---------------------------------------------------------------------------
# coerce_bool
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        (None, False),
        (True, True),
        (False, False),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("false", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("no", False),
        (1, True),
        (0, False),
    ],
)
def test_coerce_bool(value, expected):
    assert coerce_bool(value) is expected


# ---------------------------------------------------------------------------
# row_fingerprint
# ---------------------------------------------------------------------------

def test_row_fingerprint_deterministic():
    row = {
        "user_id": "u1",
        "ts": "2023-06-15T10:30:00Z",
        "spotify_track_uri": "spotify:track:abc",
        "ms_played": 180000,
    }
    assert row_fingerprint(row) == row_fingerprint(dict(row))


def test_row_fingerprint_differs_on_ts():
    base = {
        "user_id": "u1",
        "ts": "2023-06-15T10:30:00Z",
        "spotify_track_uri": "spotify:track:abc",
        "ms_played": 180000,
    }
    other = dict(base, ts="2023-06-15T10:31:00Z")
    assert row_fingerprint(base) != row_fingerprint(other)


def test_row_fingerprint_differs_on_user():
    base = {
        "user_id": "u1",
        "ts": "2023-06-15T10:30:00Z",
        "spotify_track_uri": "spotify:track:abc",
        "ms_played": 180000,
    }
    other = dict(base, user_id="u2")
    assert row_fingerprint(base) != row_fingerprint(other)


def test_row_fingerprint_is_sha256_hex():
    row = {"user_id": "u1", "ts": None, "ms_played": 0}
    fp = row_fingerprint(row)
    assert len(fp) == 64
    int(fp, 16)  # raises if not valid hex
