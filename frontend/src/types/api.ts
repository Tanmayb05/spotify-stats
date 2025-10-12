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
