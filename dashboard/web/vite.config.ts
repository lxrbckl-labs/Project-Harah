import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Frontend dev server proxies /api to the FastAPI backend (127.0.0.1:8770),
// so there are no CORS concerns and prod can serve both from one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8770',
    },
  },
})
