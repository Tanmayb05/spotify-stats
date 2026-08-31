"""
Fetch Track Information from Spotify API with Genre Enrichment

This script fetches complete track information and enriches with artist genres.

IMPORTANT: Since Spotify doesn't provide genres directly on tracks, this script:
1. Fetches track information from Spotify API
2. Extracts artist IDs from the track object
3. Loads artist genres from artists_info.json (must be created first!)
4. Enriches track with genres from all associated artists

Features:
- Idempotent processing (resume capability)
- Advanced rate limiting (30-second rolling window)
- Batch API (50 tracks per request)
- Incremental saving every 10 tracks
- Proper 429 error handling with Retry-After header
- Genre enrichment from artist data

Requirements:
    pip install spotipy python-dotenv

Environment Variables:
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

Prerequisites:
    1. Run extract_unique_entities.py first
    2. Run fetch_artists_info.py BEFORE this script (required for genres!)

Usage:
    python fetch_tracks_info.py
"""

import json
import os
import csv
import time
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from collections import deque
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException

from path_utils import DATA_DIR, OUTPUT_DIR

# Load environment variables
repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(repo_root / 'spotify-insights.env')

# Constants
UNIQUE_TRACKS_CSV = DATA_DIR / 'unique_tracks.csv'
ARTISTS_INFO_JSON = OUTPUT_DIR / 'data' / 'artists_info.json'
TRACKS_INFO_JSON = OUTPUT_DIR / 'data' / 'tracks_info.json'
SAVE_INTERVAL = 10
BATCH_SIZE = 50  # Spotify allows 50 tracks per request


