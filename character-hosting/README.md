# 🎴 Anya Bot - Character Collection System

A comprehensive character image hosting and gacha system for anime, manga, video game, and cartoon characters. Features web scraping with intelligent deduplication, Firebase hosting, and Discord bot integration.

## ✨ Features

### 🔍 Web Scraping
- **Multi-source scraping**: Google Images, Bing Images, Danbooru, Safebooru
- **Intelligent deduplication**: Perceptual hashing to remove duplicate images
- **Up to 100 images per character**: Curated collection of high-quality images
- **Automatic optimization**: WebP conversion and thumbnail generation
- **Safe content filtering**: Only SFW images from anime boards

### ☁️ Firebase Integration
- **Cloud storage**: All images hosted on Firebase Storage with unique UIDs
- **Firestore database**: Character metadata, tags, and relationships
- **Public CDN**: Fast image delivery with caching
- **Scalable architecture**: Handles thousands of characters

### 🌐 Web Interface
- **Character Dex**: Browse and search all characters
- **Advanced filtering**: By series, rarity, tags, and more
- **Leaderboard**: Track top collectors
- **Responsive design**: Works on all devices
- **Modern UI**: Beautiful gradient effects and animations

### 🎮 Discord Bot Integration
- **Gacha system**: Roll for random characters
- **Rarity tiers**: Common, Rare, Super Rare, Ultra Rare
- **Daily rolls**: Free daily character roll
- **Multi-rolls**: Roll 10 characters at once
- **Character lookup**: View detailed character information
- **Collection tracking**: Track user collections and stats

## 📦 Installation

### Prerequisites
- Node.js 18+
- Python 3.11+ (for Discord bot)
- Firebase account
- Discord bot token

### Setup

1. **Clone the repository**
```bash
cd character-hosting
```

2. **Install dependencies**
```bash
npm install
```

3. **Configure Firebase**
- Create a Firebase project at https://console.firebase.google.com
- Enable Firestore Database and Storage
- Download service account key
- Copy `.env.example` to `.env` and fill in your credentials:

```env
FIREBASE_API_KEY=your_api_key
FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_STORAGE_BUCKET=your_project.appspot.com
FIREBASE_MESSAGING_SENDER_ID=your_sender_id
FIREBASE_APP_ID=your_app_id

DISCORD_BOT_TOKEN=your_bot_token
DISCORD_BOT_ID=your_bot_id
```

4. **Initialize Firebase**
```bash
firebase login
firebase init
```

Select:
- Firestore
- Storage
- Hosting
- Functions (optional)

5. **Deploy Firestore rules**
```bash
firebase deploy --only firestore:rules
firebase deploy --only storage:rules
```

## 🚀 Usage

### Scraping Characters

Create a character data file or use the API:

```javascript
import { CharacterScraper } from './src/scraper/index.js';

const scraper = new CharacterScraper();

const characterData = {
  name: "Anya Forger",
  series: "Spy x Family",
  aliases: [
    "Subject 007",
    "Chihuahua Girl",
    "Ania Forger",
    "Starlight Anya"
  ],
  tags: [
    "Main Character",
    "Protagonist",
    "Eden Academy",
    "Pink Hair",
    "Green Eyes",
    "Ahoge"
  ],
  voiceActors: {
    english: "Megan Shipman",
    japanese: "Atsumi Tanezaki"
  },
  rarity: "SSR"
};

const result = await scraper.scrapeCharacter(characterData);
console.log(`Scraped ${result.imageCount} images for ${characterData.name}`);
```

Run the scraper:
```bash
npm run scrape
```

### Batch Scraping

Create a JSON file with multiple characters:

```json
[
  {
    "name": "Anya Forger",
    "series": "Spy x Family",
    "rarity": "SSR",
    ...
  },
  {
    "name": "Loid Forger",
    "series": "Spy x Family",
    "rarity": "SR",
    ...
  }
]
```

Then scrape all:
```javascript
const characters = require('./characters.json');
const results = await scraper.scrapeMultipleCharacters(characters);
```

### Running the Website

**Local development:**
```bash
npm run serve
```

**Deploy to Firebase:**
```bash
npm run deploy
```

Your site will be live at: `https://your-project.web.app`

### Discord Bot Integration

1. **Copy the gacha cog to your bot:**
```bash
cp src/discord/gacha-cog.py /path/to/your/bot/cogs/
```

2. **Load the cog in your bot:**
```python
await bot.load_extension('cogs.gacha-cog')
```

