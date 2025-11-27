# Discord Token Setup

## Quick Setup

Run this command to automatically fetch your bot token from MongoDB and set it up:

```bash
npm install
npm run setup:token
npm run dev
```

This will:
1. Read `MONGO_URI` from `.github/.env`
2. Connect to MongoDB `Bot.information` collection
3. Fetch the `Token` field (matching your Python bot's configuration)
4. Write it to `anya-bot-website/.env` as `VITE_DISCORD_BOT_TOKEN`

## Manual Setup

If the script doesn't work, manually add to `anya-bot-website/.env`:
```env
VITE_DISCORD_BOT_TOKEN=your_discord_bot_token_here
```

## Overview
The website fetches bot stats using the Discord API with your bot token.

## Changes Made

### 1. Backend API Endpoint
**File:** `server/api/bot-token.ts`

This endpoint:
- Reads MongoDB URI from `.github/.env`
- Connects to MongoDB database `Bot`, collection `information`
- Fetches token based on `bot_config` (matching Python `const.py`)
- Returns token to frontend with caching

### 2. Frontend Token Fetching
**File:** `src/services/discordAPI.ts`

Updated to:
- Fetch token from `/api/bot-token` endpoint
- Fall back to `VITE_DISCORD_BOT_TOKEN` env variable if backend fails
- Cache token to avoid repeated API calls

### 3. Bot Configuration
Matches your Python configuration:
```typescript
const bot_config = {
  true: {  // Test bot
    prefix: '-',
    token_key: 'Test_Token'
  },
  false: {  // Production bot
    prefix: '.',
    token_key: 'Token'
  }
};
```

## Required Dependencies

Install these packages for the backend:
```bash
cd anya-bot-website
npm install express mongodb @types/express @types/node
```

## MongoDB Structure

Your MongoDB should have:
- **Database:** `Bot`
- **Collection:** `information`
- **Document Structure:**
  ```json
  {
    "Token": "your_discord_bot_token_here",
    "Test_Token": "your_test_bot_token_here"
  }
  ```

## Environment Setup

### .github/.env
Should contain:
```env
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/Bot
# or
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/Bot
```

### anya-bot-website/.env (Optional Fallback)
```env
VITE_DISCORD_BOT_TOKEN=your_fallback_token_here
```

## How It Works

1. **Frontend Request:** Dashboard/HomePage calls `fetchBotStats()`
2. **Token Fetch:** `discordAPI.ts` calls `/api/bot-token`
3. **Backend:** Reads `.github/.env` for MongoDB URI
4. **MongoDB Query:** Fetches document with `Token` or `Test_Token` field
5. **Response:** Returns token to frontend
6. **Caching:** Token is cached in memory to avoid repeated DB calls
7. **Discord API:** Uses token to fetch guild/user counts

## Testing

1. **Verify MongoDB Connection:**
   ```bash
   # Check that .github/.env has MONGO_URI
   cat .github/.env | grep MONGO
   ```

2. **Test Backend Endpoint:**
   ```bash
   # Start dev server
   npm run dev
   
   # In another terminal, test the endpoint
   curl http://localhost:3001/api/bot-token
   ```

3. **Check Dashboard:**
   - Navigate to `/dashboard`
   - Should see real server/user counts (not "N/A")
   - Check console for any errors

## Troubleshooting

### "Discord bot token not found"
- Check that `.github/.env` has `MONGO_URI` or `MONGODB_URI`
- Verify MongoDB database is `Bot` and collection is `information`
- Ensure document has `Token` field with valid bot token

### Backend Errors
- Install dependencies: `npm install express mongodb @types/express @types/node`
- Check MongoDB connection string is correct
- Verify bot token in MongoDB is valid

### WASM Errors (Pokemon Predictor)
These are expected and handled gracefully:
- The Pokemon predictor falls back to random predictions
- WASM files need correct MIME types (application/wasm)
- Single-threaded mode is used to avoid COEP requirements

## Security Notes

⚠️ **Important:**
- Never commit `.github/.env` to version control
- Bot token is fetched server-side, not exposed to client
- Token is cached in memory only (not localStorage)
- Use HTTPS in production to protect token in transit

## Production Deployment

For production:
1. Set up environment variables on your hosting platform
2. Ensure MongoDB is accessible from your server
3. Use connection pooling for MongoDB
4. Add rate limiting to `/api/bot-token` endpoint
5. Consider adding authentication for the endpoint

## Alternative: Environment Variable Only

If you prefer not to use MongoDB for token storage:
1. Delete `server/api/bot-token.ts`
2. Set `VITE_DISCORD_BOT_TOKEN` in `.env`
3. The frontend will automatically fall back to env variable

## Code Flow

```
Dashboard Page
    ↓
fetchBotStats()
    ↓
isDiscordAPIConfigured()
    ↓
fetchBotToken()
    ↓
GET /api/bot-token
    ↓
Read .github/.env
    ↓
Connect to MongoDB
    ↓
Query Bot.information
    ↓
Return token
    ↓
Cache token
    ↓
Use token for Discord API
    ↓
Display stats
```

## Next Steps

1. Install backend dependencies
2. Verify MongoDB connection
3. Test `/api/bot-token` endpoint
4. Check dashboard displays real stats
5. Monitor console for errors

## Notes

- The `use_test_bot` variable in `bot-token.ts` controls which token to use
- Set to `true` for test bot, `false` for production
- Token is cached until server restart
- Frontend has fallback to env variable if backend fails
