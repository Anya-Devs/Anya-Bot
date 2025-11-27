import fs from 'fs';
import path from 'path';
import https from 'https';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BOT_ID = '1234247716243112100';
const OUTPUT_PATH = path.join(__dirname, '..', 'public', 'avatar.png');

/**
 * Download bot avatar from Discord API
 */
async function downloadAvatar() {
  console.log('🔍 Fetching bot information from Discord API...');
  
  try {
    // Fetch bot data from Discord API
    const response = await fetch(`https://discord.com/api/v10/applications/${BOT_ID}/rpc`);
    
    if (!response.ok) {
      throw new Error(`Discord API returned ${response.status}`);
    }
    
    const botData = await response.json();
    
    if (!botData.icon) {
      console.warn('⚠️  No avatar found for bot, using existing avatar.png');
      return;
    }
    
    const avatarUrl = `https://cdn.discordapp.com/app-icons/${BOT_ID}/${botData.icon}.png?size=512`;
    console.log(`📥 Downloading avatar from: ${avatarUrl}`);
    
    // Download the avatar
    const avatarResponse = await fetch(avatarUrl);
    if (!avatarResponse.ok) {
      throw new Error(`Failed to download avatar: ${avatarResponse.status}`);
    }
    
    const buffer = await avatarResponse.arrayBuffer();
    
    // Save to public directory
    fs.writeFileSync(OUTPUT_PATH, Buffer.from(buffer));
    console.log(`✅ Avatar saved to: ${OUTPUT_PATH}`);
    
  } catch (error) {
    console.error('❌ Failed to download bot avatar:', error.message);
    console.log('⚠️  Build will continue with existing avatar.png');
  }
}

// Run the download
downloadAvatar();
