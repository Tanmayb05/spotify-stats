# Detailed Lyrics Failure Logging Enhancement

**Date:** 2025-10-18
**Status:** Completed
**Issue:** "Not found" errors didn't explain WHY lyrics weren't found or which sources were tried

## Problem Description

Previous output was too vague:
```
[3/500] Hello World - Brian Tyler
   ✗ Not found
```

**Problems:**
- Doesn't indicate both Genius AND Musixmatch were tried
- No explanation of why the lookup failed
- Can't distinguish between:
  - Track not in database
  - API error
  - Instrumental track (no lyrics exist)
  - Rate limiting
  - ISRC vs search lookup failures

## Solution

### Enhanced Logging Strategy

Changed all lookup methods to return **tuple** `(result, status_message)`:

1. **Genius API**: Returns specific failure reason
   - "Track not found in Genius"
   - "Track found but no lyrics available"
   - "Genius API not initialized"
   - "Genius API error: {error}"

2. **Musixmatch API**: Returns pipeline of failure reasons
   - ISRC lookup attempt → Search lookup attempt
   - Each step logs its specific failure
   - All failures joined with " | " separator

### Example Output (New Format)

```
[3/500] Hello World - Brian Tyler
   ✗ Not found in both sources:
      • Genius: Track not found in Genius
      • Musixmatch: No ISRC available | Search: track not found

[4/500] I Know - Brian Tyler
   ✗ Not found in both sources:
      • Genius: Track found but no lyrics available
      • Musixmatch: ISRC lookup: status 404 | Search: no lyrics in response
```

## Changes Made

### 1. Modified `get_lyrics_from_genius()` (Lines 118-145)

**Before:**
```python
def get_lyrics_from_genius(self, track_name: str, artist_name: str) -> Optional[Dict]:
    # ...
    if not song:
        return None  # No context!
```

**After:**
```python
def get_lyrics_from_genius(self, track_name: str, artist_name: str) -> tuple[Optional[Dict], str]:
    """Returns: Tuple of (lyrics_dict, status_message)"""

    if not self.genius:
        return None, "Genius API not initialized"

    if not song:
        return None, "Track not found in Genius"

    if not lyrics_text:
        return None, "Track found but no lyrics available"

    return lyrics_dict, "Success"
```

### 2. Modified `get_lyrics_from_musixmatch()` (Lines 147-232)

**Before:**
```python
def get_lyrics_from_musixmatch(...) -> Optional[Dict]:
    # Try ISRC
    # Try search
    return None  # No explanation!
```

**After:**
```python
def get_lyrics_from_musixmatch(...) -> tuple[Optional[Dict], str]:
    """Returns: Tuple of (lyrics_dict, status_message)"""

    failure_reasons = []

    # Try ISRC
    if isrc and isrc != 'N/A':
        if status_code == 200:
            return lyrics_dict, "Success"
        else:
            failure_reasons.append(f"ISRC lookup: status {status_code}")
    else:
        failure_reasons.append("No ISRC available")

    # Try search
    if status_code != 200:
        failure_reasons.append(f"Search: status {status_code}")

    if not track_list:
        failure_reasons.append("Search: track not found")

    return None, " | ".join(failure_reasons)
```

### 3. Modified `process_single_song()` (Lines 234-263)

**Before:**
```python
def process_single_song(self, song: Dict) -> Optional[Dict]:
    lyrics = self.get_lyrics_from_genius(track_name, artist_name)
    if lyrics:
        return {**song, 'lyrics': lyrics, 'lyrics_source': 'genius'}

    # No status tracking
```

**After:**
```python
def process_single_song(self, song: Dict) -> tuple[Optional[Dict], Dict[str, str]]:
    status_logs = {
        'genius': '',
        'musixmatch': ''
    }

    lyrics, genius_status = self.get_lyrics_from_genius(track_name, artist_name)
    status_logs['genius'] = genius_status
    if lyrics:
        return {**song, 'lyrics': lyrics, 'lyrics_source': 'genius'}, status_logs

    lyrics, musixmatch_status = self.get_lyrics_from_musixmatch(isrc, track_name, artist_name)
    status_logs['musixmatch'] = musixmatch_status

    return None, status_logs  # Return logs even on failure
```

