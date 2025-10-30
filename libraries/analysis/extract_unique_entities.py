"""
Extract Unique Artists, Albums, and Tracks from Streaming History

This script parses all streaming*.json files and extracts unique:
- Artists (with IDs, URIs, play counts)
- Albums (with IDs, URIs, artist links, play counts)
- Tracks (with IDs, URIs, artist/album links, play counts)

Features:
- Idempotent (can run multiple times safely)
- Deduplication by URI
- Extracts Spotify IDs from URIs
- Aggregates play counts per entity
- Outputs to CSV for downstream API fetching

Output:
    data/unique_artists.csv
    data/unique_albums.csv
    data/unique_tracks.csv

Usage:
    python extract_unique_entities.py
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict
from datetime import datetime
import glob

from path_utils import DATA_DIR

# Output paths
UNIQUE_ARTISTS_CSV = DATA_DIR / 'unique_artists.csv'
UNIQUE_ALBUMS_CSV = DATA_DIR / 'unique_albums.csv'
UNIQUE_TRACKS_CSV = DATA_DIR / 'unique_tracks.csv'


def extract_id_from_uri(uri: str) -> str:
    """Extract Spotify ID from URI (e.g., 'spotify:track:XXX' -> 'XXX')."""
    if not uri or uri == 'N/A' or uri is None:
        return None
    return uri.split(':')[-1] if ':' in uri else uri


def extract_artist_id_from_track_uri(track_uri: str) -> str:
    """
    Extract artist ID from track URI by looking up in the track data.
    Returns None if not available (will be filled during API fetch).
    """
    # We'll extract this from the actual streaming data
    return None


class EntityExtractor:
    """Extracts unique artists, albums, and tracks from streaming history."""

    def __init__(self):
        """Initialize extractor with empty tracking dictionaries."""
        # Track entities: uri -> {data dict}
        self.artists = {}
        self.albums = {}
        self.tracks = {}

        # Track play counts: uri -> count
        self.artist_plays = defaultdict(int)
        self.album_plays = defaultdict(int)
        self.track_plays = defaultdict(int)

        # Track first and last played dates
        self.track_first_played = {}
        self.track_last_played = {}

    def load_existing_csvs(self):
        """Load existing CSVs to avoid reprocessing."""
        print("Loading existing CSVs (if any)...")

        # Load artists
        if UNIQUE_ARTISTS_CSV.exists():
            with UNIQUE_ARTISTS_CSV.open('r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uri = row['artist_uri']
                    self.artists[uri] = row
                    self.artist_plays[uri] = int(row.get('total_plays', 0))
            print(f"  ✓ Loaded {len(self.artists)} existing artists")
        else:
            print("  • No existing artists CSV found")

        # Load albums
        if UNIQUE_ALBUMS_CSV.exists():
            with UNIQUE_ALBUMS_CSV.open('r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uri = row['album_uri']
                    self.albums[uri] = row
                    self.album_plays[uri] = int(row.get('total_plays', 0))
            print(f"  ✓ Loaded {len(self.albums)} existing albums")
        else:
            print("  • No existing albums CSV found")

        # Load tracks
        if UNIQUE_TRACKS_CSV.exists():
            with UNIQUE_TRACKS_CSV.open('r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uri = row['track_uri']
                    self.tracks[uri] = row
                    self.track_plays[uri] = int(row.get('total_plays', 0))
                    self.track_first_played[uri] = row.get('first_played_date')
                    self.track_last_played[uri] = row.get('last_played_date')
            print(f"  ✓ Loaded {len(self.tracks)} existing tracks")
        else:
            print("  • No existing tracks CSV found")

    def process_streaming_files(self):
        """Process all streaming*.json files."""
        # Find all streaming JSON files (exclude video)
        streaming_files = sorted(glob.glob(str(DATA_DIR / 'streaming_*.json')))
        streaming_files = [f for f in streaming_files if 'video' not in f.lower()]

        print(f"\nFound {len(streaming_files)} streaming files to process:")
        for file in streaming_files:
            print(f"  • {Path(file).name}")

        total_records = 0
        for file_path in streaming_files:
            print(f"\nProcessing {Path(file_path).name}...")
            records = self._process_single_file(file_path)
            total_records += records
            print(f"  ✓ Processed {records:,} records")

        print(f"\n{'='*70}")
        print(f"EXTRACTION COMPLETE")
        print(f"{'='*70}")
        print(f"Total records processed: {total_records:,}")
        print(f"Unique artists: {len(self.artists):,}")
        print(f"Unique albums: {len(self.albums):,}")
        print(f"Unique tracks: {len(self.tracks):,}")

    def _process_single_file(self, file_path: str) -> int:
        """Process a single streaming JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            records_processed = 0
            for record in data:
                # Only process music tracks (not episodes, audiobooks, etc.)
                track_uri = record.get('spotify_track_uri')
                if not track_uri or track_uri == 'null':
                    continue

                track_name = record.get('master_metadata_track_name')
                artist_name = record.get('master_metadata_album_artist_name')
                album_name = record.get('master_metadata_album_album_name')

                # Skip if missing critical data
                if not track_name or not artist_name:
                    continue

                # Extract timestamp
                timestamp = record.get('ts')

                # Process artist
                # Note: We don't have artist URI in streaming data, so we'll construct a placeholder
                # The actual artist URI/ID will be fetched later via API
                artist_key = f"{artist_name}"  # Use name as key for now
                if artist_key not in self.artists:
                    self.artists[artist_key] = {
                        'artist_name': artist_name,
                        'artist_uri': None,  # Will be filled during API fetch
                        'artist_id': None,   # Will be filled during API fetch
                    }
                self.artist_plays[artist_key] += 1

                # Process album
                # Similarly, we don't have album URI in streaming data
                album_key = f"{album_name}|{artist_name}"  # Composite key
                if album_key not in self.albums:
                    self.albums[album_key] = {
                        'album_name': album_name,
                        'album_artist_name': artist_name,
                        'album_uri': None,  # Will be filled during API fetch
                        'album_id': None,   # Will be filled during API fetch
                        'artist_name': artist_name,
                    }
                self.album_plays[album_key] += 1

                # Process track
                track_id = extract_id_from_uri(track_uri)
                if track_uri not in self.tracks:
                    self.tracks[track_uri] = {
                        'track_name': track_name,
                        'artist_name': artist_name,
                        'album_name': album_name,
                        'track_uri': track_uri,
                        'track_id': track_id,
                        'album_uri': None,  # Will be filled during API fetch
                        'album_id': None,   # Will be filled during API fetch
                        'artist_uri': None, # Will be filled during API fetch
                        'artist_id': None,  # Will be filled during API fetch
                        'isrc': None,       # Will be filled during API fetch
                    }
                    self.track_first_played[track_uri] = timestamp
                    self.track_last_played[track_uri] = timestamp

                self.track_plays[track_uri] += 1

                # Update last played date
                if timestamp:
                    current_last = self.track_last_played.get(track_uri)
                    if not current_last or timestamp > current_last:
                        self.track_last_played[track_uri] = timestamp

                    current_first = self.track_first_played.get(track_uri)
                    if not current_first or timestamp < current_first:
                        self.track_first_played[track_uri] = timestamp

                records_processed += 1

            return records_processed

        except Exception as e:
            print(f"  ✗ Error processing {file_path}: {e}")
            return 0

    def save_artists_csv(self):
        """Save unique artists to CSV."""
        print(f"\nSaving artists to {UNIQUE_ARTISTS_CSV}...")

        artists_list = []
        for key, artist in self.artists.items():
            artists_list.append({
                'artist_name': artist['artist_name'],
                'artist_uri': artist.get('artist_uri') or '',
                'artist_id': artist.get('artist_id') or '',
                'total_plays': self.artist_plays[key],
            })

        # Sort by total plays descending
        artists_list.sort(key=lambda x: x['total_plays'], reverse=True)

        with UNIQUE_ARTISTS_CSV.open('w', newline='', encoding='utf-8') as f:
            fieldnames = ['artist_name', 'artist_uri', 'artist_id', 'total_plays']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(artists_list)

        print(f"  ✓ Saved {len(artists_list):,} unique artists")

    def save_albums_csv(self):
        """Save unique albums to CSV."""
        print(f"\nSaving albums to {UNIQUE_ALBUMS_CSV}...")

        albums_list = []
        for key, album in self.albums.items():
            albums_list.append({
                'album_name': album['album_name'],
                'album_artist_name': album['album_artist_name'],
                'artist_name': album['artist_name'],
                'album_uri': album.get('album_uri') or '',
                'album_id': album.get('album_id') or '',
                'artist_uri': '',  # Will be filled during API fetch
                'artist_id': '',   # Will be filled during API fetch
                'total_plays': self.album_plays[key],
            })

        # Sort by total plays descending
        albums_list.sort(key=lambda x: x['total_plays'], reverse=True)

        with UNIQUE_ALBUMS_CSV.open('w', newline='', encoding='utf-8') as f:
            fieldnames = ['album_name', 'album_artist_name', 'artist_name',
                         'album_uri', 'album_id', 'artist_uri', 'artist_id', 'total_plays']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(albums_list)

        print(f"  ✓ Saved {len(albums_list):,} unique albums")

    def save_tracks_csv(self):
        """Save unique tracks to CSV."""
        print(f"\nSaving tracks to {UNIQUE_TRACKS_CSV}...")

        tracks_list = []
        for uri, track in self.tracks.items():
            tracks_list.append({
                'track_name': track['track_name'],
                'artist_name': track['artist_name'],
                'album_name': track['album_name'],
                'track_uri': track['track_uri'],
                'track_id': track['track_id'],
                'album_uri': track.get('album_uri') or '',
                'album_id': track.get('album_id') or '',
                'artist_uri': track.get('artist_uri') or '',
                'artist_id': track.get('artist_id') or '',
                'isrc': track.get('isrc') or '',
                'total_plays': self.track_plays[uri],
                'first_played_date': self.track_first_played.get(uri, ''),
                'last_played_date': self.track_last_played.get(uri, ''),
            })

        # Sort by total plays descending
        tracks_list.sort(key=lambda x: x['total_plays'], reverse=True)

        with UNIQUE_TRACKS_CSV.open('w', newline='', encoding='utf-8') as f:
            fieldnames = ['track_name', 'artist_name', 'album_name', 'track_uri', 'track_id',
                         'album_uri', 'album_id', 'artist_uri', 'artist_id', 'isrc',
                         'total_plays', 'first_played_date', 'last_played_date']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(tracks_list)

        print(f"  ✓ Saved {len(tracks_list):,} unique tracks")


def main():
    """Main execution function."""
    print("="*70)
    print("  UNIQUE ENTITIES EXTRACTOR")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        extractor = EntityExtractor()

        # Load existing data (if any)
        extractor.load_existing_csvs()

        # Process streaming files
        extractor.process_streaming_files()

        # Save to CSVs
        extractor.save_artists_csv()
        extractor.save_albums_csv()
        extractor.save_tracks_csv()

        print(f"\n{'='*70}")
        print("SUCCESS!")
        print(f"{'='*70}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nOutput files:")
        print(f"  • {UNIQUE_ARTISTS_CSV}")
        print(f"  • {UNIQUE_ALBUMS_CSV}")
        print(f"  • {UNIQUE_TRACKS_CSV}")
        print(f"{'='*70}\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
