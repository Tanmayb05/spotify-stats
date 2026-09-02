"""Shared helpers for the Phase 13.5 EDA notebooks.

Every notebook imports this module so that no query, palette, or chart-styling
logic is duplicated across the eight of them. Notebooks stay thin: parameters,
a call into here, a chart, and a `## Decision inputs` cell.

Run prerequisites
-----------------
The notebooks read the local Postgres warehouse, not Supabase::

    docker compose up          # publishes Postgres on host port 5433

and the environment needs both of::

    DB_BACKEND=local
    DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/spotify

set either in `spotify-insights.env` at the repo root or exported. See
`get_engine()` below -- it raises with this text if they are missing.

Two conventions this module pins (both are real ambiguities in the warehouse;
notebooks must not each pick their own)
--------------------------------------------------------------------------
1. **Time comes from `gold.dim_time`, never from `EXTRACT(... FROM ts)`.**
   `dim_time` is built once at ingest, whereas `EXTRACT` depends on the session
   `TimeZone` and will silently disagree if that ever changes.
   `dim_time.iso_dow` is 1=Mon..7=Sun (`is_weekend = iso_dow >= 6`). Note
   `data_loader`'s Python heuristics use `datetime.weekday()`, which is
   0=Mon..6=Sun -- the *same* weekend set, different numbering. Do not copy one
   predicate into the other's numbering.

   **`dim_time.hour` is UTC.** Verified: the warehouse runs `TimeZone=Etc/UTC`,
   Spotify exports `ts` in UTC, and `dim_time.hour == EXTRACT(hour FROM ts)`
   exactly. The all-user histogram peaks at 03:00-05:00 UTC, which is not a
   listening pattern -- it is ~08:30-10:30 in IST (UTC+5:30), a morning peak.
   Any notebook deriving hour-of-day buckets, a `night_share` cutoff, or a
   `context_label` set MUST convert to a listener-local hour first
   (`local_hour()` below); labelling UTC hours would hand Phase 14 buckets that
   are shifted by the offset. The warehouse stores no per-user timezone, so the
   offset is an explicit, documented assumption -- see `LOCAL_UTC_OFFSET_HOURS`.

2. **Artist/track identity: `*_name` counts, `*_key` groups.**
   `gold.fact_streams.artist_name` / `track_name` are case-sensitive degenerate
   dimensions kept so aggregates reproduce the pre-star-schema
   `COUNT(DISTINCT master_metadata_*_name)` semantics -- "KALEO" and "Kaleo"
   count as two. Grouping by `artist_key` (= `lower(trim(name))`) silently
   merges them. Every metric in a notebook must say which it used; the loaders
   below return both columns so the choice is explicit at the call site.

PII rule
--------
`gold.dim_user.username` holds real first names (migration 007 masked only
`display_name`, and the masked values look real, which is worse for a reader who
cannot tell they are synthetic). The loaders here **never project either
column**. Users appear only as `user_01`..`user_10`, assigned by
`alias_users()`. Enforcing this at the query layer is deliberate -- it cannot be
forgotten in one notebook the way a per-notebook drop could be.

Notebook outputs are stripped before commit (`nbstripout`); see the README.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# `app.*` lives one level up from notebooks/. Notebooks are launched from a
# variety of working directories (jupyter from repo root, nbconvert from
# apps/api), so make the import work regardless.
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))


# ---------------------------------------------------------------------------
# palette / style
# ---------------------------------------------------------------------------
# The project palette (see CLAUDE.md). Ordered dark -> light.
PALETTE: list[str] = ["#1c0b19", "#140d4f", "#4ea699", "#2dd881", "#6fedb7"]

# The three that read well as data marks on a white notebook background;
# #1c0b19 and #140d4f are near-black and are reserved for text/axes.
SERIES_COLORS: list[str] = ["#2dd881", "#4ea699", "#6fedb7"]

INK = "#1c0b19"
ACCENT = "#140d4f"


def use_style() -> None:
    """Apply the project chart style. Call once, in each notebook's setup cell.

    Kept deliberately small: rcParams only, no seaborn theme, so a notebook can
    still reach for seaborn locally without fighting a global override.
    """
    import matplotlib as mpl
    from cycler import cycler

    mpl.rcParams.update(
        {
            "figure.figsize": (10, 5),
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "axes.prop_cycle": cycler(color=SERIES_COLORS),
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.grid": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.alpha": 0.25,
            "grid.linestyle": "-",
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "font.size": 10,
            "legend.frameon": False,
        }
    )


# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------
_DSN_HINT = "postgresql+psycopg://postgres:postgres@localhost:5433/spotify"

_SETUP_HELP = f"""\
The EDA notebooks need the local Postgres warehouse.

  1. Start it:   docker compose up
  2. Point at it, in spotify-insights.env at the repo root (or export):

       DB_BACKEND=local
       DATABASE_URL={_DSN_HINT}

