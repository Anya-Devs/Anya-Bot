# Character Dex - Real API Integration Guide

## 🎯 Overview

The Character Dex now uses **real anime image APIs** to automatically fetch high-quality character images from multiple sources.

## 🔌 Integrated APIs

### 1. **Danbooru** (Primary Source)
- **URL**: https://danbooru.donmai.us
- **Type**: Large anime image database
- **API Key**: Not required for basic usage
- **Rate Limit**: ~2 requests/second
- **Features**: High-quality images, extensive tagging

### 2. **Safebooru** (Safe Content Only)
- **URL**: https://safebooru.org
- **Type**: SFW anime images only
- **API Key**: Not required
- **Rate Limit**: ~1 request/second
- **Features**: Family-friendly, filtered content

### 3. **Gelbooru** (Alternative Source)
- **URL**: https://gelbooru.com
- **Type**: Large anime image database
- **API Key**: Not required for basic usage
- **Rate Limit**: ~2 requests/second
- **Features**: Extensive collection, good search

## 🚀 How It Works

### Automatic Image Fetching

```typescript
// When a character is added:
1. Character data is provided (name, series, tags)
2. System searches multiple APIs in parallel
3. Images are filtered (safe content, minimum dimensions)
4. Duplicates are removed
5. Best images are selected and stored
6. Character is added to database with images
```

### Search Process

```typescript
// Example: Adding "Anya Forger" from "Spy x Family"
const character = await addCharacter({
  name: "Anya Forger",
  series: "Spy x Family",
  aliases: ["Subject 007"],
  tags: ["Pink Hair", "Green Eyes", "Telepathy"],
  role: ["Main Character", "Protagonist"]
});

// System automatically:
// 1. Searches: "anya_forger spy_x_family"
// 2. Fetches ~30 images from APIs
// 3. Filters to safe, high-quality images
// 4. Stores top 10 images
// 5. Returns character with images
```

## 📊 Rarity System

### Automatic Rarity Assignment

```typescript
SSR (5% chance)  - Main protagonists, extremely popular
SR  (15% chance) - Important supporting characters
R   (30% chance) - Regular characters with roles
C   (50% chance) - Common/background characters
```

### Manual Override

```typescript
await addCharacter({
  name: "Character Name",
  series: "Series Name",
  rarity: "SSR", // Force specific rarity
  // ...
});
```

## 🔄 Real-Time Updates

### Live Character Updates

The Character Dex automatically updates when new characters are added:

```typescript
// Subscribe to updates
const unsubscribe = subscribeToCharacters((characters) => {
  console.log(`Updated: ${characters.length} characters`);
  // UI automatically refreshes
});

// Cleanup
unsubscribe();
```

### Manual Refresh

Users can click the refresh button to reload all characters.

## 🎨 Image Quality Standards

### Minimum Requirements
- **Width**: 400px minimum
- **Height**: 400px minimum
- **Rating**: Safe content only (by default)
- **Format**: JPG, PNG, WebP supported

### Filtering
- Duplicate detection by URL
- Quality scoring (coming soon)
- Aspect ratio validation
- File size limits

## 📝 Adding New Characters

### Method 1: Single Character

```typescript
import { addCharacter } from './services/characterDatabase';

const character = await addCharacter({
  name: "Naruto Uzumaki",
  series: "Naruto",
  aliases: ["Number One Hyperactive Knucklehead Ninja"],
  tags: ["Blonde Hair", "Blue Eyes", "Ninja"],
  voiceActors: {
    english: "Maile Flanagan",
    japanese: "Junko Takeuchi"
  },
  description: "A young ninja who seeks recognition...",
  affiliation: ["Konohagakure", "Team 7"],
  role: ["Main Character", "Protagonist"]
});

console.log(`Added ${character.name} with ${character.imageCount} images`);
```

### Method 2: Batch Import

```typescript
import { batchImportCharacters } from './services/characterDatabase';

const characters = [
  { name: "Character 1", series: "Series 1", ... },
  { name: "Character 2", series: "Series 2", ... },
  // ...
];

const imported = await batchImportCharacters(characters);
console.log(`Imported ${imported.length} characters`);
```

### Method 3: From JSON File

