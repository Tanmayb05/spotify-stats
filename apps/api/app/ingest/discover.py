"""File discovery for the Dagster ingestion pipeline.

Adapts to the repo's data/ layout as it is on disk (Owner Decision 1), no file
moves:

  * primary user   -> data/streaming_[0-9]*.json          (flat, video-excluded)
  * 9 other users  -> data/other users/<slug>/Streaming_History_Audio_*.json

Excluded everywhere: any *Video*/*video* file and anything under
data/Spotify Account Data/.

No DB access -- pure filesystem + hashing, unit-testable (see
tests/test_discover.py).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# slug (directory name) -> masked display name. Moved verbatim from
# load_multi_user_data.py:66-76 (migration 007 masked these; the slug is the
# stable join key). load_multi_user_data.py / load_json_to_supabase.py import
# this back after their Phase 12 deprecation.
USER_SLUGS: dict[str, str] = {
    "abhiraj": "John Smith",
    "amit": "Richard Roe",
    "antara": "Jane Doe",
    "ash": "Mary Major",
    "nihal": "John Stiles",
    "prathamesh": "Richard Miles",
    "sam": "Jane Roe",
    "snehal": "Mary Minor",
    "sohan": "John Poe",
}

PRIMARY_SLUG = "primary"
PRIMARY_DISPLAY_NAME = "Primary User"

# All 10 partition keys, in deterministic order. Dagster's
# StaticPartitionsDefinition (assets.py) uses this list verbatim.
ALL_SLUGS: list[str] = [PRIMARY_SLUG, *sorted(USER_SLUGS)]


@dataclass(frozen=True)
class DiscoveredFile:
    path: Path
    rel_path: str          # path relative to data_root(), POSIX-style, for provenance
    slug: str
    display_name: str
    file_hash: str         # sha256 hex of the file bytes
    size_bytes: int
    is_primary: bool


def data_root() -> Path:
    """Repo-root data/ directory. Overridable by callers (tests, the Dagster
    DataRootResource) via discover_files(root=...)."""
    # apps/api/app/ingest/discover.py -> parents[4] == repo root
    return Path(__file__).resolve().parents[4] / "data"


def file_sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _is_excluded(path: Path, root: Path) -> bool:
    """Video exports and the Spotify Account Data dump are never ingested."""
    name_l = path.name.lower()
    if "video" in name_l:
        return True
    try:
        rel_parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        rel_parts = path.parts
    return "spotify account data" in (p.lower() for p in rel_parts)


def _mk(path: Path, root: Path, slug: str, display_name: str, is_primary: bool) -> DiscoveredFile:
    return DiscoveredFile(
        path=path,
        rel_path=path.resolve().relative_to(root.resolve()).as_posix(),
        slug=slug,
        display_name=display_name,
        file_hash=file_sha256(path),
        size_bytes=path.stat().st_size,
        is_primary=is_primary,
    )


def discover_files(
    root: Path | None = None,
    only: Sequence[str] | None = None,
) -> list[DiscoveredFile]:
    """Return every ingestable export file, sorted by (slug, rel_path).

    `only` restricts to a subset of slugs (the old --only flag / a Dagster
    partition selection). Unknown slugs in `only` are ignored.
    """
    root = (root or data_root()).resolve()
    wanted = set(only) if only else None
    out: list[DiscoveredFile] = []

    # Primary: flat data/streaming_[0-9]*.json. The [0-9] class is what makes
    # this video-excluding already (streaming_video_*.json has no digit after
    # the underscore); the _is_excluded belt-and-braces catches the rest.
    if wanted is None or PRIMARY_SLUG in wanted:
        for path in root.glob("streaming_[0-9]*.json"):
            if path.is_file() and not _is_excluded(path, root):
                out.append(_mk(path, root, PRIMARY_SLUG, PRIMARY_DISPLAY_NAME, True))

    # Other users: data/other users/<slug>/Streaming_History_Audio_*.json
    others_dir = root / "other users"
    for slug, display_name in USER_SLUGS.items():
        if wanted is not None and slug not in wanted:
            continue
        user_dir = others_dir / slug
        if not user_dir.is_dir():
            continue
        for path in user_dir.glob("Streaming_History_Audio_*.json"):
            if path.is_file() and not _is_excluded(path, root):
                out.append(_mk(path, root, slug, display_name, False))

    out.sort(key=lambda df: (df.slug, df.rel_path))
    return out
