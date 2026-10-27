import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        // Only public versioned APIs are forwarded. /internal remains inaccessible.
        '^/api/m1/api/v1/': { target: env.M1_PROXY_TARGET || 'http://127.0.0.1:3101', rewrite: path => path.replace(/^\/api\/m1/, '') },
        '^/api/d/api/v1/': { target: env.D_PROXY_TARGET || 'http://127.0.0.1:3104', rewrite: path => path.replace(/^\/api\/d/, '') },
        '^/api/m3/v1/': { target: env.M3_PROXY_TARGET || 'http://127.0.0.1:3103' },
      },
    },
  };
});
