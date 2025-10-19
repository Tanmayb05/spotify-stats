"""
Shared path utilities for analysis scripts.
"""

from __future__ import annotations

from pathlib import Path


def find_project_root() -> Path:
    """Detect repository root by locating the shared data directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / 'data').exists():
            return parent
    return current.parent


PROJECT_ROOT = find_project_root()
DATA_DIR = PROJECT_ROOT / 'data'
OUTPUT_DIR = PROJECT_ROOT / 'outputs'
IMAGES_DIR = OUTPUT_DIR / 'images'
DATA_OUTPUT_DIR = OUTPUT_DIR / 'data'
