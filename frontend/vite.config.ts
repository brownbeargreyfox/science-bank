import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev proxy target: set API_PROXY_TARGET (e.g. http://127.0.0.1:8791) to point
// the dev server at a running backend. Defaults to a local uvicorn on :8000.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/healthz': { target: apiTarget, changeOrigin: true },
      '/readyz': { target: apiTarget, changeOrigin: true },
    },
  },
})
