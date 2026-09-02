"""Jobs over the ingestion assets."""

from __future__ import annotations

from dagster import AssetSelection, define_asset_job

# Everything: land all user slugs -> silver -> gold -> refresh MVs.
nightly_ingest_job = define_asset_job(
    name="nightly_ingest_job",
    selection=AssetSelection.all(),
    description="Full ingestion: bronze landing (all slugs) -> silver dedup -> "
    "gold star -> MV refresh.",
)