Note the port: Compose publishes Postgres on 5433, not the usual 5432, to avoid
clashing with a locally-installed Postgres (docker-compose.yml). A DSN pointing
at 5432 will either fail to connect or -- worse -- silently connect to an
unrelated database."""


def get_engine() -> Engine:
    """The process-wide SQLAlchemy engine, from `app.db.session`.

    Thin wrapper: the app already owns engine construction (psycopg3 pinning,
    `pool_pre_ping`), and a notebook must never carry its own DSN. The only
    thing added here is a better error -- the underlying message names port
    5432, which is wrong for this Compose stack.
    """
    from app.db.session import get_engine as _app_get_engine

    try:
        return _app_get_engine()
    except ValueError as exc:  # DATABASE_URL unset
        raise RuntimeError(f"{exc}\n\n{_SETUP_HELP}") from exc


def db_available() -> bool:
    """True if the warehouse is reachable. Never raises.

    Used by the notebooks' setup cell so a missing database degrades to a
    printed message rather than a traceback (same spirit as `enough()`).
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# guards -- thin-data degradation
# ---------------------------------------------------------------------------
# The committed CI fixture is 40 rows, far below anything these notebooks
# analyse. Every analysis cell is wrapped in `enough(...)` so a fixture run is a
# clean sequence of "insufficient data" messages and exits 0, while a real
# 71k-row run renders fully. This is what makes the set CI-able in Phase 16.
MIN_ROWS_OVERVIEW = 100  # basic counts / coverage
MIN_ROWS_TEMPORAL = 500  # hour x dow needs cells to be non-empty
MIN_ROWS_ARTIST = 500  # per-artist gaps need repeat plays
MIN_ROWS_SESSION = 1000  # sessionizing then clustering needs >= 10 sessions
MIN_ROWS_CF = 1000  # user x track sparsity


