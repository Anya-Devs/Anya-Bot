class KitsuProvider {
  constructor() {
    this.name = 'Kitsu';
    this.baseUrl = 'https://kitsu.io/api/edge';
  }
  
  async fetchCharacters() {
    const topAnime = await this.fetchTopAnime();
    
    const animePromises = topAnime.slice(0, 80).map(anime =>
      this.fetchAnimeCharacters(anime).catch(() => [])
    );
    
    const results = await Promise.all(animePromises);
    return results.flat();
  }
  
  async fetchTopAnime() {
    const pagePromises = [];
    for (let offset = 0; offset < 400; offset += 20) {
      pagePromises.push(
        fetch(
          `${this.baseUrl}/anime?page[limit]=20&page[offset]=${offset}&sort=-userCount`,
          { headers: { 'Accept': 'application/vnd.api+json' } }
        )
        .then(async res => {
          if (!res.ok) return [];
          const data = await res.json();
          return (data?.data || []).map(anime => ({
            id: anime.id,
            title: anime.attributes?.canonicalTitle || anime.attributes?.titles?.en || 'Unknown',
            userCount: anime.attributes?.userCount || 0
          }));
        })
        .catch(() => [])
      );
    }
    
    const results = await Promise.all(pagePromises);
    return results.flat();
  }
  
  async fetchAnimeCharacters(anime) {
    const characters = [];
    
    try {
      const response = await fetch(
        `${this.baseUrl}/anime/${anime.id}/characters?include=character&page[limit]=15`,
        {
          headers: { 'Accept': 'application/vnd.api+json' }
        }
      );
      
      if (!response.ok) return characters;
      
      const data = await response.json();
      const included = data?.included || [];
      
      for (const item of included) {
        if (item.type !== 'characters') continue;
        
        const attrs = item.attributes || {};
        const imageUrl = attrs.image?.original || attrs.image?.large || attrs.image?.medium;
        
        if (!imageUrl || imageUrl.includes('missing')) continue;
        
        characters.push({
          id: parseInt(item.id) || this.generateId(attrs.name),
          name: attrs.canonicalName || attrs.name || 'Unknown',
          anime: anime.title,
          anime_popularity: anime.userCount,
          image_url: imageUrl,
          gender: 'Unknown',
          favorites: attrs.favoritesCount || 0,
          description: this.cleanDescription(attrs.description),
          api_source: 'Kitsu'
        });
      }
    } catch (error) {
      console.error(`Kitsu characters for anime ${anime.id} error:`, error.message);
    }
    
    return characters;
  }
  
  generateId(name) {
    if (!name) return Math.floor(Math.random() * 1000000);
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = ((hash << 5) - hash) + name.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash);
  }
  
  cleanDescription(desc) {
    if (!desc) return '';
    return desc
      .replace(/<[^>]*>/g, '')
      .replace(/\n+/g, ' ')
      .trim()
      .slice(0, 300);
  }
  
}

module.exports = KitsuProvider;
