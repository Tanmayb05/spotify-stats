"""
Debug script to check why artist genres are empty.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json

# Load environment variables
repo_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(repo_root / 'spotify-insights.env')

# Initialize Spotify
client_id = os.getenv('SPOTIFY_CLIENT_ID')
client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
spotify = spotipy.Spotify(auth_manager=auth_manager)

# Test with known artists
test_artists = [
    "ZAYN",
    "Post Malone",
    "Taylor Swift",
    "Ed Sheeran",
    "Drake"
]

print("Testing artist genre retrieval:\n")
print("="*70)

for artist_name in test_artists:
    print(f"\nArtist: {artist_name}")

    # Search for artist
    results = spotify.search(q=f'artist:"{artist_name}"', type='artist', limit=1)

    if results and 'artists' in results and results['artists']['items']:
        artist = results['artists']['items'][0]

        print(f"  Found: {artist['name']}")
        print(f"  ID: {artist['id']}")
        print(f"  Genres from search: {artist.get('genres', [])}")

        # Now fetch full artist object
        full_artist = spotify.artist(artist['id'])
        print(f"  Genres from artist endpoint: {full_artist.get('genres', [])}")

        # Show full artist object structure
        print(f"\n  Full artist object keys: {list(full_artist.keys())}")
        print(f"  Full artist object:")
        print(f"  {json.dumps(full_artist, indent=4)}")
    else:
        print(f"  Not found!")

    print("-"*70)
