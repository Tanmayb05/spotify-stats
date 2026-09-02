"""Tests for GET /api/health/data.

The repo's first FastAPI TestClient test. DB-free: the backend is monkeypatched,
so this runs in CI without a database.
"""

import pytest
from fastapi.testclient import TestClient

import app.routes.health as health_mod
from app.main import app

client = TestClient(app)


class _FakeBackend:
    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = tables

    def select(self, table, columns, *, eq=None, order=None, limit=None, range_=None):
        rows = list(self._tables.get(table, []))
        if eq:
            for k, v in eq.items():
                rows = [r for r in rows if str(r.get(k)) == str(v)]
        if limit:
            rows = rows[:limit]
        return rows


@pytest.fixture(autouse=True)
def _clear_cache():
    health_mod._backend.cache_clear()
    yield
    health_mod._backend.cache_clear()


@pytest.fixture
def patch_backend(monkeypatch):
    def _apply(tables):
        monkeypatch.setattr(health_mod, "_backend", lambda: _FakeBackend(tables))
        monkeypatch.setattr(
            "app.services.supabase_data_loader.supabase_data.list_users",
            lambda: [],
        )

    return _apply


def test_liveness_blob_untouched():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_empty_backend_is_200_and_has_run_false(patch_backend):
    patch_backend({})
    r = client.get("/api/health/data")
    assert r.status_code == 200
    body = r.json()
    assert body["dq"]["has_run"] is False
    assert body["ingest"]["has_run"] is False
    assert body["dq"]["categories"] == []
    assert body["trend"] == []


def test_canned_dq_run_groups_by_category(patch_backend):
    dq_run_id = "11111111-1111-1111-1111-111111111111"
    results = [
        {"dq_run_id": dq_run_id, "name": f"c_{cat}", "category": cat,
         "severity": "blocking", "passed": True, "skipped": False,
         "observed": "ok", "observed_numeric": 0, "expected": "-", "rows_failed": 0,
         "user_id": None, "detail": None}
        for cat in (
            "uniqueness", "referential_integrity", "range",
            "freshness", "completeness", "anomaly",
        )
    ]
    tables = {
        "dq_run": [{
            "dq_run_id": dq_run_id, "run_at": "2026-09-02T00:00:00Z",
            "finished_at": "2026-09-02T00:01:00Z", "status": "pass",
            "ingest_run_id": None, "checks_total": 6, "passed": 6,
            "failed": 0, "warned": 0, "skipped": 0, "duration_ms": 100,
        }],
        "dq_result": results,
    }
    patch_backend(tables)
    r = client.get("/api/health/data")
    assert r.status_code == 200
    body = r.json()
    assert body["dq"]["has_run"] is True
    cats = body["dq"]["categories"]
    assert len(cats) >= 6
    assert {c["category"] for c in cats} == {
        "uniqueness", "referential_integrity", "range",
        "freshness", "completeness", "anomaly",
    }
    assert all(c["status"] == "pass" for c in cats)


def test_ingest_invariants_computed(patch_backend):
    tables = {
        "bronze_ingest_run": [{
            "run_id": "22222222-2222-2222-2222-222222222222",
            "started_at": "2026-09-02T00:00:00Z", "finished_at": None,
            "status": "success", "users": 10,
            "rows_raw": 100, "rows_valid": 90, "rows_quarantined": 10,
            "rows_landed": 90, "dups_dropped": 5, "rows_silver": 85,
            "rows_fact": 85, "track_match_rate": 0.5, "artist_match_rate": 0.8,
        }],
    }
    patch_backend(tables)
    body = client.get("/api/health/data").json()
    inv = body["ingest"]["invariants"]
    assert inv["rows_raw_equals_valid_plus_quarantined"] is True
    assert inv["rows_silver_equals_landed_minus_dups"] is True
    assert inv["match_rates_in_unit_interval"] is True
