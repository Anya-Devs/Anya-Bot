import { Character } from '../types/character';
import { getAllCharacters, initializeDatabase, searchCharactersFromAPI } from './characterDatabase';

// Initialize database on first load
let initialized = false;

export async function getCharacters(): Promise<Character[]> {
  if (!initialized) {
    await initializeDatabase();
    initialized = true;
  }
  
  return getAllCharacters();
}

/**
 * Search characters - searches local cache first, then API if not found
 */
export async function searchCharacters(query: string, characters: Character[]): Promise<Character[]> {
  const lowerQuery = query.toLowerCase().trim();
  
  // More flexible search - includes partial matches and fuzzy matching
  const localResults = characters.filter(char => {
    const nameMatch = char.name.toLowerCase().includes(lowerQuery);
    const seriesMatch = char.series.toLowerCase().includes(lowerQuery);
    const aliasMatch = char.aliases.some(alias => 
      alias.toLowerCase().includes(lowerQuery) || 
      lowerQuery.includes(alias.toLowerCase())
    );
    const tagMatch = char.tags.some(tag => 
      tag.toLowerCase().includes(lowerQuery) || 
      lowerQuery.includes(tag.toLowerCase())
    );
    
    // Also check if query contains parts of the name (fuzzy matching)
    const queryParts = lowerQuery.split(' ');
    const fuzzyMatch = queryParts.some(part => 
      part.length > 2 && char.name.toLowerCase().includes(part)
    );
    
    return nameMatch || seriesMatch || aliasMatch || tagMatch || fuzzyMatch;
  });
  
  // If we have local results, return them
  if (localResults.length > 0) {
    return localResults;
  }
  
  // If no local results and query is specific enough, search API
  if (query.length >= 3) {
    console.log('[Search] No local results, searching API...');
    const apiResults = await searchCharactersFromAPI(query);
    return apiResults;
  }
  
  return [];
}

export function filterByRarity(characters: Character[], rarity: string): Character[] {
  if (!rarity || rarity === 'all') return characters;
  return characters.filter(char => char.rarity === rarity);
}

export function filterBySeries(characters: Character[], series: string): Character[] {
  if (!series || series === 'all') return characters;
  return characters.filter(char => char.series === series);
}
