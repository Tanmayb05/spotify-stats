# Supabase Migration Checklist

Copy this checklist and check off items as you complete them.

---

## 📋 Pre-Migration

- [ ] Read [SUPABASE_QUICKSTART.md](SUPABASE_QUICKSTART.md)
- [ ] Read [documentation/20251019_SUPABASE_MIGRATION.md](documentation/20251019_SUPABASE_MIGRATION.md)
- [ ] Backup your JSON files (optional but recommended)
- [ ] Have Python 3.8+ installed
- [ ] Have ~200K streaming records in `data/streaming_*.json` files

---

## 🏗️ Supabase Setup (10 min)

### Create Project
- [ ] Go to [supabase.com](https://supabase.com)
- [ ] Sign up / Log in
- [ ] Click "New Project"
- [ ] Enter project name
- [ ] Choose database password
- [ ] Select region (closest to you)
- [ ] Wait for initialization (~1 min)

### Get Credentials
- [ ] Go to Settings → API
- [ ] Copy Project URL → `https://xxxxx.supabase.co`
- [ ] Copy service_role key → `eyJhbG...`
- [ ] Copy anon key → `eyJhbG...`

### Update spotify-stats.env File
- [ ] Run: `cp spotify-stats.env.example spotify-stats.env`
- [ ] Edit `spotify-stats.env` file
- [ ] Add `SUPABASE_URL=https://xxxxx.supabase.co`
- [ ] Add `SUPABASE_SERVICE_KEY=eyJhbG...` (service_role key)
- [ ] Add `SUPABASE_ANON_KEY=eyJhbG...` (anon key)
- [ ] Save file

---

## 🗄️ Database Setup (5 min)

### Run Migrations
- [ ] Open Supabase dashboard
- [ ] Go to SQL Editor
- [ ] Open `apps/api/migrations/001_create_streaming_table.sql`
- [ ] Copy entire contents
- [ ] Paste into SQL Editor
- [ ] Click "Run" button
- [ ] Verify ✅ Success message

- [ ] Open `apps/api/migrations/002_helper_functions.sql`
- [ ] Copy entire contents
- [ ] Paste into SQL Editor
- [ ] Click "Run" button
- [ ] Verify ✅ Success message

### Verify Tables
- [ ] In SQL Editor, run: `SELECT COUNT(*) FROM streaming_history;`
- [ ] Should see: `0` (table exists but empty)
- [ ] Run: `\df get_*` to see functions
- [ ] Should see list of functions

---

## 🐍 Python Setup (2 min)

### Install Dependencies
- [ ] Run: `pip install -r requirements.txt`
- [ ] Verify: `pip list | grep supabase`
- [ ] Verify: `pip list | grep psutil`
- [ ] Verify: `pip list | grep tabulate`

### Test Connection
```bash
python -c "
import sys
sys.path.append('apps/api')
from app.services.supabase_data_loader import SupabaseDataLoader
loader = SupabaseDataLoader()
print('✅ Connection successful!')
"
```
- [ ] See: `✅ Connection successful!`

---

## 📥 Data Migration (5-10 min)

### Load Data
- [ ] Run: `python apps/api/scripts/load_json_to_supabase.py`
- [ ] Watch progress bars
- [ ] Wait for completion
- [ ] Verify success message

Expected output:
```
✅ Total records loaded: 203,456
✅ Inserted 203,456 records
✅ Verification complete
✅ Migration complete!
```

### Verify Data
- [ ] In Supabase SQL Editor, run: `SELECT COUNT(*) FROM streaming_history;`
- [ ] Should see your record count (e.g., `203,456`)
- [ ] Run: `SELECT MIN(ts), MAX(ts) FROM streaming_history;`
- [ ] Should see your date range
- [ ] Run: `SELECT * FROM get_top_artists(5);`
- [ ] Should see your top 5 artists

---

## ⚡ Performance Testing (2 min)

### Run Comparison
- [ ] Run: `python apps/api/scripts/compare_performance.py`
- [ ] Wait for both tests to complete
- [ ] Review comparison table

Expected results:
- [ ] Initial setup: 20-50x faster
- [ ] Memory usage: 50-100x less
- [ ] Queries: 50-200x faster
- [ ] Overall: 30-50x faster

### Verify Speedup
- [ ] Supabase should be significantly faster
- [ ] If not, check indexes: `SELECT * FROM pg_indexes WHERE tablename = 'streaming_history';`

---

## 🔄 Backend Integration

### Update Code
- [ ] Open your FastAPI routes or backend code
- [ ] Find: `from app.services.data_loader import spotify_data`
- [ ] Replace with: `from app.services.supabase_data_loader import supabase_data`
- [ ] Update variable name if needed

**Or use environment variable:**
```python
import os
if os.getenv('USE_SUPABASE', 'true').lower() == 'true':
    from app.services.supabase_data_loader import supabase_data as loader
else:
    from app.services.data_loader import spotify_data as loader
```

### Test Endpoints
- [ ] Start your backend: `uvicorn app.main:app --reload`
- [ ] Test: `/api/stats/overview`
- [ ] Test: `/api/top/artists?limit=10`
- [ ] Test: `/api/top/tracks?limit=10`
- [ ] Test: `/api/time/monthly`
- [ ] Test: `/api/platforms`
- [ ] All should work instantly!

---

## ✅ Final Verification

### Data Integrity
- [ ] Compare JSON vs Supabase results side-by-side
- [ ] Top artists match?
- [ ] Top tracks match?
- [ ] Total streams match?
- [ ] Date ranges match?

### Performance
- [ ] API responses < 100ms?
- [ ] No memory issues?
- [ ] Multiple concurrent requests work?

### Documentation
- [ ] Bookmark [documentation/20251019_SUPABASE_MIGRATION.md](documentation/20251019_SUPABASE_MIGRATION.md)
- [ ] Note any customizations you made
- [ ] Document any issues encountered

---

## 🎉 Celebration

- [ ] You just made your app 30-50x faster!
- [ ] You reduced memory usage by 50-100x!
- [ ] You're now using a production-grade database!
- [ ] Pat yourself on the back! 🎊

---

## 📝 Optional Enhancements

### Scheduled View Refresh
```sql
-- In Supabase SQL Editor
CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.schedule(
    'refresh-stats',
    '0 2 * * *',  -- Daily at 2 AM
    'SELECT refresh_all_views();'
);
```
- [ ] Enable pg_cron extension
- [ ] Schedule daily refresh

### Monitoring
```sql
-- Add these queries to your monitoring
SELECT pg_size_pretty(pg_total_relation_size('streaming_history'));
SELECT * FROM pg_stat_user_indexes WHERE tablename = 'streaming_history';
```
- [ ] Check table size periodically
- [ ] Monitor index usage

### Backups
- [ ] Enable automatic backups in Supabase settings
- [ ] Set retention period
- [ ] Test restore process

---

## 🐛 Troubleshooting

If something goes wrong, check:

1. **Credentials**: `cat spotify-stats.env | grep SUPABASE`
2. **Migrations**: Re-run SQL files in Supabase SQL Editor
3. **Dependencies**: `pip install -r requirements.txt`
4. **Data**: `SELECT COUNT(*) FROM streaming_history;` in SQL Editor
5. **Functions**: `\df get_*` in SQL Editor

For detailed troubleshooting, see [documentation/20251019_SUPABASE_MIGRATION.md](documentation/20251019_SUPABASE_MIGRATION.md#-troubleshooting)

---

## 📞 Support

- **Supabase Docs**: [https://supabase.com/docs](https://supabase.com/docs)
- **PostgreSQL Docs**: [https://www.postgresql.org/docs/](https://www.postgresql.org/docs/)
- **Migration Guide**: [documentation/20251019_SUPABASE_MIGRATION.md](documentation/20251019_SUPABASE_MIGRATION.md)

---

**Total Time**: ~30 minutes
**Performance Gain**: 30-50x faster
**Worth It**: Absolutely! 🚀

---

## ✨ After Migration

Your app now has:
- ✅ Professional database backend
- ✅ Lightning-fast queries
- ✅ Minimal memory usage
- ✅ Scalable architecture
- ✅ Real-time capabilities
- ✅ Industry best practices

**Congratulations on completing the migration!** 🎉
