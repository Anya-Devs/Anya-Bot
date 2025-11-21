/**
 * AniList API Integration
 * Get character information, popularity, favorites
 */

interface AniListCharacter {
  id: number;
  name: {
    full: string;
    native: string;
    alternative: string[];
  };
  image: {
    large: string;
    medium: string;
  };
  description: string;
  favourites: number;
  siteUrl: string;
  media: {
    nodes: Array<{
      title: {
        romaji: string;
        english: string;
      };
      type: string;
    }>;
  };
}

const ANILIST_API = '/api/anilist';

/**
 * Search character on AniList
 */
export async function searchAniListCharacter(name: string): Promise<AniListCharacter | null> {
  const query = `
    query ($search: String) {
      Character(search: $search, sort: FAVOURITES_DESC) {
        id
        name {
          full
          native
          alternative
        }
        image {
          large
          medium
        }
        description
        favourites
        siteUrl
        media(sort: POPULARITY_DESC, perPage: 5) {
          nodes {
            title {
              romaji
              english
            }
            type
          }
        }
      }
    }
  `;

  try {
    const response = await fetch(ANILIST_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query,
        variables: { search: name }
      })
    });

    if (!response.ok) throw new Error('AniList API failed');

    const data = await response.json();
    return data.data?.Character || null;
  } catch (error) {
    console.error('[AniList] Search failed:', error);
    return null;
  }
}

/**
 * Get character by ID
 */
export async function getAniListCharacterById(id: number): Promise<AniListCharacter | null> {
  const query = `
    query ($id: Int) {
      Character(id: $id) {
        id
        name {
          full
          native
          alternative
        }
        image {
          large
          medium
        }
        description
        favourites
        siteUrl
        media(sort: POPULARITY_DESC, perPage: 10) {
          nodes {
            title {
              romaji
              english
            }
            type
            popularity
          }
        }
      }
    }
  `;

  try {
    const response = await fetch(ANILIST_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query,
        variables: { id }
      })
    });

    if (!response.ok) throw new Error('AniList API failed');

    const data = await response.json();
    return data.data?.Character || null;
  } catch (error) {
    console.error('[AniList] Get by ID failed:', error);
    return null;
  }
}

/**
 * Get popular characters
 */
export async function getPopularCharacters(page: number = 1, perPage: number = 50): Promise<AniListCharacter[]> {
  const query = `
    query ($page: Int, $perPage: Int) {
      Page(page: $page, perPage: $perPage) {
        characters(sort: FAVOURITES_DESC) {
          id
          name {
            full
            native
            alternative
          }
          image {
            large
            medium
          }
          description
          favourites
          siteUrl
          media(sort: POPULARITY_DESC, perPage: 3) {
            nodes {
              title {
                romaji
                english
              }
              type
            }
          }
        }
      }
    }
  `;

  try {
    const response = await fetch(ANILIST_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query,
        variables: { page, perPage }
      })
    });

    if (!response.ok) throw new Error('AniList API failed');

    const data = await response.json();
    return data.data?.Page?.characters || [];
  } catch (error) {
    console.error('[AniList] Get popular failed:', error);
    return [];
  }
}

/**
 * Calculate rarity based on favorites/popularity
 */
export function calculateRarityFromFavorites(favourites: number): 'C' | 'R' | 'SR' | 'SSR' {
  if (favourites >= 10000) return 'SSR';  // 10k+ favorites
  if (favourites >= 5000) return 'SR';    // 5k-10k favorites
  if (favourites >= 1000) return 'R';     // 1k-5k favorites
  return 'C';                              // < 1k favorites
}

export type { AniListCharacter };
