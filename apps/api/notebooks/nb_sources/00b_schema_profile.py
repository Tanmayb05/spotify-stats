# %% [markdown]
# # 00b · Schema profile
#
# **Question:** what tables actually exist in this warehouse, what do their
# columns look like, and what values do they hold?
#
# General reference, not a decision-support notebook — no `## Decision inputs`
# cell, same as `00_exploratory`. Everything here is **generated from
# `information_schema` and per-column queries**, not a hand-maintained table
# list, so it stays correct as migrations add or change tables.
#
# **Scope:** the app-owned base tables in `bronze`, `silver`, `gold`, `quality`,
# and `public`. Excluded on purpose:
# - `public.*` **views** (`gold_fact_streams`, `bronze_quarantine`, etc.) — these
#   are read-compat wrappers over the `gold`/`bronze` base tables (Blocker B1,
#   see `DATA_MODEL.md`); profiling them would just duplicate the base table.
# - schema `dagster` (27 tables) — Dagster's own internal run/event-log storage,
#   not application data.
#
# For narrative schema semantics (why a column exists, natural keys, the D1-D4
# decisions), see `documentation/DATA_MODEL.md` and `documentation/DATA_QUALITY.md`
# — this notebook complements those with **measured** values, not designed ones.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import pandas as pd

import _common as C

C.use_style()
DB = C.db_available()
if not DB:
    print("no database -- every cell below will report insufficient data")

SCHEMAS = ("bronze", "silver", "gold", "quality", "public")

# Columns worth profiling deeply (dtype, nulls, distinct count) vs. columns to
# just count rows for. Very wide/rare tables (Dagster-adjacent, migration
# tracking) get the light treatment.
LIGHT_PROFILE_TABLES = {"schema_migrations"}

# Cap on distinct values shown for a low-cardinality column, and on sample rows.
TOP_N_VALUES = 12
SAMPLE_ROWS = 5

pd.set_option("display.max_colwidth", 60)

# %% [markdown]
# ## All tables, by schema
#
# Base tables only (no views), pulled live from `information_schema` so this is
# never stale.

