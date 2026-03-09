// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0'
  },
  build: {
    outDir: 'dist'
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [],
  },
})

