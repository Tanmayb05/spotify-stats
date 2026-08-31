# Multi-User Spotify Streaming Data Storage Design

**Date:** 2025-01-27  
**Status:** Design Document  
**Purpose:** Optimal database schema for storing streaming history from multiple users

---

## 1. JSON Data Structure Analysis

### Current Structure (Single User)

Your `streaming_*.json` files contain records with the following structure:

```json
{
  "ts": "2024-08-06T10:02:32Z",                    // ISO 8601 timestamp (UTC)
  "platform": "ios",                                // Platform identifier
  "ms_played": 337613,                              // Milliseconds played
  "conn_country": "IN",                             // ISO country code
  "ip_addr": "REDACTED_IP",                      // IP address
  "master_metadata_track_name": "Smoke on the Water",
  "master_metadata_album_artist_name": "Deep Purple",
  "master_metadata_album_album_name": "Deepest Purple: The Very Best of Deep Purple",
  "spotify_track_uri": "spotify:track:0XHWClSz0v6RIaRSGqJH3X",
  "episode_name": null,                             // Podcast episode (nullable)
  "episode_show_name": null,                        // Podcast show (nullable)
  "spotify_episode_uri": null,                      // Podcast URI (nullable)
  "audiobook_title": null,                          // Audiobook title (nullable)
  "audiobook_uri": null,                            // Audiobook URI (nullable)
  "audiobook_chapter_uri": null,                    // Audiobook chapter URI (nullable)
  "audiobook_chapter_title": null,                  // Audiobook chapter title (nullable)
  "reason_start": "trackdone",                      // Why track started
  "reason_end": "trackdone",                        // Why track ended
  "shuffle": true,                                  // Shuffle mode
  "skipped": false,                                 // Track skipped
  "offline": false,                                 // Offline playback
  "offline_timestamp": 1722938214,                  // Unix timestamp (nullable)
  "incognito_mode": false                           // Private session
}
```

**Key Insights:**
- **Timestamps**: ISO 8601 UTC format
- **Content Type**: Music tracks, podcasts, or audiobooks
- **Track URI**: Unique Spotify identifier (format: `spotify:track:ID`)
- **22 fields total**: Mix of timestamps, metadata, and behavioral flags

---

## 2. Optimal Multi-User Storage Schema

### Database Choice: **PostgreSQL (Supabase)**

**Why PostgreSQL?**
- ✅ Handles millions of streaming records efficiently
- ✅ Rich indexing for time-series queries
- ✅ JSONB support for flexible metadata
- ✅ Row-level security for multi-user data isolation
- ✅ Materialized views for pre-aggregated analytics
- ✅ Your current stack already uses Supabase

---

## 3. Proposed Database Schema

### Table 1: `users`

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- User identification
    username VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Preferences (optional)
    profile_json JSONB,  -- Flexible profile data
    
    CONSTRAINT valid_username CHECK (char_length(username) >= 3)
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

**Purpose:** Store user accounts with authentication info.

---

### Table 2: `streaming_history` (Modified)

```sql
CREATE TABLE streaming_history (
    id BIGSERIAL PRIMARY KEY,
    
    -- User relationship (NEW)
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Timestamp and platform
    ts TIMESTAMPTZ NOT NULL,
    platform VARCHAR(200),
    
    -- Playback metrics
    ms_played INTEGER NOT NULL,
    
    -- Location
    conn_country VARCHAR(2),
    ip_addr INET,
    
    -- Track metadata
    master_metadata_track_name TEXT,
    master_metadata_album_artist_name TEXT,
    master_metadata_album_album_name TEXT,
    spotify_track_uri VARCHAR(255),
    
    -- Podcast metadata (nullable)
    episode_name TEXT,
    episode_show_name TEXT,
    spotify_episode_uri VARCHAR(255),
    
    -- Audiobook metadata (nullable)
    audiobook_title TEXT,
    audiobook_uri VARCHAR(255),
    audiobook_chapter_uri VARCHAR(255),
    audiobook_chapter_title TEXT,
    
    -- Playback context
    reason_start VARCHAR(100),
    reason_end VARCHAR(100),
    shuffle BOOLEAN DEFAULT FALSE,
    skipped BOOLEAN DEFAULT FALSE,
    offline BOOLEAN DEFAULT FALSE,
    offline_timestamp BIGINT,
    incognito_mode BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Composite index for user + timestamp queries (CRITICAL for performance)
CREATE INDEX idx_streaming_user_ts ON streaming_history(user_id, ts DESC);
CREATE INDEX idx_streaming_user_ts_artist ON streaming_history(user_id, ts DESC, master_metadata_album_artist_name);

-- User-specific indexes
CREATE INDEX idx_streaming_user_artist ON streaming_history(user_id, master_metadata_album_artist_name);
CREATE INDEX idx_streaming_user_track ON streaming_history(user_id, spotify_track_uri);
CREATE INDEX idx_streaming_user_platform ON streaming_history(user_id, platform);

-- Partial index for music only (excludes podcasts/audiobooks)
CREATE INDEX idx_streaming_user_music_only ON streaming_history(user_id, ts DESC)
WHERE spotify_track_uri IS NOT NULL
  AND episode_name IS NULL
  AND audiobook_title IS NULL;

COMMENT ON TABLE streaming_history IS 'Multi-user Spotify streaming history';
COMMENT ON COLUMN streaming_history.user_id IS 'Foreign key to users table';
```

