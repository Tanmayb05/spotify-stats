"""Unit tests for app/ingest/validate.py -- Pandera schema, no DB.

The malformed fixture (data/fixtures/malformed_streaming_history.json) is the
V3 gate: 7 array elements -> 6 quarantined (6 distinct rules) + 1 landed.
Real data trips none of these rules, so this fixture is what exercises the lane.
"""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.ingest.validate import validate_rows

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "fixtures"
MALFORMED = FIXTURES / "malformed_streaming_history.json"
FULL = FIXTURES / "sample_streaming_history_full.json"


@pytest.fixture
def malformed_rows():
    return json.loads(MALFORMED.read_text())


def test_malformed_fixture_v3_gate(malformed_rows):
    out = validate_rows(malformed_rows, source_file="m.json", user_id=uuid4())
    assert len(out.valid) == 1
    assert len(out.quarantined) == 6
    assert len({q.rule for q in out.quarantined}) == 6


def test_malformed_fixture_rule_vocabulary(malformed_rows):
    out = validate_rows(malformed_rows, source_file="m.json", user_id=uuid4())
    rules = {q.rule for q in out.quarantined}
    assert rules == {
        "ts_missing",
        "ts_unparseable",
        "ms_played_range",
        "row_not_a_dict",
        "music_row_track_name",
        "platform_type",
    }


def test_clean_control_row_lands(malformed_rows):
    out = validate_rows(malformed_rows, source_file="m.json", user_id=uuid4())
    assert out.valid[0]["master_metadata_track_name"] == "Clean Control Row"


def test_ms_played_missing_is_not_a_reject():
    rows = [{"ts": "2023-01-01T00:00:00Z", "master_metadata_track_name": "x",
             "spotify_track_uri": "spotify:track:x"}]
    out = validate_rows(rows, source_file="m.json", user_id=uuid4())
    assert len(out.valid) == 1


def test_negative_and_over_day_ms_both_ms_played_range():
    rows = [
        {"ts": "2023-01-01T00:00:00Z", "ms_played": -1, "master_metadata_track_name": "a",
         "spotify_track_uri": "spotify:track:a"},
        {"ts": "2023-01-01T01:00:00Z", "ms_played": 86_400_001, "master_metadata_track_name": "b",
         "spotify_track_uri": "spotify:track:b"},
    ]
    out = validate_rows(rows, source_file="m.json", user_id=uuid4())
    assert len(out.quarantined) == 2
    assert all(q.rule == "ms_played_range" for q in out.quarantined)


def test_full_fixture_all_valid_one_warn():
    rows = json.loads(FULL.read_text())
    out = validate_rows(rows, source_file="full.json", user_id=uuid4())
    assert len(out.quarantined) == 0
    assert len(out.valid) == len(rows)
    assert out.warn_counts.get("reason_start_enum") == 1


def test_podcast_and_audiobook_rows_are_not_music_row_rejects():
    """A row with no spotify_track_uri and no track name is a podcast/audiobook
    row -- it must NOT trip music_row_track_name (that rule only fires when a
    track URI is present)."""
    rows = [
        {"ts": "2023-01-01T00:00:00Z", "ms_played": 1000, "episode_name": "Ep 1",
         "spotify_episode_uri": "spotify:episode:x"},
        {"ts": "2023-01-01T01:00:00Z", "ms_played": 1000, "audiobook_title": "Book",
         "audiobook_uri": "spotify:show:x"},
    ]
    out = validate_rows(rows, source_file="m.json", user_id=uuid4())
    assert len(out.quarantined) == 0
    assert len(out.valid) == 2
