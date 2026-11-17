import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // 5173 is the origin the backend's CORS_ORIGINS allows by default.
  server: { host: true, port: 5173, strictPort: true },
  preview: { port: 5173 },
  // Unit tests cover pure logic (grouping, validation, formatting); no DOM needed.
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
