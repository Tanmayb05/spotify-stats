"""Centralised configuration for the API.

Before this module, env handling was ad-hoc `os.getenv` at module scope in each
file that needed it. Everything now reads from `settings`.

Env resolution order (first hit wins):
  1. A real environment variable (this is how Docker Compose injects config).
  2. `spotify-insights.env`, discovered by walking up from this file so it works
     regardless of the process CWD (start.sh launches uvicorn from apps/api,
     scripts run from the repo root).
"""

import os
from pathlib import Path
from typing import List, Literal, Optional

from dotenv import load_dotenv

DBBackendName = Literal["local", "supabase"]

# The four origins the app served before CORS became configurable. Kept as the
# default so an unset CORS_ORIGINS changes nothing.
_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3010",
    "http://localhost:5173",
    "http://localhost:3000",
    "https://tanmays-spotify-stats.netlify.app",
]


def _find_repo_root() -> Optional[Path]:
    """Nearest ancestor directory containing spotify-insights.env."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "spotify-insights.env").exists():
            return parent
    return None


def _load_env_file() -> Optional[Path]:
    """Load spotify-insights.env if we can find it. Real env vars still win.

    `load_dotenv` does not override already-set variables, which is what makes
    the Compose-injected values take precedence over a developer's local file.
    """
    root = _find_repo_root()
    if root is not None:
        load_dotenv(root / "spotify-insights.env")
        return root / "spotify-insights.env"
    # Last-resort relative fallback, matching the previous behaviour.
    load_dotenv("spotify-insights.env")
    return None


class Settings:
    """Resolved configuration. Instantiated once as `settings` below."""

    def __init__(self) -> None:
        self.env_file = _load_env_file()

        backend = (os.getenv("DB_BACKEND") or "supabase").strip().lower()
        if backend not in ("local", "supabase"):
            raise ValueError(
                f"DB_BACKEND must be 'local' or 'supabase', got {backend!r}"
            )
        # Default stays 'supabase' until Phase 16 so the live demo is unaffected.
        self.db_backend: DBBackendName = backend  # type: ignore[assignment]

        # Local Postgres (DB_BACKEND=local)
        self.database_url: Optional[str] = os.getenv("DATABASE_URL") or None

        # Supabase / PostgREST (DB_BACKEND=supabase)
        self.supabase_url: Optional[str] = os.getenv("SUPABASE_URL") or None
        self.supabase_key: Optional[str] = (
            os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY") or None
        )

        self.cors_origins: List[str] = self._parse_cors(os.getenv("CORS_ORIGINS"))

    @staticmethod
    def _parse_cors(raw: Optional[str]) -> List[str]:
        if not raw or not raw.strip():
            return list(_DEFAULT_CORS_ORIGINS)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def is_local(self) -> bool:
        return self.db_backend == "local"

    def __repr__(self) -> str:  # credentials deliberately not included
        return (
            f"Settings(db_backend={self.db_backend!r}, "
            f"database_url_set={bool(self.database_url)}, "
            f"supabase_url_set={bool(self.supabase_url)}, "
            f"cors_origins={len(self.cors_origins)})"
        )


settings = Settings()
