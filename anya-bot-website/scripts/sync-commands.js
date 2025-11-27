#!/usr/bin/env node

/**
 * Sync commands from Python cog files to commands.json
 * 
 * Features:
 * - Detects NEW commands added to bot
 * - Detects DELETED commands removed from bot
 * - Detects RENAMED commands (removed + added)
 * - Preserves manually written descriptions/examples
 * - Shows diff before applying changes
 * 
 * Usage:
 *   node sync-commands.js          # Show what would change (dry run)
 *   node sync-commands.js --apply  # Apply changes to commands.json
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BOT_COGS_DIR = path.join(__dirname, '../../bot/cogs');
const COMMANDS_JSON = path.join(__dirname, '../public/commands.json');

const APPLY_MODE = process.argv.includes('--apply');

// Categories to exclude from sync (hidden/disabled features)
const EXCLUDED_CATEGORIES = ['CelestialTribute', 'Sync', 'Help', 'Halloween'];

// Commands to preserve even if not found in bot (manually documented)
const PRESERVED_COMMANDS = {
  'Fun': ['Action Commands'],  // Dynamic commands documented manually
};

// Specific commands to exclude from syncing (hidden/deprecated)
const EXCLUDED_COMMANDS = [
  'pt shinychannel',
  'pt shinychannel log',
  'pt shinychannel log remove',
  'notetaker',
  'notetaker clear',
  'note',
  'quest removeall',
  'quest setlimit', 
  'quest serverquest'
];

// ANSI colors
const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  reset: '\x1b[0m',
  bold: '\x1b[1m'
};

console.log(`\n${colors.bold}🔄 Command Sync Tool${colors.reset}`);
console.log(`${colors.cyan}Mode: ${APPLY_MODE ? 'APPLY CHANGES' : 'DRY RUN (preview)'}${colors.reset}\n`);

/**
 * Build a mapping of group identifiers to their full command paths
 */
