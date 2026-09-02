// API Response Types

export interface OverviewStats {
  total_streams: number;
  total_hours: number;
  unique_tracks: number;
  unique_artists: number;
  unique_albums: number;
}

export interface TopArtist {
  artist: string;
  streams: number;
}

export interface TopTrack {
  track: string;
  artist: string;
  streams: number;
}

export interface MonthlyData {
  month: string;
  streams: number;
  hours: number;
}

export interface PlatformStat {
  platform: string;
  streams: number;
}

// Phase 3 - Discovery Types

export interface DiscoveryTimeline {
  month: string;
  new_artists_count: number;
}

export interface ArtistLoyalty {
  artist: string;
  return_prob: number;
  half_life_days: number;
  total_streams: number;
}

export interface ArtistObsession {
  artist: string;
  period_start: string;
  period_end: string;
  period_share: number;
  streams_in_period: number;
}

export interface ReflectiveInsights {
  total_streams: number;
  longest_streak_days: number;
  most_active_hour: number;
  most_active_day: string;
  top_artist: string;
  avg_streams_per_day: number;
  insights: string[];
}

// Phase 3+ - Additional Overview Types

export interface HourlyDistribution {
  hour: number;
  streams: number;
}

export interface DailyDistribution {
  day: string;
  streams: number;
}

export interface SkipBehavior {
  artist: string;
  total_streams: number;
  skipped_count: number;
  skip_rate: number;
}

export interface YearlyComparison {
  year: number;
  streams: number;
  hours: number;
}

// Listening Patterns Types

export interface SessionDuration {
  duration_range: string;
  session_count: number;
}

export interface BingeSession {
  session_date: string;
  duration_minutes: number;
  track_count: number;
}

export interface SessionStatistics {
  total_sessions: number;
  avg_duration_minutes: number;
  median_duration_minutes: number;
  avg_tracks_per_session: number;
  longest_session_minutes: number;
}

export interface WeekendWeekdayComparison {
  weekday: {
    streams: number;
    hours: number;
    avg_per_day: number;
  };
  weekend: {
    streams: number;
    hours: number;
    avg_per_day: number;
  };
}

export interface ListeningStreak {
  start_date: string;
  end_date: string;
  length_days: number;
  total_streams: number;
}

export interface RepeatedTrack {
  track: string;
  artist: string;
  play_count: number;
  repeat_score: number;
}

export interface MonthlyDiversity {
  month: string;
  unique_artists: number;
  total_streams: number;
  diversity_ratio: number;
}

// Phase 6 - Recommendations
export interface RecommendationWhyFeature {
  feature: string;
  value: number;
}

export interface RecommendationWhy {
  summary: string;
  top_features: RecommendationWhyFeature[];
}

export interface Recommendation {
  track: string;
  artist: string;
  album: string;
  track_uri: string;
  score: number;
  play_count: number;
  why: RecommendationWhy;
}

export interface RecommendationsResponse {
  target_mood: string | null;
  generated_at: string;
  count: number;
  recommendations: Recommendation[];
}

export type TargetMood = 'happy' | 'energetic' | 'chill';

// Multi-user switcher
export interface CompareUser {
  user_id: string;
  username: string;
  display_name: string;
  is_primary: boolean;
}

// Phase 13 - Data Health (/api/health/data)

export type DqStatus = 'pass' | 'warn' | 'fail' | 'running' | 'error' | 'unknown';

export interface DqCheck {
  name: string;
  severity: 'blocking' | 'warn';
  passed: boolean;
  skipped: boolean;
  observed: string | null;
  observed_numeric: number | null;
  expected: string | null;
  rows_failed: number;
  user_id: string | null;
  detail: Record<string, unknown> | null;
}

export interface DqCategory {
  category: string;
  total: number;
  passed: number;
  failed: number;
  warned: number;
  skipped: number;
  status: 'pass' | 'warn' | 'fail';
  checks: DqCheck[];
}

export interface DqBlock {
  has_run: boolean;
  status: DqStatus;
  message?: string;
  dq_run_id?: string;
  run_at?: string;
  finished_at?: string | null;
  ingest_run_id?: string | null;
  checks_total?: number;
  passed?: number;
  failed?: number;
  warned?: number;
  skipped?: number;
  duration_ms?: number | null;
  categories: DqCategory[];
}

export interface IngestBlock {
  has_run: boolean;
  message?: string;
  run_id?: string;
  started_at?: string;
  finished_at?: string | null;
  status?: string;
  users?: number;
  files_seen?: number;
  files_new?: number;
  rows_raw?: number;
  rows_valid?: number;
  rows_quarantined?: number;
  rows_landed?: number;
  dups_dropped?: number;
  rows_silver?: number;
  rows_fact?: number;
  track_match_rate?: number | null;
  artist_match_rate?: number | null;
  unmatched_tracks?: number | null;
  unmatched_artists?: number | null;
  invariants?: Record<string, boolean | null>;
}

export interface PerUserHealth {
  user_id: string;
  username: string | null;
  display_name: string | null;
  is_primary: boolean;
  rows_raw: number;
  rows_silver: number;
  dups_dropped: number;
  rows_quarantined: number;
  max_ts: string | null;
  freshness_days: number | null;
  freshness_status: string;
}

export interface TrendPoint {
  run_id: string;
  started_at: string | null;
  rows_fact: number;
  rows_raw: number;
  rows_quarantined: number;
  dups_dropped: number;
  status: string | null;
}

export interface DataHealthResponse {
  backend: string;
  generated_at: string;
  dq: DqBlock;
  ingest: IngestBlock;
  per_user: PerUserHealth[];
  quarantine: {
    total: number;
    by_rule: Record<string, number>;
    sample: Array<Record<string, unknown>>;
  };
  trend: TrendPoint[];
}
