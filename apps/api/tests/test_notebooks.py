"""Tests for the Phase 13.5 EDA notebooks (apps/api/notebooks/).

Pure tests (no DB) always run in CI -- the PII checks are the point of this
file and must not be skippable. DB-backed tests are skipped unless DATABASE_URL
is set, following the convention in test_quality.py / test_dedup.py.

The PII checks read the list of real first names out of
migrations/007_mask_user_names.sql at test time rather than hardcoding them:
writing the names into a committed test file would leak exactly what the test
exists to prevent.
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = API_ROOT / "notebooks"
MASK_MIGRATION = API_ROOT / "migrations" / "007_mask_user_names.sql"
EDA_FINDINGS = REPO_ROOT / "documentation" / "EDA_FINDINGS.md"

DB_URL = os.getenv("DATABASE_URL")
db_only = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")

EXPECTED_NOTEBOOKS = 9  # 00 exploratory (no decision framing) + 8 decision-support
# 00 is general look-and-see -- no downstream decision, no Decision-inputs cell.
NO_DECISION_INPUTS = {"00_exploratory"}


def notebooks() -> list[Path]:
    return sorted(NOTEBOOK_DIR.glob("[0-9][0-9]_*.ipynb"))


def decision_notebooks() -> list[Path]:
    return [p for p in notebooks() if p.stem not in NO_DECISION_INPUTS]


def real_usernames() -> set[str]:
    """The 10 real first names, parsed from the masking migration's VALUES rows.

    Lines look like:  ('tanmay',     'John Doe'),
    """
    sql = MASK_MIGRATION.read_text()
    body = sql.split("UPDATE users SET display_name", 1)[-1]
    names = set(re.findall(r"\(\s*'([a-z]+)'\s*,\s*'[^']+'\s*\)", body))
    return names


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------
def test_notebook_dir_exists():
    assert NOTEBOOK_DIR.is_dir(), f"missing {NOTEBOOK_DIR}"


def test_expected_notebook_count():
    found = notebooks()
    assert len(found) == EXPECTED_NOTEBOOKS, (
        f"expected {EXPECTED_NOTEBOOKS} notebooks, found {len(found)}: "
        f"{[p.name for p in found]}"
    )


def test_common_module_present():
    assert (NOTEBOOK_DIR / "_common.py").is_file()


def test_readme_present():
    assert (NOTEBOOK_DIR / "README.md").is_file()


@pytest.mark.parametrize("nb_path", notebooks(), ids=lambda p: p.name)
def test_notebook_is_valid_json(nb_path: Path):
    json.loads(nb_path.read_text())


@pytest.mark.parametrize("nb_path", decision_notebooks(), ids=lambda p: p.name)
def test_notebook_has_decision_inputs_cell(nb_path: Path):
    """Every decision-support notebook must end with the numbers a later phase
    can quote. Exploratory notebooks (NO_DECISION_INPUTS) are exempt."""
    nb = json.loads(nb_path.read_text())
    text = "\n".join(
        "".join(c.get("source", []))
        for c in nb["cells"]
        if c.get("cell_type") == "markdown"
    )
    assert "## Decision inputs" in text, (
        f"{nb_path.name} has no '## Decision inputs' cell -- that cell is the "
        "phase's deliverable"
    )


@pytest.mark.parametrize("nb_path", decision_notebooks(), ids=lambda p: p.name)
def test_notebook_calls_decision_helper(nb_path: Path):
    nb = json.loads(nb_path.read_text())
    code = "\n".join(
        "".join(c.get("source", []))
        for c in nb["cells"]
        if c.get("cell_type") == "code"
    )
    assert "C.decision(" in code, f"{nb_path.name} never calls C.decision()"


# ---------------------------------------------------------------------------
# PII -- these must never be skipped
# ---------------------------------------------------------------------------
def test_migration_name_list_is_parseable():
    """Guard the guard: if this parse breaks, the PII tests silently pass."""
    names = real_usernames()
    assert len(names) >= 10, (
        f"parsed only {len(names)} usernames from {MASK_MIGRATION.name}; "
        "the PII checks below depend on this list being complete"
    )


@pytest.mark.parametrize("nb_path", notebooks(), ids=lambda p: p.name)
def test_notebook_has_no_outputs(nb_path: Path):
    """Committed notebooks carry no outputs -- outputs embed real listening
    history for ten identifiable people."""
    nb = json.loads(nb_path.read_text())
    offenders = [
        i for i, c in enumerate(nb["cells"])
        if c.get("cell_type") == "code" and c.get("outputs")
    ]
    assert not offenders, (
        f"{nb_path.name} has outputs in cells {offenders}. Re-run "
        "`python notebooks/build_notebooks.py` or `nbstripout` before committing."
    )


@pytest.mark.parametrize("nb_path", notebooks(), ids=lambda p: p.name)
def test_notebook_contains_no_real_usernames(nb_path: Path):
    names = real_usernames()
    content = nb_path.read_text().lower()
    # Word-boundary match: a substring hit on a short name would fire on
    # ordinary English and make this test useless noise.
    found = {n for n in names if re.search(rf"\b{re.escape(n)}\b", content)}
    assert not found, f"{nb_path.name} contains real username(s): {sorted(found)}"


def test_common_module_contains_no_real_usernames():
    names = real_usernames()
    content = (NOTEBOOK_DIR / "_common.py").read_text().lower()
    found = {n for n in names if re.search(rf"\b{re.escape(n)}\b", content)}
    assert not found, f"_common.py contains real username(s): {sorted(found)}"


def test_eda_findings_contains_no_real_usernames():
    if not EDA_FINDINGS.is_file():
        pytest.skip("EDA_FINDINGS.md not written yet")
    names = real_usernames()
    content = EDA_FINDINGS.read_text().lower()
    found = {n for n in names if re.search(rf"\b{re.escape(n)}\b", content)}
    assert not found, f"EDA_FINDINGS.md contains real username(s): {sorted(found)}"


@pytest.mark.parametrize("nb_path", notebooks(), ids=lambda p: p.name)
def test_notebook_does_not_select_name_columns(nb_path: Path):
    """No notebook may query username / display_name, even aliased later."""
    nb = json.loads(nb_path.read_text())
    code = "\n".join(
        "".join(c.get("source", []))
        for c in nb["cells"]
        if c.get("cell_type") == "code"
    ).lower()
    for column in ("username", "display_name"):
        assert column not in code, (
            f"{nb_path.name} references {column!r}; use the alias from "
            "_common.load_fact() instead"
        )


# ---------------------------------------------------------------------------
# _common contract (DB-backed)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def common_module():
    sys.path.insert(0, str(NOTEBOOK_DIR))
    sys.path.insert(0, str(API_ROOT))
    import _common

    return _common


def test_common_imports_without_a_database(common_module):
    """Importing must not touch the DB -- notebooks import before connecting."""
    assert common_module.PALETTE[0].startswith("#")
    assert common_module.LOCAL_UTC_OFFSET_HOURS == 5.5


def test_enough_guard_semantics(common_module):
    assert common_module.enough(500, 100, "rows") is True
    assert common_module.enough(5, 100, "rows") is False
    assert common_module.enough(None, 1, "rows") is False
    assert common_module.enough([], 1, "rows") is False


def test_local_hour_applies_the_offset(common_module):
    import pandas as pd

    df = pd.DataFrame(
        {"ts": pd.to_datetime(["2025-01-01 00:00:00+00:00"], utc=True), "hour": [0]}
    )
    # 00:00 UTC + 5:30 = 05:30 local -> hour 5
    assert int(common_module.local_hour(df).iloc[0]) == 5


@db_only
def test_load_fact_never_returns_name_columns(common_module):
    df = common_module.load_fact(limit=50)
    assert "username" not in df.columns
    assert "display_name" not in df.columns
    assert "user" in df.columns


@db_only
def test_aliases_are_stable_and_anonymous(common_module):
    first = common_module.alias_users()
    second = common_module.alias_users()
    assert first == second, "alias assignment must be deterministic across calls"
    assert all(re.fullmatch(r"user_\d{2}", a) for a in first.values())


@db_only
def test_primary_user_is_user_01(common_module):
    aliases = common_module.alias_users()
    primary = common_module.primary_user_id()
    if primary is None:
        pytest.skip("no primary user in this database")
    assert aliases[primary] == "user_01"


@db_only
def test_load_dim_user_is_anonymised(common_module):
    df = common_module.load_dim("user")
    assert "username" not in df.columns
    assert "display_name" not in df.columns
