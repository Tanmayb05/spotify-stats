"""Bronze landing: parse an export file and append its rows to bronze.raw_streams.

Incremental & idempotent (Phase 12 idempotency model):

  * FILE level  -- (user_id, file_hash) UNIQUE on bronze.ingest_state. A file
    whose hash is already recorded is skipped outright, no parse.
  * ROW level   -- on a superset re-export of the same user, only rows with
    ts >= user_watermark AND whose row_fingerprint is not already in bronze for
    that user are appended. `>=` + the fingerprint anti-join (not strict `>`) so
    a play sharing the watermark second is not lost and a half-failed run
    resumes without duplication.

bronze stays append-only (never UPDATE/DELETE a landed row). A file's FIRST
landing appends every row it contains, intra-file byte-identical dupes included
-- collapsing those is dedup.py's job in silver.

ip_addr is popped from `_raw` before it is written (V8 -- the single most
important line here; the replaced load_json_to_supabase.py kept it).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from app.ingest.discover import PRIMARY_SLUG, DiscoveredFile
from app.ingest.normalize import row_fingerprint, to_utc
from app.ingest.salvage import salvage_json_array
from app.ingest.validate import ValidationOutcome, validate_rows, write_quarantine

BATCH = 5_000

# Columns copied verbatim from the export row into bronze.raw_streams (matches
# migration 008's column list; NO ip_addr).
_VERBATIM_COLS = (
    "platform", "ms_played", "conn_country",
    "master_metadata_track_name", "master_metadata_album_artist_name",
    "master_metadata_album_album_name", "spotify_track_uri",
    "episode_name", "episode_show_name", "spotify_episode_uri",
    "audiobook_title", "audiobook_uri", "audiobook_chapter_uri", "audiobook_chapter_title",
    "reason_start", "reason_end", "shuffle", "skipped", "offline",
    "offline_timestamp", "incognito_mode",
)


@dataclass
class LandingResult:
    slug: str
    user_id: UUID
    rel_path: str
    file_hash: str
    skipped_reason: str | None            # 'file_hash_seen' | None
    rows_in_file: int
    rows_landed: int
    rows_quarantined: int
    rows_below_watermark: int
    warn_counts: dict
    min_ts: datetime | None
    max_ts: datetime | None


def get_or_create_user(conn, slug: str, display_name: str, is_primary: bool) -> UUID:
    """Resolve a slug to a users.id, creating the row if absent.

    The primary slug maps to the existing is_primary=TRUE row (username may be
    anything historically -- 'tanmay' in this repo). A partial-unique index
    forbids a second is_primary row, so never INSERT is_primary=TRUE here.
    """
    if is_primary or slug == PRIMARY_SLUG:
        row = conn.execute(
            text("SELECT id FROM users WHERE is_primary = TRUE LIMIT 1")
        ).first()
        if row:
            return row[0]
        # No primary yet -- create one under the canonical slug.
        return conn.execute(
            text(
                "INSERT INTO users (username, display_name, is_primary) "
                "VALUES (:u, :d, TRUE) RETURNING id"
            ),
            {"u": PRIMARY_SLUG, "d": display_name},
        ).scalar_one()

    row = conn.execute(
        text("SELECT id FROM users WHERE username = :u"), {"u": slug}
    ).first()
    if row:
        return row[0]
    return conn.execute(
        text(
            "INSERT INTO users (username, display_name, is_primary) "
            "VALUES (:u, :d, FALSE) RETURNING id"
        ),
        {"u": slug, "d": display_name},
    ).scalar_one()


def read_export(path: Path) -> list:
    """json.load, falling back to salvage for a truncated write. Non-dict array
    elements are wrapped so validate.py quarantines them as row_not_a_dict."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = salvage_json_array(path, path.stem) or _salvage_bare_array(path)
    if not isinstance(data, list):
        return []
    out = []
    for el in data:
        if isinstance(el, dict):
            out.append(el)
        else:
            out.append({"__not_a_dict__": repr(el)[:500]})
    return out


def _salvage_bare_array(path: Path) -> list:
    """Spotify exports are a bare top-level JSON array; salvage_json_array wants
    an object with a keyed array. Decode element-by-element from the first '['."""
    txt = path.read_text(encoding="utf-8")
    try:
        start = txt.index("[") + 1
    except ValueError:
        return []
    dec = json.JSONDecoder()
    items, i, n = [], start, len(txt)
    while i < n:
        while i < n and txt[i] in " \t\r\n,":
            i += 1
        if i >= n or txt[i] == "]":
            break
        try:
            obj, end = dec.raw_decode(txt, i)
        except json.JSONDecodeError:
            break
        items.append(obj)
        i = end
    return items


def user_watermark(conn, user_id: UUID) -> datetime | None:
    """MAX(max_ts) over this user's landed files -- the row-incremental floor."""
    return conn.execute(
        text("SELECT MAX(max_ts) FROM bronze.ingest_state WHERE user_id = :u"),
        {"u": str(user_id)},
    ).scalar()