**Key Changes:**
1. ✅ **Added `user_id`** foreign key to link streams to users
2. ✅ **Composite indexes** on `(user_id, ts)` for fast user-specific queries
3. ✅ **All existing indexes** now include `user_id`
4. ✅ **ON DELETE CASCADE** to auto-clean user data on deletion

---

### Table 3: `user_statistics` (Pre-aggregated)

```sql
CREATE TABLE user_statistics (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Period identification
    stat_type VARCHAR(50) NOT NULL,  -- 'monthly', 'weekly', 'yearly'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    -- Aggregated metrics
    total_streams BIGINT NOT NULL,
    total_hours DECIMAL(10, 2) NOT NULL,
    unique_artists INTEGER NOT NULL,
    unique_tracks INTEGER NOT NULL,
    unique_albums INTEGER NOT NULL,
    
    -- Behavioral metrics
    skip_rate DECIMAL(5, 2),
    shuffle_rate DECIMAL(5, 2),
    offline_rate DECIMAL(5, 2),
    
    -- Metadata
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, stat_type, period_start)
);

CREATE INDEX idx_user_stats_user_type ON user_statistics(user_id, stat_type, period_start DESC);
```

**Purpose:** Cache aggregated statistics to avoid recalculating on every request.

---

### Table 4: `user_similarities` (For Recommendations)

```sql
CREATE TABLE user_similarities (
    id BIGSERIAL PRIMARY KEY,
    
    -- User pair
    user_id_1 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_id_2 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Similarity metrics
    artist_overlap_score DECIMAL(5, 4),      -- Jaccard similarity on artists
    track_overlap_score DECIMAL(5, 4),       -- Jaccard similarity on tracks
    genre_overlap_score DECIMAL(5, 4),       -- Cosine similarity on genres
    overall_similarity DECIMAL(5, 4),        -- Weighted combination
    
    -- Metadata
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    last_recalculated_at TIMESTAMPTZ,
    
    UNIQUE(user_id_1, user_id_2),
    CHECK (user_id_1 != user_id_2)
);

CREATE INDEX idx_similarities_user1 ON user_similarities(user_id_1, overall_similarity DESC);
CREATE INDEX idx_similarities_user2 ON user_similarities(user_id_2, overall_similarity DESC);
```

**Purpose:** Store computed similarity scores between user pairs for collaborative filtering.

---

### Table 5: `recommendations` (Pre-computed)

```sql
CREATE TABLE recommendations (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Recommended item
    spotify_track_uri VARCHAR(255) NOT NULL,
    track_name TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    
    -- Recommendation scores
    content_score DECIMAL(5, 4),             -- Content-based score
    collaborative_score DECIMAL(5, 4),       -- Collaborative filtering score
    diversity_score DECIMAL(5, 4),           -- Diversity boost
    final_score DECIMAL(5, 4) NOT NULL,      -- Combined score
    
    -- Why this recommendation?
    why_reason TEXT,                         -- Human-readable explanation
    
    -- Metadata
    recommended_at TIMESTAMPTZ DEFAULT NOW(),
    rank INTEGER NOT NULL,                   -- Rank in user's recommendation list
    
    UNIQUE(user_id, spotify_track_uri)
);

CREATE INDEX idx_recommendations_user_score ON recommendations(user_id, final_score DESC);
CREATE INDEX idx_recommendations_user_rank ON recommendations(user_id, rank);
```

