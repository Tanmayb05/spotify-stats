# Phase 12 — Dagster ingestion pipeline

## Context

Phases 9–11 are DONE. Phase 11 built the Medallion star schema (`bronze`/`silver`/`gold`) and repointed 3 MVs + 8 RPCs at `gold.fact_streams`, but data still gets into the DB by hand: two Supabase-only loader scripts write straight to `public.streaming_history`, and `scripts/build_star_schema.py` rebuilds the star from a one-time `bronze` backfill. Nothing is incremental, nothing is idempotent, there is no quarantine lane, and there are no ingestion metrics.

Phase 12 replaces all of that with one Dagster asset pipeline: discover → validate → land (bronze) → dedup (silver) → dims + fact (gold) → refresh MVs, with a quarantine table and per-run/per-user metrics. It also finishes the star-schema migration by repointing the last 10 analytics RPCs off `streaming_history`.

Spec: `documentation/20260901_013603_roadmap_trimmed_5features.md` § PHASE 12. Status: `UPDATE.md`. Rules: `CLAUDE.md` (Senior DE rigor; branch first; on completion update `UPDATE.md` + write the phase doc).

**Branch:** `feat/phase-12-dagster-ingestion` off `main`.

---

## Owner decisions (locked this session)

| # | Decision | Roadmap deviation? |
|---|---|---|
| 1 | `discover.py` adapts to disk as-is (flat `data/streaming_[0-9]*.json` → primary; `data/other users/<slug>/Streaming_History_Audio_*.json` → 9 users). No file moves. Exclude `data/Spotify Account Data/` and all `*Video*.json`. | Yes — roadmap said `data/raw/<user>/`, which does not exist |
| 2 | Dedup actually collapses byte-identical rows in silver; measure and report the exact delta; re-baseline. | No |
| 3 | Repoint all 10 remaining migration-006 RPCs at `gold.fact_streams` in migration 012, as a **separate commit**. | No |
| 4 | Verify gate = full 44-route API baseline diff via existing `capture_api_baseline.py` / `compare_api_baseline.py`. | No |
| 5 | Exclude video/podcast export files; report the fact-count delta as **two** numbers (scope vs dedup). | No — corrects a `seed_local_db.py` glob bug |
| 6 | DELETE migration-008's bronze backfill rows in migration 011. | Yes — destructive step, justified below |
| 7 | `reason_start`/`reason_end` enum is **warn-only**, not quarantining. | Yes — roadmap said "enum on reason_start/end" |
| 8 | `raw_streams` partitioned by **user slug only** (10 static partitions), not user×date. | Yes |

---

## Measured facts that shape the plan

**Phase 11's 71,052 includes 235 video rows.** `seed_local_db.py:108` globs `streaming_*.json`; `load_json_to_supabase.py:74` globs `streaming_[0-9]*.json` and excludes video. The local DB Phase 11 verified against carried the video file; Supabase never did.

```
primary user audio files          = 70,817
+ streaming_video_2018-2025.json  =    235
                                    71,052   ← Phase 11 V1 number
```

Expected Phase 12 fact counts — **two separate effects, never report as one blended number**:

| effect | primary | 9 others | total |
|---|---|---|---|
| video exclusion (scope) | −235 | −847 | −1,082 |
| dedup (`row_fingerprint`) | −182 | −1,222 | −1,404 |

Primary-user target: **70,817 raw → 70,635 silver/fact**.

**Real data violates none of the blocking validation rules.** Across all 10 users: `ts` non-null 100%; zero rows `ms_played > 24h` (max ~30 min); `reason_start`/`reason_end` zero nulls, 10/11 distinct values. **The quarantine lane will be empty on real data** — so the malformed fixture is the only thing that exercises it and must be committed, not poked in by hand.

Observed enum values (for the warn-only check):
- `reason_start`: `trackdone, fwdbtn, clickrow, appload, playbtn, backbtn, remote, trackerror, unknown, switched-to-audio`
- `reason_end`: `trackdone, fwdbtn, endplay, logout, unexpected-exit-while-paused, backbtn, remote, unknown, trackerror, unexpected-exit, switched-to-video`

---

## Idempotency model — stated explicitly

Two keys, two enforcement points:

| level | key | enforced where | prevents |
|---|---|---|---|
| **file** | `(user_id, file_hash)` | DB `UNIQUE` on `bronze.ingest_state` | re-landing an already-landed file |
| **row** | `(user_id, row_fingerprint)` | **app logic** in `dedup.py` (`ROW_NUMBER`), *not* a DB constraint | export-internal byte-identical dupes |

The row key is deliberately not a unique constraint: `bronze` must retain dupes verbatim ("keep all in bronze"), and a constraint on `silver` would make the rebuild *fail* on a legitimate dupe instead of *counting* it. Silver's idempotency comes from being deterministically rebuilt from bronze.

**Incremental where it pays, full-rebuild where it is safer:** bronze landing is incremental and append-only; silver and gold are rebuilt in full every run (existing TRUNCATE semantics kept). Rationale — dedup by `ROW_NUMBER` over `(user_id, row_fingerprint)` is inherently whole-partition; `dim_time`/`dim_album` are cheap derived tables; and a full rebuild is *provably* deterministic from bronze, which is what makes the API baseline diff meaningful. Whole silver→gold rebuild stays in **one** `engine.begin()`, so a mid-rebuild failure leaves the previous star serving the app. Document this in `INGESTION.md` — a reviewer will otherwise read TRUNCATE as an accident.

---

## Commit 1 — migration 011

**File:** `apps/api/migrations/011_ingest_state_and_runs.sql`

- `ALTER TABLE bronze.raw_streams ADD COLUMN IF NOT EXISTS row_fingerprint CHAR(64)` + index `(user_id, row_fingerprint)`. **No SQL backfill expression** — under decision 6 the legacy rows are deleted, so there is never a second definition of the fingerprint to drift from `normalize.row_fingerprint`.
- `ALTER TABLE silver.streams ADD COLUMN IF NOT EXISTS row_fingerprint CHAR(64)` (no unique constraint).
- `bronze.ingest_state(state_id, user_id FK, source_file, file_hash CHAR(64), max_ts, min_ts, rows_in_file, rows_landed, ingested_at, run_id, UNIQUE(user_id, file_hash))`
- `bronze.quarantine(quarantine_id, _ingest_id BIGINT NULL FK→raw_streams ON DELETE SET NULL, run_id, user_id, source_file, source_index, rule NOT NULL, detail, _raw JSONB NOT NULL, quarantined_at)` — `_ingest_id` is **nullable** because rows are quarantined *pre*-landing (an unparseable `ts` has no bronze row to point at); the roadmap's column list assumed post-landing only.
- `bronze.ingest_run(run_id UUID PK, started_at, finished_at, users, files_seen, files_new, rows_raw, rows_valid, rows_quarantined, rows_landed, dups_dropped, rows_silver, rows_fact, track_match_rate NUMERIC(5,4), artist_match_rate, unmatched_tracks, unmatched_artists, status CHECK IN ('running','success','failed','partial'), dagster_run_id, detail JSONB)`
- `bronze.ingest_run_user(run_id FK, user_id FK, files_seen, files_new, rows_raw, rows_valid, rows_quarantined, rows_landed, dups_dropped, rows_silver, max_ts, PK(run_id,user_id))`
- Four `public.bronze_*` compat views (`bronze_ingest_run`, `bronze_ingest_run_user`, `bronze_quarantine`, `bronze_ingest_state`) — same pattern as `009:241-247`, because `backends.py`'s `_IDENT_RE` rejects dotted schema names (Blocker B1). Phase 13's `/api/health/data` needs these.
- **Terminal destructive step**, with a comment explaining why:
  ```sql
  DELETE FROM bronze.raw_streams WHERE _source_file = 'phase11_backfill:streaming_history';
  ```
  Safe: `silver.streams._ingest_id` is a nullable FK and silver is TRUNCATEd every run; `gold.fact_streams._ingest_id` is a plain `BIGINT` with **no** FK (`009:157`). Between the DELETE and the first job run the app serves the untouched old gold tables — no downtime.

**Verify:** `python db/migrate.py --dry-run` then apply; `--status` shows 011; second run is a no-op; backfill rows gone.

---

## Commit 2 — `app/ingest/` modules + `build_star_schema.py` refactor

All under `apps/api/app/ingest/`.

