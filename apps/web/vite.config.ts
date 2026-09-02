import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Where the dev server proxies /api and /health. Defaults to the local backend
// from start.sh; docker compose sets it to the api service (http://api:3011).
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:3011'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3010,
    // Allow current ngrok URL plus future ngrok-free.dev subdomains.
    allowedHosts: ['dominion-undrilled-rural.ngrok-free.dev', '.ngrok-free.dev'],
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '/health': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    // Optimize build for production
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-mui': ['@mui/material', '@emotion/react', '@emotion/styled', '@mui/icons-material'],
          'vendor-charts': ['@mui/x-charts'],
        },
      },
    },
  },
})
