import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';
import fetch from 'node-fetch';

// Initialize Firebase Admin
admin.initializeApp();

// In-memory cache for bot stats (shared across all requests on same instance)
let statsCache: {
  data: BotStats | null;
  timestamp: number;
} = {
  data: null,
  timestamp: 0
};

// Cache duration: 5 minutes (300,000 ms)
const CACHE_DURATION = 5 * 60 * 1000;

interface BotStats {
  servers: number;
  users: number;
  commands: number;
  status: 'online' | 'offline' | 'idle' | 'unknown';
  lastUpdated: string;
}

interface DiscordGuild {
  id: string;
  name: string;
  approximate_member_count?: number;
}

/**
 * Fetch bot guilds from Discord API
 */
async function fetchDiscordGuilds(token: string): Promise<DiscordGuild[]> {
  try {
    const response = await fetch('https://discord.com/api/v10/users/@me/guilds?with_counts=true', {
      headers: {
        'Authorization': `Bot ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 429) {
        console.warn('Discord API rate limited');
        return [];
      }
      throw new Error(`Discord API error: ${response.status}`);
    }

    return await response.json() as DiscordGuild[];
  } catch (error) {
    console.error('Failed to fetch Discord guilds:', error);
    return [];
  }
}

/**
 * Calculate user count from guilds
 */
function calculateUserCount(guilds: DiscordGuild[]): number {
  const total = guilds.reduce((sum, guild) => {
    return sum + (guild.approximate_member_count || 0);
  }, 0);

  // Estimate if no counts available
  if (total === 0 && guilds.length > 0) {
    return guilds.length * 500;
  }

  return total;
}

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
 * Get bot stats - main logic
 */
async function getBotStats(): Promise<BotStats> {
  const token = process.env.DISCORD_BOT_TOKEN || functions.config().discord?.token;
  
  if (!token) {
    console.warn('Discord bot token not configured');
    return {
      servers: 0,
      users: 0,
      commands: 50,
      status: 'unknown',
      lastUpdated: new Date().toISOString(),
    };
  }

  const guilds = await fetchDiscordGuilds(token);
  const userCount = calculateUserCount(guilds);

  return {
    servers: guilds.length,
    users: userCount,
    commands: 50, // Could be fetched from a config
    status: guilds.length > 0 ? 'online' : 'unknown',
    lastUpdated: new Date().toISOString(),
  };
}

/**
 * HTTP Function: Get bot statistics
 * This is called by all website visitors, but only fetches from Discord API
 * every 5 minutes (uses server-side cache)
 */
export const botStats = functions.https.onRequest(async (req, res) => {
  // Enable CORS
  res.set('Access-Control-Allow-Origin', '*');
  res.set('Access-Control-Allow-Methods', 'GET');
  res.set('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(204).send('');
    return;
  }

  if (req.method !== 'GET') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  try {
    const now = Date.now();

    // Check if cache is still valid
    if (statsCache.data && (now - statsCache.timestamp) < CACHE_DURATION) {
      console.log('Returning cached stats');
      res.set('X-Cache', 'HIT');
      res.set('Cache-Control', 'public, max-age=60'); // Browser can cache for 1 min
      res.json({
        ...statsCache.data,
        cached: true,
        cacheAge: Math.floor((now - statsCache.timestamp) / 1000),
      });
      return;
    }

    // Fetch fresh stats
    console.log('Fetching fresh stats from Discord API');
    const stats = await getBotStats();

    // Update cache
    statsCache = {
      data: stats,
      timestamp: now,
    };

    // Also store in Firestore for persistence across function instances
    try {
      await admin.firestore().collection('cache').doc('botStats').set({
        ...stats,
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
      });
    } catch (firestoreError) {
      console.warn('Failed to update Firestore cache:', firestoreError);
    }

    res.set('X-Cache', 'MISS');
    res.set('Cache-Control', 'public, max-age=60');
    res.json({
      ...stats,
      cached: false,
    });

  } catch (error) {
    console.error('Error fetching bot stats:', error);
    
    // Try to return cached data even if stale
    if (statsCache.data) {
      res.set('X-Cache', 'STALE');
      res.json({
        ...statsCache.data,
        cached: true,
        stale: true,
      });
      return;
    }

    res.status(500).json({
      error: 'Failed to fetch bot stats',
      servers: 0,
      users: 0,
      commands: 50,
      status: 'unknown',
    });
  }
});

/**
 * Scheduled function: Refresh stats every 5 minutes
 * This ensures the cache is always warm
 */
export const refreshBotStats = functions.pubsub
  .schedule('every 5 minutes')
  .onRun(async () => {
    console.log('Scheduled refresh of bot stats');
    
    try {
      const stats = await getBotStats();
      
      statsCache = {
        data: stats,
        timestamp: Date.now(),
      };

      await admin.firestore().collection('cache').doc('botStats').set({
        ...stats,
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
      });

      console.log('Bot stats refreshed successfully');
    } catch (error) {
      console.error('Failed to refresh bot stats:', error);
    }

    return null;
  });

/**
 * On cold start, try to load cached stats from Firestore
 */
async function loadCachedStats() {
  try {
    const doc = await admin.firestore().collection('cache').doc('botStats').get();
    if (doc.exists) {
      const data = doc.data();
      if (data) {
        statsCache = {
          data: {
            servers: data.servers,
            users: data.users,
            commands: data.commands,
            status: data.status,
            lastUpdated: data.lastUpdated,
          },
          timestamp: data.timestamp?.toMillis() || Date.now() - CACHE_DURATION,
        };
        console.log('Loaded cached stats from Firestore');
      }
    }
  } catch (error) {
    console.warn('Could not load cached stats from Firestore:', error);
  }
}

// Load cached stats on cold start
loadCachedStats();
