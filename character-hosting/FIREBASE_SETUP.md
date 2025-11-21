# Firebase Database Setup - NO STATIC DATA

## 🎯 Overview

**ALL character data is now stored in Firebase Firestore.** No hardcoded characters, no static JSON files.

## 🔥 Firebase Setup

### 1. Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add Project"
3. Name it (e.g., "anya-bot-characters")
4. Disable Google Analytics (optional)
5. Create project

### 2. Enable Firestore

1. In Firebase Console, go to **Firestore Database**
2. Click "Create Database"
3. Choose **Production Mode** (we'll set rules later)
4. Select a location (closest to your users)
5. Click "Enable"

### 3. Get Configuration

1. Go to **Project Settings** (gear icon)
2. Scroll to "Your apps"
3. Click **Web** icon (</>)
4. Register app (name: "Anya Bot Website")
5. Copy the configuration:

```javascript
const firebaseConfig = {
  apiKey: "AIza...",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abc123"
};
```

### 4. Configure Environment Variables

Create `.env` file in `character-hosting/`:

```env
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
```

### 5. Set Firestore Rules

In Firebase Console → Firestore → Rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Characters collection - read public, write authenticated
    match /characters/{characterId} {
      allow read: if true;  // Anyone can read
      allow write: if request.auth != null;  // Only authenticated users can write
    }
    
    // Series collection
    match /series/{seriesId} {
      allow read: if true;
      allow write: if request.auth != null;
    }
  }
}
```

## 📝 Adding Characters

### Method 1: Using the Website (Recommended)

```typescript
// In browser console or admin panel
import { addCharacter } from './services/characterDatabase';

await addCharacter({
  name: "Anya Forger",
  series: "Spy x Family",
  aliases: ["Subject 007", "Anya-chan"],
  tags: ["Pink Hair", "Green Eyes", "Telepathy", "Cute"],
  role: ["Main Character", "Protagonist"],
  affiliation: ["Forger Family", "Eden Academy"],
  voiceActors: {
    english: "Megan Shipman",
    japanese: "Atsumi Tanezaki"
  },
  description: "A young telepath who was adopted by Loid Forger...",
  rarity: "SSR"  // Optional, auto-assigned if not provided
});
```

### Method 2: Batch Import Script

Create `scripts/import-characters.js`:

```javascript
import { addCharacter } from '../src/services/characterDatabase.js';

const characters = [
  {
    name: "Naruto Uzumaki",
    series: "Naruto",
    // ... character data
  },
  // ... more characters
];

for (const char of characters) {
  await addCharacter(char);
  console.log(`Added: ${char.name}`);
  
  // Wait to avoid rate limits
  await new Promise(resolve => setTimeout(resolve, 2000));
}
```

### Method 3: Firebase Admin SDK (Backend)

```javascript
const admin = require('firebase-admin');
const serviceAccount = require('./serviceAccountKey.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});

const db = admin.firestore();

async function addCharacter(characterData) {
  const docRef = db.collection('characters').doc();
  
  await docRef.set({
    ...characterData,
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    updatedAt: admin.firestore.FieldValue.serverTimestamp()
  });
  
  console.log(`Added character: ${characterData.name}`);
}
```

## 🔍 How It Works

### Data Flow

```
1. Website loads → Checks Firebase
2. If Firebase configured → Fetch characters from Firestore
3. If no characters → Show empty state
4. User adds character → Fetch images from anime APIs
5. Save to Firestore → Update UI in real-time
```

### No Static Data

```typescript
// ❌ OLD (Static)
const characters = [
  { name: "Anya", series: "Spy x Family", images: [...] }
];

// ✅ NEW (Firebase)
const characters = await fetchCharactersFromFirestore();
// Returns: Characters from Firestore database
// If empty: Returns []
// No fallback to static data
```

## 🎨 Image Fetching

When a character is added:

1. **Search anime APIs** (Danbooru, Safebooru, Gelbooru)
2. **Fetch 10 best images** (safe content, high quality)
3. **Store URLs in Firestore** (not the images themselves)
4. **Display on website** (images loaded from original sources)

## 🔄 Real-Time Updates

Characters update automatically across all users:

```typescript
// Subscribe to changes
subscribeToCharacters((characters) => {
  console.log(`${characters.length} characters in database`);
  // UI updates automatically
});
```

## 📊 Database Structure

### Firestore Collections

```
/characters/{characterId}
  - name: string
  - series: string
  - description: string
  - rarity: "C" | "R" | "SR" | "SSR"
  - aliases: string[]
  - tags: string[]
  - images: string[]  // URLs from anime APIs
  - imageCount: number
  - role: string[]
  - affiliation: string[]
  - voiceActors: {
      english: string
      japanese: string
    }
  - createdAt: timestamp
  - updatedAt: timestamp

/series/{seriesId}
  - name: string
  - characters: string[]  // Character IDs
  - characterCount: number
```

## 🚀 Deployment

### Build with Firebase

```bash
# Set environment variables
cp .env.example .env
# Edit .env with your Firebase config

# Build
npm run build

# Deploy to Firebase Hosting
firebase deploy
```

### Verify Setup

```bash
# Check Firebase connection
npm run dev

# Open browser console
# Should see: "[DB] Initializing database from Firebase..."
# If configured: "[DB] Loaded X characters from Firebase"
# If not configured: "[DB] Firebase not configured..."
```

## 🐛 Troubleshooting

### "Firebase not configured"

- Check `.env` file exists
- Verify all `VITE_FIREBASE_*` variables are set
- Restart dev server after changing `.env`

### "No characters found"

- Database is empty (expected for new setup)
- Add characters using `addCharacter()`
- Check Firestore console for data

### "Failed to fetch characters"

- Check Firestore rules allow read access
- Verify project ID is correct
- Check browser console for errors

### Images not loading

- Check anime API rate limits
- Verify character name spelling
- Try different search terms
- Check browser console for CORS errors

## 📚 API Reference

### Add Character

```typescript
await addCharacter({
  name: string;
  series: string;
  aliases?: string[];
  tags?: string[];
  role?: string[];
  affiliation?: string[];
  voiceActors?: {
    english?: string;
    japanese?: string;
  };
  description?: string;
  rarity?: "C" | "R" | "SR" | "SSR";
});
```

### Fetch Characters

```typescript
const characters = await fetchCharactersFromFirestore();
// Returns: Character[]
```

### Search Characters

```typescript
const results = await searchCharactersInFirestore("naruto");
// Returns: Character[]
```

### Update Character

```typescript
await updateCharacterInFirestore(characterId, {
  description: "New description",
  tags: ["new", "tags"]
});
```

### Delete Character

```typescript
await deleteCharacterFromFirestore(characterId);
```

## ✅ Checklist

- [ ] Firebase project created
- [ ] Firestore enabled
- [ ] `.env` file configured
- [ ] Firestore rules set
- [ ] Characters added to database
- [ ] Website loads characters from Firebase
- [ ] Images fetch from anime APIs
- [ ] Real-time updates work
- [ ] No static data anywhere

## 🎉 Result

✅ **Zero static data**
✅ **All characters in Firebase**
✅ **Real anime images from APIs**
✅ **Real-time synchronization**
✅ **Scalable database**
✅ **Production-ready**

Your character database is now fully dynamic and cloud-based! 🚀
