"""Dagster resources: a Postgres engine and the data-root path.

PostgresResource wraps app.db.session.make_engine -- NOT get_engine(), which is
lru_cache'd and returns one process-wide engine. A long-lived Dagster daemon
wants an engine whose lifecycle it controls; make_engine builds a fresh one
bound to this resource's config.

make_engine(None) already falls back to settings.database_url, which reads the
repo-root spotify-insights.env, so a bare `dagster dev` works unconfigured. The
compose service passes DATABASE_URL explicitly.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import cached_property
from pathlib import Path

from dagster import ConfigurableResource
from sqlalchemy.engine import Engine

from app.db.session import make_engine
from app.ingest.discover import data_root


class PostgresResource(ConfigurableResource):
    """SQLAlchemy engine for the local Postgres backend.

    `database_url` is optional: unset -> settings.database_url (spotify-insights.env).
    """

    database_url: str | None = None

    @cached_property
    def engine(self) -> Engine:
        return make_engine(self.database_url or None)

    @contextmanager
    def begin(self):
        """`with postgres.begin() as conn:` -- a transaction on the resource engine."""
        with self.engine.begin() as conn:
            yield conn

    @contextmanager
    def connect(self):
        with self.engine.connect() as conn:
            yield conn


class DataRootResource(ConfigurableResource):
    """Filesystem root under which discover.py looks for export files.

    Defaults to <repo>/data (discover.data_root()). The compose service sets
    INGEST_DATA_ROOT=/app/data.
    """

    path: str | None = None

    @cached_property
    def root(self) -> Path:
        return Path(self.path) if self.path else data_root()
