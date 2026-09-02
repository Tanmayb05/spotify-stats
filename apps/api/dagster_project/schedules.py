"""Schedules. Shipped STOPPED -- a portfolio repo should not auto-run a daemon
job on clone; enable it in the Dagster UI (Automation tab) when wanted.
"""

from __future__ import annotations

from dagster import DefaultScheduleStatus, ScheduleDefinition

from dagster_project.jobs import nightly_ingest_job

nightly_ingest_schedule = ScheduleDefinition(
    name="nightly_ingest_schedule",
    job=nightly_ingest_job,
    cron_schedule="0 3 * * *",
    execution_timezone="UTC",
    default_status=DefaultScheduleStatus.STOPPED,
    description="03:00 UTC daily. Idempotent: a night with no new export files "
    "lands nothing and just rebuilds the star.",
)
