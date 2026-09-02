"""Tests for app/quality/.

Pure tests (no DB) always run in CI. DB-backed tests are skipped unless
DATABASE_URL is set with migrations 001-013 applied and the star schema populated.
"""

import os

import pytest
from sqlalchemy import text

from app.quality.checks import ALL_CHECKS, CATEGORIES, CheckResult, _mad_anomalies
from app.quality.run import run_all, summarize

DB_URL = os.getenv("DATABASE_URL")
db_only = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")


# ---------------------------------------------------------------------------
# pure
# ---------------------------------------------------------------------------
def test_all_checks_have_unique_names():
    # per-user fan-out checks emit one name; the DDL UNIQUE is (dq_run_id, name, user_id)
    names = [c.name for c in ALL_CHECKS]
    assert len(names) == len(set(names)), "duplicate check name in the registry"


def test_all_six_categories_are_covered():
    covered = {c.category for c in ALL_CHECKS}
    assert covered == set(CATEGORIES), f"missing categories: {set(CATEGORIES) - covered}"


def test_every_check_severity_is_valid():
    for c in ALL_CHECKS:
        assert c.severity in ("blocking", "warn"), c.name


def test_blocking_set_is_tight():
    # Keep the blast radius small: a mis-marked warn turns the nightly job red.
    blocking = {c.name for c in ALL_CHECKS if c.severity == "blocking"}
    assert blocking == {
        "fact_ingest_id_unique",
        "dim_track_uri_unique",
        "silver_fingerprint_unique",
        "fact_track_key_fk",
        "fact_user_id_fk",
        "fact_artist_key_fk",
        "fact_time_key_fk",
        "ms_played_range",
        "ingest_run_match_rate_range",
        "latest_ingest_run_terminal",
        "fact_track_name_rate",
        "fact_artist_name_rate",
        "fact_time_key_rate",
    }


def _cr(name, sev, passed, *, skipped=False, cat="uniqueness"):
    return CheckResult(name=name, category=cat, severity=sev, passed=passed, skipped=skipped)


def test_summarize_status_precedence():
    assert summarize([_cr("a", "blocking", True)])["status"] == "pass"
    assert summarize([_cr("a", "warn", False)])["status"] == "warn"
    assert summarize([_cr("a", "blocking", False)])["status"] == "fail"
    # blocking failure beats a warn failure
    s = summarize([_cr("a", "warn", False), _cr("b", "blocking", False)])
    assert s["status"] == "fail" and s["failed"] == 1 and s["warned"] == 1
    # a skipped check is neither pass nor fail
    s = summarize([_cr("a", "blocking", True, skipped=True)])
    assert s["skipped"] == 1 and s["passed"] == 0 and s["status"] == "pass"


def test_summarize_counts_sum_to_total():
    results = [
        _cr("a", "blocking", True),
        _cr("b", "warn", False),
        _cr("c", "blocking", False),
        _cr("d", "warn", True, skipped=True),
    ]
    s = summarize(results)
    assert s["total"] == s["passed"] + s["failed"] + s["warned"] + s["skipped"]


def test_mad_anomaly_flags_a_known_spike():
    series = [(f"d{i}", 100.0 + (i % 3)) for i in range(30)] + [("spike", 5000.0)]
    flagged = _mad_anomalies(series, window=30, k=4.0)
    assert len(flagged) == 1 and flagged[0]["label"] == "spike"


def test_mad_anomaly_flat_series_flags_nothing():
    # MAD == 0 must be skipped, not treated as infinite sensitivity
    series = [(f"d{i}", 100.0) for i in range(40)]
    assert _mad_anomalies(series, window=30, k=4.0) == []


def test_fk_checks_sql_shape():
    from app.quality.checks import _fk_check

    class _FakeConn:
        def execute(self, clause, params=None):
            self.sql = str(clause)

            class _R:
                def scalar_one(self_inner):
                    return 0

            return _R()

    fc = _FakeConn()
    _fk_check(fc, name="x", fact_col="track_key", dim_table="gold.dim_track", dim_col="track_key")
    s = " ".join(fc.sql.split())
    assert "LEFT JOIN gold.dim_track" in s
    assert "IS NOT NULL AND d.track_key IS NULL" in s


# ---------------------------------------------------------------------------
# DB-backed
# ---------------------------------------------------------------------------
@pytest.fixture
def engine():
    from app.db.session import make_engine

    return make_engine(DB_URL)


@db_only
def test_run_all_persists_a_dq_run_and_result_per_check(engine):
    dq_run_id, results = run_all(engine)
    assert dq_run_id is not None and results
    with engine.connect() as conn:
        run = conn.execute(
            text("SELECT * FROM quality.dq_run WHERE dq_run_id = :i"),
            {"i": str(dq_run_id)},
        ).mappings().one()
        n = conn.execute(
            text("SELECT count(*) FROM quality.dq_result WHERE dq_run_id = :i"),
            {"i": str(dq_run_id)},
        ).scalar_one()
    assert n == len(results)
    assert run["checks_total"] == run["passed"] + run["failed"] + run["warned"] + run["skipped"]
    assert run["status"] in ("pass", "warn", "fail")


@db_only
def test_run_all_is_read_only_wrt_gold(engine):
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM gold.fact_streams")).scalar_one()
    run_all(engine, persist=False)
    with engine.connect() as conn:
        after = conn.execute(text("SELECT count(*) FROM gold.fact_streams")).scalar_one()
    assert before == after


@db_only
def test_all_six_categories_present_in_persisted_results(engine):
    dq_run_id, _ = run_all(engine)
    with engine.connect() as conn:
        cats = {
            r[0]
            for r in conn.execute(
                text("SELECT DISTINCT category FROM quality.dq_result WHERE dq_run_id = :i"),
                {"i": str(dq_run_id)},
            ).all()
        }
    assert cats == set(CATEGORIES)


@db_only
def test_no_persist_writes_nothing(engine):
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM quality.dq_run")).scalar_one()
    run_all(engine, persist=False)
    with engine.connect() as conn:
        after = conn.execute(text("SELECT count(*) FROM quality.dq_run")).scalar_one()
    assert before == after
