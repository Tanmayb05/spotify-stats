"""Dagster code location for the Spotify Insights ingestion pipeline (Phase 12).

The asset graph wraps the plain-Python pipeline library in app/ingest/:

    raw_streams (per-user-slug partition)
      +-> quarantine        (unpartitioned)
      +-> silver_streams    (unpartitioned, dedup, full rebuild)
            +-> gold_star @multi_asset -> dim_user / dim_time / dim_artist
            |                             dim_track / dim_album / fact_streams
            +-> refreshed_views (terminal; V7 MV-freshness assertion)

`dagster dev -m dagster_project.definitions` (or the compose `dagster` service)
serves the lineage graph + the nightly schedule. No app/ code imports this
package -- it is orchestration only.
"""

from dagster_project.definitions import defs

__all__ = ["defs"]
