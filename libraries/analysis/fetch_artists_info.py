"""
Fetch Artist Information from Spotify API

This script fetches complete artist information including genres from Spotify Web API.
IMPORTANT: Must run BEFORE fetch_tracks_info.py as tracks need artist genres.

Features:
- Idempotent processing (resume capability)
- Advanced rate limiting (30-second rolling window)
- Batch API (50 artists per request)
- Incremental saving every 10 artists
- Proper 429 error handling with Retry-After header
- Searches for artists by name if not in streaming data

Requirements:
    pip install spotipy python-dotenv

Environment Variables:
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

Usage:
    python fetch_artists_info.py
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
UNIQUE_ARTISTS_CSV = DATA_DIR / 'unique_artists.csv'
ARTISTS_INFO_JSON = OUTPUT_DIR / 'data' / 'artists_info.json'
SAVE_INTERVAL = 10
BATCH_SIZE = 50  # Spotify allows 50 artists per request


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


class ArtistInfoFetcher:
    """Fetches artist information from Spotify API."""

    def __init__(self, rate_limit: int = 180):
        # Spotify API
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET required")

        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.spotify = spotipy.Spotify(auth_manager=auth_manager)
        self.rate_limiter = RateLimiter(max_calls_per_30s=rate_limit)

        print("✓ Spotify API initialized")
        print(f"✓ Rate limiter configured: {rate_limit} calls per 30s")

    def load_artists_csv(self) -> List[Dict]:
        """Load unique artists from CSV."""
        if not UNIQUE_ARTISTS_CSV.exists():
            raise FileNotFoundError(f"{UNIQUE_ARTISTS_CSV} not found. Run extract_unique_entities.py first.")

        artists = []
        with UNIQUE_ARTISTS_CSV.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                artists.append(row)

        return artists

    def load_progress(self) -> Dict:
        """Load existing progress from JSON."""
        if not ARTISTS_INFO_JSON.exists():
            return {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'last_updated': None,
                'processing_started': datetime.now().isoformat(),
                'artists': []
            }

        with ARTISTS_INFO_JSON.open('r', encoding='utf-8') as f:
            return json.load(f)

    def get_processed_artist_names(self, progress: Dict) -> Set[str]:
        """Extract set of already processed artist names."""
        return {artist['artist_name'] for artist in progress.get('artists', [])}

    def save_progress(self, progress: Dict):
        """Save progress to JSON file."""
        progress['last_updated'] = datetime.now().isoformat()
        ARTISTS_INFO_JSON.parent.mkdir(parents=True, exist_ok=True)
        with ARTISTS_INFO_JSON.open('w', encoding='utf-8') as f:
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

    def search_artist_by_name(self, artist_name: str) -> Optional[Dict]:
        """
        Search for artist by name and return the best match.

        Returns:
            Artist object or None if not found
        """
        try:
            results = self._make_api_call(
                self.spotify.search,
                q=f'artist:"{artist_name}"',
                type='artist',
                limit=1
            )

            if results and 'artists' in results and results['artists']['items']:
                artist = results['artists']['items'][0]
                # Verify it's a reasonable match (case-insensitive)
                if artist['name'].lower() == artist_name.lower():
                    return artist
                # Allow partial match if very close
                if artist_name.lower() in artist['name'].lower() or artist['name'].lower() in artist_name.lower():
                    return artist

            return None

        except Exception as e:
            print(f"   ✗ Error searching for artist '{artist_name}': {e}")
            return None

    def fetch_artists_batch(self, artist_ids: List[str]) -> List[Dict]:
        """
        Fetch multiple artists in a single request (50 per batch).

        Args:
            artist_ids: List of Spotify artist IDs

        Returns:
            List of artist objects
        """
        if not artist_ids:
            return []

        results = []
        for i in range(0, len(artist_ids), BATCH_SIZE):
            batch = artist_ids[i:i + BATCH_SIZE]
            batch = [aid for aid in batch if aid]  # Filter out None/empty

            if not batch:
                continue

            artists_data = self._make_api_call(self.spotify.artists, batch)

            if artists_data and 'artists' in artists_data:
                results.extend([a for a in artists_data['artists'] if a])
            else:
                results.extend([None] * len(batch))

        return results

    def process_artists(self, artists_list: List[Dict], progress: Dict) -> Dict:
        """Process a list of artists."""
        print(f"\n{'='*70}")
        print(f"PROCESSING {len(artists_list)} ARTISTS")
        print(f"{'='*70}\n")

        batch_results = []
        successful = 0
        failed = 0

        for idx, artist_row in enumerate(artists_list, 1):
            artist_name = artist_row['artist_name']
            total_plays = int(artist_row.get('total_plays', 0))

            print(f"[{idx}/{len(artists_list)}] {artist_name}")

            # Try to get artist info
            artist_info = None

            # If we have an artist_id, use batch fetch
            artist_id = artist_row.get('artist_id')
            if artist_id:
                print(f"   → Fetching by ID: {artist_id}")
                artists = self.fetch_artists_batch([artist_id])
                if artists and artists[0]:
                    artist_info = artists[0]

            # If no ID or fetch failed, search by name
            if not artist_info:
                print(f"   → Searching by name: {artist_name}")
                artist_info = self.search_artist_by_name(artist_name)

            if artist_info:
                record = {
                    'artist_id': artist_info['id'],
                    'artist_uri': artist_info['uri'],
                    'artist_name': artist_info['name'],
                    'genres': artist_info.get('genres', []),
                    'popularity': artist_info.get('popularity', 0),
                    'followers': artist_info.get('followers', {}).get('total', 0),
                    'images': artist_info.get('images', []),
                    'external_urls': artist_info.get('external_urls', {}),
                    'total_plays_in_history': total_plays,
                    'fetched_at': datetime.now().isoformat()
                }

                batch_results.append(record)
                successful += 1
                print(f"   ✓ Found - Genres: {', '.join(record['genres'][:3]) if record['genres'] else 'None'}")

            else:
                failed += 1
                print(f"   ✗ Not found")

            # Save progress incrementally
            if idx % SAVE_INTERVAL == 0:
                progress['artists'].extend(batch_results)
                progress['total_processed'] += len(batch_results)
                progress['successful'] += successful
                progress['failed'] += failed
                self.save_progress(progress)
                batch_results = []
                successful = 0
                failed = 0
                print(f"   → Progress saved ({idx} artists processed)")

        # Save remaining results
        if batch_results:
            progress['artists'].extend(batch_results)
            progress['total_processed'] += len(batch_results)
            progress['successful'] += successful
            progress['failed'] += failed
            self.save_progress(progress)

        return progress


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("  ARTIST INFO FETCHER")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output: {ARTISTS_INFO_JSON}\n")

    try:
        # Initialize fetcher
        print("Initializing Spotify API client...")
        fetcher = ArtistInfoFetcher(rate_limit=180)
        print("✓ Client initialized\n")

        # Load artists list
        print("Loading unique artists from CSV...")
        artists_list = fetcher.load_artists_csv()
        print(f"✓ Loaded {len(artists_list)} total artists\n")

        # Load progress
        print("Loading existing progress...")
        progress = fetcher.load_progress()
        processed_names = fetcher.get_processed_artist_names(progress)
        print(f"✓ Already processed: {len(processed_names)} artists\n")

        # Filter unprocessed
        unprocessed = [
            artist for artist in artists_list
            if artist['artist_name'] not in processed_names
        ]

        print(f"📝 Artists to process: {len(unprocessed)}")
        print(f"   • Already done: {len(processed_names)}")
        print(f"   • Remaining: {len(unprocessed)}\n")

        if not unprocessed:
            print("✓ All artists already processed!")
            return

        # Process artists
        progress = fetcher.process_artists(unprocessed, progress)

        # Final summary
        print(f"\n{'='*70}")
        print("PROCESSING COMPLETED!")
        print(f"{'='*70}")
        print(f"Total artists processed: {progress['total_processed']}")
        print(f"Successful: {progress['successful']}")
        print(f"Failed: {progress['failed']}")
        print(f"Output saved to: {ARTISTS_INFO_JSON}")

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
