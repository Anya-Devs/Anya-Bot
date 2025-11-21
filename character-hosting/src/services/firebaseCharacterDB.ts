/**
 * Firebase Character Database
 * NO STATIC DATA - All characters stored in Firebase Firestore
 */

import { Character } from '../types/character';
import { getCharacterImages } from './animeImageAPI';

// Firebase configuration
const FIREBASE_CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

// Firestore REST API endpoints
const FIRESTORE_BASE = `https://firestore.googleapis.com/v1/projects/${FIREBASE_CONFIG.projectId}/databases/(default)/documents`;

/**
 * Fetch all characters from Firestore
 */
export async function fetchCharactersFromFirestore(): Promise<Character[]> {
  try {
    const response = await fetch(`${FIRESTORE_BASE}/characters`);
    
    if (!response.ok) {
      console.warn('[Firestore] Failed to fetch characters, database may be empty');
      return [];
    }
    
    const data = await response.json();
    
    if (!data.documents || data.documents.length === 0) {
      console.log('[Firestore] No characters found in database');
      return [];
    }
    
    // Transform Firestore documents to Character objects
    return data.documents.map((doc: any) => ({
      id: doc.name.split('/').pop(),
      ...firestoreToCharacter(doc.fields)
    }));
  } catch (error) {
    console.error('[Firestore] Error fetching characters:', error);
    return [];
  }
}

/**
 * Add character to Firestore
 */
export async function addCharacterToFirestore(characterData: Omit<Character, 'id' | 'images' | 'imageCount' | 'createdAt' | 'updatedAt'>): Promise<Character> {
  const id = generateId(characterData.name, characterData.series);
  
  // Check if character already exists using REST API
  try {
    const checkResponse = await fetch(`${FIRESTORE_BASE}/characters/${id}`);
    if (checkResponse.ok) {
      const existingData = await checkResponse.json();
      if (existingData.fields) {
        console.log(`[Firestore] Character already exists: ${characterData.name}`);
        // Convert Firestore format back to Character
        const existingChar: Character = {
          id,
          name: existingData.fields.name.stringValue,
          series: existingData.fields.series.stringValue,
          description: existingData.fields.description.stringValue,
          images: existingData.fields.images.arrayValue.values.map((v: any) => v.stringValue),
          imageCount: existingData.fields.imageCount.integerValue,
          rarity: existingData.fields.rarity.stringValue as any,
          role: existingData.fields.role.arrayValue.values.map((v: any) => v.stringValue),
          affiliation: existingData.fields.affiliation.arrayValue.values.map((v: any) => v.stringValue),
          appearance: existingData.fields.appearance.arrayValue.values.map((v: any) => v.stringValue),
          voiceActors: {},
          aliases: existingData.fields.aliases.arrayValue.values.map((v: any) => v.stringValue),
          tags: existingData.fields.tags.arrayValue.values.map((v: any) => v.stringValue),
          createdAt: existingData.fields.createdAt.stringValue,
          updatedAt: existingData.fields.updatedAt.stringValue
        };
        return existingChar;
      }
    }
  } catch (error) {
    // Character doesn't exist, continue with adding
  }
  
  console.log(`[Firestore] Adding character: ${characterData.name}`);
  
  // Fetch images from anime APIs
  const images = await getCharacterImages(characterData.name, characterData.series, 10);
  
  const character: Character = {
    id,
    ...characterData,
    images,
    imageCount: images.length,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
  
  // Convert to Firestore format
  const firestoreDoc = characterToFirestore(character);
  
  // Save to Firestore
  const response = await fetch(`${FIRESTORE_BASE}/characters/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields: firestoreDoc })
  });
  
  if (!response.ok) {
    throw new Error('Failed to save character to Firestore');
  }
  
  console.log(`[Firestore] Character added: ${character.name} with ${images.length} images`);
  
  return character;
}

/**
 * Update character in Firestore
 */
export async function updateCharacterInFirestore(id: string, updates: Partial<Character>): Promise<void> {
  const firestoreDoc = characterToFirestore(updates as Character);
  
  await fetch(`${FIRESTORE_BASE}/characters/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fields: firestoreDoc })
  });
}

/**
 * Delete character from Firestore
 */
export async function deleteCharacterFromFirestore(id: string): Promise<void> {
  await fetch(`${FIRESTORE_BASE}/characters/${id}`, {
    method: 'DELETE'
  });
}

