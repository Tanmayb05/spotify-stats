"""The ingestion asset graph.

    raw_streams (StaticPartitionsDefinition over discover.ALL_SLUGS)
      +-> quarantine        (unpartitioned; count of rows rejected pre-landing)
      +-> silver_streams    (unpartitioned; TRUNCATE + dedup rebuild from bronze)
            +-> gold_star @multi_asset  ->  dim_user  dim_time  dim_artist
            |                               dim_track dim_album fact_streams
            +-> refreshed_views  (refresh MVs + V7 freshness assertion)
                  +-> data_quality  (terminal; app.quality suite, owns finish_run,
                                     raises on a blocking-severity failure)

Transaction shape (matches scripts/build_star_schema.py, which stays a valid
standalone entrypoint):

  * raw_streams  -- one engine.begin() per file (append-only landing).
  * gold_star    -- the whole TRUNCATE + dims + fact rebuild in ONE
    postgres.begin(): a mid-rebuild failure leaves the previous star serving
    the app. @multi_asset gives one transaction AND six named lineage nodes.
  * refreshed_views -- its own transaction AFTER gold_star commits (a REFRESH
    inside the TRUNCATE/INSERT txn would see pre-commit state -- R4).

Run metrics (bronze.ingest_run / _run_user) are written through metrics.py,
which uses its own short-lived connections OUTSIDE these transactions so a
failed run still leaves a status-bearing row. The ingest_run row is keyed to
Dagster's context.run_id via metrics.ensure_run.
"""

from dagster import (
    AssetExecutionContext,
    AssetOut,
    MaterializeResult,
    MetadataValue,
    StaticPartitionsDefinition,
    asset,
    multi_asset,
)
from sqlalchemy import text

from app.ingest import dedup, enrich, metrics
from app.ingest.discover import ALL_SLUGS, discover_files
from app.ingest.landing import get_or_create_user, land_file, user_watermark
from dagster_project.resources import DataRootResource, PostgresResource

slug_partitions = StaticPartitionsDefinition(ALL_SLUGS)


class IngestVerificationError(Exception):
    """A pipeline verification gate (V1, V7) failed -- fails the Dagster run."""


# ---------------------------------------------------------------------------
# bronze
# ---------------------------------------------------------------------------
def _land_slug(context, postgres, data_root, run_id, slug: str) -> dict:
    """Land every discovered export file for one user slug. Own transaction per
    file (append-only). Records per-user metrics; returns a counter dict the
    caller folds into the run totals."""
    files = discover_files(root=data_root.root, only=[slug])
    context.log.info("slug=%s: %d export file(s) discovered", slug, len(files))

    files_new = rows_in = rows_landed = rows_quar = below_wm = 0
    warn_counts: dict = {}
    max_ts = None
    user_id = None

    for df in files:
        with postgres.begin() as conn:
            user_id = get_or_create_user(conn, df.slug, df.display_name, df.is_primary)
            wm = user_watermark(conn, user_id)
            res = land_file(conn, df, user_id, run_id, wm)
        if res.skipped_reason:
            context.log.info("  %s  SKIP (%s)", df.rel_path, res.skipped_reason)
            continue
        files_new += 1
        rows_in += res.rows_in_file
        rows_landed += res.rows_landed
        rows_quar += res.rows_quarantined
        below_wm += res.rows_below_watermark
        for k, v in res.warn_counts.items():
            warn_counts[k] = warn_counts.get(k, 0) + v
        if res.max_ts and (max_ts is None or res.max_ts > max_ts):
            max_ts = res.max_ts
        context.log.info(
            "  %s  landed=%d quarantined=%d below_wm=%d",
            df.rel_path, res.rows_landed, res.rows_quarantined, res.rows_below_watermark,
        )

    rows_valid = rows_in - rows_quar
    if user_id is not None:
        metrics.record_user(
            postgres.engine, run_id, user_id,
            max_ts=max_ts,
            files_seen=len(files), files_new=files_new,
            rows_raw=rows_in, rows_valid=rows_valid,
            rows_quarantined=rows_quar, rows_landed=rows_landed,
        )
    return {
        "slug": slug,
        "files_seen": len(files),
        "files_new": files_new,
        "rows_raw": rows_in,
        "rows_valid": rows_valid,
        "rows_landed": rows_landed,
        "rows_quarantined": rows_quar,
        "rows_below_watermark": below_wm,
        "warn_counts": warn_counts,
        "had_files": bool(files),
    }


