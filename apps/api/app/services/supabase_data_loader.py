"""
Supabase-based data loader for Spotify streaming data

This is a drop-in replacement for the JSON-based SpotifyDataLoader that uses
PostgreSQL queries instead of loading JSON files into memory.

Performance benefits:
- No need to load 55MB+ of JSON into memory
- Leverages database indexes for fast queries
- Materialized views for pre-aggregated statistics
- Concurrent queries possible
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError(
        "supabase-py is required. Install with: pip install supabase"
    )

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')


class SupabaseDataLoader:
    """Service to load and process Spotify streaming data from Supabase"""

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
            )

        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self._loaded = True  # Database is always "loaded"

    def get_overview_stats(self) -> Dict[str, Any]:
        """Get overview statistics using optimized SQL function"""
        try:
            response = self.supabase.rpc('get_overview_stats').execute()
            if response.data and len(response.data) > 0:
                data = response.data[0]
                return {
                    'total_streams': data['total_streams'],
                    'total_hours': float(data['total_hours']),
                    'unique_tracks': data['unique_tracks'],
                    'unique_artists': data['unique_artists'],
                    'unique_albums': data['unique_albums'],
                }
            return {}
        except Exception as e:
            print(f"Error getting overview stats: {e}")
            return {}

    def get_top_artists(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top artists from materialized view"""
        try:
            response = self.supabase.rpc('get_top_artists', {'limit_count': limit}).execute()
            if response.data:
                return [
                    {
                        'artist': row['artist'],
                        'streams': row['streams']
                    }
                    for row in response.data
                ]
            return []
        except Exception as e:
            print(f"Error getting top artists: {e}")
            return []

    def get_top_tracks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top tracks from materialized view"""
        try:
            response = self.supabase.rpc('get_top_tracks', {'limit_count': limit}).execute()
            if response.data:
                return [
                    {
                        'track': row['track'],
                        'artist': row['artist'],
                        'streams': row['streams']
                    }
                    for row in response.data
                ]
            return []
        except Exception as e:
            print(f"Error getting top tracks: {e}")
            return []

    def get_monthly_data(self) -> List[Dict[str, Any]]:
        """Get monthly streaming statistics from materialized view"""
        try:
            response = self.supabase.rpc('get_monthly_data').execute()
            if response.data:
                return [
                    {
                        'month': row['month'][:7],  # Format as YYYY-MM
                        'streams': row['streams'],
                        'hours': float(row['hours'])
                    }
                    for row in response.data
                ]
            return []
        except Exception as e:
            print(f"Error getting monthly data: {e}")
            return []

    def get_platform_stats(self) -> List[Dict[str, Any]]:
        """Get platform usage statistics"""
        try:
            response = self.supabase.rpc('get_platform_stats').execute()
            if response.data:
                # Return top 10 platforms, group rest as "Other"
                platforms = response.data[:10]
                result = [
                    {
                        'platform': row['platform'],
                        'streams': row['streams']
                    }
                    for row in platforms
                ]

                # Calculate "Other" if there are more platforms
                if len(response.data) > 10:
                    other_streams = sum(row['streams'] for row in response.data[10:])
                    result.append({'platform': 'Other', 'streams': other_streams})

                return result
            return []
        except Exception as e:
            print(f"Error getting platform stats: {e}")
            return []

    def get_hourly_distribution(self) -> List[Dict[str, Any]]:
        """Get listening distribution by hour of day"""
        try:
            response = self.supabase.rpc('get_hourly_distribution').execute()
            if response.data:
                return [
                    {
                        'hour': row['hour'],
                        'streams': row['streams']
                    }
                    for row in response.data
                ]
            return []
        except Exception as e:
            print(f"Error getting hourly distribution: {e}")
            return []

    def get_daily_distribution(self) -> List[Dict[str, Any]]:
        """Get listening distribution by day of week"""
        try:
            response = self.supabase.rpc('get_daily_distribution').execute()
            if response.data:
                # Map day numbers to names
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                return [
                    {
                        'day': day_names[row['day_of_week'] - 1],
                        'streams': row['streams']
                    }
                    for row in response.data
                ]
            return []
        except Exception as e:
            print(f"Error getting daily distribution: {e}")
            return []

    def get_skip_behavior(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get skip behavior by artist"""
        try:
            response = self.supabase.rpc('get_skip_behavior', {'limit_count': limit}).execute()
            if response.data:
                return [
                    {
                        'artist': row['artist'],
                        'total_streams': row['total_streams'],
                        'skipped_count': row['skipped_count'],
                        'skip_rate': float(row['skip_rate'])
                    }
                    for row in response.data
                ]
            return []
        except Exception as e:
            print(f"Error getting skip behavior: {e}")
            return []

    def get_yearly_comparison(self) -> List[Dict[str, Any]]:
        """Get year-over-year comparison"""
        try:
            response = self.supabase.rpc('get_yearly_comparison').execute()
            if response.data:
                return [
                    {
                        'year': row['year'],
                        'streams': row['streams'],
                        'hours': float(row['hours'])
                    }
                    for row in response.data
                ]
            return []
        except Exception as e:
            print(f"Error getting yearly comparison: {e}")
            return []

    def get_listening_streaks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get listening streaks"""
        try:
            response = self.supabase.rpc('get_listening_streaks', {'limit_count': limit}).execute()
            if response.data:
                return [
                    {
                        'start_date': row['start_date'],
                        'end_date': row['end_date'],
                        'length_days': row['length_days'],
                        'total_streams': row['total_streams']
                    }
                    for row in response.data
                ]
            return []
        except Exception as e:
            print(f"Error getting listening streaks: {e}")
            return []

    # Placeholder methods for features not yet implemented in SQL
    # These can be implemented later with SQL functions

    def get_mood_summary(self, window_days: int = 30) -> Dict[str, Any]:
        """Get mood statistics - placeholder for future implementation"""
        # TODO: Implement with SQL function
        return {
            'window_days': window_days,
            'avg_valence': None,
            'avg_energy': None,
            'avg_danceability': None,
            'sample_size': 0,
        }

    def get_mood_contexts(self) -> Dict[str, Any]:
        """Get mood contexts - placeholder for future implementation"""
        # TODO: Implement with SQL function
        return {
            'weekday_vs_weekend': {
                'weekday': {'avg_valence': None, 'avg_energy': None, 'avg_danceability': None, 'sample_size': 0},
                'weekend': {'avg_valence': None, 'avg_energy': None, 'avg_danceability': None, 'sample_size': 0}
            },
            'by_platform': {}
        }

    def get_mood_monthly(self) -> List[Dict[str, Any]]:
        """Get monthly mood averages - placeholder for future implementation"""
        # TODO: Implement with SQL function
        return []

    def get_discovery_timeline(self) -> List[Dict[str, Any]]:
        """Get artist discovery timeline"""
        # TODO: Implement with SQL function
        return []

    def get_artist_loyalty(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Calculate artist loyalty metrics"""
        # TODO: Implement with SQL function
        return []

    def get_artist_obsessions(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Identify obsession periods"""
        # TODO: Implement with SQL function
        return []

    def get_reflective_insights(self) -> Dict[str, Any]:
        """Generate reflective insights"""
        # TODO: Implement with SQL function
        return {
            'total_streams': 0,
            'longest_streak_days': 0,
            'most_active_hour': 0,
            'most_active_day': 'Unknown',
            'top_artist': 'Unknown',
            'avg_streams_per_day': 0,
            'insights': []
        }

    def get_session_durations(self) -> List[Dict[str, Any]]:
        """Get session duration distribution"""
        # TODO: Implement with SQL function
        return []

    def get_binge_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top binge sessions"""
        # TODO: Implement with SQL function
        return []

    def get_session_statistics(self) -> Dict[str, Any]:
        """Get aggregate session statistics"""
        # TODO: Implement with SQL function
        return {
            'total_sessions': 0,
            'avg_duration_minutes': 0,
            'median_duration_minutes': 0,
            'avg_tracks_per_session': 0,
            'longest_session_minutes': 0,
        }

    def get_weekend_weekday_comparison(self) -> Dict[str, Any]:
        """Weekend vs weekday comparison"""
        # TODO: Implement with SQL function
        return {
            'weekday': {'streams': 0, 'hours': 0, 'avg_per_day': 0},
            'weekend': {'streams': 0, 'hours': 0, 'avg_per_day': 0}
        }

    def get_most_repeated_tracks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most repeated tracks"""
        # TODO: Implement with SQL function
        return []

    def get_monthly_diversity(self) -> List[Dict[str, Any]]:
        """Get artist diversity over time"""
        # TODO: Implement with SQL function
        return []

    def get_listening_heatmap(self) -> List[Dict[str, Any]]:
        """Get day-hour heatmap data"""
        # TODO: Implement with SQL function
        return []

    def get_session_clusters(self) -> Dict[str, Any]:
        """Get session cluster statistics"""
        # TODO: Implement with SQL function
        return {'error': 'Not implemented yet'}

    def get_session_centroids(self) -> List[Dict[str, Any]]:
        """Get cluster centroids"""
        # TODO: Implement with SQL function
        return []

    def get_session_assignments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get session assignments"""
        # TODO: Implement with SQL function
        return []

    def get_milestones_list(self) -> List[Dict[str, Any]]:
        """Get all milestones"""
        # TODO: Implement with SQL function
        return []

    def get_flashback(self, date_str: str) -> Dict[str, Any]:
        """Get flashback for specific date"""
        # TODO: Implement with SQL function
        return {'error': 'Not implemented yet', 'date': date_str}


# Global instance
supabase_data = SupabaseDataLoader()
