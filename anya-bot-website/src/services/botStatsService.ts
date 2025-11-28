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
      return Object.values(commands).reduce((total: number, category: any) => {
        if (category && typeof category === 'object') {
          return total + Object.keys(category).length;
        }
        return total;
      }, 0);
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
    // Avoid hammering the dev server with proxy errors when Firebase Functions aren't running locally
    if (import.meta.env?.DEV && !import.meta.env?.VITE_FUNCTIONS_BASE_URL) {
      return null;
    }

    // Use the Firebase Function endpoint
    const baseUrl = import.meta.env?.VITE_FUNCTIONS_BASE_URL || '';
    const response = await fetch(`${baseUrl}/api/bot-stats`);
    
    if (!response.ok) {
      // Silently fail - functions may not be deployed
      return null;
    }
    
    const data = await response.json();
    console.log(`📊 Bot stats ${data.cached ? '(cached)' : '(fresh)'}`);
    return data;
  } catch (error) {
    if (!(import.meta.env?.DEV)) {
      console.warn('bot-stats fetch failed', error);
    }
    // Silently fail - expected if functions aren't deployed
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
      // Fallback with estimated values when API is unavailable
      stats = {
        servers: '150',
        users: '75K+',
        commands: commandCount,
        status: 'online',
        lastUpdated: new Date()
      };
    }

    // Update local cache
    statsCache = stats;
    lastFetchTime = now;

    return stats;
  } catch {
    // Return fallback values on any error
    return {
      servers: '150',
      users: '75K+',
      commands: await getCommandCount(),
      status: 'online',
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