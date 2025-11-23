import imageHash from 'image-hash';
import axios from 'axios';
import sharp from 'sharp';
import { promisify } from 'util';

const imageHashAsync = promisify(imageHash);

/**
 * Image deduplication using perceptual hashing
 */
export class ImageDeduplicator {
  constructor() {
    this.similarityThreshold = parseFloat(process.env.IMAGE_SIMILARITY_THRESHOLD) || 0.95;
    this.seenHashes = new Map();
  }

  /**
   * Remove duplicate images from array
   */
  async removeDuplicates(images) {
    const uniqueImages = [];
    const processedHashes = new Set();
    
    for (let i = 0; i < images.length; i++) {
      const image = images[i];
      
      try {
        // Download image
        const imageBuffer = await this.downloadImage(image.url);
        
        if (!imageBuffer) continue;
        
        // Validate image
        const metadata = await sharp(imageBuffer).metadata();
        
        // Skip images that are too small
        if (metadata.width < 200 || metadata.height < 200) {
          continue;
        }
        
        // Calculate perceptual hash
        const hash = await this.calculateHash(imageBuffer);
        
        // Check for duplicates
        if (!this.isDuplicate(hash, processedHashes)) {
          processedHashes.add(hash);
          uniqueImages.push({
            ...image,
            hash,
            buffer: imageBuffer,
            metadata
          });
        }
        
      } catch (error) {
        console.warn(`    ⚠️  Failed to process image ${i + 1}:`, error.message);
      }
    }
    
    return uniqueImages;
  }

  /**
   * Download image from URL
   */
  async downloadImage(url) {
    try {
      const response = await axios.get(url, {
        responseType: 'arraybuffer',
        timeout: 10000,
        maxContentLength: 10 * 1024 * 1024, // 10MB max
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
      });
      
      return Buffer.from(response.data);
    } catch (error) {
      console.warn(`Failed to download image from ${url}:`, error.message);
      return null;
    }
  }

  /**
   * Calculate perceptual hash of image
   */
  async calculateHash(imageBuffer) {
    try {
      // Resize to standard size for consistent hashing
      const resized = await sharp(imageBuffer)
        .resize(256, 256, { fit: 'cover' })
        .toBuffer();
      
      // Calculate hash using difference hash algorithm
      return await this.dhash(resized);
    } catch (error) {
      throw new Error(`Hash calculation failed: ${error.message}`);
    }
  }

  /**
   * Difference hash algorithm
   */
  async dhash(imageBuffer) {
    const { data, info } = await sharp(imageBuffer)
      .greyscale()
      .resize(9, 8, { fit: 'fill' })
      .raw()
      .toBuffer({ resolveWithObject: true });
    
    let hash = '';
    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 8; col++) {
        const left = data[row * 9 + col];
        const right = data[row * 9 + col + 1];
        hash += left < right ? '1' : '0';
      }
    }
    
    return hash;
  }

  /**
   * Check if hash is duplicate
   */
  isDuplicate(hash, existingHashes) {
    for (const existingHash of existingHashes) {
      const similarity = this.calculateSimilarity(hash, existingHash);
      if (similarity >= this.similarityThreshold) {
        return true;
      }
    }
    return false;
  }

  /**
   * Calculate similarity between two hashes (Hamming distance)
   */
  calculateSimilarity(hash1, hash2) {
    if (hash1.length !== hash2.length) return 0;
    
    let matches = 0;
    for (let i = 0; i < hash1.length; i++) {
      if (hash1[i] === hash2[i]) matches++;
    }
    
    return matches / hash1.length;
  }

  /**
   * Reset seen hashes (for new character)
   */
  reset() {
    this.seenHashes.clear();
  }
}
