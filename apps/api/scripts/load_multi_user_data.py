"""DEPRECATED (Phase 12). Do not use.

This batch-loaded the 9 other users' Extended Streaming History from
data/other users/<slug>/Streaming_History_Audio*.json straight into
public.streaming_history (stripping ip_addr, one users row per slug). It has
been replaced by the Dagster ingestion pipeline (apps/api/dagster_project/,
backed by app/ingest/), which discovers the same per-user files, lands them
into bronze, dedups to silver, and builds gold.fact_streams -- incrementally,
idempotently, with a quarantine lane and per-run/per-user metrics.

The per-user slug -> display-name map that used to live here is now the
canonical USER_SLUGS in app/ingest/discover.py (re-exported below for any
external importer). discover.py's discover_files(only=[...]) is the direct
replacement for the old --only flag; a per-user re-ingest is
`dagster job execute` with the raw_streams partition for that slug, or
`build_star_schema.py --only <slug>`.

Load data now with either:

    docker compose exec dagster \\
        dagster job execute -j nightly_ingest_job -m dagster_project.definitions

    cd apps/api && python scripts/build_star_schema.py            # all users
    cd apps/api && python scripts/build_star_schema.py --only amit sam

See documentation/INGESTION.md.
"""

import sys

from app.ingest.discover import USER_SLUGS

# Back-compat alias: this module historically exported the map as USERS.
USERS = USER_SLUGS


def main() -> None:
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
