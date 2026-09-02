"""Pandera DataFrame contracts for the silver and gold layers.

SCOPE, honestly stated: nearly every DQ check in ``checks.py`` is a SQL aggregate
and belongs in SQL -- pulling 338k rows into pandas to COUNT them would be
strictly worse. These schemas therefore validate a bounded SAMPLE
(``SAMPLE_ROWS``) and exist to catch what aggregates cannot: dtype and shape
drift (``ms_played`` becoming text, ``ts`` losing its tz, a column disappearing
after a migration).

They deliberately do NOT share code with ``app/ingest/schemas.py``: that schema
validates RAW export dicts pre-landing (``master_metadata_track_name``,
``spotify_track_uri``, ``reason_start``) -- a different column set entirely. The
only genuinely shared constant is ``MS_PER_DAY``, imported from there.

dtype note (R11): ``pd.read_sql`` infers dtypes from the returned rows, so a
nullable integer column comes back ``float64`` when a NULL is present and
``int64`` when not. Columns that can be null use pandas nullable dtypes
(``Int64``) and ``coerce=True`` so the check does not flake between runs.
"""

from __future__ import annotations

import pandas as pd
from pandera.pandas import Check, Column, DataFrameSchema

from app.ingest.schemas import MS_PER_DAY

SAMPLE_ROWS = 5000

SILVER_STREAMS_SCHEMA = DataFrameSchema(
    columns={
        "user_id": Column("object", nullable=False),
        "ts": Column("datetime64[ns, UTC]", nullable=False),
        "ms_played": Column(
            "Int64", checks=Check.in_range(0, MS_PER_DAY, name="ms_played_in_day"),
            nullable=False, coerce=True,
        ),
        "row_fingerprint": Column(
            "object",
            checks=Check.str_length(64, 64, name="fingerprint_is_sha256_hex"),
            nullable=True,
        ),
    },
    strict=False,
    coerce=False,
    name="silver_streams_sample",
)

FACT_STREAMS_SCHEMA = DataFrameSchema(
    columns={
        "stream_id": Column("int64", nullable=False, unique=True),
        "user_id": Column("object", nullable=False),
        "time_key": Column("Int64", nullable=True, coerce=True),
        "ms_played": Column(
            "Int64", checks=Check.in_range(0, MS_PER_DAY, name="ms_played_in_day"),
            nullable=False, coerce=True,
        ),
        "ts": Column("datetime64[ns, UTC]", nullable=False),
        "skipped": Column("boolean", nullable=True, coerce=True),
        "is_music": Column("boolean", nullable=True, coerce=True),
    },
    strict=False,
    coerce=False,
    name="fact_streams_sample",
)

DIM_TRACK_SCHEMA = DataFrameSchema(
    columns={
        "track_key": Column("object", nullable=False, unique=True),
        "track_name": Column("object", nullable=False),
        "audio_source": Column(
            "object",
            checks=Check.isin(
                ["none", "enriched", "proxy_heuristic"], name="audio_source_enum"
            ),
        ),
        "release_year": Column("Int16", nullable=True, coerce=True),
    },
    strict=False,
    coerce=False,
    name="dim_track_sample",
)


def validate_sample(schema: DataFrameSchema, df: pd.DataFrame) -> list[dict]:
    """Run one schema against a sample; return a list of failure-case dicts
    (empty == passed). Reuses the ``lazy=True`` + ``failure_cases`` pattern from
    ``app/ingest/validate.py``.
    """
    if df.empty:
        return []
    try:
        schema.validate(df, lazy=True)
    except Exception as exc:  # pandera SchemaErrors
        failure_cases = getattr(exc, "failure_cases", None)
        if failure_cases is None:
            raise
        return failure_cases.head(20).to_dict("records")
    return []
