"""Dagster Definitions -- the code location entrypoint.

Referenced by pyproject.toml `[tool.dagster] module_name` and by the compose
`dagster` service (`-m dagster_project.definitions`).
"""

from __future__ import annotations

import os

from dagster import (
    Definitions,
    RunFailureSensorContext,
    load_assets_from_modules,
    run_failure_sensor,
)

from app.ingest import metrics
from dagster_project import assets as assets_module
from dagster_project.jobs import nightly_ingest_job
from dagster_project.resources import DataRootResource, PostgresResource
from dagster_project.schedules import nightly_ingest_schedule

all_assets = load_assets_from_modules([assets_module])

_postgres = PostgresResource(database_url=os.getenv("DATABASE_URL"))


@run_failure_sensor(
    monitored_jobs=[nightly_ingest_job],
    description="On a failed nightly_ingest_job run, flip its bronze.ingest_run "
    "row from 'running' to 'failed' (the assets only ever set 'success').",
)
def mark_ingest_run_failed(context: RunFailureSensorContext) -> None:
    n = metrics.fail_run_by_dagster_id(_postgres.engine, context.dagster_run.run_id)
    context.log.info(
        "run %s failed -> marked %d ingest_run row(s) failed",
        context.dagster_run.run_id, n,
    )


defs = Definitions(
    assets=all_assets,
    jobs=[nightly_ingest_job],
    schedules=[nightly_ingest_schedule],
    sensors=[mark_ingest_run_failed],
    resources={
        # database_url unset -> settings.database_url (repo-root spotify-insights.env),
        # so a bare `dagster dev` works. Compose passes DATABASE_URL explicitly.
        "postgres": _postgres,
        "data_root": DataRootResource(path=os.getenv("INGEST_DATA_ROOT")),
    },
)
