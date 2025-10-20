# Lyrics Batch Processing System

## Overview

A comprehensive batch processing system for extracting lyrics from your Spotify listening history with:
- ✅ **Resume capability** - Never lose progress
- ✅ **Dual API fallback** - Genius → Musixmatch
- ✅ **Batch processing** - 500 songs per batch
- ✅ **Progress tracking** - CSV queue + JSON results
- ✅ **Automatic continuation** - Processes all songs sequentially

## System Architecture

### Files Created

1. **`libraries/analysis/extract_songs.py`** - Extracts unique songs and fetches Spotify metadata
2. **`libraries/analysis/process_lyrics_batch.py`** - Batch lyrics processor with resume capability
3. **`data/unique_songs.csv`** - All unique songs from your listening history
4. **`data/songs_processing_queue.csv`** - Processing queue with Spotify metadata (ISRC, track_id)
5. **`outputs/lyrics-1.json`** - Cumulative lyrics results with all fetched lyrics

### CSV Structure

**unique_songs.csv:**
```
track_uri, track_name, artist_name, album_name, total_plays, first_played_date, last_played_date
```

**songs_processing_queue.csv:**
```
track_uri, track_id, track_name, artist_name, album_name, isrc, total_plays,
first_played_date, last_played_date, processed, lyrics_found, lyrics_source,
batch_number, processed_timestamp
```

**lyrics-1.json:**
```json
{
  "total_processed": 1500,
  "successful": 1200,
  "failed": 300,
  "batches_completed": [1, 2, 3],
  "lyrics_sources": {"genius": 800, "musixmatch": 400},
  "tracks": [...]
}
```

## Usage

### Step 1: Extract Songs & Create Processing Queue

This extracts all unique songs from your JSON data and fetches Spotify metadata (ISRC codes) for each song:

```bash
python libraries/analysis/extract_songs.py
```

**What it does:**
- Scans all JSON files in `data/` directory
- Extracts 13,837 unique songs
- Fetches Spotify metadata (ISRC, track_id) for all songs
- Creates two CSVs:
  - `data/unique_songs.csv` - Basic song info
  - `data/songs_processing_queue.csv` - Full metadata for processing

**Expected output:**
```
STEP 1: EXTRACTING UNIQUE SONGS
✓ Extracted 13,837 unique songs
✓ Saved to data/unique_songs.csv

STEP 2: FETCHING SPOTIFY METADATA
✓ Successfully fetched metadata for 13,837/13,837 songs
✓ Saved processing queue to data/songs_processing_queue.csv
```

### Step 2: Process Lyrics in Batches

This processes songs in batches of 500 with automatic resume capability:

```bash
python libraries/analysis/process_lyrics_batch.py
```

**What it does:**
- Reads `data/songs_processing_queue.csv`
- Checks `outputs/lyrics-1.json` for already processed songs
- Processes next 500 unprocessed songs (Batch 1)
- Saves results every 10 songs to `lyrics-1.json`
- Updates `songs_processing_queue.csv` with processing status
- Automatically moves to Batch 2, then Batch 3, etc.
- Continues until all songs are processed

**Expected output:**
```
BATCH LYRICS PROCESSOR
Batch size: 500 songs
Strategy: Genius API → Musixmatch API

✓ Loaded 13,837 total songs
✓ Already processed: 0 songs
✓ Completed batches: []

PROCESSING BATCH 1
Songs in batch: 500

[1/500] Song Name - Artist Name
   ✓ Found via GENIUS
   → Progress saved (10 songs processed)

[500/500] Last Song - Last Artist
   ✓ Found via MUSIXMATCH

✓ Batch 1 completed
   Total progress: 500/13,837 songs

PROCESSING BATCH 2
...
```

## Features

### 1. Resume Capability

If the script is interrupted:
- All progress is saved in `lyrics-1.json`
- Queue CSV is updated with processing status
- Next run automatically resumes from where it stopped

**To resume:**
```bash
python libraries/analysis/process_lyrics_batch.py  # Just run again!
```

### 2. Batch Verification

Each batch completion is tracked:
- `batches_completed` array in JSON shows which batches are done
- Script automatically moves to next incomplete batch
- No duplicate processing

### 3. Progress Tracking

**Real-time updates:**
- Progress saved every 10 songs
- CSV updated with `processed=True`, `lyrics_found`, `lyrics_source`
- Timestamp recorded for each processed song

**Check progress:**
```bash
# View queue status
head -20 data/songs_processing_queue.csv

# Check completion stats
cat outputs/lyrics-1.json | grep -E "total_processed|successful|failed"
```

### 4. Fallback Strategy

For each song:
1. **Try Genius API** (if token configured)
   - Better lyrics coverage
   - Full song text
2. **Fallback to Musixmatch ISRC lookup**
   - Uses Spotify ISRC code
3. **Fallback to Musixmatch search**
   - Searches by track name + artist

### 5. Rate Limiting

- 1 second delay between songs
- Prevents API rate limits
- Safe for long-running batches

## Configuration

### Required Environment Variables

Add to your `spotify-stats.env` file:

```bash
# Spotify API (required for metadata fetching)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Genius API (optional but recommended)
GENIUS_ACCESS_TOKEN=your_genius_token

# Musixmatch API (automatic, no setup needed)
# Uses musicxmatch-api package
```

### Batch Size

To change batch size, edit `libraries/analysis/process_lyrics_batch.py`:

```python
BATCH_SIZE = 500  # Change to 100, 250, 1000, etc.
```

### Save Interval

To change how often progress is saved:

```python
SAVE_INTERVAL = 10  # Save every N songs (default: 10)
```

## Monitoring Progress

### Check CSV Queue Status

```bash
# Count processed songs
grep -c "True" data/songs_processing_queue.csv

# Check success rate
grep -c "genius" data/songs_processing_queue.csv  # Genius successes
grep -c "isrc\|search" data/songs_processing_queue.csv  # Musixmatch successes
```

### View JSON Progress

```python
import json

with open('outputs/lyrics-1.json') as f:
    data = json.load(f)

print(f"Total processed: {data['total_processed']}")
print(f"Successful: {data['successful']}")
print(f"Failed: {data['failed']}")
print(f"Completed batches: {data['batches_completed']}")
print(f"Genius: {data['lyrics_sources']['genius']}")
print(f"Musixmatch: {data['lyrics_sources']['musixmatch']}")
```

## Handling Errors

### If Script Crashes

The system is designed to handle crashes gracefully:

1. **Progress is saved** - Every 10 songs, results are written to disk
2. **Queue is updated** - CSV shows which songs were processed
3. **Just restart** - Script automatically resumes

```bash
python libraries/analysis/process_lyrics_batch.py  # Resume from last save point
```

### If You Need to Reset

To start completely fresh:

```bash
# Remove progress files
rm outputs/lyrics-1.json

# Reset queue CSV
python libraries/analysis/extract_songs.py  # Recreates queue from scratch
```

### If a Batch Fails Repeatedly

Check specific songs causing issues:

```bash
# Find unprocessed songs in queue
grep "False" data/songs_processing_queue.csv | head -10
```

## Performance

### Expected Processing Time

- **Songs per hour:** ~1,800 songs (with 1s delay between songs)
- **13,837 songs:** ~7.5 hours total
- **Per batch (500 songs):** ~28 minutes

### Optimization Tips

1. **Run overnight** - Let it process while you sleep
2. **Use screen/tmux** - Keep script running if SSH session disconnects
3. **Monitor logs** - Check which API is working best for your library

## Output Files

### lyrics-1.json

Contains all successfully fetched lyrics:

```json
{
  "total_processed": 13837,
  "successful": 11500,
  "failed": 2337,
  "batches_completed": [1, 2, 3, ..., 28],
  "lyrics_sources": {
    "genius": 7000,
    "musixmatch": 4500
  },
  "tracks": [
    {
      "track_uri": "spotify:track:xxx",
      "track_name": "Song Name",
      "artist_name": "Artist Name",
      "lyrics": {
        "lyrics_body": "Full lyrics text...",
        "lookup_method": "genius"
      },
      "lyrics_source": "genius"
    }
  ]
}
```

### songs_processing_queue.csv

Tracks processing status for each song:

```csv
track_uri,track_id,track_name,artist_name,isrc,processed,lyrics_found,lyrics_source,batch_number,processed_timestamp
spotify:track:abc,abc,Song1,Artist1,US1234567,True,True,genius,1,2025-10-16 20:30:15
spotify:track:def,def,Song2,Artist2,US7654321,True,False,,1,2025-10-16 20:30:30
```

## Next Steps

After processing completes:

1. **Analyze lyrics** - Use `lyrics-1.json` for sentiment analysis, word clouds, etc.
2. **Build recommender** - Use behavioral data + lyrics for Phase 6 recommendations
3. **Export subset** - Extract specific artists/genres for focused analysis

## Troubleshooting

### "No track URIs found"

```bash
# Check if data directory has JSON files
ls -lh data/*.json
```

### "SPOTIFY_CLIENT_ID not set"

```bash
# Add to spotify-stats.env file
echo "SPOTIFY_CLIENT_ID=your_id" >> spotify-stats.env
echo "SPOTIFY_CLIENT_SECRET=your_secret" >> spotify-stats.env
```

### "Queue CSV not found"

```bash
# Run extraction first
python libraries/analysis/extract_songs.py
```

### Process is slow

This is normal! With 13,837 songs and 1-second delays:
- Total time: ~8 hours
- The delays prevent API rate limiting
- Progress is saved frequently, so you can stop/resume anytime

---

## Summary

Your batch lyrics processing system is now ready!

**Quick Start:**
```bash
# Step 1: Extract songs (run once)
python libraries/analysis/extract_songs.py

# Step 2: Process lyrics (runs until complete, resumable)
python libraries/analysis/process_lyrics_batch.py
```

The system will automatically:
- Process 500 songs at a time
- Try Genius, then Musixmatch for each song
- Save progress every 10 songs
- Move to next batch when current completes
- Resume from where it stopped if interrupted

Check `outputs/lyrics-1.json` for results and `data/songs_processing_queue.csv` for status!
