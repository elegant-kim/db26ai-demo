import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// 백엔드(:8247)는 그대로 두고 개발 서버가 /api·/legacy·/static 을 프록시한다.
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://localhost:8247', changeOrigin: true },
      '/legacy': { target: 'http://localhost:8247', changeOrigin: true },
      '/static': { target: 'http://localhost:8247', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
