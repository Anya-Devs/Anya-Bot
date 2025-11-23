# Quick Start Guide

## 🚀 Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your configuration
```

### 3. Configuration Options

#### Option A: Use Without Firebase (Demo Mode)
**Leave Firebase variables empty** - The app will work but without character persistence.

```env
# Leave these empty for demo mode
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_PROJECT_ID=
```

**What works:**
- ✅ Command showcase
- ✅ Bot stats (from commands.json)
- ✅ Character search from APIs
- ❌ Character persistence (won't save to database)

#### Option B: Full Setup with Firebase
**Required for character database**

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project
3. Enable Firestore Database
4. Get your config from Project Settings > Your apps > Web app
5. Add to `.env`:

```env
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
```

**What works:**
- ✅ Everything from Option A
- ✅ Character persistence
- ✅ Character database
- ✅ Real-time updates

### 4. Run Development Server

```bash
npm run dev
```

Visit: http://localhost:3000

## 📊 Features Status

### ✅ Working Out of the Box

1. **Command Showcase**
   - Real-time timestamps
   - All commands from commands.json
   - Discord-style embeds
   - Code block formatting

2. **Bot Stats**
   - Command count (calculated)
   - Server/User count (shows "N/A" without backend)

3. **Character Search**
   - AniList API (no key required)
   - Jikan/MAL API (no key required)
   - Kitsu API (no key required)

4. **Image Scraping**
   - Danbooru (no key required)
   - Safebooru (no key required)
   - Gelbooru (no key required)

### ⚙️ Optional Configuration

1. **Backend Stats API** (Optional)
   ```env
   VITE_BACKEND_API_URL=https://your-api.com
   ```
   For real server/user counts from your bot

2. **GIF APIs** (Optional - has defaults)
   ```env
   VITE_TENOR_API_KEY=your_key
   VITE_GIPHY_API_KEY=your_key
   ```
   For character GIFs in detail modal

## 🎮 Using the Character System

### Add a Character (Simple)

```typescript
// In browser console or code
import { addCharacter } from './services/characterDatabase';

// Just provide name - fetches everything from APIs
await addCharacter({ name: "Anya Forger" });

// Result:
// - Data from AniList, Jikan, Kitsu
// - 15 highest-voted images
// - Rarity based on popularity
// - All aliases, tags, voice actors
```

### Add Character with Series

```typescript
await addCharacter({ 
  name: "Naruto Uzumaki",
  series: "Naruto"
});
```

### Import Popular Characters

```typescript
import { importPopularCharacters } from './services/multiAPICharacter';

// Import top 50 most popular characters
const characters = await importPopularCharacters(50);
```

## 🐛 Troubleshooting

### "Firebase not configured"
**This is normal if you haven't set up Firebase.**

**Solution:**
- Either set up Firebase (see Option B above)
- Or ignore - app works in demo mode

### "Backend API not available"
**This is normal if you don't have a backend API.**

**Solution:**
- Stats will show "N/A" for server/user counts
- Command count still works (calculated from commands.json)
- This is expected behavior

### "Failed to fetch characters"
**Possible causes:**
1. Firebase not configured (expected)
2. No characters in database yet

**Solution:**
- Add characters using `addCharacter()` in console
- Or use demo mode without Firebase

### Images not loading
**Possible causes:**
1. API rate limits
2. Character name spelling

**Solution:**
- Wait 1 second between requests
- Try different character names
- Check browser console for errors

## 📝 Console Commands

Open browser console (F12) and try:

```javascript
// Add a character
await addCharacter({ name: "Anya Forger" });

// Search character
import { searchCharacterAllAPIs } from './services/multiAPICharacter';
const char = await searchCharacterAllAPIs("Anya Forger");
console.log(char);

// Get popular characters
import { getPopularCharacters } from './services/anilistAPI';
const popular = await getPopularCharacters(1, 10);
console.log(popular);
```

## ✅ Verification Checklist

- [ ] `npm install` completed
- [ ] `.env` file created (even if empty)
- [ ] `npm run dev` runs without errors
- [ ] Website loads at localhost:3000
- [ ] Command showcase shows commands
- [ ] Timestamps show current time
- [ ] Character dex page loads
- [ ] (Optional) Firebase configured
- [ ] (Optional) Characters can be added

## 🎯 What's Working Right Now

### Without Any Configuration

✅ **Command Showcase**
- All commands displayed
- Real-time timestamps
- Discord embeds
- Code formatting

✅ **Character Search**
- Search any anime character
- Fetches from 3+ APIs
- Gets images automatically
- Calculates rarity

✅ **Bot Stats**
- Command count (calculated)
- Server/User (shows N/A)

### With Firebase

✅ **Everything above, plus:**
- Character persistence
- Database storage
- Real-time updates
- Character collections

## 🚀 Next Steps

1. **Start using it!** - Everything works without configuration
2. **Add Firebase** (optional) - For character persistence
3. **Set up backend** (optional) - For real bot stats
4. **Add characters** - Use console commands or UI

## 📚 Documentation

- **MULTI_API_GUIDE.md** - Character API system
- **CHARACTER_DEX_COMPLETE.md** - Character detail pages
- **FIREBASE_SETUP.md** - Firebase configuration
- **DYNAMIC_DATA_GUIDE.md** - How everything works

## 🎉 You're Ready!

The app is fully functional without any API keys or configuration. Just run `npm run dev` and start using it!

Optional configurations only add extra features like persistence and real-time stats.
