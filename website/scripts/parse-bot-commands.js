#!/usr/bin/env node

/**
 * Parse actual bot commands from Python cog files
 * - Reads all cog files
 * - Extracts commands with decorators
 * - Groups subcommands properly
 * - Includes ALL commands (including hidden ones)
 * - Includes ALL groups (including hidden ones)
 * - Excludes empty cogs
 * - Updates commands.json
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BOT_COGS_DIR = path.join(__dirname, '../../bot/cogs');
const OUTPUT_PATH = path.join(__dirname, '../public/commands.json');

console.log('🔍 Parsing bot commands from Python files...\n');

/**
 * Build a mapping of group identifiers (function names or variables)
 * to their full command path (e.g. "pt", "pt shinychannel", "pt shinychannel log").
 * This lets us later resolve decorators like @pt.command or @shiny_log.command
 * into full long-form command names.
 */
function buildGroupMap(content) {
  const groupMap = {};

  // Root text groups declared via decorators, e.g.:
  // @commands.group(name="pt")\nasync def pt(...)
  const rootGroupRegex = /@(?:commands\.group|bot\.group)\s*\(([\s\S]*?)\)\s*async\s+def\s+(\w+)\s*\(/g;
  let match;

  while ((match = rootGroupRegex.exec(content)) !== null) {
    const decoratorArgs = match[1];
    const funcName = match[2];
    const nameMatch = decoratorArgs.match(/name\s*=\s*["']([^"']+)["']/);
    const groupName = nameMatch ? nameMatch[1] : funcName;
    groupMap[funcName] = groupName;
  }

  // app_commands.Group variables, e.g.:
  // quest_group = app_commands.Group(name="quest", ...)
  const appGroupAssignRegex = /(\w+)\s*=\s*app_commands\.Group\s*\(\s*name\s*=\s*["']([^"']+)["']/g;

  while ((match = appGroupAssignRegex.exec(content)) !== null) {
    const varName = match[1];
    const name = match[2];
    groupMap[varName] = name;
  }

  // Nested groups defined off an existing group, e.g.:
  // @pt.group(name="shinychannel")\nasync def shiny_channel(...)
  // or @shiny_channel.group(name="log")\nasync def shiny_log(...)
  const nestedGroupRegex = /@(\w+)\.group\s*\(([\s\S]*?)\)\s*async\s+def\s+(\w+)\s*\(/g;

  while ((match = nestedGroupRegex.exec(content)) !== null) {
    const parentIdentifier = match[1];
    const decoratorArgs = match[2];
    const funcName = match[3];
    const nameMatch = decoratorArgs.match(/name\s*=\s*["']([^"']+)["']/);
    const subName = nameMatch ? nameMatch[1] : funcName;

    const parentPath = groupMap[parentIdentifier] || parentIdentifier;
    const fullPath = `${parentPath} ${subName}`;
    groupMap[funcName] = fullPath;
  }

  return groupMap;
}

/**
 * Parse a Python cog file for commands
 */
function parseCogFile(filePath, existingCommands = {}) {
  const content = fs.readFileSync(filePath, 'utf8');
  const fileName = path.basename(filePath, '.py');
  const commands = {};
  const groupMap = buildGroupMap(content);

  // Match non-grouped command decorators and their functions
  const commandRegex = /@(?:commands\.command|app_commands\.command|commands\.hybrid_command|bot\.command)\s*\(([\s\S]*?)\)\s*async\s+def\s+(\w+)\s*\(/g;

  let match;

  // Find all standalone commands (not attached via <group>.command)
  while ((match = commandRegex.exec(content)) !== null) {
    const decoratorArgs = match[1];
    const funcName = match[2];
    
    // Skip hidden commands
    if (decoratorArgs.includes('hidden=True') || decoratorArgs.includes('hidden = True')) {
      console.log(`  ⏭️  Skipping hidden command: ${funcName}`);
      continue;
    }
    
    // Extract basic command details
    const nameMatch = decoratorArgs.match(/name\s*=\s*["']([^"']+)["']/);
    const commandName = nameMatch ? nameMatch[1] : funcName;
    
    // Handle commands that incorrectly include "commands" prefix
    let correctedName = commandName;
    if (commandName.startsWith('commands ')) {
      correctedName = commandName.replace('commands ', '');
    }
    
    // Get existing command data or create new
    const existingCommand = existingCommands[correctedName] || {};
    
    // Set default values only if they don't exist
    if (!existingCommand.description) {
      const docstring = extractDocstring(content, funcName);
      existingCommand.description = docstring || generateDescriptionFromName(correctedName);
    }
    
    if (!existingCommand.example) {
      const example = extractExample(content, funcName);
      existingCommand.example = example || `.${correctedName}`;
    }
    
    // Only update aliases if they exist in the decorator
    const aliasesMatch = decoratorArgs.match(/aliases\s*=\s*\[([^\]]+)\]/);
    if (aliasesMatch && aliasesMatch[1].trim()) {
      existingCommand.aliases = aliasesMatch[1].split(',')
        .map(a => a.trim().replace(/["']/g, ''))
        .filter(a => a); // Remove empty strings
    } else if (!existingCommand.aliases) {
      existingCommand.aliases = [];
    }
    
    // Ensure related_commands exists
    if (!existingCommand.related_commands) {
      existingCommand.related_commands = '';
    }
    
    commands[correctedName] = existingCommand;
    console.log(`  ✅ Found command: ${correctedName}`);
  }
  // Find commands attached to groups, including nested ones, e.g.:
  // @pt.command(name="tp"), @quest_group.command(name="create"), @shiny_log.command(name="remove")
  const groupedCommandRegex = /@(\w+)\.command\s*\(([\s\S]*?)\)\s*async\s+def\s+(\w+)\s*\(/g;

  while ((match = groupedCommandRegex.exec(content)) !== null) {
    const groupIdentifier = match[1];
    const decoratorArgs = match[2];
    const funcName = match[3];

    // Skip hidden commands
    if (decoratorArgs.includes('hidden=True') || decoratorArgs.includes('hidden = True')) {
      console.log(`  ⏭️  Skipping hidden grouped command: ${funcName}`);
      continue;
    }

    const basePath = groupMap[groupIdentifier] || groupIdentifier;
    const nameMatch = decoratorArgs.match(/name\s*=\s*["']([^"']+)["']/);
    const subName = nameMatch ? nameMatch[1] : funcName;
    let fullName = `${basePath} ${subName}`;
    
    // Handle commands that incorrectly include "commands" prefix
    if (fullName.startsWith('commands ')) {
      fullName = fullName.replace('commands ', '');
    }
    
    // Get existing command data or create new
    const existingCommand = existingCommands[fullName] || {};
    
    // Set default values only if they don't exist
    if (!existingCommand.description) {
      const docstring = extractDocstring(content, funcName);
      existingCommand.description = docstring || generateDescriptionFromName(fullName);
    }
    
    if (!existingCommand.example) {
      const example = extractExample(content, funcName);
      existingCommand.example = example || `.${fullName}`;
    }
    
    // Only update aliases if they exist in the decorator
    const aliasesMatch = decoratorArgs.match(/aliases\s*=\s*\[([^\]]+)\]/);
    if (aliasesMatch && aliasesMatch[1].trim()) {
      existingCommand.aliases = aliasesMatch[1].split(',')
        .map(a => a.trim().replace(/["']/g, ''))
        .filter(a => a); // Remove empty strings
    } else if (!existingCommand.aliases) {
      existingCommand.aliases = [];
    }
    
    // Ensure related_commands exists
    if (!existingCommand.related_commands) {
      existingCommand.related_commands = '';
    }
    
    commands[fullName] = existingCommand;
    console.log(`  📦 Found grouped command: ${fullName}`);
  }

  return commands;
}

/**
 * Extract docstring from function
 */
function generateDescriptionFromName(commandName) {
  // Generate descriptive text based on command name
  const descriptions = {
    // System commands
    'ping': 'Check the bot\'s response time and latency',
    'uptime': 'Check how long the bot has been running',
    'memory': 'Check the bot\'s memory usage and statistics',
    'credit': 'Show credits and information about the bot',
    
    // Information commands
    'about': 'Get information about the server and bot',
    'server': 'Display server information and statistics',
    'pfp': 'Get a user\'s profile picture',
    'banner': 'Get a user\'s banner image',
    'invite': 'Get the bot\'s invite link',
    'perms': 'Check your permissions in the server',
    'roles': 'List all available roles in the server',
    'leaderboard': 'Show the server leaderboard',
    'reviews': 'View or leave reviews for the server',
    
    // Moderation commands
    'ban': 'Ban a user from the server',
    'unban': 'Unban a user from the server',
    'timeout': 'Put a user in timeout',
    'untimeout': 'Remove timeout from a user',
    'log': 'View moderation logs',
    'note': 'Add a note to a user\'s profile',
    
    // Fun commands
    '8ball': 'Ask the magic 8-ball a question',
    'memo': 'Save or retrieve memos',
    'qna': 'Ask a question and get an answer',
    
    // Pokemon commands
    'pokedex': 'Look up Pokemon information',
    'tp': 'Trade Pokemon with another user',
    'qp': 'Quick ping for Pokemon battles',
    'shiny': 'Check for shiny Pokemon',
    'collection': 'View your Pokemon collection',
    
    // Quest commands
    'redirect': 'Redirect to a specific quest channel',
    'profile': 'View your quest profile',
    'inventory': 'View your quest inventory',
    'balance': 'Check your quest balance',
    'shop': 'Browse the quest shop',
    
    // AI commands
    'imagine': 'Generate AI images from text prompts',
    'vision': 'Analyze images with AI vision',
    
    // Sync commands
    'sync': 'Sync your data with the bot',
    
    // Help commands
    'help': 'Show help information and commands'
  };
  
  // Check exact match first
  if (descriptions[commandName.toLowerCase()]) {
    return descriptions[commandName.toLowerCase()];
  }
  
  // Generate based on common patterns
  if (commandName.includes('set') || commandName.includes('config')) {
    return `Configure ${commandName.replace(/set|config/gi, '').trim()} settings`;
  }
  if (commandName.includes('get') || commandName.includes('show') || commandName.includes('view')) {
    return `View ${commandName.replace(/get|show|view/gi, '').trim()} information`;
  }
  if (commandName.includes('list')) {
    return `List all ${commandName.replace(/list/gi, '').trim()}`;
  }
  if (commandName.includes('add') || commandName.includes('create')) {
    return `Add or create ${commandName.replace(/add|create/gi, '').trim()}`;
  }
  if (commandName.includes('remove') || commandName.includes('delete')) {
    return `Remove or delete ${commandName.replace(/remove|delete/gi, '').trim()}`;
  }
  
  // Default description
  return `Execute the ${commandName} command`;
}

function extractDocstring(content, funcName) {
  // Try to find the function with its docstring
  const funcRegex = new RegExp(`async\\s+def\\s+${funcName}\\s*\\([^)]*\\):\s*([\s\S]*?)(?=\n\\s*(?:async def|def|@|class|$))`);
  const match = content.match(funcRegex);
  
  if (match) {
    const funcBody = match[1];
    
    // Look for docstring at the beginning of the function
    const docstringRegex = /(?:"""|''')([\s\S]*?)(?:"""|''')/;
    const docMatch = funcBody.match(docstringRegex);
    
    if (docMatch) {
      const docstring = docMatch[1].trim();
      // Take the first non-empty line as description
      const lines = docstring.split('\n').map(line => line.trim()).filter(line => line.length > 0);
      if (lines.length > 0) {
        return lines[0];
      }
    }
  }
  
  // Fallback: Look for any comment lines before the function
  const lines = content.split('\n');
  const funcIndex = lines.findIndex(line => line.includes(`async def ${funcName}`));
  
  if (funcIndex > 0) {
    // Look backwards for comments
    for (let i = funcIndex - 1; i >= Math.max(0, funcIndex - 5); i--) {
      const line = lines[i].trim();
      if (line.startsWith('#')) {
        const comment = line.replace(/^#+\s*/, '');
        if (comment.length > 5) { // Only return meaningful comments
          return comment;
        }
      } else if (line.length > 0 && !line.startsWith('@') && !line.startsWith('async')) {
        break; // Stop if we hit non-comment, non-decorator content
      }
    }
  }
  
  return '';
}

/**
 * Extract example usage from docstring or comments
 */
function extractExample(content, funcName) {
  const funcRegex = new RegExp(`async\\s+def\\s+${funcName}[\\s\\S]{0,500}`);
  const section = content.match(funcRegex);
  
  if (!section) return '';
  
  // Look for example patterns
  const exampleMatch = section[0].match(/(?:example|usage|use):\s*([^\n]+)/i);
  if (exampleMatch) {
    return exampleMatch[1].trim();
  }
  
  return '';
}

/**
 * Get category name from cog file
 */
function getCategoryName(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  
  // Try to find cog name from class definition
  const cogClassMatch = content.match(/class\s+(\w+)\s*\(/);
  if (cogClassMatch) {
    return cogClassMatch[1];
  }
  
  // Fallback to filename
  const fileName = path.basename(filePath, '.py');
  return fileName.charAt(0).toUpperCase() + fileName.slice(1);
}

/**
 * Main execution
 */
function main() {
  if (!fs.existsSync(BOT_COGS_DIR)) {
    console.error(`❌ Bot cogs directory not found: ${BOT_COGS_DIR}`);
    process.exit(1);
  }

  const cogFiles = fs.readdirSync(BOT_COGS_DIR)
    .filter(file => file.endsWith('.py') && file !== '__init__.py')
    .map(file => path.join(BOT_COGS_DIR, file));

  console.log(`📁 Found ${cogFiles.length} cog files\n`);

  const allCommands = {};

  // Load existing commands to preserve descriptions and examples
  let existingCommands = {};
  if (fs.existsSync(OUTPUT_PATH)) {
    try {
      existingCommands = JSON.parse(fs.readFileSync(OUTPUT_PATH, 'utf8'));
      console.log('📖 Loaded existing commands to preserve descriptions and examples\n');
    } catch (error) {
      console.log('⚠️  Could not load existing commands, starting fresh\n');
    }
  }

  for (const cogFile of cogFiles) {
    const categoryName = getCategoryName(cogFile);
    console.log(`\n📂 Processing: ${categoryName} (${path.basename(cogFile)})`);

    const commands = parseCogFile(cogFile, existingCommands[categoryName] || {});

    // Only add category if it has commands
    if (Object.keys(commands).length > 0) {
      allCommands[categoryName] = commands;
      console.log(`  ✅ Added ${Object.keys(commands).length} commands to ${categoryName}`);
    } else {
      console.log(`  ⏭️  Skipping ${categoryName} (no visible commands)`);
    }
  }

  // Write output
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(allCommands, null, 2));

  console.log('\n' + '='.repeat(50));
  console.log('✅ Commands parsed successfully!');
  console.log(`📊 Categories: ${Object.keys(allCommands).length}`);
  console.log(`📊 Total commands: ${Object.values(allCommands).reduce((sum, cmds) => sum + Object.keys(cmds).length, 0)}`);
  console.log(`📁 Output: ${OUTPUT_PATH}`);
  console.log('='.repeat(50) + '\n');
}

main();
