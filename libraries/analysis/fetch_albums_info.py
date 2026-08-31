"""
Fetch Album Information from Spotify API

This script fetches complete album information from Spotify Web API.

Features:
- Idempotent processing (resume capability)
- Advanced rate limiting (30-second rolling window)
- Batch API (20 albums per request)
- Incremental saving every 10 albums
- Proper 429 error handling with Retry-After header
- Searches for albums by name and artist if not in streaming data

Requirements:
    pip install spotipy python-dotenv

Environment Variables:
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

Usage:
    python fetch_albums_info.py
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
UNIQUE_ALBUMS_CSV = DATA_DIR / 'unique_albums.csv'
ALBUMS_INFO_JSON = OUTPUT_DIR / 'data' / 'albums_info.json'
SAVE_INTERVAL = 10
BATCH_SIZE = 20  # Spotify allows 20 albums per request


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


class AlbumInfoFetcher:
    """Fetches album information from Spotify API."""

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

    def load_albums_csv(self) -> List[Dict]:
        """Load unique albums from CSV."""
        if not UNIQUE_ALBUMS_CSV.exists():
            raise FileNotFoundError(f"{UNIQUE_ALBUMS_CSV} not found. Run extract_unique_entities.py first.")

        albums = []
        with UNIQUE_ALBUMS_CSV.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                albums.append(row)

        return albums

    def load_progress(self) -> Dict:
        """Load existing progress from JSON."""
        if not ALBUMS_INFO_JSON.exists():
            return {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'last_updated': None,
                'processing_started': datetime.now().isoformat(),
                'albums': []
            }

        with ALBUMS_INFO_JSON.open('r', encoding='utf-8') as f:
            return json.load(f)

    def get_processed_album_keys(self, progress: Dict) -> Set[str]:
        """Extract set of already processed album keys (album_name|artist_name)."""
        return {f"{album['album_name']}|{album['artist_name']}" for album in progress.get('albums', [])}

    def save_progress(self, progress: Dict):
        """Save progress to JSON file."""
        progress['last_updated'] = datetime.now().isoformat()
        ALBUMS_INFO_JSON.parent.mkdir(parents=True, exist_ok=True)
        with ALBUMS_INFO_JSON.open('w', encoding='utf-8') as f:
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

    def search_album_by_name(self, album_name: str, artist_name: str) -> Optional[Dict]:
        """
        Search for album by name and artist, return the best match.

        Returns:
            Album object or None if not found
        """
        try:
            # Search with both album and artist
            search_query = f'album:"{album_name}" artist:"{artist_name}"'
            results = self._make_api_call(
                self.spotify.search,
                q=search_query,
                type='album',
                limit=5
            )

            if results and 'albums' in results and results['albums']['items']:
                # Find best match
                for album in results['albums']['items']:
                    album_match = album['name'].lower() == album_name.lower()
                    artist_match = any(
                        a['name'].lower() == artist_name.lower()
                        for a in album['artists']
                    )

                    if album_match and artist_match:
                        return album

                # Return first result if exact match not found
                return results['albums']['items'][0]

            return None

        except Exception as e:
            print(f"   ✗ Error searching for album '{album_name}': {e}")
            return None

    def fetch_albums_batch(self, album_ids: List[str]) -> List[Dict]:
        """
        Fetch multiple albums in a single request (20 per batch).

        Args:
            album_ids: List of Spotify album IDs

        Returns:
            List of album objects
        """
        if not album_ids:
            return []

        results = []
        for i in range(0, len(album_ids), BATCH_SIZE):
            batch = album_ids[i:i + BATCH_SIZE]
            batch = [aid for aid in batch if aid]  # Filter out None/empty

            if not batch:
                continue

            albums_data = self._make_api_call(self.spotify.albums, batch)

            if albums_data and 'albums' in albums_data:
                results.extend([a for a in albums_data['albums'] if a])
            else:
                results.extend([None] * len(batch))

        return results

    def process_albums(self, albums_list: List[Dict], progress: Dict) -> Dict:
        """Process a list of albums."""
        print(f"\n{'='*70}")
        print(f"PROCESSING {len(albums_list)} ALBUMS")
        print(f"{'='*70}\n")

        batch_results = []
        successful = 0
        failed = 0

        for idx, album_row in enumerate(albums_list, 1):
            album_name = album_row['album_name']
            artist_name = album_row['artist_name']
            total_plays = int(album_row.get('total_plays', 0))

            print(f"[{idx}/{len(albums_list)}] {album_name} - {artist_name}")

            # Try to get album info
            album_info = None

            # If we have an album_id, use batch fetch
            album_id = album_row.get('album_id')
            if album_id:
                print(f"   → Fetching by ID: {album_id}")
                albums = self.fetch_albums_batch([album_id])
                if albums and albums[0]:
                    album_info = albums[0]

            # If no ID or fetch failed, search by name
            if not album_info:
                print(f"   → Searching by name: {album_name}")
                album_info = self.search_album_by_name(album_name, artist_name)

            if album_info:
                # Extract artist info from album
                artist_ids = [a['id'] for a in album_info.get('artists', [])]
                artist_names = [a['name'] for a in album_info.get('artists', [])]

                record = {
                    'album_id': album_info['id'],
                    'album_uri': album_info['uri'],
                    'album_name': album_info['name'],
                    'artist_ids': artist_ids,
                    'artist_names': artist_names,
                    'artist_name': artist_names[0] if artist_names else artist_name,
                    'release_date': album_info.get('release_date'),
                    'release_date_precision': album_info.get('release_date_precision'),
                    'total_tracks': album_info.get('total_tracks', 0),
                    'album_type': album_info.get('album_type'),
                    'label': album_info.get('label'),
                    'genres': album_info.get('genres', []),
                    'popularity': album_info.get('popularity', 0),
                    'images': album_info.get('images', []),
                    'external_urls': album_info.get('external_urls', {}),
                    'total_plays_in_history': total_plays,
                    'fetched_at': datetime.now().isoformat()
                }

                batch_results.append(record)
                successful += 1
                print(f"   ✓ Found - Released: {record['release_date']}, Tracks: {record['total_tracks']}")

            else:
                failed += 1
                print(f"   ✗ Not found")

            # Save progress incrementally
            if idx % SAVE_INTERVAL == 0:
                progress['albums'].extend(batch_results)
                progress['total_processed'] += len(batch_results)
                progress['successful'] += successful
                progress['failed'] += failed
                self.save_progress(progress)
                batch_results = []
                successful = 0
                failed = 0
                print(f"   → Progress saved ({idx} albums processed)")

        # Save remaining results
        if batch_results:
            progress['albums'].extend(batch_results)
            progress['total_processed'] += len(batch_results)
            progress['successful'] += successful
            progress['failed'] += failed
            self.save_progress(progress)

        return progress


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("  ALBUM INFO FETCHER")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output: {ALBUMS_INFO_JSON}\n")

    try:
        # Initialize fetcher
        print("Initializing Spotify API client...")
        fetcher = AlbumInfoFetcher(rate_limit=180)
        print("✓ Client initialized\n")

        # Load albums list
        print("Loading unique albums from CSV...")
        albums_list = fetcher.load_albums_csv()
        print(f"✓ Loaded {len(albums_list)} total albums\n")

        # Load progress
        print("Loading existing progress...")
        progress = fetcher.load_progress()
        processed_keys = fetcher.get_processed_album_keys(progress)
        print(f"✓ Already processed: {len(processed_keys)} albums\n")

        # Filter unprocessed
        unprocessed = [
            album for album in albums_list
            if f"{album['album_name']}|{album['artist_name']}" not in processed_keys
        ]

        print(f"📝 Albums to process: {len(unprocessed)}")
        print(f"   • Already done: {len(processed_keys)}")
        print(f"   • Remaining: {len(unprocessed)}\n")

        if not unprocessed:
            print("✓ All albums already processed!")
            return

        # Process albums
        progress = fetcher.process_albums(unprocessed, progress)

        # Final summary
        print(f"\n{'='*70}")
        print("PROCESSING COMPLETED!")
        print(f"{'='*70}")
        print(f"Total albums processed: {progress['total_processed']}")
        print(f"Successful: {progress['successful']}")
        print(f"Failed: {progress['failed']}")
        print(f"Output saved to: {ALBUMS_INFO_JSON}")

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