@asset(
    partitions_def=slug_partitions,
    group_name="bronze",
    description="Append export files to bronze.raw_streams (file- and row-level "
    "idempotent). One partition per user slug; an unpartitioned run "
    "(nightly_ingest_job) lands ALL slugs.",
)
def raw_streams(
    context: AssetExecutionContext,
    postgres: PostgresResource,
    data_root: DataRootResource,
) -> MaterializeResult:
    run_id = metrics.ensure_run(postgres.engine, context.run.run_id)

    if context.has_partition_key:
        slugs = [context.partition_key]
    else:
        slugs = list(ALL_SLUGS)
        context.log.info("unpartitioned run: landing all %d slugs", len(slugs))

    totals = {
        "files_seen": 0, "files_new": 0, "rows_raw": 0, "rows_valid": 0,
        "rows_landed": 0, "rows_quarantined": 0, "rows_below_watermark": 0,
    }
    users = 0
    warn_counts: dict = {}
    for slug in slugs:
        r = _land_slug(context, postgres, data_root, run_id, slug)
        for k in totals:
            totals[k] += r[k]
        users += 1 if r["had_files"] else 0
        for k, v in r["warn_counts"].items():
            warn_counts[k] = warn_counts.get(k, 0) + v

    metrics.bump_run(
        postgres.engine, run_id,
        users=users,
        files_seen=totals["files_seen"], files_new=totals["files_new"],
        rows_raw=totals["rows_raw"], rows_valid=totals["rows_valid"],
        rows_quarantined=totals["rows_quarantined"], rows_landed=totals["rows_landed"],
    )

    return MaterializeResult(
        metadata={
            "slugs": MetadataValue.json(slugs),
            "files_seen": totals["files_seen"],
            "files_new": totals["files_new"],
            "rows_in_files": totals["rows_raw"],
            "rows_landed": totals["rows_landed"],
            "rows_quarantined": totals["rows_quarantined"],
            "rows_below_watermark": totals["rows_below_watermark"],
            "warn_counts": MetadataValue.json(warn_counts),
            "ingest_run_id": str(run_id),
        }
    )


@asset(
    deps=["raw_streams"],
    group_name="bronze",
    description="Count of rows rejected by validation and written to "
    "bronze.quarantine for the latest run (empty on real data).",
)
def quarantine(
    context: AssetExecutionContext,
    postgres: PostgresResource,
) -> MaterializeResult:
    run_id = metrics.ensure_run(postgres.engine, context.run.run_id)
    with postgres.connect() as conn:
        by_rule = conn.execute(
            text(
                "SELECT rule, count(*) AS n FROM bronze.quarantine "
                "WHERE run_id = :r GROUP BY rule ORDER BY n DESC"
            ),
            {"r": str(run_id)},
        ).mappings().all()
        total = conn.execute(
            text("SELECT count(*) FROM bronze.quarantine WHERE run_id = :r"),
            {"r": str(run_id)},
        ).scalar_one()
    rules = {r["rule"]: r["n"] for r in by_rule}
    context.log.info("quarantine rows this run: %d %s", total, rules or "")
    return MaterializeResult(
        metadata={
            "rows_quarantined": total,
            "by_rule": MetadataValue.json(rules),
        }
    )


# ---------------------------------------------------------------------------
# silver
# ---------------------------------------------------------------------------
@asset(
    deps=["raw_streams"],
    group_name="silver",
    description="Rebuild silver.streams from bronze, collapsing byte-identical "
    "export dupes on (user_id, row_fingerprint), keep lowest _ingest_id.",
)
def silver_streams(
    context: AssetExecutionContext,
    postgres: PostgresResource,
) -> MaterializeResult:
    run_id = metrics.ensure_run(postgres.engine, context.run.run_id)
    with postgres.begin() as conn:
        stats = dedup.build_silver(conn)
    context.log.info(
        "silver: %d bronze -> %d silver (%d dups dropped)",
        stats.rows_in, stats.rows_out, stats.dups_dropped,
    )

    # Per-user dedup delta into ingest_run_user (V5).
    with postgres.connect() as conn:
        uid_by_name = {
            r[0]: r[1]
            for r in conn.execute(text("SELECT username, id FROM users")).all()
        }
    for row in stats.per_user:
        uid = uid_by_name.get(row["username"])
        if uid is not None:
            metrics.record_user(
                postgres.engine, run_id, uid,
                dups_dropped=row["dups_dropped"], rows_silver=row["silver"],
            )
    metrics.bump_run(
        postgres.engine, run_id,
        dups_dropped=stats.dups_dropped, rows_silver=stats.rows_out,
    )

    return MaterializeResult(
        metadata={
            "rows_in_bronze": stats.rows_in,
            "rows_out_silver": stats.rows_out,
            "dups_dropped": stats.dups_dropped,
            "per_user": MetadataValue.json(stats.per_user),
        }
    )


