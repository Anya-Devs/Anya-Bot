#!/usr/bin/env node

/**
 * Setup script for character hosting system
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import readline from 'readline';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function question(query) {
  return new Promise(resolve => rl.question(query, resolve));
}

async function setup() {
  console.log('🎴 Anya Bot Character Hosting Setup\n');
  console.log('This script will help you configure your Firebase project.\n');

  // Check if .env exists
  const envPath = path.join(__dirname, '..', '.env');
  if (fs.existsSync(envPath)) {
    const overwrite = await question('.env file already exists. Overwrite? (y/N): ');
    if (overwrite.toLowerCase() !== 'y') {
      console.log('Setup cancelled.');
      rl.close();
      return;
    }
  }

  console.log('\n📋 Firebase Configuration\n');
  console.log('Get these values from Firebase Console > Project Settings > General\n');

  const apiKey = await question('Firebase API Key: ');
  const authDomain = await question('Auth Domain (e.g., your-project.firebaseapp.com): ');
  const projectId = await question('Project ID: ');
  const storageBucket = await question('Storage Bucket (e.g., your-project.appspot.com): ');
  const messagingSenderId = await question('Messaging Sender ID: ');
  const appId = await question('App ID: ');

  console.log('\n🤖 Discord Bot Configuration\n');

  const botToken = await question('Discord Bot Token: ');
  const botId = await question('Discord Bot ID: ');

  console.log('\n⚙️  Scraper Configuration\n');

  const maxImages = await question('Max images per character (default: 100): ') || '100';
  const similarity = await question('Image similarity threshold (default: 0.95): ') || '0.95';
  const delay = await question('Scrape delay in ms (default: 1000): ') || '1000';

  // Create .env file
  const envContent = `# Firebase Configuration
FIREBASE_API_KEY=${apiKey}
FIREBASE_AUTH_DOMAIN=${authDomain}
FIREBASE_PROJECT_ID=${projectId}
FIREBASE_STORAGE_BUCKET=${storageBucket}
FIREBASE_MESSAGING_SENDER_ID=${messagingSenderId}
FIREBASE_APP_ID=${appId}

# Scraper Configuration
MAX_IMAGES_PER_CHARACTER=${maxImages}
IMAGE_SIMILARITY_THRESHOLD=${similarity}
SCRAPE_DELAY_MS=${delay}

# Discord Bot Integration
DISCORD_BOT_TOKEN=${botToken}
DISCORD_BOT_ID=${botId}
`;

  fs.writeFileSync(envPath, envContent);
  console.log('\n✅ .env file created successfully!');

  // Update config.js
  const configPath = path.join(__dirname, '..', 'public', 'scripts', 'config.js');
  if (fs.existsSync(configPath)) {
    let configContent = fs.readFileSync(configPath, 'utf8');
    
    configContent = configContent.replace(
      /apiKey: ".*"/,
      `apiKey: "${apiKey}"`
    );
    configContent = configContent.replace(
      /authDomain: ".*"/,
      `authDomain: "${authDomain}"`
    );
    configContent = configContent.replace(
      /projectId: ".*"/,
      `projectId: "${projectId}"`
    );
    configContent = configContent.replace(
      /storageBucket: ".*"/,
      `storageBucket: "${storageBucket}"`
    );
    configContent = configContent.replace(
      /messagingSenderId: ".*"/,
      `messagingSenderId: "${messagingSenderId}"`
    );
    configContent = configContent.replace(
      /appId: ".*"/,
      `appId: "${appId}"`
    );
    configContent = configContent.replace(
      /botId: ".*"/,
      `botId: "${botId}"`
    );

    fs.writeFileSync(configPath, configContent);
    console.log('✅ config.js updated successfully!');
  }

  console.log('\n📝 Next Steps:\n');
  console.log('1. Run: firebase login');
  console.log('2. Run: firebase init (select Firestore, Storage, Hosting)');
  console.log('3. Run: firebase deploy --only firestore:rules,storage:rules');
  console.log('4. Run: npm run scrape (to start scraping characters)');
  console.log('5. Run: npm run serve (to test locally)');
  console.log('6. Run: npm run deploy (to deploy to Firebase)\n');

  rl.close();
}

setup().catch(console.error);
