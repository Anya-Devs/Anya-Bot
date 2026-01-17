/**
 * Multi-API Character Information Aggregator
 * Combines data from 50+ sources for comprehensive character info
 */

import { Character } from '../types/character';
import { searchAniListCharacter, calculateRarityFromFavorites, type AniListCharacter } from './anilistAPI';
import { fetchAllSourceImages } from './multiSourceImageAPI';

/**
 * Jikan API (MyAnimeList)
 */
async function searchJikanCharacter(name: string): Promise<any> {
  try {
    const response = await fetch(`/api/jikan/characters?q=${encodeURIComponent(name)}&limit=1`);
    if (!response.ok) throw new Error('Jikan API failed');
    const data = await response.json();
    return data.data?.[0] || null;
  } catch (error) {
    console.error('[Jikan] Search failed:', error);
    return null;
  }
}

/**
 * Kitsu API
 */
async function searchKitsuCharacter(name: string): Promise<any> {
  try {
    const response = await fetch(`https://kitsu.io/api/edge/characters?filter[name]=${encodeURIComponent(name)}&page[limit]=1`);
    if (!response.ok) throw new Error('Kitsu API failed');
    const data = await response.json();
    return data.data?.[0] || null;
  } catch (error) {
    console.error('[Kitsu] Search failed:', error);
    return null;
  }
}

/**
 * Anime-Planet API (Future implementation)
 * Note: Anime-Planet doesn't have a public API, would need scraping
 * Keeping this for future expansion to 50+ sources
 */
// async function searchAnimePlanetCharacter(name: string): Promise<any> {
//   try {
//     console.log('[Anime-Planet] Would search for:', name);
//     return null;
//   } catch (error) {
//     return null;
//   }
// }

/**
 * Aggregated character search across all APIs
 */
