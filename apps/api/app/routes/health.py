"""Health endpoints.

  GET /health           -- liveness blob (unchanged, no DB touch)
  GET /api/health/data  -- data-quality + ingestion status for the Data Health
                           page. Reads ONLY through the unqualified public.*
                           compat views (public.dq_run, public.dq_result,
                           public.bronze_ingest_run/_user, public.bronze_quarantine)
                           via DBBackend.select(), so it works on both the local
                           and the Supabase backend. Every read is caught: on a
                           backend where the quality/bronze schemas were never
                           migrated (the hosted Supabase demo), the endpoint
                           degrades to has_run=false, HTTP 200 -- a state, not an
                           error.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "spotify-insights-api",
    }


@lru_cache(maxsize=1)
def _backend():
    # build_backend raises without Supabase creds -- keep it lazy so importing
    # app.main works for a local-only dev with no env file.
    from app.db.backends import build_backend

    return build_backend(settings)


def _safe_select(table: str, columns: str, **kw) -> list[dict]:
    try:
        return _backend().select(table, columns, **kw) or []
    except Exception as exc:  # missing schema on Supabase, etc.
        logger.warning("health/data: select %s failed: %s", table, exc)
        return []


def _one(rows: list[dict]) -> dict | None:
    return rows[0] if rows else None


def _f(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


@router.get("/api/health/data")
async def health_data():
    now = datetime.now(timezone.utc).isoformat()

    # ---- users (for name mapping; already backend-agnostic) -----------------
    try:
        from app.services.supabase_data_loader import supabase_data

        users = {u["user_id"]: u for u in (supabase_data.list_users() or [])}
    except Exception as exc:
        logger.warning("health/data: list_users failed: %s", exc)
        users = {}

    # ---- latest dq_run + its results ---------------------------------------
    dq_row = _one(
        _safe_select("dq_run", "*", order=[("run_at", True)], limit=1)
    )
    dq_results: list[dict] = []
    if dq_row:
        dq_results = _safe_select(
            "dq_result",
            "*",
            eq={"dq_run_id": dq_row["dq_run_id"]},
            order=[("category", False), ("name", False)],
        )

    if not dq_row:
        dq_block: dict = {
            "has_run": False,
            "status": "unknown",
            "categories": [],
            "message": (
                "No DQ run recorded. The data-quality suite runs on the local "
                "Postgres pipeline (Dagster `data_quality` asset); this backend "
                "has no quality.dq_run rows."
            ),
        }
    else:
        by_cat: dict[str, dict] = {}
        for r in dq_results:
            c = by_cat.setdefault(
                r["category"],
                {
                    "category": r["category"],
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "warned": 0,
                    "skipped": 0,
                    "checks": [],
                },
            )
            c["total"] += 1
            if r["skipped"]:
                c["skipped"] += 1
            elif r["passed"]:
                c["passed"] += 1
            elif r["severity"] == "blocking":
                c["failed"] += 1
            else:
                c["warned"] += 1
            c["checks"].append(
                {
                    "name": r["name"],
                    "severity": r["severity"],
                    "passed": r["passed"],
                    "skipped": r["skipped"],
                    "observed": r["observed"],
                    "observed_numeric": _f(r.get("observed_numeric")),
                    "expected": r["expected"],
                    "rows_failed": r.get("rows_failed", 0),
                    "user_id": r.get("user_id"),
                    "detail": r.get("detail"),
                }
            )
        for c in by_cat.values():
            c["status"] = (
                "fail" if c["failed"] else "warn" if c["warned"] else "pass"
            )
        dq_block = {
            "has_run": True,
            "dq_run_id": dq_row["dq_run_id"],
            "run_at": dq_row["run_at"],
            "finished_at": dq_row.get("finished_at"),
            "status": dq_row["status"],
            "ingest_run_id": dq_row.get("ingest_run_id"),
            "checks_total": dq_row.get("checks_total", 0),
            "passed": dq_row.get("passed", 0),
            "failed": dq_row.get("failed", 0),
            "warned": dq_row.get("warned", 0),
            "skipped": dq_row.get("skipped", 0),
            "duration_ms": dq_row.get("duration_ms"),
            "categories": sorted(by_cat.values(), key=lambda x: x["category"]),
        }

    # ---- latest ingest run + per-user + quarantine + trend ----------------
    ir = _one(
        _safe_select("bronze_ingest_run", "*", order=[("started_at", True)], limit=1)
    )
    per_user_rows: list[dict] = []
    quarantine_rows: list[dict] = []
    if ir:
        per_user_rows = _safe_select(
            "bronze_ingest_run_user", "*", eq={"run_id": ir["run_id"]}
        )
        quarantine_rows = _safe_select(
            "bronze_quarantine",
            "quarantine_id,run_id,rule,source_file,quarantined_at",
            eq={"run_id": ir["run_id"]},
            limit=50,
        )

    if not ir:
        ingest_block: dict = {"has_run": False, "message": "No ingest run recorded."}
    else:
        rr, rv, rq = (
            ir.get("rows_raw") or 0,
            ir.get("rows_valid") or 0,
            ir.get("rows_quarantined") or 0,
        )
        rl, dd, rs = (
            ir.get("rows_landed") or 0,
            ir.get("dups_dropped") or 0,
            ir.get("rows_silver") or 0,
        )
        tmr, amr = _f(ir.get("track_match_rate")), _f(ir.get("artist_match_rate"))
        ingest_block = {
            "has_run": True,
            "run_id": ir["run_id"],
            "started_at": ir.get("started_at"),
            "finished_at": ir.get("finished_at"),
            "status": ir.get("status"),
            "users": ir.get("users", 0),
            "files_seen": ir.get("files_seen", 0),
            "files_new": ir.get("files_new", 0),
            "rows_raw": rr,
            "rows_valid": rv,
            "rows_quarantined": rq,
            "rows_landed": rl,
            "dups_dropped": dd,
            "rows_silver": rs,
            "rows_fact": ir.get("rows_fact", 0),
            "track_match_rate": tmr,
            "artist_match_rate": amr,
            "unmatched_tracks": ir.get("unmatched_tracks"),
            "unmatched_artists": ir.get("unmatched_artists"),
            # migration-011 invariants. rows_silver = rows_landed - dups_dropped
            # only holds on a fresh landing run; on an idempotent re-run
            # rows_landed=0 while silver is rebuilt in full from bronze, so that
            # one is checked only when this run actually landed rows.
            "invariants": {
                "rows_raw_equals_valid_plus_quarantined": rr == rv + rq,
                "rows_silver_equals_landed_minus_dups": (
                    None if rl == 0 else rs == rl - dd
                ),
                "match_rates_in_unit_interval": all(
                    x is None or 0.0 <= x <= 1.0 for x in (tmr, amr)
                ),
            },
        }

    # per-user freshness from the dq_result fan-out, keyed by user_id
    freshness_by_user: dict[str, dict] = {}
    for r in dq_results:
        if r["name"] == "per_user_fact_freshness" and r.get("user_id"):
            freshness_by_user[r["user_id"]] = r

    per_user = []
    for r in per_user_rows:
        uid = r["user_id"]
        u = users.get(uid, {})
        fr = freshness_by_user.get(uid)
        per_user.append(
            {
                "user_id": uid,
                "username": u.get("username"),
                "display_name": u.get("display_name"),
                "is_primary": u.get("is_primary", False),
                "rows_raw": r.get("rows_raw", 0),
                "rows_silver": r.get("rows_silver", 0),
                "dups_dropped": r.get("dups_dropped", 0),
                "rows_quarantined": r.get("rows_quarantined", 0),
                "max_ts": r.get("max_ts"),
                "freshness_days": _f(fr["observed_numeric"]) if fr else None,
                "freshness_status": (
                    "pass" if fr and fr["passed"] else "warn" if fr else "unknown"
                ),
            }
        )
    per_user.sort(key=lambda x: (not x["is_primary"], x["username"] or ""))

    q_by_rule: dict[str, int] = {}
    for r in quarantine_rows:
        q_by_rule[r["rule"]] = q_by_rule.get(r["rule"], 0) + 1

    trend = [
        {
            "run_id": r["run_id"],
            "started_at": r.get("started_at"),
            "rows_fact": r.get("rows_fact", 0),
            "rows_raw": r.get("rows_raw", 0),
            "rows_quarantined": r.get("rows_quarantined", 0),
            "dups_dropped": r.get("dups_dropped", 0),
            "status": r.get("status"),
        }
        for r in reversed(
            _safe_select(
                "bronze_ingest_run",
                "run_id,started_at,rows_fact,rows_raw,rows_quarantined,dups_dropped,status",
                order=[("started_at", True)],
                limit=30,
            )
        )
    ]

    return {
        "backend": "local" if settings.is_local else "supabase",
        "generated_at": now,
        "dq": dq_block,
        "ingest": ingest_block,
        "per_user": per_user,
        "quarantine": {
            "total": len(quarantine_rows),
            "by_rule": q_by_rule,
            "sample": quarantine_rows[:20],
        },
        "trend": trend,
    }
