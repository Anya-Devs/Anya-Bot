const express = require('express');
const cors = require('cors');
const compression = require('compression');
const helmet = require('helmet');
const characterRoutes = require('./routes/characters');
const CacheManager = require('./services/CacheManager');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(helmet());
app.use(cors());
app.use(compression());
app.use(express.json());

app.use('/api/characters', characterRoutes);

app.get('/health', (req, res) => {
  const cache = CacheManager.getInstance();
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    cache: {
      loaded: cache.isLoaded(),
      stats: cache.getStats()
    }
  });
});

app.get('/', (req, res) => {
  res.json({
    name: 'Anime Gacha API',
    version: '1.0.0',
    endpoints: {
      health: '/health',
      random: '/api/characters/random?rarity=common|uncommon|rare|epic|legendary',
      batch: '/api/characters/batch?count=3&rarities=common,rare,legendary',
      search: '/api/characters/search?name=naruto',
      byId: '/api/characters/:id',
      stats: '/api/characters/stats'
    }
  });
});

async function startServer() {
  const cache = CacheManager.getInstance();
  
  console.log('🚀 Starting Anime Gacha API...');
  console.log('📦 Loading character cache...');
  
  await cache.initialize();
  
  app.listen(PORT, () => {
    console.log(`✅ Server running on port ${PORT}`);
    console.log(`📊 Cache loaded: ${cache.getStats().total} characters`);
  });
}

startServer().catch(console.error);
