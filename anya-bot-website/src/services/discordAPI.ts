// Discord Official API service for bot statistics

// Cache for bot token
let cachedToken: string | null = null;

// Cache for API results to avoid rate limiting
let guildCache: { data: DiscordGuild[]; timestamp: number } | null = null;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes cache

/**
 * Get Discord bot token from environment variable
 * Token should be set in .env as VITE_DISCORD_BOT_TOKEN
 */
function getBotToken(): string | null {
  if (cachedToken) {
    return cachedToken;
  }

  const envToken = import.meta.env.VITE_DISCORD_BOT_TOKEN;
  if (envToken) {
    cachedToken = envToken;
    return envToken;
  }

  return null;
}

/**
 * Format large numbers (1000 -> "1K+", 1500000 -> "1.5M+")
 */
export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M+';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'K+';
  }
  return num.toString();
}

interface DiscordGuild {
  id: string;
  name: string;
  icon: string | null;
  owner: boolean;
  permissions: string;
  features: string[];
  approximate_member_count?: number;
  approximate_presence_count?: number;
}

interface DiscordBotStats {
  guilds: number;
  users: number;
  uptime: number;
  shards: number;
}

/**
 * Fetch bot guilds from Discord API
 * Uses token from VITE_DISCORD_BOT_TOKEN environment variable
 * Includes caching to prevent rate limiting
 */
async function fetchBotGuilds(): Promise<DiscordGuild[]> {
  // Return cached data if still valid
  if (guildCache && Date.now() - guildCache.timestamp < CACHE_TTL) {
    return guildCache.data;
  }

  const token = getBotToken();
  
  if (!token) {
    // Silent fail - token not configured
    return [];
  }

  try {
    const response = await fetch('https://discord.com/api/v10/users/@me/guilds?with_counts=true', {
      headers: {
        'Authorization': `Bot ${token}`,
        'Content-Type': 'application/json',
      },
    });

    // Handle rate limiting
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      console.warn(`Rate limited. Retry after ${retryAfter}s. Using cached data.`);
      return guildCache?.data || [];
    }

    if (!response.ok) {
      throw new Error(`Discord API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    
    // Cache the result
    guildCache = { data, timestamp: Date.now() };
    
    return data;
  } catch (error) {
    console.error('Failed to fetch Discord guilds:', error);
    return guildCache?.data || [];
  }
}

/**
 * Fetch bot application info from Discord API
 */
export async function fetchBotApplication() {
  const token = getBotToken();
  
  if (!token) {
    return null;
  }

  try {
    const response = await fetch('https://discord.com/api/v10/oauth2/applications/@me', {
      headers: {
        'Authorization': `Bot ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Discord API error: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Failed to fetch bot application:', error);
    return null;
  }
}

/**
 * Calculate approximate user count from guilds
 */
function calculateUserCount(guilds: DiscordGuild[]): number {
  // Sum up approximate member counts if available
  const total = guilds.reduce((sum, guild) => {
    return sum + (guild.approximate_member_count || 0);
  }, 0);

  // If no approximate counts, estimate based on average guild size
  if (total === 0 && guilds.length > 0) {
    return guilds.length * 500; // Rough estimate
  }

  return total;
}

/**
 * Get comprehensive bot statistics from Discord API
 */
export async function fetchDiscordBotStats(): Promise<DiscordBotStats> {
  const guilds = await fetchBotGuilds();
  const userCount = calculateUserCount(guilds);

  return {
    guilds: guilds.length,
    users: userCount,
    uptime: performance.now(), // Approximation - would need backend for real uptime
    shards: 1, // Would need to be configured based on your bot setup
  };
}

/**
 * Check if Discord API is configured
 */
export function isDiscordAPIConfigured(): boolean {
  return !!getBotToken();
}

/**
 * Get bot status (online/offline/idle)
 * Uses cached guild data to avoid extra API calls
 */
export function getBotStatus(): 'online' | 'offline' | 'idle' | 'unknown' {
  if (!getBotToken()) {
    return 'unknown';
  }
  
  // If we have cached guilds, bot is online
  if (guildCache && guildCache.data.length > 0) {
    // Check if cache is fresh (within 5 mins = online, older = idle)
    const age = Date.now() - guildCache.timestamp;
    if (age < CACHE_TTL) {
      return 'online';
    } else {
      return 'idle';
    }
  }
  
  return 'unknown';
}
