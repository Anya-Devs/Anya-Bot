import { Character } from '../types/character';
import { getCharacterImages } from './animeImageAPI';

/**
 * Character Database Service
 * Manages character data with real-time updates
 */

// In-memory cache for development
// In production, use Firebase Realtime Database or Firestore
const characterCache = new Map<string, Character>();
const listeners = new Set<(characters: Character[]) => void>();

/**
 * Rarity weights for character gacha system
 */
export const RARITY_WEIGHTS = {
  'C': 50,   // Common - 50%
  'R': 30,   // Rare - 30%
  'SR': 15,  // Super Rare - 15%
  'SSR': 5   // Ultra Rare - 5%
};

/**
 * Generate character ID
 */
function generateCharacterId(name: string, series: string): string {
  // Remove timestamp to ensure consistent IDs for the same character
  const slug = `${name}-${series}`.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return slug;
}

/**
 * Assign rarity based on character popularity/importance
 */
function assignRarity(character: {
  name: string;
  role?: string[];
  tags?: string[];
}): 'C' | 'R' | 'SR' | 'SSR' {
  const roles = character.role || [];
  const tags = character.tags || [];
  
  // SSR - Main protagonists, extremely popular characters
  if (roles.includes('Main Character') || roles.includes('Protagonist')) {
    return 'SSR';
  }
  
  // SR - Important supporting characters
  if (roles.includes('Supporting Character') || tags.includes('Popular')) {
    return 'SR';
  }
  
  // R - Regular characters with some importance
  if (roles.length > 0) {
    return 'R';
  }
  
  // C - Common/background characters
  return 'C';
}

/**
 * Add new character to database using Multi-API system
 */
