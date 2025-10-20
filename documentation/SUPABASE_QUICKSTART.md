# Supabase Migration - Quick Start Guide

Get your Spotify stats running on Supabase in **under 10 minutes**.

---

## 📦 Prerequisites

- Python 3.8+
- Supabase account (free tier works!)
- Your Spotify streaming JSON files in `data/` directory

---

## ⚡ Quick Setup (4 Steps)

### 1️⃣ Create Supabase Project (2 min)

1. Go to [https://supabase.com](https://supabase.com) → Sign up
2. Click **New Project**
3. Choose a name, database password, and region
4. Wait for project to initialize (~1 minute)

### 2️⃣ Get Your Credentials (1 min)

1. In your Supabase project, go to **Settings** → **API**
2. Copy these values:

```bash
# Project URL
https://xxxxxxxxxxxxx.supabase.co

# API Keys (show them)
service_role key: eyJhbG... (long key)
anon key: eyJhbG... (different long key)
```

3. Create `spotify-stats.env` file in project root:

```bash
cp spotify-stats.env.example spotify-stats.env
```

4. Edit `spotify-stats.env` and add:

```env
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbG... (your service_role key)
SUPABASE_ANON_KEY=eyJhbG... (your anon key)
```

### 3️⃣ Run Database Migrations (2 min)

1. In Supabase dashboard, go to **SQL Editor**
2. Copy the contents of `apps/api/migrations/001_create_streaming_table.sql`
3. Paste into SQL Editor and click **Run**
4. Do the same for `apps/api/migrations/002_helper_functions.sql`

You should see ✅ Success messages.

### 4️⃣ Load Your Data (3 min)

```bash
# Install dependencies
pip install supabase psutil tabulate

# Load data
python apps/api/scripts/load_json_to_supabase.py
```

You'll see progress bars and should get:
```
✅ Inserted 203,456 records
✅ Migration complete!
```

---

## 🧪 Verify It Works

```bash
# Run performance comparison
python apps/api/scripts/compare_performance.py
```

You should see Supabase is **20-50x faster** than JSON files!

---

## 🚀 Use in Your App

**Update your backend imports:**

```python
# OLD
from app.services.data_loader import spotify_data

# NEW
from app.services.supabase_data_loader import supabase_data
```

That's it! All methods have the same signature.

---

## 📊 Quick Test Queries

Try these in Supabase SQL Editor:

```sql
-- How many records?
SELECT COUNT(*) FROM streaming_history;

-- Date range?
SELECT MIN(ts), MAX(ts) FROM streaming_history;

-- Top 5 artists?
SELECT * FROM get_top_artists(5);

-- Monthly stats?
SELECT * FROM monthly_stats ORDER BY month DESC LIMIT 12;
```

---

## 🆘 Common Issues

### "Missing credentials"
→ Check your `spotify-stats.env` file has `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`

### "Table does not exist"
→ Run the SQL migrations (step 3)

### "Function does not exist"
→ Run migration 002 (helper functions)

### Data not loading
→ Make sure JSON files are in `data/` directory and named `streaming_*.json`

---

## 📈 What You Get

- ⚡ **20-50x faster** queries
- 💾 **50-100x less** memory usage
- 👥 **Unlimited** concurrent users
- 🔄 **Real-time** data updates
- 📊 **Advanced** SQL analytics

---

## 📚 Full Documentation

See [documentation/20251019_SUPABASE_MIGRATION.md](documentation/20251019_SUPABASE_MIGRATION.md) for:
- Detailed architecture
- Performance benchmarks
- Troubleshooting guide
- Advanced features

---

## ✅ Checklist

- [ ] Supabase project created
- [ ] Credentials in `spotify-stats.env`
- [ ] Migrations run (both SQL files)
- [ ] Data loaded successfully
- [ ] Comparison shows speedup
- [ ] Backend updated to use Supabase

**Done?** You're ready to rock! 🎸

---

**Time spent:** ~10 minutes
**Performance gain:** 20-50x faster
**Worth it?** Absolutely! 🚀
