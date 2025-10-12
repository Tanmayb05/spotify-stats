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
