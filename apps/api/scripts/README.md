# Backend Scripts

This directory contains utility scripts for data management and migration.

---

## 📄 Scripts

### `build_star_schema.py`

**Purpose:** Build the warehouse end to end without Dagster — discover export
files → land bronze → dedup to silver → dims + fact (gold) → refresh MVs. Same
pipeline the Dagster `nightly_ingest_job` runs (see `documentation/INGESTION.md`).

**Usage:**
```bash
python scripts/build_star_schema.py                 # all users
python scripts/build_star_schema.py --only amit sam # one/some slugs
python scripts/build_star_schema.py --no-land       # rebuild silver/gold from bronze
```

Exit code 0 = V1 verification passed, 1 = mismatch. Idempotent — re-running
lands nothing new and rebuilds the star deterministically.

---

### `load_json_to_supabase.py` / `load_multi_user_data.py` — DEPRECATED

Both were replaced by the ingestion pipeline in Phase 12 and are now one-line
stubs that print a pointer and exit 1. Their `ip_addr`-retaining code paths were
**deleted** (they were the last DB write path for `ip_addr`). Use
`build_star_schema.py` above, or the Dagster job:

```bash
docker compose exec dagster \
    dagster job execute -j nightly_ingest_job -m dagster_project.definitions
```

---


### `compare_performance.py`

**Purpose:** Benchmark JSON files vs Supabase PostgreSQL performance

**Usage:**
```bash
python compare_performance.py
```

**What it does:**
1. Tests JSON-based data loader
2. Tests Supabase-based data loader
3. Measures execution time for 10 common queries
4. Tracks memory usage
5. Generates detailed comparison report

**Metrics Measured:**
- Initial load time
- Query execution time (10 queries)
- Memory usage
- Total workflow time

**Prerequisites:**
- Both loaders available
- Data loaded in Supabase
- Dependencies installed: `pip install tabulate psutil`

**Output:**
```
======================================================================
⚡ Spotify Insights Performance Comparison
======================================================================

1. Initial Setup
+----------+---------+-----------+
| Method   | Time    | Memory    |
| JSON     | 2.34s   | 387.42 MB |
| Supabase | 0.087s  | 3.21 MB   |
| Speedup  | 26.9x   | 120.7x    |
+----------+---------+-----------+

2. Query Performance (10 queries tested)
3. Overall Summary
4. Key Insights
5. Additional Benefits
```

**Queries Tested:**
1. Overview Stats
2. Top 10 Artists
3. Top 10 Tracks
4. Monthly Data
5. Platform Stats
6. Hourly Distribution
7. Daily Distribution
8. Skip Behavior
9. Yearly Comparison
10. Listening Streaks

---

## 🚀 Quick Start

### First-Time Setup