/**
 * Search characters in Firestore
 */
export async function searchCharactersInFirestore(query: string): Promise<Character[]> {
  const allCharacters = await fetchCharactersFromFirestore();
  const lowerQuery = query.toLowerCase();
  
  return allCharacters.filter(char =>
    char.name.toLowerCase().includes(lowerQuery) ||
    char.series.toLowerCase().includes(lowerQuery) ||
    char.aliases.some(a => a.toLowerCase().includes(lowerQuery))
  );
}

/**
 * Convert Character to Firestore format
 */
function characterToFirestore(character: Partial<Character>): any {
  const fields: any = {};
  
  if (character.name) fields.name = { stringValue: character.name };
  if (character.series) fields.series = { stringValue: character.series };
  if (character.description) fields.description = { stringValue: character.description };
  if (character.rarity) fields.rarity = { stringValue: character.rarity };
  if (character.createdAt) fields.createdAt = { stringValue: character.createdAt };
  if (character.updatedAt) fields.updatedAt = { stringValue: character.updatedAt };
  if (character.imageCount !== undefined) fields.imageCount = { integerValue: character.imageCount };
  
  if (character.aliases) {
    fields.aliases = {
      arrayValue: {
        values: character.aliases.map(a => ({ stringValue: a }))
      }
    };
  }
  
  if (character.tags) {
    fields.tags = {
      arrayValue: {
        values: character.tags.map(t => ({ stringValue: t }))
      }
    };
  }
  
  if (character.images) {
    fields.images = {
      arrayValue: {
        values: character.images.map(i => ({ stringValue: i }))
      }
    };
  }
  
  if (character.role) {
    fields.role = {
      arrayValue: {
        values: character.role.map(r => ({ stringValue: r }))
      }
    };
  }
  
  if (character.affiliation) {
    fields.affiliation = {
      arrayValue: {
        values: character.affiliation.map(a => ({ stringValue: a }))
      }
    };
  }
  
  if (character.voiceActors) {
    fields.voiceActors = {
      mapValue: {
        fields: {
          english: { stringValue: character.voiceActors.english || '' },
          japanese: { stringValue: character.voiceActors.japanese || '' }
        }
      }
    };
  }
  
  return fields;
}

/**
 * Convert Firestore document to Character
 */
function firestoreToCharacter(fields: any): Omit<Character, 'id'> {
  return {
    name: fields.name?.stringValue || '',
    series: fields.series?.stringValue || '',
    description: fields.description?.stringValue || '',
    rarity: (fields.rarity?.stringValue || 'C') as 'C' | 'R' | 'SR' | 'SSR',
    aliases: fields.aliases?.arrayValue?.values?.map((v: any) => v.stringValue) || [],
    tags: fields.tags?.arrayValue?.values?.map((v: any) => v.stringValue) || [],
    images: fields.images?.arrayValue?.values?.map((v: any) => v.stringValue) || [],
    role: fields.role?.arrayValue?.values?.map((v: any) => v.stringValue) || [],
    affiliation: fields.affiliation?.arrayValue?.values?.map((v: any) => v.stringValue) || [],
    imageCount: parseInt(fields.imageCount?.integerValue || '0'),
    voiceActors: {
      english: fields.voiceActors?.mapValue?.fields?.english?.stringValue,
      japanese: fields.voiceActors?.mapValue?.fields?.japanese?.stringValue
    },
    appearance: fields.appearance?.arrayValue?.values?.map((v: any) => v.stringValue) || [],
    createdAt: fields.createdAt?.stringValue || new Date().toISOString(),
    updatedAt: fields.updatedAt?.stringValue || new Date().toISOString()
  };
}

/**
 * Generate unique character ID
 */
function generateId(name: string, series: string): string {
  const slug = `${name}-${series}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return slug;
}

/**
 * Check if Firebase is configured
 */
export function isFirebaseConfigured(): boolean {
  return !!(
    FIREBASE_CONFIG.apiKey &&
    FIREBASE_CONFIG.projectId &&
    FIREBASE_CONFIG.apiKey !== 'undefined' &&
    FIREBASE_CONFIG.apiKey !== '' &&
    FIREBASE_CONFIG.projectId !== 'undefined' &&
    FIREBASE_CONFIG.projectId !== ''
  );
}
