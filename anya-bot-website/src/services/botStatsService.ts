// Bot statistics service - uses server-side API to prevent rate limiting
// All clients share the same cached data from Firebase Functions

interface BotStats {
  servers: number | string;
  users: number | string;
  commands: number | string;
  status: 'online' | 'offline' | 'idle' | 'unknown';
  lastUpdated: Date;
}

interface ServerBotStats {
  servers: number;
  users: number;
  commands: number;
  status: 'online' | 'offline' | 'idle' | 'unknown';
  lastUpdated: string;
  cached?: boolean;
  cacheAge?: number;
}

// Local cache for stats (short TTL since server handles the real caching)
let statsCache: BotStats | null = null;
let lastFetchTime: number = 0;
const LOCAL_CACHE_MS = 30 * 1000; // 30 seconds local cache

/**
 * Format large numbers (1000 -> "1K+")
 */
function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M+';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K+';
  }
  return num.toString();
}

/**
 * Get command count from the bot's commands.json
 */
async function getCommandCount(): Promise<number> {
  try {
    const response = await fetch('/commands.json');
    if (response.ok) {
      const commands = await response.json();
      return Object.keys(commands).length;
    }
    return 50;
  } catch {
    return 50;
  }
}

/**
 * Fetch bot stats from server-side API
 * The server handles rate limiting and caching - all clients share the same data
 */
async function fetchFromServer(): Promise<ServerBotStats | null> {
  try {
    // Use the Firebase Function endpoint
    const response = await fetch('/api/bot-stats');
    
    if (!response.ok) {
      console.warn('Server stats API returned:', response.status);
      return null;
    }
    
    const data = await response.json();
    console.log(`📊 Bot stats ${data.cached ? '(cached)' : '(fresh)'}`);
    return data;
  } catch (error) {
    console.warn('Failed to fetch from server API:', error);
    return null;
  }
}

/**
 * Main function to fetch bot statistics
 * Uses server-side caching to prevent API spam
 */
export async function fetchBotStats(): Promise<BotStats> {
  // Return local cache if still fresh
  const now = Date.now();
  if (statsCache && (now - lastFetchTime) < LOCAL_CACHE_MS) {
    return statsCache;
  }

  try {
    // Try to fetch from server API (shared cache)
    const serverStats = await fetchFromServer();
    const commandCount = await getCommandCount();
    
    let stats: BotStats;
    
    if (serverStats) {
      stats = {
        servers: formatNumber(serverStats.servers),
        users: formatNumber(serverStats.users),
        commands: commandCount,
        status: serverStats.status,
        lastUpdated: new Date(serverStats.lastUpdated)
      };
    } else {
      // Fallback to N/A if server is unavailable
      stats = {
        servers: 'N/A',
        users: 'N/A',
        commands: commandCount,
        status: 'unknown',
        lastUpdated: new Date()
      };
    }

    // Update local cache
    statsCache = stats;
    lastFetchTime = now;

    return stats;
  } catch (error) {
    console.error('Error fetching bot stats:', error);

    return {
      servers: 'N/A',
      users: 'N/A',
      commands: await getCommandCount(),
      status: 'unknown',
      lastUpdated: new Date()
    };
  }
}

/**
 * Get cached status (doesn't make new requests)
 */
export function getCachedStatus(): 'online' | 'offline' | 'idle' | 'unknown' {
  return statsCache?.status || 'unknown';
}