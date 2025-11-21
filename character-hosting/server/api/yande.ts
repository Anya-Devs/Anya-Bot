import express from 'express';

const router = express.Router();

// Enable CORS for all routes
router.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  next();
});

// Proxy Yande.re API requests
router.get('/post.json', async (req, res) => {
  try {
    const { tags, limit = 20 } = req.query;

    // Build Yande.re API URL
    const baseUrl = 'https://yande.re/post.json';
    const params = new URLSearchParams();

    if (tags) params.append('tags', tags as string);
    if (limit) params.append('limit', limit as string);

    const apiUrl = `${baseUrl}?${params.toString()}`;

    console.log(`[Yande.re API] Fetching: ${apiUrl}`);

    const response = await fetch(apiUrl, {
      headers: {
        'User-Agent': 'Anya-Bot-Character-Hosting/1.0',
        'Accept': 'application/json'
      },
      signal: AbortSignal.timeout(10000)
    });

    console.log(`[Yande.re API] Response status: ${response.status}`);

    if (!response.ok) {
      console.error(`[Yande.re API] Failed with status ${response.status}: ${response.statusText}`);
      if (response.status === 403 || response.status === 401) {
        console.log('[Yande.re API] Authentication/rate limit issue, returning empty results');
        return res.json([]);
      }
      throw new Error(`Yande.re API returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`[Yande.re API] Successfully fetched ${data.length} posts`);
    res.json(data);
  } catch (error) {
    console.error('Error in Yande.re API:', error);
    res.json([]);
  }
});

export default router;