# ---------------------------------------------------------------------------
# gold -- one transaction, six named assets
# ---------------------------------------------------------------------------
_GOLD_OUTS = {
    "dim_user": AssetOut(group_name="gold"),
    "dim_time": AssetOut(group_name="gold"),
    "dim_artist": AssetOut(group_name="gold"),
    "dim_track": AssetOut(group_name="gold"),
    "dim_album": AssetOut(group_name="gold"),
    "fact_streams": AssetOut(group_name="gold"),
}


@multi_asset(
    outs=_GOLD_OUTS,
    deps=["silver_streams"],
    description="TRUNCATE gold.fact_streams then rebuild all dims + fact from "
    "silver in ONE transaction.",
)
def gold_star(
    context: AssetExecutionContext,
    postgres: PostgresResource,
):
    run_id = metrics.ensure_run(postgres.engine, context.run.run_id)
    with postgres.begin() as conn:
        conn.execute(text("TRUNCATE TABLE gold.fact_streams RESTART IDENTITY"))

        n_user = enrich.stage_dim_user(conn)
        n_time = enrich.stage_dim_time(conn)
        a = enrich.stage_dim_artist(conn)
        t = enrich.stage_dim_track(conn)
        n_album = enrich.stage_dim_album(conn)
        n_fact = enrich.stage_fact_streams(conn)

        mr = enrich.match_rates(conn)
        v1_ok = enrich.verify_v1(conn)

    if not v1_ok:
        raise IngestVerificationError(
            "V1 FAILED (see logs) -- silver != fact per user"
        )

    # Record fact count + match rates now, but DO NOT mark the run finished --
    # refreshed_views is the true terminal asset (V7). A V7 / infra failure after
    # this point must leave the run non-success; the run_failure_sensor
    # (definitions.py) flips it to 'failed'.
    metrics.bump_run(postgres.engine, run_id, rows_fact=n_fact)
    metrics.set_run_fields(
        postgres.engine, run_id,
        rows_fact=n_fact,
        track_match_rate=mr.track_enriched_rate,
        artist_match_rate=mr.artist_enriched_rate,
        unmatched_tracks=mr.unmatched_tracks,
        unmatched_artists=mr.unmatched_artists,
        detail={
            "artist_fk_rate": mr.artist_fk_rate,
            "track_fk_rate": mr.track_fk_rate,
        },
    )

    context.log.info(
        "gold: dim_user=%d dim_time=%d dim_artist=%d dim_track=%d dim_album=%d fact=%d",
        n_user, n_time, a["after"], t["after"], n_album, n_fact,
    )

    common = {
        "ingest_run_id": str(run_id),
        "artist_enriched_rate": mr.artist_enriched_rate,
        "track_enriched_rate": mr.track_enriched_rate,
    }
    yield MaterializeResult(asset_key="dim_user", metadata={"rows": n_user})
    yield MaterializeResult(asset_key="dim_time", metadata={"rows": n_time})
    yield MaterializeResult(
        asset_key="dim_artist",
        metadata={"rows": a["after"], "stubs_added": a["stubs_added"], **common},
    )
    yield MaterializeResult(
        asset_key="dim_track",
        metadata={"rows": t["after"], "stubs_added": t["stubs_added"], **common},
    )
    yield MaterializeResult(asset_key="dim_album", metadata={"rows": n_album})
    yield MaterializeResult(
        asset_key="fact_streams",
        metadata={"rows": n_fact, "v1_verification": "PASS", **common},
    )


