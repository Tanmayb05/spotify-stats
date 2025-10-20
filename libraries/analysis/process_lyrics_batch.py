"""
Batch Lyrics Processing with Resume Capability

This script processes songs in batches of 500 with:
- Resume capability (tracks progress in lyrics-1.json)
- Genius API (primary) → Musixmatch API (fallback)
- Automatic batch verification and continuation
- Updates processing queue CSV with results

Requirements:
    pip install spotipy python-dotenv lyricsgenius musixmatch

Environment Variables:
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, GENIUS_ACCESS_TOKEN

Note: This uses the musixmatch package which scrapes data (no API key needed).
      Status 401 errors mean the scraping endpoints may have changed.
"""

import json
import os
import csv
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
from musicxmatch_api import MusixMatchAPI
import time

from path_utils import DATA_DIR, OUTPUT_DIR

# Load environment variables from spotify-stats.env
load_dotenv('../../spotify-stats.env')

# Constants
BATCH_SIZE = 500
QUEUE_CSV = DATA_DIR / 'songs_processing_queue.csv'
LYRICS_JSON = OUTPUT_DIR / 'lyrics-1.json'
SAVE_INTERVAL = 10  # Save progress every N songs


class BatchLyricsProcessor:
    """Processes lyrics in batches with resume capability."""

    def __init__(self):
        """Initialize API clients."""
        # Spotify API
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        if not client_id or not client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET required")

        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.spotify = spotipy.Spotify(auth_manager=auth_manager)

        # Genius API
        genius_token = os.getenv('GENIUS_ACCESS_TOKEN')
        if genius_token:
            self.genius = lyricsgenius.Genius(genius_token, verbose=False, remove_section_headers=True)
            self.genius.timeout = 15
            print("✓ Genius API initialized")
        else:
            self.genius = None
            print("⚠ GENIUS_ACCESS_TOKEN not found - Genius API disabled")

        # Musixmatch API
        self.musixmatch = MusixMatchAPI()
        print("✓ Musixmatch API initialized")

    def load_processing_queue(self) -> List[Dict]:
        """Load the processing queue CSV."""
        if not QUEUE_CSV.exists():
            raise FileNotFoundError(f"{QUEUE_CSV} not found. Run extract_songs.py first.")

        songs = []
        with QUEUE_CSV.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert string booleans to actual booleans
                row['processed'] = row['processed'].lower() == 'true'
                row['lyrics_found'] = row['lyrics_found'].lower() == 'true'
                row['batch_number'] = int(row['batch_number'])
                songs.append(row)

        return songs

    def load_lyrics_progress(self) -> Dict:
        """Load existing lyrics progress from JSON."""
        if not LYRICS_JSON.exists():
            return {
                'total_processed': 0,
                'successful': 0,
                'failed': 0,
                'batches_completed': [],
                'lyrics_sources': {'genius': 0, 'musixmatch': 0},
                'tracks': []
            }

        with LYRICS_JSON.open('r', encoding='utf-8') as f:
            return json.load(f)

    def get_processed_track_uris(self, progress: Dict) -> Set[str]:
        """Extract set of already processed track URIs from progress."""
        return {track['track_uri'] for track in progress.get('tracks', [])}

    def get_next_batch(self, queue: List[Dict], processed_uris: Set[str], batch_number: int) -> List[Dict]:
        """Get the next batch of unprocessed songs."""
        unprocessed = [
            song for song in queue
            if not song['processed'] and song['track_uri'] not in processed_uris
        ]

        # Calculate batch start index
        start_idx = (batch_number - 1) * BATCH_SIZE
        end_idx = start_idx + BATCH_SIZE

        batch = unprocessed[start_idx:end_idx] if start_idx < len(unprocessed) else []
        return batch

    def get_lyrics_from_genius(self, track_name: str, artist_name: str) -> tuple[Optional[Dict], str]:
        """Fetch lyrics from Genius API.

        Returns:
            Tuple of (lyrics_dict, status_message)
        """
        if not self.genius:
            return None, "Genius API not initialized"

        try:
            song = self.genius.search_song(track_name, artist_name)
            if not song:
                return None, "Track not found in Genius"

            lyrics_text = song.lyrics if hasattr(song, 'lyrics') and song.lyrics else None
            if not lyrics_text:
                return None, "Track found but no lyrics available"

            return {
                'lyrics_body': lyrics_text,
                'song_id': getattr(song, 'id', None),
                'title': getattr(song, 'title', track_name),
                'artist': getattr(song, 'artist', artist_name),
                'url': getattr(song, 'url', None),
                'lookup_method': 'genius'
            }, "Success"
        except Exception as e:
            return None, f"Genius API error: {str(e)[:50]}"

    def get_lyrics_from_musixmatch(self, isrc: str, track_name: str, artist_name: str) -> tuple[Optional[Dict], str]:
        """Fetch lyrics from Musixmatch API.

        Returns:
            Tuple of (lyrics_dict, status_message)
        """
        failure_reasons = []

        try:
            # Try ISRC first
            if isrc and isrc != 'N/A':
                try:
                    lyrics_data = self.musixmatch.get_track_lyrics(track_isrc=isrc)
                    if lyrics_data and isinstance(lyrics_data, dict):
                        status_code = lyrics_data.get('message', {}).get('header', {}).get('status_code')
                        if status_code == 200:
                            lyrics_body = lyrics_data['message']['body'].get('lyrics', {})
                            if lyrics_body and lyrics_body.get('lyrics_body'):
                                return {
                                    'lyrics_body': lyrics_body.get('lyrics_body'),
                                    'lyrics_language': lyrics_body.get('lyrics_language'),
                                    'lyrics_copyright': lyrics_body.get('lyrics_copyright'),
                                    'lookup_method': 'musixmatch_isrc'
                                }, "Success"
                            else:
                                failure_reasons.append("ISRC lookup: no lyrics in response")
                        else:
                            failure_reasons.append(f"ISRC lookup: status {status_code}")
                    else:
                        failure_reasons.append("ISRC lookup: invalid API response")
                except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
                    failure_reasons.append(f"ISRC lookup: {type(e).__name__}")
            else:
                failure_reasons.append("No ISRC available")

            # Fallback to search
            search_query = f"{track_name} {artist_name}"
            try:
                search_data = self.musixmatch.search_tracks(track_query=search_query, page=1)

                if not search_data or not isinstance(search_data, dict):
                    failure_reasons.append("Search: invalid API response")
                    return None, " | ".join(failure_reasons)

                status_code = search_data.get('message', {}).get('header', {}).get('status_code')
                if status_code != 200:
                    failure_reasons.append(f"Search: status {status_code}")
                    return None, " | ".join(failure_reasons)

                track_list = search_data.get('message', {}).get('body', {}).get('track_list', [])
                if not track_list:
                    failure_reasons.append("Search: track not found")
                    return None, " | ".join(failure_reasons)

                track_id = track_list[0]['track']['track_id']
                lyrics_data = self.musixmatch.get_track_lyrics(track_id=track_id)

                if not lyrics_data or not isinstance(lyrics_data, dict):
                    failure_reasons.append("Search: invalid lyrics response")
                    return None, " | ".join(failure_reasons)

                status_code = lyrics_data.get('message', {}).get('header', {}).get('status_code')
                if status_code != 200:
                    failure_reasons.append(f"Search lyrics: status {status_code}")
                    return None, " | ".join(failure_reasons)

                lyrics_body = lyrics_data.get('message', {}).get('body', {}).get('lyrics', {})
                if lyrics_body and lyrics_body.get('lyrics_body'):
                    return {
                        'lyrics_body': lyrics_body.get('lyrics_body'),
                        'lyrics_language': lyrics_body.get('lyrics_language'),
                        'lyrics_copyright': lyrics_body.get('lyrics_copyright'),
                        'lookup_method': 'musixmatch_search'
                    }, "Success"
                else:
                    failure_reasons.append("Search: no lyrics in response")

            except (json.JSONDecodeError, KeyError, TypeError, AttributeError, IndexError) as e:
                failure_reasons.append(f"Search: {type(e).__name__}")
                return None, " | ".join(failure_reasons)

            return None, " | ".join(failure_reasons)

        except Exception as e:
            failure_reasons.append(f"Unexpected error: {str(e)[:50]}")
            return None, " | ".join(failure_reasons)

    def process_single_song(self, song: Dict) -> tuple[Optional[Dict], Dict[str, str]]:
        """Process a single song with Genius → Musixmatch fallback.

        Returns:
            Tuple of (result_dict, status_logs)
        """
        track_name = song['track_name']
        artist_name = song['artist_name']
        isrc = song.get('isrc', 'N/A')

        status_logs = {
            'genius': '',
            'musixmatch': ''
        }

        # Try Genius first
        if self.genius:
            lyrics, genius_status = self.get_lyrics_from_genius(track_name, artist_name)
            status_logs['genius'] = genius_status
            if lyrics:
                return {**song, 'lyrics': lyrics, 'lyrics_source': 'genius'}, status_logs

        # Fallback to Musixmatch
        lyrics, musixmatch_status = self.get_lyrics_from_musixmatch(isrc, track_name, artist_name)
        status_logs['musixmatch'] = musixmatch_status
        if lyrics:
            source = lyrics['lookup_method']
            return {**song, 'lyrics': lyrics, 'lyrics_source': source}, status_logs

        return None, status_logs

    def save_progress(self, progress: Dict):
        """Save progress to JSON file."""
        LYRICS_JSON.parent.mkdir(parents=True, exist_ok=True)
        with LYRICS_JSON.open('w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)

    def update_queue_csv(self, song: Dict, lyrics_found: bool, lyrics_source: str, batch_number: int):
        """Update a single row in the processing queue CSV."""
        queue = self.load_processing_queue()

        for i, row in enumerate(queue):
            if row['track_uri'] == song['track_uri']:
                queue[i]['processed'] = True
                queue[i]['lyrics_found'] = lyrics_found
                queue[i]['lyrics_source'] = lyrics_source
                queue[i]['batch_number'] = batch_number
                queue[i]['processed_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                break

        # Save updated queue
        with QUEUE_CSV.open('w', newline='', encoding='utf-8') as f:
            fieldnames = list(queue[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(queue)

    def process_batch(self, batch: List[Dict], batch_number: int, progress: Dict) -> Dict:
        """Process a batch of songs."""
        print(f"\n{'='*70}")
        print(f"PROCESSING BATCH {batch_number}")
        print(f"{'='*70}")
        print(f"Songs in batch: {len(batch)}\n")

        batch_results = []
        successful = 0
        failed = 0

        for idx, song in enumerate(batch, 1):
            print(f"[{idx}/{len(batch)}] {song['track_name']} - {song['artist_name']}")

            result, status_logs = self.process_single_song(song)

            if result and result.get('lyrics'):
                batch_results.append(result)
                successful += 1
                source = result.get('lyrics_source', 'unknown')
                progress['lyrics_sources'][source] = progress['lyrics_sources'].get(source, 0) + 1
                print(f"   ✓ Found via {source.upper()}")

                # Update queue
                self.update_queue_csv(song, True, source, batch_number)
            else:
                failed += 1
                # Display detailed failure reasons
                print(f"   ✗ Not found in both sources:")
                if status_logs.get('genius'):
                    print(f"      • Genius: {status_logs['genius']}")
                if status_logs.get('musixmatch'):
                    print(f"      • Musixmatch: {status_logs['musixmatch']}")

                # Update queue
                self.update_queue_csv(song, False, '', batch_number)

            # Save progress incrementally
            if idx % SAVE_INTERVAL == 0:
                progress['tracks'].extend(batch_results)
                progress['total_processed'] += len(batch_results)
                progress['successful'] += successful
                progress['failed'] += failed
                self.save_progress(progress)
                batch_results = []
                successful = 0
                failed = 0
                print(f"   → Progress saved ({idx} songs processed)")

            # Rate limiting
            time.sleep(1)

        # Save remaining results
        if batch_results:
            progress['tracks'].extend(batch_results)
            progress['total_processed'] += len(batch_results)
            progress['successful'] += successful
            progress['failed'] += failed

        # Mark batch as completed
        if batch_number not in progress['batches_completed']:
            progress['batches_completed'].append(batch_number)

        self.save_progress(progress)
        return progress


def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("  BATCH LYRICS PROCESSOR")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Batch size: {BATCH_SIZE} songs")
    print(f"Strategy: Genius API → Musixmatch API\n")

    try:
        # Initialize processor
        print("Initializing API clients...")
        processor = BatchLyricsProcessor()
        print("✓ All clients initialized\n")

        # Load queue and progress
        print("Loading processing queue...")
        queue = processor.load_processing_queue()
        print(f"✓ Loaded {len(queue)} total songs\n")

        print("Loading existing progress...")
        progress = processor.load_lyrics_progress()
        processed_uris = processor.get_processed_track_uris(progress)
        print(f"✓ Already processed: {len(processed_uris)} songs")
        print(f"✓ Completed batches: {progress.get('batches_completed', [])}\n")

        # Determine next batch number
        completed_batches = progress.get('batches_completed', [])
        next_batch_num = max(completed_batches, default=0) + 1

        # Process batches until all done
        while True:
            batch = processor.get_next_batch(queue, processed_uris, next_batch_num)

            if not batch:
                print(f"\n{'='*70}")
                print("ALL BATCHES COMPLETED!")
                print(f"{'='*70}")
                print(f"Total processed: {progress['total_processed']}")
                print(f"Successful: {progress['successful']}")
                print(f"Failed: {progress['failed']}")
                print(f"Batches completed: {len(progress['batches_completed'])}")
                print(f"{'='*70}\n")
                break

            # Process this batch
            progress = processor.process_batch(batch, next_batch_num, progress)

            print(f"\n✓ Batch {next_batch_num} completed")
            print(f"   Total progress: {progress['total_processed']}/{len(queue)} songs")

            # Move to next batch
            next_batch_num += 1
            processed_uris = processor.get_processed_track_uris(progress)

    except KeyboardInterrupt:
        print("\n\n⚠ Process interrupted by user")
        print("Progress has been saved. Run again to resume.")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
