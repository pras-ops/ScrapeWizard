import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    strictPort: true,
    // Proxy all API calls to the FastAPI backend — avoids CORS in dev
    proxy: {
      '/tests':     { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/runs':      { target: 'http://127.0.0.1:8000', changeOrigin: true, ws: true },
      '/settings':  { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/stats':     { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/artifacts': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
    }
  }
})