**Purpose:** Pre-compute and cache personalized recommendations for each user.

---

## 4. Migration Strategy

### Step 1: Add User Support Without Breaking Existing Data

```sql
-- Migration: Add multi-user support
-- File: apps/api/migrations/003_add_multi_user_support.sql

-- 1. Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    profile_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- 2. Add user_id column to streaming_history (nullable initially)
ALTER TABLE streaming_history ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

-- 3. Create default user for existing data
INSERT INTO users (username, display_name, email)
VALUES ('tanmay', 'Tanmay', 'tanmay@example.com')
ON CONFLICT (username) DO NOTHING;

-- 4. Backfill existing streaming_history records with default user
UPDATE streaming_history
SET user_id = (SELECT id FROM users WHERE username = 'tanmay')
WHERE user_id IS NULL;

-- 5. Make user_id NOT NULL now that all rows have a user
ALTER TABLE streaming_history ALTER COLUMN user_id SET NOT NULL;

-- 6. Create new indexes with user_id
CREATE INDEX IF NOT EXISTS idx_streaming_user_ts ON streaming_history(user_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_streaming_user_ts_artist ON streaming_history(user_id, ts DESC, master_metadata_album_artist_name);
CREATE INDEX IF NOT EXISTS idx_streaming_user_artist ON streaming_history(user_id, master_metadata_album_artist_name);
CREATE INDEX IF NOT EXISTS idx_streaming_user_track ON streaming_history(user_id, spotify_track_uri);
CREATE INDEX IF NOT EXISTS idx_streaming_user_platform ON streaming_history(user_id, platform);

CREATE INDEX IF NOT EXISTS idx_streaming_user_music_only ON streaming_history(user_id, ts DESC)
WHERE spotify_track_uri IS NOT NULL
  AND episode_name IS NULL
  AND audiobook_title IS NULL;

-- 7. Drop old single-user indexes (optional, for cleanup)
-- DROP INDEX IF EXISTS idx_streaming_ts;  -- Only if you're confident
-- DROP INDEX IF EXISTS idx_streaming_artist;  -- Keep commenting out for safety
```

---

### Step 2: Create Supporting Tables

```sql
-- Migration: Create recommendation tables
-- File: apps/api/migrations/004_recommendation_tables.sql

-- User statistics
CREATE TABLE IF NOT EXISTS user_statistics (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stat_type VARCHAR(50) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_streams BIGINT NOT NULL,
    total_hours DECIMAL(10, 2) NOT NULL,
    unique_artists INTEGER NOT NULL,
    unique_tracks INTEGER NOT NULL,
    unique_albums INTEGER NOT NULL,
    skip_rate DECIMAL(5, 2),
    shuffle_rate DECIMAL(5, 2),
    offline_rate DECIMAL(5, 2),
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, stat_type, period_start)
);

CREATE INDEX IF NOT EXISTS idx_user_stats_user_type ON user_statistics(user_id, stat_type, period_start DESC);

-- User similarities
CREATE TABLE IF NOT EXISTS user_similarities (
    id BIGSERIAL PRIMARY KEY,
    user_id_1 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_id_2 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    artist_overlap_score DECIMAL(5, 4),
    track_overlap_score DECIMAL(5, 4),
    genre_overlap_score DECIMAL(5, 4),
    overall_similarity DECIMAL(5, 4),
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    last_recalculated_at TIMESTAMPTZ,
    UNIQUE(user_id_1, user_id_2),
    CHECK (user_id_1 != user_id_2)
);

CREATE INDEX IF NOT EXISTS idx_similarities_user1 ON user_similarities(user_id_1, overall_similarity DESC);
CREATE INDEX IF NOT EXISTS idx_similarities_user2 ON user_similarities(user_id_2, overall_similarity DESC);

-- Recommendations
CREATE TABLE IF NOT EXISTS recommendations (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    spotify_track_uri VARCHAR(255) NOT NULL,
    track_name TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    content_score DECIMAL(5, 4),
    collaborative_score DECIMAL(5, 4),
    diversity_score DECIMAL(5, 4),
    final_score DECIMAL(5, 4) NOT NULL,
    why_reason TEXT,
    recommended_at TIMESTAMPTZ DEFAULT NOW(),
    rank INTEGER NOT NULL,
    UNIQUE(user_id, spotify_track_uri)
);

CREATE INDEX IF NOT EXISTS idx_recommendations_user_score ON recommendations(user_id, final_score DESC);
CREATE INDEX IF NOT EXISTS idx_recommendations_user_rank ON recommendations(user_id, rank);
```

