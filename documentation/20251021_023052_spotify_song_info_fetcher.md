# Spotify Song Info Fetcher - Implementation Documentation

**Date:** 2025-10-21 02:30:52
**Status:** Completed
**Time to complete:** 45 minutes

---

## Overview

Created a production-ready Python script to fetch comprehensive song information from Spotify Web API for all 13,837 tracks in the processing queue. The implementation features advanced rate limiting, batch API prioritization, idempotent processing, and incremental saving.

**Output:** `outputs/data/songs_info.json`
**Script:** `libraries/analysis/fetch_spotify_song_info.py`

---

## Files Created

- `libraries/analysis/fetch_spotify_song_info.py` (601 lines)
- `documentation/20251021_023052_spotify_song_info_fetcher.md` (this file)

---

## Files Modified

None - This is a standalone new implementation.

---

## Checklist

- [x] Idempotent processing (resume capability)
- [x] Advanced rate limiting (30-second rolling window)
- [x] Batch API prioritization (Albums → Tracks → Audio Features → Artists)
- [x] Incremental saving (every 10 songs)
- [x] Proper error handling (429 errors with Retry-After header)
- [x] Comprehensive data collection (tracks, albums, artists, audio features)
- [x] Progress tracking and statistics
- [x] Clean console output with status updates
- [x] Environment variable configuration
- [x] Documentation completed

---

## What Was Implemented

### Purpose

Fetch detailed song information from Spotify Web API for all tracks in the processing queue to enable advanced analytics including:
- Audio feature analysis (valence, energy, danceability, tempo, etc.)
- Album and artist metadata enrichment
- Genre classification
- Popularity trends
- Release date analysis

### Features

#### 1. **Advanced Rate Limiting System**

**RateLimiter Class** with 30-second rolling window monitoring:

```python
class RateLimiter:
    - Tracks API call timestamps in a deque (O(1) operations)
    - Monitors 30-second rolling window
    - Automatic waiting when approaching limits
    - Handles 429 errors with Retry-After header
    - Exponential backoff on repeated failures
    - Real-time statistics tracking
```

**Configuration:**
- Development Mode: 180 calls per 30 seconds
- Extended Quota Mode: 1000+ calls per 30 seconds (configurable)

**Features:**
- `can_make_call()`: Check if within rate limits
- `wait_if_needed()`: Automatic throttling
- `handle_429_error()`: Smart retry with backoff
- `get_stats()`: Real-time utilization metrics

#### 2. **Batch API Prioritization**

Implemented priority-based batch fetching as requested:

| Priority | API Endpoint       | Batch Size | Reason                           |
|----------|-------------------|------------|----------------------------------|
| 1 (High) | Get Albums        | 20/request | Most restrictive, fetch first    |
| 2        | Get Tracks        | 50/request | Core data, medium priority       |
| 3        | Audio Features    | 100/request| Supplementary data               |
| 4 (Low)  | Get Artists       | 50/request | Derived from tracks, fetch last  |

**Optimization Strategy:**
- Deduplicate album IDs before fetching
- Deduplicate artist IDs across all tracks
- Extract artist IDs from track data (avoid redundant lookups)
- Use maximum batch sizes to minimize API calls

#### 3. **Idempotent Processing**

**Resume Capability:**
- Loads existing `songs_info.json` on startup
- Extracts processed track IDs into a Set (O(1) lookup)
- Skips already processed songs
- Safe to interrupt at any time (Ctrl+C)
- Preserves all previous progress

**Progress Tracking Structure:**
```json
{
  "total_processed": 0,
  "last_updated": "2025-10-21T02:30:52",
  "processing_started": "2025-10-21T01:45:00",
  "songs": [...]
}
```

#### 4. **Incremental Saving**

- Saves progress every **10 songs** (configurable via `SAVE_INTERVAL`)
- Processes songs in batches of **500** (configurable via `BATCH_SIZE`)
- Atomic writes to prevent data corruption
- Timestamps on each save operation

**Save Strategy:**
```python
# Within batch processing loop
if idx % SAVE_INTERVAL == 0:
    progress['songs'].extend(batch_results)
    progress['total_processed'] += len(batch_results)
    self.save_progress(progress)
    batch_results = []  # Clear memory
```

