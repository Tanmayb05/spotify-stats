import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

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

    def get_discovery_timeline(self) -> List[Dict[str, Any]]:
        """
        Get artist discovery timeline - when artists were first discovered

        Returns:
            List of {month, new_artists_count}
        """
        if not self._loaded:
            self.load_data()

        # Track first appearance of each artist
        artist_first_seen = {}

        for record in self._data:
            ts = record.get('ts')
            artist = record.get('master_metadata_album_artist_name')

            if not ts or not artist:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))

            # Track first time we saw this artist
            if artist not in artist_first_seen:
                artist_first_seen[artist] = dt

        # Count discoveries by month
        monthly_discoveries = defaultdict(int)
        for artist, first_date in artist_first_seen.items():
            month_key = first_date.strftime('%Y-%m')
            monthly_discoveries[month_key] += 1

        # Convert to sorted list
        result = [
            {
                'month': month,
                'new_artists_count': count
            }
            for month, count in sorted(monthly_discoveries.items())
        ]

        return result

    def get_artist_loyalty(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Calculate artist loyalty metrics based on return probability and half-life

        Args:
            limit: Number of top artists to analyze

        Returns:
            List of {artist, return_prob, half_life_days, total_streams}
        """
        if not self._loaded:
            self.load_data()

        # Get top artists first
        top_artists_data = self.get_top_artists(limit=limit * 2)  # Get more to filter
        top_artists = {a['artist'] for a in top_artists_data[:limit]}

        # Track listening sessions per artist
        artist_sessions = defaultdict(list)

        for record in self._data:
            artist = record.get('master_metadata_album_artist_name')
            ts = record.get('ts')

            if not artist or not ts or artist not in top_artists:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            artist_sessions[artist].append(dt)

        # Calculate loyalty metrics
        results = []
        for artist in top_artists:
            if artist not in artist_sessions:
                continue

            sessions = sorted(artist_sessions[artist])
            if len(sessions) < 5:  # Need minimum sessions to calculate
                continue

            # Calculate gaps between listens
            gaps = []
            for i in range(1, len(sessions)):
                gap = (sessions[i] - sessions[i-1]).days
                if gap > 0:  # Only count positive gaps
                    gaps.append(gap)

            if not gaps:
                continue

            # Return probability: inverse of average gap
            # Smaller gaps = higher return probability
            avg_gap = statistics.mean(gaps)
            return_prob = min(100.0, 100.0 / (1 + avg_gap))

            # Half-life: median gap (time until 50% likely to return)
            half_life = statistics.median(gaps)

            results.append({
                'artist': artist,
                'return_prob': round(return_prob, 1),
                'half_life_days': round(half_life, 1),
                'total_streams': len(sessions)
            })

        # Sort by return probability
        results.sort(key=lambda x: x['return_prob'], reverse=True)

        return results[:limit]

    def get_artist_obsessions(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Identify obsession periods - when an artist dominated listening

        Args:
            limit: Number of top obsessions to return

        Returns:
            List of {artist, period_start, period_end, period_share, streams_in_period}
        """
        if not self._loaded:
            self.load_data()

        # Group streams by 7-day windows
        window_days = 7
        artist_by_window = defaultdict(lambda: defaultdict(int))
        window_totals = defaultdict(int)

        for record in self._data:
            ts = record.get('ts')
            artist = record.get('master_metadata_album_artist_name')

            if not ts or not artist:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            # Create window key (week starting Monday)
            week_start = dt - timedelta(days=dt.weekday())
            window_key = week_start.strftime('%Y-%m-%d')

            artist_by_window[window_key][artist] += 1
            window_totals[window_key] += 1

        # Find periods where artist dominated (>30% share)
        obsessions = []
        for window, artists in artist_by_window.items():
            total = window_totals[window]
            if total < 10:  # Skip windows with very few streams
                continue

            for artist, count in artists.items():
                share = (count / total) * 100
                if share >= 30.0:  # Obsession threshold
                    window_date = datetime.strptime(window, '%Y-%m-%d')
                    obsessions.append({
                        'artist': artist,
                        'period_start': window,
                        'period_end': (window_date + timedelta(days=6)).strftime('%Y-%m-%d'),
                        'period_share': round(share, 1),
                        'streams_in_period': count
                    })

        # Sort by period share
        obsessions.sort(key=lambda x: x['period_share'], reverse=True)

        return obsessions[:limit]

    def get_reflective_insights(self) -> Dict[str, Any]:
        """
        Generate reflective insights about listening patterns

        Returns:
            Dictionary with various insights and statistics
        """
        if not self._loaded:
            self.load_data()

        # Calculate various insights
        total_streams = len(self._data)

        # Time-based insights
        hour_distribution = defaultdict(int)
        weekday_distribution = defaultdict(int)

        # Streak calculations
        daily_streams = defaultdict(int)

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            hour_distribution[dt.hour] += 1
            weekday_distribution[dt.weekday()] += 1
            daily_streams[dt.date()] += 1

        # Find longest streak
        if daily_streams:
            sorted_dates = sorted(daily_streams.keys())
            current_streak = 1
            longest_streak = 1

            for i in range(1, len(sorted_dates)):
                if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                    current_streak += 1
                    longest_streak = max(longest_streak, current_streak)
                else:
                    current_streak = 1
        else:
            longest_streak = 0

        # Most active hour
        most_active_hour = max(hour_distribution.items(), key=lambda x: x[1])[0] if hour_distribution else 0

        # Most active day
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        most_active_day_idx = max(weekday_distribution.items(), key=lambda x: x[1])[0] if weekday_distribution else 0
        most_active_day = day_names[most_active_day_idx]

        # Top artist
        top_artist = self.get_top_artists(limit=1)[0]['artist'] if self._data else 'Unknown'

        # Calculate average streams per day
        if daily_streams:
            date_range = (max(daily_streams.keys()) - min(daily_streams.keys())).days + 1
            avg_streams_per_day = total_streams / date_range if date_range > 0 else 0
        else:
            avg_streams_per_day = 0

        return {
            'total_streams': total_streams,
            'longest_streak_days': longest_streak,
            'most_active_hour': most_active_hour,
            'most_active_day': most_active_day,
            'top_artist': top_artist,
            'avg_streams_per_day': round(avg_streams_per_day, 1),
            'insights': [
                f"You've maintained a {longest_streak}-day listening streak!",
                f"Your peak listening hour is {most_active_hour}:00",
                f"{most_active_day}s are your most active listening days",
                f"{top_artist} is your most-played artist"
            ]
        }

    def get_hourly_distribution(self) -> List[Dict[str, Any]]:
        """
        Get listening distribution by hour of day (0-23)

        Returns:
            List of {hour, streams}
        """
        if not self._loaded:
            self.load_data()

        hour_distribution = defaultdict(int)

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            hour_distribution[dt.hour] += 1

        # Create list for all 24 hours (fill missing with 0)
        result = [
            {'hour': hour, 'streams': hour_distribution.get(hour, 0)}
            for hour in range(24)
        ]

        return result

    def get_daily_distribution(self) -> List[Dict[str, Any]]:
        """
        Get listening distribution by day of week

        Returns:
            List of {day, streams} - ordered Mon-Sun
        """
        if not self._loaded:
            self.load_data()

        day_distribution = defaultdict(int)

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            day_distribution[dt.weekday()] += 1

        # Map to day names
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        result = [
            {'day': day_names[day_idx], 'streams': day_distribution.get(day_idx, 0)}
            for day_idx in range(7)
        ]

        return result

    def get_skip_behavior(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Analyze skip behavior by artist

        Args:
            limit: Number of top artists to analyze

        Returns:
            List of {artist, total_streams, skipped_count, skip_rate}
        """
        if not self._loaded:
            self.load_data()

        # Track streams and skips per artist
        artist_stats = defaultdict(lambda: {'total': 0, 'skipped': 0})

        for record in self._data:
            artist = record.get('master_metadata_album_artist_name')
            if not artist:
                continue

            skipped = record.get('skipped', False)
            artist_stats[artist]['total'] += 1
            if skipped:
                artist_stats[artist]['skipped'] += 1

        # Calculate skip rates
        results = []
        for artist, stats in artist_stats.items():
            if stats['total'] < 5:  # Need minimum streams for meaningful rate
                continue

            skip_rate = (stats['skipped'] / stats['total']) * 100 if stats['total'] > 0 else 0
            results.append({
                'artist': artist,
                'total_streams': stats['total'],
                'skipped_count': stats['skipped'],
                'skip_rate': round(skip_rate, 2)
            })

        # Get top artists by total streams, then show their skip rates
        results.sort(key=lambda x: x['total_streams'], reverse=True)

        return results[:limit]

    def get_yearly_comparison(self) -> List[Dict[str, Any]]:
        """
        Get year-over-year listening comparison

        Returns:
            List of {year, streams, hours}
        """
        if not self._loaded:
            self.load_data()

        yearly_stats = defaultdict(lambda: {'streams': 0, 'hours': 0})

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            year = dt.year

            yearly_stats[year]['streams'] += 1
            yearly_stats[year]['hours'] += record.get('ms_played', 0) / 3_600_000

        # Convert to sorted list
        result = [
            {
                'year': year,
                'streams': data['streams'],
                'hours': round(data['hours'], 2)
            }
            for year, data in sorted(yearly_stats.items())
        ]

        return result

    def get_session_durations(self) -> List[Dict[str, Any]]:
        """
        Get distribution of session durations (grouped listening periods)
        Session = continuous listening with <30min gaps

        Returns:
            List of {duration_minutes, session_count} for histogram
        """
        if not self._loaded:
            self.load_data()

        # Group streams into sessions (30min gap threshold)
        sessions = []
        current_session_start = None
        current_session_end = None

        sorted_records = sorted(
            [r for r in self._data if r.get('ts')],
            key=lambda x: datetime.fromisoformat(x['ts'].replace('Z', '+00:00'))
        )

        for record in sorted_records:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))

            if current_session_start is None:
                current_session_start = dt
                current_session_end = dt
            else:
                # Check if this is same session (<30min gap)
                gap = (dt - current_session_end).total_seconds() / 60
                if gap <= 30:
                    current_session_end = dt
                else:
                    # Save previous session and start new one
                    duration_mins = (current_session_end - current_session_start).total_seconds() / 60
                    sessions.append(duration_mins)
                    current_session_start = dt
                    current_session_end = dt

        # Don't forget last session
        if current_session_start and current_session_end:
            duration_mins = (current_session_end - current_session_start).total_seconds() / 60
            sessions.append(duration_mins)

        # Group into buckets for distribution
        buckets = defaultdict(int)
        for duration in sessions:
            if duration < 15:
                buckets['0-15'] += 1
            elif duration < 30:
                buckets['15-30'] += 1
            elif duration < 60:
                buckets['30-60'] += 1
            elif duration < 120:
                buckets['60-120'] += 1
            elif duration < 180:
                buckets['120-180'] += 1
            else:
                buckets['180+'] += 1

        bucket_order = ['0-15', '15-30', '30-60', '60-120', '120-180', '180+']
        result = [
            {'duration_range': bucket, 'session_count': buckets.get(bucket, 0)}
            for bucket in bucket_order
        ]

        return result

    def get_binge_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get top binge sessions (longest continuous listening periods)

        Returns:
            List of {session_date, duration_minutes, track_count}
        """
        if not self._loaded:
            self.load_data()

        # Group streams into sessions (30min gap threshold)
        sessions = []
        current_session = {
            'start': None,
            'end': None,
            'tracks': 0
        }

        sorted_records = sorted(
            [r for r in self._data if r.get('ts')],
            key=lambda x: datetime.fromisoformat(x['ts'].replace('Z', '+00:00'))
        )

        for record in sorted_records:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))

            if current_session['start'] is None:
                current_session['start'] = dt
                current_session['end'] = dt
                current_session['tracks'] = 1
            else:
                gap = (dt - current_session['end']).total_seconds() / 60
                if gap <= 30:
                    current_session['end'] = dt
                    current_session['tracks'] += 1
                else:
                    # Save and start new
                    sessions.append(current_session.copy())
                    current_session = {
                        'start': dt,
                        'end': dt,
                        'tracks': 1
                    }

        # Don't forget last session
        if current_session['start']:
            sessions.append(current_session)

        # Calculate durations and sort
        for session in sessions:
            duration = (session['end'] - session['start']).total_seconds() / 60
            session['duration_minutes'] = round(duration, 1)
            session['session_date'] = session['start'].strftime('%Y-%m-%d %H:%M')

        sessions.sort(key=lambda x: x['duration_minutes'], reverse=True)

        return [
            {
                'session_date': s['session_date'],
                'duration_minutes': s['duration_minutes'],
                'track_count': s['tracks']
            }
            for s in sessions[:limit]
        ]

    def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate session statistics

        Returns:
            Overall session stats (avg duration, tracks per session, etc.)
        """
        if not self._loaded:
            self.load_data()

        sessions = []
        current_session = {'start': None, 'end': None, 'tracks': 0}

        sorted_records = sorted(
            [r for r in self._data if r.get('ts')],
            key=lambda x: datetime.fromisoformat(x['ts'].replace('Z', '+00:00'))
        )

        for record in sorted_records:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))

            if current_session['start'] is None:
                current_session = {'start': dt, 'end': dt, 'tracks': 1}
            else:
                gap = (dt - current_session['end']).total_seconds() / 60
                if gap <= 30:
                    current_session['end'] = dt
                    current_session['tracks'] += 1
                else:
                    sessions.append(current_session.copy())
                    current_session = {'start': dt, 'end': dt, 'tracks': 1}

        if current_session['start']:
            sessions.append(current_session)

        # Calculate stats
        durations = [(s['end'] - s['start']).total_seconds() / 60 for s in sessions]
        track_counts = [s['tracks'] for s in sessions]

        return {
            'total_sessions': len(sessions),
            'avg_duration_minutes': round(statistics.mean(durations), 1) if durations else 0,
            'median_duration_minutes': round(statistics.median(durations), 1) if durations else 0,
            'avg_tracks_per_session': round(statistics.mean(track_counts), 1) if track_counts else 0,
            'longest_session_minutes': round(max(durations), 1) if durations else 0,
        }

    def get_weekend_weekday_comparison(self) -> Dict[str, Any]:
        """
        Detailed weekend vs weekday listening comparison

        Returns:
            Comparison statistics and breakdown
        """
        if not self._loaded:
            self.load_data()

        weekday_streams = 0
        weekend_streams = 0
        weekday_hours = 0.0
        weekend_hours = 0.0

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            is_weekend = dt.weekday() >= 5
            hours = record.get('ms_played', 0) / 3_600_000

            if is_weekend:
                weekend_streams += 1
                weekend_hours += hours
            else:
                weekday_streams += 1
                weekday_hours += hours

        return {
            'weekday': {
                'streams': weekday_streams,
                'hours': round(weekday_hours, 2),
                'avg_per_day': round(weekday_streams / 5, 1) if weekday_streams > 0 else 0
            },
            'weekend': {
                'streams': weekend_streams,
                'hours': round(weekend_hours, 2),
                'avg_per_day': round(weekend_streams / 2, 1) if weekend_streams > 0 else 0
            }
        }

    def get_listening_streaks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get consecutive day listening streaks

        Returns:
            List of {start_date, end_date, length_days, total_streams}
        """
        if not self._loaded:
            self.load_data()

        # Get unique dates with stream counts
        daily_streams = defaultdict(int)
        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            daily_streams[dt.date()] += 1

        if not daily_streams:
            return []

        # Find streaks
        sorted_dates = sorted(daily_streams.keys())
        streaks = []
        current_streak = {
            'start': sorted_dates[0],
            'end': sorted_dates[0],
            'streams': daily_streams[sorted_dates[0]]
        }

        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                # Continue streak
                current_streak['end'] = sorted_dates[i]
                current_streak['streams'] += daily_streams[sorted_dates[i]]
            else:
                # End streak, save and start new
                if (current_streak['end'] - current_streak['start']).days >= 2:
                    streaks.append(current_streak.copy())
                current_streak = {
                    'start': sorted_dates[i],
                    'end': sorted_dates[i],
                    'streams': daily_streams[sorted_dates[i]]
                }

        # Don't forget last streak
        if (current_streak['end'] - current_streak['start']).days >= 2:
            streaks.append(current_streak)

        # Sort by length
        for streak in streaks:
            streak['length_days'] = (streak['end'] - streak['start']).days + 1
            streak['start_date'] = streak['start'].isoformat()
            streak['end_date'] = streak['end'].isoformat()
            streak['total_streams'] = streak['streams']
            del streak['start']
            del streak['end']
            del streak['streams']

        streaks.sort(key=lambda x: x['length_days'], reverse=True)

        return streaks[:limit]

    def get_most_repeated_tracks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get tracks played most frequently (on repeat)

        Returns:
            List of {track, artist, play_count, repeat_score}
        """
        if not self._loaded:
            self.load_data()

        track_plays = defaultdict(lambda: {'count': 0, 'dates': set(), 'artist': None})

        for record in self._data:
            track = record.get('master_metadata_track_name')
            artist = record.get('master_metadata_album_artist_name')
            ts = record.get('ts')

            if not track or not artist or not ts:
                continue

            key = f"{track}|||{artist}"
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))

            track_plays[key]['count'] += 1
            track_plays[key]['dates'].add(dt.date())
            track_plays[key]['artist'] = artist

        # Calculate repeat score (plays per unique day)
        results = []
        for key, data in track_plays.items():
            if data['count'] < 5:  # Minimum threshold
                continue

            repeat_score = data['count'] / len(data['dates'])
            track_name = key.split('|||')[0]

            results.append({
                'track': track_name,
                'artist': data['artist'],
                'play_count': data['count'],
                'repeat_score': round(repeat_score, 2)
            })

        results.sort(key=lambda x: x['repeat_score'], reverse=True)

        return results[:limit]

    def get_monthly_diversity(self) -> List[Dict[str, Any]]:
        """
        Get artist diversity over time (unique artists per month)

        Returns:
            List of {month, unique_artists, total_streams}
        """
        if not self._loaded:
            self.load_data()

        monthly_artists = defaultdict(set)
        monthly_streams = defaultdict(int)

        for record in self._data:
            ts = record.get('ts')
            artist = record.get('master_metadata_album_artist_name')

            if not ts or not artist:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            month_key = dt.strftime('%Y-%m')

            monthly_artists[month_key].add(artist)
            monthly_streams[month_key] += 1

        result = [
            {
                'month': month,
                'unique_artists': len(artists),
                'total_streams': monthly_streams[month],
                'diversity_ratio': round(len(artists) / monthly_streams[month] * 100, 2) if monthly_streams[month] > 0 else 0
            }
            for month, artists in sorted(monthly_artists.items())
        ]

        return result

    def get_listening_heatmap(self) -> List[Dict[str, Any]]:
        """
        Get day-hour heatmap data

        Returns:
            List of {day, hour, stream_count} for heatmap visualization
        """
        if not self._loaded:
            self.load_data()

        heatmap_data = defaultdict(int)

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            day = dt.weekday()  # 0=Monday, 6=Sunday
            hour = dt.hour

            key = (day, hour)
            heatmap_data[key] += 1

        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        result = [
            {
                'day': day_names[day],
                'hour': hour,
                'stream_count': heatmap_data.get((day, hour), 0)
            }
            for day in range(7)
            for hour in range(24)
        ]

        return result

    def _build_sessions(self) -> List[Dict[str, Any]]:
        """
        Build sessions from streaming data with 30-minute gap threshold

        Returns:
            List of sessions with features
        """
        if not self._loaded:
            self.load_data()

        # Sort records by timestamp
        sorted_records = sorted(
            [r for r in self._data if r.get('ts')],
            key=lambda x: datetime.fromisoformat(x['ts'].replace('Z', '+00:00'))
        )

        if not sorted_records:
            return []

        sessions = []
        current_session = {
            'records': [],
            'start_time': None,
            'end_time': None
        }

        for record in sorted_records:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))

            if current_session['start_time'] is None:
                # Start new session
                current_session['start_time'] = dt
                current_session['end_time'] = dt
                current_session['records'] = [record]
            else:
                # Check if this record belongs to current session (30-min gap)
                gap_minutes = (dt - current_session['end_time']).total_seconds() / 60

                if gap_minutes <= 30:
                    # Add to current session
                    current_session['end_time'] = dt
                    current_session['records'].append(record)
                else:
                    # Save current session and start new one
                    if len(current_session['records']) >= 3:  # Only save sessions with 3+ tracks
                        sessions.append(self._extract_session_features(current_session))

                    current_session = {
                        'start_time': dt,
                        'end_time': dt,
                        'records': [record]
                    }

        # Don't forget last session
        if current_session['start_time'] and len(current_session['records']) >= 3:
            sessions.append(self._extract_session_features(current_session))

        return sessions

    def _extract_session_features(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract features from a session for clustering

        Features:
        - duration_minutes: Total session duration
        - track_count: Number of tracks played
        - unique_artists_count: Number of unique artists
        - skip_ratio: Percentage of tracks skipped
        - avg_track_duration: Average track play duration
        - hour_of_day: Hour when session started (0-23)
        - is_weekend: Whether session was on weekend
        - diversity_score: Unique artists / total tracks
        """
        records = session['records']
        start_time = session['start_time']
        end_time = session['end_time']

        # Basic metrics
        duration_minutes = (end_time - start_time).total_seconds() / 60
        track_count = len(records)

        # Artist diversity
        artists = set()
        for r in records:
            artist = r.get('master_metadata_album_artist_name')
            if artist:
                artists.add(artist)
        unique_artists_count = len(artists)

        # Skip ratio
        skipped_count = sum(1 for r in records if r.get('skipped', False))
        skip_ratio = (skipped_count / track_count * 100) if track_count > 0 else 0

        # Average track duration (in minutes)
        track_durations = [r.get('ms_played', 0) / 60000 for r in records]
        avg_track_duration = statistics.mean(track_durations) if track_durations else 0

        # Time features
        hour_of_day = start_time.hour
        is_weekend = 1 if start_time.weekday() >= 5 else 0

        # Diversity score
        diversity_score = (unique_artists_count / track_count) if track_count > 0 else 0

        # Platform
        platforms = [r.get('platform', 'unknown') for r in records]
        most_common_platform = max(set(platforms), key=platforms.count) if platforms else 'unknown'

        return {
            'session_id': f"{start_time.isoformat()}",
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_minutes': round(duration_minutes, 2),
            'track_count': track_count,
            'unique_artists_count': unique_artists_count,
            'skip_ratio': round(skip_ratio, 2),
            'avg_track_duration': round(avg_track_duration, 2),
            'hour_of_day': hour_of_day,
            'is_weekend': is_weekend,
            'diversity_score': round(diversity_score, 3),
            'platform': most_common_platform,
            'records': records  # Keep for later analysis if needed
        }

    def _cluster_sessions(self) -> Dict[str, Any]:
        """
        Cluster sessions using k-means with optimal k selection via silhouette score

        Returns:
            Dictionary with sessions, cluster labels, centroids, and metadata
        """
        sessions = self._build_sessions()

        if len(sessions) < 10:  # Need minimum sessions for clustering
            return {
                'sessions': sessions,
                'labels': [0] * len(sessions),
                'n_clusters': 1,
                'centroids': [],
                'feature_names': [],
                'error': 'Not enough sessions for clustering'
            }

        # Extract features for clustering
        feature_names = [
            'duration_minutes',
            'track_count',
            'unique_artists_count',
            'skip_ratio',
            'avg_track_duration',
            'hour_of_day',
            'is_weekend',
            'diversity_score'
        ]

        X = np.array([[s[f] for f in feature_names] for s in sessions])

        # Normalize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Find optimal k using silhouette score (test k=2 to k=min(8, n_sessions/10))
        max_k = min(8, len(sessions) // 10)
        if max_k < 2:
            max_k = 2

        best_k = 3  # Default
        best_score = -1

        for k in range(2, max_k + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            score = silhouette_score(X_scaled, labels)

            if score > best_score:
                best_score = score
                best_k = k

        # Perform final clustering with best k
        kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        # Transform centroids back to original scale
        centroids_scaled = kmeans.cluster_centers_
        centroids = scaler.inverse_transform(centroids_scaled)

        # Add cluster labels to sessions
        for i, session in enumerate(sessions):
            session['cluster_label'] = int(labels[i])

        return {
            'sessions': sessions,
            'labels': labels.tolist(),
            'n_clusters': best_k,
            'centroids': centroids.tolist(),
            'feature_names': feature_names,
            'silhouette_score': round(best_score, 3)
        }

    def get_session_clusters(self) -> Dict[str, Any]:
        """
        Get cluster statistics and profiles

        Returns:
            Cluster profiles with statistics
        """
        clustering_result = self._cluster_sessions()

        if 'error' in clustering_result:
            return clustering_result

        sessions = clustering_result['sessions']
        n_clusters = clustering_result['n_clusters']

        # Calculate cluster statistics
        clusters = []
        for cluster_id in range(n_clusters):
            cluster_sessions = [s for s in sessions if s['cluster_label'] == cluster_id]

            if not cluster_sessions:
                continue

            # Aggregate statistics
            clusters.append({
                'cluster_id': cluster_id,
                'session_count': len(cluster_sessions),
                'avg_duration': round(statistics.mean([s['duration_minutes'] for s in cluster_sessions]), 1),
                'avg_tracks': round(statistics.mean([s['track_count'] for s in cluster_sessions]), 1),
                'avg_skip_ratio': round(statistics.mean([s['skip_ratio'] for s in cluster_sessions]), 1),
                'avg_diversity': round(statistics.mean([s['diversity_score'] for s in cluster_sessions]), 2),
                'common_hour': round(statistics.mean([s['hour_of_day'] for s in cluster_sessions])),
                'weekend_ratio': round(sum([s['is_weekend'] for s in cluster_sessions]) / len(cluster_sessions) * 100, 1)
            })

        return {
            'n_clusters': n_clusters,
            'total_sessions': len(sessions),
            'silhouette_score': clustering_result['silhouette_score'],
            'clusters': clusters
        }

    def get_session_centroids(self) -> List[Dict[str, Any]]:
        """
        Get cluster centroids with feature values

        Returns:
            List of centroids with feature names and values
        """
        clustering_result = self._cluster_sessions()

        if 'error' in clustering_result:
            return []

        centroids = clustering_result['centroids']
        feature_names = clustering_result['feature_names']

        result = []
        for i, centroid in enumerate(centroids):
            centroid_dict = {
                'cluster_id': i,
                'features': {}
            }
            for j, feature_name in enumerate(feature_names):
                centroid_dict['features'][feature_name] = round(centroid[j], 2)
            result.append(centroid_dict)

        return result

    def get_session_assignments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent sessions with their cluster assignments

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of recent sessions with cluster labels
        """
        clustering_result = self._cluster_sessions()

        if 'error' in clustering_result:
            return []

        sessions = clustering_result['sessions']

        # Sort by start time (most recent first) and limit
        sessions_sorted = sorted(sessions, key=lambda x: x['start_time'], reverse=True)[:limit]

        # Remove 'records' field for cleaner response
        result = []
        for session in sessions_sorted:
            session_copy = session.copy()
            if 'records' in session_copy:
                del session_copy['records']
            result.append(session_copy)

        return result

    def get_milestones_list(self) -> List[Dict[str, Any]]:
        """
        Get all milestones - streaks, top days, firsts, and notable achievements

        Returns:
            List of {date, year, type, title, description, value, badge_color}
        """
        if not self._loaded:
            self.load_data()

        milestones = []

        # Track daily streams and dates
        daily_streams = defaultdict(int)
        daily_hours = defaultdict(float)
        daily_tracks = defaultdict(set)
        daily_artists = defaultdict(set)
        artist_first_seen = {}
        track_first_seen = {}

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            date_key = dt.date()

            daily_streams[date_key] += 1
            daily_hours[date_key] += record.get('ms_played', 0) / 3_600_000

            track = record.get('master_metadata_track_name')
            artist = record.get('master_metadata_album_artist_name')

            if track and artist:
                daily_tracks[date_key].add(f"{track}|||{artist}")
                daily_artists[date_key].add(artist)

                # Track firsts
                if artist not in artist_first_seen:
                    artist_first_seen[artist] = dt

                if track not in track_first_seen:
                    track_first_seen[track] = (dt, artist)

        if not daily_streams:
            return []

        # 1. Find listening streaks (3+ consecutive days)
        sorted_dates = sorted(daily_streams.keys())
        current_streak_start = sorted_dates[0]
        current_streak_end = sorted_dates[0]
        streaks = []

        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                current_streak_end = sorted_dates[i]
            else:
                # End streak
                streak_length = (current_streak_end - current_streak_start).days + 1
                if streak_length >= 3:  # Only save streaks of 3+ days
                    streaks.append({
                        'start': current_streak_start,
                        'end': current_streak_end,
                        'length': streak_length
                    })
                current_streak_start = sorted_dates[i]
                current_streak_end = sorted_dates[i]

        # Don't forget last streak
        streak_length = (current_streak_end - current_streak_start).days + 1
        if streak_length >= 3:
            streaks.append({
                'start': current_streak_start,
                'end': current_streak_end,
                'length': streak_length
            })

        # Add streak milestones
        for streak in sorted(streaks, key=lambda x: x['length'], reverse=True)[:10]:
            milestones.append({
                'date': streak['start'].isoformat(),
                'year': streak['start'].year,
                'type': 'streak',
                'title': f"{streak['length']}-Day Listening Streak",
                'description': f"From {streak['start'].strftime('%b %d')} to {streak['end'].strftime('%b %d, %Y')}",
                'value': streak['length'],
                'badge_color': '#2dd881'
            })

        # 2. Top listening days
        top_days = sorted(daily_streams.items(), key=lambda x: x[1], reverse=True)[:15]
        for date, count in top_days:
            if count >= 50:  # Only notable days
                milestones.append({
                    'date': date.isoformat(),
                    'year': date.year,
                    'type': 'top_day',
                    'title': f"{count} Streams in One Day",
                    'description': f"Peak listening day on {date.strftime('%b %d, %Y')} with {round(daily_hours[date], 1)} hours",
                    'value': count,
                    'badge_color': '#4ea699'
                })

        # 3. First discoveries (notable artists)
        top_artists = self.get_top_artists(limit=20)
        top_artist_names = {a['artist'] for a in top_artists}

        for artist, first_date in sorted(artist_first_seen.items(), key=lambda x: x[1])[:20]:
            if artist in top_artist_names:
                milestones.append({
                    'date': first_date.date().isoformat(),
                    'year': first_date.year,
                    'type': 'first_artist',
                    'title': f"Discovered {artist}",
                    'description': f"First listened to {artist} on {first_date.strftime('%b %d, %Y')}",
                    'value': 0,
                    'badge_color': '#6fedb7'
                })

        # 4. Diversity milestones (days with many unique artists)
        diverse_days = sorted(daily_artists.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        for date, artists in diverse_days:
            if len(artists) >= 20:  # Only notable diversity
                milestones.append({
                    'date': date.isoformat(),
                    'year': date.year,
                    'type': 'diversity',
                    'title': f"{len(artists)} Different Artists",
                    'description': f"Explored {len(artists)} artists on {date.strftime('%b %d, %Y')}",
                    'value': len(artists),
                    'badge_color': '#140d4f'
                })

        # Sort all milestones by date (most recent first)
        milestones.sort(key=lambda x: x['date'], reverse=True)

        return milestones

    def get_flashback(self, date_str: str) -> Dict[str, Any]:
        """
        Get detailed flashback for a specific date

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Detailed listening data for that date
        """
        if not self._loaded:
            self.load_data()

        try:
            target_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            return {
                'error': 'Invalid date format. Use YYYY-MM-DD',
                'date': date_str
            }

        # Collect all streams for this date
        day_streams = []
        artists_played = defaultdict(int)
        tracks_played = defaultdict(lambda: {'count': 0, 'artist': None})
        total_hours = 0
        skipped_count = 0

        for record in self._data:
            ts = record.get('ts')
            if not ts:
                continue

            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if dt.date() != target_date:
                continue

            day_streams.append(record)
            total_hours += record.get('ms_played', 0) / 3_600_000

            if record.get('skipped'):
                skipped_count += 1

            artist = record.get('master_metadata_album_artist_name')
            track = record.get('master_metadata_track_name')

            if artist:
                artists_played[artist] += 1

            if track and artist:
                tracks_played[track]['count'] += 1
                tracks_played[track]['artist'] = artist

        if not day_streams:
            return {
                'date': date_str,
                'streams': 0,
                'message': 'No listening data found for this date'
            }

        # Get top artists and tracks for that day
        top_artists_day = sorted(artists_played.items(), key=lambda x: x[1], reverse=True)[:5]
        top_tracks_day = sorted(
            [(track, data) for track, data in tracks_played.items()],
            key=lambda x: x[1]['count'],
            reverse=True
        )[:5]

        # Get first and last stream times
        timestamps = [
            datetime.fromisoformat(r.get('ts').replace('Z', '+00:00'))
            for r in day_streams if r.get('ts')
        ]
        first_stream = min(timestamps) if timestamps else None
        last_stream = max(timestamps) if timestamps else None

        return {
            'date': date_str,
            'day_of_week': target_date.strftime('%A'),
            'streams': len(day_streams),
            'hours': round(total_hours, 2),
            'unique_artists': len(artists_played),
            'unique_tracks': len(tracks_played),
            'skipped': skipped_count,
            'skip_rate': round((skipped_count / len(day_streams)) * 100, 1) if day_streams else 0,
            'first_stream': first_stream.strftime('%I:%M %p') if first_stream else None,
            'last_stream': last_stream.strftime('%I:%M %p') if last_stream else None,
            'listening_duration': f"{(last_stream - first_stream).total_seconds() / 3600:.1f} hours" if first_stream and last_stream else None,
            'top_artists': [
                {'artist': artist, 'streams': count}
                for artist, count in top_artists_day
            ],
            'top_tracks': [
                {'track': track, 'artist': data['artist'], 'plays': data['count']}
                for track, data in top_tracks_day
            ]
        }


# Global instance
spotify_data = SpotifyDataLoader()
