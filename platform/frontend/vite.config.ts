import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Dev: proxy /api → backend so the SPA stays same-origin.
// VITE_BASE=/apps/kooremapper/ 로 빌드하면 HEAX 포탈 서브패스용 산출물이 된다.
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    port: Number(process.env.WEB_PORT) || 5273,
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8700',
        changeOrigin: true,
      },
    },
  },
})
