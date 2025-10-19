"""
Extract Unique Songs & Create Processing Queue

This script:
1. Extracts all unique songs from JSON streaming data
2. Creates unique_songs.csv with basic information
3. Fetches Spotify metadata (ISRC, track_id) for all songs
4. Creates songs_processing_queue.csv ready for batch lyrics processing

Requirements:
    pip install spotipy python-dotenv pandas

Environment Variables:
    SPOTIFY_CLIENT_ID - Spotify API client ID
    SPOTIFY_CLIENT_SECRET - Spotify API client secret
"""

import json
import os
import csv
from pathlib import Path
from typing import Set, Dict, List, Optional, Union
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import time

from path_utils import DATA_DIR

# Load environment variables
load_dotenv()

UNIQUE_SONGS_CSV = DATA_DIR / 'unique_songs.csv'
PROCESSING_QUEUE_CSV = DATA_DIR / 'songs_processing_queue.csv'


class SongExtractor:
    """Extracts unique songs and prepares processing queue."""

    def __init__(self):
        """Initialize Spotify API client."""
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")

        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.spotify = spotipy.Spotify(auth_manager=auth_manager)

    def extract_unique_songs(self, data_dir: Union[str, Path] = DATA_DIR) -> tuple[List[Dict], Dict[str, Set[str]]]:
        """
        Extract all unique songs from JSON streaming data and group by album.

        Args:
            data_dir: Directory containing JSON streaming files

        Returns:
            Tuple of (unique_songs, album_to_tracks_mapping)
        """
        print("\n" + "="*70)
        print("STEP 1: EXTRACTING UNIQUE SONGS FROM JSON DATA")
        print("="*70)

        data_path = Path(data_dir)
        json_files = sorted([f for f in data_path.glob("*.json") if not f.name.startswith('.')])

        print(f"Found {len(json_files)} JSON files in {data_path}/")
        print(f"Starting extraction...\n")

        # Track unique songs and their metadata
        songs_data = {}
        track_stats = defaultdict(lambda: {
            'total_plays': 0,
            'first_played': None,
            'last_played': None
        })

        # Track album URI to track URIs mapping for batch fetching
        album_to_tracks = defaultdict(set)
        track_to_album = {}  # track_uri -> album_uri

        total_entries = 0
        valid_tracks = 0

        for file_idx, json_file in enumerate(json_files, 1):
            file_start = time.time()
            print(f"[{file_idx}/{len(json_files)}] Processing {json_file.name}...")

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                file_entries = len(data)
                total_entries += file_entries

                for entry in data:
                    track_uri = entry.get('spotify_track_uri')
                    album_uri = entry.get('spotify_album_uri')

                    # Only process valid track URIs
                    if not track_uri or not track_uri.startswith('spotify:track:'):
                        continue

                    track_name = entry.get('master_metadata_track_name')
                    artist_name = entry.get('master_metadata_album_artist_name')
                    album_name = entry.get('master_metadata_album_album_name')
                    timestamp = entry.get('ts')

                    if not track_name or not artist_name:
                        continue

                    valid_tracks += 1

                    # Store unique song info
                    if track_uri not in songs_data:
                        songs_data[track_uri] = {
                            'track_uri': track_uri,
                            'track_name': track_name,
                            'artist_name': artist_name,
                            'album_name': album_name or 'Unknown',
                            'album_uri': album_uri or None
                        }

                        # Map track to album for batch fetching
                        if album_uri and album_uri.startswith('spotify:album:'):
                            album_to_tracks[album_uri].add(track_uri)
                            track_to_album[track_uri] = album_uri

                    # Track statistics
                    track_stats[track_uri]['total_plays'] += 1

                    if timestamp:
                        ts_date = timestamp.split('T')[0]
                        if track_stats[track_uri]['first_played'] is None:
                            track_stats[track_uri]['first_played'] = ts_date
                            track_stats[track_uri]['last_played'] = ts_date
                        else:
                            if ts_date < track_stats[track_uri]['first_played']:
                                track_stats[track_uri]['first_played'] = ts_date
                            if ts_date > track_stats[track_uri]['last_played']:
                                track_stats[track_uri]['last_played'] = ts_date

                file_time = time.time() - file_start
                unique_so_far = len(songs_data)
                print(f"   ✓ {file_entries} entries | {unique_so_far} unique songs | {file_time:.2f}s")

            except Exception as e:
                print(f"   ✗ Error processing {json_file.name}: {e}")
                continue

        # Combine song data with stats
        unique_songs = []
        for track_uri, song_info in songs_data.items():
            stats = track_stats[track_uri]
            unique_songs.append({
                **song_info,
                'total_plays': stats['total_plays'],
                'first_played_date': stats['first_played'] or 'Unknown',
                'last_played_date': stats['last_played'] or 'Unknown'
            })

        print(f"\n{'='*70}")
        print(f"EXTRACTION COMPLETE")
        print(f"{'='*70}")
        print(f"✓ Total entries processed: {total_entries:,}")
        print(f"✓ Valid track entries: {valid_tracks:,}")
        print(f"✓ Unique songs extracted: {len(unique_songs):,}")
        print(f"✓ Unique albums found: {len(album_to_tracks):,}")
        print(f"✓ Deduplication rate: {(1 - len(unique_songs)/valid_tracks)*100:.1f}%\n")

        return unique_songs, album_to_tracks

    def save_unique_songs_csv(self, songs: List[Dict], output_path: Union[str, Path] = UNIQUE_SONGS_CSV):
        """Save unique songs to CSV."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nSaving unique songs to {output_path}...")

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['track_uri', 'track_name', 'artist_name', 'album_name',
                         'total_plays', 'first_played_date', 'last_played_date']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(songs)

        print(f"✓ Saved {len(songs)} songs to {output_path}")

    def fetch_albums_batch(self, album_ids: List[str]) -> Dict[str, Dict]:
        """
        Fetch multiple albums in a single API call (max 20 albums).

        Args:
            album_ids: List of Spotify album IDs (max 20)

        Returns:
            Dict mapping album_id to album data with tracks and ISRCs
        """
        try:
            # Spotify albums endpoint accepts max 20 IDs
            albums_data = self.spotify.albums(album_ids)

            result = {}
            for album in albums_data.get('albums', []):
                if not album:
                    continue

                album_id = album['id']
                tracks_info = {}

                # Extract track info and ISRC from album
                for track in album.get('tracks', {}).get('items', []):
                    track_id = track['id']
                    track_uri = f"spotify:track:{track_id}"

                    # Get ISRC from track (need individual track call for ISRC)
                    # Note: Album endpoint doesn't include ISRC, only individual track endpoint does
                    tracks_info[track_uri] = {
                        'track_id': track_id,
                        'track_name': track['name'],
                        'artist_name': track['artists'][0]['name'] if track.get('artists') else 'Unknown',
                        'album_id': album_id,
                        'album_uri': f"spotify:album:{album_id}",
                        'album_name': album['name']
                    }

                result[album_id] = {
                    'album_info': album,
                    'tracks': tracks_info
                }

            return result

        except Exception as e:
            print(f"      Error fetching album batch: {str(e)[:50]}")
            return {}

    def fetch_spotify_metadata(self, songs: List[Dict], album_to_tracks: Dict[str, Set[str]]) -> List[Dict]:
        """
        Fetch Spotify metadata (ISRC, track_id) for all songs with batch processing.

        Args:
            songs: List of unique songs

        Returns:
            Songs enriched with Spotify metadata
        """
        print("\n" + "="*70)
        print("STEP 2: FETCHING SPOTIFY METADATA (BATCH PROCESSING)")
        print("="*70)
        print(f"Total songs: {len(songs)}")
        print(f"Batch size: 50 songs")
        print(f"Rate limit: 0.35s per song (~3 req/sec, within 180/min limit)\n")

        # Check if queue CSV exists for resume capability
        queue_path = PROCESSING_QUEUE_CSV
        existing_songs = {}
        start_index = 0

        if queue_path.exists():
            print("Found existing processing queue - checking for completed songs...")
            with open(queue_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['isrc'] != 'N/A' and row['isrc']:
                        existing_songs[row['track_uri']] = row

            if existing_songs:
                print(f"✓ Found {len(existing_songs)} songs with existing metadata")
                print(f"→ Will skip these and fetch {len(songs) - len(existing_songs)} remaining songs\n")

        enriched_songs = []
        failed_count = 0
        success_count = 0
        batch_size = 50
        total_batches = (len(songs) + batch_size - 1) // batch_size

        batch_start_time = time.time()

        for batch_num in range(1, total_batches + 1):
            batch_start_idx = (batch_num - 1) * batch_size
            batch_end_idx = min(batch_num * batch_size, len(songs))
            batch = songs[batch_start_idx:batch_end_idx]

            # Progress bar
            progress = (batch_num / total_batches) * 100
            bar_length = 30
            filled = int((progress / 100) * bar_length)
            bar = '━' * filled + '░' * (bar_length - filled)

            print(f"Batch {batch_num}/{total_batches} [{batch_end_idx}/{len(songs)} songs] {bar} {progress:.1f}%")

            batch_success = 0
            batch_failed = 0

            for i, song in enumerate(batch, 1):
                track_uri = song['track_uri']

                # Skip if already have metadata
                if track_uri in existing_songs:
                    enriched_songs.append(existing_songs[track_uri])
                    success_count += 1
                    continue

                max_retries = 3
                retry_count = 0
                success = False

                while retry_count < max_retries and not success:
                    try:
                        api_start = time.time()

                        # Extract track ID from URI
                        track_id = track_uri.split(':')[-1]

                        # Get track details from Spotify with rate limit handling
                        track = self.spotify.track(track_id)
                        isrc = track.get('external_ids', {}).get('isrc')

                        api_time = time.time() - api_start

                        enriched_songs.append({
                            **song,
                            'track_id': track_id,
                            'isrc': isrc or 'N/A',
                            'processed': False,
                            'lyrics_found': False,
                            'lyrics_source': '',
                            'batch_number': 0,
                            'processed_timestamp': ''
                        })

                        batch_success += 1
                        success_count += 1
                        success = True

                        # Show progress for each song
                        print(f"  ✓ [{i}/{len(batch)}] {song['track_name'][:40]:<40} - {song['artist_name'][:20]:<20} ({api_time:.2f}s)")

                        # Rate limiting: ~3 requests/second (well within 180/min limit)
                        time.sleep(0.35)

                    except Exception as e:
                        error_msg = str(e)

                        # Check if it's a rate limit error (429)
                        if '429' in error_msg or 'rate limit' in error_msg.lower():
                            retry_count += 1

                            # Try to extract Retry-After from error message
                            retry_after = 60  # Default to 60 seconds
                            if 'Retry will occur after:' in error_msg:
                                try:
                                    # Extract the number from the error message
                                    import re
                                    match = re.search(r'after:\s*(\d+)', error_msg)
                                    if match:
                                        retry_after = int(match.group(1))
                                        if retry_after > 3600:  # If it's a timestamp, it's too large
                                            retry_after = min(retry_after, 300)  # Cap at 5 minutes
                                except:
                                    pass

                            if retry_count < max_retries:
                                print(f"  ⚠ [{i}/{len(batch)}] Rate limit hit! Waiting {retry_after}s before retry {retry_count}/{max_retries}...")
                                time.sleep(retry_after)
                            else:
                                print(f"  ✗ [{i}/{len(batch)}] {song['track_name'][:40]:<40} - Max retries reached")
                                # Still add to queue but without ISRC
                                enriched_songs.append({
                                    **song,
                                    'track_id': song['track_uri'].split(':')[-1],
                                    'isrc': 'N/A',
                                    'processed': False,
                                    'lyrics_found': False,
                                    'lyrics_source': '',
                                    'batch_number': 0,
                                    'processed_timestamp': ''
                                })
                                batch_failed += 1
                                failed_count += 1
                        else:
                            # Non-rate-limit error
                            print(f"  ✗ [{i}/{len(batch)}] {song['track_name'][:40]:<40} - Error: {error_msg[:30]}")
                            enriched_songs.append({
                                **song,
                                'track_id': song['track_uri'].split(':')[-1],
                                'isrc': 'N/A',
                                'processed': False,
                                'lyrics_found': False,
                                'lyrics_source': '',
                                'batch_number': 0,
                                'processed_timestamp': ''
                            })
                            batch_failed += 1
                            failed_count += 1
                            success = True  # Don't retry non-rate-limit errors
                            time.sleep(0.5)

            batch_time = time.time() - batch_start_time
            avg_per_song = batch_time / batch_end_idx if batch_end_idx > 0 else 0
            remaining_songs = len(songs) - batch_end_idx
            eta_seconds = remaining_songs * avg_per_song
            eta_minutes = eta_seconds / 60

            print(f"  ✓ Batch {batch_num} complete! Success: {batch_success}, Failed: {batch_failed}")
            print(f"  ⏱ Time: {batch_time:.1f}s | Avg: {avg_per_song:.2f}s/song | ETA: {eta_minutes:.1f} min\n")

            # Save progress after each batch
            self.save_processing_queue_csv(enriched_songs, PROCESSING_QUEUE_CSV)

            batch_start_time = time.time()

        total_time = sum([time.time() - batch_start_time])
        print(f"{'='*70}")
        print(f"METADATA FETCHING COMPLETE")
        print(f"{'='*70}")
        print(f"✓ Successfully fetched: {success_count}/{len(songs)} songs")
        if failed_count > 0:
            print(f"⚠ Failed to fetch: {failed_count} songs")
        print(f"⏱ Total time: {total_time:.1f}s\n")

        return enriched_songs

    def save_processing_queue_csv(self, songs: List[Dict], output_path: Union[str, Path] = PROCESSING_QUEUE_CSV):
        """Save processing queue to CSV."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nSaving processing queue to {output_path}...")

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['track_uri', 'track_id', 'track_name', 'artist_name', 'album_name',
                         'isrc', 'total_plays', 'first_played_date', 'last_played_date',
                         'processed', 'lyrics_found', 'lyrics_source', 'batch_number', 'processed_timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(songs)

        print(f"✓ Saved processing queue with {len(songs)} songs to {output_path}")


def main():
    """Main execution function."""
    script_start = time.time()
    print("\n" + "="*70)
    print("  SONG EXTRACTION & PROCESSING QUEUE GENERATOR")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        # Initialize extractor
        print("Initializing Spotify API client...")
        extractor = SongExtractor()
        print("✓ Initialized\n")

        # Step 1: Extract unique songs
        unique_songs = extractor.extract_unique_songs()

        # Save unique songs CSV
        extractor.save_unique_songs_csv(unique_songs)

        # Step 2: Fetch Spotify metadata
        enriched_songs = extractor.fetch_spotify_metadata(unique_songs)

        # Save processing queue CSV
        extractor.save_processing_queue_csv(enriched_songs)

        # Summary
        total_time = time.time() - script_start
        print("\n" + "="*70)
        print("EXTRACTION COMPLETE")
        print("="*70)
        print(f"✓ Unique songs extracted: {len(unique_songs)}")
        print(f"✓ Songs with metadata: {len(enriched_songs)}")
        print(f"✓ Processing queue ready")
        print(f"⏱ Total time: {total_time:.2f}s")
        print("="*70)
        print("\nNext step: Run process_lyrics_batch.py to fetch lyrics")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
