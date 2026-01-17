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
      // Removed COEP/COOP headers to allow Discord CDN images
      // 'Cross-Origin-Embedder-Policy': 'require-corp',
      // 'Cross-Origin-Opener-Policy': 'same-origin',
    },
    fs: {
      // Allow serving files from one level up to the project root
      allow: ['..']
    },
    // Configure MIME types for WASM files
    middlewareMode: false,
    proxy: {
      // Bot Stats API - local dev proxy with mock data
      '/api/bot-stats': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        bypass: async (req, res) => {
          if (req.method !== 'GET') return;
          
          const token = process.env.VITE_DISCORD_BOT_TOKEN;
          
          // If token available, try real Discord API
          if (token) {
            try {
              const discordRes = await fetch('https://discord.com/api/v10/users/@me/guilds?with_counts=true', {
                headers: { 'Authorization': `Bot ${token}` }
              });
              
              if (discordRes.ok) {
                const guilds = await discordRes.json();
                const users = guilds.reduce((sum: number, g: any) => sum + (g.approximate_member_count || 0), 0);
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                  servers: guilds.length,
                  users: users || guilds.length * 500,
                  commands: 50,
                  status: 'online',
                  lastUpdated: new Date().toISOString(),
                  cached: false,
                  source: 'local-dev'
                }));
                return;
              }
            } catch (e) {
              console.log('Local dev: Discord API failed, using mock data');
            }
          }
          
          // Fallback to mock data
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            servers: 150,
            users: 75000,
            commands: 50,
            status: 'online',
            lastUpdated: new Date().toISOString(),
            cached: true,
            mock: true
          }));
        }
      },
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
