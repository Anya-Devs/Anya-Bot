/**
 * Copy commands.json from bot data to website public folder
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sourceFile = path.join(__dirname, '../../data/commands/help/commands.json');
const destFile = path.join(__dirname, '../public/commands.json');

try {
  // Ensure public directory exists
  const publicDir = path.dirname(destFile);
  if (!fs.existsSync(publicDir)) {
    fs.mkdirSync(publicDir, { recursive: true });
  }

  // Copy the file
  fs.copyFileSync(sourceFile, destFile);
  console.log('✅ Commands copied successfully!');
  console.log(`   From: ${sourceFile}`);
  console.log(`   To: ${destFile}`);
} catch (error) {
  console.error('❌ Error copying commands:', error.message);
  process.exit(1);
}
