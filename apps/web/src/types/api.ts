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

// Phase 2 - Mood Types

export interface MoodSummary {
  window_days: number;
  avg_valence: number | null;
  avg_energy: number | null;
  avg_danceability: number | null;
  sample_size: number;
}

export interface MoodMetrics {
  avg_valence: number | null;
  avg_energy: number | null;
  avg_danceability: number | null;
  sample_size: number;
}

export interface MoodContexts {
  weekday_vs_weekend: {
    weekday: MoodMetrics;
    weekend: MoodMetrics;
  };
  by_platform: Record<string, MoodMetrics>;
}

export interface MonthlyMood {
  month: string;
  avg_valence: number | null;
  avg_energy: number | null;
  avg_danceability: number | null;
  sample_size: number;
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

export interface HeatmapData {
  day: string;
  hour: number;
  stream_count: number;
}

// Phase 4 - Milestones Types

export interface Milestone {
  date: string;
  year: number;
  type: 'streak' | 'top_day' | 'first_artist' | 'diversity';
  title: string;
  description: string;
  value: number;
  badge_color: string;
}

export interface FlashbackData {
  date: string;
  day_of_week: string;
  streams: number;
  hours: number;
  unique_artists: number;
  unique_tracks: number;
  skipped: number;
  skip_rate: number;
  first_stream: string | null;
  last_stream: string | null;
  listening_duration: string | null;
  top_artists: Array<{ artist: string; streams: number }>;
  top_tracks: Array<{ track: string; artist: string; plays: number }>;
  message?: string;
  error?: string;
}

// Phase 5 - Sessions & Clustering Types

export interface SessionClusterProfile {
  cluster_id: number;
  session_count: number;
  avg_duration: number;
  avg_tracks: number;
  avg_skip_ratio: number;
  avg_diversity: number;
  common_hour: number;
  weekend_ratio: number;
}

export interface SessionClustersResponse {
  n_clusters: number;
  total_sessions: number;
  silhouette_score: number;
  clusters: SessionClusterProfile[];
  error?: string;
}

export interface SessionCentroid {
  cluster_id: number;
  features: {
    duration_minutes: number;
    track_count: number;
    unique_artists_count: number;
    skip_ratio: number;
    avg_track_duration: number;
    hour_of_day: number;
    is_weekend: number;
    diversity_score: number;
  };
}

export interface SessionAssignment {
  session_id: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  track_count: number;
  unique_artists_count: number;
  skip_ratio: number;
  avg_track_duration: number;
  hour_of_day: number;
  is_weekend: number;
  diversity_score: number;
  platform: string;
  cluster_label: number;
}
