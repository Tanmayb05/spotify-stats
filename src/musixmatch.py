"""
Musixmatch Lyrics Fetcher

This script extracts unique Spotify track URIs from JSON streaming data,
retrieves their ISRC codes via Spotify API, and fetches lyrics using Musixmatch API.

Requirements:
    pip install spotipy python-dotenv musicxmatch-api

Environment Variables:
    SPOTIFY_CLIENT_ID - Spotify API client ID
    SPOTIFY_CLIENT_SECRET - Spotify API client secret
"""

import json
import os
from pathlib import Path
from typing import Set, Dict, Optional, List
from datetime import datetime
import random
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from musicxmatch_api import MusixMatchAPI
import time

# Load environment variables
load_dotenv()

class LyricsFetcher:
    """Handles fetching lyrics for Spotify tracks via Musixmatch API."""

    def __init__(self):
        """Initialize API clients."""
        # Spotify API setup
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in environment variables")

        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.spotify = spotipy.Spotify(auth_manager=auth_manager)

        # Musixmatch API setup using musicxmatch_api library
        self.musixmatch = MusixMatchAPI()

    def extract_unique_track_uris(self, data_dir: str = "data") -> Set[str]:
        """
        Extract all unique Spotify track URIs from JSON files in the data directory.

        Args:
            data_dir: Directory containing JSON streaming data files

        Returns:
            Set of unique track URIs
        """
        track_uris = set()
        data_path = Path(data_dir)

        json_files = list(data_path.glob("*.json"))
        print(f"Found {len(json_files)} JSON files in {data_dir}/")

        for json_file in json_files:
            print(f"Processing {json_file.name}...")
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for entry in data:
                    track_uri = entry.get('spotify_track_uri')
                    # Only add if it's a valid track URI (not null and is a track)
                    if track_uri and track_uri.startswith('spotify:track:'):
                        track_uris.add(track_uri)

            except Exception as e:
                print(f"Error processing {json_file.name}: {e}")
                continue

        print(f"\nTotal unique tracks found: {len(track_uris)}")
        return track_uris

    def get_track_isrc(self, track_uri: str) -> Optional[Dict[str, str]]:
        """
        Get ISRC code and track metadata from Spotify API.

        Args:
            track_uri: Spotify track URI (e.g., 'spotify:track:7IatLQIKChU9gt0OexdEXp')

        Returns:
            Dict with track info including ISRC, or None if not found
        """
        try:
            # Extract track ID from URI
            track_id = track_uri.split(':')[-1]

            # Get track details from Spotify
            track = self.spotify.track(track_id)

            isrc = track.get('external_ids', {}).get('isrc')

            return {
                'track_id': track_id,
                'track_uri': track_uri,
                'name': track['name'],
                'artist': ', '.join([artist['name'] for artist in track['artists']]),
                'album': track['album']['name'],
                'isrc': isrc
            }

        except Exception as e:
            print(f"Error fetching ISRC for {track_uri}: {e}")
            return None

    def get_lyrics_by_isrc(self, isrc: str, track_name: str = "", artist_name: str = "") -> Optional[Dict]:
        """
        Get lyrics from Musixmatch API using ISRC code.
        Falls back to searching by track name and artist if ISRC fails.

        Args:
            isrc: International Standard Recording Code
            track_name: Track name (for fallback search)
            artist_name: Artist name (for fallback search)

        Returns:
            Dict with lyrics data, or None if not found
        """
        try:
            # Try 1: Get lyrics directly using ISRC
            lyrics_data = self.musixmatch.get_track_lyrics(track_isrc=isrc)

            if lyrics_data and lyrics_data.get('message', {}).get('header', {}).get('status_code') == 200:
                lyrics_body = lyrics_data['message']['body']['lyrics']

                # Also get track info for track_id
                track_data = self.musixmatch.get_track(track_isrc=isrc)
                track_id = None
                if track_data and track_data.get('message', {}).get('header', {}).get('status_code') == 200:
                    track_id = track_data['message']['body']['track']['track_id']

                return {
                    'track_id': track_id,
                    'lyrics_body': lyrics_body.get('lyrics_body'),
                    'lyrics_language': lyrics_body.get('lyrics_language'),
                    'script_tracking_url': lyrics_body.get('script_tracking_url'),
                    'pixel_tracking_url': lyrics_body.get('pixel_tracking_url'),
                    'lyrics_copyright': lyrics_body.get('lyrics_copyright'),
                    'updated_time': lyrics_body.get('updated_time'),
                    'lookup_method': 'isrc'
                }

            # Try 2: ISRC failed, search by track name and artist
            print(f"   ⚠ ISRC lookup failed, trying search by name/artist...")

            if not track_name or not artist_name:
                print(f"   ✗ No track name/artist provided for fallback search")
                return None

            # Build search query
            search_query = f"{track_name} {artist_name}"

            # Search for the track using search_tracks method
            search_data = self.musixmatch.search_tracks(track_query=search_query, page=1)

            if not search_data or search_data.get('message', {}).get('header', {}).get('status_code') != 200:
                print(f"   ✗ Track not found in search: {track_name} - {artist_name}")
                return None

            track_list = search_data['message']['body']['track_list']
            if not track_list:
                print(f"   ✗ No results found in search")
                return None

            # Get the first (best) match
            track_id = track_list[0]['track']['track_id']
            matched_track_name = track_list[0]['track']['track_name']
            matched_artist = track_list[0]['track']['artist_name']
            print(f"   ✓ Found track via search")
            print(f"      Match: {matched_track_name} - {matched_artist} (ID: {track_id})")

            # Now get lyrics using track_id
            lyrics_data = self.musixmatch.get_track_lyrics(track_id=track_id)

            if not lyrics_data or lyrics_data.get('message', {}).get('header', {}).get('status_code') != 200:
                print(f"   ✗ Lyrics not found for track_id {track_id}")
                return None

            lyrics_body = lyrics_data['message']['body']['lyrics']

            return {
                'track_id': track_id,
                'lyrics_body': lyrics_body.get('lyrics_body'),
                'lyrics_language': lyrics_body.get('lyrics_language'),
                'script_tracking_url': lyrics_body.get('script_tracking_url'),
                'pixel_tracking_url': lyrics_body.get('pixel_tracking_url'),
                'lyrics_copyright': lyrics_body.get('lyrics_copyright'),
                'updated_time': lyrics_body.get('updated_time'),
                'lookup_method': 'search'
            }

        except Exception as e:
            print(f"   ✗ Error fetching lyrics: {e}")
            return None

    def process_single_track(self, track_uri: str) -> Optional[Dict]:
        """
        Complete workflow: Get ISRC from Spotify and fetch lyrics from Musixmatch.

        Args:
            track_uri: Spotify track URI

        Returns:
            Dict with track info and lyrics
        """
        track_start = time.time()
        timestamp = datetime.now().strftime("%H:%M:%S")

        print(f"\n{'='*60}")
        print(f"[{timestamp}] Processing: {track_uri}")
        print(f"{'='*60}")

        # Step 1: Get ISRC from Spotify
        step1_start = time.time()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] → Fetching track info from Spotify...")
        track_info = self.get_track_isrc(track_uri)
        step1_time = time.time() - step1_start

        if not track_info:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ Failed to get track info ({step1_time:.2f}s)")
            return None

        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Track info retrieved ({step1_time:.2f}s)")
        print(f"   • Track: {track_info['name']}")
        print(f"   • Artist: {track_info['artist']}")
        print(f"   • Album: {track_info['album']}")
        print(f"   • ISRC: {track_info['isrc']}")

        if not track_info['isrc']:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ No ISRC found for this track")
            return None

        # Step 2: Get lyrics from Musixmatch using ISRC
        time.sleep(0.5)  # Rate limiting
        step2_start = time.time()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] → Fetching lyrics from Musixmatch...")

        lyrics_data = self.get_lyrics_by_isrc(
            track_info['isrc'],
            track_name=track_info['name'],
            artist_name=track_info['artist']
        )
        step2_time = time.time() - step2_start

        if not lyrics_data:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ No lyrics found ({step2_time:.2f}s)")
            return {**track_info, 'lyrics': None}

        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Lyrics retrieved ({step2_time:.2f}s)")
        print(f"   • Language: {lyrics_data.get('lyrics_language')}")
        print(f"   • Copyright: {lyrics_data.get('lyrics_copyright')}")

        total_time = time.time() - track_start
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Completed in {total_time:.2f}s total")

        return {
            **track_info,
            'lyrics': lyrics_data
        }


