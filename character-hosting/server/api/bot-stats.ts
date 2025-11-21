import express from 'express';
import { MongoClient } from 'mongodb';

const router = express.Router();

// Enable CORS for all routes
router.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  next();
});

// Bot configuration
const botConfig = {
  test: {
    prefix: "-",
    token_key: "Test_Token"
  },
  prod: {
    prefix: ".",
    token_key: "Token"
  }
};

const useTestBot = process.env.NODE_ENV === 'development' || process.env.USE_TEST_BOT === 'true';

async function getBotToken() {
  const mongoUrl = process.env.MONGO_URI;
  if (!mongoUrl) {
    throw new Error("No MONGO_URI found in environment variables");
  }

  const client = new MongoClient(mongoUrl);
  try {
    await client.connect();
    const db = client.db("Bot");
    const collection = db.collection("information");

    const config = useTestBot ? botConfig.test : botConfig.prod;
    const tokenData = await collection.findOne({ [config.token_key]: { $exists: true } });

    if (tokenData) {
      return tokenData[config.token_key];
    } else {
      throw new Error(`No token found in the database for key: ${config.token_key}`);
    }
  } finally {
    await client.close();
  }
}

// Get bot stats endpoint
router.get('/stats', async (req, res) => {
  try {
    const token = await getBotToken();

    // Fetch bot guilds from Discord API
    const guildsResponse = await fetch('https://discord.com/api/v10/users/@me/guilds', {
      headers: {
        'Authorization': `Bot ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!guildsResponse.ok) {
      throw new Error(`Discord API error: ${guildsResponse.status}`);
    }

    const guilds = await guildsResponse.json();

    // Calculate total member count
    const totalMembers = guilds.reduce((sum: number, guild: any) => sum + (guild.approximate_member_count || 0), 0);
    const totalServers = guilds.length;

    // Fetch bot user info
    const botResponse = await fetch('https://discord.com/api/v10/users/@me', {
      headers: {
        'Authorization': `Bot ${token}`,
        'Content-Type': 'application/json',
      },
    });

    let botInfo = null;
    if (botResponse.ok) {
      botInfo = await botResponse.json();
    }

    res.json({
      totalServers,
      totalMembers,
      botInfo,
      lastUpdated: new Date().toISOString()
    });

  } catch (error) {
    console.error('Error fetching bot stats:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
    res.status(500).json({
      error: 'Failed to fetch bot statistics',
      message: errorMessage
    });
  }
});

export default router;
