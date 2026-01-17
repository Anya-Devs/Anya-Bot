const AniListProvider = require('./providers/AniListProvider');
const JikanProvider = require('./providers/JikanProvider');
const KitsuProvider = require('./providers/KitsuProvider');

class CacheManager {
  static instance = null;
  
  constructor() {
    this.characters = {
      legendary: [],
      epic: [],
      rare: [],
      uncommon: [],
      common: []
    };
    this.characterIndex = new Map();
    this.nameIndex = new Map();
    this.loaded = false;
    this.lastRefresh = null;
    this.providers = [
      new AniListProvider(),
      new JikanProvider(),
      new KitsuProvider()
    ];
  }
  
  static getInstance() {
    if (!CacheManager.instance) {
      CacheManager.instance = new CacheManager();
    }
    return CacheManager.instance;
  }
  
  isLoaded() {
    return this.loaded;
  }
  
  async initialize() {
    console.log('🔄 Initializing cache from multiple sources...');
    const startTime = Date.now();
    
    const providerPromises = this.providers.map(provider =>
      provider.fetchCharacters()
        .then(chars => {
          console.log(`   ✓ Got ${chars.length} characters from ${provider.name}`);
          return chars;
        })
        .catch(error => {
          console.error(`   ✗ ${provider.name} failed:`, error.message);
          return [];
        })
    );
    
    const results = await Promise.all(providerPromises);
    const allCharacters = results.flat();
    
    this.processCharacters(allCharacters);
    this.loaded = true;
    this.lastRefresh = new Date();
    
    const loadTime = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`✅ Cache initialized in ${loadTime}s!`);
    this.logStats();
    
    this.scheduleRefresh();
  }
  
  processCharacters(characters) {
    const seen = new Set();
    let processed = 0;
    
    for (const char of characters) {
      if (!char?.name || !char?.image_url || !char?.anime) continue;
      
      const key = `${char.name.toLowerCase()}-${char.anime.toLowerCase()}`;
      if (seen.has(key)) continue;
      seen.add(key);
      
      const rarity = this.calculateRarity(char.favorites || 0, char.anime_popularity || 0);
      char.rarity = rarity;
      char.id = char.id || this.generateId(char);
      
      this.characters[rarity].push(char);
      this.characterIndex.set(String(char.id), char);
      
      const nameLower = char.name.toLowerCase();
      if (!this.nameIndex.has(nameLower)) {
        this.nameIndex.set(nameLower, []);
      }
      this.nameIndex.get(nameLower).push(char);
      
      processed++;
    }
    
    console.log(`   📦 Processed ${processed} unique characters`);
  }
  
  calculateRarity(favorites, animePopularity) {
    const charScore = 
      favorites >= 7000 ? 5 :
      favorites >= 3000 ? 4 :
      favorites >= 800 ? 3 :
      favorites >= 150 ? 2 : 1;
    
    const animeScore = 
      animePopularity >= 2000000 ? 5 :
      animePopularity >= 1000000 ? 4 :
      animePopularity >= 500000 ? 3 :
      animePopularity >= 100000 ? 2 : 1;
    
    const combined = (charScore * 0.8) + (animeScore * 0.2);
    
    if (combined >= 4.5) return 'legendary';
    if (combined >= 3.5) return 'epic';
    if (combined >= 2.5) return 'rare';
    if (combined >= 1.5) return 'uncommon';
    return 'common';
  }
  
  generateId(char) {
    const str = `${char.name}-${char.anime}-${Date.now()}`;
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash);
  }
  
  async getRandomCharacter(targetRarity) {
    const rarity = targetRarity.toLowerCase();
    const pool = this.characters[rarity];
    
    if (!pool?.length) {
      const fallbackOrder = ['common', 'uncommon', 'rare', 'epic', 'legendary'];
      for (const fallback of fallbackOrder) {
        const fallbackPool = this.characters[fallback];
        if (fallbackPool?.length) {
          return fallbackPool[(Math.random() * fallbackPool.length) | 0];
        }
      }
      return null;
    }
    
    return pool[(Math.random() * pool.length) | 0];
  }
  
  searchCharacters(name, limit = 10) {
    const query = name.toLowerCase();
    const results = [];
    const seen = new Set();
    
    if (this.nameIndex.has(query)) {
      const exactMatches = this.nameIndex.get(query);
      for (const char of exactMatches) {
        if (!seen.has(char.id)) {
          results.push(char);
          seen.add(char.id);
          if (results.length >= limit) return results;
        }
      }
    }
    
    for (const [charName, chars] of this.nameIndex) {
      if (charName.includes(query)) {
        for (const char of chars) {
          if (!seen.has(char.id)) {
            results.push(char);
            seen.add(char.id);
            if (results.length >= limit) return results;
          }
        }
      }
    }
    
    for (const pool of Object.values(this.characters)) {
      for (const char of pool) {
        if (!seen.has(char.id) && char.anime?.toLowerCase().includes(query)) {
          results.push(char);
          seen.add(char.id);
          if (results.length >= limit) return results;
        }
      }
    }
    
    return results;
  }
  
  getCharacterById(id) {
    return this.characterIndex.get(String(id)) || null;
  }
  
  getStats() {
    return {
      legendary: this.characters.legendary.length,
      epic: this.characters.epic.length,
      rare: this.characters.rare.length,
      uncommon: this.characters.uncommon.length,
      common: this.characters.common.length,
      total: Object.values(this.characters).reduce((a, b) => a + b.length, 0),
      lastRefresh: this.lastRefresh
    };
  }
  
  logStats() {
    const stats = this.getStats();
    console.log('📊 Cache Statistics:');
    console.log(`   🟡 Legendary: ${stats.legendary}`);
    console.log(`   🟣 Epic: ${stats.epic}`);
    console.log(`   🔵 Rare: ${stats.rare}`);
    console.log(`   🟢 Uncommon: ${stats.uncommon}`);
    console.log(`   ⚪ Common: ${stats.common}`);
    console.log(`   📦 Total: ${stats.total}`);
  }
  
  async refreshCache() {
    console.log('🔄 Refreshing cache...');
    
    this.characters = {
      legendary: [],
      epic: [],
      rare: [],
      uncommon: [],
      common: []
    };
    this.characterIndex.clear();
    this.nameIndex.clear();
    
    await this.initialize();
  }
  
  scheduleRefresh() {
    const REFRESH_INTERVAL = 12 * 60 * 60 * 1000;
    
    setInterval(async () => {
      console.log('⏰ Scheduled cache refresh starting...');
      await this.refreshCache();
    }, REFRESH_INTERVAL);
  }
}

module.exports = CacheManager;