### `discover.py` (new)
```python
@dataclass(frozen=True)
class DiscoveredFile:
    path: Path; rel_path: str; slug: str; display_name: str
    file_hash: str; size_bytes: int; is_primary: bool

USER_SLUGS: dict[str, str]        # moved verbatim from load_multi_user_data.py:66-76
PRIMARY_SLUG = "primary"

def data_root() -> Path
def file_sha256(path: Path, chunk: int = 1 << 20) -> str
def discover_files(root: Path | None = None, only: Sequence[str] | None = None) -> list[DiscoveredFile]
```
Primary glob `streaming_[0-9]*.json` (reuses `load_json_to_supabase.py:74`'s pattern, already video-excluding); others `(root/"other users"/slug).glob("Streaming_History_Audio_*.json")`. Belt-and-braces exclude on `*Video*`/`*video*` and anything under `data/Spotify Account Data/`. Deterministic sort by `(slug, rel_path)`.

### `landing.py` (new)
```python
@dataclass
class LandingResult:
    slug: str; user_id: UUID; rel_path: str; file_hash: str
    skipped_reason: str | None            # 'file_hash_seen' | None
    rows_in_file: int; rows_landed: int; rows_quarantined: int
    rows_below_watermark: int
    min_ts: datetime | None; max_ts: datetime | None

def get_or_create_user(conn, slug, display_name, is_primary) -> UUID
def read_export(path: Path) -> list[dict]          # json.load, falls back to salvage_json_array on JSONDecodeError
def user_watermark(conn, user_id: UUID) -> datetime | None    # MAX(max_ts) over ingest_state
def land_file(conn, df, user_id, run_id, watermark, *, force=False) -> LandingResult
```

**Two-tier watermark:**
1. *File skip* — `SELECT 1 FROM bronze.ingest_state WHERE user_id=? AND file_hash=?`. Hit → return immediately, no parse. This is what makes "re-run ⇒ `files_new=0, rows_landed=0`" true. Keying on `file_hash` not `source_file` means a renamed-but-identical file is correctly skipped and a same-named-but-changed file is correctly reprocessed.
2. *Row incremental on superset re-export* — land rows with `ts >= watermark` whose `row_fingerprint` is not already present for that user in bronze (one indexed batch lookup against the 011 index). Use `>=` **plus** the fingerprint anti-join, not strict `>`: strict `>` loses ties when two plays share the watermark second. This also makes a partially-failed run resumable without duplication. **Roadmap deviation to log:** bronze's incremental path is no longer "append everything verbatim" — it stays append-only (never UPDATE/DELETE) and a file's *first* landing still appends every row including intra-file dupes.
3. `_raw` is the row dict **with `ip_addr` popped** — the V10 hard constraint, and the single most important line in the module, because the script being replaced (`load_json_to_supabase.py:111`) kept it. Assert in a test.
4. Batch inserts of 5,000. On success, upsert `ingest_state` `ON CONFLICT (user_id, file_hash) DO UPDATE` so a mid-file crash converges on re-run.

### `schemas.py` + `validate.py` (new)
```python
def validate_rows(rows, *, source_file, user_id, run_id) -> ValidationOutcome   # .valid / .quarantined
def write_quarantine(conn, rows) -> int
```
Pandera `DataFrameSchema`, `lazy=True`, `strict=False` (real exports have 23 keys, fixture 17 — never reject on column set), `coerce=False`. Runs **pre-landing** on parsed dicts via pandas (already a runtime dep). Map `failure_cases.check → rule`, `.index → source_index`, `.failure_case → detail`.

Rule vocabulary written to `bronze.quarantine.rule`:

| rule | condition | severity |
|---|---|---|
| `ts_missing` | `ts` absent/empty | blocking |
| `ts_unparseable` | `to_utc(ts)` is `None` | blocking |
| `ms_played_range` | `< 0` or `> 86_400_000` | blocking |
| `music_row_track_name` | `spotify_track_uri` present but track name null/blank | blocking (dataframe-level check — handle the differing `failure_cases` shape) |
| `platform_type` | `platform` present and not `str` | blocking |
| `row_not_a_dict` | array element not a JSON object | blocking, caught in `read_export` pre-Pandera |
| `reason_start_enum` | not in the 10 observed | **warn** → land, count in `ingest_run.detail` |
| `reason_end_enum` | not in the 11 observed | **warn** → land, count in `ingest_run.detail` |

### `normalize.py` — unchanged
Gets its first production callers (`to_utc`, `coerce_ms_played`, `coerce_bool`, `row_fingerprint`). Only edit: strip the now-stale "not yet used / Phase 12's dedup.py consumes it" docstring wording.

### `dedup.py` (new)
```python
DEDUP_SELECT_SQL: str
def build_silver(conn, *, full_rebuild: bool = True) -> DedupStats   # rows_in, rows_out, dups_dropped, per_user
def dedup_report(conn) -> list[dict]
```
Tie-break rule (roadmap requires it documented): **keep the lowest `_ingest_id`** — the first-landed occurrence; deterministic and stable because `_ingest_id` is a BIGSERIAL assigned in file order.
```sql
INSERT INTO silver.streams (...)
SELECT ... FROM (
  SELECT b.*, ROW_NUMBER() OVER (PARTITION BY b.user_id, b.row_fingerprint
                                 ORDER BY b._ingest_id) AS rn
  FROM bronze.raw_streams b WHERE b.ts IS NOT NULL
) d WHERE d.rn = 1
```

### `enrich.py` (new)
```python
def build_dims(conn) -> dict[str, int]
def build_fact(conn) -> int
def match_rates(conn) -> MatchRates
```
Holds the "unmatched rows still flow" contract: the existing `ON CONFLICT DO NOTHING` stub-inserts guarantee every silver `artist_key`/`track_key` has an FK target, so no fact row is ever dropped. `match_rates` measures against `audio_source='enriched'` — the meaningful *enrichment* rate, not the trivially-100% FK-presence rate `report_match_rates()` prints today. Report both; `ingest_run.{track,artist}_match_rate` get the enrichment rate.

### `metrics.py` (new)
```python
def start_run(conn, dagster_run_id=None) -> UUID
def record_user(conn, run_id, user_id, **counters) -> None
def bump_run(conn, run_id, **counters) -> None      # additive UPDATE ... SET x = x + ?
def finish_run(conn, run_id, status, **finals) -> None
def latest_run(conn) -> dict | None
```
**Metrics writes use their own short-lived connection**, outside the pipeline transaction — otherwise a failed run rolls back its own failure record and `ingest_run` never shows a `failed` row.

### `build_star_schema.py` refactor
Move its 7 stage functions into `app/ingest/dedup.py` (stage 1, now with the dedup window) and `app/ingest/enrich.py` (stages 2–7 + `report_match_rates` + `verify_v1`); leave the script a ~40-line wrapper preserving its CLI/exit-code contract.

Not option (a) import-the-script: `scripts/` has no `__init__.py` and `build_star_schema.py` does a module-scope `sys.path.insert`. Not (c) duplicate: Phase 11's V4 gate already caught "a stale container copy of `build_star_schema.py` missing new columns" — one definition.

**`verify_v1` must be rewritten in this commit**, not left to fail: its `count(streaming_history) == count(fact_streams)` assertion becomes false the moment dedup lands. Replace with
- V1a `count(bronze) − dups_dropped == count(silver)` per user
- V1b `count(silver) == count(gold.fact_streams)` per user, exact
- V1c `count(fact_streams) == <disk-derived constant>` per user (70,635 primary)

**Verify:** `pytest apps/api/tests -q` green (35 existing + new); `python scripts/build_star_schema.py` still runs standalone with the same stage log; record the new fact count.

---

## Commit 3 — Dagster project + compose service

**`apps/api/dagster_project/{__init__,definitions,assets,resources,jobs,schedules}.py`** + `apps/api/pyproject.toml` with `[tool.dagster] module_name = "dagster_project.definitions"` (none exists today).

### `resources.py`
```python
class PostgresResource(ConfigurableResource):
    database_url: str | None = None
    @cached_property
    def engine(self) -> Engine: return make_engine(self.database_url)   # NOT get_engine() — lru_cached, wrong for a daemon
```
`make_engine(None)` already falls back to `settings.database_url`, which already reads repo-root `spotify-insights.env`, so bare `dagster dev` works unconfigured. Second resource `DataRootResource(path=EnvVar.optional("INGEST_DATA_ROOT"))` defaulting to `<repo>/data`.

### `assets.py`
```
raw_streams (StaticPartitionsDefinition: 10 user slugs)
  ├─→ quarantine        (unpartitioned)
  └─→ silver_streams    (unpartitioned, dedup, full rebuild)
        └─→ gold_star @multi_asset → dim_user, dim_time, dim_artist, dim_track, dim_album, fact_streams
              └─→ refreshed_views
```

**Partitioning (decision 8).** Static, by user slug only. Files are physically per-user and a user can be re-ingested independently (the old `--only` flag). A user×daily grid over 2018-2025 would be ~28,000 near-empty partitions, each re-reading the same multi-year 60 MB file. Downstream assets unpartitioned — honest, since the silver rebuild is global by construction.

**Transaction shape.** Assets are separate calls and cannot share one `engine.begin()`. Use `@multi_asset` for the gold rebuild so it is one transaction *and* six named assets in the lineage graph:
```python
@multi_asset(outs={"dim_user": AssetOut(), ..., "fact_streams": AssetOut()},
             deps=[silver_streams], group_name="gold")
def gold_star(context, postgres):
    with postgres.begin() as conn:
        conn.execute(text("TRUNCATE TABLE gold.fact_streams RESTART IDENTITY"))
        yield Output(enrich.stage_dim_user(conn), "dim_user")
        ...
        yield Output(enrich.stage_fact_streams(conn), "fact_streams")
```
Every asset returns `MaterializeResult(metadata=...)` so counters show in the Dagster UI *and* land in `ingest_run`.

`jobs.py`: `define_asset_job("nightly_ingest_job", selection=AssetSelection.all())`.
`schedules.py`: cron `0 3 * * *`, `execution_timezone="UTC"`, `default_status=DefaultScheduleStatus.STOPPED` (do not auto-start a schedule in a portfolio repo).

### `docker-compose.yml` — `dagster` service
Builds from `apps/api/Dockerfile` (repo-root context). `command: dagster dev -h 0.0.0.0 -p 3000 -m dagster_project.definitions`. Port `3000:3000`. Env: `DB_BACKEND=local`, `DATABASE_URL`, `DAGSTER_HOME=/opt/dagster/home`, `INGEST_DATA_ROOT=/app/data`. Volumes `./data:/app/data:ro` + named `dagster_home`. `depends_on: db (service_healthy), api (service_started)` — the api container runs `db/migrate.py`, so do **not** duplicate the migration call here (two containers racing `migrate.py` on a cold `up` is a real failure).

- `DAGSTER_HOME` is required — `dagster dev` refuses to start without it. Named volume so run history survives `down`.
- Add `dagster-postgres==1.13.20` to requirements (**not currently pinned**) + `dagster.yaml` pointing run/event-log/schedule storage at the same Postgres with `schema: dagster` — keeps ~8 Dagster tables out of `public` next to `streaming_history` and the 7 `gold_*` compat views.
- **Move `dagster` + `pandera` from `requirements-dev.txt` to `requirements.txt`** — from this phase forward Dagster is how the app's data gets built, not a dev nicety. Confirm the api Dockerfile installs whichever file they end up in.
- No separate `dagster-daemon` service — `dagster dev` runs webserver + daemon in one process.
- Update the compose header comment, `README.md`, and `start.sh` port table (real ports: web 3010, api 3011, dagster 3000 — the roadmap's "5173" is wrong).

**Verify:** `dagster job execute -j nightly_ingest_job` green; immediate re-run ⇒ `files_new=0, rows_landed=0`; malformed-fixture test green; `docker compose up` → lineage graph at localhost:3000.

---

## Commit 4 — migration 012, RPC repoint (separate, per decision 3)

**File:** `apps/api/migrations/012_repoint_analytics_functions.sql`. The 10 functions still reading `streaming_history` (from `006_analytics_functions.sql`):

`get_discovery_timeline` (:236), `get_artist_loyalty` (:269), `get_artist_obsessions` (:338), `get_reflective_insights` (:383), `get_weekend_weekday_comparison` (:478), `get_most_repeated_tracks` (:518), `get_monthly_diversity` (:550), `get_listening_heatmap` (:579), `get_milestones_list` (:622), `get_flashback` (:771).

Not on the list — already indirectly repointed via `_mood_rows`, do not double-count: `get_mood_summary`, `get_mood_contexts`, `get_mood_monthly`.

**Mechanical rule (this is R1, the highest-severity risk):** copy each body verbatim from 006, change **only** `FROM streaming_history` → `FROM gold.fact_streams` and the three column names —
`master_metadata_album_artist_name → fs.artist_name`, `master_metadata_track_name → fs.track_name`, `master_metadata_album_album_name → fs.album_name`.
**Never** map to `fs.artist_key`. `gold.fact_streams` carries those denormalized case-sensitive columns precisely so 010 could reproduce `COUNT(DISTINCT master_metadata_*_name)` bit-for-bit; the dataset has 4 rows differing only by artist-name casing ("KALEO"/"Kaleo", "LEN"/"Len"). Grouping by `artist_key` silently merges them and moves `new_artists_count` and diversity numbers. Blast radius: `get_discovery_timeline`, `get_artist_loyalty`, `get_artist_obsessions`, `get_monthly_diversity`, `get_most_repeated_tracks`. Imitate `010_mvs_on_star.sql:139` exactly, including the `DROP FUNCTION IF EXISTS` with exact signature before each (Blocker B2).

**Verify:** this commit must change **zero** numbers — the baseline diff against `post_phase12` must be byte-clean. That is the whole reason it is separate from the pipeline commit, which *does* change numbers.

---

## Commit 5 — docs + legacy loader deprecation

`documentation/INGESTION.md`; `UPDATE.md` row → DONE + log entry (record all 8 deviations); `documentation/YYYYMMDD_HHMMSS_phase_12_dagster_ingestion.md` per the CLAUDE.md schema.

Turn `load_json_to_supabase.py` and `load_multi_user_data.py` into thin deprecated wrappers printing a notice pointing at the Dagster job. While there: **delete the blocking `input()` at `load_json_to_supabase.py:297` and its `ip_addr`-retaining `transform_record`** — that script is the only remaining code path that would write `ip_addr`, and leaving it live as "deprecated" is a PII footgun. Both import `USER_SLUGS` from `discover.py`.

`INGESTION.md` must state that `public.streaming_history` is **frozen legacy**: after migration 012 it has zero readers. The pipeline never writes it (maintaining a second pre-dedup, video-inclusive grain forever is not worth it). Leave it populated-but-stale for one phase — Phase 13's DQ suite may want it as a cross-check; dropping a table is not this phase's job.

---

## Fixtures to add

| file | purpose |
|---|---|
| `data/fixtures/malformed_streaming_history.json` | ~7 rows, one per blocking rule + one clean control. Makes the roadmap's "inject a malformed row" a repeatable pytest assertion (6 quarantine rows, 6 distinct rules, 1 landed), not a manual poke. Required, because real data trips none of these rules. |
| `data/fixtures/sample_streaming_history_full.json` | ~12 rows with **all 23 real-export keys**. The existing fixture has 17 and lacks `ip_addr`, `offline_timestamp`, and all 4 `audiobook_*` — so a pipeline green on it alone has never executed the ip_addr-strip line or the `audiobook_title IS NULL` branch of `is_music`. Include: a row with `ip_addr: "203.0.113.1"` (RFC 5737 TEST-NET, obviously synthetic, safe to commit), an audiobook row, a podcast row, and a byte-identical dupe pair. **The highest-value test in the phase.** |

---

## Verification

| # | gate | how | pass criterion |
|---|---|---|---|
| V1 | job green | `dagster job execute -j nightly_ingest_job -m dagster_project.definitions` | exit 0, all assets materialized |
| V2 | idempotent | immediately re-run V1 | `files_new=0`, `rows_landed=0`; bronze count identical before/after |
| V3 | quarantine | `pytest apps/api/tests/test_validate.py` + run against the malformed fixture | 6 quarantine rows, 6 distinct `rule`s, 1 landed |
| V4 | metrics sane | latest `bronze.ingest_run` | `rows_raw = rows_valid + rows_quarantined`; `rows_silver = rows_landed − dups_dropped`; `0 ≤ match_rate ≤ 1`; `status='success'` |
| V5 | dedup delta | per-user bronze/silver/fact counts, before + after | reported as **two** numbers (scope vs dedup); `dups_dropped` exactly equals `bronze − silver` for `ts IS NOT NULL` |
| V6 | API baseline | `capture_api_baseline.py` before commit 2; `compare_api_baseline.py` after commits 2, 3, 4 | see below |
| V7 | MV freshness | `refreshed_views` asset assertion | `sum(monthly_stats.stream_count) == count(fact_streams)` for primary |
| V8 | no PII | `SELECT count(*) FROM bronze.raw_streams WHERE _raw ? 'ip_addr'` | **0** |
| V9 | migration replay | `db/migrate.py` twice from a fresh DB | idempotent, 12/12 applied |
| V10 | RPC repoint | `SELECT proname FROM pg_proc WHERE prosrc ILIKE '%streaming_history%'` | none of the 10 remain |

**V5 measurement query** (run before and after):
```sql
SELECT u.username,
       (SELECT count(*) FROM bronze.raw_streams b WHERE b.user_id=u.id) AS bronze,
       (SELECT count(*) FROM silver.streams   s WHERE s.user_id=u.id) AS silver,
       (SELECT count(*) FROM gold.fact_streams f WHERE f.user_id=u.id) AS fact
FROM users u ORDER BY u.username;
```
Phase doc must say: "fact_streams dropped by N. Of that, X is **scope** (video/podcast export no longer ingested — `seed_local_db.py`'s glob was including it; the Supabase loader never did) and Y is **dedup** (`row_fingerprint` collapse, keep-lowest-`_ingest_id`)."

**V6 procedure.** The diff after commits 2/3 will be **non-clean, and that is correct** — 1,404 dupes + 1,082 video rows are gone. Expected to move: `/api/stats/overview`, `/api/stats/top-*`, `/api/time/monthly`, anything counting rows. Expected *not* to move: `/api/stats/date-range` — **but verify**, since a video row could be the global min or max ts, in which case it moves too and must be explained rather than waved through. Triage every diffed path into "explained by the −2,486 rows" or "unexplained"; **any unexplained diff blocks the phase**. Then re-baseline to `outputs/baseline/post_phase12` and note in `UPDATE.md` that `pre_phase11` is superseded. After commit 4 the diff against `post_phase12` must be **byte-clean** — the strongest signal in the phase, proving the 10 repointed functions reproduce their `streaming_history` semantics on `gold.fact_streams`.

---

## Risks

- **R1 — casing trap on 10 more functions.** Highest severity. Mitigation is the mechanical repoint rule in commit 4; commit 4's clean baseline diff is the detector, but write it right the first time.
- **R2 — fixture/real schema divergence.** Mitigated by `sample_streaming_history_full.json` above.
- **R3 — bronze double-landing.** Resolved by the migration-011 DELETE (decision 6). Rejected alternative — synthesizing `ingest_state` rows — needs a fake `file_hash` that matches no real file, so the next real file still lands in full: same doubling one step later, plus bronze provenance becomes a lie.
- **R4 — MV staleness.** Phase 11 shipped this bug once. `refreshed_views` must be a real terminal asset inside `AssetSelection.all()`, with the V7 assertion converting the bug into a hard gate. `refresh_all_views()` must run in its **own** transaction after the rebuild commits — a `REFRESH MATERIALIZED VIEW` inside the TRUNCATE/INSERT transaction sees pre-commit state.
- **R5 — `streaming_history` writes.** The pipeline never writes it. Consequence: `verify_v1` must be rewritten in commit 2 (see above), not left to fail.
- **R6 — migrate.py race.** `depends_on: api (service_started)` does not wait for migrations to finish. If flaky, add an api healthcheck on `/health` and switch to `service_healthy`.

---

## Files

**New:** `apps/api/migrations/011_ingest_state_and_runs.sql`, `012_repoint_analytics_functions.sql`; `apps/api/app/ingest/{discover,landing,validate,schemas,dedup,enrich,metrics}.py`; `apps/api/dagster_project/{__init__,definitions,assets,resources,jobs,schedules}.py`; `apps/api/pyproject.toml`; `apps/api/dagster_home/dagster.yaml`; `apps/api/tests/test_{discover,landing,validate,dedup}.py`; `data/fixtures/{malformed_streaming_history,sample_streaming_history_full}.json`; `documentation/INGESTION.md`; `documentation/<ts>_phase_12_dagster_ingestion.md`.

**Modified:** `apps/api/scripts/build_star_schema.py` (→ wrapper), `load_json_to_supabase.py` + `load_multi_user_data.py` (→ deprecated wrappers, PII path deleted), `apps/api/app/ingest/normalize.py` (docstrings only), `docker-compose.yml`, `apps/api/requirements.txt` + `requirements-dev.txt`, `apps/api/Dockerfile` (if needed), `README.md`, `start.sh`, `UPDATE.md`.