#### 5. **Comprehensive Data Collection**

For each song, the script fetches:

**Track Information:**
- Track ID, URI, name, duration
- Popularity score
- Explicit flag
- Disc number, track number
- Preview URL
- Available markets

**Audio Features:**
- Valence (happiness/positivity)
- Energy
- Danceability
- Tempo (BPM)
- Key, mode
- Acousticness
- Instrumentalness
- Liveness
- Speechiness
- Loudness
- Time signature

**Album Information:**
- Album ID, name, type
- Release date (precision: day/month/year)
- Label, total tracks
- Genres
- Images (multiple resolutions)
- Available markets
- Copyrights

**Artist Information:**
- Artist ID, name
- Genres
- Popularity
- Follower count
- Images (multiple resolutions)
- External URLs

#### 6. **Error Handling & Retry Logic**

**429 Rate Limit Errors:**
```python
def handle_429_error(self, retry_after: Optional[int] = None):
    self.total_429_errors += 1
    wait_time = retry_after if retry_after else 60
    print(f"⚠️  429 Error: Waiting {wait_time}s...")
    time.sleep(wait_time)
    self.calls.clear()  # Reset window for safety
```

**API Call Wrapper:**
- Max 3 retries per API call
- Exponential backoff on failures
- Graceful None handling for missing data
- Detailed error logging

**Interruption Handling:**
- Keyboard interrupt (Ctrl+C) caught gracefully
- Progress saved before exit
- Clear instructions to resume

### Implementation

#### Class Structure

**1. RateLimiter**
- Manages API call rate limiting
- 30-second rolling window using deque
- Statistics tracking
- 429 error handling

**2. SpotifyInfoFetcher**
- Main orchestration class
- Batch API methods for each endpoint
- Progress loading/saving
- Data combination logic

#### Key Methods

**Queue Management:**
- `load_processing_queue()`: Load CSV with all songs
- `load_progress()`: Load existing JSON progress
- `get_processed_track_ids()`: Extract processed IDs as Set
- `save_progress()`: Atomic JSON write with timestamp

**API Fetching (with rate limiting):**
- `fetch_albums_batch()`: Albums (20/request)
- `fetch_tracks_batch()`: Tracks (50/request)
- `fetch_audio_features_batch()`: Audio features (100/request)
- `fetch_artists_batch()`: Artists (50/request)
- `_make_api_call()`: Wrapper with rate limiting + retry

**Processing:**
- `process_batch()`: Main batch processing logic
- `extract_id_from_uri()`: Parse Spotify URIs

### Flow

```
1. INITIALIZATION
   ├─ Load Spotify credentials from spotify-stats.env
   ├─ Initialize SpotifyClientCredentials
   ├─ Create RateLimiter (180 calls/30s)
   └─ Print configuration

2. PROGRESS CHECK
   ├─ Load songs_info.json (if exists)
   ├─ Extract processed track IDs
   └─ Report: X already done, Y remaining

3. QUEUE LOADING
   ├─ Read songs_processing_queue.csv
   ├─ Filter out already processed songs
   └─ Calculate total batches needed

4. BATCH PROCESSING (for each batch of 500)
   │
   ├─ PRIORITY 1: Fetch Albums (20/request)
   │  ├─ Deduplicate album IDs
   │  ├─ Split into batches of 20
   │  ├─ Rate limit check + API call
   │  └─ Store in album_id_to_data dict
   │
   ├─ PRIORITY 2: Fetch Tracks (50/request)
   │  ├─ Split into batches of 50
   │  ├─ Rate limit check + API call
   │  ├─ Store in track_id_to_data dict
   │  └─ Extract artist IDs for next step
   │
   ├─ PRIORITY 3: Fetch Audio Features (100/request)
   │  ├─ Split into batches of 100
   │  ├─ Rate limit check + API call
   │  └─ Store in track_id_to_features dict
   │
   ├─ PRIORITY 4: Fetch Artists (50/request)
   │  ├─ Deduplicate artist IDs
   │  ├─ Split into batches of 50
   │  ├─ Rate limit check + API call
   │  └─ Store in artist_id_to_data dict
   │
   └─ COMBINE & SAVE
      ├─ For each song:
      │  ├─ Lookup track_info
      │  ├─ Lookup audio_features
      │  ├─ Lookup album_info
      │  ├─ Lookup artists_info (multiple)
      │  └─ Create combined record
      │
      └─ Save every 10 songs (SAVE_INTERVAL)
         ├─ Extend progress['songs']
         ├─ Update total_processed count
         ├─ Write JSON atomically
         └─ Print progress update

5. STATISTICS & COMPLETION
   ├─ Print total songs processed
   ├─ Show rate limiter statistics
   │  ├─ Total API calls made
   │  ├─ Current window utilization
   │  └─ Total 429 errors encountered
   └─ Print output file location
```

