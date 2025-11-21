# Character Image Scraper Setup

## Overview
The character scraper automatically finds and downloads high-quality images for anime/manga characters.

## Architecture

### Frontend (React/TypeScript)
- `src/services/scraperService.ts` - Image scraping logic
- `src/services/characterService.ts` - Character data management
- `src/types/character.ts` - TypeScript interfaces

### Backend (Node.js - Optional)
- `src/scraper/index.js` - Main scraper orchestrator
- `src/scraper/image-scraper.js` - Image search implementation
- `src/scraper/deduplicator.js` - Duplicate image detection

## Setup Instructions

### 1. Install Dependencies

```bash
npm install puppeteer axios sharp
```

### 2. Configure API Keys

Create `.env` file:

```env
# Google Custom Search API
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id

# Bing Image Search API
BING_API_KEY=your_bing_api_key

# Firebase (for image storage)
FIREBASE_API_KEY=your_firebase_api_key
FIREBASE_STORAGE_BUCKET=your_storage_bucket

# Scraper Settings
MAX_IMAGES_PER_CHARACTER=50
SCRAPE_DELAY_MS=1000
IMAGE_MIN_WIDTH=400
IMAGE_MIN_HEIGHT=400
```

### 3. API Integration Options

#### Option A: Google Custom Search API
```typescript
async searchImages(query: string): Promise<string[]> {
  const response = await fetch(
    `https://www.googleapis.com/customsearch/v1?` +
    `key=${process.env.GOOGLE_API_KEY}&` +
    `cx=${process.env.GOOGLE_SEARCH_ENGINE_ID}&` +
    `q=${encodeURIComponent(query)}&` +
    `searchType=image&` +
    `num=10&` +
    `imgSize=large`
  );
  
  const data = await response.json();
  return data.items?.map((item: any) => item.link) || [];
}
```

#### Option B: Danbooru API (Anime-specific)
```typescript
async searchDanbooru(tags: string[]): Promise<string[]> {
  const tagString = tags.join(' ');
  const response = await fetch(
    `https://danbooru.donmai.us/posts.json?` +
    `tags=${encodeURIComponent(tagString)}&` +
    `limit=100&` +
    `only=file_url`
  );
  
  const data = await response.json();
  return data.map((post: any) => post.file_url).filter(Boolean);
}
```

#### Option C: Gelbooru API
```typescript
async searchGelbooru(tags: string[]): Promise<string[]> {
  const tagString = tags.join(' ');
  const response = await fetch(
    `https://gelbooru.com/index.php?` +
    `page=dapi&` +
    `s=post&` +
    `q=index&` +
    `json=1&` +
    `tags=${encodeURIComponent(tagString)}&` +
    `limit=100`
  );
  
  const data = await response.json();
  return data.post?.map((p: any) => p.file_url) || [];
}
```

### 4. Run Scraper

#### Scrape Single Character
```bash
node src/scraper/index.js
```

#### Batch Scrape from JSON
```bash
node scripts/batch-scrape.js
```

## Image Storage

### Firebase Storage
Images are uploaded to Firebase Storage with the following structure:

```
characters/
  ├── character-name-id/
  │   ├── image-1.jpg
  │   ├── image-2.jpg
  │   └── ...
```

### Local Storage (Development)
For development, images can be stored locally:

```
public/
  └── character-images/
      ├── anya-forger/
      │   ├── 1.jpg
      │   ├── 2.jpg
      │   └── ...
```

## Deduplication

The scraper uses perceptual hashing to detect duplicate/similar images:

1. **Exact Duplicates** - Same file hash
2. **Similar Images** - Perceptual hash distance < threshold
3. **Different Sizes** - Keep highest resolution

## Usage in Frontend

```typescript
import { getCharacters } from './services/characterService';

// Characters are automatically loaded with scraped images
const characters = await getCharacters();

// Images are cached for performance
// Scraping happens in background for missing images
```

## Production Considerations

1. **Rate Limiting** - Add delays between API requests
2. **Error Handling** - Retry failed scrapes
3. **Image Validation** - Check dimensions, file size, format
4. **Copyright** - Only use images with appropriate licenses
5. **CDN** - Use CDN for image delivery
6. **Lazy Loading** - Load images on demand

## Troubleshooting

### Images Not Loading
- Check API keys are correct
- Verify network connectivity
- Check browser console for errors

### Duplicate Images
- Adjust perceptual hash threshold
- Enable stricter deduplication

### Slow Performance
- Reduce `MAX_IMAGES_PER_CHARACTER`
- Increase `SCRAPE_DELAY_MS`
- Use CDN for image delivery

## Future Enhancements

- [ ] AI-powered image quality scoring
- [ ] Automatic tagging/categorization
- [ ] Face detection for character portraits
- [ ] Background removal
- [ ] Image upscaling
- [ ] NSFW content filtering
