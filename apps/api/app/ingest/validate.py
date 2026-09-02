"""Pre-landing validation: split parsed export rows into valid / quarantined.

Runs the Pandera schema (schemas.py) over a DataFrame built from the parsed
list-of-dicts, maps Pandera failure_cases to the quarantine rule vocabulary,
and returns the clean rows plus a list of quarantine records.

Blocking rules quarantine the row. `reason_start`/`reason_end` enum misses are
WARN-only (Owner Decision 7): the row still lands, the count goes into
ingest_run.detail.

On real data every blocking rule passes -- the malformed fixture is what
exercises this module (tests/test_validate.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import text

from app.ingest.schemas import (
    RAW_ROW_SCHEMA,
    REASON_END_VALUES,
    REASON_START_VALUES,
)

# Pandera check name -> quarantine rule slug. ts_parseable splits in two below.
_CHECK_TO_RULE = {
    "ms_played_range": "ms_played_range",
    "platform_type": "platform_type",
    "music_row_track_name": "music_row_track_name",
}


@dataclass
class QuarantineRow:
    user_id: UUID
    source_file: str
    source_index: int
    rule: str
    detail: str
    raw: dict


@dataclass
class ValidationOutcome:
    valid: list[dict] = field(default_factory=list)
    quarantined: list[QuarantineRow] = field(default_factory=list)
    warn_counts: dict[str, int] = field(default_factory=dict)


def _split_ts_rule(row: dict) -> str:
    ts = row.get("ts")
    if ts is None or (isinstance(ts, float) and pd.isna(ts)) or str(ts or "").strip() == "":
        return "ts_missing"
    return "ts_unparseable"


def validate_rows(
    rows: list[dict],
    *,
    source_file: str,
    user_id: UUID,
    run_id: Any = None,
) -> ValidationOutcome:
    """`rows` is the parsed export array (already dict-checked in read_export;
    any non-dict elements are passed in as {'__not_a_dict__': <repr>} and
    quarantined here as row_not_a_dict)."""
    out = ValidationOutcome()
    if not rows:
        return out

    bad_index: dict[int, list[tuple[str, str]]] = {}

    # Elements that failed the is-a-dict check upstream.
    real_rows: list[tuple[int, dict]] = []
    for i, r in enumerate(rows):
        if isinstance(r, dict) and "__not_a_dict__" not in r:
            real_rows.append((i, r))
        else:
            detail = r.get("__not_a_dict__") if isinstance(r, dict) else repr(r)
            bad_index.setdefault(i, []).append(("row_not_a_dict", str(detail)[:500]))

    if real_rows:
        idx = [i for i, _ in real_rows]
        df = pd.DataFrame([r for _, r in real_rows], index=idx)
        try:
            RAW_ROW_SCHEMA.validate(df, lazy=True)
        except Exception as exc:  # pandera SchemaErrors
            failure_cases = getattr(exc, "failure_cases", None)
            if failure_cases is None:
                raise
            for _, fc in failure_cases.iterrows():
                check = fc.get("check")
                col = fc.get("column")
                fail_idx = fc.get("index")
                fcase = fc.get("failure_case")
                # A null/absent ts raises the implicit not_nullable check on the
                # ts column; a present-but-garbage ts raises ts_parseable.
                if check == "ts_parseable" or (
                    str(check).startswith("not_nullable") and col == "ts"
                ):
                    if fail_idx is None or fail_idx not in idx:
                        continue
                    rule = _split_ts_rule(rows[fail_idx])
                    bad_index.setdefault(fail_idx, []).append((rule, str(fcase)[:500]))
                    continue
                rule = _CHECK_TO_RULE.get(str(check))
                if rule is None:
                    continue
                if fail_idx is None:
                    # dataframe-level check with no index -> re-scan to attribute
                    continue
                if fail_idx in idx:
                    bad_index.setdefault(fail_idx, []).append((rule, str(fcase)[:500]))

    # First rule wins per row (deterministic: schema column order, then df check).
    for i, r in enumerate(rows):
        if i in bad_index:
            rule, detail = bad_index[i][0]
            raw = r if isinstance(r, dict) and "__not_a_dict__" not in r else {"_raw_repr": repr(r)}
            out.quarantined.append(
                QuarantineRow(
                    user_id=user_id,
                    source_file=source_file,
                    source_index=i,
                    rule=rule,
                    detail=detail,
                    raw=raw,
                )
            )
            continue

        # Row is valid. Warn-only enum checks (do not quarantine).
        rs = r.get("reason_start")
        if rs is not None and str(rs) not in REASON_START_VALUES:
            out.warn_counts["reason_start_enum"] = out.warn_counts.get("reason_start_enum", 0) + 1
        re_ = r.get("reason_end")
        if re_ is not None and str(re_) not in REASON_END_VALUES:
            out.warn_counts["reason_end_enum"] = out.warn_counts.get("reason_end_enum", 0) + 1

        out.valid.append(r)

    return out


def write_quarantine(conn, rows: list[QuarantineRow], *, run_id=None) -> int:
    """Insert quarantine rows. `conn` is an open SQLAlchemy connection inside
    the caller's transaction. Returns the count written."""
    if not rows:
        return 0
    import json

    conn.execute(
        text(
            """
            INSERT INTO bronze.quarantine
                (run_id, user_id, source_file, source_index, rule, detail, _raw)
            VALUES
                (:run_id, :user_id, :source_file, :source_index, :rule, :detail, CAST(:raw AS jsonb))
            """
        ),
        [
            {
                "run_id": str(run_id) if run_id else None,
                "user_id": str(q.user_id),
                "source_file": q.source_file,
                "source_index": q.source_index,
                "rule": q.rule,
                "detail": q.detail,
                "raw": json.dumps({k: v for k, v in q.raw.items() if k != "ip_addr"}, default=str),
            }
            for q in rows
        ],
    )
    return len(rows)
