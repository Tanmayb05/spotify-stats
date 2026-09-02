"""Generate the eight Phase 13.5 EDA notebooks from the cell sources in nb_sources/.

Notebooks are JSON and are painful to hand-author and to review in a diff. Each
notebook here is written as a plain .py file under `nb_sources/`, split into
cells by `# %% [markdown]` / `# %%` markers (the standard percent format), and
this script renders them to .ipynb with **empty outputs**.

    python notebooks/build_notebooks.py            # build all
    python notebooks/build_notebooks.py 02 05      # build a subset

Committed notebooks always have empty outputs (the PII rule -- outputs embed
real listening history for ten people), so regenerating is also the fastest way
to strip a notebook someone executed locally: re-run this script.

This script is a build tool, not part of the analysis. It imports nothing from
the app and touches no database.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent
SRC_DIR = HERE / "nb_sources"

_MD = "# %% [markdown]"
_CODE = "# %%"


def parse_cells(text: str) -> list[tuple[str, str]]:
    """Split percent-format source into (kind, body) cells."""
    cells: list[tuple[str, str]] = []
    kind: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if kind is None:
            return
        body = "\n".join(buf).strip("\n")
        if body.strip():
            cells.append((kind, body))

    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped == _MD:
            flush()
            kind, buf = "markdown", []
        elif stripped == _CODE:
            flush()
            kind, buf = "code", []
        elif kind == "markdown" and stripped.startswith("# "):
            buf.append(stripped[2:])
        elif kind == "markdown" and stripped == "#":
            buf.append("")
        else:
            buf.append(line)
    flush()
    return cells


def build(src: Path) -> Path:
    nb = nbformat.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    }
    for kind, body in parse_cells(src.read_text()):
        if kind == "markdown":
            nb.cells.append(nbformat.v4.new_markdown_cell(body))
        else:
            cell = nbformat.v4.new_code_cell(body)
            cell.outputs = []
            cell.execution_count = None
            nb.cells.append(cell)

    out = HERE / f"{src.stem}.ipynb"
    nbformat.write(nb, out)
    return out


def main(argv: list[str]) -> int:
    if not SRC_DIR.is_dir():
        print(f"missing {SRC_DIR}", file=sys.stderr)
        return 1
    sources = sorted(SRC_DIR.glob("*.py"))
    if argv:
        sources = [s for s in sources if any(s.stem.startswith(a) for a in argv)]
    if not sources:
        print("no matching sources", file=sys.stderr)
        return 1
    for src in sources:
        out = build(src)
        print(f"wrote {out.relative_to(HERE.parent.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
