"""Data-quality suite: SQL + Pandera checks over the bronze/silver/gold warehouse.

SQL-BACKED, LOCAL-POSTGRES-ONLY. The checks need a SQLAlchemy engine and
schema-qualified reads, which the Supabase PostgREST backend cannot do. They run
as the Dagster `data_quality` asset (terminal, owns bronze.ingest_run's
finish_run) and via `python -m app.quality.run`. Results persist to
quality.dq_run / quality.dq_result; `/api/health/data` only READS those (through
the public.dq_* compat views), so the endpoint works on both backends.
"""

from app.quality.checks import ALL_CHECKS, CheckResult

__all__ = ["ALL_CHECKS", "CheckResult"]