class RateLimiter:
    """Rate limiter for Spotify API based on 30-second rolling window."""

    def __init__(self, max_calls_per_30s: int = 180):
        self.max_calls = max_calls_per_30s
        self.window_seconds = 30
        self.calls = deque()
        self.total_calls = 0
        self.total_429_errors = 0

    def can_make_call(self) -> bool:
        self._cleanup_old_calls()
        return len(self.calls) < self.max_calls

    def _cleanup_old_calls(self):
        cutoff_time = datetime.now() - timedelta(seconds=self.window_seconds)
        while self.calls and self.calls[0] < cutoff_time:
            self.calls.popleft()

    def record_call(self):
        self.calls.append(datetime.now())
        self.total_calls += 1

    def wait_if_needed(self):
        while not self.can_make_call():
            self._cleanup_old_calls()
            if not self.can_make_call():
                oldest_call = self.calls[0]
                wait_time = (oldest_call + timedelta(seconds=self.window_seconds) - datetime.now()).total_seconds()
                if wait_time > 0:
                    print(f"   ⏳ Rate limit reached. Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time + 0.5)

    def handle_429_error(self, retry_after: Optional[int] = None):
        self.total_429_errors += 1
        wait_time = retry_after if retry_after else 60
        print(f"   ⚠️  429 Error #{self.total_429_errors}: Waiting {wait_time}s...")
        time.sleep(wait_time)
        self.calls.clear()

    def get_stats(self) -> Dict:
        self._cleanup_old_calls()
        return {
            'total_calls': self.total_calls,
            'calls_in_window': len(self.calls),
            'max_calls': self.max_calls,
            'total_429_errors': self.total_429_errors,
            'utilization': f"{(len(self.calls) / self.max_calls * 100):.1f}%"
        }


class TrackInfoFetcher:
    """Fetches track information from Spotify API and enriches with genres."""

    def __init__(self, rate_limit: int = 180):
        # Spotify API
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET required")

        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.spotify = spotipy.Spotify(auth_manager=auth_manager)
        self.rate_limiter = RateLimiter(max_calls_per_30s=rate_limit)

        # Load artist genres lookup
        self.artist_genres = self._load_artist_genres()

        print("✓ Spotify API initialized")
        print(f"✓ Rate limiter configured: {rate_limit} calls per 30s")
        print(f"✓ Loaded genres for {len(self.artist_genres)} artists")

    def _load_artist_genres(self) -> Dict[str, List[str]]:
        """
        Load artist genres from artists_info.json.

        Returns:
            Dictionary mapping artist_id -> genres list
        """
        if not ARTISTS_INFO_JSON.exists():
            print(f"\n⚠️  WARNING: {ARTISTS_INFO_JSON} not found!")
            print("   Genre enrichment will not be possible.")
            print("   Please run fetch_artists_info.py first.\n")
            return {}

        try:
            with ARTISTS_INFO_JSON.open('r', encoding='utf-8') as f:
                artists_data = json.load(f)

            artist_genres = {}
            for artist in artists_data.get('artists', []):
                artist_id = artist.get('artist_id')
                genres = artist.get('genres', [])
                if artist_id:
                    artist_genres[artist_id] = genres

            return artist_genres

        except Exception as e:
            print(f"\n⚠️  Error loading artist genres: {e}")
            return {}

    def load_tracks_csv(self) -> List[Dict]:
        """Load unique tracks from CSV."""
        if not UNIQUE_TRACKS_CSV.exists():
            raise FileNotFoundError(f"{UNIQUE_TRACKS_CSV} not found. Run extract_unique_entities.py first.")

        tracks = []
        with UNIQUE_TRACKS_CSV.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tracks.append(row)

        return tracks

    def load_progress(self) -> Dict:
        """Load existing progress from JSON."""
        if not TRACKS_INFO_JSON.exists():
            return {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'tracks_with_genres': 0,
                'last_updated': None,
                'processing_started': datetime.now().isoformat(),
                'tracks': []
            }

        with TRACKS_INFO_JSON.open('r', encoding='utf-8') as f:
            return json.load(f)

    def get_processed_track_ids(self, progress: Dict) -> Set[str]:
        """Extract set of already processed track IDs."""
        return {track['track_id'] for track in progress.get('tracks', [])}

    def save_progress(self, progress: Dict):
        """Save progress to JSON file."""
        progress['last_updated'] = datetime.now().isoformat()
        TRACKS_INFO_JSON.parent.mkdir(parents=True, exist_ok=True)
        with TRACKS_INFO_JSON.open('w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)

    def _make_api_call(self, api_func, *args, **kwargs):
        """Make an API call with rate limiting and error handling."""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                self.rate_limiter.wait_if_needed()
                result = api_func(*args, **kwargs)
                self.rate_limiter.record_call()
                return result

            except SpotifyException as e:
                if e.http_status == 429:
                    retry_after = int(e.headers.get('Retry-After', 60))
                    self.rate_limiter.handle_429_error(retry_after)
                    retry_count += 1
                    continue
                else:
                    print(f"   ✗ Spotify API error: {e}")
                    return None

            except Exception as e:
                print(f"   ✗ Unexpected error: {e}")
                return None

        print(f"   ✗ Max retries exceeded for API call")
        return None

    def fetch_tracks_batch(self, track_ids: List[str]) -> List[Dict]:
        """
        Fetch multiple tracks in a single request (50 per batch).

        Args:
            track_ids: List of Spotify track IDs

        Returns:
            List of track objects
        """
        if not track_ids:
            return []

        results = []
        for i in range(0, len(track_ids), BATCH_SIZE):
            batch = track_ids[i:i + BATCH_SIZE]
            batch = [tid for tid in batch if tid]  # Filter out None/empty

            if not batch:
                continue

            tracks_data = self._make_api_call(self.spotify.tracks, batch)

            if tracks_data and 'tracks' in tracks_data:
                results.extend([t for t in tracks_data['tracks'] if t])
            else:
                results.extend([None] * len(batch))

        return results

    def enrich_with_genres(self, track_info: Dict) -> List[str]:
        """
        Enrich track with genres from its artists and album (fallback).

        Strategy:
        1. Try to get genres from all artists on the track
        2. If no artist genres found, use album genres as fallback
        3. Deduplicate while preserving order

        Args:
            track_info: Spotify track object

        Returns:
            List of genres (aggregated from artists and album)
        """
        if not track_info:
            return []

        all_genres = []

        # Try to get genres from artists
        if 'artists' in track_info:
            for artist in track_info['artists']:
                artist_id = artist.get('id')
                if artist_id and artist_id in self.artist_genres:
                    artist_genres = self.artist_genres[artist_id]
                    all_genres.extend(artist_genres)

        # Fallback to album genres if no artist genres found
        if not all_genres and 'album' in track_info:
            album_genres = track_info['album'].get('genres', [])
            all_genres.extend(album_genres)

        # Deduplicate while preserving order
        seen = set()
        unique_genres = []
        for genre in all_genres:
            if genre not in seen:
                seen.add(genre)
                unique_genres.append(genre)

        return unique_genres

    def process_tracks(self, tracks_list: List[Dict], progress: Dict) -> Dict:
        """Process a list of tracks with genre enrichment."""
        print(f"\n{'='*70}")
        print(f"PROCESSING {len(tracks_list)} TRACKS")
        print(f"{'='*70}\n")

        batch_results = []
        successful = 0
        failed = 0
        tracks_with_genres = 0

        for idx, track_row in enumerate(tracks_list, 1):
            track_name = track_row['track_name']
            artist_name = track_row['artist_name']
            track_id = track_row['track_id']
            total_plays = int(track_row.get('total_plays', 0))

            print(f"[{idx}/{len(tracks_list)}] {track_name} - {artist_name}")

            # Fetch track info
            if not track_id:
                print(f"   ✗ No track ID")
                failed += 1
                continue

            tracks_data = self.fetch_tracks_batch([track_id])
            track_info = tracks_data[0] if tracks_data else None

            if track_info:
                # Enrich with genres from artists
                genres = self.enrich_with_genres(track_info)

                # Extract artist information
                artist_ids = [a['id'] for a in track_info.get('artists', [])]
                artist_names = [a['name'] for a in track_info.get('artists', [])]

                # Extract album information
                album_info = track_info.get('album', {})
                album_id = album_info.get('id')
                album_name = album_info.get('name')

                record = {
                    'track_id': track_info['id'],
                    'track_uri': track_info['uri'],
                    'track_name': track_info['name'],
                    'artist_ids': artist_ids,
                    'artist_names': artist_names,
                    'album_id': album_id,
                    'album_name': album_name,
                    'genres': genres,  # ENRICHED from artists!
                    'duration_ms': track_info.get('duration_ms'),
                    'popularity': track_info.get('popularity', 0),
                    'explicit': track_info.get('explicit', False),
                    'isrc': track_info.get('external_ids', {}).get('isrc'),
                    'preview_url': track_info.get('preview_url'),
                    'track_number': track_info.get('track_number'),
                    'disc_number': track_info.get('disc_number'),
                    'external_urls': track_info.get('external_urls', {}),
                    'total_plays_in_history': total_plays,
                    'first_played_date': track_row.get('first_played_date'),
                    'last_played_date': track_row.get('last_played_date'),
                    'fetched_at': datetime.now().isoformat()
                }

                batch_results.append(record)
                successful += 1
                if genres:
                    tracks_with_genres += 1
                    print(f"   ✓ Found - Genres: {', '.join(genres[:3])}{'...' if len(genres) > 3 else ''}")
                else:
                    print(f"   ✓ Found - No genres available")

            else:
                failed += 1
                print(f"   ✗ Not found")

            # Save progress incrementally
            if idx % SAVE_INTERVAL == 0:
                progress['tracks'].extend(batch_results)
                progress['total_processed'] += len(batch_results)
                progress['successful'] += successful
                progress['failed'] += failed
                progress['tracks_with_genres'] += tracks_with_genres
                self.save_progress(progress)
                batch_results = []
                successful = 0
                failed = 0
                tracks_with_genres = 0
                print(f"   → Progress saved ({idx} tracks processed)")

        # Save remaining results
        if batch_results:
            progress['tracks'].extend(batch_results)
            progress['total_processed'] += len(batch_results)
            progress['successful'] += successful
            progress['failed'] += failed
            progress['tracks_with_genres'] += tracks_with_genres
            self.save_progress(progress)

        return progress


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("  TRACK INFO FETCHER (with Genre Enrichment)")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output: {TRACKS_INFO_JSON}\n")

    try:
        # Initialize fetcher
        print("Initializing Spotify API client...")
        fetcher = TrackInfoFetcher(rate_limit=180)
        print("✓ Client initialized\n")

        # Load tracks list
        print("Loading unique tracks from CSV...")
        tracks_list = fetcher.load_tracks_csv()
        print(f"✓ Loaded {len(tracks_list)} total tracks\n")

        # Load progress
        print("Loading existing progress...")
        progress = fetcher.load_progress()
        processed_ids = fetcher.get_processed_track_ids(progress)
        print(f"✓ Already processed: {len(processed_ids)} tracks\n")

        # Filter unprocessed
        unprocessed = [
            track for track in tracks_list
            if track['track_id'] not in processed_ids
        ]

        print(f"📝 Tracks to process: {len(unprocessed)}")
        print(f"   • Already done: {len(processed_ids)}")
        print(f"   • Remaining: {len(unprocessed)}\n")

        if not unprocessed:
            print("✓ All tracks already processed!")
            return

        # Process tracks
        progress = fetcher.process_tracks(unprocessed, progress)

        # Final summary
        print(f"\n{'='*70}")
        print("PROCESSING COMPLETED!")
        print(f"{'='*70}")
        print(f"Total tracks processed: {progress['total_processed']}")
        print(f"Successful: {progress['successful']}")
        print(f"Failed: {progress['failed']}")
        print(f"Tracks with genres: {progress.get('tracks_with_genres', 0)}")
        genre_percentage = (progress.get('tracks_with_genres', 0) / progress['total_processed'] * 100) if progress['total_processed'] > 0 else 0
        print(f"Genre coverage: {genre_percentage:.1f}%")
        print(f"Output saved to: {TRACKS_INFO_JSON}")

        stats = fetcher.rate_limiter.get_stats()
        print(f"\n📊 Rate Limiter Stats:")
        print(f"   • Total API calls: {stats['total_calls']}")
        print(f"   • Total 429 errors: {stats['total_429_errors']}")
        print(f"{'='*70}\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        print("Progress has been saved. Run again to resume.")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
