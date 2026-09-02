# EDA notebooks (Phase 13.5)

Nine read-only notebooks over the quality-gated star schema. Eight are written to
be **read later as evidence** when a Phase 14/15/16 design decision is in doubt;
one (`00_exploratory`) is general look-and-see with no decision framing. They
write nothing: no app, API, or schema change belongs in this directory.

If you do not want to boot Jupyter, read
[`documentation/EDA_FINDINGS.md`](../../../documentation/EDA_FINDINGS.md) — a
digest of every decision-support notebook's question, chart, and the number a
later phase should quote. `00_exploratory` isn't in that digest — it's charts and
distributions, not decisions.

## Which notebook answers your question

| Notebook | Question it settles | Feeds |
|---|---|---|
| `00_exploratory` | General trends, distributions, top artists/tracks, platform mix, skip behaviour, heatmaps | Nothing specific — just look-and-see |
| `01_dataset_overview` | What is in the warehouse, how much per person, and was it gate-clean? | P16 write-up (n=10 caveats); the per-user coverage floor |
| `02_temporal_behavior` | When do people listen, and where do the natural cut points fall? | **P14** `user_temporal_preferences`: `hour_bucket`, `dow_bucket`, `context_label`, `night_share` |
| `03_artist_loyalty_discovery` | How fast do people return to an artist; repeat vs new? | **P14** `user_artist_affinity` half-life + `repeat_ratio`; **P15** explorer/loyalist split |
| `04_genre_coverage` | Is genre metadata complete enough to build on? | **P14 genre-affinity kill gate** |
| `05_session_archetypes` | What does a session look like; are there real archetypes? | **P14** `_cluster_sessions` port (gap, k); **P13** Insights chart |
| `06_mood_proxy_validation` | What do "valence / energy / danceability" actually measure? | **P14** `mood_proxy_*`; **P16** limitations section |
| `07_cf_feasibility` | Can collaborative filtering work at n=10? | **P15** Model 2 expectations; the hybrid's β |
| `08_candidate_pool` | How many candidates does a recommender really have? | **P15** `candidates(user_id)`; Baseline-0 design |

Every notebook ends with a **`## Decision inputs`** cell. That cell is the
deliverable — later phases should quote it rather than re-deriving thresholds by
hand.

## Running them

1. **Start the warehouse.** From the repo root:

   ```bash
   docker compose up
   ```

   Compose publishes Postgres on host port **5433**, not 5432, to avoid clashing
   with a locally-installed Postgres.

2. **Point at it.** In `spotify-insights.env` at the repo root, or exported:

   ```
   DB_BACKEND=local
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/spotify
   ```

   Neither key is in the committed env file, so a first run needs this step.
   `_common.get_engine()` raises with these instructions if they are missing.

3. **Install the notebook dependencies:**

   ```bash
   pip install -r apps/api/requirements-dev.txt
   ```

4. **Run.** From `apps/api`:

   ```bash
   jupyter lab notebooks/
   ```

   Or headlessly, which is what CI does:

   ```bash
   jupyter nbconvert --to notebook --execute notebooks/01_dataset_overview.ipynb --stdout > /dev/null
   ```

Notebooks are independent — run them in any order. Each has a parameters cell at
the top (`USERS`, `SINCE`) if you want to narrow the scope.

## Editing them: edit the `.py`, not the `.ipynb`

Notebook JSON is painful to hand-edit and worse to review in a diff, so each
notebook's real source is a percent-format Python file under `nb_sources/`:

```bash
# edit nb_sources/02_temporal_behavior.py, then:
python notebooks/build_notebooks.py 02      # rebuild just that one
python notebooks/build_notebooks.py         # rebuild all eight
```

`build_notebooks.py` always writes **empty outputs**, so rebuilding is also the
quickest way to strip a notebook you executed locally.

## Two rules that are enforced, not just documented

**1. No real names.** `gold.dim_user.username` holds real first names —
migration `007_mask_user_names.sql` masked only `display_name`, and the masked
values look real, which is worse for a reader who cannot tell they are
synthetic. The loaders in `_common.py` never project either column; people
appear only as `user_01`..`user_10`, assigned by `alias_users()` in
`(is_primary DESC, user_id)` order. Ordering by name would leak the names
through the alias ordering itself.

**2. No committed outputs.** Outputs embed real listening history for ten
identifiable people. Committed notebooks carry none.

`tests/test_notebooks.py` enforces both, plus the presence of every
`## Decision inputs` cell. The PII checks run without a database, so they cannot
be skipped in CI. Install the stripping hook if you like belt and braces:

```bash
nbstripout --install --attributes .gitattributes
```

## Where charts go

- `outputs/eda/` — gitignored. Per-user and full-resolution charts land here.
- `documentation/assets/eda/` — committed. **Aggregate charts only**, via
  `save_fig(name, aggregate=True)`; these are the ones quoted in
  `EDA_FINDINGS.md` and the Phase 16 write-up.

## Thin data and CI

The committed CI fixture is 40 rows — far below anything these notebooks
analyse. Every analysis cell is wrapped in `_common.enough(...)`, so a fixture
(or empty) database produces a clean run of `insufficient data -- skipped`
messages and exits 0, while the real ~337k-row warehouse renders fully. That is
what makes the set CI-able in Phase 16 without pinning it to private data.

## Two conventions `_common.py` pins

Both are genuine ambiguities in the warehouse. Notebooks must not each pick
their own answer.

**Time is UTC in storage.** `gold.dim_time.hour` equals `EXTRACT(hour FROM ts)`
under the warehouse's `TimeZone=Etc/UTC`. Taken raw, the all-user histogram
peaks at 03:00–05:00, which is not a listening pattern — it is a UTC+5:30
audience's morning. Use `_common.local_hour()` / `local_iso_dow()`, which apply
`LOCAL_UTC_OFFSET_HOURS = 5.5`. That offset is an explicit assumption (the
warehouse stores no per-user timezone) and Phase 14 must revisit it if the user
base stops being single-region.

**`*_name` counts, `*_key` groups.** `fact_streams.artist_name` / `track_name`
are case-sensitive degenerate dimensions kept so aggregates reproduce the
pre-star-schema `COUNT(DISTINCT master_metadata_*_name)` semantics — "KALEO" and
"Kaleo" count as two. `artist_key` / `track_key` are normalised
(`lower(trim(...))`) and merge them. Both are returned by `load_fact()` so the
choice is explicit at the call site; each metric should say which it used.

## Related documents

- [`documentation/EDA_FINDINGS.md`](../../../documentation/EDA_FINDINGS.md) — the digest.
- [`documentation/DATA_MODEL.md`](../../../documentation/DATA_MODEL.md) — schema, natural keys, decisions D1–D4.
- [`documentation/DATA_QUALITY.md`](../../../documentation/DATA_QUALITY.md) — the 21 checks and the pipeline gate.
- [`documentation/INGESTION.md`](../../../documentation/INGESTION.md) — how the warehouse is built.
