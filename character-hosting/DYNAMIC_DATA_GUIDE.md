# Dynamic Data System - No Static Data

## 🎯 Overview

**ALL data is now dynamic** - no hardcoded values anywhere. Everything is fetched from APIs, databases, or calculated in real-time.

## 📊 Bot Statistics (Real-Time)

### How It Works

```typescript
// ❌ OLD (Static)
stats: {
  servers: '1,000+',  // Hardcoded
  users: '50,000+',   // Hardcoded
  commands: '100+',   // Hardcoded
  uptime: '99.9%'     // Hardcoded
}

// ✅ NEW (Dynamic)
const stats = await fetchBotStats();
// Fetches from:
// 1. Your backend API (primary)
// 2. Discord API (fallback)
// 3. Calculated from commands.json (command count)
```

### Setup Backend Stats API

Your Discord bot should POST stats every 5 minutes:

```python
# In your Discord bot (Python example)
import aiohttp
import asyncio

async def post_stats():
    stats = {
        'guild_count': len(bot.guilds),
        'user_count': sum(g.member_count for g in bot.guilds),
        'command_count': len(bot.commands),
        'uptime_percentage': calculate_uptime()
    }
    
    async with aiohttp.ClientSession() as session:
        await session.post(
            f'https://your-api.com/bot/{bot.user.id}/stats',
            json=stats,
            headers={'Authorization': f'Bearer {BOT_SECRET}'}
        )

# Run every 5 minutes
@tasks.loop(minutes=5)
async def update_stats():
    await post_stats()
```

### Backend API (Node.js/Express)

```javascript
// server.js
const express = require('express');
const redis = require('redis');
const app = express();
const client = redis.createClient();

app.use(express.json());

// POST stats from bot
app.post('/bot/:botId/stats', async (req, res) => {
  const { botId } = req.params;
  const { guild_count, user_count, command_count, uptime_percentage } = req.body;
  
  // Verify bot token
  if (req.headers.authorization !== `Bearer ${process.env.BOT_SECRET}`) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  
  // Store in Redis (5 minute expiry)
  await client.setex(`bot:${botId}:stats`, 300, JSON.stringify({
    guild_count,
    user_count,
    command_count,
    uptime_percentage,
    last_updated: new Date().toISOString()
  }));
  
  res.json({ success: true });
});

// GET stats for website
app.get('/bot/:botId/stats', async (req, res) => {
  const { botId } = req.params;
  const stats = await client.get(`bot:${botId}:stats`);
  
  if (!stats) {
    return res.status(404).json({ error: 'Stats not found' });
  }
  
  res.json(JSON.parse(stats));
});

app.listen(3000);
```

## 🎮 Commands (Processed Dynamically)

### Command Processing

```bash
# Run before build
npm run process-commands
```

This script:
1. ✅ Groups subcommands (`anime manga`, `pt qp`, `pt sh`)
2. ✅ Removes duplicate commands
3. ✅ Cleans empty categories
4. ✅ Standardizes format
5. ✅ Outputs to `public/commands.json`

### Command Groups

```json
{
  "Anime": {
    "anime": { ... },
    "anime manga": { ... },      // Grouped
    "anime character": { ... }   // Grouped
  },
  "PoketwoCommands": {
    "pt": { ... },
    "pt qp": { ... },            // Grouped
    "pt sh": { ... },            // Grouped
    "pt special": { ... }        // Grouped
  }
}
```

### Command Count

```typescript
// Dynamically counted from commands.json
const count = await getCommandCount();
// Returns actual number of commands
```

## 🎨 Character Database (Real Anime APIs)

### No Static Characters

```typescript
// ❌ OLD (Static)
const characters = [
  { name: "Anya", series: "Spy x Family", images: [...] }
];

// ✅ NEW (Dynamic from APIs)
const character = await addCharacter({
  name: "Anya Forger",
  series: "Spy x Family"
});
// Automatically fetches 10 real images from:
// - Danbooru
// - Safebooru  
// - Gelbooru
```

### Image Sources

1. **Danbooru** - `https://danbooru.donmai.us/posts.json`
2. **Safebooru** - `https://safebooru.org/index.php?page=dapi`
3. **Gelbooru** - `https://gelbooru.com/index.php?page=dapi`

### Auto-Rarity Assignment

```typescript
// Rarity assigned based on character role
if (role.includes('Main Character')) → SSR (5%)
if (role.includes('Supporting')) → SR (15%)
if (has roles) → R (30%)
else → C (50%)
```

## 🔄 Real-Time Updates

### Character Updates

```typescript
// Subscribe to live updates
const unsubscribe = subscribeToCharacters((characters) => {
  // UI updates automatically
  console.log(`${characters.length} characters`);
});
```

### Stats Updates

```typescript
// Stats refresh every 5 minutes (from backend)
// Or manually refresh
await fetchBotStats();
```

## 📝 Data Flow

### 1. Bot Stats
```
Discord Bot → POST /api/stats → Redis → GET /api/stats → Website
     ↓
  Every 5 min
```

### 2. Commands
```
commands.json → process-commands.js → public/commands.json → Website
                      ↓
              Groups & Deduplicates
```

### 3. Characters
```
User adds character → Search APIs → Fetch images → Store in DB → Website
                          ↓
                    Danbooru/Safebooru/Gelbooru
```

## 🚀 Setup Instructions

### 1. Backend API

```bash
# Create backend API
cd backend
npm init -y
npm install express redis cors

# Create server.js (see example above)
node server.js
```

### 2. Bot Stats Reporter

```python
# In your Discord bot
# Add stats posting task (see example above)
```

### 3. Environment Variables

```env
# .env
VITE_API_URL=https://your-api.com
BOT_SECRET=your_secret_token

# Backend .env
BOT_SECRET=your_secret_token
REDIS_URL=redis://localhost:6379
```

### 4. Build & Deploy

```bash
# Process commands & build
npm run build

# Deploy
npm run deploy
```

## ✅ Checklist

### Bot Stats
- [ ] Backend API created
- [ ] Redis configured
- [ ] Bot posts stats every 5 minutes
- [ ] Website fetches from API
- [ ] Fallback to Discord API works

### Commands
- [ ] process-commands.js runs on build
- [ ] Duplicates removed
- [ ] Subcommands grouped
- [ ] Command count is dynamic

### Characters
- [ ] Anime APIs integrated
- [ ] Images fetch automatically
- [ ] Rarity auto-assigned
- [ ] Real-time updates work
- [ ] No static character data

## 🐛 Troubleshooting

### Stats Show "N/A"
- Check backend API is running
- Verify bot is posting stats
- Check Redis connection
- Verify API endpoint URL

### Commands Not Grouped
- Run `npm run process-commands`
- Check output in `public/commands.json`
- Verify command groups in script

### No Character Images
- Check API rate limits
- Verify character name spelling
- Check browser console for errors
- Try different search terms

## 📚 Key Files

- `src/services/botStatsService.ts` - Stats fetching
- `src/services/characterDatabase.ts` - Character CRUD
- `src/services/animeImageAPI.ts` - Image search
- `scripts/process-commands.js` - Command processing
- `CHARACTER_DEX_API_GUIDE.md` - Character system docs

## 🎉 Result

✅ **Zero static data**
✅ **Real-time stats**
✅ **Dynamic commands**
✅ **Live character updates**
✅ **Real anime images**
✅ **Auto-rarity system**
✅ **API-driven everything**

Everything is now dynamic and updates in real-time! 🚀