export async function addCharacter(characterData: any): Promise<Character> {
  // Check for duplicates first
  const existingId = generateCharacterId(characterData.name, characterData.series || 'Unknown');
  if (characterCache.has(existingId)) {
    console.log(`[DB] Character already exists: ${characterData.name}`);
    return characterCache.get(existingId)!;
  }
  
  // If only name provided, fetch from APIs
  if (characterData.name && !characterData.description) {
    console.log(`[DB] Fetching character data from APIs: ${characterData.name}`);
    const { searchCharacterAllAPIs } = await import('./multiAPICharacter');
    const character = await searchCharacterAllAPIs(characterData.name, characterData.series);
    
    if (!character) {
      throw new Error(`Character not found: ${characterData.name}`);
    }
    
    characterCache.set(character.id, character);
    notifyListeners();
    
    return character;
  }
  
  // Full character data provided
  const id = generateCharacterId(characterData.name, characterData.series || 'Unknown');
  
  // Auto-assign rarity if not provided
  const rarity = characterData.rarity || assignRarity(characterData);
  
  // Fetch images from anime APIs
  console.log(`[DB] Fetching images for ${characterData.name}...`);
  const images = await getCharacterImages(characterData.name, characterData.series || 'Unknown', 10);
  
  const character: Character = {
    id,
    name: characterData.name,
    series: characterData.series || 'Unknown',
    aliases: characterData.aliases || [],
    tags: characterData.tags || [],
    voiceActors: characterData.voiceActors || {},
    description: characterData.description || '',
    affiliation: characterData.affiliation || [],
    role: characterData.role || [],
    appearance: characterData.appearance || [],
    rarity,
    images,
    imageCount: images.length,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
  
  characterCache.set(id, character);
  notifyListeners();
  
  console.log(`[DB] Added character: ${character.name} (${character.rarity}) with ${images.length} images`);
  
  return character;
}

/**
 * Get all characters
 */
export async function getAllCharacters(): Promise<Character[]> {
  return Array.from(characterCache.values());
}

/**
 * Get character by ID
 */
export async function getCharacterById(id: string): Promise<Character | null> {
  return characterCache.get(id) || null;
}

/**
 * Update character
 */
export async function updateCharacter(id: string, updates: Partial<Character>): Promise<Character | null> {
  const character = characterCache.get(id);
  if (!character) return null;
  
  const updated = {
    ...character,
    ...updates,
    updatedAt: new Date().toISOString()
  };
  
  characterCache.set(id, updated);
  notifyListeners();
  
  return updated;
}

/**
 * Delete character
 */
export async function deleteCharacter(id: string): Promise<boolean> {
  const deleted = characterCache.delete(id);
  if (deleted) {
    notifyListeners();
  }
  return deleted;
}

/**
 * Search characters
 */
export async function searchCharacters(query: string): Promise<Character[]> {
  const lowerQuery = query.toLowerCase();
  const all = await getAllCharacters();
  
  return all.filter(char =>
    char.name.toLowerCase().includes(lowerQuery) ||
    char.series.toLowerCase().includes(lowerQuery) ||
    char.aliases.some(a => a.toLowerCase().includes(lowerQuery)) ||
    char.tags.some(t => t.toLowerCase().includes(lowerQuery))
  );
}

/**
 * Filter by rarity
 */
export async function getCharactersByRarity(rarity: 'C' | 'R' | 'SR' | 'SSR'): Promise<Character[]> {
  const all = await getAllCharacters();
  return all.filter(char => char.rarity === rarity);
}

/**
 * Filter by series
 */
export async function getCharactersBySeries(series: string): Promise<Character[]> {
  const all = await getAllCharacters();
  return all.filter(char => char.series === series);
}

/**
 * Get random character for gacha (weighted by rarity)
 */
export async function getRandomCharacter(): Promise<Character | null> {
  const all = await getAllCharacters();
  if (all.length === 0) return null;
  
  // Calculate total weight
  const totalWeight = all.reduce((sum, char) => sum + RARITY_WEIGHTS[char.rarity], 0);
  
  // Random weighted selection
  let random = Math.random() * totalWeight;
  
  for (const char of all) {
    random -= RARITY_WEIGHTS[char.rarity];
    if (random <= 0) {
      return char;
    }
  }
  
  return all[0]; // Fallback
}

/**
 * Subscribe to character updates
 */
export function subscribeToCharacters(callback: (characters: Character[]) => void): () => void {
  listeners.add(callback);
  
  // Send initial data
  getAllCharacters().then(callback);
  
  // Return unsubscribe function
  return () => {
    listeners.delete(callback);
  };
}

/**
 * Notify all listeners of changes
 */
function notifyListeners() {
  getAllCharacters().then(characters => {
    listeners.forEach(callback => callback(characters));
  });
}

/**
 * Batch import characters
 */
export async function batchImportCharacters(charactersData: any[]): Promise<Character[]> {
  console.log(`[DB] Batch importing ${charactersData.length} characters...`);
  
  const imported: Character[] = [];
  
  for (const data of charactersData) {
    try {
      const character = await addCharacter(data);
      imported.push(character);
    } catch (error) {
      console.error(`Failed to import ${data.name}:`, error);
    }
  }
  
  console.log(`[DB] Successfully imported ${imported.length}/${charactersData.length} characters`);
  
  return imported;
}

// Track if we've already shown the Firebase warning
let firebaseWarningShown = false;

/**
 * Load ALL anime characters from AniList API (paginated)
 */
async function loadAllAnimeCharacters(): Promise<void> {
  try {
    console.log('[DB] 🔍 Fetching ALL anime characters from AniList, Jikan, and Kitsu APIs...');
    
    // Add initial delay to help with rate limiting
    console.log('[DB] Waiting 2 seconds before starting API requests...');
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const { getPopularCharacters } = await import('./anilistAPI');
    const { searchCharacterAllAPIs } = await import('./multiAPICharacter');
    
    // Fetch multiple pages to get more characters
    const pages = [1]; // Start with just 1 page for testing
    let totalProcessed = 0;
    
    for (const page of pages) {
      console.log(`[DB] Fetching page ${page}...`);
      const popularChars = await getPopularCharacters(page, 10); // Reduce to 10 characters per page
      
      if (popularChars.length === 0) break;
      
      // Process characters in batches of 10 to avoid overwhelming the APIs
      for (let i = 0; i < popularChars.length && i < 5; i++) { // Process only 5 characters per page
        const anilistChar = popularChars[i];
        try {
          const character = await searchCharacterAllAPIs(anilistChar.name.full);
          
          if (character) {
            // Check for duplicates before adding
            if (!characterCache.has(character.id)) {
              characterCache.set(character.id, character);
              totalProcessed++;
              
              if (totalProcessed % 10 === 0) {
                console.log(`[DB] Processed ${totalProcessed} characters...`);
                notifyListeners(); // Update UI periodically
              }
            } else {
              console.log(`[DB] Skipping duplicate character: ${character.name}`);
            }
          }
          
          // Rate limiting
          await new Promise(resolve => setTimeout(resolve, 1000));
        } catch (error) {
          console.error(`[DB] Failed to process ${anilistChar.name.full}:`, error);
        }
      }
    }
    
    console.log(`[DB] ✅ Successfully loaded ${totalProcessed} anime characters from APIs`);
    notifyListeners();
  } catch (error) {
    console.error('[DB] Failed to load anime characters:', error);
  }
}

/**
 * Initialize database from Firebase or load top anime characters
 */
export async function initializeDatabase(): Promise<void> {
  if (characterCache.size > 0) {
    return; // Already initialized
  }
  
  try {
    // Try to load from Firebase first
    const { fetchCharactersFromFirestore, isFirebaseConfigured } = await import('./firebaseCharacterDB');
    
    if (!isFirebaseConfigured()) {
      // Only show warning once
      if (!firebaseWarningShown) {
        console.log('[DB] ℹ️ Firebase not configured - Loading top anime characters from APIs');
        firebaseWarningShown = true;
      }
      
      // Load ALL anime characters from APIs instead
      await loadAllAnimeCharacters();
      return;
    }
    
    const characters = await fetchCharactersFromFirestore();
    
    if (characters.length === 0) {
      console.log('[DB] No characters in Firebase - Loading ALL anime characters from APIs');
      await loadAllAnimeCharacters();
      return;
    }
    
    // Load into cache
    characters.forEach(char => {
      characterCache.set(char.id, char);
    });
    
    console.log(`[DB] ✅ Loaded ${characters.length} characters from Firebase`);
    notifyListeners();
  } catch (error) {
    if (!firebaseWarningShown) {
      console.log('[DB] ℹ️ Firebase not available - Loading ALL anime characters from APIs');
      firebaseWarningShown = true;
    }
    
    // Fallback to loading from APIs
    await loadAllAnimeCharacters();
  }
}

/**
 * Search characters from API (live search)
 */
export async function searchCharactersFromAPI(query: string): Promise<Character[]> {
  if (!query || query.length < 2) return [];
  
  try {
    console.log(`[DB] 🔍 Searching API for: ${query}`);
    const { searchCharacterAllAPIs } = await import('./multiAPICharacter');
    
    const character = await searchCharacterAllAPIs(query);
    
    if (character) {
      // Check for duplicates before adding
      if (!characterCache.has(character.id)) {
        // Add to cache
        characterCache.set(character.id, character);
        notifyListeners();
      } else {
        console.log(`[DB] Character already exists: ${character.name}`);
      }
      return [character];
    }
    
    return [];
  } catch (error) {
    console.error('[DB] API search failed:', error);
    return [];
  }
}
