"""DEPRECATED (Phase 12). Do not use.

This was the original one-shot loader: read data/streaming_[0-9]*.json, transform
each row (INCLUDING ip_addr), batch-insert straight into public.streaming_history,
refresh the MVs. It has been replaced by the Dagster ingestion pipeline
(apps/api/dagster_project/, backed by app/ingest/). The pipeline is incremental,
idempotent, has a quarantine lane and run metrics, pops ip_addr before every
bronze write, and builds bronze -> silver -> gold.fact_streams.

The old body -- including its blocking input() prompt and its ip_addr-retaining
transform_record -- was DELETED in Phase 12 Commit 5: it was the last code path
in the repo that could write ip_addr into the database, and keeping it live
"just deprecated" is a PII footgun.

Load data now with either:

    # local Postgres, full pipeline (discover -> bronze -> silver -> gold -> MVs)
    docker compose exec dagster \\
        dagster job execute -j nightly_ingest_job -m dagster_project.definitions

    # or, without Dagster, the same pipeline as a plain script:
    cd apps/api && python scripts/build_star_schema.py

See documentation/INGESTION.md.
"""

import sys

# Re-exported for any external caller that imported the slug map from here
# (the canonical definition now lives in app/ingest/discover.py).
from app.ingest.discover import USER_SLUGS  # noqa: F401


def main() -> None:
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
