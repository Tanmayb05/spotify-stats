"""
Retry Failed Lyrics Processing with Multi-Source Fallback

This script targets songs from failed_lyrics.csv and attempts to fetch lyrics
using a 3-tier fallback strategy:
1. Genius API (primary, most comprehensive)
2. Lyrics.ovh API (secondary, free no-auth API)
3. Musixmatch API (fallback, auto-disables if unavailable)

Features:
- Intelligent name cleaning (removes "Live", "Acoustic", etc.)
- Auto-disable broken APIs after 10 consecutive failures
- Rate limiting to prevent API blocks
- Detailed failure tracking and categorization
- Instrumental/score detection
- Progress saving and resume capability

Results saved to: lyrics-failed-retry.json

Requirements:
    pip install spotipy python-dotenv lyricsgenius musicxmatch-api requests

Environment Variables:
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, GENIUS_ACCESS_TOKEN

Usage:
    python libraries/analysis/process_failed_lyrics_retry.py
"""

import json
import os
import csv
import re
import requests
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

# Load environment variables from spotify-insights.env
repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(repo_root / 'spotify-insights.env')

# Constants
BATCH_SIZE = 100  # Smaller batch size for retry attempts
FAILED_CSV = DATA_DIR / 'failed_lyrics.csv'
OUTPUT_JSON = OUTPUT_DIR / 'lyrics-failed-retry.json'
SAVE_INTERVAL = 10  # Save progress every N songs


