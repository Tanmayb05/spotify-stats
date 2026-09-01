#!/usr/bin/env python3
"""Build the star schema: public.streaming_history -> bronze -> silver -> gold.

    python scripts/build_star_schema.py

Re-runnable: TRUNCATE ... RESTART IDENTITY on gold + silver before rebuilding
(bronze stays append-only and is only backfilled once by migration 008 --
Phase 12's Dagster pipeline is what lands new bronze rows going forward).

One transaction end-to-end so a failure midway leaves the previous star
schema intact rather than a half-built one.

Stages, each logged (rows in/out, match-rates, unmatched counts):
  1. silver.streams   <- bronze.raw_streams (typed, normalized keys)
  2. gold.dim_user     <- users (1:1, D3: no re-keying)
  3. gold.dim_time      <- distinct (date, hour) observed in silver.streams
  4. gold.dim_artist    <- upsert any artist_key from silver not already
                            present (load_enrichment_to_db.py already seeded
                            the enriched ones; this fills the rest with
                            NULL-enrichment stub rows so every play has an FK
                            target -- Decision: unmatched rows still produce a
                            fact row, never dropped)
  5. gold.dim_track     <- same idea for track_key
  6. gold.dim_album     <- same idea for (album_name, artist_key)
  7. gold.fact_streams  <- one row per silver.streams row (D6: no dedup, 1:1
                            with source). Verified against streaming_history
                            count per user at the end (V1).

Unmatched artist/track/album rows get NULL FK columns in fact_streams --
never silently dropped, which is what would move any downstream aggregate.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402



def log(msg: str) -> None:
    print(msg, flush=True)


def stage_silver(conn) -> int:
    log("\n[1/7] silver.streams <- bronze.raw_streams")
    conn.execute(text("TRUNCATE TABLE silver.streams RESTART IDENTITY"))

    # Normalization done in SQL (lower/trim) to keep this a single set-based
    # statement rather than a row-by-row Python loop over 71k+ rows. The
    # normalization rule (lower(trim(...))) is identical to
    # app.ingest.normalize.normalize_artist_key/normalize_track_key -- kept in
    # sync by test_normalize.py asserting the same rule in Python.
    result = conn.execute(text("""
        INSERT INTO silver.streams (
            _ingest_id, user_id, ts, artist_key, track_key,
            track_name, artist_name, album_name,
            ms_played, platform, conn_country, reason_start, reason_end,
            shuffle, skipped, offline, incognito_mode, is_music
        )
        SELECT
            b._ingest_id,
            b.user_id,
            b.ts,
            NULLIF(lower(trim(b.master_metadata_album_artist_name)), ''),
            COALESCE(
                b.spotify_track_uri,
                CASE
                    WHEN b.master_metadata_track_name IS NOT NULL
                     AND b.master_metadata_album_artist_name IS NOT NULL
                    THEN 'hash:' || md5(
                        lower(trim(b.master_metadata_track_name)) || '|||' ||
                        lower(trim(b.master_metadata_album_artist_name))
                    )
                    ELSE NULL
                END
            ),
            b.master_metadata_track_name,
            b.master_metadata_album_artist_name,
            b.master_metadata_album_album_name,
            COALESCE(b.ms_played, 0),
            b.platform,
            b.conn_country,
            b.reason_start,
            b.reason_end,
            COALESCE(b.shuffle, FALSE),
            COALESCE(b.skipped, FALSE),
            COALESCE(b.offline, FALSE),
            COALESCE(b.incognito_mode, FALSE),
            (b.spotify_track_uri IS NOT NULL
             AND b.episode_name IS NULL
             AND b.audiobook_title IS NULL)
        FROM bronze.raw_streams b
        WHERE b.ts IS NOT NULL
    """))
    n = result.rowcount
    log(f"  inserted {n:,} silver.streams rows")
    return n


def stage_dim_user(conn) -> int:
    log("\n[2/7] gold.dim_user <- users (D3: reuse UUIDs verbatim, no re-keying)")
    conn.execute(text("""
        INSERT INTO gold.dim_user (user_id, username, display_name, is_primary)
        SELECT id, username, display_name, is_primary FROM users
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            display_name = EXCLUDED.display_name,
            is_primary = EXCLUDED.is_primary
    """))
    n = conn.execute(text("SELECT count(*) FROM gold.dim_user")).scalar_one()
    log(f"  {n} dim_user rows")
    return n


def stage_dim_time(conn) -> int:
    log("\n[3/7] gold.dim_time <- distinct (date, hour) observed in silver.streams")
    # CASCADE: fact_streams.time_key FKs here. fact_streams is already
    # truncated in main() before this stage runs, but Postgres still requires
    # CASCADE (or a combined multi-table TRUNCATE) on a plain TRUNCATE of a
    # table with an inbound FK, even when the referencing table is empty.
    conn.execute(text("TRUNCATE TABLE gold.dim_time CASCADE"))
    result = conn.execute(text("""
        INSERT INTO gold.dim_time (time_key, date, hour, year, month, day, iso_dow, is_weekend, week_start)
        SELECT
            (EXTRACT(YEAR FROM d)::INT * 10000 + EXTRACT(MONTH FROM d)::INT * 100 + EXTRACT(DAY FROM d)::INT) * 100 + hr,
            d,
            hr,
            EXTRACT(YEAR FROM d)::SMALLINT,
            EXTRACT(MONTH FROM d)::SMALLINT,
            EXTRACT(DAY FROM d)::SMALLINT,
            EXTRACT(ISODOW FROM d)::SMALLINT,
            (EXTRACT(ISODOW FROM d) >= 6),
            date_trunc('week', d)::date
        FROM (
            SELECT DISTINCT ts::date AS d, EXTRACT(HOUR FROM ts)::INT AS hr
            FROM silver.streams
        ) distinct_dh
    """))
    n = result.rowcount
    log(f"  inserted {n:,} dim_time rows")
    return n


def stage_dim_artist(conn) -> Dict[str, int]:
    log("\n[4/7] gold.dim_artist <- fill any artist_key from silver not already enriched")
    before = conn.execute(text("SELECT count(*) FROM gold.dim_artist")).scalar_one()
    conn.execute(text("""
        INSERT INTO gold.dim_artist (artist_key, artist_name, audio_source)
        SELECT DISTINCT ON (s.artist_key)
            s.artist_key, s.artist_name, 'none'
        FROM silver.streams s
        WHERE s.artist_key IS NOT NULL
        ON CONFLICT (artist_key) DO NOTHING
    """))
    after = conn.execute(text("SELECT count(*) FROM gold.dim_artist")).scalar_one()
    log(f"  {before} pre-existing -> {after} total ({after - before} stub rows added)")
    return {"before": before, "after": after}


def stage_dim_track(conn) -> Dict[str, int]:
    log("\n[5/7] gold.dim_track <- fill any track_key from silver not already enriched")
    before = conn.execute(text("SELECT count(*) FROM gold.dim_track")).scalar_one()
    conn.execute(text("""
        INSERT INTO gold.dim_track (track_key, spotify_track_uri, track_name, artist_key, artist_name, audio_source)
        SELECT DISTINCT ON (s.track_key)
            s.track_key,
            CASE WHEN s.track_key NOT LIKE 'hash:%' THEN s.track_key ELSE NULL END,
            s.track_name,
            s.artist_key,
            s.artist_name,
            'none'
        FROM silver.streams s
        WHERE s.track_key IS NOT NULL
        ON CONFLICT (track_key) DO NOTHING
    """))
    after = conn.execute(text("SELECT count(*) FROM gold.dim_track")).scalar_one()
    log(f"  {before} pre-existing -> {after} total ({after - before} stub rows added)")
    return {"before": before, "after": after}


def stage_dim_album(conn) -> int:
    log("\n[6/7] gold.dim_album <- distinct (album_name, artist_key) from silver")
    conn.execute(text("TRUNCATE TABLE gold.dim_album CASCADE"))
    conn.execute(text("""
        INSERT INTO gold.dim_album (album_key, album_name, artist_key)
        SELECT DISTINCT ON (album_key) album_key, album_name, artist_key
        FROM (
            SELECT
                lower(trim(s.album_name)) || '|||' || COALESCE(s.artist_key, '') AS album_key,
                s.album_name,
                s.artist_key
            FROM silver.streams s
            WHERE s.album_name IS NOT NULL
        ) x
        WHERE album_key IS NOT NULL
        ON CONFLICT (album_key) DO NOTHING
    """))
    n = conn.execute(text("SELECT count(*) FROM gold.dim_album")).scalar_one()
    log(f"  {n:,} dim_album rows")
    return n


def stage_fact_streams(conn) -> int:
    log("\n[7/7] gold.fact_streams <- silver.streams (1:1, D6: no dedup)")
    # Already truncated in main() before stage_dim_album's CASCADE truncate.
    result = conn.execute(text("""
        INSERT INTO gold.fact_streams (
            _ingest_id, user_id, time_key, artist_key, track_key, album_key,
            artist_name, track_name, album_name,
            ts, ms_played, skipped, shuffle, offline, incognito_mode,
            reason_start, reason_end, platform, conn_country, is_music
        )
        SELECT
            s._ingest_id,
            s.user_id,
            (EXTRACT(YEAR FROM s.ts)::INT * 10000 + EXTRACT(MONTH FROM s.ts)::INT * 100 + EXTRACT(DAY FROM s.ts)::INT) * 100
                + EXTRACT(HOUR FROM s.ts)::INT,
            s.artist_key,
            s.track_key,
            CASE WHEN s.album_name IS NOT NULL
                 THEN lower(trim(s.album_name)) || '|||' || COALESCE(s.artist_key, '')
                 ELSE NULL END,
            s.artist_name,
            s.track_name,
            s.album_name,
            s.ts,
            s.ms_played,
            s.skipped,
            s.shuffle,
            s.offline,
            s.incognito_mode,
            s.reason_start,
            s.reason_end,
            s.platform,
            s.conn_country,
            s.is_music
        FROM silver.streams s
    """))
    n = result.rowcount
    log(f"  inserted {n:,} fact_streams rows")
    return n


def report_match_rates(conn) -> None:
    log("\n--- Match rates ---")
    row = conn.execute(text("""
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE artist_key IS NOT NULL) AS with_artist,
            count(*) FILTER (WHERE track_key IS NOT NULL) AS with_track
        FROM gold.fact_streams
    """)).mappings().one()
    total = row["total"] or 1
    log(f"  artist_key present: {row['with_artist']:,}/{row['total']:,} "
        f"({100.0 * row['with_artist'] / total:.1f}%)")
    log(f"  track_key  present: {row['with_track']:,}/{row['total']:,} "
        f"({100.0 * row['with_track'] / total:.1f}%)")

    enriched = conn.execute(text(
        "SELECT count(*) FROM gold.dim_track WHERE audio_source = 'enriched'"
    )).scalar_one()
    log(f"  dim_track rows with audio_source='enriched': {enriched:,}")


def verify_v1(conn) -> bool:
    """V1: fact_streams row count == streaming_history row count, exactly, per user."""
    log("\n--- V1: fact completeness (per user) ---")
    rows = conn.execute(text("""
        SELECT
            u.username,
            (SELECT count(*) FROM streaming_history sh WHERE sh.user_id = u.id) AS source_count,
            (SELECT count(*) FROM gold.fact_streams fs WHERE fs.user_id = u.id) AS fact_count
        FROM users u
        ORDER BY u.username
    """)).mappings().all()
    ok = True
    for r in rows:
        match = "OK" if r["source_count"] == r["fact_count"] else "MISMATCH"
        if r["source_count"] != r["fact_count"]:
            ok = False
        log(f"  {r['username']:<20} source={r['source_count']:>8,}  fact={r['fact_count']:>8,}  {match}")
    log(f"\nV1 {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    from app.db.session import make_engine

    engine = make_engine()

    with engine.begin() as conn:
        has_bronze = conn.execute(text("SELECT to_regclass('bronze.raw_streams')")).scalar()
        if not has_bronze:
            print("bronze.raw_streams does not exist. Run: python db/migrate.py")
            return 1

        # fact_streams is truncated first (before dim_album's TRUNCATE ...
        # CASCADE in stage_dim_album) so a re-run never cascade-deletes rows
        # from the *previous* build via the album_key FK.
        conn.execute(text("TRUNCATE TABLE gold.fact_streams RESTART IDENTITY"))

        stage_silver(conn)
        stage_dim_user(conn)
        stage_dim_time(conn)
        stage_dim_artist(conn)
        stage_dim_track(conn)
        stage_dim_album(conn)
        stage_fact_streams(conn)
        report_match_rates(conn)
        v1_ok = verify_v1(conn)

    # monthly_stats/top_artists/top_tracks (migration 010) read gold.fact_streams.
    # If they were created/refreshed before this build populated fact_streams
    # (e.g. right after migrate.py, before the first build_star_schema.py run),
    # they are stale or empty. Refresh them here unconditionally so a build is
    # never followed by a manual "oh, also refresh the views" step -- this is
    # what api/stats/top-artists, top-tracks, and time/monthly read from.
    log("\nRefreshing monthly_stats / top_artists / top_tracks ...")
    with engine.begin() as conn:
        conn.execute(text("SELECT refresh_all_views()"))
    log("  done")

    print("\nBuild complete." if v1_ok else "\nBuild complete WITH V1 MISMATCH -- investigate before proceeding.")
    return 0 if v1_ok else 1


if __name__ == "__main__":
    sys.exit(main())
