import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type ThemeMode = 'light' | 'dark';

interface AppState {
  themeMode: ThemeMode;
  toggleTheme: () => void;
  error: string | null;
  setError: (error: string | null) => void;
  isLoading: boolean;
  setLoading: (loading: boolean) => void;
  /**
   * Currently selected user for all analytics pages.
   * `null` = the primary user; API calls then omit `user_id` and the backend
   * falls back to the primary user (SQL `_effective_user_id`). Persisted so a
   * reload keeps the chosen user.
   */
  selectedUserId: string | null;
  setSelectedUserId: (id: string | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      themeMode: 'dark',
      toggleTheme: () =>
        set((state) => ({
          themeMode: state.themeMode === 'dark' ? 'light' : 'dark',
        })),
      error: null,
      setError: (error) => set({ error }),
      isLoading: false,
      setLoading: (loading) => set({ isLoading: loading }),
      selectedUserId: null,
      setSelectedUserId: (id) => set({ selectedUserId: id }),
    }),
    {
      name: 'spotify-insights-user',
      // only the user selection is persisted; theme/error/loading stay in memory
      partialize: (state) => ({ selectedUserId: state.selectedUserId }),
    }
  )
);