```typescript
// Load from public/data/example-characters.json
const response = await fetch('/data/example-characters.json');
const data = await response.json();
await batchImportCharacters(data);
```

## 🔧 Configuration

### Environment Variables

Create `.env` file (optional):

```env
# API Configuration
VITE_SAFE_MODE=true              # Only fetch safe images
VITE_MIN_IMAGE_WIDTH=400         # Minimum image width
VITE_MIN_IMAGE_HEIGHT=400        # Minimum image height
VITE_MAX_IMAGES_PER_CHARACTER=10 # Images to fetch per character

# Rate Limiting
VITE_API_DELAY_MS=500            # Delay between API calls
VITE_MAX_CONCURRENT_REQUESTS=3   # Max parallel requests
```

### Customizing Image Search

```typescript
// In animeImageAPI.ts
export async function searchAllSources(
  characterName: string,
  seriesName: string,
  options: {
    safeOnly?: boolean;      // Default: true
    minWidth?: number;       // Default: 400
    minHeight?: number;      // Default: 400
    maxResults?: number;     // Default: 30
  } = {}
): Promise<ImageSearchResult[]>
```

## 🎮 Usage Examples

### Search Characters

```typescript
const results = await searchCharacters("naruto");
// Returns all characters matching "naruto"
```

### Filter by Rarity

```typescript
const ssrCharacters = await getCharactersByRarity("SSR");
// Returns only SSR rarity characters
```

### Filter by Series

```typescript
const spyFamily = await getCharactersBySeries("Spy x Family");
// Returns all characters from Spy x Family
```

### Random Gacha Pull

```typescript
const character = await getRandomCharacter();
// Returns random character weighted by rarity
// SSR: 5% chance, SR: 15%, R: 30%, C: 50%
```

## 🐛 Troubleshooting

### Images Not Loading

**Problem**: Characters have no images
**Solution**: 
1. Check browser console for API errors
2. Verify character name/series spelling
3. Try alternative search terms
4. Check API rate limits

### CORS Errors

**Problem**: API requests blocked by CORS
**Solution**:
1. Use a CORS proxy (development only)
2. Set up backend proxy (production)
3. Use APIs that support CORS

### Rate Limiting

**Problem**: Too many API requests
**Solution**:
1. Reduce `maxResults` in search
2. Increase delay between requests
3. Implement request queue
4. Cache results longer

## 🚀 Production Deployment

### Recommended Setup

1. **Backend Proxy**: Route API requests through your server
2. **Image CDN**: Store images on CDN (Cloudflare, AWS)
3. **Database**: Use Firebase/Firestore for persistence
4. **Caching**: Implement Redis for API response caching
5. **Rate Limiting**: Add request throttling

### Example Backend Proxy (Node.js)

```javascript
app.get('/api/search-images', async (req, res) => {
  const { character, series } = req.query;
  
  // Add rate limiting
  // Add caching
  // Add error handling
  
  const results = await searchAllSources(character, series);
  res.json(results);
});
```

## 📈 Performance Tips

1. **Lazy Loading**: Load images on demand
2. **Pagination**: Show 20-50 characters per page
3. **Thumbnail First**: Load thumbnails before full images
4. **Background Fetching**: Fetch images in background
5. **Service Worker**: Cache images offline

## 🔐 Security Considerations

1. **Content Filtering**: Always use safe mode in production
2. **Input Validation**: Sanitize character names/series
3. **Rate Limiting**: Prevent API abuse
4. **CORS**: Properly configure CORS headers
5. **API Keys**: Store keys securely (if using premium APIs)

## 📚 Additional Resources

- [Danbooru API Docs](https://danbooru.donmai.us/wiki_pages/help:api)
- [Safebooru API](https://safebooru.org/index.php?page=help&topic=dapi)
- [Gelbooru API](https://gelbooru.com/index.php?page=wiki&s=view&id=18780)

## 🎉 Features

✅ Real anime image APIs
✅ Automatic image fetching
✅ Rarity system with weights
✅ Real-time updates
✅ Safe content filtering
✅ Duplicate detection
✅ Multiple source fallbacks
✅ Responsive UI
✅ Search and filters
✅ Character cards with images

The Character Dex is now fully functional with real anime image APIs! 🚀