1. **Create Supabase Project**
   - Go to [supabase.com](https://supabase.com)
   - Create new project
   - Get URL and service_role key

2. **Set Environment Variables**
   ```bash
   # In project root .env file
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your_service_role_key
   ```

3. **Run Migrations**
   - Open Supabase SQL Editor
   - Run `apps/api/migrations/001_create_streaming_table.sql`
   - Run `apps/api/migrations/002_helper_functions.sql`

4. **Install Dependencies**
   ```bash
   pip install -r apps/api/requirements.txt
   ```

5. **Load Data**
   ```bash
   cd apps/api/scripts
   python load_json_to_supabase.py
   ```

6. **Verify Performance**
   ```bash
   python compare_performance.py
   ```

---

## 🔄 Regular Usage

### Adding New Data

When you get new Spotify data exports:

```bash
# Option 1: Full reload (recommended for now)
python load_json_to_supabase.py
# Will prompt to clear and reload

# Option 2: Incremental (TODO - to be implemented)
python load_json_to_supabase.py --incremental
```

### Refreshing Stats

After loading new data, refresh materialized views:

```bash
# Via SQL (in Supabase SQL Editor)
SELECT refresh_all_views();

# Or via Python
python -c "
import sys
from pathlib import Path
sys.path.append(str(Path('apps/api')))
from app.services.supabase_data_loader import supabase_data
supabase_data.supabase.rpc('refresh_all_views').execute()
print('✅ Views refreshed')
"
```

### Performance Testing

Run benchmark after any changes:

```bash
python compare_performance.py
```

---

## 📊 Expected Results

### Typical Performance Gains

Based on ~200K records:

| Metric | JSON Files | Supabase | Improvement |
|--------|-----------|----------|-------------|
| **Initial Load** | 2-5s | 0.1s | 20-50x |
| **Memory Usage** | 300-500 MB | 5-10 MB | 50-100x |
| **Query Time** | 0.5-2s | 0.01-0.05s | 50-200x |
| **Total Workflow** | 6-10s | 0.2-0.5s | 30-50x |

### Real-World Example

```
JSON Files:
- Load: 2.34s
- Queries: 4.23s
- Total: 6.57s
- Memory: 387 MB

Supabase:
- Connect: 0.087s
- Queries: 0.095s
- Total: 0.182s
- Memory: 3.2 MB

Speedup: 36.1x faster
Memory savings: 120x less
```

---

## 🐛 Troubleshooting

### Script: `load_json_to_supabase.py`

**Problem:** "Missing Supabase credentials"
```bash
# Check .env file
cat .env | grep SUPABASE
```

**Problem:** "Table does not exist"
```bash
# Run migrations in Supabase SQL Editor
# 1. 001_create_streaming_table.sql
# 2. 002_helper_functions.sql
```

**Problem:** "No JSON files found"
```bash
# Check data directory
ls -lh data/streaming_*.json
```

**Problem:** Slow insertion
```bash
# Increase batch size (edit script)
BATCH_SIZE = 2000  # Default is 1000
```

### Script: `compare_performance.py`

**Problem:** "Supabase test failed"
```bash
# Make sure data is loaded
python -c "
import sys
from pathlib import Path
sys.path.append(str(Path('apps/api')))
from app.services.supabase_data_loader import supabase_data
response = supabase_data.supabase.table('streaming_history').select('id').limit(1).execute()
print(f'Records in DB: {len(response.data)}')
"
```

**Problem:** Import errors
```bash
# Install missing dependencies
pip install supabase psutil tabulate
```

**Problem:** "Module not found"
```bash
# Run from correct directory
cd apps/api/scripts
python compare_performance.py
```

---

## 📝 Notes

### Data Safety

- The load script prompts before clearing existing data
- Always backup your JSON files before migration
- Supabase provides automatic backups (check your plan)

### Performance Tips

1. **Indexes are crucial** - Make sure migrations ran successfully
2. **Materialized views** - Refresh after loading new data
3. **Batch size** - Default 1000 works well, adjust if needed
4. **Connection pooling** - For production, use connection pooling

### Future Enhancements

- [ ] Incremental data loading (avoid full reload)
- [ ] Parallel batch insertion
- [ ] Data validation checks
- [ ] Automatic view refresh scheduling
- [ ] Progress bar improvements
- [ ] Resume capability for interrupted loads

---

## 🔗 Related Files

- `apps/api/migrations/` - SQL migration files
- `apps/api/app/services/data_loader.py` - Original JSON loader
- `apps/api/app/services/supabase_data_loader.py` - New Supabase loader
- `documentation/20251019_SUPABASE_MIGRATION.md` - Full migration guide
- `SUPABASE_QUICKSTART.md` - Quick setup guide

---

## 💡 Tips

### Development

```bash
# Test with small dataset first
# Edit load_json_to_supabase.py, line 35:
audio_files = sorted(DATA_DIR.glob('streaming_[0-9]*.json'))[:1]  # Only first file
```

### Production

```bash
# Use service_role key (not anon key)
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Set up automated refresh (in Supabase SQL Editor)
SELECT cron.schedule(
    'refresh-stats',
    '0 2 * * *',  # Daily at 2 AM
    'SELECT refresh_all_views();'
);
```

### Monitoring

```bash
# Check table size
SELECT pg_size_pretty(pg_total_relation_size('streaming_history'));

# Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE tablename = 'streaming_history';

# Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE query LIKE '%streaming_history%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

**Questions?** Check the full migration guide in `documentation/20251019_SUPABASE_MIGRATION.md`
