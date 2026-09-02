"""Ingestion primitives shared by the seeder, the enrichment loader, and
scripts/build_star_schema.py.

Phase 11 extracts what was inline logic in scripts/seed_local_db.py into pure,
testable functions here (normalize.py) plus the JSON salvage-parser shared
with app/services/data_loader.py (salvage.py). Phase 12's Dagster pipeline
imports from here directly -- see normalize.row_fingerprint, defined now but
first *used* for dedup in Phase 12.
"""
