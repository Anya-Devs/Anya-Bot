#!/usr/bin/env node
/**
 * Generate OG Banner Image
 * Creates a 1200x630 banner for social media embeds
 * 
 * Usage: node scripts/generate-og-banner.js
 * 
 * Note: This creates an HTML template. Take a screenshot or use a service.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(__dirname, '..', 'public');

// Create an HTML template that can be screenshot
const bannerHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      width: 1200px;
      height: 630px;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%);
      font-family: 'Segoe UI', system-ui, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      position: relative;
    }
    .glow {
      position: absolute;
      width: 400px;
      height: 400px;
      background: radial-gradient(circle, rgba(255,107,157,0.3) 0%, transparent 70%);
      top: -100px;
      right: -100px;
    }
    .glow2 {
      position: absolute;
      width: 300px;
      height: 300px;
      background: radial-gradient(circle, rgba(147,51,234,0.2) 0%, transparent 70%);
      bottom: -50px;
      left: -50px;
    }
    .container {
      display: flex;
      align-items: center;
      gap: 60px;
      z-index: 1;
    }
    .avatar {
      width: 200px;
      height: 200px;
      border-radius: 50%;
      border: 4px solid rgba(255,107,157,0.5);
      box-shadow: 0 0 60px rgba(255,107,157,0.4);
    }
    .content {
      max-width: 700px;
    }
    .title {
      font-size: 72px;
      font-weight: 800;
      background: linear-gradient(135deg, #FF6B9D 0%, #c084fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 20px;
    }
    .subtitle {
      font-size: 28px;
      color: #a0a0b0;
      margin-bottom: 30px;
    }
    .features {
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
    }
    .feature {
      background: rgba(255,255,255,0.1);
      padding: 12px 24px;
      border-radius: 30px;
      color: #fff;
      font-size: 18px;
      border: 1px solid rgba(255,107,157,0.3);
    }
    .url {
      position: absolute;
      bottom: 30px;
      left: 50%;
      transform: translateX(-50%);
      color: #666;
      font-size: 20px;
    }
  </style>
</head>
<body>
  <div class="glow"></div>
  <div class="glow2"></div>
  <div class="container">
    <img src="avatar.png" alt="Anya Bot" class="avatar">
    <div class="content">
      <h1 class="title">Anya Bot</h1>
      <p class="subtitle">Your Ultimate Discord Companion</p>
      <div class="features">
        <span class="feature">🎮 100+ Commands</span>
        <span class="feature">🔍 Pokémon Detection</span>
        <span class="feature">📺 Anime Lookup</span>
        <span class="feature">🎉 Fun & Games</span>
      </div>
    </div>
  </div>
  <p class="url">anya-bot-1fe76.web.app</p>
</body>
</html>`;

const outputPath = path.join(publicDir, 'og-banner.html');
fs.writeFileSync(outputPath, bannerHtml);

console.log('✅ Created og-banner.html in public folder');
console.log('');
console.log('📸 To create the banner image:');
console.log('   1. Open: file://' + outputPath.replace(/\\\\/g, '/'));
console.log('   2. Take a screenshot (1200x630)');
console.log('   3. Save as: public/og-banner.png');
console.log('');
console.log('Or use a screenshot service like:');
console.log('   https://screenshot.rocks/');
console.log('   https://www.screenshotmachine.com/');
