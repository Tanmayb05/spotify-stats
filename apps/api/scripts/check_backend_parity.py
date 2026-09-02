#!/usr/bin/env python3
"""Diff every loader method between the two DB backends.

The loader swallows exceptions and returns {} / [] on failure, so a wrong
function signature or a type mismatch on the local path surfaces as a blank
chart rather than an error. This script is the guard against that class of
silent regression, and is the main verification step for Phase 10.

    python scripts/check_backend_parity.py

Requires both backends to be reachable and pointed at the SAME data:
  DATABASE_URL      local Postgres, seeded from the same export
  SUPABASE_URL / SUPABASE_SERVICE_KEY

Row counts will differ if the two hold different data; --tolerant compares
shapes and types rather than values, which is the useful mode then.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# (method name, kwargs). Covers all four families: RPC-backed, table reads,
# materialized-view reads, and the delegated numpy/sklearn paths.
CALLS: List[Tuple[str, Dict[str, Any]]] = [
    ("get_overview_stats", {}),
    ("get_top_artists", {"limit": 10}),
    ("get_top_tracks", {"limit": 10}),
    ("get_monthly_data", {}),
    ("get_platform_stats", {}),
    ("get_hourly_distribution", {}),
    ("get_daily_distribution", {}),
    ("get_skip_behavior", {"limit": 10}),
    ("get_yearly_comparison", {}),
    ("get_listening_streaks", {"limit": 10}),
    ("get_leaderboard", {}),
    ("list_users", {}),
    ("get_mood_summary", {"window_days": 30}),
    ("get_mood_contexts", {}),          # RETURNS jsonb
    ("get_mood_monthly", {}),
    ("get_discovery_timeline", {}),
    ("get_artist_loyalty", {"limit": 10}),
    ("get_artist_obsessions", {"limit": 10}),
    ("get_reflective_insights", {}),    # RETURNS jsonb
    ("get_weekend_weekday_comparison", {}),  # RETURNS jsonb
    ("get_most_repeated_tracks", {"limit": 10}),
    ("get_monthly_diversity", {}),
    ("get_listening_heatmap", {}),
    ("get_milestones_list", {}),
    ("get_flashback", {"date_str": "2023-01-15"}),  # RETURNS jsonb
    ("get_session_statistics", {}),
    ("get_session_clusters", {}),
    ("get_session_centroids", {}),
    ("get_session_assignments", {}),
    ("get_session_durations", {}),
    ("get_binge_sessions", {}),
    ("get_sim_artists", {}),
    ("get_recommendations", {"top_k": 10}),
    ("get_simulation", {"n": 10}),
]


def shape(value: Any, depth: int = 0) -> Any:
    """A structural fingerprint: types and keys, not values."""
    if depth > 3:
        return "..."
    if isinstance(value, dict):
        return {k: shape(v, depth + 1) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0], depth + 1)] if value else []
    return type(value).__name__


def run_backend(backend: str) -> Dict[str, Any]:
    """Collect every method's result under one backend, in a fresh process state."""
    import app.config
    import app.db.backends as backends_mod
    import app.services.supabase_data_loader as loader_mod

    app.config.settings.db_backend = backend  # type: ignore[assignment]
    loader_mod.reset_loader()
    loader = loader_mod.SupabaseDataLoader(backends_mod.build_backend(app.config.settings))

    results: Dict[str, Any] = {}
    for name, kwargs in CALLS:
        try:
            results[name] = getattr(loader, name)(**kwargs)
        except Exception as exc:  # noqa: BLE001
            results[name] = {"__error__": f"{type(exc).__name__}: {exc}"}
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the two DB backends.")
    parser.add_argument(
        "--tolerant",
        action="store_true",
        help="Compare structure/types only, not values (use when the two "
        "backends hold different data).",
    )
    parser.add_argument("--verbose", action="store_true", help="Print the first diff in full")
    args = parser.parse_args()

    print("Running local backend ...")
    local = run_backend("local")
    print("Running supabase backend ...")
    supa = run_backend("supabase")

    failures: List[str] = []
    print(f"\n{'RESULT':<9} {'METHOD':<34} LOCAL / SUPABASE")
    for name, _ in CALLS:
        lhs, rhs = local[name], supa[name]

        l_err = isinstance(lhs, dict) and "__error__" in lhs
        r_err = isinstance(rhs, dict) and "__error__" in rhs
        if l_err or r_err:
            failures.append(name)
            print(f"{'ERROR':<9} {name:<34} {lhs if l_err else ''} {rhs if r_err else ''}")
            continue

        if args.tolerant:
            same = shape(lhs) == shape(rhs)
        else:
            same = json.dumps(lhs, sort_keys=True, default=str) == json.dumps(
                rhs, sort_keys=True, default=str
            )

        l_n = len(lhs) if hasattr(lhs, "__len__") else "-"
        r_n = len(rhs) if hasattr(rhs, "__len__") else "-"
        verdict = "match" if same else "DIFF"
        if not same:
            failures.append(name)
        print(f"{verdict:<9} {name:<34} {type(lhs).__name__}({l_n}) / {type(rhs).__name__}({r_n})")

        if not same and args.verbose:
            print(f"    local:    {json.dumps(lhs, default=str)[:400]}")
            print(f"    supabase: {json.dumps(rhs, default=str)[:400]}")

    print()
    if failures:
        print(f"{len(failures)} mismatch(es): {', '.join(failures)}")
        return 1
    print(f"All {len(CALLS)} methods agree across backends.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
