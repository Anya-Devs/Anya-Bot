# Anime Gacha API

Fast anime character API for gacha systems. Pre-caches characters from multiple sources for instant retrieval.

## Features

- ⚡ **Instant responses** - Characters are pre-cached in memory
- 🔄 **Multi-source** - Fetches from AniList, Jikan (MAL), and Kitsu
- 🎲 **Rarity system** - Characters sorted by popularity into 5 tiers
- 🔍 **Search** - Find characters by name
- 📦 **Batch fetch** - Get multiple characters in one request

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | API health and cache status |
| `GET /api/characters/random?rarity=common` | Get random character by rarity |
| `GET /api/characters/batch?count=3&rarities=common,rare,epic` | Get multiple characters |
| `GET /api/characters/search?name=naruto&limit=10` | Search characters by name |
| `GET /api/characters/stats` | Get cache statistics |
| `GET /api/characters/:id` | Get character by ID |
| `GET /api/characters/refresh` | Force cache refresh |

## Rarity Tiers

| Tier | Favorites Threshold | Color |
|------|---------------------|-------|
| 🟡 Legendary | 7,000+ | Gold |
| 🟣 Epic | 3,000+ | Purple |
| 🔵 Rare | 800+ | Blue |
| 🟢 Uncommon | 150+ | Green |
| ⚪ Common | 0+ | Grey |

## Response Format

```json
{
  "id": 12345,
  "name": "Naruto Uzumaki",
  "anime": "Naruto",
  "anime_popularity": 2500000,
  "image_url": "https://...",
  "gender": "Male",
  "favorites": 50000,
  "rarity": "legendary",
  "api_source": "AniList"
}
```

## Local Development

```bash
npm install
npm run dev
```

## Deploy to Render.com

1. Create a new **Web Service** on Render
2. Connect your GitHub repository
3. Set build command: `npm install`
4. Set start command: `npm start`
5. Choose a free instance (or paid for better performance)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 3000 | Server port |

## Testing

```bash
npm test
```
