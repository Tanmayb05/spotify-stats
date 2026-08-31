"""
Fetch Comprehensive Song Information from Spotify API

This script fetches detailed song information from Spotify Web API for all tracks
in the processing queue with:
- Idempotent processing (resume capability)
- Advanced rate limiting (30-second rolling window)
- Batch API prioritization (Albums → Tracks → Artists)
- Incremental saving every 10 songs
- Proper 429 error handling with Retry-After header

Requirements:
    pip install spotipy python-dotenv

Environment Variables:
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

Usage:
    python fetch_spotify_song_info.py
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

# Load environment variables from spotify-insights.env
repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(repo_root / 'spotify-insights.env')

# Constants
BATCH_SIZE = 500
QUEUE_CSV = DATA_DIR / 'songs_processing_queue.csv'
SONGS_INFO_JSON = OUTPUT_DIR / 'data' / 'songs_info.json'
SAVE_INTERVAL = 10  # Save progress every N songs

# Spotify API Batch Limits
BATCH_LIMITS = {
    'albums': 20,
    'tracks': 50,
    'artists': 50
}


class RateLimiter:
    """
    Rate limiter for Spotify API based on 30-second rolling window.

    Tracks API calls and ensures we don't exceed the rate limit.
    Implements exponential backoff on 429 errors.
    """

    def __init__(self, max_calls_per_30s: int = 30):
        """
        Initialize rate limiter.

        Args:
            max_calls_per_30s: Maximum API calls allowed in 30 seconds
                             (default: 180 for development mode)
        """
        self.max_calls = max_calls_per_30s
        self.window_seconds = 30
        self.calls = deque()  # Store timestamps of API calls
        self.total_calls = 0
        self.total_429_errors = 0

    def can_make_call(self) -> bool:
        """Check if we can make an API call within rate limits."""
        self._cleanup_old_calls()
        return len(self.calls) < self.max_calls

    def _cleanup_old_calls(self):
        """Remove calls older than 30 seconds from the window."""
        cutoff_time = datetime.now() - timedelta(seconds=self.window_seconds)
        while self.calls and self.calls[0] < cutoff_time:
            self.calls.popleft()

    def record_call(self):
        """Record an API call timestamp."""
        self.calls.append(datetime.now())
        self.total_calls += 1

    def wait_if_needed(self):
        """Wait if we're at the rate limit."""
        while not self.can_make_call():
            self._cleanup_old_calls()
            if not self.can_make_call():
                # Calculate wait time
                oldest_call = self.calls[0]
                wait_time = (oldest_call + timedelta(seconds=self.window_seconds) - datetime.now()).total_seconds()
                if wait_time > 0:
                    print(f"   ⏳ Rate limit reached. Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time + 0.5)  # Add buffer

    def handle_429_error(self, retry_after: Optional[int] = None):
        """
        Handle 429 rate limit error.

        Args:
            retry_after: Seconds to wait from Retry-After header
        """
        self.total_429_errors += 1
        wait_time = retry_after if retry_after else 60
        print(f"   ⚠️  429 Error #{self.total_429_errors}: Waiting {wait_time}s (Retry-After: {retry_after})...")
        time.sleep(wait_time)
        # Clear recent calls to be safe
        self.calls.clear()

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        self._cleanup_old_calls()
        return {
            'total_calls': self.total_calls,
            'calls_in_window': len(self.calls),
            'max_calls': self.max_calls,
            'total_429_errors': self.total_429_errors,
            'utilization': f"{(len(self.calls) / self.max_calls * 100):.1f}%"
        }


class SpotifyInfoFetcher:
    """Fetches comprehensive song information from Spotify API."""

    def __init__(self, rate_limit: int = 180):
        """
        Initialize Spotify API client and rate limiter.

        Args:
            rate_limit: Max API calls per 30 seconds (180 for dev, higher for extended quota)
        """
        # Spotify API
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET required")

        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.spotify = spotipy.Spotify(auth_manager=auth_manager)

        # Rate limiter
        self.rate_limiter = RateLimiter(max_calls_per_30s=rate_limit)

        print("✓ Spotify API initialized")
        print(f"✓ Rate limiter configured: {rate_limit} calls per 30s")

    def load_processing_queue(self) -> List[Dict]:
        """Load the processing queue CSV."""
        if not QUEUE_CSV.exists():
            raise FileNotFoundError(f"{QUEUE_CSV} not found")

        songs = []
        with QUEUE_CSV.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                songs.append(row)

        return songs

    def load_progress(self) -> Dict:
        """Load existing progress from JSON."""
        if not SONGS_INFO_JSON.exists():
            return {
                'total_processed': 0,
                'last_updated': None,
                'processing_started': datetime.now().isoformat(),
                'songs': []
            }

        with SONGS_INFO_JSON.open('r', encoding='utf-8') as f:
            return json.load(f)

    def get_processed_track_ids(self, progress: Dict) -> Set[str]:
        """Extract set of already processed track IDs."""
        return {song['track_id'] for song in progress.get('songs', [])}

    def save_progress(self, progress: Dict):
        """Save progress to JSON file."""
        progress['last_updated'] = datetime.now().isoformat()
        SONGS_INFO_JSON.parent.mkdir(parents=True, exist_ok=True)
        with SONGS_INFO_JSON.open('w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)

    def _make_api_call(self, api_func, *args, **kwargs):
        """
        Make an API call with rate limiting and error handling.

        Args:
            api_func: Spotify API function to call
            *args, **kwargs: Arguments to pass to the function

        Returns:
            API response or None on error
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Wait if needed before making call
                self.rate_limiter.wait_if_needed()

                # Make the API call
                result = api_func(*args, **kwargs)

                # Record successful call
                self.rate_limiter.record_call()

                return result

            except SpotifyException as e:
                if e.http_status == 429:
                    # Rate limited - get Retry-After header
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
        Fetch track information in batch (50 tracks per request).

        Args:
            track_ids: List of Spotify track IDs

        Returns:
            List of track information dictionaries
        """
        results = []
        batch_limit = BATCH_LIMITS['tracks']

        for i in range(0, len(track_ids), batch_limit):
            batch = track_ids[i:i + batch_limit]
            tracks_data = self._make_api_call(self.spotify.tracks, batch)

            if tracks_data and 'tracks' in tracks_data:
                results.extend(tracks_data['tracks'])
            else:
                # Add None placeholders for failed fetches
                results.extend([None] * len(batch))

        return results

    def fetch_albums_batch(self, album_ids: List[str]) -> List[Dict]:
        """
        Fetch album information in batch (20 albums per request).
        HIGHEST PRIORITY - Called first.

        Args:
            album_ids: List of Spotify album IDs

        Returns:
            List of album information dictionaries
        """
        results = []
        batch_limit = BATCH_LIMITS['albums']

        for i in range(0, len(album_ids), batch_limit):
            batch = album_ids[i:i + batch_limit]
            albums_data = self._make_api_call(self.spotify.albums, batch)

            if albums_data and 'albums' in albums_data:
                results.extend(albums_data['albums'])
            else:
                # Add None placeholders for failed fetches
                results.extend([None] * len(batch))

        return results

    def fetch_artists_batch(self, artist_ids: List[str]) -> List[Dict]:
        """
        Fetch artist information in batch (50 artists per request).

        Args:
            artist_ids: List of Spotify artist IDs

        Returns:
            List of artist information dictionaries
        """
        results = []
        batch_limit = BATCH_LIMITS['artists']

        for i in range(0, len(artist_ids), batch_limit):
            batch = artist_ids[i:i + batch_limit]
            artists_data = self._make_api_call(self.spotify.artists, batch)

            if artists_data and 'artists' in artists_data:
                results.extend(artists_data['artists'])
            else:
                # Add None placeholders for failed fetches
                results.extend([None] * len(batch))

        return results

    def extract_id_from_uri(self, uri: str) -> str:
        """Extract Spotify ID from URI (e.g., 'spotify:track:XXX' -> 'XXX')."""
        if not uri or uri == 'N/A':
            return None
        return uri.split(':')[-1] if ':' in uri else uri

    def process_batch(self, batch: List[Dict], progress: Dict) -> Dict:
        """
        Process a batch of songs with batch API prioritization.

        Priority order:
        1. Albums (highest - most restrictive batch size)
        2. Tracks
        3. Artists (lowest)

        Args:
            batch: List of song dictionaries from CSV
            progress: Progress tracking dictionary

        Returns:
            Updated progress dictionary
        """
        print(f"\n{'='*70}")
        print(f"PROCESSING BATCH OF {len(batch)} SONGS")
        print(f"{'='*70}\n")

        # Extract IDs
        track_ids = []
        album_ids = []
        artist_ids_set = set()

        for song in batch:
            track_id = self.extract_id_from_uri(song.get('track_uri'))
            album_id = self.extract_id_from_uri(song.get('album_uri'))

            if track_id:
                track_ids.append(track_id)
            if album_id:
                album_ids.append(album_id)

        # Create ID to song mapping
        track_id_to_song = {self.extract_id_from_uri(s.get('track_uri')): s for s in batch}

        # PRIORITY 1: Fetch Albums (20 per request)
        print(f"[1/3] Fetching {len(album_ids)} unique albums...")
        albums_data = self.fetch_albums_batch(album_ids) if album_ids else []
        album_id_to_data = {a['id']: a for a in albums_data if a}
        print(f"   ✓ Retrieved {len([a for a in albums_data if a])}/{len(album_ids)} albums")

        # PRIORITY 2: Fetch Tracks (50 per request)
        print(f"\n[2/3] Fetching {len(track_ids)} tracks...")
        tracks_data = self.fetch_tracks_batch(track_ids) if track_ids else []
        track_id_to_data = {t['id']: t for t in tracks_data if t}
        print(f"   ✓ Retrieved {len([t for t in tracks_data if t])}/{len(track_ids)} tracks")

        # Extract artist IDs from track data
        for track in tracks_data:
            if track and 'artists' in track:
                for artist in track['artists']:
                    artist_ids_set.add(artist['id'])

        artist_ids = list(artist_ids_set)

        # PRIORITY 3: Fetch Artists (50 per request)
        print(f"\n[3/3] Fetching {len(artist_ids)} unique artists...")
        artists_data = self.fetch_artists_batch(artist_ids) if artist_ids else []
        artist_id_to_data = {a['id']: a for a in artists_data if a}
        print(f"   ✓ Retrieved {len([a for a in artists_data if a])}/{len(artist_ids)} artists")

        # Combine all data
        print(f"\n{'='*70}")
        print("COMBINING DATA AND SAVING")
        print(f"{'='*70}\n")

        batch_results = []
        for idx, song in enumerate(batch, 1):
            track_id = self.extract_id_from_uri(song.get('track_uri'))
            album_id = self.extract_id_from_uri(song.get('album_uri'))

            if not track_id:
                continue

            # Gather all info
            track_info = track_id_to_data.get(track_id)
            album_info = album_id_to_data.get(album_id)

            # Get artist info
            artist_info_list = []
            if track_info and 'artists' in track_info:
                for artist_ref in track_info['artists']:
                    artist_data = artist_id_to_data.get(artist_ref['id'])
                    if artist_data:
                        artist_info_list.append(artist_data)

            # Create combined record
            record = {
                'track_id': track_id,
                'track_uri': song.get('track_uri'),
                'track_name': song.get('track_name'),
                'artist_name': song.get('artist_name'),
                'album_name': song.get('album_name'),
                'isrc': song.get('isrc'),
                'total_plays': song.get('total_plays'),
                'first_played_date': song.get('first_played_date'),
                'last_played_date': song.get('last_played_date'),
                'track_info': track_info,
                'album_info': album_info,
                'artists_info': artist_info_list,
                'fetched_at': datetime.now().isoformat()
            }

            batch_results.append(record)

            # Save incrementally every SAVE_INTERVAL songs
            if idx % SAVE_INTERVAL == 0:
                progress['songs'].extend(batch_results)
                progress['total_processed'] += len(batch_results)
                self.save_progress(progress)
                batch_results = []
                print(f"[{idx}/{len(batch)}] Progress saved ({idx} songs processed)")

        # Save remaining results
        if batch_results:
            progress['songs'].extend(batch_results)
            progress['total_processed'] += len(batch_results)
            self.save_progress(progress)

        # Show rate limiter stats
        stats = self.rate_limiter.get_stats()
        print(f"\n📊 Rate Limiter Stats:")
        print(f"   • Total API calls: {stats['total_calls']}")
        print(f"   • Current window: {stats['calls_in_window']}/{stats['max_calls']} ({stats['utilization']})")
        print(f"   • 429 errors: {stats['total_429_errors']}")

        return progress


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("  SPOTIFY SONG INFO FETCHER")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Batch size: {BATCH_SIZE} songs")
    print(f"Save interval: Every {SAVE_INTERVAL} songs")
    print(f"Output: {SONGS_INFO_JSON}\n")

    try:
        # Initialize fetcher
        print("Initializing Spotify API client...")
        fetcher = SpotifyInfoFetcher(rate_limit=180)  # Adjust based on your quota
        print("✓ Client initialized\n")

        # Load queue and progress
        print("Loading processing queue...")
        queue = fetcher.load_processing_queue()
        print(f"✓ Loaded {len(queue)} total songs\n")

        print("Loading existing progress...")
        progress = fetcher.load_progress()
        processed_ids = fetcher.get_processed_track_ids(progress)
        print(f"✓ Already processed: {len(processed_ids)} songs\n")

        # Filter unprocessed songs
        unprocessed = [
            song for song in queue
            if fetcher.extract_id_from_uri(song.get('track_uri')) not in processed_ids
        ]

        print(f"📝 Songs to process: {len(unprocessed)}")
        print(f"   • Already done: {len(processed_ids)}")
        print(f"   • Remaining: {len(unprocessed)}\n")

        if not unprocessed:
            print("✓ All songs already processed!")
            return

        # Process in batches
        total_batches = (len(unprocessed) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num in range(total_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(unprocessed))
            batch = unprocessed[start_idx:end_idx]

            print(f"\n{'='*70}")
            print(f"BATCH {batch_num + 1}/{total_batches}")
            print(f"{'='*70}")

            progress = fetcher.process_batch(batch, progress)

            print(f"\n✓ Batch {batch_num + 1}/{total_batches} completed")
            print(f"   Total progress: {progress['total_processed']}/{len(queue)} songs")

        # Final summary
        print(f"\n{'='*70}")
        print("ALL PROCESSING COMPLETED!")
        print(f"{'='*70}")
        print(f"Total songs processed: {progress['total_processed']}")
        print(f"Output saved to: {SONGS_INFO_JSON}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        stats = fetcher.rate_limiter.get_stats()
        print(f"\n📊 Final Rate Limiter Stats:")
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
