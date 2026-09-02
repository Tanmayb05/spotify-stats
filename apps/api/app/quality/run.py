"""Run the data-quality suite and persist to quality.dq_run / quality.dq_result.

    python -m app.quality.run                       # all checks, persist
    python -m app.quality.run --category range,freshness
    python -m app.quality.run --only fact_track_key_fk
    python -m app.quality.run --no-persist --json

Exit code is the contract (Phase 16 CI uses it directly):
    0  no blocking failures (pass or warn)
    1  at least one blocking check failed
    2  infrastructure error (no DB / migration 013 not applied)

CRITICAL: the dq_run / dq_result writes use their OWN short-lived connections,
OUTSIDE any caller transaction -- the same rule as app/ingest/metrics.py. A
raising blocking check (in the Dagster asset) must still leave its dq_run row.
"""

from __future__ import annotations

import json as _json
import sys
import traceback
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.quality.checks import ALL_CHECKS, CATEGORIES, CheckResult, latest_ingest_run_terminal

_STATUS_PRECEDENCE = ("fail", "warn", "pass")


# ---------------------------------------------------------------------------
# persistence -- own connections, per the metrics.py rule
# ---------------------------------------------------------------------------
def _start_dq_run(
    engine: Engine, ingest_run_id: UUID | str | None, dagster_run_id: str | None
) -> UUID:
    dq_run_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO quality.dq_run (dq_run_id, ingest_run_id, dagster_run_id, status) "
                "VALUES (:i, :ir, :dr, 'running')"
            ),
            {
                "i": str(dq_run_id),
                "ir": str(ingest_run_id) if ingest_run_id else None,
                "dr": dagster_run_id,
            },
        )
    return dq_run_id


def _finish_dq_run(
    engine: Engine, dq_run_id: UUID, results: list[CheckResult], duration_ms: int
) -> None:
    s = summarize(results)
    with engine.begin() as conn:
        for r in results:
            conn.execute(
                text(
                    """
                    INSERT INTO quality.dq_result
                      (dq_run_id, name, category, severity, passed, skipped,
                       observed, observed_numeric, expected, rows_failed,
                       user_id, detail, duration_ms)
                    VALUES
                      (:dq_run_id, :name, :category, :severity, :passed, :skipped,
                       :observed, :observed_numeric, :expected, :rows_failed,
                       :user_id, CAST(:detail AS jsonb), :duration_ms)
                    ON CONFLICT (dq_run_id, name, user_id) DO NOTHING
                    """
                ),
                {
                    "dq_run_id": str(dq_run_id),
                    "name": r.name,
                    "category": r.category,
                    "severity": r.severity,
                    "passed": r.passed,
                    "skipped": r.skipped,
                    "observed": r.observed,
                    "observed_numeric": r.observed_numeric,
                    "expected": r.expected,
                    "rows_failed": r.rows_failed,
                    "user_id": r.user_id,
                    "detail": _json.dumps(r.detail) if r.detail is not None else None,
                    "duration_ms": r.duration_ms,
                },
            )
        conn.execute(
            text(
                """
                UPDATE quality.dq_run
                SET finished_at = now(), duration_ms = :dur,
                    checks_total = :total, passed = :passed, failed = :failed,
                    warned = :warned, skipped = :skipped, status = :status
                WHERE dq_run_id = :id
                """
            ),
            {
                "dur": duration_ms,
                "total": s["total"],
                "passed": s["passed"],
                "failed": s["failed"],
                "warned": s["warned"],
                "skipped": s["skipped"],
                "status": s["status"],
                "id": str(dq_run_id),
            },
        )