class FailedLyricsRetryProcessor:
    """Retry processor specifically for failed lyrics."""

    def __init__(self):
        """Initialize API clients."""
        print("\nInitializing API clients...")

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
            self.genius = lyricsgenius.Genius(
                genius_token,
                timeout=15,
                retries=3,
                remove_section_headers=True,
                verbose=False
            )
            print("✓ Genius API initialized")
        else:
            self.genius = None
            print("⚠ Genius API token not found - will use Musixmatch only")

        # Musixmatch API (scraping-based, no key needed)
        # Note: May have rate limits or authentication issues
        try:
            self.musixmatch = MusixMatchAPI()
            print("✓ Musixmatch API initialized (may have limited availability)")
        except Exception as e:
            print(f"⚠ Musixmatch initialization failed: {e}")
            self.musixmatch = None

        # Track Musixmatch failures and auto-disable
        self.musixmatch_consecutive_failures = 0
        self.musixmatch_disabled = False
        self.musixmatch_disable_threshold = 10

        print("✓ All clients initialized\n")

        # Progress tracking
        self.processed = {}
        self.success_count = 0
        self.fail_count = 0
        self.retry_attempts = {}

        # Source tracking
        self.genius_count = 0
        self.lyricsovh_count = 0
        self.musixmatch_count = 0

    def load_failed_songs(self) -> List[Dict]:
        """Load songs from failed_lyrics.csv."""
        print("Loading failed songs...")
        songs = []

        if not FAILED_CSV.exists():
            print(f"✗ Failed lyrics CSV not found: {FAILED_CSV}")
            return songs

        with open(FAILED_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            songs = list(reader)

        print(f"✓ Loaded {len(songs)} failed songs for retry\n")
        return songs

    def load_existing_progress(self):
        """Load existing progress from output JSON."""
        if OUTPUT_JSON.exists():
            print("Loading existing retry progress...")
            try:
                with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed = data.get('songs', {})
                    self.retry_attempts = data.get('retry_attempts', {})

                    # Count successes
                    self.success_count = sum(
                        1 for song in self.processed.values()
                        if song.get('lyrics_found', False)
                    )
                    self.fail_count = len(self.processed) - self.success_count

                    print(f"✓ Found {len(self.processed)} previously processed songs")
                    print(f"  - Successful: {self.success_count}")
                    print(f"  - Failed: {self.fail_count}\n")
            except Exception as e:
                print(f"⚠ Error loading progress: {e}\n")
        else:
            print("No existing retry progress found - starting fresh\n")

    def fetch_lyrics_genius(self, track_name: str, artist_name: str) -> Optional[str]:
        """Fetch lyrics from Genius API."""
        if not self.genius:
            print(f"  ⊘ Genius API not initialized")
            return None

        try:
            print(f"  → Searching Genius for: '{track_name}' by '{artist_name}'")
            song = self.genius.search_song(track_name, artist_name)

            if not song:
                print(f"  ✗ Genius: No search results found")
                return None

            print(f"  ✓ Genius: Found '{song.title}' by '{song.artist}'")

            if song.lyrics:
                lyrics_length = len(song.lyrics)
                print(f"  ✓ Genius: Lyrics retrieved ({lyrics_length} chars)")
                return song.lyrics
            else:
                print(f"  ✗ Genius: Song found but no lyrics available")
                return None

        except Exception as e:
            print(f"  ✗ Genius API error: {type(e).__name__}: {str(e)}")
            return None

    def _clean_name_for_search(self, name: str) -> str:
        """
        Clean track/artist name for better API search matching.
        Removes common suffixes and parentheticals that cause mismatches.
        """
        # Remove common parentheticals
        patterns_to_remove = [
            r'\s*\(feat\..*?\)',
            r'\s*\(ft\..*?\)',
            r'\s*\(with.*?\)',
            r'\s*\(Live.*?\)',
            r'\s*\(Acoustic.*?\)',
            r'\s*\(Remastered.*?\)',
            r'\s*\(Radio Edit.*?\)',
            r'\s*\(.*?Version\)',
            r'\s*\(.*?Mix\)',
            r'\s*-\s*Live.*',
            r'\s*-\s*Acoustic.*',
            r'\s*-\s*Remastered.*',
            r'\s*-\s*From\s+".*?"',
            r'\s*-\s*Recorded at.*',
            r'\s*-\s*Radio Edit.*',
        ]

        cleaned = name
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def fetch_lyrics_lyricsovh(self, track_name: str, artist_name: str) -> Optional[str]:
        """
        Fetch lyrics from Lyrics.ovh API (free, no auth required).
        API: https://api.lyrics.ovh/v1/{artist}/{title}
        """
        try:
            # Clean names for better matching
            clean_track = self._clean_name_for_search(track_name)
            clean_artist = self._clean_name_for_search(artist_name)

            print(f"  → Lyrics.ovh: Searching for '{clean_track}' by '{clean_artist}'")

            # Build API URL
            url = f"https://api.lyrics.ovh/v1/{clean_artist}/{clean_track}"

            # Make request with timeout
            response = requests.get(url, timeout=10)

            if response.status_code == 404:
                print(f"  ✗ Lyrics.ovh: Song not found in database")
                return None

            if response.status_code != 200:
                print(f"  ✗ Lyrics.ovh: Request failed (status: {response.status_code})")
                return None

            # Parse JSON response
            data = response.json()
            lyrics = data.get('lyrics')

            if lyrics:
                lyrics_length = len(lyrics)
                print(f"  ✓ Lyrics.ovh: Lyrics retrieved ({lyrics_length} chars)")
                return lyrics
            else:
                print(f"  ✗ Lyrics.ovh: Response OK but no lyrics in data")
                return None

        except requests.exceptions.Timeout:
            print(f"  ✗ Lyrics.ovh: Request timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Lyrics.ovh: Request error: {type(e).__name__}")
            return None
        except json.JSONDecodeError:
            print(f"  ✗ Lyrics.ovh: Invalid JSON response")
            return None
        except Exception as e:
            print(f"  ✗ Lyrics.ovh: Unexpected error: {type(e).__name__}: {str(e)}")
            return None

    def fetch_lyrics_musixmatch(self, track_name: str, artist_name: str, isrc: Optional[str] = None) -> Optional[str]:
        """Fetch lyrics from Musixmatch API using ISRC or search."""
        if not self.musixmatch:
            print(f"  ⊘ Musixmatch API not initialized")
            return None

        # Check if Musixmatch is disabled due to consecutive failures
        if self.musixmatch_disabled:
            print(f"  ⊘ Musixmatch disabled (too many consecutive failures)")
            return None

        try:
            # Try 1: Use ISRC if available
            if isrc:
                print(f"  → Musixmatch: Trying ISRC lookup ({isrc})")
                lyrics_data = self.musixmatch.get_track_lyrics(track_isrc=isrc)

                if lyrics_data and lyrics_data.get('message', {}).get('header', {}).get('status_code') == 200:
                    lyrics_body = lyrics_data['message']['body']['lyrics'].get('lyrics_body')
                    if lyrics_body:
                        print(f"  ✓ Musixmatch: Found via ISRC ({len(lyrics_body)} chars)")
                        return lyrics_body
                    else:
                        print(f"  ✗ Musixmatch: ISRC found but no lyrics body")
                else:
                    status_code = lyrics_data.get('message', {}).get('header', {}).get('status_code') if lyrics_data else None
                    print(f"  ✗ Musixmatch: ISRC lookup failed (status: {status_code})")
            else:
                print(f"  ⊘ Musixmatch: No ISRC available, skipping ISRC lookup")

            # Try 2: Search by track name and artist together
            search_query = f"{track_name} {artist_name}"
            print(f"  → Musixmatch: Searching for '{search_query}'")
            track_id = self._search_track_musixmatch(search_query)

            # Try 3: Search by track name only
            if not track_id:
                print(f"  → Musixmatch: Trying search with track name only: '{track_name}'")
                track_id = self._search_track_musixmatch(track_name)

            # Try 4: Search by artist first, then find track in their catalog
            if not track_id:
                print(f"  → Musixmatch: Trying artist-first search for '{artist_name}'")
                track_id = self._search_via_artist_musixmatch(track_name, artist_name)

            # If we found a track_id through any method, try to get lyrics
            if track_id:
                lyrics_body = self._get_lyrics_by_track_id(track_id)
                if lyrics_body:
                    # Success - reset failure counter
                    self.musixmatch_consecutive_failures = 0
                    return lyrics_body
                else:
                    print(f"  ✗ Musixmatch: Track found but no lyrics available")
                    self._handle_musixmatch_failure()
                    return None
            else:
                print(f"  ✗ Musixmatch: Track not found through any search method")
                self._handle_musixmatch_failure()
                return None

        except json.JSONDecodeError as e:
            print(f"  ✗ Musixmatch error: JSONDecodeError (empty or invalid response)")
            self._handle_musixmatch_failure()
            return None
        except Exception as e:
            print(f"  ✗ Musixmatch error: {type(e).__name__}: {str(e)}")
            self._handle_musixmatch_failure()
            return None

    def _handle_musixmatch_failure(self):
        """Track Musixmatch failures and auto-disable after threshold."""
        self.musixmatch_consecutive_failures += 1

        if self.musixmatch_consecutive_failures >= self.musixmatch_disable_threshold:
            if not self.musixmatch_disabled:
                self.musixmatch_disabled = True
                print(f"\n{'='*70}")
                print(f"⚠ WARNING: Musixmatch disabled after {self.musixmatch_consecutive_failures} consecutive failures")
                print(f"  Likely causes: API rate limit, blocked scraper, or service unavailable")
                print(f"  Will continue with Genius and Lyrics.ovh only")
                print(f"{'='*70}\n")

    def _search_track_musixmatch(self, search_query: str) -> Optional[int]:
        """
        Search for a track on Musixmatch using search_tracks().
        Returns track_id if found, None otherwise.
        """
        try:
            search_data = self.musixmatch.search_tracks(track_query=search_query, page=1)

            if not search_data:
                print(f"    ✗ Search returned no data")
                return None

            status_code = search_data.get('message', {}).get('header', {}).get('status_code')
            if status_code != 200:
                print(f"    ✗ Search failed (status: {status_code})")
                return None

            track_list = search_data.get('message', {}).get('body', {}).get('track_list', [])
            if not track_list:
                print(f"    ✗ No tracks found")
                return None

            # Get the first match
            track_id = track_list[0]['track']['track_id']
            matched_name = track_list[0]['track']['track_name']
            matched_artist = track_list[0]['track']['artist_name']
            print(f"    ✓ Found '{matched_name}' by '{matched_artist}' (ID: {track_id})")
            return track_id

        except Exception as e:
            print(f"    ✗ Search error: {type(e).__name__}: {str(e)}")
            return None

    def _search_via_artist_musixmatch(self, track_name: str, artist_name: str) -> Optional[int]:
        """
        Search for artist first using search_artist(), then find the track in their albums.
        Returns track_id if found, None otherwise.
        """
        try:
            # Step 1: Search for the artist
            print(f"    → Searching for artist: '{artist_name}'")
            artist_data = self.musixmatch.search_artist(query=artist_name, page=1)

            if not artist_data:
                print(f"    ✗ Artist search returned no data")
                return None

            status_code = artist_data.get('message', {}).get('header', {}).get('status_code')
            if status_code != 200:
                print(f"    ✗ Artist search failed (status: {status_code})")
                return None

            artist_list = artist_data.get('message', {}).get('body', {}).get('artist_list', [])
            if not artist_list:
                print(f"    ✗ Artist not found")
                return None

            # Get the first (best) artist match
            artist_id = artist_list[0]['artist']['artist_id']
            matched_artist = artist_list[0]['artist']['artist_name']
            print(f"    ✓ Found artist: '{matched_artist}' (ID: {artist_id})")

            # Step 2: Get artist's albums
            print(f"    → Fetching albums for artist {artist_id}")
            albums_data = self.musixmatch.get_artist_albums(artist_id=artist_id, page=1)

            if not albums_data or albums_data.get('message', {}).get('header', {}).get('status_code') != 200:
                print(f"    ✗ Could not fetch artist albums")
                # Fallback: Try direct track search with artist_id if available
                return self._search_track_by_artist_id(track_name, artist_id)

            album_list = albums_data.get('message', {}).get('body', {}).get('album_list', [])
            if not album_list:
                print(f"    ✗ No albums found for artist")
                return self._search_track_by_artist_id(track_name, artist_id)

            # Step 3: Search through albums for the track
            print(f"    → Searching through {len(album_list)} albums")
            for album_item in album_list[:5]:  # Check first 5 albums to avoid too many requests
                album_id = album_item['album']['album_id']
                album_name = album_item['album']['album_name']

                try:
                    tracks_data = self.musixmatch.get_album_tracks(album_id=album_id, page=1)
                    if tracks_data and tracks_data.get('message', {}).get('header', {}).get('status_code') == 200:
                        track_list = tracks_data.get('message', {}).get('body', {}).get('track_list', [])

                        for track_item in track_list:
                            track = track_item['track']
                            # Case-insensitive comparison
                            if track['track_name'].lower() == track_name.lower():
                                track_id = track['track_id']
                                print(f"    ✓ Found track in album '{album_name}' (ID: {track_id})")
                                return track_id

                except Exception as e:
                    continue  # Skip problematic albums

            print(f"    ✗ Track not found in artist's albums")
            return None

        except Exception as e:
            print(f"    ✗ Artist search error: {type(e).__name__}: {str(e)}")
            return None

    def _search_track_by_artist_id(self, track_name: str, artist_id: int) -> Optional[int]:
        """
        Fallback: Search for track using track name with artist context.
        Returns track_id if found, None otherwise.
        """
        try:
            # Try searching with just the track name and filter by artist in results
            search_data = self.musixmatch.search_tracks(track_query=track_name, page=1)

            if not search_data or search_data.get('message', {}).get('header', {}).get('status_code') != 200:
                return None

            track_list = search_data.get('message', {}).get('body', {}).get('track_list', [])

            # Look for a track by this artist
            for track_item in track_list[:10]:  # Check first 10 results
                track = track_item['track']
                if track['artist_id'] == artist_id:
                    track_id = track['track_id']
                    print(f"    ✓ Found track via artist_id match (ID: {track_id})")
                    return track_id

            return None

        except Exception as e:
            return None

    def _get_lyrics_by_track_id(self, track_id: int) -> Optional[str]:
        """
        Fetch lyrics using a track_id.
        Returns lyrics text if found, None otherwise.
        """
        try:
            print(f"  → Musixmatch: Fetching lyrics for track_id {track_id}")
            lyrics_data = self.musixmatch.get_track_lyrics(track_id=track_id)

            if not lyrics_data:
                print(f"    ✗ Lyrics request returned no data")
                return None

            status_code = lyrics_data.get('message', {}).get('header', {}).get('status_code')
            if status_code != 200:
                print(f"    ✗ Lyrics fetch failed (status: {status_code})")
                return None

            lyrics_body = lyrics_data.get('message', {}).get('body', {}).get('lyrics', {}).get('lyrics_body')
            if lyrics_body:
                print(f"  ✓ Musixmatch: Lyrics retrieved ({len(lyrics_body)} chars)")
                return lyrics_body
            else:
                return None

        except Exception as e:
            print(f"    ✗ Lyrics fetch error: {type(e).__name__}: {str(e)}")
            return None

    def process_song(self, song: Dict) -> Dict:
        """Process a single song and attempt to fetch lyrics."""
        track_id = song['track_id']
        track_name = song['track_name']
        artist_name = song['artist_name']

        # Skip if already successfully processed
        if track_id in self.processed:
            if self.processed[track_id].get('lyrics_found', False):
                print(f"⊘ Skipping {track_name} - {artist_name} (already found)")
                return self.processed[track_id]

        # Track retry attempts
        attempts = self.retry_attempts.get(track_id, 0) + 1
        self.retry_attempts[track_id] = attempts

        print(f"🔄 [{attempts}] {track_name} - {artist_name}")

        result = {
            'track_id': track_id,
            'track_name': track_name,
            'artist_name': artist_name,
            'album_name': song.get('album_name', ''),
            'isrc': song.get('isrc', ''),
            'lyrics_found': False,
            'lyrics_source': None,
            'lyrics': None,
            'failure_reason': None,
            'attempted_sources': [],
            'api_errors': {},
            'processed_timestamp': datetime.now().isoformat(),
            'retry_attempt': attempts
        }

        # Strategy 1: Try Genius API (primary)
        result['attempted_sources'].append('genius')
        lyrics = self.fetch_lyrics_genius(track_name, artist_name)
        if lyrics:
            result['lyrics'] = lyrics
            result['lyrics_found'] = True
            result['lyrics_source'] = 'genius'
            print(f"  ✓ Found via Genius")
            self.success_count += 1
            self.genius_count += 1
            return result

        # Strategy 2: Try Lyrics.ovh API (secondary)
        time.sleep(1)  # Rate limiting
        result['attempted_sources'].append('lyricsovh')
        lyrics = self.fetch_lyrics_lyricsovh(track_name, artist_name)
        if lyrics:
            result['lyrics'] = lyrics
            result['lyrics_found'] = True
            result['lyrics_source'] = 'lyricsovh'
            print(f"  ✓ Found via Lyrics.ovh")
            self.success_count += 1
            self.lyricsovh_count += 1
            return result

        # Strategy 3: Try Musixmatch API (fallback, if not disabled)
        time.sleep(1.5)  # Rate limiting
        if not self.musixmatch_disabled:
            result['attempted_sources'].append('musixmatch')
            isrc = song.get('isrc')
            lyrics = self.fetch_lyrics_musixmatch(track_name, artist_name, isrc)
            if lyrics:
                result['lyrics'] = lyrics
                result['lyrics_found'] = True
                result['lyrics_source'] = 'musixmatch'
                print(f"  ✓ Found via Musixmatch")
                self.success_count += 1
                self.musixmatch_count += 1
                return result
        else:
            result['api_errors']['musixmatch'] = 'Disabled due to consecutive failures'

        # Still failed - determine reason
        print(f"  ✗ Not found")

        # Build detailed failure reason
        sources_tried = ', '.join(result['attempted_sources'])
        result['failure_reason'] = f'Not found on any source (tried: {sources_tried})'

        # Add ISRC context
        if not song.get('isrc'):
            result['failure_reason'] += '; No ISRC available for Musixmatch lookup'

        # Check if it might be instrumental/score
        track_lower = track_name.lower()
        instrumental_keywords = ['instrumental', 'theme', 'score', 'soundtrack', 'orchestral', 'outro', 'intro', 'interlude', 'overture', 'prelude']
        if any(keyword in track_lower for keyword in instrumental_keywords):
            result['failure_reason'] += ' (likely instrumental/score - no lyrics exist)'

        # Add Musixmatch status if disabled
        if self.musixmatch_disabled and 'musixmatch' not in result['attempted_sources']:
            result['failure_reason'] += ' (Musixmatch was disabled)'

        print(f"  → Reason: {result['failure_reason']}")

        self.fail_count += 1
        return result

    def save_progress(self):
        """Save current progress to JSON."""
        output_data = {
            'metadata': {
                'total_processed': len(self.processed),
                'successful': self.success_count,
                'failed': self.fail_count,
                'success_by_source': {
                    'genius': self.genius_count,
                    'lyricsovh': self.lyricsovh_count,
                    'musixmatch': self.musixmatch_count
                },
                'musixmatch_status': {
                    'disabled': self.musixmatch_disabled,
                    'consecutive_failures': self.musixmatch_consecutive_failures
                },
                'last_updated': datetime.now().isoformat(),
                'source_file': str(FAILED_CSV),
            },
            'songs': self.processed,
            'retry_attempts': self.retry_attempts
        }

        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

    def run(self):
        """Main processing loop."""
        songs = self.load_failed_songs()
        if not songs:
            print("No songs to process!")
            return

        self.load_existing_progress()

        print("=" * 70)
        print("  RETRY PROCESSING FAILED LYRICS")
        print("=" * 70)
        print(f"Total songs to retry: {len(songs)}")
        print(f"Output: {OUTPUT_JSON}")
        print("=" * 70 + "\n")

        for i, song in enumerate(songs, 1):
            try:
                result = self.process_song(song)
                self.processed[song['track_id']] = result

                # Save periodically
                if i % SAVE_INTERVAL == 0:
                    self.save_progress()
                    print(f"\n💾 Progress saved ({i}/{len(songs)})\n")

            except Exception as e:
                print(f"✗ Error processing {song.get('track_name', 'unknown')}: {e}\n")
                continue

        # Final save
        self.save_progress()

        # Print summary
        print("\n" + "=" * 70)
        print("  RETRY PROCESSING COMPLETE!")
        print("=" * 70)
        print(f"Total processed: {len(self.processed)}")
        print(f"Newly found: {self.success_count}")
        print(f"Still failed: {self.fail_count}")
        print(f"\nSuccess by Source:")
        print(f"  • Genius API: {self.genius_count}")
        print(f"  • Lyrics.ovh API: {self.lyricsovh_count}")
        print(f"  • Musixmatch API: {self.musixmatch_count}")
        print(f"\nMusixmatch Status:")
        if self.musixmatch_disabled:
            print(f"  • Disabled after {self.musixmatch_consecutive_failures} consecutive failures")
        else:
            print(f"  • Active (consecutive failures: {self.musixmatch_consecutive_failures})")
        print(f"\nOutput saved to: {OUTPUT_JSON}")
        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    try:
        processor = FailedLyricsRetryProcessor()
        processor.run()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        if hasattr(processor, 'save_progress'):
            print("Saving progress...")
            processor.save_progress()
            print("✓ Progress saved")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