---

## 5. Data Loading Script for Multiple Users

### Script: `load_multi_user_data.py`

```python
# apps/api/scripts/load_multi_user_data.py

"""
Load Spotify streaming data for multiple users into Supabase
Assumes data is organized as: data/{username}/streaming_*.json
"""

import json
import os
from pathlib import Path
from supabase import create_client, Client
from typing import List, Dict, Any
import uuid

# Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
DATA_DIR = Path(__file__).parent.parent.parent.parent / 'data'

def load_streaming_files_for_user(username: str) -> List[Dict[str, Any]]:
    """Load all streaming_*.json files for a specific user"""
    user_data_dir = DATA_DIR / username
    if not user_data_dir.exists():
        # Check 'other users' directory
        user_data_dir = DATA_DIR / 'other users' / f'{username}_my_spotify_data'
        if not user_data_dir.exists():
            print(f"❌ User data directory not found: {username}")
            return []
    
    # Unzip if needed
    zip_files = list(user_data_dir.glob('*.zip'))
    for zip_file in zip_files:
        import zipfile
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(user_data_dir / 'extracted')
    
    # Load JSON files
    json_files = sorted(user_data_dir.glob('**/StreamingHistory*.json')) + \
                 sorted(user_data_dir.glob('**/streaming_*.json'))
    
    all_records = []
    for json_file in json_files:
        print(f"  📄 Loading {json_file.name}...")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_records.extend(data)
    
    return all_records

def get_or_create_user(supabase: Client, username: str, display_name: str = None) -> str:
    """Get existing user or create new one, return user_id"""
    # Check if user exists
    response = supabase.table('users').select('id').eq('username', username).execute()
    
    if response.data and len(response.data) > 0:
        return response.data[0]['id']
    
    # Create new user
    user_data = {
        'username': username,
        'display_name': display_name or username.title(),
        'email': f'{username}@spotify-insights.local'
    }
    
    response = supabase.table('users').insert(user_data).execute()
    return response.data[0]['id']

def transform_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Transform JSON record to database format"""
    return {
        'ts': record.get('ts'),
        'platform': record.get('platform'),
        'ms_played': record.get('ms_played'),
        'conn_country': record.get('conn_country'),
        'ip_addr': record.get('ip_addr'),
        'master_metadata_track_name': record.get('master_metadata_track_name'),
        'master_metadata_album_artist_name': record.get('master_metadata_album_artist_name'),
        'master_metadata_album_album_name': record.get('master_metadata_album_album_name'),
        'spotify_track_uri': record.get('spotify_track_uri'),
        'episode_name': record.get('episode_name'),
        'episode_show_name': record.get('episode_show_name'),
        'spotify_episode_uri': record.get('spotify_episode_uri'),
        'audiobook_title': record.get('audiobook_title'),
        'audiobook_uri': record.get('audiobook_uri'),
        'audiobook_chapter_uri': record.get('audiobook_chapter_uri'),
        'audiobook_chapter_title': record.get('audiobook_chapter_title'),
        'reason_start': record.get('reason_start'),
        'reason_end': record.get('reason_end'),
        'shuffle': record.get('shuffle', False),
        'skipped': record.get('skipped', False),
        'offline': record.get('offline', False),
        'offline_timestamp': record.get('offline_timestamp'),
        'incognito_mode': record.get('incognito_mode', False)
    }

def load_user_data(username: str, batch_size: int = 5000):
    """Load streaming data for a single user"""
    print(f"\n{'='*60}")
    print(f"Loading data for user: {username}")
    print(f"{'='*60}")
    
    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get or create user
    user_id = get_or_create_user(supabase, username)
    print(f"✅ User ID: {user_id}")
    
    # Load streaming files
    records = load_streaming_files_for_user(username)
    print(f"📊 Total records: {len(records):,}")
    
    if not records:
        print("⚠️  No records found, skipping...")
        return
    
    # Check for existing data
    existing_count = supabase.table('streaming_history').select('id', count='exact').eq('user_id', user_id).execute()
    existing_records = existing_count.count if hasattr(existing_count, 'count') else 0
    
    if existing_records > 0:
        print(f"⚠️  User already has {existing_records:,} records. Skipping to avoid duplicates.")
        response = input("Delete existing data and reload? (yes/no): ")
        if response.lower() == 'yes':
            supabase.table('streaming_history').delete().eq('user_id', user_id).execute()
            print("🗑️  Deleted existing data")
        else:
            print("❌ Aborted")
            return
    
    # Transform and insert in batches
    transformed = [transform_record(r) for r in records]
    
    # Add user_id to each record
    for record in transformed:
        record['user_id'] = user_id
    
    # Insert in batches
    total_inserted = 0
    for i in range(0, len(transformed), batch_size):
        batch = transformed[i:i + batch_size]
        try:
            supabase.table('streaming_history').insert(batch).execute()
            total_inserted += len(batch)
            print(f"  ✅ Inserted batch: {total_inserted:,} / {len(transformed):,}")
        except Exception as e:
            print(f"  ❌ Batch insert failed: {str(e)}")
    
    print(f"\n✅ Successfully loaded {total_inserted:,} records for {username}")

def main():
    """Main entry point"""
    # Get list of users from data directory
    users = []
    
    # Check main data directory (tanmay's data)
    if (DATA_DIR / 'streaming_2018-2020_0.json').exists():
        users.append('tanmay')
    
    # Check 'other users' directory
    other_users_dir = DATA_DIR / 'other users'
    if other_users_dir.exists():
        for zip_file in other_users_dir.glob('*.zip'):
            username = zip_file.stem.replace('_my_spotify_data', '').replace('_', '')
            users.append(username)
    
    print(f"\nFound {len(users)} users: {', '.join(users)}")
    print("\nWhich users would you like to load?")
    print("  (1) Load all users")
    print("  (2) Select specific users")
    print("  (3) Load only new users (skip existing)")
    
    choice = input("\nEnter choice (1-3): ")
    
    if choice == '1':
        for username in users:
            load_user_data(username)
    elif choice == '2':
        print("\nAvailable users:")
        for i, username in enumerate(users, 1):
            print(f"  {i}. {username}")
        selected = input("\nEnter user numbers (comma-separated): ")
        indices = [int(x.strip()) for x in selected.split(',')]
        for idx in indices:
            if 1 <= idx <= len(users):
                load_user_data(users[idx - 1])
    elif choice == '3':
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        for username in users:
            # Check if user has data
            response = supabase.table('users').select('username').eq('username', username).execute()
            if response.data:
                print(f"⏭️  Skipping {username} (already exists)")
            else:
                load_user_data(username)
    else:
        print("Invalid choice")

if __name__ == '__main__':
    main()
```