def enough(obj, min_rows: int, what: str = "rows") -> bool:
    """Guard an analysis cell. Prints and returns False when data is too thin.

    Accepts a DataFrame, a sized collection, or an int::

        if not enough(df, MIN_ROWS_TEMPORAL, "plays"):
            pass          # notebook continues to the next cell
        else:
            ...
    """
    if obj is None:
        have = 0
    elif isinstance(obj, int):
        have = obj
    elif hasattr(obj, "__len__"):
        have = len(obj)
    else:  # pragma: no cover - defensive
        have = 0

    if have < min_rows:
        print(
            f"insufficient data -- skipped (need {min_rows:,} {what}, have {have:,})"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# user aliasing
# ---------------------------------------------------------------------------
def alias_users(engine: Optional[Engine] = None) -> dict[str, str]:
    """Map `user_id` (str UUID) -> stable alias `user_01`..`user_NN`.

    Ordered by `(is_primary DESC, user_id)`. Ordering by `username` would leak
    the real names through the alias ordering itself, which is exactly what the
    aliasing exists to prevent. The primary user is always `user_01`; the rest
    follow UUID order, which is random but stable across runs.
    """
    engine = engine or get_engine()
    sql = text(
        """
        SELECT user_id::text AS user_id
        FROM gold.dim_user
        ORDER BY is_primary DESC, user_id
        """
    )
    with engine.connect() as conn:
        ids = [r[0] for r in conn.execute(sql)]
    return {uid: f"user_{i:02d}" for i, uid in enumerate(ids, start=1)}


def primary_user_id(engine: Optional[Engine] = None) -> Optional[str]:
    """The owner's `user_id`, or None. `is_primary` is uniquely enforced."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT user_id::text FROM gold.dim_user "
                "WHERE is_primary ORDER BY user_id LIMIT 1"
            )
        ).fetchone()
    return row[0] if row else None


def _resolve_users(
    users: Optional[Iterable[str]], aliases: Mapping[str, str]
) -> Optional[list[str]]:
    """Accept either aliases ('user_01') or raw UUIDs; return UUIDs."""
    if users is None:
        return None
    reverse = {alias: uid for uid, alias in aliases.items()}
    out: list[str] = []
    for u in users:
        if u in reverse:
            out.append(reverse[u])
        elif u in aliases:
            out.append(u)
        else:
            raise KeyError(
                f"unknown user {u!r}; expected one of {sorted(reverse)} "
                "or a raw user_id"
            )
    return out


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------
# Columns worth having in nearly every notebook. `artist_name`/`track_name` are
# the case-sensitive degenerate dimensions; `artist_key`/`track_key` are the
# normalised join keys. Both are returned -- see the module docstring.
_FACT_DEFAULT_COLS: tuple[str, ...] = (
    "user_id",
    "ts",
    "ms_played",
    "skipped",
    "shuffle",
    "platform",
    "reason_start",
    "reason_end",
    "artist_key",
    "artist_name",
    "track_key",
    "track_name",
    "album_key",
    "is_music",
)

_TIME_COLS: tuple[str, ...] = ("hour", "iso_dow", "is_weekend", "date")

# --- listener-local time -----------------------------------------------------
# The warehouse stores UTC and holds no per-user timezone (Spotify's export has
# no offset field). Every listener in this dataset is India-based, so a single
# +5:30 offset is applied to recover a local hour. This is an ASSUMPTION, not a
# measurement: it is stated here once, quoted in EDA_FINDINGS.md, and is the
# number Phase 14 must revisit if the user base ever stops being single-region.
LOCAL_UTC_OFFSET_HOURS: float = 5.5


def local_hour(df: pd.DataFrame, source: str = "hour") -> pd.Series:
    """UTC hour column -> listener-local hour (0-23), as a float-free int Series.

    Uses `LOCAL_UTC_OFFSET_HOURS`. Half-hour offsets shift which *clock* hour a
    play lands in, so the offset is applied to the full timestamp when `ts` is
    available and to the hour column otherwise.
    """
    if "ts" in df.columns:
        shifted = df["ts"] + pd.Timedelta(hours=LOCAL_UTC_OFFSET_HOURS)
        return shifted.dt.hour.astype("int16")
    hours = df[source].astype("float64") + LOCAL_UTC_OFFSET_HOURS
    return (hours.astype("int64") % 24).astype("int16")


def local_iso_dow(df: pd.DataFrame) -> pd.Series:
    """Listener-local ISO day-of-week (1=Mon..7=Sun), offset-corrected.

    A play just after midnight UTC belongs to the previous local day for a
    negative offset and the same/next for a positive one -- deriving weekday
    from the UTC `iso_dow` misfiles those plays.
    """
    shifted = df["ts"] + pd.Timedelta(hours=LOCAL_UTC_OFFSET_HOURS)
    return (shifted.dt.dayofweek + 1).astype("int16")  # pandas: Mon=0 -> ISO Mon=1


def load_fact(
    users: Optional[Iterable[str]] = None,
    cols: Optional[Sequence[str]] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    music_only: bool = True,
    limit: Optional[int] = None,
    engine: Optional[Engine] = None,
) -> pd.DataFrame:
    """Load `gold.fact_streams` joined to `gold.dim_time`, with aliased users.

    Never projects `username` or `display_name` -- see the module PII rule. The
    returned frame carries a `user` column holding `user_01`-style aliases and
    keeps `user_id` for joins.

    Parameters
    ----------
    users : aliases ('user_01') or raw UUIDs. None = all users.
    cols  : extra/override fact columns. None = `_FACT_DEFAULT_COLS`.
    since, until : ISO dates, compared against `ts`.
    music_only : keep `is_music` rows only (drops video/podcast). Phase 12
        measured 1,082 non-music rows; leaving them in inflates artist counts.
    """
    engine = engine or get_engine()
    aliases = alias_users(engine)
    user_ids = _resolve_users(users, aliases)

    fact_cols = tuple(cols) if cols else _FACT_DEFAULT_COLS
    select_bits = [f"f.{c}" for c in fact_cols]
    select_bits += [f"t.{c}" for c in _TIME_COLS]

    where: list[str] = []
    params: dict[str, object] = {}
    if music_only:
        where.append("f.is_music")
    if user_ids is not None:
        where.append("f.user_id = ANY(:user_ids)")
        params["user_ids"] = [str(u) for u in user_ids]
    if since:
        where.append("f.ts >= :since")
        params["since"] = since
    if until:
        where.append("f.ts < :until")
        params["until"] = until

    sql = (
        f"SELECT {', '.join(select_bits)} "
        "FROM gold.fact_streams f "
        "JOIN gold.dim_time t ON t.time_key = f.time_key"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY f.user_id, f.ts"
    if limit:
        sql += f" LIMIT {int(limit)}"

    df = pd.read_sql(text(sql), engine, params=params)
    if "user_id" in df.columns:
        df["user_id"] = df["user_id"].astype(str)
        df.insert(0, "user", df["user_id"].map(aliases).fillna("unknown"))
    return df


def load_dim(name: str, engine: Optional[Engine] = None) -> pd.DataFrame:
    """Load a `gold` dimension by short name ('artist', 'track', ...).

    `dim_user` is special-cased to drop `username` / `display_name` and expose
    the alias instead -- the same PII rule as `load_fact`.
    """
    engine = engine or get_engine()
    table = name if name.startswith("dim_") else f"dim_{name}"
    allowed = {"dim_user", "dim_time", "dim_artist", "dim_track", "dim_album"}
    if table not in allowed:
        raise ValueError(f"unknown dimension {name!r}; expected one of {sorted(allowed)}")

    if table == "dim_user":
        aliases = alias_users(engine)
        df = pd.read_sql(
            text("SELECT user_id::text AS user_id, is_primary FROM gold.dim_user"),
            engine,
        )
        df.insert(0, "user", df["user_id"].map(aliases).fillna("unknown"))
        return df.sort_values("user").reset_index(drop=True)

    return pd.read_sql(text(f"SELECT * FROM gold.{table}"), engine)


def query(sql: str, params: Optional[Mapping[str, object]] = None,
          engine: Optional[Engine] = None) -> pd.DataFrame:
    """Escape hatch for notebook-specific aggregate SQL.

    Anything selecting from `gold.dim_user` must alias users itself -- prefer
    `load_fact` / `load_dim`, which cannot leak names.
    """
    engine = engine or get_engine()
    return pd.read_sql(text(sql), engine, params=dict(params or {}))


def latest_dq_run(engine: Optional[Engine] = None) -> Optional[dict]:
    """The most recent Phase 13 data-quality run, or None if the suite never ran.

    Notebook 01 reports this so a reader knows whether the findings below it
    were computed on a gate-clean warehouse. Returns None rather than raising
    when migration 013 is absent (e.g. an older database).
    """
    engine = engine or get_engine()
    from sqlalchemy.exc import ProgrammingError

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT dq_run_id::text AS dq_run_id, run_at, status,
                           checks_total, passed, failed, warned, skipped
                    FROM quality.dq_run
                    WHERE status <> 'running'
                    ORDER BY run_at DESC
                    LIMIT 1
                    """
                )
            ).fetchone()
    except ProgrammingError:
        # Migration 013 not applied (older database). Narrow on purpose: a
        # broader `except` here would swallow a column-name typo and silently
        # report "no DQ run" on a warehouse that has plenty.
        return None
    if row is None:
        return None
    return dict(row._mapping)


