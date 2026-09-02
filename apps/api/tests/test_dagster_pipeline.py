"""Dagster asset-graph integration tests (Phase 12, Commit 3).

DB-backed: skipped unless DATABASE_URL points at a Postgres with migrations
001-011 applied. These materialize the real assets against a temp data root, so
they write to bronze/silver/gold -- run them against a disposable DB (the
compose `db` service is fine; they clean up after themselves).

Covered:
  * V1  -- full job green, per-user silver == fact
  * V2  -- immediate re-materialization lands nothing (file_hash_seen)
  * V3  -- malformed fixture: 6 quarantine rows / 6 distinct rules for the run
  * V8  -- no ip_addr in bronze._raw after a run over the full fixture
"""

import os
import shutil
from pathlib import Path

import pytest
from sqlalchemy import text

DB_URL = os.getenv("DATABASE_URL")

# These tests TRUNCATE bronze/silver/gold between cases -- DESTRUCTIVE. They only
# run against a throwaway DB explicitly opted in with DAGSTER_PIPELINE_TEST_DB=1.
# CI (Phase 16) spins up a scratch Postgres for this; do not point it at a DB
# that holds real data.
_OPTED_IN = os.getenv("DAGSTER_PIPELINE_TEST_DB") == "1"
pytestmark = pytest.mark.skipif(
    not (DB_URL and _OPTED_IN),
    reason="needs DATABASE_URL + DAGSTER_PIPELINE_TEST_DB=1 (destructive: truncates bronze/silver/gold)",
)

def _find_fixtures() -> Path:
    for base in Path(__file__).resolve().parents:
        cand = base / "data" / "fixtures"
        if cand.is_dir():
            return cand
    raise RuntimeError("data/fixtures not found")


FIXTURES = _find_fixtures()


@pytest.fixture
def engine():
    from app.db.session import make_engine

    return make_engine(DB_URL)


@pytest.fixture
def temp_data_root(tmp_path: Path) -> Path:
    """A data/ tree discover.py understands: primary export files at the root."""
    root = tmp_path / "data"
    root.mkdir()
    return root


def _materialize(assets, resources, partition_key=None):
    from dagster import materialize

    return materialize(assets, resources=resources, partition_key=partition_key)


def _resources(engine, data_root: Path):
    from dagster_project.resources import DataRootResource, PostgresResource

    return {
        "postgres": PostgresResource(database_url=DB_URL),
        "data_root": DataRootResource(path=str(data_root)),
    }


def _all_assets():
    from dagster import load_assets_from_modules

    from dagster_project import assets as m

    return load_assets_from_modules([m])


def _cleanup(engine):
    """Drop everything a run wrote so tests do not accrete state."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE bronze.raw_streams RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE silver.streams RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE gold.fact_streams RESTART IDENTITY"))
        conn.execute(text("TRUNCATE bronze.quarantine RESTART IDENTITY"))
        conn.execute(text("DELETE FROM bronze.ingest_state"))
        conn.execute(text("TRUNCATE bronze.ingest_run CASCADE"))


def test_v1_v2_full_graph_idempotent(engine, temp_data_root):
    shutil.copy(
        FIXTURES / "sample_streaming_history_full.json",
        temp_data_root / "streaming_2023-2024_0.json",
    )
    _cleanup(engine)
    try:
        r1 = _materialize(_all_assets(), _resources(engine, temp_data_root),
                          partition_key="primary")
        assert r1.success

        with engine.connect() as conn:
            silver = conn.execute(text("SELECT count(*) FROM silver.streams")).scalar_one()
            fact = conn.execute(text("SELECT count(*) FROM gold.fact_streams")).scalar_one()
            bronze1 = conn.execute(
                text("SELECT count(*) FROM bronze.raw_streams")
            ).scalar_one()
        assert silver == fact > 0            # V1b
        assert silver < bronze1              # the fixture has a dupe pair -> dedup fired

        # V2: re-materialize the bronze partition -> file_hash_seen, nothing new.
        r2 = _materialize(
            [a for a in _all_assets() if "raw_streams" in {k.to_user_string() for k in a.keys}],
            _resources(engine, temp_data_root),
            partition_key="primary",
        )
        assert r2.success
        with engine.connect() as conn:
            bronze2 = conn.execute(
                text("SELECT count(*) FROM bronze.raw_streams")
            ).scalar_one()
        assert bronze2 == bronze1
    finally:
        _cleanup(engine)


def test_v3_malformed_fixture_quarantines(engine, temp_data_root):
    shutil.copy(
        FIXTURES / "malformed_streaming_history.json",
        temp_data_root / "streaming_2023-2024_0.json",
    )
    _cleanup(engine)
    try:
        result = _materialize(
            [a for a in _all_assets() if "raw_streams" in {k.to_user_string() for k in a.keys}],
            _resources(engine, temp_data_root),
            partition_key="primary",
        )
        assert result.success

        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT rule FROM bronze.quarantine")
            ).scalars().all()
            landed = conn.execute(
                text("SELECT count(*) FROM bronze.raw_streams")
            ).scalar_one()
        assert len(rows) == 6                      # V3
        assert len(set(rows)) == 6                 # 6 distinct rules
        assert landed == 1                         # the one clean control row
    finally:
        _cleanup(engine)


def test_v8_no_ip_addr_in_bronze(engine, temp_data_root):
    shutil.copy(
        FIXTURES / "sample_streaming_history_full.json",
        temp_data_root / "streaming_2023-2024_0.json",
    )
    _cleanup(engine)
    try:
        _materialize(
            [a for a in _all_assets() if "raw_streams" in {k.to_user_string() for k in a.keys}],
            _resources(engine, temp_data_root),
            partition_key="primary",
        )
        with engine.connect() as conn:
            n = conn.execute(
                text("SELECT count(*) FROM bronze.raw_streams WHERE _raw ? 'ip_addr'")
            ).scalar_one()
        assert n == 0
    finally:
        _cleanup(engine)
