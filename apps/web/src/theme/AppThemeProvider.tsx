import { useMemo } from 'react';
import type { ReactNode } from 'react';
import { createTheme, ThemeProvider, CssBaseline } from '@mui/material';
import { useAppStore } from '../store/app';

interface AppThemeProviderProps {
  children: ReactNode;
}

export default function AppThemeProvider({ children }: AppThemeProviderProps) {
  const mode = useAppStore((state) => state.themeMode);

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode,
          ...(mode === 'dark'
            ? {
                primary: {
                  main: '#2dd881', // Emerald
                },
                secondary: {
                  main: '#4ea699', // Keppel
                },
                background: {
                  default: '#1c0b19', // Dark purple
                  paper: '#140d4f', // Federal blue
                },
              }
            : {
                primary: {
                  main: '#2dd881', // Emerald
                },
                secondary: {
                  main: '#4ea699', // Keppel
                },
              }),
        },
        typography: {
          fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
          h1: {
            fontWeight: 700,
          },
          h2: {
            fontWeight: 700,
          },
          h3: {
            fontWeight: 600,
          },
          h4: {
            fontWeight: 600,
          },
          h5: {
            fontWeight: 600,
          },
          h6: {
            fontWeight: 600,
          },
        },
        shape: {
          borderRadius: 8,
        },
        components: {
          MuiButton: {
            styleOverrides: {
              root: {
                textTransform: 'none',
                fontWeight: 600,
              },
            },
          },
          MuiCard: {
            styleOverrides: {
              root: {
                backgroundImage: 'none',
              },
            },
          },
        },
      }),
    [mode]
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}
