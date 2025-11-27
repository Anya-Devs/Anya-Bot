# Server-Side Caching for Bot Stats

## Problem
When the website is deployed to Firebase Hosting, every user opening the site makes their own API calls to Discord. This causes:
- **Rate limiting (429 errors)** when multiple users access the site
- **Wasted API quota** with duplicate requests
- **Slow loading** when rate limited

## Solution
A Firebase Function handles all Discord API calls server-side with caching:

```
User A ──┐
User B ──┼──> Firebase Function ──> Cache ──> Discord API (every 5 min)
User C ──┘         │
                   └── Returns cached data instantly
```

## How It Works

### 1. Firebase Function (`/api/bot-stats`)
- All clients call this single endpoint
- Function caches Discord API responses for 5 minutes
- Only makes a fresh Discord API call when cache expires
- Stores cache in Firestore for persistence across function instances

### 2. Scheduled Refresh
- A cron job runs every 5 minutes to keep the cache warm
- Even if no users visit, the cache stays fresh

### 3. Client-Side
- Clients have a 30-second local cache
- Prevents excessive server calls from rapid refreshes
- Falls back gracefully if server is unavailable

## Setup

### 1. Install Functions Dependencies
```bash
cd functions
npm install
```

### 2. Set Discord Token
```bash
# Option 1: Using Firebase Config
firebase functions:config:set discord.token="YOUR_BOT_TOKEN"

# Option 2: Using .env file (for local development)
cp .env.example .env
# Edit .env and add your token
```

### 3. Deploy Functions
```bash
cd anya-bot-website
firebase deploy --only functions
```

### 4. Deploy Hosting
```bash
firebase deploy --only hosting
```

## API Endpoint

### GET /api/bot-stats

**Response:**
```json
{
  "servers": 150,
  "users": 75000,
  "commands": 50,
  "status": "online",
  "lastUpdated": "2024-01-15T12:00:00.000Z",
  "cached": true,
  "cacheAge": 120
}
```

**Headers:**
- `X-Cache: HIT` - Data from cache
- `X-Cache: MISS` - Fresh data from Discord
- `X-Cache: STALE` - Error occurred, returning old cache

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Firebase Hosting                      │
│                    (anya-bot.web.app)                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      │ /api/bot-stats
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  Firebase Function                       │
│                    (botStats)                            │
│                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ In-Memory   │    │  Firestore  │    │  Discord    │  │
│  │   Cache     │◄───│   Cache     │◄───│    API      │  │
│  │  (5 min)    │    │ (backup)    │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Benefits

1. **No more 429 errors** - Only 1 API call every 5 minutes
2. **Faster loading** - Cached responses are instant
3. **Works at scale** - 1000 users = still only 1 API call
4. **Resilient** - Falls back to stale cache on errors
5. **Cost effective** - Minimal Firebase Function invocations

## Local Development

For local development, the frontend will try `/api/bot-stats` which won't work without running the Firebase emulator.

To test locally:
```bash
# Terminal 1: Run Firebase Emulator
cd functions && npm run serve

# Terminal 2: Run Vite with proxy
cd anya-bot-website && npm run dev
```

Or add a proxy to `vite.config.ts`:
```typescript
proxy: {
  '/api/bot-stats': {
    target: 'http://localhost:5001/your-project/us-central1',
    changeOrigin: true,
  }
}
```

## Monitoring

View function logs:
```bash
firebase functions:log
```

Check Firestore cache:
- Go to Firebase Console > Firestore
- Collection: `cache` > Document: `botStats`