# ---------------------------------------------------------------------------
# refreshed_views -- terminal, with the V7 MV-freshness assertion (R4)
# ---------------------------------------------------------------------------
@asset(
    deps=["fact_streams"],
    group_name="gold",
    description="Refresh monthly_stats / top_artists / top_tracks, then assert "
    "sum(monthly_stats.stream_count) == count(fact_streams) for the primary user (V7).",
)
def refreshed_views(
    context: AssetExecutionContext,
    postgres: PostgresResource,
) -> MaterializeResult:
    run_id = metrics.ensure_run(postgres.engine, context.run.run_id)
    with postgres.begin() as conn:
        conn.execute(text("SELECT refresh_all_views()"))

    with postgres.connect() as conn:
        primary_id = conn.execute(
            text("SELECT id FROM users WHERE is_primary = TRUE LIMIT 1")
        ).scalar_one()
        mv_sum = conn.execute(
            text(
                "SELECT COALESCE(sum(total_streams), 0) FROM monthly_stats "
                "WHERE user_id = :u"
            ),
            {"u": str(primary_id)},
        ).scalar_one()
        # monthly_stats filters `track_name IS NOT NULL`; match that here so the
        # comparison is apples-to-apples (V7 tests MV freshness, not row parity).
        fact_ct = conn.execute(
            text(
                "SELECT count(*) FROM gold.fact_streams "
                "WHERE user_id = :u AND track_name IS NOT NULL"
            ),
            {"u": str(primary_id)},
        ).scalar_one()

    context.log.info("V7: monthly_stats sum=%s  fact_streams=%s", mv_sum, fact_ct)
    if int(mv_sum) != int(fact_ct):
        raise IngestVerificationError(
            f"V7 MV freshness FAILED: monthly_stats sum {mv_sum} != "
            f"fact_streams {fact_ct} (primary user). Views are stale."
        )

    # NOT terminal any longer -- Phase 13's `data_quality` asset owns
    # metrics.finish_run. Leaving status='running' here is deliberate: if
    # data_quality fails on a blocking check (or never runs), the
    # run_failure_sensor flips this run to 'failed'.

    return MaterializeResult(
        metadata={
            "monthly_stats_sum": int(mv_sum),
            "fact_streams_count": int(fact_ct),
            "v7_freshness": "PASS",
            "ingest_run_id": str(run_id),
        }
    )


# ---------------------------------------------------------------------------
# data_quality -- terminal. Runs app.quality over the rebuilt warehouse, owns
# bronze.ingest_run's finish_run, raises on any blocking-severity failure.
# ---------------------------------------------------------------------------
@asset(
    deps=["refreshed_views"],
    group_name="quality",
    description="Run the data-quality suite (app.quality) over the rebuilt "
    "warehouse and persist to quality.dq_run/dq_result. TERMINAL asset: owns "
    "bronze.ingest_run's finish_run (success / partial). Raises on any "
    "blocking-severity failure, leaving status='running' for the "
    "run_failure_sensor to flip to 'failed'.",
)
def data_quality(
    context: AssetExecutionContext,
    postgres: PostgresResource,
) -> MaterializeResult:
    from app.quality.run import run_all, summarize

    run_id = metrics.ensure_run(postgres.engine, context.run.run_id)
    dq_run_id, results = run_all(
        postgres.engine,
        ingest_run_id=run_id,
        dagster_run_id=context.run.run_id,
    )
    s = summarize(results)

    for r in results:
        if not r.passed and not r.skipped:
            context.log.warning(
                "DQ %s [%s/%s] observed=%s expected=%s",
                r.name, r.category, r.severity, r.observed, r.expected,
            )

    md = {
        "dq_run_id": str(dq_run_id),
        "ingest_run_id": str(run_id),
        "checks_total": s["total"],
        "passed": s["passed"],
        "failed_blocking": s["failed"],
        "warned": s["warned"],
        "skipped": s["skipped"],
        "dq_status": s["status"],
        "by_category": MetadataValue.json(s["by_category"]),
        "failures": MetadataValue.json(s["blocking_failures"] + s["warn_failures"]),
    }

    if s["failed"] > 0:
        # Do NOT finish_run -- leave status='running' for the run_failure_sensor.
        raise IngestVerificationError(
            f"Data quality FAILED: {s['failed']} blocking check(s) -- "
            f"{', '.join(s['blocking_failures'])}. See quality.dq_result "
            f"(dq_run_id={dq_run_id})."
        )

    # Merge into the detail that gold_star already wrote (finish_run overwrites
    # the whole JSONB column -- R1).
    prev = metrics.latest_run(postgres.engine) or {}
    prev_detail = prev.get("detail") or {}
    if not isinstance(prev_detail, dict):
        prev_detail = {}
    status = "partial" if s["warned"] > 0 else "success"
    metrics.finish_run(
        postgres.engine, run_id, status,
        detail={
            **prev_detail,
            "dq_run_id": str(dq_run_id),
            "dq_status": s["status"],
            "dq_warned": s["warned"],
            "dq_failed": s["failed"],
        },
    )
    return MaterializeResult(metadata=md)