---

## 6. API Endpoints for Multi-User Queries

### Backend Routes (FastAPI)

```python
# apps/api/app/routes/stats.py

@router.get("/overview")
async def get_overview(
    user_id: Optional[str] = None,  # Default to current authenticated user
    session: Session = Depends(get_session)
):
    """Get overview stats for a specific user"""
    if not user_id:
        user_id = session.user_id  # From authentication
    
    # Query with user_id filter
    stats = calculate_overview_stats(user_id=user_id)
    return stats

@router.get("/top/artists")
async def get_top_artists(
    limit: int = 10,
    user_id: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Get top artists for a specific user"""
    if not user_id:
        user_id = session.user_id
    
    # Query with user_id filter
    top_artists = get_top_artists_for_user(user_id, limit)
    return {"artists": top_artists}
```

---

## 7. Recommendation System Algorithms

### Content-Based Filtering

```sql
-- Query: Find tracks similar to user's top artists
WITH user_top_artists AS (
    SELECT DISTINCT master_metadata_album_artist_name as artist_name
    FROM streaming_history
    WHERE user_id = $1
    GROUP BY master_metadata_album_artist_name
    ORDER BY COUNT(*) DESC
    LIMIT 20
),
recommended_tracks AS (
    SELECT DISTINCT sh.spotify_track_uri, sh.master_metadata_track_name, sh.master_metadata_album_artist_name
    FROM streaming_history sh
    INNER JOIN user_top_artists uta ON sh.master_metadata_album_artist_name = uta.artist_name
    WHERE sh.user_id != $1  -- Tracks from OTHER users
      AND sh.spotify_track_uri IS NOT NULL
    GROUP BY sh.spotify_track_uri, sh.master_metadata_track_name, sh.master_metadata_album_artist_name
    ORDER BY COUNT(*) DESC
    LIMIT 50
)
SELECT * FROM recommended_tracks;
```