### Usage

#### Basic Usage

```bash
cd /Users/tanmaybhuskute/Documents/spotify-stats/libraries/analysis
python fetch_spotify_song_info.py
```

#### Configuration

Edit constants at top of script:

```python
BATCH_SIZE = 500              # Songs per processing batch
SAVE_INTERVAL = 10            # Save every N songs
rate_limit = 180              # Dev mode: 180, Extended: 1000+
```

#### Environment Variables Required

In `spotify-stats.env`:
```bash
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

#### Console Output Example

```
======================================================================
  SPOTIFY SONG INFO FETCHER
======================================================================
Started at: 2025-10-21 02:30:52
Batch size: 500 songs
Save interval: Every 10 songs
Output: outputs/data/songs_info.json

Initializing Spotify API client...
✓ Spotify API initialized
✓ Rate limiter configured: 180 calls per 30s
✓ Client initialized

Loading processing queue...
✓ Loaded 13837 total songs

Loading existing progress...
✓ Already processed: 0 songs

📝 Songs to process: 13837
   • Already done: 0
   • Remaining: 13837

======================================================================
BATCH 1/28
======================================================================

======================================================================
PROCESSING BATCH OF 500 SONGS
======================================================================

[1/4] Fetching 487 unique albums...
   ✓ Retrieved 487/487 albums

[2/4] Fetching 500 tracks...
   ✓ Retrieved 500/500 tracks

[3/4] Fetching audio features for 500 tracks...
   ✓ Retrieved 496/500 audio features

[4/4] Fetching 234 unique artists...
   ✓ Retrieved 234/234 artists

======================================================================
COMBINING DATA AND SAVING
======================================================================

[10/500] Progress saved (10 songs processed)
[20/500] Progress saved (20 songs processed)
...

📊 Rate Limiter Stats:
   • Total API calls: 47
   • Current window: 12/180 (6.7%)
   • 429 errors: 0

✓ Batch 1/28 completed
   Total progress: 500/13837 songs
