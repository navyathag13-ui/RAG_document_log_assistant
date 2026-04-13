import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // CORS is open on the backend, so no proxy needed.
    // The frontend reads VITE_API_BASE_URL from .env to know where the backend lives.
  },
})
