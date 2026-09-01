"""Database backends behind one interface.

`SupabaseDataLoader` reaches the database through exactly three primitives:
a stored-function call, a filtered table/view read, and range pagination. Those
are the only things this module abstracts, which is why the loader's ~800 lines
of result-shaping stay backend-agnostic and identical for both paths.

  SupabaseBackend -> supabase-py / PostgREST  (DB_BACKEND=supabase, the default)
  LocalBackend    -> SQLAlchemy + psycopg     (DB_BACKEND=local, Docker Compose)

The local path calls the *same* SQL functions defined in apps/api/migrations/,
so migrations remain the single source of truth for both backends.

PostgREST return-shape contract, which LocalBackend must reproduce exactly:
  * A function declared `RETURNS TABLE (...)` yields a **list of row dicts**.
  * A function declared `RETURNS jsonb` yields the **decoded value itself**
    (an object), not a list wrapping it. Four functions do this today:
    get_mood_contexts, get_reflective_insights, get_weekend_weekday_comparison
    and get_flashback -- see supabase_data_loader.get_mood_contexts, which does
    `return resp.data` directly.
Getting this wrong yields silently-empty dashboards rather than errors, because
every caller wraps its call in try/except and falls back to {} or [].
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)

# Identifiers are supplied by module-level constants in the loader, never by
# request input. This is belt-and-braces so no future caller can pass one
# through into SQL text.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_identifier(name: str, kind: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Unsafe {kind} identifier: {name!r}")
    return name


def _jsonify(value: Any) -> Any:
    """Convert a psycopg-native value to what PostgREST would have returned.

    PostgREST serialises results as JSON, so the loader's callers expect
    timestamps as ISO-8601 strings, numerics as floats, and UUIDs as strings.
    psycopg hands back datetime / Decimal / UUID objects instead. Without this,
    the mismatch shows up far downstream as
    `'datetime.datetime' object is not subscriptable` -- or, worse, is swallowed
    by a caller's except-and-return-empty and becomes a blank chart.
    """
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, _dt.timedelta):
        return value.total_seconds()
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    return value


def _jsonify_rows(rows: Sequence[Any]) -> List[Dict[str, Any]]:
    return [{k: _jsonify(v) for k, v in dict(row).items()} for row in rows]


class DBBackend(Protocol):
    """The database surface the loader depends on."""

    def rpc(self, fn: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Call a stored function. Returns a list of rows, or a scalar jsonb value."""
        ...

    def select(
        self,
        table: str,
        columns: str,
        *,
        eq: Optional[Dict[str, Any]] = None,
        order: Optional[Sequence[Tuple[str, bool]]] = None,
        limit: Optional[int] = None,
        range_: Optional[Tuple[int, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Read a table or view. `order` is a sequence of (column, descending).

        `range_` is an inclusive (start, end) row range, matching PostgREST's
        .range() semantics.
        """
        ...


class SupabaseBackend:
    """PostgREST via supabase-py. Behaviourally identical to the pre-Phase-10 code."""

    def __init__(self, url: Optional[str], key: Optional[str]) -> None:
        if not url or not key:
            raise ValueError(
                "Missing Supabase credentials. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_KEY in spotify-insights.env, or set "
                "DB_BACKEND=local with DATABASE_URL to use a local Postgres."
            )
        try:
            from supabase import Client, create_client
        except ImportError:  # pragma: no cover
            raise ImportError("supabase-py is required. Install with: pip install supabase")

        self.client: "Client" = create_client(url, key)

    def rpc(self, fn: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self.client.rpc(fn, params or {}).execute().data

    def select(
        self,
        table: str,
        columns: str,
        *,
        eq: Optional[Dict[str, Any]] = None,
        order: Optional[Sequence[Tuple[str, bool]]] = None,
        limit: Optional[int] = None,
        range_: Optional[Tuple[int, int]] = None,
    ) -> List[Dict[str, Any]]:
        query = self.client.table(table).select(columns)
        for column, value in (eq or {}).items():
            query = query.eq(column, value)
        for column, descending in order or ():
            query = query.order(column, desc=descending)
        if limit is not None:
            query = query.limit(limit)
        if range_ is not None:
            query = query.range(range_[0], range_[1])
        return query.execute().data or []


class LocalBackend:
    """Direct SQL against a local Postgres, via SQLAlchemy."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError(
                "DB_BACKEND=local requires DATABASE_URL "
                "(e.g. postgresql+psycopg://postgres:postgres@localhost:5432/spotify)"
            )
        from sqlalchemy import create_engine

        # pool_pre_ping keeps long-lived dev sessions alive across DB restarts.
        self.engine = create_engine(
            self._normalise_url(database_url), pool_pre_ping=True, future=True
        )

    @staticmethod
    def _normalise_url(url: str) -> str:
        """Pin the psycopg3 driver; a bare postgresql:// URL defaults to psycopg2."""
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    def rpc(self, fn: str, params: Optional[Dict[str, Any]] = None) -> Any:
        from sqlalchemy import text

        _check_identifier(fn, "function")
        params = params or {}

        # Named-argument syntax (`limit_count => :limit_count`) means an omitted
        # key falls through to the function's DEFAULT. That is what preserves
        # the loader's `_uid()` contract: leaving p_user_id out lets SQL's
        # _effective_user_id() resolve to the primary user.
        arg_list = ", ".join(f"{_check_identifier(k, 'argument')} => :{k}" for k in params)
        sql = f"SELECT * FROM {fn}({arg_list})"

        with self.engine.connect() as conn:
            try:
                result = conn.execute(text(sql), params)
                rows = result.mappings().all()
                columns = list(result.keys())
            except Exception:
                # Surface the statement: callers swallow exceptions and return
                # empty, so without this a signature mismatch is invisible.
                logger.exception("Local RPC failed: %s params=%s", sql, sorted(params))
                raise

        # A `RETURNS jsonb` function produces a single column named after the
        # function itself; unwrap it so callers see the object, as PostgREST does.
        if len(columns) == 1 and columns[0] == fn:
            if not rows:
                return None
            return _jsonify(rows[0][columns[0]])

        return _jsonify_rows(rows)

    def select(
        self,
        table: str,
        columns: str,
        *,
        eq: Optional[Dict[str, Any]] = None,
        order: Optional[Sequence[Tuple[str, bool]]] = None,
        limit: Optional[int] = None,
        range_: Optional[Tuple[int, int]] = None,
    ) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        _check_identifier(table, "table")

        if columns.strip() == "*":
            projection = "*"
        else:
            cols = [c.strip() for c in columns.split(",") if c.strip()]
            projection = ", ".join(_check_identifier(c, "column") for c in cols)

        sql = f"SELECT {projection} FROM {table}"
        params: Dict[str, Any] = {}

        if eq:
            clauses = []
            for i, (column, value) in enumerate(eq.items()):
                key = f"eq_{i}"
                clauses.append(f"{_check_identifier(column, 'column')} = :{key}")
                params[key] = value
            sql += " WHERE " + " AND ".join(clauses)

        if order:
            parts = [
                f"{_check_identifier(c, 'column')} {'DESC' if desc else 'ASC'}"
                for c, desc in order
            ]
            sql += " ORDER BY " + ", ".join(parts)

        if range_ is not None:
            start, end = range_
            params["_limit"] = end - start + 1  # PostgREST ranges are inclusive
            params["_offset"] = start
            sql += " LIMIT :_limit OFFSET :_offset"
        elif limit is not None:
            params["_limit"] = limit
            sql += " LIMIT :_limit"

        with self.engine.connect() as conn:
            try:
                rows = conn.execute(text(sql), params).mappings().all()
            except Exception:
                logger.exception("Local select failed: %s", sql)
                raise
        return _jsonify_rows(rows)


def build_backend(settings) -> DBBackend:
    """Construct the backend named by settings.db_backend."""
    if settings.is_local:
        return LocalBackend(settings.database_url or "")
    return SupabaseBackend(settings.supabase_url, settings.supabase_key)