# ---------------------------------------------------------------------------
# figure output
# ---------------------------------------------------------------------------
def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() or (parent / "docker-compose.yml").exists():
            return parent
    return _API_ROOT.parent.parent


def save_fig(name: str, aggregate: bool = False, fig=None) -> Path:
    """Save the current figure.

    aggregate=False (default) -> `outputs/eda/<name>.png`, which is gitignored.
    Per-user and full-resolution charts stay here: they are derived from real
    listening history for ten identifiable people.

    aggregate=True -> `documentation/assets/eda/<name>.png`, which IS committed.
    Only charts that are aggregate across users -- no per-user series, no
    identifiable listening detail -- may use this, since they are quoted in
    `EDA_FINDINGS.md` and the Phase 16 write-up.
    """
    import matplotlib.pyplot as plt

    root = _repo_root()
    if aggregate:
        out_dir = root / "documentation" / "assets" / "eda"
    else:
        out_dir = root / "outputs" / "eda"
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / (name if name.endswith(".png") else f"{name}.png")
    (fig or plt.gcf()).savefig(path)
    return path


# ---------------------------------------------------------------------------
# decision block
# ---------------------------------------------------------------------------
def decision(**kwargs) -> None:
    """Render a notebook's closing `## Decision inputs` values identically.

    The point of this phase: each notebook ends with the numbers a later phase
    should quote. Call with keyword args, e.g.::

        decision(night_share_cutoff=0.18, hour_buckets="[0-6),[6-12),...",
                 feeds="P14 user_temporal_preferences")

    `feeds` is pulled out and shown first when present.
    """
    try:
        from IPython.display import Markdown, display
    except Exception:  # pragma: no cover - non-IPython execution
        display = None  # type: ignore[assignment]
        Markdown = None  # type: ignore[assignment]

    feeds = kwargs.pop("feeds", None)
    lines = ["**Decision inputs**", ""]
    if feeds:
        lines.append(f"_Feeds:_ {feeds}")
        lines.append("")
    for key, value in kwargs.items():
        if isinstance(value, bool):
            shown = str(value)
        elif isinstance(value, int):
            shown = f"{value:,}"
        elif isinstance(value, float):
            # Never scientific notation: these values get copied into design
            # docs and read by people, so 39,150 beats 3.915e+04.
            if not math.isfinite(value):  # NaN or +/-inf
                shown = str(value)
            elif abs(value) >= 1000:
                shown = f"{value:,.1f}"
            elif abs(value) >= 1:
                shown = f"{value:,.3f}"
            else:
                shown = f"{value:.4f}"
        else:
            shown = str(value)
        lines.append(f"- `{key}` = **{shown}**")
    body = "\n".join(lines)

    if display is not None and Markdown is not None:
        display(Markdown(body))
    else:
        print(body.replace("**", "").replace("_", ""))


__all__ = [
    "PALETTE",
    "SERIES_COLORS",
    "INK",
    "ACCENT",
    "use_style",
    "get_engine",
    "db_available",
    "enough",
    "MIN_ROWS_OVERVIEW",
    "MIN_ROWS_TEMPORAL",
    "MIN_ROWS_ARTIST",
    "MIN_ROWS_SESSION",
    "MIN_ROWS_CF",
    "alias_users",
    "primary_user_id",
    "load_fact",
    "load_dim",
    "LOCAL_UTC_OFFSET_HOURS",
    "local_hour",
    "local_iso_dow",
    "query",
    "latest_dq_run",
    "save_fig",
    "decision",
]
