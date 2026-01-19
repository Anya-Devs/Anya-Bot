# Deploy Image API to Render.com

## Repository Ready! ✅
Your API is now at: https://github.com/senko-sleep/anya-image-api

## Deploy Steps:

### 1. Go to Render Dashboard
https://dashboard.render.com/

### 2. Create New Web Service
1. Click **"New +"** → **"Web Service"**
2. Click **"Connect to GitHub"** (if not already connected)
3. Find and select **"anya-image-api"** repository
4. Click **"Connect"**

### 3. Configure Service (auto-filled)
- **Name**: `anya-image-api` (or customize)
- **Region**: Oregon (or closest to you)
- **Branch**: `main`
- **Root Directory**: (leave empty)
- **Runtime**: Node (auto-detected)
- **Build Command**: `npm install`
- **Start Command**: `npm start`
- **Instance Type**: Free

### 4. Create Service
Click **"Create Web Service"**

### 5. Wait for Deployment
- Takes 2-3 minutes
- Watch the logs in Render dashboard
- Look for: `ANYA IMAGE API v1.0` in logs

### 6. Get Your API URL
After deployment, you'll get:
```
https://anya-image-api.onrender.com
```

### 7. Test API
```bash
# Health check
curl https://anya-image-api.onrender.com/health

# Test search
curl "https://anya-image-api.onrender.com/api/search?character=Anya&series=Spy+x+Family&limit=10"
```

### 8. Update Bot
Set environment variable for your bot:
```bash
# Windows PowerShell
$env:IMAGE_API_URL = "https://anya-image-api.onrender.com"

# Or add to .env file in bot directory
IMAGE_API_URL=https://anya-image-api.onrender.com
```

## Done! 🎉

Your bot will now use the ultra-fast API automatically with:
- Smart rate limiting
- Parallel fetching
- LRU caching
- 6 booru sources
- Automatic fallback if API is down

## Notes:
- Free tier spins down after 15 min inactivity
- Cold starts take ~30 seconds
- API auto-restarts on errors
- Logs available in Render dashboard
