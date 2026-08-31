import axios, { AxiosError } from 'axios';
import { useAppStore } from '../store/app';

const rawApiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').trim();
const API_BASE_URL = rawApiBaseUrl.replace(/\/+$/, '');

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

/**
 * Adds `user_id` to a query-string when a non-primary user is selected in the
 * global store. Selecting the primary user stores `null`, so primary requests
 * carry no `user_id` and the backend uses its primary-user fallback.
 * Read outside React on purpose — `useAppStore` is a plain store.
 */
function withUser(params?: URLSearchParams): URLSearchParams {
  const q = params ?? new URLSearchParams();
  const uid = useAppStore.getState().selectedUserId;
  if (uid) q.set('user_id', uid);
  return q;
}

/** `?a=b` when the query string is non-empty, else `''`. */
function qs(params: URLSearchParams): string {
  const s = params.toString();
  return s ? `?${s}` : '';
}

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
  SessionDuration,
  BingeSession,
  SessionStatistics,
  WeekendWeekdayComparison,
  ListeningStreak,
  RepeatedTrack,
  MonthlyDiversity,
  HeatmapData,
  Milestone,
  FlashbackData,
  SessionClustersResponse,
  SessionCentroid,
  SessionAssignment,
  RecommendationsResponse,
  TargetMood,
  SimulationResponse,
  CompareUser,
  LeaderboardRow,
  OverlapResult,
  SimilarityMatrix,
  TopArtistsMulti,
} from '../types/api';

