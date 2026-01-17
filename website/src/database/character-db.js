import { adminDb } from '../firebase/config.js';
import { v4 as uuidv4 } from 'uuid';

/**
 * Character database operations
 */
export class CharacterDatabase {
  constructor() {
    this.charactersCollection = adminDb.collection('characters');
    this.seriesCollection = adminDb.collection('series');
  }

  /**
   * Save character to database
   */
  async saveCharacter(characterData) {
    const characterId = characterData.id || this.generateCharacterId(characterData.name);
    
    const characterDoc = {
      id: characterId,
      name: characterData.name,
      series: characterData.series,
      aliases: characterData.aliases || [],
      tags: characterData.tags || [],
      voiceActors: characterData.voiceActors || {},
      rarity: characterData.rarity || 'R',
      images: characterData.images || [],
      imageCount: characterData.images?.length || 0,
      description: characterData.description || '',
      affiliation: characterData.affiliation || [],
      role: characterData.role || [],
      appearance: this.extractAppearanceTags(characterData.tags),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      scrapedAt: characterData.scrapedAt || new Date().toISOString()
    };
    
    await this.charactersCollection.doc(characterId).set(characterDoc);
    
    // Update series collection
    await this.updateSeriesData(characterData.series, characterId);
    
    console.log(`    ✓ Saved character: ${characterId}`);
    return characterId;
  }

  /**
   * Get character by ID
   */
  async getCharacter(characterId) {
    const doc = await this.charactersCollection.doc(characterId).get();
    return doc.exists ? doc.data() : null;
  }

  /**
   * Search characters
   */
  async searchCharacters(query, options = {}) {
    const {
      series = null,
      tags = [],
      rarity = null,
      limit = 50
    } = options;
    
    let queryRef = this.charactersCollection;
    
    if (series) {
      queryRef = queryRef.where('series', '==', series);
    }
    
    if (tags.length > 0) {
      queryRef = queryRef.where('tags', 'array-contains-any', tags);
    }
    
    if (rarity) {
      queryRef = queryRef.where('rarity', '==', rarity);
    }
    
    queryRef = queryRef.limit(limit);
    
    const snapshot = await queryRef.get();
    return snapshot.docs.map(doc => doc.data());
  }

  /**
   * Get random character for gacha
   */
  async getRandomCharacter(rarity = null) {
    let queryRef = this.charactersCollection;
    
    if (rarity) {
      queryRef = queryRef.where('rarity', '==', rarity);
    }
    
    const snapshot = await queryRef.get();
    
    if (snapshot.empty) return null;
    
    const randomIndex = Math.floor(Math.random() * snapshot.size);
    return snapshot.docs[randomIndex].data();
  }

  /**
   * Get random character image
   */
  async getRandomCharacterImage(characterId) {
    const character = await this.getCharacter(characterId);
    
    if (!character || !character.images || character.images.length === 0) {
      return null;
    }
    
    const randomIndex = Math.floor(Math.random() * character.images.length);
    return character.images[randomIndex];
  }

  /**
   * Update series data
   */
  async updateSeriesData(seriesName, characterId) {
    const seriesId = this.slugify(seriesName);
    const seriesRef = this.seriesCollection.doc(seriesId);
    
    const seriesDoc = await seriesRef.get();
    
    if (seriesDoc.exists) {
      // Add character to existing series
      await seriesRef.update({
        characters: adminDb.FieldValue.arrayUnion(characterId),
        characterCount: adminDb.FieldValue.increment(1),
        updatedAt: new Date().toISOString()
      });
    } else {
      // Create new series
      await seriesRef.set({
        id: seriesId,
        name: seriesName,
        characters: [characterId],
        characterCount: 1,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });
    }
  }

  /**
   * Get all series
   */
  async getAllSeries() {
    const snapshot = await this.seriesCollection.orderBy('name').get();
    return snapshot.docs.map(doc => doc.data());
  }

  /**
   * Get characters by series
   */
  async getCharactersBySeries(seriesName) {
    const snapshot = await this.charactersCollection
      .where('series', '==', seriesName)
      .get();
    
    return snapshot.docs.map(doc => doc.data());
  }

  /**
   * Extract appearance tags from all tags
   */
  extractAppearanceTags(tags) {
    const appearanceKeywords = [
      'hair', 'eyes', 'dress', 'outfit', 'height',
      'child', 'adult', 'tall', 'short', 'color'
    ];
    
    return tags.filter(tag => 
      appearanceKeywords.some(keyword => 
        tag.toLowerCase().includes(keyword)
      )
    );
  }

  /**
   * Generate character ID from name
   */
  generateCharacterId(name) {
    const slug = this.slugify(name);
    const shortId = uuidv4().split('-')[0];
    return `${slug}-${shortId}`;
  }

  /**
   * Convert string to slug
   */
  slugify(text) {
    return text
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .trim();
  }

  /**
   * Batch import characters
   */
  async batchImportCharacters(charactersData) {
    const batch = adminDb.batch();
    const characterIds = [];
    
    for (const characterData of charactersData) {
      const characterId = this.generateCharacterId(characterData.name);
      const characterRef = this.charactersCollection.doc(characterId);
      
      batch.set(characterRef, {
        ...characterData,
        id: characterId,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });
      
      characterIds.push(characterId);
    }
    
    await batch.commit();
    console.log(`Batch imported ${characterIds.length} characters`);
    
    return characterIds;
  }
}