def _error_dq_run(engine: Engine, dq_run_id: UUID, exc: Exception) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE quality.dq_run SET finished_at = now(), status = 'error', "
                    "detail = CAST(:d AS jsonb) WHERE dq_run_id = :id"
                ),
                {"d": _json.dumps({"error": str(exc)}), "id": str(dq_run_id)},
            )
    except Exception:  # pragma: no cover -- best effort
        pass


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------
def summarize(results: list[CheckResult]) -> dict:
    passed = failed = warned = skipped = 0
    blocking_failures: list[str] = []
    warn_failures: list[str] = []
    by_category: dict[str, dict] = {c: {"total": 0, "passed": 0, "failed": 0, "warned": 0, "skipped": 0} for c in CATEGORIES}

    for r in results:
        cat = by_category[r.category]
        cat["total"] += 1
        if r.skipped:
            skipped += 1
            cat["skipped"] += 1
        elif r.passed:
            passed += 1
            cat["passed"] += 1
        elif r.severity == "blocking":
            failed += 1
            cat["failed"] += 1
            blocking_failures.append(r.name)
        else:
            warned += 1
            cat["warned"] += 1
            warn_failures.append(r.name)

    for c, agg in by_category.items():
        agg["status"] = (
            "fail" if agg["failed"] else "warn" if agg["warned"] else "pass"
        )

    status = "fail" if failed else "warn" if warned else "pass"
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "skipped": skipped,
        "status": status,
        "blocking_failures": blocking_failures,
        "warn_failures": warn_failures,
        "by_category": by_category,
    }


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
def run_all(
    engine: Engine,
    *,
    ingest_run_id: UUID | str | None = None,
    dagster_run_id: str | None = None,
    only: list[str] | None = None,
    categories: list[str] | None = None,
    persist: bool = True,
) -> tuple[UUID | None, list[CheckResult]]:
    checks = list(ALL_CHECKS)
    if categories:
        checks = [c for c in checks if c.category in set(categories)]
    if only:
        checks = [c for c in checks if c.name in set(only)]

    dq_run_id: UUID | None = _start_dq_run(engine, ingest_run_id, dagster_run_id) if persist else None
    t0 = perf_counter()
    results: list[CheckResult] = []

    try:
        with engine.connect() as conn:
            for chk in checks:
                ct = perf_counter()
                try:
                    if chk.name == "latest_ingest_run_terminal":
                        raw = latest_ingest_run_terminal(
                            conn, exclude_run_id=str(ingest_run_id) if ingest_run_id else None
                        )
                    else:
                        raw = chk.fn(conn)
                except Exception as exc:  # one raising check must not abort the suite
                    raw = CheckResult(
                        name=chk.name,
                        category=chk.category,
                        severity=chk.severity,
                        passed=False,
                        observed=f"ERROR: {exc}",
                        expected="check to run without raising",
                        detail={"traceback": traceback.format_exc()[-2000:]},
                    )
                dur = int((perf_counter() - ct) * 1000)
                for res in raw if isinstance(raw, list) else [raw]:
                    # stamp identity from the registry so a fn can't lie about it
                    res.name = chk.name
                    res.category = chk.category
                    res.severity = chk.severity
                    if res.duration_ms is None:
                        res.duration_ms = dur
                    results.append(res)
    except Exception as exc:
        if dq_run_id is not None:
            _error_dq_run(engine, dq_run_id, exc)
        raise

    duration_ms = int((perf_counter() - t0) * 1000)
    if dq_run_id is not None:
        _finish_dq_run(engine, dq_run_id, results, duration_ms)
    return dq_run_id, results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_table(results: list[CheckResult]) -> None:
    print(f"\n--- Data quality: {len(results)} checks ---")
    print(
        f"{'CATEGORY':<22} {'CHECK':<32} {'SEV':<9} {'STATUS':<7} "
        f"{'OBSERVED':<40} EXPECTED"
    )
    for r in results:
        status = "SKIP" if r.skipped else ("PASS" if r.passed else "FAIL")
        label = r.name
        if r.user_id and r.detail and r.detail.get("username"):
            label = f"{r.name}[{r.detail['username']}]"
        print(
            f"{r.category:<22} {label:<32} {r.severity:<9} {status:<7} "
            f"{(r.observed or '')[:40]:<40} {(r.expected or '')[:60]}"
        )
    s = summarize(results)
    print(
        f"\n{s['total']} checks: {s['passed']} passed, {s['failed']} failed (blocking), "
        f"{s['warned']} warned, {s['skipped']} skipped   ->  {s['status'].upper()}"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the data-quality suite.")
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--category",
        default=None,
        help="comma-separated: uniqueness,referential_integrity,range,freshness,completeness,anomaly",
    )
    parser.add_argument("--only", default=None, help="comma-separated check names")
    parser.add_argument("--no-persist", action="store_true", help="do not write quality.dq_*")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of the table")
    args = parser.parse_args()

    from app.db.session import make_engine

    try:
        engine = make_engine(args.database_url)
    except Exception as exc:
        print(f"ERROR: cannot build engine: {exc}", file=sys.stderr)
        return 2

    try:
        dq_run_id, results = run_all(
            engine,
            only=args.only.split(",") if args.only else None,
            categories=args.category.split(",") if args.category else None,
            persist=not args.no_persist,
        )
    except Exception as exc:
        print(f"ERROR: suite failed to run: {exc}", file=sys.stderr)
        return 2

    s = summarize(results)
    if args.json:
        print(
            _json.dumps(
                {
                    "dq_run_id": str(dq_run_id) if dq_run_id else None,
                    "summary": {k: v for k, v in s.items() if k != "by_category"},
                    "by_category": s["by_category"],
                    "results": [
                        {
                            "name": r.name,
                            "category": r.category,
                            "severity": r.severity,
                            "passed": r.passed,
                            "skipped": r.skipped,
                            "observed": r.observed,
                            "expected": r.expected,
                            "rows_failed": r.rows_failed,
                            "user_id": r.user_id,
                        }
                        for r in results
                    ],
                },
                indent=2,
                default=str,
            )
        )
    else:
        _print_table(results)
        if dq_run_id:
            print(f"dq_run_id = {dq_run_id}  (quality.dq_run)")

    return 1 if s["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