3. **Available commands:**
- `/roll` - Roll for a random character
- `/daily` - Claim daily free roll
- `/multi` - Roll 10 characters at once
- `/dex [character]` - Look up character info
- `/collection` - View your collection
- `/leaderboard` - View top collectors

## 🎨 Customization

### Rarity Configuration

Edit `public/scripts/config.js`:

```javascript
export const RARITY_CONFIG = {
  'C': { 
    name: 'Common', 
    color: '#9CA3AF', 
    weight: 50,
    emoji: '⚪'
  },
  // Add more rarities...
};
```

### Scraper Sources

Add custom image sources in `src/scraper/image-scraper.js`:

```javascript
async scrapeCustomSource(browser, query, limit) {
  // Your scraping logic
  return images;
}
```

### Styling

Customize colors in `public/style/main.css`:

```css
:root {
  --primary-color: #FF6B9D;
  --secondary-color: #C060A1;
  --accent-color: #FEC260;
  /* Customize more... */
}
```

## 📊 Database Schema

### Characters Collection
```javascript
{
  id: "anya-forger-abc123",
  name: "Anya Forger",
  series: "Spy x Family",
  aliases: ["Subject 007", "Chihuahua Girl"],
  tags: ["Pink Hair", "Green Eyes", "Protagonist"],
  rarity: "SSR",
  images: [
    {
      id: "uuid",
      url: "https://storage.googleapis.com/...",
      thumbnail: "https://storage.googleapis.com/...",
      width: 1920,
      height: 1080,
      hash: "..."
    }
  ],
  imageCount: 87,
  voiceActors: {
    japanese: "Atsumi Tanezaki",
    english: "Megan Shipman"
  },
  createdAt: "2025-01-01T00:00:00Z",
  updatedAt: "2025-01-01T00:00:00Z"
}
```

### Series Collection
```javascript
{
  id: "spy-x-family",
  name: "Spy x Family",
  characters: ["anya-forger-abc123", "loid-forger-def456"],
  characterCount: 2,
  createdAt: "2025-01-01T00:00:00Z"
}
```

### User Collections (Discord)
```javascript
{
  userId: "discord_user_id",
  username: "User#1234",
  characters: {
    "anya-forger-abc123": {
      obtainedAt: "2025-01-01T00:00:00Z",
      count: 3
    }
  },
  totalCharacters: 150,
  rareCharacters: 25,
  seriesCompleted: 5
}
```

## 🔧 Configuration

### Scraper Settings

```env
MAX_IMAGES_PER_CHARACTER=100
IMAGE_SIMILARITY_THRESHOLD=0.95
SCRAPE_DELAY_MS=1000
```

### Firebase Storage Rules

Images are publicly readable but only admins can write:

```
service firebase.storage {
  match /b/{bucket}/o {
    match /characters/{characterId}/{imageId} {
      allow read: if true;
      allow write: if request.auth.token.admin == true;
    }
  }
}
```

## 🐛 Troubleshooting

### Scraper Issues

**Problem**: Images not downloading
- Check internet connection
- Verify source websites are accessible
- Increase timeout in scraper settings

**Problem**: Too many duplicates
- Lower `IMAGE_SIMILARITY_THRESHOLD` (e.g., 0.90)
- Check perceptual hash algorithm

### Firebase Issues

**Problem**: Permission denied
- Verify Firebase rules are deployed
- Check service account credentials
- Ensure admin token is set

**Problem**: Storage quota exceeded
- Upgrade Firebase plan
- Reduce image quality settings
- Delete unused images

### Website Issues

**Problem**: Characters not loading
- Check Firebase configuration in `config.js`
- Verify Firestore indexes are created
- Check browser console for errors

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📧 Support

- Discord: https://discord.gg/5Sc82qwSxd
- Issues: GitHub Issues
- Email: support@anyabot.com

## 🎯 Roadmap

- [ ] Trading system between users
- [ ] Character fusion/evolution
- [ ] Seasonal events and limited characters
- [ ] Mobile app
- [ ] Character wishlists
- [ ] Duplicate exchange system
- [ ] Achievement system
- [ ] Custom character submissions

## 🙏 Credits

- Built with Firebase, Puppeteer, and Discord.js
- Image sources: Google Images, Bing Images, Danbooru, Safebooru
- Inspired by gacha games and character collection systems

---

Made with ❤️ by the Anya Bot Team
