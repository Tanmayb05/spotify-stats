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


def ensure_run(engine: Engine, dagster_run_id: str) -> UUID:
    """Return the bronze.ingest_run.run_id for this Dagster run, creating it once.

    Dagster assets are separate executions with no shared Python state, but they
    do share `context.run_id`. The first asset in a job creates the ingest_run
    row; the rest look it up. `dagster_run_id` has no DB unique constraint, so a
    check-then-insert in one short transaction is the guard -- fine for the
    single-daemon dev/compose setup this ships with.
    """
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT run_id FROM bronze.ingest_run "
                "WHERE dagster_run_id = :d ORDER BY started_at DESC LIMIT 1"
            ),
            {"d": dagster_run_id},
        ).first()
        if row:
            return row[0]
        run_id = uuid4()
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


_FINAL_FIELDS = {
    "rows_silver", "rows_fact", "track_match_rate", "artist_match_rate",
    "unmatched_tracks", "unmatched_artists", "users", "files_seen",
    "files_new", "rows_raw", "rows_valid", "rows_quarantined", "rows_landed",
    "dups_dropped",
}


def set_run_fields(engine: Engine, run_id: UUID, *, detail: dict | None = None, **fields) -> None:
    """Plain UPDATE of non-counter run fields (match rates, final totals, detail).
    Does NOT touch `status` / `finished_at` -- use finish_run for that."""
    import json

    cols = [c for c in fields if c in _FINAL_FIELDS]
    if not cols and detail is None:
        return
    set_parts = [f"{c} = :{c}" for c in cols]
    params: dict = {"r": str(run_id), **{c: fields[c] for c in cols}}
    if detail is not None:
        set_parts.append("detail = CAST(:detail AS jsonb)")
        params["detail"] = json.dumps(detail, default=str)
    with engine.begin() as conn:
        conn.execute(
            text(f"UPDATE bronze.ingest_run SET {', '.join(set_parts)} WHERE run_id = :r"),
            params,
        )


def finish_run(engine: Engine, run_id: UUID, status: str, *, detail: dict | None = None, **finals) -> None:
    """Terminal: stamp finished_at + status, optionally with final field values."""
    import json

    cols = [c for c in finals if c in _FINAL_FIELDS]
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


def fail_run_by_dagster_id(engine: Engine, dagster_run_id: str) -> int:
    """Mark any not-yet-finished ingest_run for this Dagster run as failed.
    Called by the run_failure_sensor. Returns rows updated."""
    with engine.begin() as conn:
        res = conn.execute(
            text(
                "UPDATE bronze.ingest_run SET status = 'failed', finished_at = now() "
                "WHERE dagster_run_id = :d AND status <> 'success'"
            ),
            {"d": dagster_run_id},
        )
    return res.rowcount


def latest_run(engine: Engine) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM bronze.ingest_run ORDER BY started_at DESC LIMIT 1")
        ).mappings().first()
    return dict(row) if row else None
