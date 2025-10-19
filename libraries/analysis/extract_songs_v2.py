"""
Extract Unique Songs & Create Processing Queue (V2 - Album Batch Optimized)

This script:
1. Extracts all unique songs from JSON streaming data
2. Creates unique_songs.csv with basic information
3. Fetches Spotify metadata using ALBUM BATCHING for efficiency
   - First: Batch fetch albums (20 albums per API call, ~10-50 tracks each)
   - Then: Individual track fetch for ISRC (only for tracks in albums)
   - Finally: Individual track fetch for tracks without albums
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
    """Extracts unique songs and prepares processing queue with album-based batch optimization."""

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

                    # Store unique song info (album_uri will be fetched from Spotify API later)
                    if track_uri not in songs_data:
                        songs_data[track_uri] = {
                            'track_uri': track_uri,
                            'track_name': track_name,
                            'artist_name': artist_name,
                            'album_name': album_name or 'Unknown',
                            'album_uri': None  # Will be populated during metadata fetching
                        }

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
        print(f"✓ Tracks with albums: {sum(len(tracks) for tracks in album_to_tracks.values()):,}")
        print(f"✓ Tracks without albums: {len(unique_songs) - sum(len(tracks) for tracks in album_to_tracks.values()):,}")
        print(f"✓ Deduplication rate: {(1 - len(unique_songs)/valid_tracks)*100:.1f}%\n")

        return unique_songs, album_to_tracks

    def save_unique_songs_csv(self, songs: List[Dict], output_path: Union[str, Path] = UNIQUE_SONGS_CSV):
        """Save unique songs to CSV."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nSaving unique songs to {output_path}...")

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['track_uri', 'track_name', 'artist_name', 'album_name', 'album_uri',
                         'total_plays', 'first_played_date', 'last_played_date']
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(songs)

        print(f"✓ Saved {len(songs)} songs to {output_path}")

    def fetch_spotify_metadata(self, songs: List[Dict], album_to_tracks: Dict[str, Set[str]]) -> List[Dict]:
        """
        Fetch Spotify metadata with BATCH OPTIMIZATION.

        Strategy:
        1. PHASE 1: Batch fetch tracks (50 tracks/call) to get album URIs and basic metadata
        2. PHASE 2: Group by album and batch fetch albums (20 albums/call) for complete track data with ISRCs
        3. PHASE 3: Individual fetch for any remaining tracks that need ISRCs

        Args:
            songs: List of unique songs
            album_to_tracks: Mapping of album_uri -> set of track_uris (initially empty, populated in Phase 1)

        Returns:
            Songs enriched with Spotify metadata
        """
        print("\n" + "="*70)
        print("STEP 2: FETCHING SPOTIFY METADATA (BATCH OPTIMIZED)")
        print("="*70)
        print(f"Total songs: {len(songs)}")
        print(f"Strategy: Track batches (50/call) → Album batches (20/call) → Individual ISRCs\n")

        # Check if queue CSV exists for resume capability
        queue_path = PROCESSING_QUEUE_CSV
        existing_songs = {}

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

        # Track what we've fetched
        track_metadata = {}  # track_uri -> metadata (including album_uri, isrc)
        album_to_tracks_map = defaultdict(set)  # album_uri -> set of track_uris
        enriched_songs = []

        # PHASE 1: BATCH FETCH TRACKS TO GET ALBUM URIs
        print(f"\n{'='*70}")
        print(f"PHASE 1: BATCH FETCHING TRACKS (Getting Album URIs)")
        print(f"{'='*70}\n")

        # Get list of track IDs to fetch
        tracks_to_fetch = [s for s in songs if s['track_uri'] not in existing_songs]
        track_batch_size = 50
        total_track_batches = (len(tracks_to_fetch) + track_batch_size - 1) // track_batch_size

        phase1_start = time.time()
        phase1_success = 0
        phase1_failed = 0

        for batch_num in range(total_track_batches):
            batch_start = batch_num * track_batch_size
            batch_end = min((batch_num + 1) * track_batch_size, len(tracks_to_fetch))
            track_batch = tracks_to_fetch[batch_start:batch_end]

            # Extract track IDs
            track_ids = [s['track_uri'].split(':')[-1] for s in track_batch]

            progress = ((batch_num + 1) / total_track_batches) * 100
            bar_length = 30
            filled = int((progress / 100) * bar_length)
            bar = '━' * filled + '░' * (bar_length - filled)

            print(f"Track Batch {batch_num + 1}/{total_track_batches} [{batch_end}/{len(tracks_to_fetch)} tracks] {bar} {progress:.1f}%")

            try:
                api_start = time.time()
                tracks_data = self.spotify.tracks(track_ids)
                api_time = time.time() - api_start

                for track in tracks_data.get('tracks', []):
                    if not track:
                        phase1_failed += 1
                        continue

                    track_id = track['id']
                    track_uri = f"spotify:track:{track_id}"
                    album_uri = track.get('album', {}).get('uri')
                    isrc = track.get('external_ids', {}).get('isrc')

                    track_metadata[track_uri] = {
                        'track_id': track_id,
                        'track_uri': track_uri,
                        'album_uri': album_uri,
                        'isrc': isrc or 'N/A'
                    }

                    # Map track to album for potential album-based fetching
                    if album_uri:
                        album_to_tracks_map[album_uri].add(track_uri)

                    phase1_success += 1

                print(f"  ✓ Fetched {len(track_batch)} tracks in {api_time:.2f}s")
                time.sleep(0.05)  # Small delay between batches

            except Exception as e:
                print(f"  ✗ Error fetching track batch: {str(e)[:100]}")
                phase1_failed += len(track_batch)
                time.sleep(1)

        phase1_time = time.time() - phase1_start
        print(f"\n✓ Phase 1 complete: {phase1_success} tracks fetched, {phase1_failed} failed in {phase1_time:.1f}s")
        print(f"✓ Found {len(album_to_tracks_map)} unique albums\n")

        # Phase 1 already fetched all metadata including ISRCs
        # No Phase 2 or Phase 3 needed since we got everything in one batch operation

        # COMBINE ALL DATA
        print(f"{'='*70}")
        print(f"COMBINING ALL METADATA")
        print(f"{'='*70}\n")

        for song in songs:
            track_uri = song['track_uri']

            if track_uri in existing_songs:
                enriched_songs.append(existing_songs[track_uri])
                continue

            metadata = track_metadata.get(track_uri, {
                'track_id': track_uri.split(':')[-1],
                'album_uri': None,
                'isrc': 'N/A'
            })

            enriched_songs.append({
                **song,
                'track_id': metadata['track_id'],
                'album_uri': metadata.get('album_uri'),
                'isrc': metadata['isrc'],
                'processed': False,
                'lyrics_found': False,
                'lyrics_source': '',
                'batch_number': 0,
                'processed_timestamp': ''
            })

        print(f"{'='*70}")
        print(f"METADATA FETCHING COMPLETE")
        print(f"{'='*70}")
        print(f"✓ Phase 1 (Batch Track Fetch): {phase1_time:.1f}s")
        print(f"✓ Total time: {phase1_time:.1f}s")
        print(f"✓ Total songs processed: {len(enriched_songs)}")
        print(f"✓ Songs with album URIs: {sum(1 for s in enriched_songs if s.get('album_uri'))}")
        print(f"✓ ISRCs found: {sum(1 for s in enriched_songs if s['isrc'] != 'N/A')}")
        print(f"✓ Unique albums: {len(album_to_tracks_map)}\n")

        return enriched_songs

    def save_processing_queue_csv(self, songs: List[Dict], output_path: Union[str, Path] = PROCESSING_QUEUE_CSV):
        """Save processing queue to CSV."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nSaving processing queue to {output_path}...")

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['track_uri', 'track_id', 'track_name', 'artist_name', 'album_name', 'album_uri',
                         'isrc', 'total_plays', 'first_played_date', 'last_played_date',
                         'processed', 'lyrics_found', 'lyrics_source', 'batch_number', 'processed_timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(songs)

        print(f"✓ Saved processing queue with {len(songs)} songs to {output_path}")


def main():
    """Main execution function."""
    script_start = time.time()
    print("\n" + "="*70)
    print("  SONG EXTRACTION & PROCESSING QUEUE GENERATOR (V2 - OPTIMIZED)")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        # Initialize extractor
        print("Initializing Spotify API client...")
        extractor = SongExtractor()
        print("✓ Initialized\n")

        # Step 1: Extract unique songs
        unique_songs, album_to_tracks = extractor.extract_unique_songs()

        # Save unique songs CSV
        extractor.save_unique_songs_csv(unique_songs)

        # Step 2: Fetch Spotify metadata with album batching
        enriched_songs = extractor.fetch_spotify_metadata(unique_songs, album_to_tracks)

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
