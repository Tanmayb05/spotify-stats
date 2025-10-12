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

  // Placeholder for future phases
  // Phase 2 - Moods
  // Phase 3 - Discovery
  // Phase 4 - Milestones
  // Phase 5 - Sessions
  // Phase 6 - Recommendations
  // Phase 7 - Simulator
};
