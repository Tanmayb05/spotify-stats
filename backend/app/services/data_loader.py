import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

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

    def _calculate_mood_metrics(self, record: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Calculate mood metrics from listening behavior patterns.

        Returns valence, energy, and danceability scores (0-1 scale)
        based on listening context and behavior.
        """
        ts = record.get('ts')
        if not ts:
            return {'valence': None, 'energy': None, 'danceability': None}

        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        hour = dt.hour
        is_weekend = dt.weekday() >= 5

        # Valence (happiness): Based on time of day and day of week
        # Higher on weekends and during daytime (10am-8pm)
        valence = 0.5
        if is_weekend:
            valence += 0.15
        if 10 <= hour <= 20:
            valence += 0.15
        elif 6 <= hour < 10 or 20 < hour <= 23:
            valence += 0.05
        else:  # Late night/early morning
            valence -= 0.10

        # Energy: Based on time of day and listening intensity
        # Higher in morning/afternoon, lower at night
        energy = 0.5
        if 6 <= hour <= 12:  # Morning
            energy += 0.25
        elif 12 < hour <= 18:  # Afternoon
            energy += 0.15
        elif 18 < hour <= 22:  # Evening
            energy += 0.05
        else:  # Night/early morning
            energy -= 0.15

        # Danceability: Based on skip behavior and play duration
        # Higher for tracks played longer (not skipped)
        ms_played = record.get('ms_played', 0)
        skipped = record.get('skipped', False)

        danceability = 0.5
        if ms_played >= 180000:  # 3+ minutes = full listen
            danceability += 0.25
        elif ms_played >= 60000:  # 1-3 minutes
            danceability += 0.10
        else:  # < 1 minute = probably skipped
            danceability -= 0.15

        if skipped:
            danceability -= 0.20

        # Clamp values to 0-1 range
        valence = max(0.0, min(1.0, valence))
        energy = max(0.0, min(1.0, energy))
        danceability = max(0.0, min(1.0, danceability))

        return {
            'valence': round(valence, 3),
            'energy': round(energy, 3),
            'danceability': round(danceability, 3)
        }

    def get_mood_summary(self, window_days: int = 30) -> Dict[str, Any]:
        """
        Get mood statistics for a time window based on listening patterns

        Args:
            window_days: Number of days to look back (7, 30, 90, etc.)

        Returns:
            Average valence, energy, danceability and sample size
        """
        if not self._loaded:
            self.load_data()

        # Use timezone-aware datetime to match data timestamps
        from datetime import timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=window_days)

        valences = []
        energies = []
        danceabilities = []

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if dt < cutoff_date:
                continue

            # Calculate mood metrics from listening behavior
            metrics = self._calculate_mood_metrics(record)

            if metrics['valence'] is not None:
                valences.append(metrics['valence'])
            if metrics['energy'] is not None:
                energies.append(metrics['energy'])
            if metrics['danceability'] is not None:
                danceabilities.append(metrics['danceability'])

        return {
            'window_days': window_days,
            'avg_valence': round(statistics.mean(valences), 3) if valences else None,
            'avg_energy': round(statistics.mean(energies), 3) if energies else None,
            'avg_danceability': round(statistics.mean(danceabilities), 3) if danceabilities else None,
            'sample_size': len(valences),
        }

    def get_mood_contexts(self) -> Dict[str, Any]:
        """
        Compare mood metrics across different contexts based on listening patterns:
        - Weekday vs Weekend
        - Different platforms (if available)

        Returns:
            Dictionary with context comparisons
        """
        if not self._loaded:
            self.load_data()

        weekday_moods = {'valence': [], 'energy': [], 'danceability': []}
        weekend_moods = {'valence': [], 'energy': [], 'danceability': []}
        platform_moods = defaultdict(lambda: {'valence': [], 'energy': [], 'danceability': []})

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            is_weekend = dt.weekday() >= 5  # Saturday=5, Sunday=6
            platform = record.get('platform', 'unknown')

            # Calculate mood metrics from listening behavior
            metrics = self._calculate_mood_metrics(record)

            valence = metrics['valence']
            energy = metrics['energy']
            danceability = metrics['danceability']

            if valence is not None:
                if is_weekend:
                    weekend_moods['valence'].append(valence)
                else:
                    weekday_moods['valence'].append(valence)
                platform_moods[platform]['valence'].append(valence)

            if energy is not None:
                if is_weekend:
                    weekend_moods['energy'].append(energy)
                else:
                    weekday_moods['energy'].append(energy)
                platform_moods[platform]['energy'].append(energy)

            if danceability is not None:
                if is_weekend:
                    weekend_moods['danceability'].append(danceability)
                else:
                    weekday_moods['danceability'].append(danceability)
                platform_moods[platform]['danceability'].append(danceability)

        # Calculate averages
        def avg_or_none(lst):
            return round(statistics.mean(lst), 3) if lst else None

        result = {
            'weekday_vs_weekend': {
                'weekday': {
                    'avg_valence': avg_or_none(weekday_moods['valence']),
                    'avg_energy': avg_or_none(weekday_moods['energy']),
                    'avg_danceability': avg_or_none(weekday_moods['danceability']),
                    'sample_size': len(weekday_moods['valence']),
                },
                'weekend': {
                    'avg_valence': avg_or_none(weekend_moods['valence']),
                    'avg_energy': avg_or_none(weekend_moods['energy']),
                    'avg_danceability': avg_or_none(weekend_moods['danceability']),
                    'sample_size': len(weekend_moods['valence']),
                }
            },
            'by_platform': {
                platform: {
                    'avg_valence': avg_or_none(moods['valence']),
                    'avg_energy': avg_or_none(moods['energy']),
                    'avg_danceability': avg_or_none(moods['danceability']),
                    'sample_size': len(moods['valence']),
                }
                for platform, moods in platform_moods.items()
                if len(moods['valence']) >= 10  # Only include platforms with enough data
            }
        }

        return result

    def get_mood_monthly(self) -> List[Dict[str, Any]]:
        """Get monthly mood averages over time based on listening patterns"""
        if not self._loaded:
            self.load_data()

        monthly_moods = defaultdict(lambda: {
            'valence': [],
            'energy': [],
            'danceability': []
        })

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            month_key = dt.strftime('%Y-%m')

            # Calculate mood metrics from listening behavior
            metrics = self._calculate_mood_metrics(record)

            if metrics['valence'] is not None:
                monthly_moods[month_key]['valence'].append(metrics['valence'])
            if metrics['energy'] is not None:
                monthly_moods[month_key]['energy'].append(metrics['energy'])
            if metrics['danceability'] is not None:
                monthly_moods[month_key]['danceability'].append(metrics['danceability'])

        # Calculate monthly averages
        result = []
        for month in sorted(monthly_moods.keys()):
            moods = monthly_moods[month]
            result.append({
                'month': month,
                'avg_valence': round(statistics.mean(moods['valence']), 3) if moods['valence'] else None,
                'avg_energy': round(statistics.mean(moods['energy']), 3) if moods['energy'] else None,
                'avg_danceability': round(statistics.mean(moods['danceability']), 3) if moods['danceability'] else None,
                'sample_size': len(moods['valence']),
            })

        return result


# Global instance
spotify_data = SpotifyDataLoader()
