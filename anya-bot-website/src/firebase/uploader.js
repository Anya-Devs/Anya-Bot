import { adminStorage } from './config.js';
import { v4 as uuidv4 } from 'uuid';
import sharp from 'sharp';

/**
 * Firebase Storage uploader for character images
 */
export class FirebaseUploader {
  constructor() {
    this.bucket = adminStorage.bucket();
  }

  /**
   * Upload character images to Firebase Storage
   */
  async uploadCharacterImages(characterName, images) {
    const uploadedImages = [];
    const characterSlug = this.slugify(characterName);
    
    for (let i = 0; i < images.length; i++) {
      const image = images[i];
      
      try {
        console.log(`    Uploading image ${i + 1}/${images.length}...`);
        
        // Generate unique ID for image
        const imageId = uuidv4();
        
        // Optimize image
        const optimized = await this.optimizeImage(image.buffer);
        
        // Create thumbnail
        const thumbnail = await this.createThumbnail(image.buffer);
        
        // Upload full image
        const fullImageUrl = await this.uploadFile(
          optimized,
          `characters/${characterSlug}/${imageId}.webp`,
          'image/webp'
        );
        
        // Upload thumbnail
        const thumbnailUrl = await this.uploadFile(
          thumbnail,
          `characters/${characterSlug}/${imageId}_thumb.webp`,
          'image/webp'
        );
        
        uploadedImages.push({
          id: imageId,
          url: fullImageUrl,
          thumbnail: thumbnailUrl,
          width: image.metadata.width,
          height: image.metadata.height,
          source: image.source,
          alt: image.alt,
          hash: image.hash
        });
        
      } catch (error) {
        console.error(`    ❌ Failed to upload image ${i + 1}:`, error.message);
      }
    }
    
    return uploadedImages;
  }

  /**
   * Optimize image for web
   */
  async optimizeImage(buffer) {
    return await sharp(buffer)
      .webp({ quality: 85 })
      .resize(1920, 1920, { 
        fit: 'inside',
        withoutEnlargement: true 
      })
      .toBuffer();
  }

  /**
   * Create thumbnail
   */
  async createThumbnail(buffer) {
    return await sharp(buffer)
      .webp({ quality: 75 })
      .resize(400, 400, { 
        fit: 'cover',
        position: 'center'
      })
      .toBuffer();
  }

  /**
   * Upload file to Firebase Storage
   */
  async uploadFile(buffer, path, contentType) {
    const file = this.bucket.file(path);
    
    await file.save(buffer, {
      metadata: {
        contentType,
        cacheControl: 'public, max-age=31536000'
      },
      public: true
    });
    
    // Get public URL
    const [metadata] = await file.getMetadata();
    return `https://storage.googleapis.com/${this.bucket.name}/${path}`;
  }

  /**
   * Delete character images
   */
  async deleteCharacterImages(characterSlug) {
    const [files] = await this.bucket.getFiles({
      prefix: `characters/${characterSlug}/`
    });
    
    await Promise.all(files.map(file => file.delete()));
    
    console.log(`Deleted ${files.length} files for ${characterSlug}`);
  }

  /**
   * Convert string to URL-friendly slug
   */
  slugify(text) {
    return text
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .trim();
  }
}
