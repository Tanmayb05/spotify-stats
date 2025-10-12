# Phase 2: Moods & Audio Features - Setup Guide

## Overview
Phase 2 adds mood analysis based on Spotify's audio features: valence (happiness), energy, and danceability.

## Prerequisites
- Spotify Developer Account
- Python 3.8+
- Your Spotify streaming data in `data/` directory

## Setup Instructions

### 1. Get Spotify API Credentials

1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account
3. Click "Create app"
4. Fill in:
   - **App name**: Spotify Stats (or any name)
   - **App description**: Personal listening statistics
   - **Redirect URI**: http://localhost (not used but required)
5. Accept the terms and click "Save"
6. Click "Settings" to view your credentials
7. Copy your **Client ID** and **Client Secret**

### 2. Configure Backend Environment

1. Copy the example env file:
   ```bash
   cp backend/.env.example backend/.env
   ```

2. Edit `backend/.env` and add your credentials:
   ```
   SPOTIFY_CLIENT_ID=your_client_id_here
   SPOTIFY_CLIENT_SECRET=your_client_secret_here
   ```

### 3. Install New Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate  # On Windows

# Install new packages
pip install -r backend/requirements.txt
```

### 4. Run Audio Features Enrichment Job

This job fetches audio features from Spotify API and caches them locally:

```bash
python3 -m backend.jobs.enrich_audio_features
```

**What it does:**
- Scans your streaming history for unique tracks
- Searches Spotify for each track
- Fetches audio features (valence, energy, danceability, etc.)
- Caches results in `data/audio_features.json`
- Shows progress every 10 tracks
- Rate-limited to avoid API throttling (0.1s delay between requests)

**Expected time:** ~5-15 minutes for 1000 unique tracks

**Note:** The job is resumable. If interrupted, run it again and it will skip already-cached tracks.

### 5. Restart Backend

Restart your backend to load the new audio features:

```bash
# Stop existing backend (Ctrl+C)
# Then restart:
cd backend
uvicorn app.main:app --reload --port 3011
```

Or use the start script:
```bash
./start.sh
```

### 6. Verify Setup

1. Check backend is running: http://localhost:3011/health
2. Test mood endpoint: http://localhost:3011/api/mood/summary?window=30d
3. Open frontend: http://localhost:3010
4. Navigate to "Moods" page

## API Endpoints

### GET /api/mood/summary
Get mood metrics for a time window.

**Parameters:**
- `window`: `7d`, `30d`, `90d`, or `all` (default: `30d`)

**Response:**
```json
{
  "window_days": 30,
  "avg_valence": 0.542,
  "avg_energy": 0.678,
  "avg_danceability": 0.623,
  "sample_size": 1234
}
```

### GET /api/mood/contexts
Compare moods across contexts (weekday/weekend, platforms).

**Response:**
```json
{
  "weekday_vs_weekend": {
    "weekday": {
      "avg_valence": 0.520,
      "avg_energy": 0.670,
      "avg_danceability": 0.610,
      "sample_size": 890
    },
    "weekend": {
      "avg_valence": 0.580,
      "avg_energy": 0.690,
      "avg_danceability": 0.650,
      "sample_size": 344
    }
  },
  "by_platform": {
    "iOS": {...},
    "Android": {...}
  }
}
```

### GET /api/mood/monthly
Get monthly mood trends over time.

**Response:**
```json
[
  {
    "month": "2024-01",
    "avg_valence": 0.542,
    "avg_energy": 0.678,
    "avg_danceability": 0.623,
    "sample_size": 456
  },
  ...
]
```

## Understanding Audio Features

### Valence (Happiness)
- **Range:** 0.0 to 1.0
- **Description:** Musical positiveness. High valence = more positive/happy/cheerful
- **Examples:**
  - High (0.8-1.0): Upbeat pop, happy songs
  - Low (0.0-0.2): Sad/melancholic tracks

### Energy
- **Range:** 0.0 to 1.0
- **Description:** Intensity and activity level
- **Examples:**
  - High (0.8-1.0): Fast, loud, noisy (rock, metal, EDM)
  - Low (0.0-0.2): Calm, soft (ambient, classical)

### Danceability
- **Range:** 0.0 to 1.0
- **Description:** How suitable for dancing based on tempo, rhythm stability, beat strength
- **Examples:**
  - High (0.8-1.0): Dance, hip-hop, Latin
  - Low (0.0-0.2): Spoken word, irregular rhythms

## Features

### Mood Ring
- Three circular progress indicators showing current averages
- Color-coded: Valence (green), Energy (teal), Danceability (aqua)
- Icons: Happy face, lightning bolt, music note

### Monthly Trends
- Line chart showing all three metrics over time
- Smooth curves (catmullRom interpolation)
- Interactive legend
- Time range from your first to latest listen

### Context Comparisons
- **Weekday vs Weekend:** Bar chart comparing mood metrics
- **By Platform:** Horizontal bars for each platform (min 10 samples)

### Time Windows
- Last 7 days
- Last 30 days (default)
- Last 90 days
- All time

## Troubleshooting

### "No audio features data available yet"
- Run the enrichment job: `python3 -m backend.jobs.enrich_audio_features`
- Make sure `data/audio_features.json` exists
- Restart backend after enrichment

### "Spotify API credentials not configured"
- Check `backend/.env` file exists
- Verify SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are set
- No quotes needed around values

### "Error loading mood data"
- Check backend is running: http://localhost:3011/health
- Check backend logs for errors
- Verify CORS allows your frontend origin

### Enrichment Job Fails
- Verify Spotify credentials are correct
- Check internet connection
- Spotify API might be rate limiting - wait and retry
- Check if your app is still active on Spotify dashboard

## Deployment Notes

### Render Environment Variables
Add these to your Render web service:
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`

### Running Enrichment Job on Production
```bash
# SSH into Render or run via Render Shell
python3 -m backend.jobs.enrich_audio_features

# Or add as a cron job (Render Cron Jobs)
```

### Updating Audio Features
- Re-run enrichment job periodically to get features for new tracks
- Job is smart about caching - only fetches missing tracks
- Recommended: Run weekly or monthly

## Next Phase
Phase 3 will add:
- Artist discovery timeline
- Loyalty metrics
- Obsession periods
- Reflective insights

For more details, see: `documentation/20251012_010000_phase_2_moods_audio_features.md`
