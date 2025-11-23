// Remove unused import
// import { Character } from '../types/character';

interface ScraperConfig {
  maxImages: number;
  searchEngines: string[];
  imageMinWidth: number;
  imageMinHeight: number;
}

const DEFAULT_CONFIG: ScraperConfig = {
  maxImages: 50,
  searchEngines: ['google', 'bing'],
  imageMinWidth: 400,
  imageMinHeight: 400
};

/**
 * Image scraper service for character images
 * Uses multiple search engines to find high-quality character images
 */
export class ImageScraperService {
  private config: ScraperConfig;
  private scrapedImages: Map<string, string[]> = new Map();

  constructor(config: Partial<ScraperConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Scrape images for a character
   */
  async scrapeCharacterImages(character: {
    name: string;
    series: string;
    aliases?: string[];
  }): Promise<string[]> {
    const cacheKey = `${character.name}-${character.series}`;
    
    // Check cache first
    if (this.scrapedImages.has(cacheKey)) {
      return this.scrapedImages.get(cacheKey)!;
    }

    const images: string[] = [];
    const searchQueries = this.buildSearchQueries(character);

    for (const query of searchQueries) {
      try {
        const results = await this.searchImages(query);
        images.push(...results);
        
        if (images.length >= this.config.maxImages) {
          break;
        }
      } catch (error) {
        console.warn(`Failed to scrape images for query: ${query}`, error);
      }
    }

    // Deduplicate images
    const uniqueImages = this.deduplicateImages(images);
    const limitedImages = uniqueImages.slice(0, this.config.maxImages);

    // Cache results
    this.scrapedImages.set(cacheKey, limitedImages);

    return limitedImages;
  }

  /**
   * Build search queries from character data
   */
  private buildSearchQueries(character: {
    name: string;
    series: string;
    aliases?: string[];
  }): string[] {
    const queries: string[] = [];

    // Primary query
    queries.push(`${character.name} ${character.series} anime`);
    queries.push(`${character.name} ${character.series} official art`);
    queries.push(`${character.name} ${character.series} fanart`);

    // Alias queries
    if (character.aliases && character.aliases.length > 0) {
      character.aliases.slice(0, 2).forEach(alias => {
        queries.push(`${alias} ${character.series} anime`);
      });
    }

    return queries;
  }

  /**
   * Search for images using various sources
   * In production, this would use actual image search APIs
   */
  private async searchImages(query: string): Promise<string[]> {
    // For now, return placeholder images
    // In production, integrate with:
    // - Google Custom Search API
    // - Bing Image Search API
    // - Danbooru/Gelbooru APIs
    // - Pixiv API
    
    console.log(`[Scraper] Searching for: ${query}`);
    
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 100));

    // Return placeholder images
    // In production, replace with actual API calls
    return [];
  }

  /**
   * Deduplicate images by URL
   */
  private deduplicateImages(images: string[]): string[] {
    return Array.from(new Set(images));
  }

  /**
      };
      
      img.onerror = () => resolve(false);
      img.src = url;
    });
  }

  /**
   * Clear cache
   */
  clearCache() {
    this.scrapedImages.clear();
  }
}

/**
 * Image deduplicator using perceptual hashing
 * Detects similar/duplicate images
 */
export class ImageDeduplicator {
  // Remove unused property
  // private hashes: Map<string, string> = new Map();

  /**
   * Remove duplicate images from array
   */
  async removeDuplicates(imageUrls: string[]): Promise<string[]> {
    const unique: string[] = [];
    const seenHashes = new Set<string>();

    for (const url of imageUrls) {
      try {
        const hash = await this.computeHash(url);
        
        if (!seenHashes.has(hash)) {
          seenHashes.add(hash);
          unique.push(url);
        }
      } catch (error) {
        // If hashing fails, include the image anyway
        unique.push(url);
      }
    }

    return unique;
  }

  /**
   * Compute perceptual hash of image
   * In production, use a proper image hashing library
   */
  private async computeHash(url: string): Promise<string> {
    // Simple hash based on URL for now
    // In production, implement actual perceptual hashing
    return url;
  }
}

// Export singleton instance
export const imageScraper = new ImageScraperService();
export const imageDeduplicator = new ImageDeduplicator();