function buildGroupMap(content) {
  const groupMap = {};
  let match;

  // Root groups: @commands.group(name="pt")
  const rootGroupRegex = /@(?:commands\.group|bot\.group)\s*\(([\s\S]*?)\)\s*async\s+def\s+(\w+)\s*\(/g;
  while ((match = rootGroupRegex.exec(content)) !== null) {
    const decoratorArgs = match[1];
    const funcName = match[2];
    const nameMatch = decoratorArgs.match(/name\s*=\s*["']([^"']+)["']/);
    groupMap[funcName] = nameMatch ? nameMatch[1] : funcName;
  }

  // app_commands.Group: quest_group = app_commands.Group(name="quest")
  const appGroupRegex = /(\w+)\s*=\s*app_commands\.Group\s*\(\s*name\s*=\s*["']([^"']+)["']/g;
  while ((match = appGroupRegex.exec(content)) !== null) {
    groupMap[match[1]] = match[2];
  }

  // Nested groups: @pt.group(name="config")
  const nestedGroupRegex = /@(\w+)\.group\s*\(([\s\S]*?)\)\s*async\s+def\s+(\w+)\s*\(/g;
  while ((match = nestedGroupRegex.exec(content)) !== null) {
    const parentId = match[1];
    const decoratorArgs = match[2];
    const funcName = match[3];
    const nameMatch = decoratorArgs.match(/name\s*=\s*["']([^"']+)["']/);
    const subName = nameMatch ? nameMatch[1] : funcName;
    const parentPath = groupMap[parentId] || parentId;
    groupMap[funcName] = `${parentPath} ${subName}`;
  }

  return groupMap;
}

/**
 * Extract aliases from decorator arguments
 */
function extractAliases(decoratorArgs) {
  const aliasesMatch = decoratorArgs.match(/aliases\s*=\s*\[([^\]]*)\]/);
  if (aliasesMatch && aliasesMatch[1].trim()) {
    return aliasesMatch[1]
      .split(',')
      .map(a => a.trim().replace(/["']/g, ''))
      .filter(a => a);
  }
  return [];
}

/**
 * Parse a single cog file and return all commands found
 */
function parseCogFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const groupMap = buildGroupMap(content);
  const commands = new Map();

  // Standalone commands: @commands.command(name="imagine")
  const standaloneRegex = /@(?:commands\.command|app_commands\.command|commands\.hybrid_command)\s*\(([\s\S]*?)\)\s*async\s+def\s+(\w+)\s*\(/g;
  let match;

  while ((match = standaloneRegex.exec(content)) !== null) {
    const decoratorArgs = match[1];
    const funcName = match[2];

    // Skip hidden commands
    if (decoratorArgs.includes('hidden=True') || decoratorArgs.includes('hidden = True')) continue;

    const nameMatch = decoratorArgs.match(/name\s*=\s*["']([^"']+)["']/);
    let cmdName = nameMatch ? nameMatch[1] : funcName;
    if (cmdName.startsWith('commands ')) cmdName = cmdName.replace('commands ', '');

    commands.set(cmdName, {
      aliases: extractAliases(decoratorArgs),
      funcName
    });
  }

  // Grouped commands: @pt.command(name="tp")
  const groupedRegex = /@(\w+)\.command\s*\(([\s\S]*?)\)\s*async\s+def\s+(\w+)\s*\(/g;

  while ((match = groupedRegex.exec(content)) !== null) {
    const groupId = match[1];
    const decoratorArgs = match[2];
    const funcName = match[3];

    // Skip hidden commands
    if (decoratorArgs.includes('hidden=True') || decoratorArgs.includes('hidden = True')) continue;

    const basePath = groupMap[groupId] || groupId;
    const nameMatch = decoratorArgs.match(/name\s*=\s*["']([^"']+)["']/);
    const subName = nameMatch ? nameMatch[1] : funcName;
    let fullName = `${basePath} ${subName}`;
    if (fullName.startsWith('commands ')) fullName = fullName.replace('commands ', '');

    commands.set(fullName, {
      aliases: extractAliases(decoratorArgs),
      funcName
    });
  }

  // Also add group commands themselves (e.g., "anime", "pt", "quest")
  for (const [funcName, groupPath] of Object.entries(groupMap)) {
    if (!groupPath.includes(' ')) { // Only root groups
      commands.set(groupPath, {
        aliases: [],
        funcName,
        isGroup: true
      });
    }
  }

  return commands;
}

/**
 * Get category name from cog class
 */
function getCategoryName(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const cogClassMatch = content.match(/class\s+(\w+)\s*\(/);
  if (cogClassMatch) {
    // Map class names to display names
    const classNameMap = {
      'Ai': 'Ai',
      'Anime': 'Anime',
      'Fun': 'Fun',
      'Information': 'Information',
      'Moderation': 'Moderation',
      'Pokemon': 'Pokemon',
      'PoketwoCommands': 'Pokemon',
      'Quest': 'Quest',
      'Quest_Slash': 'Quest',
      'System': 'System',
      'Help': 'Help',
      'Sync': 'Sync'
    };
    return classNameMap[cogClassMatch[1]] || cogClassMatch[1];
  }
  const fileName = path.basename(filePath, '.py');
  return fileName.charAt(0).toUpperCase() + fileName.slice(1);
}

/**
 * Generate a default description for a command
 */
function generateDescription(cmdName) {
  const parts = cmdName.split(' ');
  const last = parts[parts.length - 1];
  
  if (parts.length > 1) {
    return `Execute the ${cmdName} command`;
  }
  
  const defaults = {
    'ping': 'Check Discord API latency',
    'uptime': 'Display how long the bot has been running',
    'memory': 'Show current bot memory usage',
    'credit': 'Show bot credits and developer information',
    'about': 'Get information about the server and bot',
    'server': 'Display server information and statistics',
    'pfp': 'Get a user\'s profile picture',
    'banner': 'Get a user\'s banner image',
    'invite': 'Get the bot\'s invite link',
    'perms': 'Check permissions in the server',
    'roles': 'List all roles in the server',
    'leaderboard': 'Show the server leaderboard',
    'reviews': 'View or leave reviews',
    'ban': 'Ban a user from the server',
    'unban': 'Unban a user from the server',
    'timeout': 'Timeout a user',
    'untimeout': 'Remove timeout from a user',
    'purge': 'Bulk delete messages',
    'log': 'Set moderation log channel',
    '8ball': 'Ask the magic 8-ball a question',
    'memo': 'Memory game with emojis',
    'qna': 'Set up Q&A channels',
    'riddle': 'Riddle system',
    'imagine': 'Generate AI images',
    'vision': 'Analyze images with AI',
    'pokedex': 'Look up Pokémon information',
    'pt': 'Pokétwo helper commands',
    'anime': 'Anime command group',
    'manga': 'Manga command group',
    'quest': 'Quest system commands',
    'profile': 'View your profile',
    'inventory': 'View your inventory',
    'balance': 'Check your balance',
    'shop': 'Browse the shop',
    'ticket': 'Support ticket system',
    'redirect': 'Set quest redirect channels'
  };
  
  return defaults[last] || `Execute the ${cmdName} command`;
}

/**
 * Main sync function
 */
function main() {
  if (!fs.existsSync(BOT_COGS_DIR)) {
    console.error(`${colors.red}❌ Bot cogs directory not found: ${BOT_COGS_DIR}${colors.reset}`);
    process.exit(1);
  }

  // Load existing commands.json
  let existingData = {};
  if (fs.existsSync(COMMANDS_JSON)) {
    existingData = JSON.parse(fs.readFileSync(COMMANDS_JSON, 'utf8'));
  }

  // Parse all cog files
  const cogFiles = fs.readdirSync(BOT_COGS_DIR)
    .filter(f => f.endsWith('.py') && f !== '__init__.py')
    .map(f => path.join(BOT_COGS_DIR, f));

  // Collect all commands from bot by category
  const botCommands = new Map(); // category -> Map<cmdName, data>

  for (const cogFile of cogFiles) {
    const category = getCategoryName(cogFile);
    
    // Skip excluded categories
    if (EXCLUDED_CATEGORIES.includes(category)) {
      console.log(`${colors.yellow}⏭️  Skipping excluded category: ${category}${colors.reset}`);
      continue;
    }
    
    const commands = parseCogFile(cogFile);
    
    if (!botCommands.has(category)) {
      botCommands.set(category, new Map());
    }
    
    const catMap = botCommands.get(category);
    for (const [name, data] of commands) {
      // Skip excluded commands
      if (EXCLUDED_COMMANDS.includes(name)) continue;
      catMap.set(name, data);
    }
  }

  // Track changes
  const changes = {
    added: [],    // { category, command }
    removed: [],  // { category, command }
    aliasChanged: [] // { category, command, oldAliases, newAliases }
  };

  // Build new commands object
  const newData = {};

  // Process each category from bot
  for (const [category, commands] of botCommands) {
    if (commands.size === 0) continue;
    
    const existingCat = existingData[category] || {};
    newData[category] = {};

    for (const [cmdName, cmdData] of commands) {
      const existing = existingCat[cmdName];

      if (existing) {
        // Command exists - preserve manual edits
        newData[category][cmdName] = {
          description: existing.description || generateDescription(cmdName),
          example: existing.example || `.${cmdName}`,
          aliases: cmdData.aliases.length > 0 ? cmdData.aliases : (existing.aliases || []),
          related_commands: existing.related_commands || ''
        };

        // Check if aliases changed
        const oldAliases = (existing.aliases || []).sort().join(',');
        const newAliases = cmdData.aliases.sort().join(',');
        if (oldAliases !== newAliases && cmdData.aliases.length > 0) {
          changes.aliasChanged.push({ category, command: cmdName, oldAliases: existing.aliases, newAliases: cmdData.aliases });
        }
      } else {
        // New command
        changes.added.push({ category, command: cmdName });
        newData[category][cmdName] = {
          description: generateDescription(cmdName),
          example: `.${cmdName}`,
          aliases: cmdData.aliases,
          related_commands: ''
        };
      }
    }
    
    // Preserve manually added commands for this category
    const preservedList = PRESERVED_COMMANDS[category] || [];
    for (const preserved of preservedList) {
      if (existingCat[preserved] && !newData[category][preserved]) {
        newData[category][preserved] = existingCat[preserved];
      }
    }
  }

  // Check for removed commands (excluding preserved ones and group parents)
  for (const [category, commands] of Object.entries(existingData)) {
    // Skip excluded categories entirely
    if (EXCLUDED_CATEGORIES.includes(category)) continue;
    
    const botCat = botCommands.get(category);
    const preservedList = PRESERVED_COMMANDS[category] || [];
    
    for (const cmdName of Object.keys(commands)) {
      // Skip preserved commands
      if (preservedList.includes(cmdName)) continue;
      
      // Skip group parent commands - they are documentation entries for command groups
      // Check if any bot command starts with this name + space (meaning it's a parent group)
      const isGroupParent = botCat && [...botCat.keys()].some(k => k.startsWith(cmdName + ' '));
      if (isGroupParent) {
        // Preserve the group parent entry
        if (!newData[category][cmdName]) {
          newData[category][cmdName] = commands[cmdName];
        }
        continue;
      }
      
      if (!botCat || !botCat.has(cmdName)) {
        changes.removed.push({ category, command: cmdName });
      }
    }
  }
  
  // Also preserve existing categories that have manual entries
  for (const [category, commands] of Object.entries(existingData)) {
    if (EXCLUDED_CATEGORIES.includes(category)) continue;
    if (!newData[category]) {
      newData[category] = commands;
    }
  }

  // Print diff
  console.log(`${colors.bold}📊 Sync Summary${colors.reset}\n`);

  if (changes.added.length > 0) {
    console.log(`${colors.green}➕ NEW commands (${changes.added.length}):${colors.reset}`);
    for (const { category, command } of changes.added) {
      console.log(`   ${colors.green}+ ${category} → ${command}${colors.reset}`);
    }
    console.log();
  }

  if (changes.removed.length > 0) {
    console.log(`${colors.red}➖ REMOVED commands (${changes.removed.length}):${colors.reset}`);
    for (const { category, command } of changes.removed) {
      console.log(`   ${colors.red}- ${category} → ${command}${colors.reset}`);
    }
    console.log();
  }

  if (changes.aliasChanged.length > 0) {
    console.log(`${colors.yellow}🔄 ALIAS changes (${changes.aliasChanged.length}):${colors.reset}`);
    for (const { category, command, oldAliases, newAliases } of changes.aliasChanged) {
      console.log(`   ${colors.yellow}~ ${category} → ${command}: [${oldAliases}] → [${newAliases}]${colors.reset}`);
    }
    console.log();
  }

  const totalChanges = changes.added.length + changes.removed.length + changes.aliasChanged.length;

  if (totalChanges === 0) {
    console.log(`${colors.green}✅ Everything is in sync! No changes needed.${colors.reset}\n`);
    return;
  }

  // Count totals
  const totalCommands = Object.values(newData).reduce((sum, cat) => sum + Object.keys(cat).length, 0);
  console.log(`${colors.cyan}📈 Total: ${Object.keys(newData).length} categories, ${totalCommands} commands${colors.reset}\n`);

  if (APPLY_MODE) {
    // Write changes
    fs.writeFileSync(COMMANDS_JSON, JSON.stringify(newData, null, 2));
    console.log(`${colors.green}${colors.bold}✅ Changes applied to commands.json${colors.reset}\n`);
  } else {
    console.log(`${colors.yellow}${colors.bold}⚠️  DRY RUN - No changes made${colors.reset}`);
    console.log(`${colors.cyan}   Run with --apply to save changes:${colors.reset}`);
    console.log(`   ${colors.bold}node scripts/sync-commands.js --apply${colors.reset}\n`);
  }
}

main();
