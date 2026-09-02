"""Salvage-parse a JSON file whose write was truncated mid-array.

Moved here from app/services/data_loader.py (Phase 11 Step 4 / deviation #6
in the Phase 11 plan) so both the live recommender/simulator loader and
scripts/load_enrichment_to_db.py share exactly one implementation instead of
two copies drifting apart.

songs_info.json in this repo is a confirmed truncated write (json.load raises
JSONDecodeError partway through); this decodes every clean object up to the
first malformed one instead of failing the whole file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def salvage_json_array(path: Path, array_key: str) -> List[Dict[str, Any]]:
    """Decode a JSON object's ``array_key`` array element-by-element, stopping
    at the first malformed entry.

    Returns [] if the file does not exist or the key marker is not found --
    never raises, so a missing/corrupt enrichment file degrades gracefully
    rather than failing the caller.
    """
    if not path.exists():
        return []
    txt = path.read_text(encoding="utf-8")
    try:
        marker = txt.index(f'"{array_key}"')
        start = txt.index("[", marker) + 1
    except ValueError:
        return []
    decoder = json.JSONDecoder()
    items: List[Dict[str, Any]] = []
    i, n = start, len(txt)
    while i < n:
        while i < n and txt[i] in " \t\r\n,":
            i += 1
        if i >= n or txt[i] == "]":
            break
        try:
            obj, end = decoder.raw_decode(txt, i)
        except json.JSONDecodeError:
            break
        if isinstance(obj, dict):
            items.append(obj)
        i = end
    return items
