#!/usr/bin/env python3
"""Capture a canonical snapshot of every API route's JSON response.

Paired with compare_api_baseline.py. This is the "numbers unchanged" gate
(V4) for Phase 11: capture BEFORE the star-schema migrations run, migrate,
then compare AFTER. Any value difference means a rewritten materialized view
or RPC silently changed a number -- which the app's except-and-return-empty
pattern (backends.py) would otherwise hide as a blank chart, not an error.

    python scripts/capture_api_baseline.py --out outputs/baseline/pre_phase11
    python scripts/capture_api_baseline.py --base-url http://localhost:3011

Canonicalisation, so a byte-diff is meaningful:
  * dict keys sorted recursively
  * floats rounded to 6 decimal places
  * response written as pretty JSON with sorted keys

Routes needing path/query parameters (flashback, compare/overlap, etc.) are
called with fixed, deterministic arguments chosen from the seeded data so the
same call can be repeated after migration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

DEFAULT_BASE_URL = "http://localhost:3011"
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[3] / "outputs" / "baseline" / "pre_phase11"


# Keys whose value is a call-time timestamp, not derived data -- e.g.
# /api/reco and /api/simulate/next both stamp `generated_at` with `now()`.
# Comparing these would always show a diff regardless of whether the
# underlying numbers changed, so they are dropped before canonicalizing.
_VOLATILE_KEYS = {"generated_at"}


def canonicalize(value: Any) -> Any:
    """Recursively sort dict keys and round floats to 6dp for a stable diff.

    Drops _VOLATILE_KEYS so call-time-only fields don't produce false diffs.
    """
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


def slugify(name: str) -> str:
    return (
        name.strip("/")
        .replace("/", "__")
        .replace("?", "_")
        .replace("&", "_")
        .replace("=", "-")
        .replace(":", "-")
        or "root"
    )


def discover_routes(base_url: str) -> List[Dict[str, Any]]:
    """Pull the live OpenAPI schema for the exact set of GET routes to hit."""
    resp = requests.get(f"{base_url}/openapi.json", timeout=10)
    resp.raise_for_status()
    schema = resp.json()
    routes = []
    for path, methods in schema.get("paths", {}).items():
        if "get" not in methods:
            continue
        routes.append({"path": path, "params": methods["get"].get("parameters", [])})
    return sorted(routes, key=lambda r: r["path"])


# Fixed, deterministic arguments for routes whose required/interesting query
# params are not safely defaultable. Chosen against the seeded primary-user
# dataset (71,052 rows, 2018-2025) so the same call is repeatable post-migration.
FIXED_PARAMS: Dict[str, Dict[str, str]] = {
    "/api/milestones/flashback": {"date": "2023-06-15"},
    "/api/compare/overlap": {"users": ""},  # filled in dynamically, see below
    "/api/compare/top-artists": {"users": ""},
}

# Routes that legitimately require dynamic data (user ids) resolved at runtime.
DYNAMIC_PARAM_ROUTES = {"/api/compare/overlap", "/api/compare/top-artists"}


def resolve_dynamic_params(base_url: str) -> Dict[str, Dict[str, str]]:
    """Resolve user_id-dependent params against the live /api/compare/users list."""
    out: Dict[str, Dict[str, str]] = {}
    try:
        resp = requests.get(f"{base_url}/api/compare/users", timeout=10)
        resp.raise_for_status()
        users = resp.json()
        ids = [u["user_id"] for u in users][:2]
        if len(ids) >= 1:
            out["/api/compare/top-artists"] = {"users": ids[0]}
        if len(ids) >= 2:
            out["/api/compare/overlap"] = {"users": ",".join(ids[:2])}
    except Exception as exc:  # pragma: no cover
        print(f"  warning: could not resolve dynamic params: {exc}")
    return out


def build_call_params(path: str, openapi_params: List[Dict[str, Any]], dynamic: Dict[str, Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Decide the query params to send for one path, or None to skip it."""
    if path in dynamic:
        return dynamic[path]
    if path in FIXED_PARAMS:
        return FIXED_PARAMS[path]
    if path in DYNAMIC_PARAM_ROUTES:
        return None  # could not resolve -- skip rather than send a bad call
    # No params needed, or all optional -- call with none (uses defaults).
    required = [p for p in openapi_params if p.get("required")]
    if required:
        print(f"  skip {path}: required params with no fixture value: "
              f"{[p['name'] for p in required]}")
        return None
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    print(f"Discovering routes from {args.base_url}/openapi.json ...")
    routes = discover_routes(args.base_url)
    print(f"  {len(routes)} GET routes found")

    dynamic = resolve_dynamic_params(args.base_url)

    manifest: List[Dict[str, Any]] = []
    ok, skipped, failed = 0, 0, 0

    for route in routes:
        path = route["path"]
        params = build_call_params(path, route["params"], dynamic)
        if params is None:
            skipped += 1
            manifest.append({"path": path, "status": "skipped"})
            continue

        try:
            resp = requests.get(f"{args.base_url}{path}", params=params, timeout=30)
            content_type = resp.headers.get("content-type", "")
            fname = slugify(path + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else ""))

            if "application/json" in content_type:
                data = canonicalize(resp.json())
                out_path = args.out / f"{fname}.json"
                out_path.write_text(json.dumps(data, indent=2, sort_keys=True))
            else:
                # CSV export endpoints -- store raw text.
                out_path = args.out / f"{fname}.txt"
                out_path.write_text(resp.text)

            manifest.append({
                "path": path,
                "params": params,
                "status_code": resp.status_code,
                "content_type": content_type,
                "file": out_path.name,
                "status": "ok" if resp.status_code == 200 else "non_200",
            })
            if resp.status_code == 200:
                ok += 1
            else:
                failed += 1
                print(f"  {resp.status_code} {path} params={params}")
        except Exception as exc:
            failed += 1
            manifest.append({"path": path, "params": params, "status": "error", "error": str(exc)})
            print(f"  ERROR {path}: {exc}")

    (args.out / "_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    print(f"\nCaptured {ok} ok, {skipped} skipped, {failed} failed -> {args.out}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