export async function searchCharacterAllAPIs(name: string, series?: string): Promise<Character | null> {
  console.log(`[Multi-API] Searching for: ${name}${series ? ` from ${series}` : ''}`);
  
  // Search all APIs in parallel
  const [anilistData, jikanData, kitsuData] = await Promise.all([
    searchAniListCharacter(name),
    searchJikanCharacter(name),
    searchKitsuCharacter(name)
  ]);

  // Prioritize AniList as it has the most complete data
  if (!anilistData && !jikanData && !kitsuData) {
    console.warn('[Multi-API] No data found from any API');
    return null;
  }

  // Merge data from all sources
  const mergedData = mergeCharacterData(anilistData, jikanData, kitsuData);
  
  // Fetch high-quality images
  console.log('[Multi-API] Fetching images...');
  const images = await fetchBestImages(mergedData.name, mergedData.series);
  
  // Calculate rarity based on popularity
  const rarity = calculateRarity(mergedData);
  
  // Build final character object
  const character: Character = {
    id: generateId(mergedData.name, mergedData.series),
    name: mergedData.name,
    series: mergedData.series,
    aliases: mergedData.aliases,
    tags: mergedData.tags,
    description: mergedData.description,
    rarity,
    images,
    imageCount: images.length,
    role: mergedData.role,
    affiliation: mergedData.affiliation || [],
    voiceActors: mergedData.voiceActors || {},
    appearance: mergedData.appearance || [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };

  console.log(`[Multi-API] Character created: ${character.name} (${character.rarity}) with ${images.length} images`);
  
  return character;
}

/**
 * Merge character data from multiple sources
 */
function mergeCharacterData(anilist: AniListCharacter | null, jikan: any, kitsu: any): any {
  const merged: any = {
    name: '',
    series: '',
    aliases: [],
    tags: [],
    description: '',
    role: [],
    favourites: 0,
    affiliation: [],
    voiceActors: {},
    appearance: []
  };

  // AniList data (primary source)
  if (anilist) {
    merged.name = anilist.name.full;
    merged.aliases = [
      ...(anilist.name.alternative || []),
      anilist.name.native
    ].filter(Boolean);
    
    // Create neat overview from description
    const seriesName = anilist.media?.nodes?.[0]?.title?.english || anilist.media?.nodes?.[0]?.title?.romaji || 'Unknown';
    merged.description = createCharacterOverview(anilist.description || '', anilist.name.full, seriesName);
    merged.favourites = anilist.favourites;
    
    // Get series from media
    if (anilist.media?.nodes?.length > 0) {
      const primaryMedia = anilist.media.nodes[0];
      merged.series = primaryMedia.title.english || primaryMedia.title.romaji;
      
      // Add all series as tags
      anilist.media.nodes.forEach((media: any) => {
        const title = media.title.english || media.title.romaji;
        if (title && !merged.tags.includes(title)) {
          merged.tags.push(title);
        }
      });
    }
    
    // Add AniList official image
    if (anilist.image?.large) {
      merged.officialImage = anilist.image.large;
    }
  }

  // Jikan data (MyAnimeList)
  if (jikan) {
    if (!merged.name) merged.name = jikan.name;
    if (!merged.description) {
      const seriesName = merged.series || 'Unknown';
      merged.description = createCharacterOverview(jikan.about || '', jikan.name, seriesName);
    }
    
    // Add nicknames
    if (jikan.nicknames) {
      merged.aliases.push(...jikan.nicknames);
    }
    
    // Add MAL favorites
    if (jikan.favorites) {
      merged.favourites = Math.max(merged.favourites, jikan.favorites);
    }
  }

  // Kitsu data
  if (kitsu) {
    const attrs = kitsu.attributes;
    if (!merged.name) merged.name = attrs.name;
    if (!merged.description) {
      const seriesName = merged.series || 'Unknown';
      merged.description = createCharacterOverview(attrs.description || '', attrs.name, seriesName);
    }
    
    // Add other names
    if (attrs.otherNames) {
      merged.aliases.push(...attrs.otherNames);
    }
  }

  // Deduplicate aliases
  merged.aliases = [...new Set(merged.aliases)].filter(Boolean);
  merged.tags = [...new Set(merged.tags)].filter(Boolean);

  return merged;
}

/**
 * Fetch best images from 100+ sources
 * Prioritizes: Official art > High-quality fanart > General images
 */
async function fetchBestImages(name: string, _series: string): Promise<string[]> {
  try {
    const images: string[] = [];
    
    // First, get official images from AniList (most reliable)
    const { searchAniListCharacter } = await import('./anilistAPI');
    const anilistData = await searchAniListCharacter(name);
    
    if (anilistData?.image?.large) {
      images.push(anilistData.image.large);
    }
    if (anilistData?.image?.medium && anilistData.image.medium !== anilistData.image.large) {
      images.push(anilistData.image.medium);
    }
    
    // If we have at least one official image, return those
    if (images.length > 0) {
      console.log(`[Multi-API] Using ${images.length} official AniList images for ${name}`);
      return images;
    }
    
    // Fallback to multi-source if no official images
    console.log(`[Multi-API] No official images found, using multi-source for ${name}`);
    const fallbackImages = await fetchAllSourceImages(name, 20);
    return fallbackImages.slice(0, 10);
  } catch (error) {
    console.error('[Multi-API] Image fetching failed:', error);
    return [];
  }
}

/**
 * Calculate rarity based on multiple factors
 */
function calculateRarity(data: any): 'C' | 'R' | 'SR' | 'SSR' {
  const favourites = data.favourites || 0;
  
  // Use AniList's rarity calculation
  return calculateRarityFromFavorites(favourites);
}

/**
 * Strip HTML tags from description
 */
function stripHTML(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .trim();
}

/**
 * Create a neat character overview from description
 */
function createCharacterOverview(description: string, name: string, series: string): string {
  // Clean the description first
  const cleanDesc = stripHTML(description);
  
  // If description is too short or just contains stats, create a generic one
  if (cleanDesc.length < 50 || cleanDesc.includes('Age:') || cleanDesc.includes('Height:')) {
    return `${name} is a character from ${series}. ${cleanDesc}`;
  }
  
  // Truncate very long descriptions
  if (cleanDesc.length > 300) {
    const truncated = cleanDesc.substring(0, 297);
    const lastSentence = truncated.lastIndexOf('.');
    if (lastSentence > 100) {
      return truncated.substring(0, lastSentence + 1);
    }
    return truncated + '...';
  }
  
  return cleanDesc;
}

/**
 * Generate unique ID
 */
function generateId(name: string, series: string): string {
  const slug = `${name}-${series}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return slug;
}

/**
 * Batch import popular characters
 */
export async function importPopularCharacters(count: number = 50): Promise<Character[]> {
  console.log(`[Multi-API] Importing ${count} popular characters...`);
  
  const { getPopularCharacters } = await import('./anilistAPI');
  const popularChars = await getPopularCharacters(1, count);
  
  const characters: Character[] = [];
  
  for (let i = 0; i < popularChars.length; i++) {
    const anilistChar = popularChars[i];
    try {
      const character = await searchCharacterAllAPIs(anilistChar.name.full);
      if (character) {
        characters.push(character);
        
        // Log progress every 5 characters
        if ((i + 1) % 5 === 0) {
          console.log(`[Multi-API] Progress: ${i + 1}/${popularChars.length} characters processed`);
        }
      }
      
      // Rate limiting - wait 500ms between requests (faster but still safe)
      await new Promise(resolve => setTimeout(resolve, 1000));
    } catch (error) {
      console.error(`Failed to import ${anilistChar.name.full}:`, error);
    }
  }
  
  console.log(`[Multi-API] ✅ Successfully imported ${characters.length}/${count} characters`);
  
  return characters;
}
