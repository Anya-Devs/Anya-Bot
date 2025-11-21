#!/usr/bin/env node

/**
 * Batch scrape characters from JSON file
 */

import { CharacterScraper } from '../src/scraper/index.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function batchScrape() {
  console.log('🎴 Starting batch character scraping...\n');

  // Load character data
  const dataPath = path.join(__dirname, '..', 'data', 'example-characters.json');
  
  if (!fs.existsSync(dataPath)) {
    console.error('❌ Character data file not found:', dataPath);
    console.log('Please create a JSON file with character data.');
    process.exit(1);
  }

  const charactersData = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
  console.log(`📋 Loaded ${charactersData.length} characters to scrape\n`);

  // Initialize scraper
  const scraper = new CharacterScraper();

  // Scrape all characters
  const results = await scraper.scrapeMultipleCharacters(charactersData);

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('📊 SCRAPING SUMMARY');
  console.log('='.repeat(60));

  const successful = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;

  console.log(`\n✅ Successful: ${successful}`);
  console.log(`❌ Failed: ${failed}`);
  console.log(`📊 Total: ${results.length}\n`);

  if (failed > 0) {
    console.log('Failed characters:');
    results
      .filter(r => !r.success)
      .forEach(r => {
        console.log(`  - ${r.name}: ${r.error}`);
      });
  }

  console.log('\n✨ Batch scraping completed!\n');

  // Save results
  const resultsPath = path.join(__dirname, '..', 'data', 'scrape-results.json');
  fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));
  console.log(`📝 Results saved to: ${resultsPath}\n`);
}

batchScrape().catch(error => {
  console.error('❌ Batch scraping failed:', error);
  process.exit(1);
});