def _existing_fingerprints(conn, user_id: UUID, fps: list[str]) -> set[str]:
    if not fps:
        return set()
    rows = conn.execute(
        text(
            "SELECT row_fingerprint FROM bronze.raw_streams "
            "WHERE user_id = :u AND row_fingerprint = ANY(:fps)"
        ),
        {"u": str(user_id), "fps": fps},
    ).scalars().all()
    return set(rows)


def land_file(
    conn,
    df: DiscoveredFile,
    user_id: UUID,
    run_id,
    watermark: datetime | None,
    *,
    force: bool = False,
) -> LandingResult:
    """Land one discovered file. `conn` is inside the caller's transaction."""
    # --- Tier 1: file-level skip -------------------------------------------
    if not force:
        seen = conn.execute(
            text(
                "SELECT 1 FROM bronze.ingest_state "
                "WHERE user_id = :u AND file_hash = :h"
            ),
            {"u": str(user_id), "h": df.file_hash},
        ).first()
        if seen:
            return LandingResult(
                slug=df.slug, user_id=user_id, rel_path=df.rel_path,
                file_hash=df.file_hash, skipped_reason="file_hash_seen",
                rows_in_file=0, rows_landed=0, rows_quarantined=0,
                rows_below_watermark=0, warn_counts={}, min_ts=None, max_ts=None,
            )

    rows = read_export(df.path)
    rows_in_file = len(rows)

    outcome: ValidationOutcome = validate_rows(
        rows, source_file=df.rel_path, user_id=user_id, run_id=run_id
    )
    rows_quarantined = write_quarantine(conn, outcome.quarantined, run_id=run_id)

    # --- Tier 2: row-level incremental on the valid rows ------------------
    to_land: list[dict] = []
    below_wm = 0
    for r in outcome.valid:
        ts = to_utc(r.get("ts"))
        if watermark is not None and ts is not None and ts < watermark:
            below_wm += 1
            continue
        rr = dict(r)
        rr["user_id"] = str(user_id)
        rr["_fp"] = row_fingerprint(rr)
        rr["_ts"] = ts
        to_land.append(rr)

    if watermark is not None and to_land:
        existing = _existing_fingerprints(conn, user_id, [r["_fp"] for r in to_land])
        to_land = [r for r in to_land if r["_fp"] not in existing]

    min_ts = min((r["_ts"] for r in to_land if r["_ts"]), default=None)
    max_ts = max((r["_ts"] for r in to_land if r["_ts"]), default=None)

    rows_landed = 0
    for start in range(0, len(to_land), BATCH):
        rows_landed += _insert_batch(conn, to_land[start:start + BATCH], df.rel_path, run_id)

    # --- ingest_state upsert: converge on re-run after a mid-file crash ---
    conn.execute(
        text(
            """
            INSERT INTO bronze.ingest_state
                (user_id, source_file, file_hash, max_ts, min_ts,
                 rows_in_file, rows_landed, run_id)
            VALUES
                (:u, :sf, :h, :max_ts, :min_ts, :rif, :rl, :run_id)
            ON CONFLICT (user_id, file_hash) DO UPDATE SET
                source_file  = EXCLUDED.source_file,
                max_ts       = GREATEST(bronze.ingest_state.max_ts, EXCLUDED.max_ts),
                min_ts       = LEAST(bronze.ingest_state.min_ts, EXCLUDED.min_ts),
                rows_in_file = EXCLUDED.rows_in_file,
                rows_landed  = bronze.ingest_state.rows_landed + EXCLUDED.rows_landed,
                run_id       = EXCLUDED.run_id,
                ingested_at  = now()
            """
        ),
        {
            "u": str(user_id), "sf": df.rel_path, "h": df.file_hash,
            "max_ts": max_ts, "min_ts": min_ts,
            "rif": rows_in_file, "rl": rows_landed,
            "run_id": str(run_id) if run_id else None,
        },
    )

    return LandingResult(
        slug=df.slug, user_id=user_id, rel_path=df.rel_path,
        file_hash=df.file_hash, skipped_reason=None,
        rows_in_file=rows_in_file, rows_landed=rows_landed,
        rows_quarantined=rows_quarantined, rows_below_watermark=below_wm,
        warn_counts=dict(outcome.warn_counts), min_ts=min_ts, max_ts=max_ts,
    )


def _insert_batch(conn, batch: list[dict], source_file: str, run_id) -> int:
    if not batch:
        return 0
    params = []
    for r in batch:
        raw = {k: v for k, v in r.items() if k not in ("_fp", "_ts", "user_id", "ip_addr")}
        params.append(
            {
                "sf": source_file,
                "raw": json.dumps(raw, default=str),
                "u": r["user_id"],
                "fp": r["_fp"],
                "ts": r["_ts"],
                **{c: r.get(c) for c in _VERBATIM_COLS},
            }
        )
    cols_sql = ", ".join(_VERBATIM_COLS)
    binds_sql = ", ".join(f":{c}" for c in _VERBATIM_COLS)
    conn.execute(
        text(
            f"""
            INSERT INTO bronze.raw_streams
                (_source_file, _raw, user_id, row_fingerprint, ts, {cols_sql})
            VALUES
                (:sf, CAST(:raw AS jsonb), :u, :fp, :ts, {binds_sql})
            """
        ),
        params,
    )
    return len(batch)
