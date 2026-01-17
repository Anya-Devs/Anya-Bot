import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';
import fetch from 'node-fetch';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { MongoClient } from 'mongodb';

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

// Bot configuration for token retrieval
const botConfig = {
  test: { prefix: '-', token_key: 'Test_Token' },
  prod: { prefix: '.', token_key: 'Token' }
};

// Cache for bot token (avoid repeated DB calls)
let tokenCache: { token: string | null; timestamp: number } = { token: null, timestamp: 0 };
const TOKEN_CACHE_DURATION = 10 * 60 * 1000; // 10 minutes

/**
 * Get bot token from MongoDB
 */
async function getBotToken(): Promise<string | null> {
  // Return cached token if still valid
  const now = Date.now();
  if (tokenCache.token && (now - tokenCache.timestamp) < TOKEN_CACHE_DURATION) {
    return tokenCache.token;
  }

  const mongoUrl = process.env.MONGO_URI || functions.config().mongo?.uri;
  if (!mongoUrl) {
    console.warn('No MONGO_URI configured');
    return null;
  }

  const client = new MongoClient(mongoUrl);
  try {
    await client.connect();
    const db = client.db('Bot');
    const collection = db.collection('information');

    // Use prod config by default
    const config = botConfig.prod;
    const tokenData = await collection.findOne({ [config.token_key]: { $exists: true } });

    if (tokenData && tokenData[config.token_key]) {
      tokenCache = { token: tokenData[config.token_key], timestamp: now };
      return tokenData[config.token_key];
    }
    
    console.warn('No token found in database');
    return null;
  } catch (error) {
    console.error('Failed to get token from MongoDB:', error);
    return null;
  } finally {
    await client.close();
  }
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
 * Get bot stats - main logic
 */
async function getBotStats(): Promise<BotStats> {
  // Try MongoDB first, then fall back to env/config
  const token = await getBotToken() || process.env.DISCORD_BOT_TOKEN || functions.config().discord?.token;
  
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

// Cache for font data
let fontCache: ArrayBuffer | null = null;

/**
 * Load Inter font for OG image rendering
 */
async function loadFont(): Promise<ArrayBuffer> {
  if (fontCache) {
    return fontCache;
  }
  
  // Fetch Inter Bold from Google Fonts
  const fontUrl = 'https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuGKYAZ9hjp-Ek-_EeA.woff';
  const response = await fetch(fontUrl);
  const buffer = await response.arrayBuffer();
  fontCache = buffer;
  return buffer;
}

/**
 * HTTP Function: Generate OG Image
 * Renders a dynamic OG image for Discord/Twitter/Facebook embeds
 */
export const ogImage = functions.https.onRequest(async (req, res) => {
  // Enable CORS
  res.set('Access-Control-Allow-Origin', '*');
  res.set('Access-Control-Allow-Methods', 'GET');

  if (req.method === 'OPTIONS') {
    res.status(204).send('');
    return;
  }

  if (req.method !== 'GET') {
    res.status(405).send('Method not allowed');
    return;
  }

  try {
    // Load font
    const fontData = await loadFont();

    // Get optional page parameter for dynamic images
    const page = (req.query.page as string) || 'home';
    
    // Define content based on page
    let title = 'Anya Bot';
    let subtitle = 'Your Ultimate Discord Companion';
    let features = ['🎮 100+ Commands', '🔍 Pokémon Detection', '📺 Anime Lookup', '🎉 Fun & Games'];
    
    if (page === 'commands') {
      title = 'Anya Bot Commands';
      subtitle = 'Browse All Available Commands';
      features = ['📖 Full Command List', '🔧 Easy to Use', '💡 Examples Included', '🎯 Categories'];
    } else if (page === 'features') {
      title = 'Anya Bot Features';
      subtitle = 'Explore What Anya Can Do';
      features = ['🌟 Pokétwo Helper', '🎭 Fun Commands', '🔔 Smart Alerts', '⚡ Fast & Reliable'];
    }

    // Create the TSX element (satori uses React-like JSX)
    const element = {
      type: 'div',
      props: {
        style: {
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%)',
          fontFamily: 'Inter',
          position: 'relative',
        },
        children: [
          // Glow effect 1
          {
            type: 'div',
            props: {
              style: {
                position: 'absolute',
                width: '400px',
                height: '400px',
                background: 'radial-gradient(circle, rgba(255,107,157,0.3) 0%, transparent 70%)',
                top: '-100px',
                right: '-100px',
                borderRadius: '50%',
              },
            },
          },
          // Glow effect 2
          {
            type: 'div',
            props: {
              style: {
                position: 'absolute',
                width: '300px',
                height: '300px',
                background: 'radial-gradient(circle, rgba(147,51,234,0.2) 0%, transparent 70%)',
                bottom: '-50px',
                left: '-50px',
                borderRadius: '50%',
              },
            },
          },
          // Main container
          {
            type: 'div',
            props: {
              style: {
                display: 'flex',
                alignItems: 'center',
                gap: '60px',
                zIndex: 1,
              },
              children: [
                // Avatar
                {
                  type: 'div',
                  props: {
                    style: {
                      width: '180px',
                      height: '180px',
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #FF6B9D 0%, #c084fc 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '80px',
                      boxShadow: '0 0 60px rgba(255,107,157,0.4)',
                      border: '4px solid rgba(255,107,157,0.5)',
                    },
                    children: '🎀',
                  },
                },
                // Content
                {
                  type: 'div',
                  props: {
                    style: {
                      display: 'flex',
                      flexDirection: 'column',
                      maxWidth: '700px',
                    },
                    children: [
                      // Title
                      {
                        type: 'div',
                        props: {
                          style: {
                            fontSize: '64px',
                            fontWeight: 800,
                            background: 'linear-gradient(135deg, #FF6B9D 0%, #c084fc 100%)',
                            backgroundClip: 'text',
                            color: 'transparent',
                            marginBottom: '16px',
                          },
                          children: title,
                        },
                      },
                      // Subtitle
                      {
                        type: 'div',
                        props: {
                          style: {
                            fontSize: '26px',
                            color: '#a0a0b0',
                            marginBottom: '24px',
                          },
                          children: subtitle,
                        },
                      },
                      // Features
                      {
                        type: 'div',
                        props: {
                          style: {
                            display: 'flex',
                            gap: '16px',
                            flexWrap: 'wrap',
                          },
                          children: features.map(feature => ({
                            type: 'div',
                            props: {
                              style: {
                                background: 'rgba(255,255,255,0.1)',
                                padding: '10px 20px',
                                borderRadius: '24px',
                                color: '#fff',
                                fontSize: '16px',
                                border: '1px solid rgba(255,107,157,0.3)',
                              },
                              children: feature,
                            },
                          })),
                        },
                      },
                    ],
                  },
                },
              ],
            },
          },
          // URL at bottom
          {
            type: 'div',
            props: {
              style: {
                position: 'absolute',
                bottom: '24px',
                color: '#666',
                fontSize: '18px',
              },
              children: 'anya-bot-1fe76.web.app',
            },
          },
        ],
      },
    };

    // Render to SVG using satori
    const svg = await satori(element as any, {
      width: 1200,
      height: 630,
      fonts: [
        {
          name: 'Inter',
          data: fontData,
          weight: 800,
          style: 'normal',
        },
      ],
    });

    // Convert SVG to PNG using resvg
    const resvg = new Resvg(svg, {
      fitTo: {
        mode: 'width',
        value: 1200,
      },
    });
    const pngData = resvg.render();
    const pngBuffer = pngData.asPng();

    // Set cache headers (cache for 1 hour)
    res.set('Cache-Control', 'public, max-age=3600, s-maxage=86400');
    res.set('Content-Type', 'image/png');
    res.send(Buffer.from(pngBuffer));

  } catch (error) {
    console.error('Error generating OG image:', error);
    res.status(500).send('Failed to generate image');
  }
});
