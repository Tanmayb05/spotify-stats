import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from collections import defaultdict

# Path to data directory
DATA_DIR = Path(__file__).parent.parent.parent.parent / 'data'


class SpotifyDataLoader:
    """Service to load and process Spotify streaming data"""

    def __init__(self):
        self._data: List[Dict[str, Any]] = []
        self._loaded = False

    def load_data(self) -> None:
        """Load all audio streaming JSON files"""
        if self._loaded:
            return

        # Load audio streaming files (exclude video)
        audio_files = sorted(DATA_DIR.glob('streaming_[0-9]*.json'))

        all_data = []
        for file in audio_files:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_data.extend(data)

        self._data = all_data
        self._loaded = True
        print(f"✅ Loaded {len(self._data)} streaming records from {len(audio_files)} files")

    def get_overview_stats(self) -> Dict[str, Any]:
        """Get overview statistics"""
        if not self._loaded:
            self.load_data()

        # Calculate basic stats
        total_streams = len(self._data)
        total_ms = sum(record.get('ms_played', 0) for record in self._data)
        total_hours = total_ms / 3_600_000

        unique_tracks = len(set(
            record.get('master_metadata_track_name')
            for record in self._data
            if record.get('master_metadata_track_name')
        ))

        unique_artists = len(set(
            record.get('master_metadata_album_artist_name')
            for record in self._data
            if record.get('master_metadata_album_artist_name')
        ))

        unique_albums = len(set(
            record.get('master_metadata_album_album_name')
            for record in self._data
            if record.get('master_metadata_album_album_name')
        ))

        return {
            'total_streams': total_streams,
            'total_hours': round(total_hours, 2),
            'unique_tracks': unique_tracks,
            'unique_artists': unique_artists,
            'unique_albums': unique_albums,
        }

    def get_top_artists(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top artists by stream count"""
        if not self._loaded:
            self.load_data()

        artist_counts = defaultdict(int)
        for record in self._data:
            artist = record.get('master_metadata_album_artist_name')
            if artist:
                artist_counts[artist] += 1

        # Sort and get top N
        top_artists = sorted(
            artist_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {'artist': artist, 'streams': count}
            for artist, count in top_artists
        ]

    def get_top_tracks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top tracks by stream count"""
        if not self._loaded:
            self.load_data()

        track_counts = defaultdict(int)
        for record in self._data:
            track = record.get('master_metadata_track_name')
            artist = record.get('master_metadata_album_artist_name')
            if track and artist:
                key = f"{track}|||{artist}"
                track_counts[key] += 1

        # Sort and get top N
        top_tracks = sorted(
            track_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {
                'track': key.split('|||')[0],
                'artist': key.split('|||')[1],
                'streams': count
            }
            for key, count in top_tracks
        ]

    def get_monthly_data(self) -> List[Dict[str, Any]]:
        """Get monthly streaming statistics"""
        if not self._loaded:
            self.load_data()

        monthly_stats = defaultdict(lambda: {'streams': 0, 'hours': 0})

        for record in self._data:
            ts = record.get('ts')
            if ts:
                # Parse timestamp
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                month_key = dt.strftime('%Y-%m')

                monthly_stats[month_key]['streams'] += 1
                monthly_stats[month_key]['hours'] += record.get('ms_played', 0) / 3_600_000

        # Convert to list and sort by month
        result = [
            {
                'month': month,
                'streams': data['streams'],
                'hours': round(data['hours'], 2)
            }
            for month, data in sorted(monthly_stats.items())
        ]

        return result

    def get_platform_stats(self) -> List[Dict[str, Any]]:
        """Get platform usage statistics"""
        if not self._loaded:
            self.load_data()

        platform_counts = defaultdict(int)
        for record in self._data:
            platform = record.get('platform')
            if platform:
                platform_counts[platform] += 1

        # Sort by count
        sorted_platforms = sorted(
            platform_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Get top 10 and group rest as "Other"
        top_10 = sorted_platforms[:10]
        other_count = sum(count for _, count in sorted_platforms[10:])

        result = [
            {'platform': platform, 'streams': count}
            for platform, count in top_10
        ]

        if other_count > 0:
            result.append({'platform': 'Other', 'streams': other_count})

        return result


# Global instance
spotify_data = SpotifyDataLoader()