---

### Collaborative Filtering

```sql
-- Query: Find users with similar taste
WITH user_artists AS (
    SELECT master_metadata_album_artist_name, COUNT(*) as play_count
    FROM streaming_history
    WHERE user_id = $1
      AND master_metadata_album_artist_name IS NOT NULL
    GROUP BY master_metadata_album_artist_name
),
similar_users AS (
    SELECT 
        sh.user_id,
        COUNT(DISTINCT sh.master_metadata_album_artist_name) as overlap_count,
        SUM(sh.count * ua.play_count) as weighted_score
    FROM streaming_history sh
    INNER JOIN user_artists ua ON sh.master_metadata_album_artist_name = ua.artist_name
    WHERE sh.user_id != $1
    GROUP BY sh.user_id
    ORDER BY weighted_score DESC
    LIMIT 10
)
SELECT * FROM similar_users;
```

---

### Hybrid Recommendation

```python
# apps/api/app/services/recommendation_service.py

class RecommendationService:
    def recommend_tracks(self, user_id: str, top_k: int = 20):
        """Generate hybrid recommendations"""
        
        # 1. Content-based: Similar artists to user's top artists
        content_scores = self.get_content_recommendations(user_id)
        
        # 2. Collaborative: Tracks from similar users
        collaborative_scores = self.get_collaborative_recommendations(user_id)
        
        # 3. Diversity boost: Penalize tracks from same artist
        diversity_scores = self.apply_diversity_boost(content_scores, collaborative_scores)
        
        # 4. Combine scores
        final_scores = {}
        for track_uri, scores in diversity_scores.items():
            final_scores[track_uri] = (
                0.6 * scores['content'] +
                0.3 * scores['collaborative'] +
                0.1 * scores['diversity']
            )
        
        # 5. Sort and return top K
        top_recommendations = sorted(
            final_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        return top_recommendations
```

---

## 8. Performance Optimizations

### 1. Materialized Views for User Stats

```sql
CREATE MATERIALIZED VIEW user_monthly_stats AS
SELECT
    user_id,
    DATE_TRUNC('month', ts)::date as month,
    COUNT(*) as total_streams,
    SUM(ms_played) / 3600000.0 as total_hours,
    COUNT(DISTINCT master_metadata_album_artist_name) as unique_artists,
    COUNT(DISTINCT spotify_track_uri) as unique_tracks
FROM streaming_history
WHERE master_metadata_track_name IS NOT NULL
GROUP BY user_id, DATE_TRUNC('month', ts);

CREATE UNIQUE INDEX idx_user_monthly_stats_unique 
    ON user_monthly_stats(user_id, month);

-- Refresh periodically (daily via cron)
REFRESH MATERIALIZED VIEW CONCURRENTLY user_monthly_stats;
```

---

### 2. Partitioning by User (For Very Large Scale)

```sql
-- If you have 100K+ users and billions of records
CREATE TABLE streaming_history_partitioned (
    -- same columns as streaming_history
    ...
) PARTITION BY HASH(user_id);

-- Create partitions (for 10 users, create 10 partitions)
CREATE TABLE streaming_history_partition_0 
    PARTITION OF streaming_history_partitioned
    FOR VALUES WITH (modulus 10, remainder 0);

-- Each partition gets its own index
CREATE INDEX idx_partition_0_user_ts 
    ON streaming_history_partition_0(user_id, ts DESC);
```

---

### 3. Query Optimization Tips

```sql
-- ❌ BAD: Scans entire table
SELECT * FROM streaming_history WHERE ts > '2024-01-01';

-- ✅ GOOD: Uses composite index
SELECT * FROM streaming_history 
WHERE user_id = $1 AND ts > '2024-01-01';

-- ❌ BAD: Function on indexed column
SELECT * FROM streaming_history 
WHERE EXTRACT(YEAR FROM ts) = 2024;

-- ✅ GOOD: Range query
SELECT * FROM streaming_history 
WHERE user_id = $1 AND ts >= '2024-01-01' AND ts < '2025-01-01';
```

