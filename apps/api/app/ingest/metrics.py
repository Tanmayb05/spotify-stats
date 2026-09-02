"""Ingestion run metrics: bronze.ingest_run + bronze.ingest_run_user.

CRITICAL: every function here opens its OWN short-lived connection from `engine`
and commits immediately -- these writes are OUTSIDE the pipeline transaction.
If they shared it, a failed run would roll back its own `status='failed'`
record and ingest_run would never show the failure.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

_RUN_COUNTERS = (
    "users", "files_seen", "files_new", "rows_raw", "rows_valid",
    "rows_quarantined", "rows_landed", "dups_dropped", "rows_silver", "rows_fact",
)
_USER_COUNTERS = (
    "files_seen", "files_new", "rows_raw", "rows_valid", "rows_quarantined",
    "rows_landed", "dups_dropped", "rows_silver",
)


def start_run(engine: Engine, dagster_run_id: str | None = None) -> UUID:
    run_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO bronze.ingest_run (run_id, status, dagster_run_id) "
                "VALUES (:r, 'running', :d)"
            ),
            {"r": str(run_id), "d": dagster_run_id},
        )
    return run_id


def record_user(engine: Engine, run_id: UUID, user_id: UUID, *, max_ts=None, **counters) -> None:
    cols = [c for c in _USER_COUNTERS if c in counters]
    set_sql = ", ".join(f"{c} = bronze.ingest_run_user.{c} + EXCLUDED.{c}" for c in cols)
    ins_cols = ", ".join(["run_id", "user_id", "max_ts", *cols])
    ins_binds = ", ".join([":run_id", ":user_id", ":max_ts", *(f":{c}" for c in cols)])
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO bronze.ingest_run_user ({ins_cols})
                VALUES ({ins_binds})
                ON CONFLICT (run_id, user_id) DO UPDATE SET
                    {set_sql},
                    max_ts = GREATEST(bronze.ingest_run_user.max_ts, EXCLUDED.max_ts)
                """
            ),
            {
                "run_id": str(run_id), "user_id": str(user_id), "max_ts": max_ts,
                **{c: counters[c] for c in cols},
            },
        )


def bump_run(engine: Engine, run_id: UUID, **counters) -> None:
    cols = [c for c in _RUN_COUNTERS if c in counters]
    if not cols:
        return
    set_sql = ", ".join(f"{c} = {c} + :{c}" for c in cols)
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE bronze.ingest_run SET {set_sql} WHERE run_id = :r"),
            {"r": str(run_id), **{c: counters[c] for c in cols}},
        )


def finish_run(engine: Engine, run_id: UUID, status: str, *, detail: dict | None = None, **finals) -> None:
    import json

    allowed = {
        "rows_silver", "rows_fact", "track_match_rate", "artist_match_rate",
        "unmatched_tracks", "unmatched_artists", "users", "files_seen",
        "files_new", "rows_raw", "rows_valid", "rows_quarantined", "rows_landed",
        "dups_dropped",
    }
    cols = [c for c in finals if c in allowed]
    set_parts = ["finished_at = now()", "status = :status"]
    params: dict = {"r": str(run_id), "status": status}
    for c in cols:
        set_parts.append(f"{c} = :{c}")
        params[c] = finals[c]
    if detail is not None:
        set_parts.append("detail = CAST(:detail AS jsonb)")
        params["detail"] = json.dumps(detail, default=str)
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE bronze.ingest_run SET {', '.join(set_parts)} WHERE run_id = :r"),
            params,
        )


def latest_run(engine: Engine) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM bronze.ingest_run ORDER BY started_at DESC LIMIT 1")
        ).mappings().first()
    return dict(row) if row else None
