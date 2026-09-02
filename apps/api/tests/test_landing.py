"""Tests for app/ingest/landing.py.

Split in two:
  * pure tests (read_export, ip_addr strip on the built _raw dict) -- always run
  * DB-backed tests -- skipped unless DATABASE_URL is set (a local Postgres with
    migrations 001-011 applied)
"""

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text

from app.ingest.discover import discover_files
from app.ingest.landing import _insert_batch, land_file, read_export
from app.ingest.normalize import row_fingerprint

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "fixtures"
FULL = FIXTURES / "sample_streaming_history_full.json"

DB_URL = os.getenv("DATABASE_URL")
db_only = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")


# --------------------------------------------------------------------------- #
# pure                                                                        #
# --------------------------------------------------------------------------- #
def test_read_export_wraps_non_dict_elements(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('[{"ts":"2023-01-01T00:00:00Z"}, "a bare string", 42]')
    rows = read_export(p)
    assert rows[0]["ts"] == "2023-01-01T00:00:00Z"
    assert "__not_a_dict__" in rows[1]
    assert "__not_a_dict__" in rows[2]


def test_read_export_salvages_truncated_array(tmp_path):
    p = tmp_path / "trunc.json"
    p.write_text('[{"ts":"2023-01-01T00:00:00Z","ms_played":1},{"ts":"2023-01-02T00:00:00')
    rows = read_export(p)
    assert len(rows) == 1
    assert rows[0]["ms_played"] == 1


def test_full_fixture_has_ip_addr_to_strip():
    """Guard: the highest-value fixture must actually contain ip_addr, else the
    strip assertion below is vacuous."""
    rows = json.loads(FULL.read_text())
    assert any("ip_addr" in r for r in rows)


class _CaptureConn:
    """Minimal stand-in that records the params handed to execute()."""
    def __init__(self):
        self.calls = []

    def execute(self, _stmt, params=None):
        self.calls.append(params)
        class _R:
            rowcount = len(params) if isinstance(params, list) else 0
        return _R()


def test_insert_batch_strips_ip_addr_from_raw():
    rows = json.loads(FULL.read_text())
    batch = []
    for r in rows:
        rr = dict(r)
        rr["user_id"] = "u1"
        rr["_fp"] = row_fingerprint(rr)
        rr["_ts"] = None
        batch.append(rr)
    conn = _CaptureConn()
    _insert_batch(conn, batch, "full.json", None)
    params = conn.calls[0]
    for p in params:
        raw = json.loads(p["raw"])
        assert "ip_addr" not in raw, "ip_addr must never reach bronze._raw (V8)"


# --------------------------------------------------------------------------- #
# DB-backed                                                                   #
# --------------------------------------------------------------------------- #
@pytest.fixture
def engine():
    from app.db.session import make_engine
    return make_engine(DB_URL)


@db_only
def test_v8_no_ip_addr_in_bronze(engine):
    with engine.connect() as conn:
        n = conn.execute(
            text("SELECT count(*) FROM bronze.raw_streams WHERE _raw ? 'ip_addr'")
        ).scalar_one()
    assert n == 0


@db_only
def test_file_hash_skip_is_idempotent(engine):
    """Landing the same discovered file twice: second call is skipped, no new
    bronze rows."""
    files = discover_files(only=["primary"])
    if not files:
        pytest.skip("no primary export files on disk")
    df = files[0]
    from app.ingest.landing import get_or_create_user, user_watermark

    with engine.begin() as conn:
        uid = get_or_create_user(conn, df.slug, df.display_name, df.is_primary)
        wm = user_watermark(conn, uid)
        before = conn.execute(
            text("SELECT count(*) FROM bronze.raw_streams WHERE user_id = :u"),
            {"u": str(uid)},
        ).scalar_one()

    with engine.begin() as conn:
        res = land_file(conn, df, uid, None, wm)
    assert res.skipped_reason == "file_hash_seen"

    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT count(*) FROM bronze.raw_streams WHERE user_id = :u"),
            {"u": str(uid)},
        ).scalar_one()
    assert after == before
