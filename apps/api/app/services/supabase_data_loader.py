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
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError(
        "supabase-py is required. Install with: pip install supabase"
    )

# Load environment variables from spotify-insights.env.
# Search upward from this file so it works regardless of the process CWD
# (start.sh launches uvicorn from apps/api, scripts run from the repo root).
_env_loaded = False
for _parent in Path(__file__).resolve().parents:
    _candidate = _parent / 'spotify-insights.env'
    if _candidate.exists():
        load_dotenv(_candidate)
        _env_loaded = True
        break
if not _env_loaded:
    load_dotenv('spotify-insights.env')  # last-resort relative fallback

# Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')


class SupabaseDataLoader:
    """Service to load and process Spotify streaming data from Supabase"""

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in spotify-insights.env"
            )

        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self._loaded = True  # Database is always "loaded"

    @staticmethod
    def _uid(params: dict, user_id: Optional[str]) -> dict:
        """Attach p_user_id to an RPC param dict when a user is specified.

        When user_id is None the SQL functions (migration 004) fall back to the
        primary user, so existing single-user callers need no changes.
        """
        if user_id:
            params = {**params, 'p_user_id': user_id}
        return params

    def get_overview_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get overview statistics using optimized SQL function"""
        try:
            response = self.supabase.rpc('get_overview_stats', self._uid({}, user_id)).execute()
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

    def get_top_artists(self, limit: int = 10, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get top artists from materialized view"""
        try:
            response = self.supabase.rpc('get_top_artists', self._uid({'limit_count': limit}, user_id)).execute()
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

    def get_top_tracks(self, limit: int = 10, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get top tracks from materialized view"""
        try:
            response = self.supabase.rpc('get_top_tracks', self._uid({'limit_count': limit}, user_id)).execute()
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

    def get_monthly_data(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get monthly streaming statistics from materialized view"""
        try:
            response = self.supabase.rpc('get_monthly_data', self._uid({}, user_id)).execute()
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

    def get_platform_stats(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get platform usage statistics"""
        try:
            response = self.supabase.rpc('get_platform_stats', self._uid({}, user_id)).execute()
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

    def get_hourly_distribution(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get listening distribution by hour of day"""
        try:
            response = self.supabase.rpc('get_hourly_distribution', self._uid({}, user_id)).execute()
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

    def get_daily_distribution(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get listening distribution by day of week"""
        try:
            response = self.supabase.rpc('get_daily_distribution', self._uid({}, user_id)).execute()
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

    def get_skip_behavior(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get skip behavior by artist"""
        try:
            response = self.supabase.rpc('get_skip_behavior', self._uid({'limit_count': limit}, user_id)).execute()
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

    def get_yearly_comparison(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get year-over-year comparison"""
        try:
            response = self.supabase.rpc('get_yearly_comparison', self._uid({}, user_id)).execute()
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

    def get_listening_streaks(self, limit: int = 10, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get listening streaks"""
        try:
            response = self.supabase.rpc('get_listening_streaks', self._uid({'limit_count': limit}, user_id)).execute()
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

    # ------------------------------------------------------------------
    # Friend-group comparison (multi-user)
    #
    # Leaderboard is one grouped aggregate (RPC). Everything else is computed
    # here in Python from the per-user `top_artists` materialized view, because
    # cross-user Jaccard / an N x N matrix would exceed the PostgREST statement
    # timeout as SQL.
    # ------------------------------------------------------------------

    def list_users(self) -> List[Dict[str, Any]]:
        """All users (primary first, then alphabetical)."""
        try:
            resp = (
                self.supabase.table('users')
                .select('id, username, display_name, is_primary')
                .order('is_primary', desc=True)
                .order('username')
                .execute()
            )
            return [
                {
                    'user_id': r['id'],
                    'username': r['username'],
                    'display_name': r['display_name'] or r['username'].title(),
                    'is_primary': r['is_primary'],
                }
                for r in (resp.data or [])
            ]
        except Exception as e:
            print(f"Error listing users: {e}")
            return []

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Per-user listening totals (RPC get_user_leaderboard)."""
        try:
            resp = self.supabase.rpc('get_user_leaderboard').execute()
            out = []
            for r in (resp.data or []):
                out.append({
                    'user_id': r['user_id'],
                    'username': r['username'],
                    'display_name': r['display_name'] or r['username'].title(),
                    'is_primary': r['is_primary'],
                    'total_streams': r['total_streams'],
                    'total_hours': float(r['total_hours']) if r['total_hours'] is not None else 0.0,
                    'unique_artists': r['unique_artists'],
                    'unique_tracks': r['unique_tracks'],
                    'skip_rate': float(r['skip_rate']) if r['skip_rate'] is not None else 0.0,
                    'first_stream': r['first_stream'],
                    'last_stream': r['last_stream'],
                })
            return out
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            return []

    def _artist_vector(self, user_id: str) -> Dict[str, int]:
        """{artist: stream_count} for a user, from the top_artists view. Cached."""
        if not hasattr(self, '_artist_vecs'):
            self._artist_vecs: Dict[str, Dict[str, int]] = {}
        if user_id in self._artist_vecs:
            return self._artist_vecs[user_id]

        vec: Dict[str, int] = {}
        page = 0
        page_size = 1000
        while True:
            start = page * page_size
            resp = (
                self.supabase.table('top_artists')
                .select('artist, stream_count')
                .eq('user_id', user_id)
                .range(start, start + page_size - 1)
                .execute()
            )
            rows = resp.data or []
            for r in rows:
                if r['artist']:
                    vec[r['artist']] = r['stream_count']
            if len(rows) < page_size:
                break
            page += 1

        self._artist_vecs[user_id] = vec
        return vec

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        union = len(a | b)
        return round(len(a & b) / union * 100, 1) if union else 0.0

    def get_overlap(self, user_ids: List[str], top_n: int = 25) -> Dict[str, Any]:
        """Artist overlap between 2+ users."""
        users = {u['user_id']: u for u in self.list_users()}
        picked = [uid for uid in user_ids if uid in users]
        if len(picked) < 2:
            return {'error': 'need at least 2 valid users'}

        vecs = {uid: self._artist_vector(uid) for uid in picked}
        sets = {uid: set(v.keys()) for uid, v in vecs.items()}

        pairs = []
        for i in range(len(picked)):
            for j in range(i + 1, len(picked)):
                a, b = picked[i], picked[j]
                pairs.append({
                    'user_a': users[a]['display_name'],
                    'user_b': users[b]['display_name'],
                    'shared': len(sets[a] & sets[b]),
                    'only_a': len(sets[a] - sets[b]),
                    'only_b': len(sets[b] - sets[a]),
                    'jaccard': self._jaccard(sets[a], sets[b]),
                })

        shared_all = set.intersection(*sets.values()) if sets else set()
        top_shared = sorted(
            (
                {'artist': art, 'total_plays': sum(vecs[uid].get(art, 0) for uid in picked)}
                for art in shared_all
            ),
            key=lambda x: x['total_plays'],
            reverse=True,
        )[:top_n]

        return {
            'users': [users[uid]['display_name'] for uid in picked],
            'pairs': pairs,
            'shared_by_all_count': len(shared_all),
            'top_shared_by_all': top_shared,
        }

    def get_similarity_matrix(self) -> Dict[str, Any]:
        """N x N pairwise artist-Jaccard % across all users (diagonal null)."""
        users = self.list_users()
        vecs = {u['user_id']: set(self._artist_vector(u['user_id']).keys()) for u in users}
        labels = [u['display_name'] for u in users]
        matrix: List[List[Optional[float]]] = []
        for ui in users:
            row: List[Optional[float]] = []
            for uj in users:
                if ui['user_id'] == uj['user_id']:
                    row.append(None)
                else:
                    row.append(self._jaccard(vecs[ui['user_id']], vecs[uj['user_id']]))
            matrix.append(row)
        return {'users': labels, 'matrix': matrix}

    def get_top_artists_multi(self, user_ids: List[str], limit: int = 10) -> Dict[str, Any]:
        """Each user's top `limit` artists, keyed by display name."""
        users = {u['user_id']: u for u in self.list_users()}
        out: Dict[str, List[Dict[str, Any]]] = {}
        for uid in user_ids:
            if uid not in users:
                continue
            vec = self._artist_vector(uid)
            top = sorted(vec.items(), key=lambda kv: kv[1], reverse=True)[:limit]
            out[users[uid]['display_name']] = [
                {'artist': art, 'streams': cnt} for art, cnt in top
            ]
        return out

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
