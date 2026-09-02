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

from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config import settings
from app.db.backends import DBBackend, build_backend
from app.services.data_loader import SpotifyDataLoader

# Env loading and credential resolution now live in app.config, which reads
# spotify-insights.env with the same upward-walk search but lets real
# environment variables win (so Docker Compose can inject configuration).


class SupabaseDataLoader:
    """Loads and processes Spotify streaming data from the configured database.

    Despite the name (kept so the ~35 call sites in app/routes/ are unchanged),
    this works against either backend: PostgREST/Supabase or a local Postgres,
    selected by DB_BACKEND. Both call the same SQL functions from
    apps/api/migrations/, so results are identical. Renamed to data_service.py
    in Phase 14 when the two loaders collapse.
    """

    def __init__(self, backend: Optional[DBBackend] = None):
        # Credentials are validated inside the backend, so the Supabase check
        # only fires when the Supabase path is actually selected.
        self.db: DBBackend = backend if backend is not None else build_backend(settings)
        self._loaded = True  # Database is always "loaded"

        # Resolved primary user id (cached; used when a caller passes user_id=None
        # for the row-fetch path, mirroring SQL's _effective_user_id fallback).
        self._primary_user_id: Optional[str] = None
        # Per-user SpotifyDataLoader instances, each pre-populated with that
        # user's streaming_history rows. Heavy compute (session KMeans, the
        # content-based recommender, the Markov simulator) is delegated to these
        # so the numpy/sklearn logic is shared verbatim with the JSON loader and
        # the return shapes are guaranteed identical.
        self._delegate_by_user: Dict[str, SpotifyDataLoader] = {}

    # ------------------------------------------------------------------
    # Per-user raw-row fetch + heavy-compute delegation
    # ------------------------------------------------------------------

    _ROW_COLUMNS = (
        "ts,ms_played,master_metadata_track_name,"
        "master_metadata_album_artist_name,master_metadata_album_album_name,"
        "platform,skipped,spotify_track_uri"
    )

    def _resolve_user_id(self, user_id: Optional[str]) -> Optional[str]:
        """Return user_id, or the primary user's id when user_id is None."""
        if user_id:
            return user_id
        if self._primary_user_id is None:
            try:
                resp = self.db.select(
                    "users", "id", eq={"is_primary": True}, limit=1
                )
                if resp:
                    self._primary_user_id = resp[0]["id"]
            except Exception as e:
                print(f"Error resolving primary user id: {e}")
        return self._primary_user_id

    def _user_rows(self, user_id: Optional[str]) -> List[Dict[str, Any]]:
        """Paginated fetch of one user's streaming_history rows.

        Returns records shaped exactly like the JSON export rows that
        SpotifyDataLoader consumes (same key names; `ts` is an ISO-8601 string).
        """
        uid = self._resolve_user_id(user_id)
        if not uid:
            return []

        rows: List[Dict[str, Any]] = []
        page = 0
        page_size = 1000
        while True:
            start = page * page_size
            resp = self.db.select(
                "streaming_history",
                self._ROW_COLUMNS,
                eq={"user_id": uid},
                range_=(start, start + page_size - 1),
            )
            batch = resp or []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return rows

    def _delegate(self, user_id: Optional[str]) -> SpotifyDataLoader:
        """A SpotifyDataLoader pre-loaded with this user's rows (cached)."""
        uid = self._resolve_user_id(user_id) or "__none__"
        cached = self._delegate_by_user.get(uid)
        if cached is not None:
            return cached

        loader = SpotifyDataLoader()
        loader._data = self._user_rows(user_id)
        loader._loaded = True  # skip load_data()'s JSON glob
        self._delegate_by_user[uid] = loader
        return loader

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
            response = self.db.rpc('get_overview_stats', self._uid({}, user_id))
            if response and len(response) > 0:
                data = response[0]
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
            response = self.db.rpc('get_top_artists', self._uid({'limit_count': limit}, user_id))
            if response:
                return [
                    {
                        'artist': row['artist'],
                        'streams': row['streams']
                    }
                    for row in response
                ]
            return []
        except Exception as e:
            print(f"Error getting top artists: {e}")
            return []

    def get_top_tracks(self, limit: int = 10, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get top tracks from materialized view"""
        try:
            response = self.db.rpc('get_top_tracks', self._uid({'limit_count': limit}, user_id))
            if response:
                return [
                    {
                        'track': row['track'],
                        'artist': row['artist'],
                        'streams': row['streams']
                    }
                    for row in response
                ]
            return []
        except Exception as e:
            print(f"Error getting top tracks: {e}")
            return []

    def get_monthly_data(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get monthly streaming statistics from materialized view"""
        try:
            response = self.db.rpc('get_monthly_data', self._uid({}, user_id))
            if response:
                return [
                    {
                        'month': row['month'][:7],  # Format as YYYY-MM
                        'streams': row['streams'],
                        'hours': float(row['hours'])
                    }
                    for row in response
                ]
            return []
        except Exception as e:
            print(f"Error getting monthly data: {e}")
            return []

    def get_platform_stats(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get platform usage statistics"""
        try:
            response = self.db.rpc('get_platform_stats', self._uid({}, user_id))
            if response:
                # Return top 10 platforms, group rest as "Other"
                platforms = response[:10]
                result = [
                    {
                        'platform': row['platform'],
                        'streams': row['streams']
                    }
                    for row in platforms
                ]

                # Calculate "Other" if there are more platforms
                if len(response) > 10:
                    other_streams = sum(row['streams'] for row in response[10:])
                    result.append({'platform': 'Other', 'streams': other_streams})

                return result
            return []
        except Exception as e:
            print(f"Error getting platform stats: {e}")
            return []

    def get_hourly_distribution(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get listening distribution by hour of day"""
        try:
            response = self.db.rpc('get_hourly_distribution', self._uid({}, user_id))
            if response:
                return [
                    {
                        'hour': row['hour'],
                        'streams': row['streams']
                    }
                    for row in response
                ]
            return []
        except Exception as e:
            print(f"Error getting hourly distribution: {e}")
            return []

    def get_daily_distribution(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get listening distribution by day of week"""
        try:
            response = self.db.rpc('get_daily_distribution', self._uid({}, user_id))
            if response:
                # Map day numbers to names
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                return [
                    {
                        'day': day_names[row['day_of_week'] - 1],
                        'streams': row['streams']
                    }
                    for row in response
                ]
            return []
        except Exception as e:
            print(f"Error getting daily distribution: {e}")
            return []

    def get_skip_behavior(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get skip behavior by artist"""
        try:
            response = self.db.rpc('get_skip_behavior', self._uid({'limit_count': limit}, user_id))
            if response:
                return [
                    {
                        'artist': row['artist'],
                        'total_streams': row['total_streams'],
                        'skipped_count': row['skipped_count'],
                        'skip_rate': float(row['skip_rate'])
                    }
                    for row in response
                ]
            return []
        except Exception as e:
            print(f"Error getting skip behavior: {e}")
            return []

    def get_yearly_comparison(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get year-over-year comparison"""
        try:
            response = self.db.rpc('get_yearly_comparison', self._uid({}, user_id))
            if response:
                return [
                    {
                        'year': row['year'],
                        'streams': row['streams'],
                        'hours': float(row['hours'])
                    }
                    for row in response
                ]
            return []
        except Exception as e:
            print(f"Error getting yearly comparison: {e}")
            return []

    def get_listening_streaks(self, limit: int = 10, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get listening streaks"""
        try:
            response = self.db.rpc('get_listening_streaks', self._uid({'limit_count': limit}, user_id))
            if response:
                return [
                    {
                        'start_date': row['start_date'],
                        'end_date': row['end_date'],
                        'length_days': row['length_days'],
                        'total_streams': row['total_streams']
                    }
                    for row in response
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
                self.db.select(
                    'users',
                    'id, username, display_name, is_primary',
                    order=[('is_primary', True), ('username', False)],
                )
            )
            return [
                {
                    'user_id': r['id'],
                    'username': r['username'],
                    'display_name': r['display_name'] or r['username'].title(),
                    'is_primary': r['is_primary'],
                }
                for r in (resp or [])
            ]
        except Exception as e:
            print(f"Error listing users: {e}")
            return []

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Per-user listening totals (RPC get_user_leaderboard)."""
        try:
            resp = self.db.rpc('get_user_leaderboard')
            out = []
            for r in (resp or []):
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
                self.db.select(
                    'top_artists',
                    'artist, stream_count',
                    eq={'user_id': user_id},
                    range_=(start, start + page_size - 1),
                )
            )
            rows = resp or []
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

    # ------------------------------------------------------------------
    # Analytics — mood / discovery / milestones / listening patterns
    #
    # Ported from the JSON SpotifyDataLoader. SQL-friendly aggregates run as
    # user-scoped RPCs from migration 006 (single indexed pass, sub-second).
    # Return shapes are identical to the JSON loader's.
    # ------------------------------------------------------------------

    def get_mood_summary(self, window_days: int = 30, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Average valence / energy / danceability over the last `window_days`."""
        try:
            resp = self.db.rpc(
                'get_mood_summary',
                self._uid({'p_window_days': window_days}, user_id),
            )
            if resp and len(resp) > 0:
                row = resp[0]
                return {
                    'window_days': row['window_days'],
                    'avg_valence': float(row['avg_valence']) if row['avg_valence'] is not None else None,
                    'avg_energy': float(row['avg_energy']) if row['avg_energy'] is not None else None,
                    'avg_danceability': float(row['avg_danceability']) if row['avg_danceability'] is not None else None,
                    'sample_size': row['sample_size'],
                }
        except Exception as e:
            print(f"Error getting mood summary: {e}")
        return {
            'window_days': window_days,
            'avg_valence': None,
            'avg_energy': None,
            'avg_danceability': None,
            'sample_size': 0,
        }

    def get_mood_contexts(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Mood metrics for weekday vs weekend and per platform."""
        try:
            resp = self.db.rpc('get_mood_contexts', self._uid({}, user_id))
            if resp:
                return resp  # RPC returns the full jsonb object
        except Exception as e:
            print(f"Error getting mood contexts: {e}")
        return {
            'weekday_vs_weekend': {
                'weekday': {'avg_valence': None, 'avg_energy': None, 'avg_danceability': None, 'sample_size': 0},
                'weekend': {'avg_valence': None, 'avg_energy': None, 'avg_danceability': None, 'sample_size': 0},
            },
            'by_platform': {},
        }

    def get_mood_monthly(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Monthly average mood metrics over time."""
        try:
            resp = self.db.rpc('get_mood_monthly', self._uid({}, user_id))
            if resp:
                return [
                    {
                        'month': row['month'],
                        'avg_valence': float(row['avg_valence']) if row['avg_valence'] is not None else None,
                        'avg_energy': float(row['avg_energy']) if row['avg_energy'] is not None else None,
                        'avg_danceability': float(row['avg_danceability']) if row['avg_danceability'] is not None else None,
                        'sample_size': row['sample_size'],
                    }
                    for row in resp
                ]
        except Exception as e:
            print(f"Error getting mood monthly: {e}")
        return []

    def get_discovery_timeline(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """New-artist discoveries per month (first listen = MIN(ts))."""
        try:
            resp = self.db.rpc('get_discovery_timeline', self._uid({}, user_id))
            if resp:
                return [
                    {'month': row['month'], 'new_artists_count': row['new_artists_count']}
                    for row in resp
                ]
        except Exception as e:
            print(f"Error getting discovery timeline: {e}")
        return []

    def get_artist_loyalty(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return probability and half-life for the top `limit` artists."""
        try:
            resp = self.db.rpc(
                'get_artist_loyalty', self._uid({'p_limit': limit}, user_id)
            )
            if resp:
                return [
                    {
                        'artist': row['artist'],
                        'return_prob': float(row['return_prob']),
                        'half_life_days': float(row['half_life_days']),
                        'total_streams': row['total_streams'],
                    }
                    for row in resp
                ]
        except Exception as e:
            print(f"Error getting artist loyalty: {e}")
        return []

    def get_artist_obsessions(self, limit: int = 15, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Weeks where one artist held >= 30% of listening."""
        try:
            resp = self.db.rpc(
                'get_artist_obsessions', self._uid({'p_limit': limit}, user_id)
            )
            if resp:
                return [
                    {
                        'artist': row['artist'],
                        'period_start': row['period_start'],
                        'period_end': row['period_end'],
                        'period_share': float(row['period_share']),
                        'streams_in_period': row['streams_in_period'],
                    }
                    for row in resp
                ]
        except Exception as e:
            print(f"Error getting artist obsessions: {e}")
        return []

    def get_reflective_insights(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Headline listening stats + 4 templated insight sentences."""
        try:
            resp = self.db.rpc('get_reflective_insights', self._uid({}, user_id))
            if resp:
                data = resp
                return {
                    'total_streams': data['total_streams'],
                    'longest_streak_days': data['longest_streak_days'],
                    'most_active_hour': data['most_active_hour'],
                    'most_active_day': data['most_active_day'],
                    'top_artist': data['top_artist'],
                    'avg_streams_per_day': float(data['avg_streams_per_day']),
                    'insights': data['insights'],
                }
        except Exception as e:
            print(f"Error getting reflective insights: {e}")
        return {
            'total_streams': 0,
            'longest_streak_days': 0,
            'most_active_hour': 0,
            'most_active_day': 'Unknown',
            'top_artist': 'Unknown',
            'avg_streams_per_day': 0,
            'insights': [],
        }

    def get_weekend_weekday_comparison(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Streams / hours / avg-per-day split by weekday vs weekend."""
        try:
            resp = self.db.rpc(
                'get_weekend_weekday_comparison', self._uid({}, user_id)
            )
            if resp:
                return resp
        except Exception as e:
            print(f"Error getting weekend/weekday comparison: {e}")
        return {
            'weekday': {'streams': 0, 'hours': 0, 'avg_per_day': 0},
            'weekend': {'streams': 0, 'hours': 0, 'avg_per_day': 0},
        }

    def get_most_repeated_tracks(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Tracks with the highest plays-per-unique-day score."""
        try:
            resp = self.db.rpc(
                'get_most_repeated_tracks', self._uid({'p_limit': limit}, user_id)
            )
            if resp:
                return [
                    {
                        'track': row['track'],
                        'artist': row['artist'],
                        'play_count': row['play_count'],
                        'repeat_score': float(row['repeat_score']),
                    }
                    for row in resp
                ]
        except Exception as e:
            print(f"Error getting most repeated tracks: {e}")
        return []

    def get_monthly_diversity(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Unique artists / total streams / diversity ratio per month."""
        try:
            resp = self.db.rpc('get_monthly_diversity', self._uid({}, user_id))
            if resp:
                return [
                    {
                        'month': row['month'],
                        'unique_artists': row['unique_artists'],
                        'total_streams': row['total_streams'],
                        'diversity_ratio': float(row['diversity_ratio']),
                    }
                    for row in resp
                ]
        except Exception as e:
            print(f"Error getting monthly diversity: {e}")
        return []

    def get_listening_heatmap(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """168-cell day-hour heatmap (Mon..Sun outer, 0..23 inner)."""
        try:
            resp = self.db.rpc('get_listening_heatmap', self._uid({}, user_id))
            if resp:
                return [
                    {'day': row['day'], 'hour': row['hour'], 'stream_count': row['stream_count']}
                    for row in resp
                ]
        except Exception as e:
            print(f"Error getting listening heatmap: {e}")
        return []

    def get_milestones_list(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Streaks / top days / first-discoveries / diverse days, newest first."""
        try:
            resp = self.db.rpc('get_milestones_list', self._uid({}, user_id))
            if resp:
                return [
                    {
                        'date': row['date'],
                        'year': row['year'],
                        'type': row['type'],
                        'title': row['title'],
                        'description': row['description'],
                        'value': row['value'],
                        'badge_color': row['badge_color'],
                    }
                    for row in resp
                ]
        except Exception as e:
            print(f"Error getting milestones list: {e}")
        return []

    def get_flashback(self, date_str: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Detailed listening recap for one date."""
        try:
            datetime.fromisoformat(date_str)
        except ValueError:
            return {'error': 'Invalid date format. Use YYYY-MM-DD', 'date': date_str}

        try:
            resp = self.db.rpc(
                'get_flashback', self._uid({'p_date': date_str}, user_id)
            )
            if resp:
                return resp
        except Exception as e:
            print(f"Error getting flashback: {e}")
        return {
            'date': date_str,
            'streams': 0,
            'message': 'No listening data found for this date',
        }

    # ------------------------------------------------------------------
    # Analytics — heavy compute (sessions / recommender / simulator)
    #
    # KMeans clustering, the sklearn content-based scorer, and the Markov
    # simulator can't be expressed as one SQL statement, so they run in Python
    # via a per-user SpotifyDataLoader delegate (see _delegate). The numpy/
    # sklearn code and return shapes are shared verbatim with the JSON loader.
    # ------------------------------------------------------------------

    def get_session_durations(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._delegate(user_id).get_session_durations()

    def get_binge_sessions(self, limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._delegate(user_id).get_binge_sessions(limit=limit)

    def get_session_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        return self._delegate(user_id).get_session_statistics()

    def get_session_clusters(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        return self._delegate(user_id).get_session_clusters()

    def get_session_centroids(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._delegate(user_id).get_session_centroids()

    def get_session_assignments(self, limit: int = 100, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._delegate(user_id).get_session_assignments(limit)

    def get_recommendations(self, top_k: int = 20, target_mood: Optional[str] = None,
                            user_id: Optional[str] = None) -> Dict[str, Any]:
        return self._delegate(user_id).get_recommendations(top_k=top_k, target_mood=target_mood)

    def get_recommendations_csv_rows(self, top_k: int = 50, target_mood: Optional[str] = None,
                                     user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._delegate(user_id).get_recommendations_csv_rows(top_k=top_k, target_mood=target_mood)

    def get_sim_artists(self, user_id: Optional[str] = None) -> List[str]:
        return self._delegate(user_id).get_sim_artists()

    def get_simulation(self, seed: Optional[str] = None, n: int = 20, hour: Optional[int] = None,
                       user_id: Optional[str] = None) -> Dict[str, Any]:
        return self._delegate(user_id).get_simulation(seed=seed, n=n, hour=hour)

    def get_simulation_csv_rows(self, seed: Optional[str] = None, n: int = 50, hour: Optional[int] = None,
                                user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._delegate(user_id).get_simulation_csv_rows(seed=seed, n=n, hour=hour)


# ----------------------------------------------------------------------
# Global instance (lazy)
# ----------------------------------------------------------------------
# Constructed on first attribute access rather than at import time. Every route
# module does `from app.services.supabase_data_loader import supabase_data` at
# module scope, so an eager instance made `import app.main` fail outright when
# credentials were absent -- the API could not boot without a Supabase account.
# Deferring construction lets the app import cleanly and, with DB_BACKEND=local,
# run against a local Postgres with no Supabase credentials at all.

_instance: Optional[SupabaseDataLoader] = None


def get_loader() -> SupabaseDataLoader:
    """The process-wide loader, constructed on first use."""
    global _instance
    if _instance is None:
        _instance = SupabaseDataLoader()
    return _instance


def reset_loader() -> None:
    """Drop the cached loader (used by tests and the parity script)."""
    global _instance
    _instance = None


class _LazyLoader:
    """Proxies attribute access to the real loader, building it on demand."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_loader(), name)


supabase_data = _LazyLoader()
