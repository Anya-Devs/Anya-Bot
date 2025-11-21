import puppeteer from 'puppeteer';
import { ImageScraper } from './image-scraper.js';
import { ImageDeduplicator } from './deduplicator.js';
import { FirebaseUploader } from '../firebase/uploader.js';
import { CharacterDatabase } from '../database/character-db.js';
import dotenv from 'dotenv';

dotenv.config();

/**
 * Main scraper orchestrator
 */
export class CharacterScraper {
  constructor() {
    this.maxImagesPerCharacter = parseInt(process.env.MAX_IMAGES_PER_CHARACTER) || 100;
    this.scrapeDelay = parseInt(process.env.SCRAPE_DELAY_MS) || 1000;
    this.imageScraper = new ImageScraper();
    this.deduplicator = new ImageDeduplicator();
    this.uploader = new FirebaseUploader();
    this.database = new CharacterDatabase();
  }

  /**
   * Scrape images for a character
   * @param {Object} characterData - Character information
   * @param {string} characterData.name - Character name
   * @param {string} characterData.series - Series name
   * @param {string[]} characterData.aliases - Character aliases
   * @param {string[]} characterData.tags - Character tags
   */
  async scrapeCharacter(characterData) {
    console.log(`\n🔍 Scraping images for: ${characterData.name} (${characterData.series})`);
    
    const browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
      // Search queries combining name, series, and aliases
      const searchQueries = this.buildSearchQueries(characterData);
      
      let allImages = [];
      
      for (const query of searchQueries) {
        console.log(`  📸 Searching: "${query}"`);
        
        const images = await this.imageScraper.searchImages(browser, query);
        allImages.push(...images);
        
        // Delay between searches
        await this.delay(this.scrapeDelay);
        
        if (allImages.length >= this.maxImagesPerCharacter * 2) {
          break; // Got enough candidates
        }
      }

      console.log(`  ✓ Found ${allImages.length} candidate images`);

      // Deduplicate images
      console.log(`  🔄 Deduplicating images...`);
      const uniqueImages = await this.deduplicator.removeDuplicates(allImages);
      console.log(`  ✓ ${uniqueImages.length} unique images after deduplication`);

      // Limit to max images
      const finalImages = uniqueImages.slice(0, this.maxImagesPerCharacter);

      // Upload to Firebase
      console.log(`  ☁️  Uploading ${finalImages.length} images to Firebase...`);
      const uploadedImages = await this.uploader.uploadCharacterImages(
        characterData.name,
        finalImages
      );

      // Save to database
      console.log(`  💾 Saving character data to database...`);
      const characterId = await this.database.saveCharacter({
        ...characterData,
        images: uploadedImages,
        imageCount: uploadedImages.length,
        scrapedAt: new Date().toISOString()
      });

      console.log(`  ✅ Successfully scraped character: ${characterId}`);
      
      return {
        characterId,
        imageCount: uploadedImages.length,
        images: uploadedImages
      };

    } catch (error) {
      console.error(`  ❌ Error scraping ${characterData.name}:`, error.message);
      throw error;
    } finally {
      await browser.close();
    }
  }

  /**
   * Build search queries from character data
   */
  buildSearchQueries(characterData) {
    const queries = [];
    
    // Primary query: character name + series
    queries.push(`${characterData.name} ${characterData.series} anime`);
    
    // Add aliases
    if (characterData.aliases && characterData.aliases.length > 0) {
      characterData.aliases.forEach(alias => {
        queries.push(`${alias} ${characterData.series}`);
      });
    }
    
    // Add specific tags for better results
    queries.push(`${characterData.name} ${characterData.series} fanart`);
    queries.push(`${characterData.name} ${characterData.series} official art`);
    
    return queries.slice(0, 5); // Limit to 5 queries
  }

  /**
   * Batch scrape multiple characters
   */
  async scrapeMultipleCharacters(charactersData) {
    const results = [];
    
    for (let i = 0; i < charactersData.length; i++) {
      const character = charactersData[i];
      console.log(`\n[${i + 1}/${charactersData.length}] Processing: ${character.name}`);
      
      try {
        const result = await this.scrapeCharacter(character);
        results.push({ success: true, ...result });
      } catch (error) {
        results.push({ 
          success: false, 
          name: character.name, 
          error: error.message 
        });
      }
      
      // Delay between characters
      await this.delay(this.scrapeDelay * 2);
    }
    
    return results;
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// CLI Usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const scraper = new CharacterScraper();
  
  // Example character data
  const exampleCharacter = {
    name: "Anya Forger",
    series: "Spy x Family",
    aliases: [
      "Subject 007",
      "Chihuahua Girl",
      "Ania Forger",
      "Anya Folger",
      "Starlight Anya",
      "Princess Anya"
    ],
    tags: [
      "Main Character",
      "Protagonist",
      "Eden Academy",
      "The Forger Family",
      "Ahoge",
      "Child-like",
      "Dress",
      "Green Eyes",
      "Hair Ornament",
      "Medium Length Hair",
      "Pink Hair"
    ],
    voiceActors: {
      english: "Megan Shipman",
      japanese: "Atsumi Tanezaki"
    },
    rarity: "SSR"
  };
  
  scraper.scrapeCharacter(exampleCharacter)
    .then(result => {
      console.log('\n✅ Scraping completed successfully!');
      console.log(JSON.stringify(result, null, 2));
    })
    .catch(error => {
      console.error('\n❌ Scraping failed:', error);
      process.exit(1);
    });
}
