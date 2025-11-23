import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'url';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  optimizeDeps: {
    esbuildOptions: {
      target: 'es2020',
      supported: { bigint: true },
      // Add this to handle .wasm files
      loader: {
        '.wasm': 'file'
      }
    },
    include: ['onnxruntime-web']
  },
  build: {
    target: 'es2020',
    outDir: 'dist',
    sourcemap: true,
    // Ensure wasm files are not inlined and keep their original names
    assetsInlineLimit: 0,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
        },
        // Handle wasm files with their original names
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.wasm')) {
            return 'assets/[name][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
      },
    },
  },
  server: {
    port: 3001,
    open: true,
    headers: {
      'Cross-Origin-Embedder-Policy': 'require-corp',
      'Cross-Origin-Opener-Policy': 'same-origin',
    },
    fs: {
      // Allow serving files from one level up to the project root
      allow: ['..']
    },
    proxy: {
      // Top.gg API
      '/api/topgg': {
        target: 'https://top.gg',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/topgg/, '/api'),
      },
      // Discord Bot List API
      '/api/dbl': {
        target: 'https://discordbotlist.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/dbl/, '/api/v1'),
      },
      // Danbooru proxy with authentication
      '/api/danbooru': {
        target: 'https://danbooru.donmai.us',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/danbooru\//, '/'),
        configure: (proxy: any) => {
          proxy.on('proxyReq', (proxyReq: any) => {
            // Add Danbooru API key if available
            if (process.env.VITE_DANBOORU_API_KEY && process.env.VITE_DANBOURU_USER) {
              proxyReq.setHeader('Authorization', `Basic ${Buffer.from(
                `${process.env.VITE_DANBOURU_USER}:${process.env.VITE_DANBOORU_API_KEY}`
              ).toString('base64')}`);
            }
          });
        }
      },
      // Gelbooru proxy with authentication
      '/api/gelbooru': {
        target: 'https://gelbooru.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/gelbooru\//, '/'),
        configure: (proxy: any) => {
          proxy.on('proxyReq', (proxyReq: any) => {
            // Add API key and user ID if available
            if (process.env.VITE_GELBOORU_API_KEY && process.env.VITE_GELBOORU_USER_ID) {
              const url = new URL(proxyReq.path, 'http://dummy.com');
              url.searchParams.set('api_key', process.env.VITE_GELBOORU_API_KEY);
              url.searchParams.set('user_id', process.env.VITE_GELBOORU_USER_ID);
              proxyReq.path = `${url.pathname}${url.search}`;
            }
          });
        }
      },
      // Anilist GraphQL API
      '/api/anilist': {
        target: 'https://graphql.anilist.co',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/anilist/, ''),
        configure: (proxy: any) => {
          proxy.on('error', (err: Error) => {
            console.log('AniList proxy error:', err);
          });
          proxy.on('proxyReq', (proxyReq: any) => {
            proxyReq.setHeader('Content-Type', 'application/json');
            proxyReq.setHeader('Accept', 'application/json');
          });
        }
      },
      // Jikan API (MyAnimeList)
      '/api/jikan': {
        target: 'https://api.jikan.moe',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/jikan/, '/v4'),
      },
      // Konachan image board
      '/api/konachan': {
        target: 'https://konachan.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/konachan\//, '/'),
      },
      // Yande.re image board
      '/api/yande': {
        target: 'https://yande.re',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/yande\//, '/'),
      }
    },
  },
});
