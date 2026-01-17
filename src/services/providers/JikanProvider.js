class JikanProvider {
  constructor() {
    this.name = 'Jikan';
    this.baseUrl = 'https://api.jikan.moe/v4';
  }
  
  async fetchCharacters() {
    const [topAnimeIds, topChars] = await Promise.all([
      this.fetchTopAnimeIds(),
      this.fetchTopCharacters()
    ]);
    
    const animePromises = topAnimeIds.slice(0, 100).map(animeId =>
      this.fetchAnimeCharacters(animeId).catch(() => [])
    );
    
    const animeResults = await Promise.all(animePromises);
    return [...animeResults.flat(), ...topChars];
  }
  
  async fetchTopAnimeIds() {
    const pagePromises = [];
    for (let page = 1; page <= 10; page++) {
      pagePromises.push(
        fetch(`${this.baseUrl}/top/anime?page=${page}&limit=25`)
          .then(async res => {
            if (!res.ok) return [];
            const data = await res.json();
            return (data?.data || []).map(anime => ({
              id: anime.mal_id,
              title: anime.title || anime.title_english || 'Unknown',
              members: anime.members || 0
            })).filter(a => a.id);
          })
          .catch(() => [])
      );
    }
    
    const results = await Promise.all(pagePromises);
    return results.flat();
  }
  
  async fetchAnimeCharacters(animeInfo) {
    const characters = [];
    
    try {
      const response = await fetch(`${this.baseUrl}/anime/${animeInfo.id}/characters`);
      if (!response.ok) return characters;
      
      const data = await response.json();
      const charList = data?.data || [];
      
      for (const charData of charList.slice(0, 15)) {
        const char = charData.character;
        if (!char) continue;
        
        const imageUrl = char.images?.jpg?.image_url || char.images?.webp?.image_url;
        if (!imageUrl) continue;
        
        characters.push({
          id: char.mal_id,
          name: char.name || 'Unknown',
          anime: animeInfo.title,
          anime_popularity: animeInfo.members,
          image_url: imageUrl,
          gender: 'Unknown',
          favorites: charData.favorites || 0,
          role: charData.role || 'Supporting',
          api_source: 'Jikan'
        });
      }
    } catch (error) {
      console.error(`Jikan characters for anime ${animeInfo.id} error:`, error.message);
    }
    
    return characters;
  }
  
  async fetchTopCharacters() {
    const pagePromises = [];
    for (let page = 1; page <= 20; page++) {
      pagePromises.push(
        fetch(`${this.baseUrl}/top/characters?page=${page}&limit=25`)
          .then(async res => {
            if (!res.ok) return [];
            const data = await res.json();
            return (data?.data || []).map(char => {
              const imageUrl = char.images?.jpg?.image_url || char.images?.webp?.image_url;
              if (!imageUrl) return null;
              
              let animeName = 'Unknown';
              if (char.anime && char.anime.length > 0) {
                const firstAnime = char.anime[0];
                animeName = firstAnime.anime?.title || firstAnime.title || 'Unknown';
              }
              
              return {
                id: char.mal_id,
                name: char.name || 'Unknown',
                anime: animeName,
                anime_popularity: 0,
                image_url: imageUrl,
                gender: 'Unknown',
                favorites: char.favorites || 0,
                about: this.cleanAbout(char.about),
                api_source: 'Jikan'
              };
            }).filter(c => c !== null);
          })
          .catch(() => [])
      );
    }
    
    const results = await Promise.all(pagePromises);
    return results.flat();
  }
  
  cleanAbout(about) {
    if (!about) return '';
    return about
      .replace(/\n+/g, ' ')
      .trim()
      .slice(0, 300);
  }
  
}

module.exports = JikanProvider;