# %%
tables = pd.DataFrame()
if DB:
    tables = C.query(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema = ANY(%(schemas)s)
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
        """.replace("%(schemas)s", "ARRAY['bronze','silver','gold','quality','public']")
    )

if C.enough(tables, 1, "tables"):
    counts = tables.groupby("table_schema").size()
    print(f"total base tables : {len(tables)}")
    print(counts.to_string())
    print()
    print(tables.to_string(index=False))

# %% [markdown]
# ## Row counts per table
#
# One query per table (`count(*)` is cheap even on the ~338k-row fact table;
# nothing here approaches a size where an estimate is needed).

# %%
row_counts = pd.DataFrame()
if C.enough(tables, 1, "tables"):
    rows = []
    for _, t in tables.iterrows():
        schema, name = t["table_schema"], t["table_name"]
        n = C.query(f'SELECT count(*) AS n FROM "{schema}"."{name}"').iloc[0]["n"]
        rows.append({"schema": schema, "table": name, "rows": int(n)})
    row_counts = pd.DataFrame(rows).sort_values(["schema", "rows"], ascending=[True, False])
    print(row_counts.to_string(index=False))

    empty = row_counts[row_counts["rows"] == 0]
    if len(empty):
        print(f"\nempty tables ({len(empty)}): {list(zip(empty['schema'], empty['table']))}")

# %% [markdown]
# ## Column inventory
#
# Every column, every table: name, type, nullability, default. Also generated
# from `information_schema`, so a new migration shows up here without editing
# this notebook.

# %%
columns = pd.DataFrame()
if C.enough(tables, 1, "tables"):
    columns = C.query(
        """
        SELECT c.table_schema, c.table_name, c.ordinal_position, c.column_name,
               c.data_type, c.is_nullable, c.column_default
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = ANY(ARRAY['bronze','silver','gold','quality','public'])
          AND t.table_type = 'BASE TABLE'
        ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """
    )
    print(f"total columns across all tables : {len(columns)}")

    by_type = columns["data_type"].value_counts()
    print("\ncolumn data types, overall:")
    print(by_type.to_string())

# %% [markdown]
# ### Widest tables

# %%
if C.enough(columns, 1, "columns"):
    width = (
        columns.groupby(["table_schema", "table_name"]).size()
        .rename("columns").sort_values(ascending=False)
    )
    print(width.head(15).to_string())

# %% [markdown]
# ## Per-table profile
#
# For every table: columns (name, type, nullable), row count, and per-column
# measured stats — null share, distinct count, and either the top values
# (categorical-looking columns) or min/max (numeric/date columns). This is the
# core of the notebook; the loop is generic, driven entirely by
# `information_schema`, so it works unchanged for a table added next migration.


# %%
def _numeric_types():
    return {
        "smallint", "integer", "bigint", "numeric", "real",
        "double precision", "decimal",
    }


def _date_types():
    return {"date", "timestamp with time zone", "timestamp without time zone"}


def profile_table(schema: str, name: str, light: bool = False) -> None:
    qualified = f'"{schema}"."{name}"'
    cols = columns[
        (columns["table_schema"] == schema) & (columns["table_name"] == name)
    ]
    n_rows = int(
        row_counts.loc[
            (row_counts["schema"] == schema) & (row_counts["table"] == name), "rows"
        ].iloc[0]
    )

    print(f"\n{'=' * 70}\n{schema}.{name}  ({n_rows:,} rows, {len(cols)} columns)\n{'=' * 70}")
    print(
        cols[["column_name", "data_type", "is_nullable", "column_default"]]
        .to_string(index=False)
    )

    if n_rows == 0:
        print("(empty table -- nothing to profile)")
        return

    if light:
        print("(light profile -- skipping per-column stats for this table)")
        return

    for _, c in cols.iterrows():
        col, dtype = c["column_name"], c["data_type"]
        try:
            if dtype == "ARRAY":
                # genres / genres_enriched etc: array columns need cardinality(),
                # not a plain distinct-value profile.
                stats = C.query(
                    f'SELECT count(*) FILTER (WHERE "{col}" IS NULL) AS nulls, '
                    f'count(*) FILTER (WHERE cardinality("{col}") > 0) AS non_empty, '
                    f'avg(cardinality("{col}")) AS avg_len '
                    f"FROM {qualified}"
                ).iloc[0]
                print(
                    f"  {col:<28} array | nulls {stats['nulls']}/{n_rows} "
                    f"| non-empty {stats['non_empty']} | avg len "
                    f"{stats['avg_len']:.2f}" if stats["avg_len"] is not None
                    else f"  {col:<28} array | all null"
                )
                continue

            base = C.query(
                f'SELECT count(*) FILTER (WHERE "{col}" IS NULL) AS nulls, '
                f'count(DISTINCT "{col}") AS distinct_vals '
                f"FROM {qualified}"
            ).iloc[0]
            null_pct = base["nulls"] / n_rows if n_rows else 0
            distinct = int(base["distinct_vals"])

            if dtype in _numeric_types() or dtype in _date_types():
                mm = C.query(
                    f'SELECT min("{col}") AS lo, max("{col}") AS hi FROM {qualified}'
                ).iloc[0]
                print(
                    f"  {col:<28} {dtype:<24} nulls {null_pct:>5.1%} | "
                    f"distinct {distinct:>7,} | range [{mm['lo']}, {mm['hi']}]"
                )
            elif distinct <= TOP_N_VALUES and dtype in (
                "text", "character varying", "boolean", "USER-DEFINED",
            ):
                top = C.query(
                    f'SELECT "{col}" AS v, count(*) AS n FROM {qualified} '
                    f'GROUP BY "{col}" ORDER BY n DESC LIMIT {TOP_N_VALUES}'
                )
                vals = ", ".join(f"{r.v!r}:{r.n}" for r in top.itertuples())
                print(
                    f"  {col:<28} {dtype:<24} nulls {null_pct:>5.1%} | "
                    f"distinct {distinct:>7,} | {vals}"
                )
            else:
                print(
                    f"  {col:<28} {dtype:<24} nulls {null_pct:>5.1%} | "
                    f"distinct {distinct:>7,}"
                )
        except Exception as exc:
            print(f"  {col:<28} <profiling failed: {exc}>")


if C.enough(tables, 1, "tables"):
    for _, t in tables.iterrows():
        schema, name = t["table_schema"], t["table_name"]
        # dim_user is PII-sensitive (username = real first name) -- profiled
        # separately below with the name columns excluded, never here.
        if (schema, name) == ("gold", "dim_user"):
            continue
        if (schema, name) == ("public", "users"):
            continue
        profile_table(schema, name, light=name in LIGHT_PROFILE_TABLES)

# %% [markdown]
# ## `dim_user` / `users` — profiled without the name columns
#
# Both tables carry real first names (`username`; see `007_mask_user_names.sql`
# and the PII rule in `_common.py`). Profiled here with those columns excluded by
# name, never included generically.

# %%
if DB:
    for schema, name, exclude in (
        ("gold", "dim_user", {"username", "display_name"}),
        ("public", "users", {"username", "display_name"}),
    ):
        present = columns[
            (columns["table_schema"] == schema) & (columns["table_name"] == name)
        ]
        if not len(present):
            continue
        n_rows = int(
            row_counts.loc[
                (row_counts["schema"] == schema) & (row_counts["table"] == name), "rows"
            ].iloc[0]
        )
        safe_cols = present[~present["column_name"].isin(exclude)]
        print(f"\n{'=' * 70}\n{schema}.{name}  ({n_rows:,} rows) -- PII columns excluded\n{'=' * 70}")
        print(safe_cols[["column_name", "data_type", "is_nullable"]].to_string(index=False))
        if "is_primary" in safe_cols["column_name"].values:
            vc = C.query(f'SELECT is_primary, count(*) AS n FROM "{schema}"."{name}" GROUP BY 1')
            print(vc.to_string(index=False))

# %% [markdown]
# ## Sample rows
#
# A handful of real rows from the tables notebooks actually read, so a reader
# can see the shape rather than just the schema. `dim_user`/`users` are skipped
# here for the same PII reason as above; `fact_streams` uses the aliasing
# loader instead of a raw sample.

# %%
if DB:
    for schema, name in (
        ("bronze", "raw_streams"),
        ("silver", "streams"),
        ("gold", "dim_artist"),
        ("gold", "dim_track"),
        ("gold", "dim_time"),
        ("quality", "dq_result"),
    ):
        try:
            sample = C.query(f'SELECT * FROM "{schema}"."{name}" LIMIT {SAMPLE_ROWS}')
        except Exception as exc:
            print(f"{schema}.{name}: <sample failed: {exc}>")
            continue
        print(f"\n--- {schema}.{name} ({SAMPLE_ROWS} rows) ---")
        print(sample.to_string(index=False))

# %%
if DB:
    fact_sample = C.load_fact(limit=5)
    print("gold.fact_streams (via _common.load_fact -- aliased, PII-safe):")
    print(fact_sample.to_string(index=False))

# %% [markdown]
# ## Foreign keys and primary keys
#
# The relationships actually enforced by the database, not just implied by
# naming. Read from `information_schema` / `pg_constraint`.

# %%
if DB:
    pks = C.query(
        """
        SELECT tc.table_schema, tc.table_name,
               string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS pk_columns
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = ANY(ARRAY['bronze','silver','gold','quality','public'])
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    )
    print("primary keys:")
    print(pks.to_string(index=False))

# %%
if DB:
    fks = C.query(
        """
        SELECT
            tc.table_schema AS from_schema, tc.table_name AS from_table,
            kcu.column_name AS from_column,
            ccu.table_schema AS to_schema, ccu.table_name AS to_table,
            ccu.column_name AS to_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = ANY(ARRAY['bronze','silver','gold','quality','public'])
        ORDER BY 1, 2, 3
        """
    )
    print("foreign keys:")
    print(fks.to_string(index=False))

# %% [markdown]
# ## Table sizes on disk
#
# Bytes, not rows -- useful for spotting a table that's wide or bloated relative
# to its row count.

# %%
if DB:
    sizes = C.query(
        """
        SELECT n.nspname AS schema, c.relname AS table,
               pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
               pg_total_relation_size(c.oid) AS total_bytes
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(ARRAY['bronze','silver','gold','quality','public'])
          AND c.relkind = 'r'
        ORDER BY total_bytes DESC
        """
    )
    print(sizes.drop(columns="total_bytes").to_string(index=False))