### 4. Modified `process_batch()` Display Logic (Lines 302-326)

**Before:**
```python
if result and result.get('lyrics'):
    print(f"   ✓ Found via {source.upper()}")
else:
    print(f"   ✗ Not found")  # Vague!
```

**After:**
```python
if result and result.get('lyrics'):
    print(f"   ✓ Found via {source.upper()}")
else:
    # Display detailed failure reasons
    print(f"   ✗ Not found in both sources:")
    if status_logs.get('genius'):
        print(f"      • Genius: {status_logs['genius']}")
    if status_logs.get('musixmatch'):
        print(f"      • Musixmatch: {status_logs['musixmatch']}")
```

## Musixmatch Failure Reason Examples

### Common Scenarios

**1. No ISRC, Track Not in Database:**
```
• Musixmatch: No ISRC available | Search: track not found
```

**2. ISRC Found, But No Lyrics:**
```
• Musixmatch: ISRC lookup: no lyrics in response | Search: no lyrics in response
```

**3. Rate Limited:**
```
• Musixmatch: ISRC lookup: JSONDecodeError | Search: invalid API response
```

**4. Track Found, Status Error:**
```
• Musixmatch: ISRC lookup: status 404 | Search: status 404
```

**5. Partial Success (ISRC works):**
```
✓ Found via MUSIXMATCH_ISRC
```

**6. Partial Success (Search works):**
```
✓ Found via MUSIXMATCH_SEARCH
```

## Genius Failure Reason Examples

**1. Track Doesn't Exist:**
```
• Genius: Track not found in Genius
```

**2. Track Exists, No Lyrics:**
```
• Genius: Track found but no lyrics available
```

**3. API Disabled:**
```
• Genius: Genius API not initialized
```

**4. API Error:**
```
• Genius: Genius API error: Timeout after 15 seconds
```

## Benefits

### For Users
- **Clear understanding** of why lyrics weren't found
- **Debugging capability**: Can identify API issues vs. legitimate "not found"
- **Transparency**: See both sources being tried

### For Developers
- **Better diagnostics**: Identify patterns in failures
- **API monitoring**: Detect rate limiting or outages
- **Data quality**: Understand coverage gaps (ISRC availability, etc.)

### For Analysis
- Can aggregate failure reasons to understand:
  - What percentage failed due to no ISRC?
  - What percentage failed at search stage?
  - Are there systematic API errors?

## Example Complete Output

```
[1/500] Stereo Love - Edward Maya
   ✓ Found via GENIUS

[2/500] Walking in the Rain to a Café - City Girl
   ✗ Not found in both sources:
      • Genius: Track not found in Genius
      • Musixmatch: No ISRC available | Search: track not found

[3/500] Hello World - Brian Tyler
   ✗ Not found in both sources:
      • Genius: Track found but no lyrics available
      • Musixmatch: ISRC lookup: no lyrics in response | Search: track not found

[4/500] Shape of You - Ed Sheeran
   ✓ Found via MUSIXMATCH_ISRC
```

## Files Modified

1. **libraries/analysis/process_lyrics_batch.py**
   - `get_lyrics_from_genius()`: Now returns tuple with status
   - `get_lyrics_from_musixmatch()`: Now returns tuple with detailed failure pipeline
   - `process_single_song()`: Collects and returns status logs
   - `process_batch()`: Displays detailed failure information

## Testing

Run the processor and verify:
```bash
python libraries/analysis/process_lyrics_batch.py
```

Expected: Each failed track shows exactly why both Genius and Musixmatch couldn't find lyrics.

## Future Enhancements

Potential additions:
1. **JSON logging**: Save failure reasons to progress file for analysis
2. **Statistics**: Count failures by reason type
3. **Retry logic**: Automatically retry specific failure types (timeouts, rate limits)
4. **Alternative sources**: Add more fallback APIs based on failure patterns

## Conclusion

This enhancement provides complete transparency into the lyrics lookup process. Users now understand exactly why tracks fail and can make informed decisions about:
- Whether to try manual lookups
- Whether to wait and retry (if rate limited)
- Whether lyrics simply don't exist for a track