---

## 9. Data Directory Structure

### Proposed Organization

```
data/
├── tanmay/
│   ├── streaming_2018-2020_0.json
│   ├── streaming_2020-2022_1.json
│   ├── streaming_2022-2023_2.json
│   ├── streaming_2023-2024_3.json
│   └── streaming_2024-2025_4.json
│
├── abhiraj/
│   ├── StreamingHistory_music_0.json
│   ├── StreamingHistory_music_1.json
│   └── ...
│
├── amit/
│   ├── StreamingHistory_music_0.json
│   └── ...
│
└── other users/
    ├── antara_my_spotify_data.zip
    ├── ash_my_spotify_data-1.zip
    └── ... (keep as archive)
```

**Action Items:**
1. Extract all ZIP files from `other users/` into user-specific directories
2. Rename extracted files to consistent `streaming_*.json` format
3. Update data loading script to handle both structures

---

## 10. Security Considerations

### Row-Level Security (RLS)

```sql
-- Enable RLS on streaming_history
ALTER TABLE streaming_history ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own data
CREATE POLICY user_data_isolation ON streaming_history
    FOR ALL
    TO authenticated
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- Grant access
GRANT SELECT, INSERT, UPDATE ON streaming_history TO authenticated;
```

---

### API Authentication

```python
# Require authentication for all user-specific endpoints
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Verify JWT and return user_id"""
    # Verify token, extract user_id
    # ...
    return user_id

@router.get("/overview")
async def get_overview(
    user_id: str = Depends(get_current_user)  # Require auth
):
    # ...
```

---

## 11. Migration Checklist

- [ ] Create migration file: `003_add_multi_user_support.sql`
- [ ] Create migration file: `004_recommendation_tables.sql`
- [ ] Run migrations in Supabase
- [ ] Update `load_json_to_supabase.py` → `load_multi_user_data.py`
- [ ] Extract ZIP files from `other users/` directory
- [ ] Load tanmay's data first (backfill)
- [ ] Load other users' data
- [ ] Update API endpoints to filter by `user_id`
- [ ] Add authentication to API routes
- [ ] Create recommendation service
- [ ] Create job to pre-compute recommendations
- [ ] Add RLS policies to tables
- [ ] Update frontend to support user switching
- [ ] Test performance with multiple users
- [ ] Create materialized views
- [ ] Set up cron jobs for refreshing views

---

## 12. Next Steps

### Immediate Actions

1. **Run migrations** to add multi-user support
2. **Extract and organize** data from ZIP files
3. **Load initial data** for all users
4. **Test queries** with multi-user data

### Short-term (1-2 weeks)

1. **Implement recommendation algorithms**
2. **Pre-compute similarity matrices**
3. **Add authentication to API**
4. **Update frontend** for user switching

### Long-term (1-2 months)

1. **Production deployment** with RLS
2. **Monitoring and alerting** for data quality
3. **A/B testing** for recommendation algorithms
4. **Scale horizontally** if needed (partitioning)

---

## Conclusion

**Key Takeaways:**

✅ **Add `user_id`** to `streaming_history` as foreign key  
✅ **Composite indexes** on `(user_id, ts)` for performance  
✅ **Pre-aggregate statistics** in `user_statistics` table  
✅ **Store similarities** in `user_similarities` table  
✅ **Cache recommendations** in `recommendations` table  
✅ **Use materialized views** for faster queries  
✅ **Implement RLS** for data security  
✅ **Batch load data** to handle large datasets  

**Benefits:**
- **Scalable**: Handles millions of records across users
- **Fast**: Indexed queries return in milliseconds
- **Secure**: Row-level security isolates user data
- **Maintainable**: Clear separation of concerns
- **Flexible**: Extensible for new recommendation algorithms

**Estimated Storage:**
- ~100K users with 1M streams each = 100B records
- Estimated size: ~10-20 TB (with compression)
- Supabase PostgreSQL can handle this scale with proper indexing

---

**Questions?**
- Database sizing calculations
- Query optimization strategies
- Recommendation algorithm tuning
- Deployment considerations


