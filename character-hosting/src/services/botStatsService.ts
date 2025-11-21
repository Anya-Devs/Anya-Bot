// Bot statistics service with proper TypeScript types and error handling

interface BotStats {
  servers: number | string;
  users: number | string;
  commands: number | string;
  uptime: string;
  lastUpdated: Date;
}

// Cache for bot stats
let statsCache: BotStats | null = null;
let lastFetchTime: number = 0;
const CACHE_DURATION_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Get command count from the bot
 */
async function getCommandCount(): Promise<number> {
  try {
    // Replace with your actual command count logic
    // Example: Count files in commands directory
    // const commandFiles = await fs.readdir(path.join(__dirname, '../commands'));
    // return commandFiles.filter(file => file.endsWith('.js') || file.endsWith('.ts')).length;
    return 50; // Example value
  } catch (error) {
    console.error('Failed to get command count:', error);
    return 0;
  }
}

/**
 * Main function to fetch bot statistics
 */
export async function fetchBotStats(): Promise<BotStats> {
  // Return cached stats if they're still fresh
  const now = Date.now();
  if (statsCache && (now - lastFetchTime) < CACHE_DURATION_MS) {
    return statsCache;
  }

  try {
    // Get command count only (server count requires backend authentication)
    const commandCount = await getCommandCount();

    // Get uptime (not available in browser environment)
    const uptime = 'N/A';

    // Create stats object
    const stats: BotStats = {
      servers: 'N/A', // Requires backend authentication
      users: 'N/A', // Requires privileged intents or database
      commands: commandCount,
      uptime,
      lastUpdated: new Date()
    };

    // Update cache
    statsCache = stats;
    lastFetchTime = now;

    return stats;
  } catch (error) {
    console.error('Error fetching bot stats:', error);

    // Return fallback stats if there's an error
    return {
      servers: 'N/A',
      users: 'N/A',
      commands: await getCommandCount(),
      uptime: 'N/A',
      lastUpdated: new Date()
    };
  }
}