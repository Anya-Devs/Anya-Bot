const express = require('express');
const router = express.Router();
const CacheManager = require('../services/CacheManager');

router.get('/random', async (req, res) => {
  try {
    const { rarity = 'common' } = req.query;
    const cache = CacheManager.getInstance();
    const character = await cache.getRandomCharacter(rarity);
    
    if (!character) {
      return res.status(404).json({ error: 'No character found for rarity: ' + rarity });
    }
    
    res.json(character);
  } catch (error) {
    console.error('Random character error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/batch', async (req, res) => {
  try {
    const { count = 3, rarities } = req.query;
    const cache = CacheManager.getInstance();
    
    const rarityList = rarities ? rarities.split(',') : ['common', 'common', 'common'];
    const numChars = Math.min(parseInt(count) || 3, 10);
    
    const characters = [];
    for (let i = 0; i < numChars; i++) {
      const rarity = rarityList[i] || rarityList[rarityList.length - 1] || 'common';
      const char = await cache.getRandomCharacter(rarity);
      if (char) characters.push(char);
    }
    
    res.json({ characters, count: characters.length });
  } catch (error) {
    console.error('Batch character error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/search', async (req, res) => {
  try {
    const { name, limit = 10 } = req.query;
    if (!name) {
      return res.status(400).json({ error: 'Name parameter required' });
    }
    
    const cache = CacheManager.getInstance();
    const results = await cache.searchCharacters(name, parseInt(limit));
    
    res.json({ results, count: results.length });
  } catch (error) {
    console.error('Search error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/stats', (req, res) => {
  const cache = CacheManager.getInstance();
  res.json(cache.getStats());
});

router.get('/refresh', async (req, res) => {
  try {
    const cache = CacheManager.getInstance();
    await cache.refreshCache();
    res.json({ success: true, stats: cache.getStats() });
  } catch (error) {
    console.error('Refresh error:', error);
    res.status(500).json({ error: 'Failed to refresh cache' });
  }
});

router.get('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const cache = CacheManager.getInstance();
    const character = cache.getCharacterById(id);
    
    if (!character) {
      return res.status(404).json({ error: 'Character not found' });
    }
    
    res.json(character);
  } catch (error) {
    console.error('Get character error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;
