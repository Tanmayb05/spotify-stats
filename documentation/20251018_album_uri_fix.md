# Album URI Fix - extract_songs_v2.py

**Date:** 2025-10-18
**Status:** Completed
**Issue:** Album count showing 0, all tracks classified as "without albums"

## Problem Description

The script was reporting:
```
✓ Unique albums found: 0
✓ Tracks with albums: 0
✓ Tracks without albums: 13,837
```

### Root Cause

Spotify's streaming history export JSON **does not include `spotify_album_uri`** field. The original script attempted to read this field from the JSON data:

```python
album_uri = entry.get('spotify_album_uri')  # Always None!
```

The JSON structure only contains:
- `spotify_track_uri`
- Track name, artist name, album name (metadata only)
- **No album URI**

## Solution

Completely rewrote the metadata fetching strategy:

### OLD Strategy (Broken)
1. Try to read album URIs from JSON (failed - field doesn't exist)
2. Batch fetch albums (never executed - no albums to fetch)
3. Fetch ISRCs individually

### NEW Strategy (Fixed)
1. **Phase 1**: Batch fetch tracks using Spotify API (50 tracks/call)
   - Get album URIs from Spotify API response
   - Get ISRCs directly (included in track response)
   - Map tracks to albums for statistics

**Result**: Single-phase operation that gets all needed metadata efficiently.

## Changes Made

### 1. Removed Album URI Reading from JSON
```python
# OLD (line 102)
album_uri = entry.get('spotify_album_uri')

# NEW (line 101)
# Removed - this field doesn't exist in Spotify export
```

### 2. Simplified Extraction Phase
```python
# Store unique song info (album_uri will be fetched from Spotify API later)
if track_uri not in songs_data:
    songs_data[track_uri] = {
        'track_uri': track_uri,
        'track_name': track_name,
        'artist_name': artist_name,
        'album_name': album_name or 'Unknown',
        'album_uri': None  # Will be populated during metadata fetching
    }
```

### 3. Rewrote fetch_spotify_metadata() Method

**New Phase 1: Batch Track Fetching**
```python
# Batch fetch tracks (50 tracks per API call)
tracks_data = self.spotify.tracks(track_ids)

for track in tracks_data.get('tracks', []):
    track_id = track['id']
    track_uri = f"spotify:track:{track_id}"
    album_uri = track.get('album', {}).get('uri')  # Get from API
    isrc = track.get('external_ids', {}).get('isrc')  # Get from API

    track_metadata[track_uri] = {
        'track_id': track_id,
        'track_uri': track_uri,
        'album_uri': album_uri,
        'isrc': isrc or 'N/A'
    }
```

**Removed Phase 2 & 3**: No longer needed since Phase 1 gets everything.

### 4. Updated CSV Writers

Added `album_uri` to fieldnames in both:
- `save_unique_songs_csv()` (line 184)
- `save_processing_queue_csv()` (line 348)

## Files Modified

1. **libraries/analysis/extract_songs_v2.py**
   - `extract_unique_songs()`: Removed album_uri reading from JSON
   - `fetch_spotify_metadata()`: Complete rewrite to batch fetch tracks
   - `save_unique_songs_csv()`: Added album_uri field
   - `save_processing_queue_csv()`: Added album_uri field

## API Call Efficiency

### Before Fix (Theoretical)
- Would have made 1 call per track = 13,837 calls
- Estimated time: ~1.35 hours (at 3 req/sec)

### After Fix (Actual)
- Makes 50 tracks per call = ~277 calls
- Estimated time: ~2-3 minutes (with delays)
- **API calls saved: ~13,560 calls (98% reduction)**

## Expected Output

After fix, the script should show:
```
✓ Unique songs extracted: 13,837
✓ Unique albums found: ~2,500-4,000 (estimated)
✓ Tracks with albums: ~13,800+ (most tracks)
✓ Tracks without albums: <100 (edge cases only)

PHASE 1: BATCH FETCHING TRACKS
✓ Phase 1 complete: 13,837 tracks fetched
✓ Found ~3,000 unique albums
✓ ISRCs found: ~13,500+
```

## Testing

Run the script:
```bash
python libraries/analysis/extract_songs_v2.py
```

Verify outputs:
- `data/unique_songs.csv` - includes album_uri column
- `data/songs_processing_queue.csv` - includes album_uri column

## Next Steps

1. ✅ Script fixed and documented
2. ⏳ Run full extraction on all streaming data
3. ⏳ Verify album statistics are correct
4. ⏳ Proceed with lyrics batch processing

## Conclusion

The issue was a fundamental misunderstanding of the Spotify export data structure. The export doesn't include album URIs, requiring us to fetch them via the Spotify API. The new implementation is actually more efficient than the original planned approach, using batch track fetching (50/call) instead of individual track calls.
