import { create } from 'zustand';

type ThemeMode = 'light' | 'dark';

interface AppState {
  themeMode: ThemeMode;
  toggleTheme: () => void;
  error: string | null;
  setError: (error: string | null) => void;
  isLoading: boolean;
  setLoading: (loading: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  themeMode: 'dark',
  toggleTheme: () =>
    set((state) => ({
      themeMode: state.themeMode === 'dark' ? 'light' : 'dark',
    })),
  error: null,
  setError: (error) => set({ error }),
  isLoading: false,
  setLoading: (loading) => set({ isLoading: loading }),
}));