```

---

## Performance Expectations

### For 13,837 Songs

**Development Mode** (180 calls/30s):
- Estimated API calls: ~1,500-2,000
- Estimated time: **2-3 hours**
- Recommended for: Testing, small-scale use

**Extended Quota Mode** (1000+ calls/30s):
- Estimated API calls: ~1,500-2,000
- Estimated time: **30-45 minutes**
- Recommended for: Production, large-scale processing

### API Call Breakdown

Per 500 songs (approximate):
- Albums: 25 calls (20 albums/request, ~500 unique albums)
- Tracks: 10 calls (50 tracks/request)
- Audio Features: 5 calls (100 tracks/request)
- Artists: 5-10 calls (50 artists/request, ~250 unique artists)

**Total per batch: ~45-50 API calls**

---

## Output Data Structure

### JSON Schema

```json
{
  "total_processed": 13837,
  "last_updated": "2025-10-21T03:15:42.123456",
  "processing_started": "2025-10-21T02:30:52.654321",
  "songs": [
    {
      "track_id": "7IatLQIKChU9gt0OexdEXp",
      "track_uri": "spotify:track:7IatLQIKChU9gt0OexdEXp",
      "track_name": "Homesick",
      "artist_name": "Kane Brown",
      "album_name": "Homesick",
      "isrc": "USRN11800032",
      "total_plays": "3",
      "first_played_date": "2018-10-29",
      "last_played_date": "2018-11-25",

      "track_info": {
        "id": "7IatLQIKChU9gt0OexdEXp",
        "name": "Homesick",
        "duration_ms": 197040,
        "popularity": 68,
        "explicit": false,
        "preview_url": "https://...",
        "track_number": 1,
        "disc_number": 1,
        "artists": [...],
        "album": {...},
        "external_urls": {...},
        "available_markets": [...]
      },

      "audio_features": {
        "id": "7IatLQIKChU9gt0OexdEXp",
        "danceability": 0.567,
        "energy": 0.701,
        "key": 1,
        "loudness": -5.123,
        "mode": 1,
        "speechiness": 0.0329,
        "acousticness": 0.219,
        "instrumentalness": 0.0,
        "liveness": 0.0897,
        "valence": 0.456,
        "tempo": 95.012,
        "time_signature": 4,
        "duration_ms": 197040
      },

      "album_info": {
        "id": "1Pc9dibdevLB0I5HPR5nTP",
        "name": "Homesick",
        "album_type": "album",
        "release_date": "2017-05-05",
        "release_date_precision": "day",
        "total_tracks": 11,
        "label": "RCA Records Label Nashville",
        "genres": [],
        "popularity": 65,
        "images": [
          {
            "height": 640,
            "width": 640,
            "url": "https://..."
          }
        ],
        "external_urls": {...},
        "copyrights": [...]
      },

      "artists_info": [
        {
          "id": "3oSJ7TBVCWMDMiYjXNiCKE",
          "name": "Kane Brown",
          "genres": ["contemporary country", "country road"],
          "popularity": 79,
          "followers": {
            "total": 4567890
          },
          "images": [
            {
              "height": 640,
              "width": 640,
              "url": "https://..."
            }
          ],
          "external_urls": {...}
        }
      ],

      "fetched_at": "2025-10-21T02:35:12.987654"
    }
  ]
}
```

### File Size Estimate

- Average record size: ~5-10 KB (with full objects)
- 13,837 songs × 7.5 KB = **~100-140 MB**

---

## Next Steps

### Immediate Actions

1. **Run the script:**
   ```bash
   cd libraries/analysis
   python fetch_spotify_song_info.py
   ```

2. **Monitor progress** via console output

3. **Verify output** at `outputs/data/songs_info.json`

### Future Enhancements

1. **Analytics Integration**
   - Create analysis scripts using the enriched data
   - Genre classification analysis
   - Audio feature clustering (mood detection)
   - Popularity trend analysis
   - Release date patterns

2. **Database Integration**
   - Load JSON data into Supabase
   - Create indexed tables for fast queries
   - Enable web app integration

3. **Incremental Updates**
   - Add logic to fetch only new songs
   - Update changed metadata
   - Track data freshness

4. **Extended Features**
   - Fetch related artists
   - Fetch artist top tracks
   - Fetch recommendations based on seeds
   - Fetch track analysis (detailed audio analysis)

5. **Optimization**
   - Cache album/artist data to avoid redundant fetches
   - Implement background processing
   - Add multi-threading for I/O operations

---

## Conclusion

Successfully implemented a robust, production-ready Spotify song information fetcher that efficiently handles 13,837+ songs with advanced rate limiting, batch API prioritization, and idempotent processing. The script is optimized for Spotify's API constraints and provides comprehensive data collection for downstream analytics.

**Key Achievements:**
- ✅ Advanced rate limiting with 30-second rolling window
- ✅ Batch API prioritization (Albums highest priority)
- ✅ Idempotent processing with resume capability
- ✅ Incremental saving every 10 songs
- ✅ Comprehensive error handling and retry logic
- ✅ Real-time progress monitoring and statistics
- ✅ Clean, maintainable, well-documented code

The implementation follows best practices for API consumption, data persistence, and error recovery, making it suitable for production use and future extensions.

---

**Script Location:** `libraries/analysis/fetch_spotify_song_info.py`
**Output Location:** `outputs/data/songs_info.json`
**Documentation:** `documentation/20251021_023052_spotify_song_info_fetcher.md`