def main():
    """Main execution function - test with 10 random songs."""

    script_start = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "="*70)
    print("  SPOTIFY LYRICS FETCHER - MUSIXMATCH INTEGRATION")
    print("="*70)
    print(f"Started at: {start_timestamp}\n")

    try:
        # Initialize fetcher
        init_start = time.time()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing API clients...")
        fetcher = LyricsFetcher()
        init_time = time.time() - init_start
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Initialized ({init_time:.2f}s)\n")

        # Step 1: Extract all unique track URIs
        step1_start = time.time()
        print("=" * 70)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] STEP 1/3: Extracting unique track URIs")
        print("=" * 70)
        track_uris = fetcher.extract_unique_track_uris()
        step1_time = time.time() - step1_start

        if not track_uris:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ No track URIs found in data directory")
            return

        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Step 1 completed ({step1_time:.2f}s)")
        print(f"   • Total unique tracks found: {len(track_uris)}\n")

        # Step 2: Select 10 random tracks for testing
        step2_start = time.time()
        print("=" * 70)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] STEP 2/3: Selecting random tracks")
        print("=" * 70)
        track_list = list(track_uris)
        num_tracks = min(10, len(track_list))  # In case there are fewer than 10 tracks
        random_tracks = random.sample(track_list, num_tracks)
        step2_time = time.time() - step2_start
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Step 2 completed ({step2_time:.2f}s)")
        print(f"   • Selected {num_tracks} tracks for processing\n")

        # Step 3: Process the tracks
        step3_start = time.time()
        print("=" * 70)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] STEP 3/3: Processing tracks")
        print("=" * 70)

        results: List[Dict] = []
        failed_tracks: List[Dict] = []
        successful = 0
        failed = 0

        for idx, track_uri in enumerate(random_tracks, 1):
            print(f"\n{'─' * 70}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Track {idx}/{num_tracks}")
            print(f"{'─' * 70}")

            track_start = time.time()
            result = fetcher.process_single_track(track_uri)
            track_time = time.time() - track_start

            if result and result.get('lyrics'):
                results.append(result)
                successful += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ SUCCESS - Track processed ({track_time:.2f}s)")
            else:
                # Add to failed list with track info but no lyrics
                if result:
                    failed_tracks.append({
                        'track_id': result.get('track_id'),
                        'track_uri': result.get('track_uri'),
                        'name': result.get('name'),
                        'artist': result.get('artist'),
                        'album': result.get('album'),
                        'isrc': result.get('isrc'),
                        'reason': 'No lyrics found'
                    })
                else:
                    failed_tracks.append({
                        'track_uri': track_uri,
                        'reason': 'Failed to fetch track info from Spotify'
                    })
                failed += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ FAILED - Track processing failed ({track_time:.2f}s)")

            # Rate limiting between requests
            if idx < num_tracks:
                time.sleep(1)  # Wait 1 second between tracks

        step3_time = time.time() - step3_start

        # Summary
        print("\n" + "="*70)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] PROCESSING COMPLETE")
        print("="*70)
        print(f"✓ Successful: {successful}/{num_tracks} ({(successful/num_tracks*100):.1f}%)")
        print(f"✗ Failed: {failed}/{num_tracks} ({(failed/num_tracks*100):.1f}%)")
        print(f"⏱ Total processing time: {step3_time:.2f}s")
        print(f"⏱ Average per track: {step3_time/num_tracks:.2f}s\n")

        # Save results
        save_start = time.time()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Saving results...")

        # Create outputs directory if it doesn't exist
        output_dir = Path("outputs/lyrics")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save results to file with timestamp
        output_file = output_dir / f"{timestamp}-lyrics.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': timestamp,
                'started_at': start_timestamp,
                'completed_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_processed': num_tracks,
                'successful': successful,
                'failed': failed,
                'execution_time': {
                    'initialization': round(init_time, 2),
                    'step1_extraction': round(step1_time, 2),
                    'step2_selection': round(step2_time, 2),
                    'step3_processing': round(step3_time, 2),
                    'total': round(time.time() - script_start, 2)
                },
                'tracks': results,
                'failed_tracks': failed_tracks
            }, f, indent=2, ensure_ascii=False)

        save_time = time.time() - save_start
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ Results saved ({save_time:.2f}s)")
        print(f"   • File: {output_file}")
        print(f"   • Tracks with lyrics: {len(results)}")
        if failed_tracks:
            print(f"   • Failed tracks: {len(failed_tracks)}")

        # Final summary
        total_time = time.time() - script_start
        print("\n" + "="*70)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] EXECUTION SUMMARY")
        print("="*70)
        print(f"⏱ Initialization: {init_time:.2f}s")
        print(f"⏱ Step 1 (Extraction): {step1_time:.2f}s")
        print(f"⏱ Step 2 (Selection): {step2_time:.2f}s")
        print(f"⏱ Step 3 (Processing): {step3_time:.2f}s")
        print(f"⏱ Saving: {save_time:.2f}s")
        print(f"{'─' * 70}")
        print(f"⏱ TOTAL TIME: {total_time:.2f}s")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✗ FATAL ERROR: {e}")
        raise


if __name__ == "__main__":
    main()