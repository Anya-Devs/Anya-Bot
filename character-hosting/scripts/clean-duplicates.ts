import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// Firebase configuration (same as in firebaseCharacterDB.ts)
const FIREBASE_CONFIG = {
  apiKey: process.env.VITE_FIREBASE_API_KEY || '',
  authDomain: process.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: process.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: process.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: process.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: process.env.VITE_FIREBASE_APP_ID || ''
};

const FIRESTORE_BASE = `https://firestore.googleapis.com/v1/projects/${FIREBASE_CONFIG.projectId}/databases/(default)/documents`;

interface Character {
  id: string;
  name: string;
  series: string;
  description: string;
  images: string[];
  imageCount: number;
  rarity: string;
  role: string[];
  affiliation: string[];
  appearance: string[];
  voiceActors: Record<string, string>;
  aliases: string[];
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

function generateId(name: string, series: string): string {
  const slug = `${name}-${series}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return slug;
}

// Convert Firestore document to Character object
function firestoreToCharacter(docId: string, data: any): Character {
  const fields = data.fields || {};
  
  return {
    id: docId,
    name: fields.name?.stringValue || '',
    series: fields.series?.stringValue || '',
    description: fields.description?.stringValue || '',
    images: (fields.images?.arrayValue?.values || []).map((v: any) => v.stringValue),
    imageCount: parseInt(fields.imageCount?.integerValue || '0'),
    rarity: fields.rarity?.stringValue || 'C',
    role: (fields.role?.arrayValue?.values || []).map((v: any) => v.stringValue),
    affiliation: (fields.affiliation?.arrayValue?.values || []).map((v: any) => v.stringValue),
    appearance: (fields.appearance?.arrayValue?.values || []).map((v: any) => v.stringValue),
    voiceActors: {},
    aliases: (fields.aliases?.arrayValue?.values || []).map((v: any) => v.stringValue),
    tags: (fields.tags?.arrayValue?.values || []).map((v: any) => v.stringValue),
    createdAt: fields.createdAt?.stringValue || '',
    updatedAt: fields.updatedAt?.stringValue || ''
  };
}

async function cleanDuplicates() {
  console.log('🧹 Starting duplicate cleanup...');
  
  if (!FIREBASE_CONFIG.projectId) {
    console.error('❌ Firebase project ID not configured. Please check environment variables.');
    return;
  }
  
  // Get all characters using REST API
  const response = await fetch(`${FIRESTORE_BASE}/characters`);
  
  if (!response.ok) {
    console.error('❌ Failed to fetch characters from Firestore');
    return;
  }
  
  const data = await response.json();
  const characters: Character[] = [];
  
  if (data.documents) {
    for (const doc of data.documents) {
      const character = firestoreToCharacter(doc.name.split('/').pop(), doc);
      characters.push(character);
    }
  }
  
  console.log(`📊 Found ${characters.length} total characters`);
  
  // Group by normalized ID
  const groups = new Map<string, Character[]>();
  
  for (const char of characters) {
    const normalizedId = generateId(char.name, char.series);
    
    if (!groups.has(normalizedId)) {
      groups.set(normalizedId, []);
    }
    groups.get(normalizedId)!.push(char);
  }
  
  // Find duplicates
  const duplicates: string[] = [];
  let duplicatesCount = 0;
  
  for (const [normalizedId, chars] of groups) {
    if (chars.length > 1) {
      console.log(`\n🔄 Found duplicates for: ${normalizedId}`);
      console.log(`   Count: ${chars.length}`);
      
      // Sort by creation date (keep the oldest)
      chars.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());
      
      // Keep the first (oldest), delete the rest
      const toKeep = chars[0];
      const toDelete = chars.slice(1);
      
      console.log(`   Keeping: ${toKeep.id} (created: ${toKeep.createdAt})`);
      console.log(`   Deleting: ${toDelete.map(c => c.id).join(', ')}`);
      
      duplicates.push(...toDelete.map(c => c.id));
      duplicatesCount += toDelete.length;
    }
  }
  
  console.log(`\n📋 Found ${duplicatesCount} duplicates to delete`);
  
  if (duplicates.length > 0) {
    // Delete duplicates one by one (using REST API)
    let deletedCount = 0;
    
    for (const docId of duplicates) {
      try {
        const deleteResponse = await fetch(`${FIRESTORE_BASE}/characters/${docId}`, {
          method: 'DELETE'
        });
        
        if (deleteResponse.ok) {
          deletedCount++;
          console.log(`🗑️  Deleted: ${docId} (${deletedCount}/${duplicates.length})`);
        } else {
          console.error(`❌ Failed to delete: ${docId}`);
        }
        
        // Small delay to avoid rate limiting
        await new Promise(resolve => setTimeout(resolve, 100));
      } catch (error) {
        console.error(`❌ Error deleting ${docId}:`, error);
      }
    }
    
    console.log(`\n✅ Successfully deleted ${deletedCount} duplicate characters!`);
  } else {
    console.log('\n✅ No duplicates found!');
  }
  
  // Show final count
  const finalResponse = await fetch(`${FIRESTORE_BASE}/characters`);
  if (finalResponse.ok) {
    const finalData = await finalResponse.json();
    console.log(`📊 Final character count: ${finalData.documents?.length || 0}`);
  }
}

// Run the cleanup
cleanDuplicates().catch(console.error);
