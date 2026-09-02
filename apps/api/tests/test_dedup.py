"""Tests for app/ingest/dedup.py.

DEDUP_SELECT_SQL shape is asserted statically; the actual collapse + tie-break
are DB-backed (skipped unless DATABASE_URL is set with migrations 001-011).
"""

import os

import pytest
from sqlalchemy import text

from app.ingest.dedup import DEDUP_SELECT_SQL, build_silver, dedup_report

DB_URL = os.getenv("DATABASE_URL")
db_only = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")


def test_dedup_sql_partitions_on_user_and_fingerprint_ordered_by_ingest_id():
    s = " ".join(DEDUP_SELECT_SQL.split())
    assert "PARTITION BY b.user_id, b.row_fingerprint" in s
    assert "ORDER BY b._ingest_id" in s
    assert "WHERE d._rn = 1" in s
    assert "b.ts IS NOT NULL" in s


@pytest.fixture
def engine():
    from app.db.session import make_engine
    return make_engine(DB_URL)


@db_only
def test_silver_equals_bronze_minus_dups_per_user(engine):
    with engine.begin() as conn:
        stats = build_silver(conn)
    assert stats.rows_out == stats.rows_in - stats.dups_dropped
    for u in stats.per_user:
        assert u["silver"] == u["bronze"] - u["dups_dropped"]


@db_only
def test_dedup_is_deterministic_across_two_rebuilds(engine):
    with engine.begin() as conn:
        a = build_silver(conn)
    with engine.begin() as conn:
        b = build_silver(conn)
    assert (a.rows_in, a.rows_out, a.dups_dropped) == (b.rows_in, b.rows_out, b.dups_dropped)


@db_only
def test_dedup_keeps_lowest_ingest_id(engine):
    """Every surviving silver row's _ingest_id is the MIN for its
    (user_id, row_fingerprint) group in bronze."""
    with engine.begin() as conn:
        build_silver(conn)
        bad = conn.execute(text("""
            SELECT count(*) FROM silver.streams s
            WHERE s._ingest_id <> (
                SELECT min(b._ingest_id) FROM bronze.raw_streams b
                WHERE b.user_id = s.user_id AND b.row_fingerprint = s.row_fingerprint
            )
        """)).scalar_one()
    assert bad == 0


@db_only
def test_dedup_report_shape(engine):
    with engine.connect() as conn:
        rows = dedup_report(conn)
    assert rows and {"username", "bronze", "silver", "fact"} <= set(rows[0])