// API functions
export const api = {
  // Health check
  health: () => apiClient.get('/health'),

  // Phase 1 - Overview endpoints
  getOverviewStats: async (): Promise<OverviewStats> => {
    const response = await apiClient.get<OverviewStats>(
      `/api/stats/overview${qs(withUser())}`
    );
    return response.data;
  },

  getTopArtists: async (limit = 10): Promise<TopArtist[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<TopArtist[]>(`/api/top/artists${qs(p)}`);
    return response.data;
  },

  getTopTracks: async (limit = 10): Promise<TopTrack[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<TopTrack[]>(`/api/top/tracks${qs(p)}`);
    return response.data;
  },

  getMonthlyData: async (): Promise<MonthlyData[]> => {
    const response = await apiClient.get<MonthlyData[]>(
      `/api/time/monthly${qs(withUser())}`
    );
    return response.data;
  },

  getPlatformStats: async (): Promise<PlatformStat[]> => {
    const response = await apiClient.get<PlatformStat[]>(
      `/api/platforms${qs(withUser())}`
    );
    return response.data;
  },

  // Phase 2 - Moods
  getMoodSummary: async (
    window: '7d' | '30d' | '90d' | 'all' = '30d'
  ): Promise<MoodSummary> => {
    const p = withUser(new URLSearchParams({ window }));
    const response = await apiClient.get<MoodSummary>(`/api/mood/summary${qs(p)}`);
    return response.data;
  },

  getMoodContexts: async (): Promise<MoodContexts> => {
    const response = await apiClient.get<MoodContexts>(
      `/api/mood/contexts${qs(withUser())}`
    );
    return response.data;
  },

  getMoodMonthly: async (): Promise<MonthlyMood[]> => {
    const response = await apiClient.get<MonthlyMood[]>(
      `/api/mood/monthly${qs(withUser())}`
    );
    return response.data;
  },

  // Phase 3 - Discovery
  getDiscoveryTimeline: async (): Promise<DiscoveryTimeline[]> => {
    const response = await apiClient.get<DiscoveryTimeline[]>(
      `/api/discovery/timeline${qs(withUser())}`
    );
    return response.data;
  },

  getArtistLoyalty: async (limit = 20): Promise<ArtistLoyalty[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<ArtistLoyalty[]>(
      `/api/discovery/loyalty${qs(p)}`
    );
    return response.data;
  },

  getArtistObsessions: async (limit = 15): Promise<ArtistObsession[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<ArtistObsession[]>(
      `/api/discovery/obsessions${qs(p)}`
    );
    return response.data;
  },

  getReflectiveInsights: async (): Promise<ReflectiveInsights> => {
    const response = await apiClient.get<ReflectiveInsights>(
      `/api/discovery/reflect${qs(withUser())}`
    );
    return response.data;
  },

  // Additional Overview Stats
  getHourlyDistribution: async (): Promise<HourlyDistribution[]> => {
    const response = await apiClient.get<HourlyDistribution[]>(
      `/api/stats/hourly${qs(withUser())}`
    );
    return response.data;
  },

  getDailyDistribution: async (): Promise<DailyDistribution[]> => {
    const response = await apiClient.get<DailyDistribution[]>(
      `/api/stats/daily${qs(withUser())}`
    );
    return response.data;
  },

  getSkipBehavior: async (limit = 20): Promise<SkipBehavior[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<SkipBehavior[]>(
      `/api/stats/skip-behavior${qs(p)}`
    );
    return response.data;
  },

  getYearlyComparison: async (): Promise<YearlyComparison[]> => {
    const response = await apiClient.get<YearlyComparison[]>(
      `/api/stats/yearly${qs(withUser())}`
    );
    return response.data;
  },

  // CSV Export functions
  exportTopArtists: (limit = 50): string => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    return `${API_BASE_URL}/api/export/top-artists${qs(p)}`;
  },

  exportTopTracks: (limit = 50): string => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    return `${API_BASE_URL}/api/export/top-tracks${qs(p)}`;
  },

  exportMonthlySummary: (): string => {
    return `${API_BASE_URL}/api/export/monthly-summary${qs(withUser())}`;
  },

  // Listening Patterns endpoints
  getSessionDurations: async (): Promise<SessionDuration[]> => {
    const response = await apiClient.get<SessionDuration[]>(
      `/api/patterns/session-durations${qs(withUser())}`
    );
    return response.data;
  },

  getBingeSessions: async (limit = 20): Promise<BingeSession[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<BingeSession[]>(
      `/api/patterns/binge-sessions${qs(p)}`
    );
    return response.data;
  },

  getSessionStatistics: async (): Promise<SessionStatistics> => {
    const response = await apiClient.get<SessionStatistics>(
      `/api/patterns/session-statistics${qs(withUser())}`
    );
    return response.data;
  },

  getWeekendWeekdayComparison: async (): Promise<WeekendWeekdayComparison> => {
    const response = await apiClient.get<WeekendWeekdayComparison>(
      `/api/patterns/weekend-weekday${qs(withUser())}`
    );
    return response.data;
  },

  getListeningStreaks: async (limit = 10): Promise<ListeningStreak[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<ListeningStreak[]>(
      `/api/patterns/listening-streaks${qs(p)}`
    );
    return response.data;
  },

  getRepeatedTracks: async (limit = 20): Promise<RepeatedTrack[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<RepeatedTrack[]>(
      `/api/patterns/repeated-tracks${qs(p)}`
    );
    return response.data;
  },

  getMonthlyDiversity: async (): Promise<MonthlyDiversity[]> => {
    const response = await apiClient.get<MonthlyDiversity[]>(
      `/api/patterns/monthly-diversity${qs(withUser())}`
    );
    return response.data;
  },

  getListeningHeatmap: async (): Promise<HeatmapData[]> => {
    const response = await apiClient.get<HeatmapData[]>(
      `/api/patterns/heatmap${qs(withUser())}`
    );
    return response.data;
  },

  // Phase 4 - Milestones
  getMilestones: async (): Promise<Milestone[]> => {
    const response = await apiClient.get<Milestone[]>(
      `/api/milestones/list${qs(withUser())}`
    );
    return response.data;
  },

  getFlashback: async (date: string): Promise<FlashbackData> => {
    const p = withUser(new URLSearchParams({ date }));
    const response = await apiClient.get<FlashbackData>(
      `/api/milestones/flashback${qs(p)}`
    );
    return response.data;
  },

  // Phase 5 - Sessions & Clustering
  getSessionClusters: async (): Promise<SessionClustersResponse> => {
    const response = await apiClient.get<SessionClustersResponse>(
      `/api/sessions/clusters${qs(withUser())}`
    );
    return response.data;
  },

  getSessionCentroids: async (): Promise<SessionCentroid[]> => {
    const response = await apiClient.get<SessionCentroid[]>(
      `/api/sessions/centroids${qs(withUser())}`
    );
    return response.data;
  },

  getSessionAssignments: async (limit = 100): Promise<SessionAssignment[]> => {
    const p = withUser(new URLSearchParams({ limit: String(limit) }));
    const response = await apiClient.get<SessionAssignment[]>(
      `/api/sessions/assignments${qs(p)}`
    );
    return response.data;
  },

  // Phase 6 - Recommendations
  getRecommendations: async (
    topK = 20,
    targetMood?: TargetMood
  ): Promise<RecommendationsResponse> => {
    const p = withUser(new URLSearchParams({ top_k: String(topK) }));
    if (targetMood) p.set('target_mood', targetMood);
    const response = await apiClient.get<RecommendationsResponse>(
      `/api/reco${qs(p)}`
    );
    return response.data;
  },

  exportRecommendations: (topK = 50, targetMood?: TargetMood): string => {
    const p = withUser(new URLSearchParams({ top_k: String(topK) }));
    if (targetMood) p.set('target_mood', targetMood);
    return `${API_BASE_URL}/api/export/recommendations${qs(p)}`;
  },

  // Phase 7 - Simulator
  getSimulation: async (
    n = 20,
    seed?: string,
    hour?: number
  ): Promise<SimulationResponse> => {
    const p = withUser(new URLSearchParams({ n: String(n) }));
    if (seed) p.set('seed', seed);
    if (hour != null) p.set('hour', String(hour));
    const response = await apiClient.get<SimulationResponse>(
      `/api/simulate/next${qs(p)}`
    );
    return response.data;
  },

  getSimulationArtists: async (): Promise<string[]> => {
    const response = await apiClient.get<{ artists: string[] }>(
      `/api/simulate/artists${qs(withUser())}`
    );
    return response.data.artists;
  },

  exportSimulation: (n = 50, seed?: string, hour?: number): string => {
    const p = withUser(new URLSearchParams({ n: String(n) }));
    if (seed) p.set('seed', seed);
    if (hour != null) p.set('hour', String(hour));
    return `${API_BASE_URL}/api/export/simulation${qs(p)}`;
  },

  // Friend-group comparison (already multi-user via `users` param — no withUser)
  getCompareUsers: async (): Promise<CompareUser[]> => {
    const response = await apiClient.get<CompareUser[]>('/api/compare/users');
    return response.data;
  },

  getLeaderboard: async (): Promise<LeaderboardRow[]> => {
    const response = await apiClient.get<LeaderboardRow[]>('/api/compare/leaderboard');
    return response.data;
  },

  getOverlap: async (userIds: string[], topN = 25): Promise<OverlapResult> => {
    const q = new URLSearchParams({ users: userIds.join(','), top_n: String(topN) });
    const response = await apiClient.get<OverlapResult>(`/api/compare/overlap?${q.toString()}`);
    return response.data;
  },

  getSimilarityMatrix: async (): Promise<SimilarityMatrix> => {
    const response = await apiClient.get<SimilarityMatrix>('/api/compare/similarity-matrix');
    return response.data;
  },

  getTopArtistsMulti: async (userIds: string[], limit = 10): Promise<TopArtistsMulti> => {
    const q = new URLSearchParams({ users: userIds.join(','), limit: String(limit) });
    const response = await apiClient.get<TopArtistsMulti>(`/api/compare/top-artists?${q.toString()}`);
    return response.data;
  },
};
