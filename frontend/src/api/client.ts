import axios, { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3011';

// Create axios instance with default config
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add any auth headers here if needed in future
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const errorMessage =
      error.response?.data?.detail ||
      error.message ||
      'An unexpected error occurred';

    console.error('API Error:', errorMessage);

    return Promise.reject(new Error(errorMessage));
  }
);

import type {
  OverviewStats,
  TopArtist,
  TopTrack,
  MonthlyData,
  PlatformStat,
  MoodSummary,
  MoodContexts,
  MonthlyMood,
  DiscoveryTimeline,
  ArtistLoyalty,
  ArtistObsession,
  ReflectiveInsights,
  HourlyDistribution,
  DailyDistribution,
  SkipBehavior,
  YearlyComparison,
} from '../types/api';

// API functions
export const api = {
  // Health check
  health: () => apiClient.get('/health'),

  // Phase 1 - Overview endpoints
  getOverviewStats: async (): Promise<OverviewStats> => {
    const response = await apiClient.get<OverviewStats>('/api/stats/overview');
    return response.data;
  },

  getTopArtists: async (limit = 10): Promise<TopArtist[]> => {
    const response = await apiClient.get<TopArtist[]>(`/api/top/artists?limit=${limit}`);
    return response.data;
  },

  getTopTracks: async (limit = 10): Promise<TopTrack[]> => {
    const response = await apiClient.get<TopTrack[]>(`/api/top/tracks?limit=${limit}`);
    return response.data;
  },

  getMonthlyData: async (): Promise<MonthlyData[]> => {
    const response = await apiClient.get<MonthlyData[]>('/api/time/monthly');
    return response.data;
  },

  getPlatformStats: async (): Promise<PlatformStat[]> => {
    const response = await apiClient.get<PlatformStat[]>('/api/platforms');
    return response.data;
  },

  // Phase 2 - Moods
  getMoodSummary: async (window: '7d' | '30d' | '90d' | 'all' = '30d'): Promise<MoodSummary> => {
    const response = await apiClient.get<MoodSummary>(`/api/mood/summary?window=${window}`);
    return response.data;
  },

  getMoodContexts: async (): Promise<MoodContexts> => {
    const response = await apiClient.get<MoodContexts>('/api/mood/contexts');
    return response.data;
  },

  getMoodMonthly: async (): Promise<MonthlyMood[]> => {
    const response = await apiClient.get<MonthlyMood[]>('/api/mood/monthly');
    return response.data;
  },

  // Phase 3 - Discovery
  getDiscoveryTimeline: async (): Promise<DiscoveryTimeline[]> => {
    const response = await apiClient.get<DiscoveryTimeline[]>('/api/discovery/timeline');
    return response.data;
  },

  getArtistLoyalty: async (limit = 20): Promise<ArtistLoyalty[]> => {
    const response = await apiClient.get<ArtistLoyalty[]>(`/api/discovery/loyalty?limit=${limit}`);
    return response.data;
  },

  getArtistObsessions: async (limit = 15): Promise<ArtistObsession[]> => {
    const response = await apiClient.get<ArtistObsession[]>(`/api/discovery/obsessions?limit=${limit}`);
    return response.data;
  },

  getReflectiveInsights: async (): Promise<ReflectiveInsights> => {
    const response = await apiClient.get<ReflectiveInsights>('/api/discovery/reflect');
    return response.data;
  },

  // Additional Overview Stats
  getHourlyDistribution: async (): Promise<HourlyDistribution[]> => {
    const response = await apiClient.get<HourlyDistribution[]>('/api/stats/hourly');
    return response.data;
  },

  getDailyDistribution: async (): Promise<DailyDistribution[]> => {
    const response = await apiClient.get<DailyDistribution[]>('/api/stats/daily');
    return response.data;
  },

  getSkipBehavior: async (limit = 20): Promise<SkipBehavior[]> => {
    const response = await apiClient.get<SkipBehavior[]>(`/api/stats/skip-behavior?limit=${limit}`);
    return response.data;
  },

  getYearlyComparison: async (): Promise<YearlyComparison[]> => {
    const response = await apiClient.get<YearlyComparison[]>('/api/stats/yearly');
    return response.data;
  },

  // CSV Export functions
  exportTopArtists: (limit = 50): string => {
    return `${API_BASE_URL}/api/export/top-artists?limit=${limit}`;
  },

  exportTopTracks: (limit = 50): string => {
    return `${API_BASE_URL}/api/export/top-tracks?limit=${limit}`;
  },

  exportMonthlySummary: (): string => {
    return `${API_BASE_URL}/api/export/monthly-summary`;
  },

  // Placeholder for future phases
  // Phase 4 - Milestones
  // Phase 5 - Sessions
  // Phase 6 - Recommendations
  // Phase 7 - Simulator
};
