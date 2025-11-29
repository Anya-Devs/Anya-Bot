/**
 * Auto-generate updates.json by scanning the codebase
 * 
 * Detects:
 * - New bot commands from cog files
 * - Package.json version changes
 * - New website features
 * 
 * Run: node scripts/generate-updates.js
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const UPDATES_FILE = path.join(__dirname, '../public/updates.json');
const CACHE_FILE = path.join(__dirname, '../.feature-cache.json');
const BOT_COGS_PATH = path.join(__dirname, '../../bot/cogs');
const WEBSITE_PAGES_PATH = path.join(__dirname, '../src/pages');

// Feature detection patterns
const COMMAND_PATTERNS = {
  python: /@commands\.command|@app_commands\.command|async def (\w+)\(.*ctx/g,
  decorator: /@commands\.command\(name=['"](\w+)['"]\)/g,
};

/**
 * Scan Python cog files for commands
 */
function scanBotCommands() {
  const commands = {};
  
  if (!fs.existsSync(BOT_COGS_PATH)) {
    console.log('⚠️  Bot cogs path not found:', BOT_COGS_PATH);
    return commands;
  }

  const files = fs.readdirSync(BOT_COGS_PATH).filter(f => f.endsWith('.py'));
  
  for (const file of files) {
    const cogName = file.replace('.py', '');
    const content = fs.readFileSync(path.join(BOT_COGS_PATH, file), 'utf-8');
    
    // Extract command names
    const cmdMatches = content.matchAll(/@commands\.command\(name=['"](\w+)['"]\)|async def (\w+)\(.*ctx/g);
    const cmds = [];
    
    for (const match of cmdMatches) {
      const cmdName = match[1] || match[2];
      if (cmdName && !cmdName.startsWith('_') && cmdName !== 'cog') {
        cmds.push(cmdName);
      }
    }
    
    if (cmds.length > 0) {
      commands[cogName] = {
        commands: [...new Set(cmds)],
        lastModified: fs.statSync(path.join(BOT_COGS_PATH, file)).mtime.toISOString()
      };
    }
  }
  
  return commands;
}

/**
 * Scan website pages
 */
function scanWebsiteFeatures() {
  const features = {};
  
  if (!fs.existsSync(WEBSITE_PAGES_PATH)) {
    return features;
  }

  const files = fs.readdirSync(WEBSITE_PAGES_PATH).filter(f => f.endsWith('.tsx'));
  
  for (const file of files) {
    const pageName = file.replace('.tsx', '');
    const stat = fs.statSync(path.join(WEBSITE_PAGES_PATH, file));
    features[pageName] = {
      lastModified: stat.mtime.toISOString()
    };
  }
  
  return features;
}

/**
 * Get git info for a file
 */
function getGitInfo(filePath) {
  try {
    const lastCommit = execSync(`git log -1 --format="%ai|%s" -- "${filePath}"`, { 
      encoding: 'utf-8',
      cwd: path.dirname(filePath)
    }).trim();
    
    if (lastCommit) {
      const [date, message] = lastCommit.split('|');
      return { date: new Date(date).toISOString(), message };
    }
  } catch (e) {
    // Git not available or file not tracked
  }
  return null;
}

/**
 * Load previous feature cache
 */
function loadCache() {
  if (fs.existsSync(CACHE_FILE)) {
    return JSON.parse(fs.readFileSync(CACHE_FILE, 'utf-8'));
  }
  return { commands: {}, features: {}, version: '0.0.0' };
}

/**
 * Save feature cache
 */
function saveCache(cache) {
  fs.writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2));
}

/**
 * Detect changes between old and new features
 */
function detectChanges(oldData, newData) {
  const changes = {
    added: [],
    modified: [],
    removed: []
  };

  // Check for new/modified
  for (const [key, value] of Object.entries(newData)) {
    if (!oldData[key]) {
      changes.added.push({ name: key, ...value });
    } else if (JSON.stringify(oldData[key]) !== JSON.stringify(value)) {
      changes.modified.push({ name: key, ...value });
    }
  }

  // Check for removed
  for (const key of Object.keys(oldData)) {
    if (!newData[key]) {
      changes.removed.push(key);
    }
  }

  return changes;
}

/**
 * Generate update entry from changes
 */
function generateUpdateEntry(commandChanges, featureChanges) {
  const now = new Date();
  const monthYear = now.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  
  const highlights = [];
  let title = '';
  let description = '';
  let type = 'improvement';

  // Prioritize based on what changed
  if (commandChanges.added.length > 0) {
    const newCmds = commandChanges.added.flatMap(c => c.commands || []);
    title = `🎉 ${newCmds.length} New Commands`;
    description = `Added new commands: ${commandChanges.added.map(c => c.name).join(', ')}`;
    highlights.push(...newCmds.slice(0, 3).map(c => `New: .${c}`));
    type = 'feature';
  } else if (commandChanges.modified.length > 0) {
    title = '⚡ Command Updates';
    description = `Updated ${commandChanges.modified.length} command module(s)`;
    highlights.push(...commandChanges.modified.map(c => `Updated: ${c.name}`).slice(0, 3));
    type = 'improvement';
  } else if (featureChanges.added.length > 0) {
    title = '✨ Website Updates';
    description = `New pages and features added`;
    highlights.push(...featureChanges.added.map(f => `New: ${f.name} page`).slice(0, 3));
    type = 'feature';
  } else {
    return null; // No significant changes
  }

  // Get version from package.json
  const pkgPath = path.join(__dirname, '../package.json');
  const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
  
  return {
    version: pkg.version,
    date: monthYear,
    title,
    description,
    type,
    highlights,
    autoGenerated: true,
    timestamp: now.toISOString()
  };
}

/**
 * Main function
 */
function main() {
  console.log('🔍 Scanning codebase for features...\n');

  // Load existing data
  const cache = loadCache();
  const existingUpdates = fs.existsSync(UPDATES_FILE) 
    ? JSON.parse(fs.readFileSync(UPDATES_FILE, 'utf-8'))
    : { updates: [], upcomingFeatures: [] };

  // Scan current state
  const currentCommands = scanBotCommands();
  const currentFeatures = scanWebsiteFeatures();

  console.log('📦 Bot Commands Found:');
  for (const [cog, data] of Object.entries(currentCommands)) {
    console.log(`   ${cog}: ${data.commands.length} commands`);
  }

  console.log('\n📄 Website Pages Found:');
  for (const page of Object.keys(currentFeatures)) {
    console.log(`   ${page}`);
  }

  // Detect changes
  const commandChanges = detectChanges(cache.commands || {}, currentCommands);
  const featureChanges = detectChanges(cache.features || {}, currentFeatures);

  console.log('\n🔄 Changes Detected:');
  console.log(`   Commands: +${commandChanges.added.length} added, ~${commandChanges.modified.length} modified`);
  console.log(`   Features: +${featureChanges.added.length} added, ~${featureChanges.modified.length} modified`);

  // Generate new update if there are changes
  const hasChanges = commandChanges.added.length > 0 || 
                     commandChanges.modified.length > 0 || 
                     featureChanges.added.length > 0;

  if (hasChanges) {
    const newUpdate = generateUpdateEntry(commandChanges, featureChanges);
    
    if (newUpdate) {
      // Check if we already have this version
      const existingVersionIdx = existingUpdates.updates.findIndex(
        u => u.version === newUpdate.version && u.autoGenerated
      );

      if (existingVersionIdx >= 0) {
        // Update existing auto-generated entry
        existingUpdates.updates[existingVersionIdx] = newUpdate;
        console.log(`\n📝 Updated existing entry for v${newUpdate.version}`);
      } else {
        // Add new entry at the top
        existingUpdates.updates.unshift(newUpdate);
        console.log(`\n✅ Added new update: ${newUpdate.title}`);
      }

      // Save updates
      fs.writeFileSync(UPDATES_FILE, JSON.stringify(existingUpdates, null, 2));
      console.log('💾 Saved to public/updates.json');
    }
  } else {
    console.log('\n✨ No new changes to report');
  }

  // Update cache
  saveCache({
    commands: currentCommands,
    features: currentFeatures,
    lastScan: new Date().toISOString()
  });

  console.log('\n✅ Done!');
}

main();
