import express from 'express';

const router = express.Router();

// Enable CORS for all routes
router.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  next();
});

// Proxy Danbooru API requests
router.get('/posts.json', async (req, res) => {
  try {
    const { tags, limit = 20, order = 'score' } = req.query;

    // Build Danbooru API URL - try different endpoints if needed
    let baseUrl = 'https://danbooru.donmai.us/posts.json';

    // Some APIs might require different approaches
    const params = new URLSearchParams();

    if (tags) params.append('tags', tags as string);
    if (limit) params.append('limit', limit as string);
    if (order && order !== 'score') params.append('order', order as string);

    const apiUrl = `${baseUrl}?${params.toString()}`;

    console.log(`[Danbooru API] Fetching: ${apiUrl}`);

    const response = await fetch(apiUrl, {
      headers: {
        'User-Agent': 'Anya-Bot-Character-Hosting/1.0',
        'Accept': 'application/json',
        // Try without authentication first
      },
      // Add timeout
      signal: AbortSignal.timeout(10000)
    });

    console.log(`[Danbooru API] Response status: ${response.status}`);

    if (!response.ok) {
      console.error(`[Danbooru API] Failed with status ${response.status}: ${response.statusText}`);
      // If 403, try a different approach or return empty array
      if (response.status === 403 || response.status === 401) {
        console.log('[Danbooru API] Authentication/rate limit issue, returning empty results');
        return res.json([]);
      }
      throw new Error(`Danbooru API returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`[Danbooru API] Successfully fetched ${data.length} posts`);
    res.json(data);
  } catch (error) {
    console.error('Error in Danbooru API:', error);
    // Return empty array instead of error to prevent client crashes
    res.json([]);
  }
});

export default router;
