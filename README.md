# Spotify Streaming History Analysis

A comprehensive analysis of my Spotify streaming history from 2018 to 2025, featuring automated data analysis, visualizations, and interactive dashboards.

## Overview

This project analyzes **71,052 streams** spanning **7 years** of listening history, totaling **3,244 hours** (135 days) of music and podcasts.

### Key Statistics
- **Unique Tracks**: 11,803
- **Unique Artists**: 4,344
- **Unique Albums**: 8,283
- **Platforms Used**: 53
- **Countries**: 5
- **Longest Listening Streak**: 118 consecutive days

## Project Structure

```
spotify-stats/
├── data/                  # Raw JSON streaming data (5 audio files + 1 video file)
├── src/                   # Python analysis scripts (original)
├── backend/               # FastAPI REST API
├── frontend/              # React + Material-UI web app
├── outputs/               # Generated visualizations and reports
│   ├── images/           # PNG charts and graphs
│   ├── data/             # CSV reports and statistics
│   └── dashboards/       # Interactive HTML dashboards
├── start.sh              # Start frontend & backend servers (macOS)
├── stop.sh               # Stop all servers (macOS)
└── README.md
```

## Web Application (NEW!)

An interactive web dashboard built with React and FastAPI for exploring your Spotify streaming history.

### 🚀 Live Deployment

The application is deployed and accessible at:

