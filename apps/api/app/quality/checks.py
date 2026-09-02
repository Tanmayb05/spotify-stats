"""Data-quality check registry.

Every check is a function ``(conn) -> CheckResult | list[CheckResult]`` registered
by ``@check(...)``. ``conn`` is an OPEN, READ-ONLY SQLAlchemy connection supplied
by ``run.py`` -- checks never open their own, never commit. (Persistence is
``run.py``'s job and uses its own short-lived connection, per the
``app/ingest/metrics.py`` rule.)

``name`` is a stable identifier: the Data Health page groups on it and
``quality.dq_result`` rows accumulate under it. Renaming one breaks the trend.

The 6 required categories and their split:

  uniqueness (3, blocking)             -- real un-enforced invariants
  referential_integrity (4, blocking) -- FK orphans (also catches an un-VALIDated FK)
  range (4 SQL blocking/warn + 2 pandera warn)
  freshness (3: 1 blocking, 2 warn)
  completeness (3 blocking + 1 warn)
  anomaly (2, warn)                    -- rolling MAD + run-over-run z-score
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from sqlalchemy import text

import pandas as pd

from app.ingest.enrich import match_rates
from app.ingest.schemas import MS_PER_DAY
from app.quality.pandera_schemas import (
    DIM_TRACK_SCHEMA,
    FACT_STREAMS_SCHEMA,
    SAMPLE_ROWS,
    SILVER_STREAMS_SCHEMA,
    validate_sample,
)

Severity = Literal["blocking", "warn"]
Category = Literal[
    "uniqueness",
    "referential_integrity",
    "range",
    "freshness",
    "completeness",
    "anomaly",
]

CATEGORIES: tuple[Category, ...] = (
    "uniqueness",
    "referential_integrity",
    "range",
    "freshness",
    "completeness",
    "anomaly",
)


# ---------------------------------------------------------------------------
# Thresholds -- one greppable, diff-reviewable, unit-testable dict.
# NOT Settings (8 more hand-written os.getenv lines for numbers nobody tunes at
# runtime) and NOT a DB table (bootstrapping problem on a fresh DB).
#
# Rate thresholds are set BELOW measured values on the real seeded DB
# (2026-09-02, 338,270 fact rows) with headroom, so the suite is green on day one:
#   track_name / artist_name completeness : measured 0.9961 -> threshold 0.95
#   time_key completeness                 : measured 1.0000 -> threshold 0.999
#   artist audio_source='enriched'        : measured 0.0000 -> WARN, threshold 0.0
#   track  audio_source='enriched'        : measured 0.0397 -> WARN, threshold 0.0
# (audio-features enrichment does not exist in this repo -- Spotify deprecated the
#  endpoint Nov 2024. `enrichment_coverage` is a WARN informational signal only.)
# ---------------------------------------------------------------------------
THRESHOLDS: dict[str, float] = {
    "freshness_ingest_max_age_days": 45,     # bronze.ingest_state.ingested_at
    "freshness_user_max_stale_days": 2000,   # per-user max(fact ts); exports are historical
    "completeness_track_name_rate": 0.95,
    "completeness_artist_name_rate": 0.95,
    "completeness_time_key_rate": 0.999,
    "enrichment_artist_rate": 0.0,           # WARN only -- see note above
    "enrichment_track_rate": 0.0,            # WARN only
    "anomaly_mad_k": 4.0,
    "anomaly_min_history_days": 30,
    "anomaly_min_runs": 6,
    "release_year_min": 1900,
}


@dataclass
class CheckResult:
    name: str
    category: Category
    severity: Severity
    passed: bool
    observed: str | None = None
    expected: str | None = None
    rows_failed: int = 0
    detail: dict[str, Any] | None = None
    # beyond the roadmap's 8 fields, needed by the DDL / UI:
    observed_numeric: float | None = None
    skipped: bool = False
    user_id: str | None = None
    duration_ms: int | None = None


@dataclass
class Check:
    name: str
    category: Category
    severity: Severity
    fn: Callable[[Any], "CheckResult | list[CheckResult]"]
    description: str = ""


ALL_CHECKS: list[Check] = []


def check(*, name: str, category: Category, severity: Severity, description: str = ""):
    def _wrap(fn):
        ALL_CHECKS.append(
            Check(name=name, category=category, severity=severity, fn=fn, description=description)
        )
        return fn

    return _wrap


def _count_result(
    conn,
    sql: str,
    *,
    name: str,
    category: Category,
    severity: Severity,
    expected: str,
    params: dict | None = None,
) -> CheckResult:
    """Standard shape: a SQL COUNT(*) of OFFENDING rows; pass iff 0."""
    n = int(conn.execute(text(sql), params or {}).scalar_one())
    return CheckResult(
        name=name,
        category=category,
        severity=severity,
        passed=(n == 0),
        observed=f"{n} offending row(s)",
        observed_numeric=float(n),
        expected=expected,
        rows_failed=n,
    )


# ===========================================================================
# uniqueness (3, all blocking)
# ===========================================================================
@check(
    name="fact_ingest_id_unique",
    category="uniqueness",
    severity="blocking",
    description="gold.fact_streams._ingest_id has no FK and no unique constraint "
    "(009:155). A double-insert in the gold_star rebuild would duplicate plays.",
)
def fact_ingest_id_unique(conn) -> CheckResult:
    return _count_result(
        conn,
        """
        SELECT count(*) FROM (
          SELECT _ingest_id FROM gold.fact_streams
          WHERE _ingest_id IS NOT NULL
          GROUP BY _ingest_id HAVING count(*) > 1
        ) d
        """,
        name="fact_ingest_id_unique",
        category="uniqueness",
        severity="blocking",
        expected="0 duplicate _ingest_id in gold.fact_streams (no DB constraint enforces this)",
    )


@check(
    name="dim_track_uri_unique",
    category="uniqueness",
    severity="blocking",
    description="track_key = spotify_track_uri when present (D3); two track_keys "
    "sharing a URI means a hash-fallback collision or a casing bug.",
)
def dim_track_uri_unique(conn) -> CheckResult:
    return _count_result(
        conn,
        """
        SELECT count(*) FROM (
          SELECT spotify_track_uri FROM gold.dim_track
          WHERE spotify_track_uri IS NOT NULL
          GROUP BY spotify_track_uri HAVING count(DISTINCT track_key) > 1
        ) d
        """,
        name="dim_track_uri_unique",
        category="uniqueness",
        severity="blocking",
        expected="0 spotify_track_uri shared across >1 track_key",
    )


@check(
    name="silver_fingerprint_unique",
    category="uniqueness",
    severity="blocking",
    description="Migration 011's header: row-level idempotency is app logic in "
    "dedup.py, NOT a DB constraint. This check is its only enforcement.",
)
def silver_fingerprint_unique(conn) -> CheckResult:
    return _count_result(
        conn,
        """
        SELECT count(*) FROM (
          SELECT user_id, row_fingerprint FROM silver.streams
          WHERE row_fingerprint IS NOT NULL
          GROUP BY user_id, row_fingerprint HAVING count(*) > 1
        ) d
        """,
        name="silver_fingerprint_unique",
        category="uniqueness",
        severity="blocking",
        expected="0 duplicate (user_id, row_fingerprint) in silver.streams (dedup.py invariant)",
    )


# ===========================================================================
# referential_integrity (4, blocking) -- FK orphans
# These are DB-enforced today, so tautologies on a healthy DB -- kept because
# they are what the roadmap's verify recipe exercises, and because 009 creates
# the FKs NOT VALID then validates (a failed validate leaves them unenforced).
# ===========================================================================
def _fk_check(conn, *, name, fact_col, dim_table, dim_col) -> CheckResult:
    sql = f"""
        SELECT count(*)
        FROM gold.fact_streams f
        LEFT JOIN {dim_table} d ON d.{dim_col} = f.{fact_col}
        WHERE f.{fact_col} IS NOT NULL AND d.{dim_col} IS NULL
    """
    return _count_result(
        conn,
        sql,
        name=name,
        category="referential_integrity",
        severity="blocking",
        expected=f"0 fact_streams.{fact_col} without a matching {dim_table} row",
    )


@check(name="fact_track_key_fk", category="referential_integrity", severity="blocking")
def fact_track_key_fk(conn) -> CheckResult:
    return _fk_check(
        conn, name="fact_track_key_fk", fact_col="track_key",
        dim_table="gold.dim_track", dim_col="track_key",
    )


@check(name="fact_user_id_fk", category="referential_integrity", severity="blocking")
def fact_user_id_fk(conn) -> CheckResult:
    return _fk_check(
        conn, name="fact_user_id_fk", fact_col="user_id",
        dim_table="gold.dim_user", dim_col="user_id",
    )


@check(name="fact_artist_key_fk", category="referential_integrity", severity="blocking")
def fact_artist_key_fk(conn) -> CheckResult:
    return _fk_check(
        conn, name="fact_artist_key_fk", fact_col="artist_key",
        dim_table="gold.dim_artist", dim_col="artist_key",
    )


@check(name="fact_time_key_fk", category="referential_integrity", severity="blocking")
def fact_time_key_fk(conn) -> CheckResult:
    return _fk_check(
        conn, name="fact_time_key_fk", fact_col="time_key",
        dim_table="gold.dim_time", dim_col="time_key",
    )


# ===========================================================================
# range (4 SQL)
# ===========================================================================
@check(name="ms_played_range", category="range", severity="blocking")
def ms_played_range(conn) -> CheckResult:
    return _count_result(
        conn,
        f"SELECT count(*) FROM gold.fact_streams WHERE ms_played < 0 OR ms_played > {MS_PER_DAY}",
        name="ms_played_range",
        category="range",
        severity="blocking",
        expected=f"every ms_played in [0, {MS_PER_DAY}] (0..24h)",
    )


@check(name="release_year_range", category="range", severity="warn")
def release_year_range(conn) -> CheckResult:
    lo = int(THRESHOLDS["release_year_min"])
    return _count_result(
        conn,
        """
        SELECT count(*) FROM gold.dim_track
        WHERE release_year IS NOT NULL
          AND (release_year < :lo OR release_year > EXTRACT(YEAR FROM now())::int + 1)
        """,
        name="release_year_range",
        category="range",
        severity="warn",
        expected=f"release_year in [{lo}, next year]",
        params={"lo": lo},
    )


@check(name="mood_proxy_range", category="range", severity="warn")
def mood_proxy_range(conn) -> CheckResult:
    return _count_result(
        conn,
        """
        SELECT count(*) FROM gold.dim_track
        WHERE (mood_proxy_valence      IS NOT NULL AND mood_proxy_valence      NOT BETWEEN 0 AND 1)
           OR (mood_proxy_energy       IS NOT NULL AND mood_proxy_energy       NOT BETWEEN 0 AND 1)
           OR (mood_proxy_danceability IS NOT NULL AND mood_proxy_danceability NOT BETWEEN 0 AND 1)
        """,
        name="mood_proxy_range",
        category="range",
        severity="warn",
        expected="every non-null mood_proxy_* in [0, 1]",
    )


@check(name="ingest_run_match_rate_range", category="range", severity="blocking")
def ingest_run_match_rate_range(conn) -> CheckResult:
    # Verbatim the `0 <= match rates <= 1` invariant from migration 011's COMMENT.
    return _count_result(
        conn,
        """
        SELECT count(*) FROM bronze.ingest_run
        WHERE (track_match_rate  IS NOT NULL AND track_match_rate  NOT BETWEEN 0 AND 1)
           OR (artist_match_rate IS NOT NULL AND artist_match_rate NOT BETWEEN 0 AND 1)
        """,
        name="ingest_run_match_rate_range",
        category="range",
        severity="blocking",
        expected="every non-null match rate in [0, 1] (migration 011 invariant)",
    )


# ---------------------------------------------------------------------------
# range (2 pandera) -- schema-contract on a bounded sample. Category "range"
# because Check.isin / Check.in_range are literally range assertions and it
# avoids muddying completeness's rate semantics.
# ---------------------------------------------------------------------------
def _schema_result(conn, *, name, sql, schemas) -> CheckResult:
    fails: list[dict] = []
    for schema in schemas:
        df = pd.read_sql(text(sql[schema.name]), conn)
        fails.extend({"schema": schema.name, **f} for f in validate_sample(schema, df))
    return CheckResult(
        name=name,
        category="range",
        severity="warn",
        passed=(len(fails) == 0),
        observed=f"{len(fails)} schema violation(s) in a {SAMPLE_ROWS}-row sample",
        observed_numeric=float(len(fails)),
        expected="sampled rows satisfy the dtype/enum/range contract",
        rows_failed=len(fails),
        detail={"failure_cases": fails[:20]} if fails else None,
    )


@check(
    name="silver_schema_contract",
    category="range",
    severity="warn",
    description="Pandera dtype/range contract on a sample of silver.streams. "
    "Catches a column type changing under a migration -- which no aggregate sees.",
)
def silver_schema_contract(conn) -> CheckResult:
    return _schema_result(
        conn,
        name="silver_schema_contract",
        sql={
            "silver_streams_sample": f"SELECT * FROM silver.streams "
            f"ORDER BY _ingest_id DESC LIMIT {SAMPLE_ROWS}"
        },
        schemas=[SILVER_STREAMS_SCHEMA],
    )


@check(
    name="gold_schema_contract",
    category="range",
    severity="warn",
    description="Pandera dtype/enum contract on samples of gold.fact_streams and "
    "gold.dim_track.",
)
def gold_schema_contract(conn) -> CheckResult:
    return _schema_result(
        conn,
        name="gold_schema_contract",
        sql={
            "fact_streams_sample": f"SELECT * FROM gold.fact_streams "
            f"ORDER BY stream_id DESC LIMIT {SAMPLE_ROWS}",
            "dim_track_sample": f"SELECT * FROM gold.dim_track LIMIT {SAMPLE_ROWS}",
        },
        schemas=[FACT_STREAMS_SCHEMA, DIM_TRACK_SCHEMA],
    )


# ===========================================================================
# freshness (3: 1 blocking, 2 warn)
# ===========================================================================
def _now() -> datetime:
    return datetime.now(timezone.utc)


@check(name="ingest_state_recent", category="freshness", severity="warn")
def ingest_state_recent(conn) -> CheckResult:
    row = conn.execute(
        text(
            "SELECT max(ingested_at) AS max_ingested, "
            "EXTRACT(DAY FROM now() - max(ingested_at))::int AS age_days "
            "FROM bronze.ingest_state"
        )
    ).mappings().one()
    limit = THRESHOLDS["freshness_ingest_max_age_days"]
    if row["max_ingested"] is None:
        # A seed_local_db.py-only DB has zero ingest_state rows -- not a defect.
        return CheckResult(
            name="ingest_state_recent",
            category="freshness",
            severity="warn",
            passed=True,
            skipped=True,
            observed="no ingest_state rows",
            expected=f"latest ingest within {limit:g} days",
        )
    age = int(row["age_days"])
    return CheckResult(
        name="ingest_state_recent",
        category="freshness",
        severity="warn",
        passed=(age <= limit),
        observed=f"{age} days since last landed file",
        observed_numeric=float(age),
        expected=f"latest ingest within {limit:g} days",
    )


@check(name="latest_ingest_run_terminal", category="freshness", severity="blocking")
def latest_ingest_run_terminal(conn, *, exclude_run_id: str | None = None) -> CheckResult:
    # Exclude the CURRENT run -- when data_quality itself runs, its own ingest_run
    # row is still 'running' and would fail this check.
    sql = "SELECT run_id, status FROM bronze.ingest_run"
    params: dict = {}
    if exclude_run_id:
        sql += " WHERE run_id <> :x"
        params["x"] = exclude_run_id
    sql += " ORDER BY started_at DESC LIMIT 1"
    row = conn.execute(text(sql), params).mappings().first()
    if row is None:
        return CheckResult(
            name="latest_ingest_run_terminal",
            category="freshness",
            severity="blocking",
            passed=True,
            skipped=True,
            observed="no completed ingest runs",
            expected="latest ingest_run status in (success, partial)",
        )
    ok = row["status"] in ("success", "partial")
    return CheckResult(
        name="latest_ingest_run_terminal",
        category="freshness",
        severity="blocking",
        passed=ok,
        observed=f"latest ingest_run status = {row['status']}",
        expected="latest ingest_run status in (success, partial)",
    )


@check(name="per_user_fact_freshness", category="freshness", severity="warn")
def per_user_fact_freshness(conn) -> list[CheckResult]:
    rows = conn.execute(
        text(
            """
            SELECT u.username, u.user_id,
                   max(f.ts) AS max_ts,
                   EXTRACT(DAY FROM now() - max(f.ts))::int AS stale_days,
                   count(*) AS fact_rows
            FROM gold.dim_user u
            JOIN gold.fact_streams f ON f.user_id = u.user_id
            GROUP BY u.username, u.user_id
            ORDER BY u.username
            """
        )
    ).mappings().all()
    limit = THRESHOLDS["freshness_user_max_stale_days"]
    out: list[CheckResult] = []
    for r in rows:
        stale = int(r["stale_days"])
        out.append(
            CheckResult(
                name="per_user_fact_freshness",
                category="freshness",
                severity="warn",
                passed=(stale <= limit),
                observed=f"{r['username']}: {stale} days stale ({r['fact_rows']} rows)",
                observed_numeric=float(stale),
                expected=f"per-user max(fact ts) within {limit:g} days",
                user_id=str(r["user_id"]),
                detail={
                    "username": r["username"],
                    "max_ts": r["max_ts"].isoformat() if r["max_ts"] else None,
                    "fact_rows": int(r["fact_rows"]),
                },
            )
        )
    return out


# ===========================================================================
# completeness (3 blocking + 1 warn)
# ===========================================================================
def _rate_result(conn, *, name, sql, threshold_key, expected_tmpl) -> CheckResult:
    row = conn.execute(text(sql)).mappings().one()
    total = int(row["total"])
    named = int(row["named"])
    rate = (named / total) if total else 1.0
    thr = THRESHOLDS[threshold_key]
    return CheckResult(
        name=name,
        category="completeness",
        severity="blocking",
        passed=(rate >= thr),
        observed=f"{rate * 100:.2f}% ({named:,}/{total:,})",
        observed_numeric=round(rate, 6),
        expected=expected_tmpl.format(thr=thr),
        rows_failed=total - named,
    )


@check(name="fact_track_name_rate", category="completeness", severity="blocking")
def fact_track_name_rate(conn) -> CheckResult:
    return _rate_result(
        conn,
        name="fact_track_name_rate",
        sql="""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE track_name IS NOT NULL AND btrim(track_name) <> '') AS named
            FROM gold.fact_streams
        """,
        threshold_key="completeness_track_name_rate",
        expected_tmpl=">= {thr:.0%} of fact rows have a non-blank track_name",
    )


@check(name="fact_artist_name_rate", category="completeness", severity="blocking")
def fact_artist_name_rate(conn) -> CheckResult:
    return _rate_result(
        conn,
        name="fact_artist_name_rate",
        sql="""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE artist_name IS NOT NULL AND btrim(artist_name) <> '') AS named
            FROM gold.fact_streams
        """,
        threshold_key="completeness_artist_name_rate",
        expected_tmpl=">= {thr:.0%} of fact rows have a non-blank artist_name",
    )


@check(name="fact_time_key_rate", category="completeness", severity="blocking")
def fact_time_key_rate(conn) -> CheckResult:
    return _rate_result(
        conn,
        name="fact_time_key_rate",
        sql="""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE time_key IS NOT NULL) AS named
            FROM gold.fact_streams
        """,
        threshold_key="completeness_time_key_rate",
        expected_tmpl=">= {thr:.1%} of fact rows have a time_key (null drops the row from every time MV)",
    )


@check(
    name="enrichment_coverage",
    category="completeness",
    severity="warn",
    description="Reuses enrich.match_rates() -- the repo's definition of "
    "'enriched'. WARN only: audio-features enrichment does not exist in this "
    "repo (Spotify deprecated the endpoint Nov 2024).",
)
def enrichment_coverage(conn) -> CheckResult:
    mr = match_rates(conn)
    a_ok = mr.artist_enriched_rate >= THRESHOLDS["enrichment_artist_rate"]
    t_ok = mr.track_enriched_rate >= THRESHOLDS["enrichment_track_rate"]
    return CheckResult(
        name="enrichment_coverage",
        category="completeness",
        severity="warn",
        passed=(a_ok and t_ok),
        observed=f"artist enriched {mr.artist_enriched_rate * 100:.1f}%, "
        f"track enriched {mr.track_enriched_rate * 100:.1f}%",
        observed_numeric=round(mr.track_enriched_rate, 6),
        expected=f">= {THRESHOLDS['enrichment_artist_rate']:.0%} artist / "
        f">= {THRESHOLDS['enrichment_track_rate']:.0%} track audio_source='enriched'",
        detail={
            "artist_fk_rate": mr.artist_fk_rate,
            "track_fk_rate": mr.track_fk_rate,
            "artist_enriched_rate": mr.artist_enriched_rate,
            "track_enriched_rate": mr.track_enriched_rate,
            "unmatched_artists": mr.unmatched_artists,
            "unmatched_tracks": mr.unmatched_tracks,
        },
    )


# ===========================================================================
# anomaly (2, both warn)
# ===========================================================================
def _mad_anomalies(series: list[tuple[Any, float]], *, window: int, k: float) -> list[dict]:
    """Rolling-window MAD outliers. `series` is [(label, value), ...] in order.

    Flags value i (i >= window) when |x - median(w)| > k * 1.4826 * MAD(w),
    where w is the `window` values ending at i-1. MAD == 0 (a flat run) -> skip
    that window, else every deviation is infinite.
    """
    out: list[dict] = []
    vals = [v for _, v in series]
    for i in range(window, len(vals)):
        w = vals[i - window : i]
        med = statistics.median(w)
        mad = statistics.median([abs(x - med) for x in w])
        if mad == 0:
            continue
        if abs(vals[i] - med) > k * 1.4826 * mad:
            out.append(
                {
                    "label": str(series[i][0]),
                    "value": vals[i],
                    "median": med,
                    "mad": mad,
                }
            )
    return out


@check(name="daily_play_count_anomaly", category="anomaly", severity="warn")
def daily_play_count_anomaly(conn) -> CheckResult:
    rows = conn.execute(
        text(
            """
            SELECT f.user_id, t.date AS day, count(*) AS plays
            FROM gold.fact_streams f
            JOIN gold.dim_time t ON t.time_key = f.time_key
            WHERE t.date >= (CURRENT_DATE - INTERVAL '400 days')
            GROUP BY f.user_id, t.date
            ORDER BY f.user_id, t.date
            """
        )
    ).mappings().all()

    by_user: dict[str, list[tuple[Any, float]]] = {}
    for r in rows:
        by_user.setdefault(str(r["user_id"]), []).append((r["day"], float(r["plays"])))

    min_days = int(THRESHOLDS["anomaly_min_history_days"])
    k = THRESHOLDS["anomaly_mad_k"]
    flagged: list[dict] = []
    judged_users = 0
    for uid, series in by_user.items():
        if len(series) < min_days:
            continue
        judged_users += 1
        for a in _mad_anomalies(series, window=min_days, k=k):
            flagged.append({"user_id": uid, **a})

    if judged_users == 0:
        return CheckResult(
            name="daily_play_count_anomaly",
            category="anomaly",
            severity="warn",
            passed=True,
            skipped=True,
            observed="no user has >= 30 days of history in the last 400 days",
            expected=f"0 daily play counts beyond {k:g}-sigma of the 30-day rolling median",
        )
    n = len(flagged)
    return CheckResult(
        name="daily_play_count_anomaly",
        category="anomaly",
        severity="warn",
        passed=(n == 0),
        observed=f"{n} anomalous user-day(s) across {judged_users} user(s)",
        observed_numeric=float(n),
        expected=f"0 daily play counts beyond {k:g}-sigma of the 30-day rolling median",
        rows_failed=n,
        detail={"anomalous_days": flagged[:20]} if flagged else None,
    )


@check(name="run_over_run_row_delta", category="anomaly", severity="warn")
def run_over_run_row_delta(conn) -> CheckResult:
    rows = conn.execute(
        text(
            """
            SELECT run_id, started_at, rows_fact
            FROM bronze.ingest_run
            WHERE status IN ('success', 'partial') AND rows_fact > 0
            ORDER BY started_at DESC
            LIMIT 30
            """
        )
    ).mappings().all()
    min_runs = int(THRESHOLDS["anomaly_min_runs"])
    if len(rows) < min_runs:
        return CheckResult(
            name="run_over_run_row_delta",
            category="anomaly",
            severity="warn",
            passed=True,
            skipped=True,
            observed=f"{len(rows)} successful run(s) of history",
            expected=f">= {min_runs} runs before a z-score is meaningful",
        )
    # rows are newest-first; reverse to chronological
    fact = [int(r["rows_fact"]) for r in reversed(rows)]
    deltas = [fact[i] - fact[i - 1] for i in range(1, len(fact))]
    latest = deltas[-1]
    prior = deltas[:-1]
    mean = statistics.fmean(prior)
    sd = statistics.pstdev(prior)
    z = 0.0 if sd == 0 else (latest - mean) / sd
    return CheckResult(
        name="run_over_run_row_delta",
        category="anomaly",
        severity="warn",
        passed=(abs(z) <= 3.0),
        observed=f"latest run-over-run rows_fact delta {latest:+,}  (z = {z:+.2f})",
        observed_numeric=round(z, 4),
        expected="|z| <= 3 vs the prior run-over-run deltas",
        detail={"latest_delta": latest, "mean_delta": round(mean, 1), "stdev": round(sd, 1)},
    )
