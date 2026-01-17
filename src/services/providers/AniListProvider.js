class AniListProvider {
  constructor() {
    this.name = 'AniList';
    this.baseUrl = 'https://graphql.anilist.co';
  }
  
  async fetchCharacters() {
    const popularityRanges = [
      { min: 200000, max: 999999, label: 'legendary' },
      { min: 100000, max: 199999, label: 'epic' },
      { min: 50000, max: 99999, label: 'rare' },
      { min: 20000, max: 49999, label: 'uncommon' },
      { min: 5000, max: 19999, label: 'common' }
    ];
    
    const promises = popularityRanges.map(range => 
      this.fetchByPopularity(range.min, range.max)
        .catch(err => {
          console.error(`AniList ${range.label} fetch failed:`, err.message);
          return [];
        })
    );
    
    const results = await Promise.all(promises);
    return results.flat();
  }
  
  async fetchByPopularity(minPop, maxPop) {
    const query = `
      query ($page: Int, $popularityMin: Int, $popularityMax: Int) {
        Page(page: $page, perPage: 50) {
          media(type: ANIME, popularity_greater: $popularityMin, popularity_lesser: $popularityMax, sort: POPULARITY_DESC) {
            id
            title { romaji english }
            popularity
            characters(sort: FAVOURITES_DESC, perPage: 25) {
              nodes {
                id
                name { full native }
                image { large medium }
                favourites
                gender
                description
              }
            }
          }
        }
      }
    `;
    
    const pagePromises = [];
    for (let page = 1; page <= 5; page++) {
      pagePromises.push(
        fetch(this.baseUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query,
            variables: { page, popularityMin: minPop, popularityMax: maxPop }
          })
        })
        .then(async res => {
          if (!res.ok) return [];
          const data = await res.json();
          const mediaList = data?.data?.Page?.media || [];
          const chars = [];
          
          for (const media of mediaList) {
            const animeName = media.title?.english || media.title?.romaji || 'Unknown';
            const animePopularity = media.popularity || 0;
            
            for (const char of media.characters?.nodes || []) {
              if (!char.image?.large && !char.image?.medium) continue;
              
              chars.push({
                id: char.id,
                name: char.name?.full || char.name?.native || 'Unknown',
                anime: animeName,
                anime_popularity: animePopularity,
                image_url: char.image?.large || char.image?.medium,
                gender: char.gender || 'Unknown',
                favorites: char.favourites || 0,
                description: this.cleanDescription(char.description),
                api_source: 'AniList'
              });
            }
          }
          return chars;
        })
        .catch(() => [])
      );
    }
    
    const results = await Promise.all(pagePromises);
    return results.flat();
  }
  
  cleanDescription(desc) {
    if (!desc) return '';
    return desc
      .replace(/<[^>]*>/g, '')
      .replace(/~!.*?!~/gs, '')
      .replace(/\n+/g, ' ')
      .trim()
      .slice(0, 300);
  }
  
}

module.exports = AniListProvider;
