import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api/m3/': {
        target: loadEnv(mode, '.', 'M3_').M3_API_TARGET || 'http://127.0.0.1:3103',
        changeOrigin: true,
      },
    },
  },
}));
