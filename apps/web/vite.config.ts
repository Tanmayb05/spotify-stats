import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3010,
    // Allow current ngrok URL plus future ngrok-free.dev subdomains.
    allowedHosts: ['dominion-undrilled-rural.ngrok-free.dev', '.ngrok-free.dev'],
    proxy: {
      '/api': {
        target: 'http://localhost:3011',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:3011',
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