- **Frontend**: [tanmays-spotify-stats.netlify.app](https://tanmays-spotify-stats.netlify.app)
- **Backend API**: [https://tanmays-spotify-stats.onrender.com](https://tanmays-spotify-stats.onrender.com)
- **API Docs**: [https://tanmays-spotify-stats.onrender.com/docs](https://tanmays-spotify-stats.onrender.com/docs)

**Deployment Dashboards** (for management):
- **Netlify Dashboard**: [https://app.netlify.com/projects/tanmays-spotify-stats/overview](https://app.netlify.com/projects/tanmays-spotify-stats/overview)
- **Render Dashboard**: [https://dashboard.render.com/web/srv-d3lia0umcj7s739v028g/events](https://dashboard.render.com/web/srv-d3lia0umcj7s739v028g/events)

### Quick Start (macOS)

```bash
# Start both frontend and backend servers in Terminal tabs
./start.sh

# Access the dashboard
open http://localhost:3010
```

The start script will:
- Open Terminal with 2 tabs
- Start backend API on port **3011** (first tab)
- Start frontend React app on port **3010** (second tab)

### Stopping Servers

```bash
# Stop all servers and clean up Terminal
./stop.sh
```

### Features

- **Overview Dashboard**: Real-time statistics with 70,817 streams analyzed
- **Interactive Charts**: Monthly trends, top artists/tracks, platform distribution
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Dark Theme**: Spotify-inspired design with #1DB954 green
- **Fast Performance**: Parallel API requests and optimized data loading

### Manual Setup

If you prefer to run servers manually:

```bash
# Terminal 1: Backend (port 3011)
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --port 3011

# Terminal 2: Frontend (port 3010)
cd frontend
npm run dev
```

### API Documentation

- **Interactive API Docs**: http://localhost:3011/docs
- **ReDoc**: http://localhost:3011/redoc
- **Health Check**: http://localhost:3011/health

## Setup (Python Analysis Scripts)

### Prerequisites
```bash
# Python 3.8 or higher required
python3 --version
```

### Installation

1. Clone or navigate to the project directory:
```bash
cd spotify-stats
```

2. Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install pandas numpy matplotlib seaborn
```

## Running the Analyses

### Run All Analyses
Execute all analysis scripts at once:
```bash
source .venv/bin/activate
python3 src/run_all_analyses.py
```

### Run Individual Analyses
Each script can also be run independently:
```bash
python3 src/explore_data.py
python3 src/listening_patterns.py
python3 src/artist_discovery.py
# ... etc
```

## Analysis Scripts

### 1. Data Exploration (`explore_data.py`)
**Purpose**: Core analysis of streaming history with essential statistics and visualizations

**Outputs**:
- **Visualizations** (8 PNG files):
  - `top_artists.png` - Top 20 most streamed artists
  - `top_tracks.png` - Top 20 most played tracks
  - `listening_over_time.png` - Monthly streaming trends
  - `listening_by_hour.png` - Hourly listening patterns
  - `listening_by_day.png` - Activity by day of week
  - `platform_usage.png` - Platform distribution
  - `skip_behavior.png` - Artists with highest/lowest skip rates
  - `yearly_comparison.png` - Year-over-year comparison

- **Data Files** (3 CSV files):
  - `top_50_artists.csv` - Top 50 artists by stream count
  - `top_50_tracks.csv` - Top 50 tracks by stream count
  - `monthly_summary.csv` - Monthly aggregated statistics

### 2. Listening Patterns (`listening_patterns.py`)
**Purpose**: Deep dive into listening habits, sessions, and temporal patterns

**Outputs**:
- **Visualizations** (4 PNG files):
  - `session_duration_distribution.png` - Distribution of listening session lengths
  - `weekend_vs_weekday_patterns.png` - Weekend vs weekday comparison
  - `listening_heatmap.png` - Day-hour heatmap of activity
  - `monthly_diversity_chart.png` - Artist diversity over time

- **Data Files** (6 CSV files):
  - `top_20_binge_sessions.csv` - Longest listening sessions
  - `session_statistics.csv` - Session analytics (avg duration, tracks per session)
  - `weekend_vs_weekday.csv` - Detailed weekend/weekday comparison
  - `peak_listening_hours.csv` - Top 10 peak listening hours
  - `listening_streaks.csv` - Consecutive listening day streaks
  - `most_repeated_tracks.csv` - Tracks played on repeat

### 3. Artist Discovery (`artist_discovery.py`)
**Purpose**: Analyze artist discovery timeline, loyalty, and preference evolution

**Outputs**:
- **Visualizations** (3 PNG files):
  - `artist_discovery_by_year.png` - New artists discovered each year
  - `artist_loyalty_analysis.png` - Artist loyalty metrics
  - `artist_evolution_over_years.png` - Top artists evolution timeline

- **Data Files** (6 CSV files):
  - `artists_discovered_per_year.csv` - Annual artist discovery
  - `artists_discovered_per_month.csv` - Monthly artist discovery
  - `most_loyal_artists.csv` - Artists with highest loyalty scores
  - `longest_listening_span_artists.csv` - Artists listened to across longest time periods
  - `monthly_top_artist.csv` - #1 artist for each month
  - `artist_obsession_periods.csv` - Periods of artist obsession (>30% monthly share)
  - `one_hit_wonders.csv` - Artists played only once (2,081 artists)
  - `artist_yearly_streams.csv` - Year-by-year artist streaming data

### 4. Detailed Statistics (`detailed_stats.py`)
**Purpose**: Comprehensive statistical reports and milestone tracking

**Outputs**:
- **Data Files** (9 CSV files):
  - `comprehensive_statistics.csv` - Overall statistics summary
  - `platform_detailed_stats.csv` - Platform usage breakdown
  - `country_listening_stats.csv` - Listening by country
  - `top_100_albums.csv` - Most played albums
  - `reason_start_analysis.csv` - Why tracks started playing
  - `reason_end_analysis.csv` - Why tracks stopped playing
  - `daily_statistics.csv` - Day-by-day statistics
  - `top_10_streaming_days.csv` - Highest streaming days
  - `most_completed_tracks.csv` - Tracks played to completion
  - `most_skipped_tracks.csv` - Most frequently skipped tracks
  - `listening_milestones.csv` - Listening achievement milestones

### 5. Advanced Visualizations (`advanced_visualizations.py`)
**Purpose**: Complex visualizations and multi-dimensional analysis

**Outputs**:
- **Visualizations** (5 PNG files):
  - `listening_calendar_2025.png` - Calendar heatmap of daily activity
  - `listening_momentum.png` - Listening momentum trends
  - `artist_timeline_bands.png` - Artist listening timelines
  - `listening_intensity_scatter.png` - Stream intensity analysis

- **Data Files** (2 CSV files):
  - `artist_co_listening.csv` - Artists often listened to together
  - `monthly_patterns_summary.csv` - Monthly pattern summaries

### 6. Google Charts Dashboard (`google_charts_viz.py`)
**Purpose**: Interactive web dashboard with Google Charts

**Outputs**:
- **Dashboard** (1 HTML file):
  - `spotify_dashboard.html` - Interactive dashboard featuring:
    - Statistics cards (total streams, hours, artists, tracks)
    - Top artists bar chart
    - Listening over time line chart
    - Hourly pattern chart
    - Day of week distribution
    - Platform pie chart
    - Yearly comparison

### 7. Advanced Google Charts Dashboard (`google_charts_advanced.py`)
**Purpose**: Advanced interactive visualizations

**Outputs**:
- **Dashboard** (1 HTML file):
  - `spotify_advanced_dashboard.html` - Advanced dashboard featuring:
    - Top tracks interactive table
    - Day-hour heatmap
    - Artist evolution over time
    - Artist treemap visualization

## Output Summary

After running all analyses, you'll have:
- **15+ PNG visualizations** in `outputs/images/`
- **30+ CSV data files** in `outputs/data/`
- **2 interactive HTML dashboards** in `outputs/dashboards/`

### Viewing the Dashboards

Open the HTML dashboards in your browser:
```bash
# Main dashboard
open outputs/dashboards/spotify_dashboard.html

# Advanced dashboard
open outputs/dashboards/spotify_advanced_dashboard.html
```

## Data Structure

### Data Files
The `data/` directory contains:
- `streaming_2018-2020_0.json` - Streaming data 2018-2020
- `streaming_2020-2022_1.json` - Streaming data 2020-2022
- `streaming_2022-2023_2.json` - Streaming data 2022-2023
- `streaming_2023-2024_3.json` - Streaming data 2023-2024
- `streaming_2024-2025_4.json` - Streaming data 2024-2025
- `streaming_video_2018-2025.json` - Video/podcast streaming data

### JSON Structure
Each streaming record contains:
- **ts**: Timestamp (when track stopped playing)
- **ms_played**: Milliseconds played
- **master_metadata_track_name**: Track name
- **master_metadata_album_artist_name**: Artist name
- **master_metadata_album_album_name**: Album name
- **platform**: Playback platform
- **conn_country**: Country code
- **shuffle**: Shuffle mode (true/false)
- **skipped**: Whether track was skipped
- **offline**: Offline mode status
- **incognito_mode**: Private session status
- **reason_start**: Why track started
- **reason_end**: Why track ended
- Plus additional metadata fields

## Key Insights

Based on the analysis:
- **Listening Behavior**: 28.6% streams use shuffle mode, 8.9% skip rate
- **Private Sessions**: 1.3% of streams in incognito mode
- **Offline Listening**: 2.2% of streams played offline
- **Session Patterns**: Longest binge session identified, average session metrics tracked
- **Artist Discovery**: 2,081 one-hit wonder artists, 7 artist obsession periods
- **Consistency**: 118-day listening streak achieved
- **Repeat Behavior**: Maximum 34 consecutive repeats of single track

## Privacy & Data Source

This data was obtained through Spotify's GDPR data request. The data contains personal information (IP addresses, location data, listening history) and should not be shared publicly.

## License

Personal data - all rights reserved.
