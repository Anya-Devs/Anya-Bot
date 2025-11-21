# 🚀 Quick Start Guide

Get your character hosting system up and running in minutes!

## 📋 Prerequisites

- Node.js 18+ installed
- Firebase account (free tier works)
- Discord bot (optional, for gacha features)

## ⚡ 5-Minute Setup

### 1. Install Dependencies

```bash
cd character-hosting
npm install
```

### 2. Configure Firebase

Run the interactive setup:

```bash
node scripts/setup.js
```

Or manually create `.env`:

```env
FIREBASE_API_KEY=your_api_key
FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
FIREBASE_MESSAGING_SENDER_ID=your_sender_id
FIREBASE_APP_ID=your_app_id
```

### 3. Initialize Firebase

```bash
firebase login
firebase init
```

Select:
- ✅ Firestore
- ✅ Storage  
- ✅ Hosting

### 4. Deploy Firebase Rules

```bash
firebase deploy --only firestore:rules,storage:rules
```

### 5. Test Locally

```bash
npm run serve
```

Visit: http://localhost:5000

## 🎴 Scraping Your First Character

### Option A: Single Character

```javascript
import { CharacterScraper } from './src/scraper/index.js';

const scraper = new CharacterScraper();

await scraper.scrapeCharacter({
  name: "Anya Forger",
  series: "Spy x Family",
  aliases: ["Subject 007", "Chihuahua Girl"],
  tags: ["Pink Hair", "Green Eyes", "Protagonist"],
  rarity: "SSR"
});
```

### Option B: Batch Scraping

Use the example data:

```bash
node scripts/batch-scrape.js
```

This will scrape 10 example characters from `data/example-characters.json`.

## 🌐 Deploy to Production

```bash
npm run deploy
```

Your site will be live at: `https://your-project.web.app`

## 🤖 Discord Bot Integration

### 1. Copy the Cog

```bash
cp src/discord/gacha-cog.py ../bot/cogs/
```

### 2. Load in Your Bot

```python
# In your bot's main file
await bot.load_extension('cogs.gacha-cog')
```

### 3. Sync Commands

```python
await bot.tree.sync()
```

### 4. Test Commands

In Discord:
- `/roll` - Roll for a character
- `/daily` - Claim daily roll
- `/dex Anya Forger` - Look up character

## 📊 Project Structure

```
character-hosting/
├── src/
│   ├── scraper/          # Web scraping modules
│   ├── firebase/         # Firebase integration
│   ├── database/         # Database operations
│   └── discord/          # Discord bot cog
├── public/
│   ├── scripts/          # Frontend JavaScript
│   ├── style/            # CSS styling
│   └── index.html        # Main HTML
├── data/
│   └── example-characters.json  # Sample data
└── scripts/
    ├── setup.js          # Interactive setup
    └── batch-scrape.js   # Batch scraping
```

## 🎯 Common Tasks

### Add a New Character

```javascript
const newCharacter = {
  name: "Character Name",
  series: "Series Name",
  aliases: ["Alias 1", "Alias 2"],
  tags: ["Tag1", "Tag2", "Tag3"],
  rarity: "SR",  // C, R, SR, or SSR
  voiceActors: {
    japanese: "Japanese VA",
    english: "English VA"
  }
};

await scraper.scrapeCharacter(newCharacter);
```

### Update Rarity Weights

Edit `public/scripts/config.js`:

```javascript
export const RARITY_CONFIG = {
  'C': { weight: 50 },   // 50% chance
  'R': { weight: 30 },   // 30% chance
  'SR': { weight: 15 },  // 15% chance
  'SSR': { weight: 5 }   // 5% chance
};
```

### Change Color Theme

Edit `public/style/main.css`:

```css
:root {
  --primary-color: #FF6B9D;    /* Main accent color */
  --secondary-color: #C060A1;  /* Secondary accent */
  --accent-color: #FEC260;     /* Highlight color */
  --bg-color: #0F0F1E;         /* Background */
}
```

### Add Custom Scraper Source

Edit `src/scraper/image-scraper.js`:

```javascript
async scrapeMySource(browser, query, limit) {
  // Your scraping logic
  return [
    {
      url: 'image_url',
      source: 'My Source',
      alt: query,
      width: 1920,
      height: 1080
    }
  ];
}
```

Then add to sources array:

```javascript
this.sources = [
  // ... existing sources
  { name: 'My Source', scraper: this.scrapeMySource.bind(this) }
];
```

## 🔧 Troubleshooting

### "Permission denied" errors

```bash
firebase deploy --only firestore:rules,storage:rules
```

### Images not loading

Check Firebase config in `public/scripts/config.js` matches your `.env`

### Scraper timing out

Increase timeout in `.env`:

```env
SCRAPE_DELAY_MS=2000
```

### Too many duplicates

Lower similarity threshold in `.env`:

```env
IMAGE_SIMILARITY_THRESHOLD=0.90
```

## 📚 Next Steps

1. **Customize the design** - Edit CSS files in `public/style/`
2. **Add more characters** - Create JSON files in `data/`
3. **Set up Discord bot** - Copy cog to your bot
4. **Enable analytics** - Add Firebase Analytics
5. **Add authentication** - Implement user accounts
6. **Create trading system** - Build character trading
7. **Add achievements** - Implement achievement system

## 💡 Pro Tips

- **Scrape during off-peak hours** to avoid rate limits
- **Use specific search terms** for better image quality
- **Tag characters thoroughly** for better filtering
- **Backup your database** regularly
- **Monitor Firebase usage** to stay within free tier
- **Optimize images** to reduce storage costs
- **Cache frequently accessed data** for better performance

## 🆘 Need Help?

- 📖 Read the full [README.md](README.md)
- 💬 Join our [Discord](https://discord.gg/5Sc82qwSxd)
- 🐛 Report issues on GitHub
- 📧 Email: support@anyabot.com

## 🎉 You're Ready!

Your character hosting system is now set up! Start scraping characters and building your collection.

Happy collecting! 🎴✨
