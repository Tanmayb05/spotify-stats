"""Silver build: bronze.raw_streams -> silver.streams, collapsing byte-identical
export duplicates on (user_id, row_fingerprint).

Full rebuild every run (TRUNCATE + INSERT). Silver's idempotency comes from
being a deterministic function of bronze, not from a unique constraint --
`bronze` must retain dupes verbatim, and a constraint on silver would make the
rebuild *fail* on a legitimate dupe instead of *counting* it.

Tie-break (roadmap requires this documented): keep the lowest `_ingest_id` --
the first-landed occurrence. Deterministic and stable because `_ingest_id` is a
BIGSERIAL assigned in file order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text

# The dedup window. PARTITION BY (user_id, row_fingerprint) ORDER BY _ingest_id,
# keep rn = 1. row_fingerprint is NULL only for pre-Phase-12 rows (all deleted
# in migration 011); COALESCE guards a mixed DB during migration.
DEDUP_SELECT_SQL = """
    SELECT d.* FROM (
        SELECT b.*,
               ROW_NUMBER() OVER (
                   PARTITION BY b.user_id, b.row_fingerprint
                   ORDER BY b._ingest_id
               ) AS _rn
        FROM bronze.raw_streams b
        WHERE b.ts IS NOT NULL
    ) d
    WHERE d._rn = 1
"""


@dataclass
class DedupStats:
    rows_in: int = 0          # bronze rows with ts IS NOT NULL
    rows_out: int = 0         # silver rows after dedup
    dups_dropped: int = 0     # rows_in - rows_out
    per_user: list[dict] = field(default_factory=list)


def build_silver(conn, *, full_rebuild: bool = True) -> DedupStats:
    """Rebuild silver.streams from bronze. `conn` is inside the caller's
    transaction (the whole silver->gold rebuild is one engine.begin())."""
    if full_rebuild:
        conn.execute(text("TRUNCATE TABLE silver.streams RESTART IDENTITY CASCADE"))

    rows_in = conn.execute(
        text("SELECT count(*) FROM bronze.raw_streams WHERE ts IS NOT NULL")
    ).scalar_one()

    result = conn.execute(text(f"""
        INSERT INTO silver.streams (
            _ingest_id, user_id, ts, artist_key, track_key,
            track_name, artist_name, album_name,
            ms_played, platform, conn_country, reason_start, reason_end,
            shuffle, skipped, offline, incognito_mode, is_music, row_fingerprint
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
             AND b.audiobook_title IS NULL),
            b.row_fingerprint
        FROM ({DEDUP_SELECT_SQL}) b
    """))
    rows_out = result.rowcount

    per_user = conn.execute(text("""
        SELECT
            u.username,
            (SELECT count(*) FROM bronze.raw_streams br
              WHERE br.user_id = u.id AND br.ts IS NOT NULL) AS bronze_rows,
            (SELECT count(*) FROM silver.streams s WHERE s.user_id = u.id) AS silver_rows
        FROM users u ORDER BY u.username
    """)).mappings().all()

    return DedupStats(
        rows_in=rows_in,
        rows_out=rows_out,
        dups_dropped=rows_in - rows_out,
        per_user=[
            {
                "username": r["username"],
                "bronze": r["bronze_rows"],
                "silver": r["silver_rows"],
                "dups_dropped": r["bronze_rows"] - r["silver_rows"],
            }
            for r in per_user
        ],
    )


def dedup_report(conn) -> list[dict]:
    """Per-user bronze/silver/fact counts -- the V5 measurement, callable
    standalone before and after a run."""
    return [
        dict(r)
        for r in conn.execute(text("""
            SELECT u.username,
                   (SELECT count(*) FROM bronze.raw_streams b WHERE b.user_id=u.id) AS bronze,
                   (SELECT count(*) FROM silver.streams   s WHERE s.user_id=u.id) AS silver,
                   (SELECT count(*) FROM gold.fact_streams f WHERE f.user_id=u.id) AS fact
            FROM users u ORDER BY u.username
        """)).mappings().all()
    ]
