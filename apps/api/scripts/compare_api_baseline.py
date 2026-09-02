#!/usr/bin/env python3
"""Diff live API responses against a captured baseline (Phase 11 gate V4).

    python scripts/capture_api_baseline.py --out outputs/baseline/pre_phase11
    # ... apply migrations 008-010, run build_star_schema.py ...
    python scripts/compare_api_baseline.py --baseline outputs/baseline/pre_phase11

Re-issues every call recorded in the baseline's _manifest.json against the
live API, canonicalizes the same way (sorted keys, floats rounded 6dp), and
reports every path whose value changed. Exit code is non-zero if any value
differs -- this is the gate, not a courtesy report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests

DEFAULT_BASE_URL = "http://localhost:3011"
DEFAULT_BASELINE_DIR = Path(__file__).resolve().parents[3] / "outputs" / "baseline" / "pre_phase11"


# Must match capture_api_baseline.py's _VOLATILE_KEYS exactly, or a call-time
# field (e.g. /api/reco's generated_at) shows up as a spurious diff.
_VOLATILE_KEYS = {"generated_at"}


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: canonicalize(value[k])
            for k in sorted(value.keys())
            if k not in _VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [canonicalize(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def diff_paths(a: Any, b: Any, path: str = "$") -> List[str]:
    """Return a list of human-readable diffs between two canonicalized values."""
    diffs: List[str] = []
    if type(a) is not type(b):
        # int vs float after rounding is fine (json roundtrip); anything else is real.
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if a != b:
                diffs.append(f"{path}: {a!r} -> {b!r}")
            return diffs
        diffs.append(f"{path}: type {type(a).__name__} -> {type(b).__name__} ({a!r} -> {b!r})")
        return diffs
    if isinstance(a, dict):
        keys = sorted(set(a.keys()) | set(b.keys()))
        for k in keys:
            if k not in a:
                diffs.append(f"{path}.{k}: MISSING in baseline -> {b[k]!r}")
            elif k not in b:
                diffs.append(f"{path}.{k}: {a[k]!r} -> MISSING in live")
            else:
                diffs.extend(diff_paths(a[k], b[k], f"{path}.{k}"))
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: length {len(a)} -> {len(b)}")
        for i, (av, bv) in enumerate(zip(a, b)):
            diffs.extend(diff_paths(av, bv, f"{path}[{i}]"))
    else:
        if a != b:
            diffs.append(f"{path}: {a!r} -> {b!r}")
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--report", type=Path, default=None,
                         help="Optional path to write the full diff report JSON")
    args = parser.parse_args()

    manifest_path = args.baseline / "_manifest.json"
    if not manifest_path.exists():
        print(f"No baseline manifest at {manifest_path}. Run capture_api_baseline.py first.")
        return 2

    manifest = json.loads(manifest_path.read_text())

    total = 0
    changed = 0
    errors = 0
    report: List[Dict[str, Any]] = []

    for entry in manifest:
        if entry.get("status") != "ok":
            continue
        path = entry["path"]
        params = entry.get("params") or {}
        total += 1

        try:
            resp = requests.get(f"{args.base_url}{path}", params=params, timeout=30)
        except Exception as exc:
            errors += 1
            report.append({"path": path, "params": params, "error": f"request failed: {exc}"})
            print(f"  ERROR {path}: request failed: {exc}")
            continue

        if resp.status_code != 200:
            errors += 1
            report.append({"path": path, "params": params, "error": f"status {resp.status_code}"})
            print(f"  ERROR {path}: status {resp.status_code} (baseline was 200)")
            continue

        baseline_file = args.baseline / entry["file"]
        if entry["file"].endswith(".json"):
            baseline_value = json.loads(baseline_file.read_text())
            live_value = canonicalize(resp.json())
            diffs = diff_paths(baseline_value, live_value)
        else:
            # Compare bytes, not text: Path.read_text() applies universal-
            # newline translation (\r\n -> \n), but resp.text does not --
            # the CSV export routes emit RFC 4180 \r\n line endings via
            # csv.writer, so a naive text-mode comparison always reports a
            # false "changed" even when the data is byte-identical.
            baseline_bytes = baseline_file.read_bytes()
            live_bytes = resp.content
            diffs = [] if baseline_bytes == live_bytes else ["byte content differs"]

        if diffs:
            changed += 1
            report.append({"path": path, "params": params, "diffs": diffs})
            print(f"  CHANGED {path} params={params} ({len(diffs)} diff(s))")
            for d in diffs[:5]:
                print(f"      {d}")
            if len(diffs) > 5:
                print(f"      ... and {len(diffs) - 5} more")

    print(f"\nCompared {total} routes: {total - changed - errors} identical, "
          f"{changed} changed, {errors} errored.")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f"Full report -> {args.report}")

    return 0 if (changed == 0 and errors == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
