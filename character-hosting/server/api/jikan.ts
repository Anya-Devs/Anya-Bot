import express from 'express';

const router = express.Router();

// Enable CORS for all routes
router.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  next();
});

// Proxy Jikan API character search requests
router.get('/characters', async (req, res) => {
  try {
    const { q, limit = 1 } = req.query;

    // Build Jikan API URL
    const baseUrl = 'https://api.jikan.moe/v4/characters';
    const params = new URLSearchParams();

    if (q) params.append('q', q as string);
    if (limit) params.append('limit', limit as string);

    const apiUrl = `${baseUrl}?${params.toString()}`;

    console.log(`[Jikan API] Fetching characters: ${apiUrl}`);

    const response = await fetch(apiUrl, {
      headers: {
        'User-Agent': 'Anya-Bot-Character-Hosting/1.0',
        'Accept': 'application/json'
      },
      signal: AbortSignal.timeout(10000)
    });

    console.log(`[Jikan API] Response status: ${response.status}`);

    if (!response.ok) {
      console.error(`[Jikan API] Failed with status ${response.status}: ${response.statusText}`);
      if (response.status === 403 || response.status === 401) {
        console.log('[Jikan API] Authentication/rate limit issue, returning empty results');
        return res.json({ data: [] });
      }
      throw new Error(`Jikan API returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`[Jikan API] Successfully fetched ${data.data?.length || 0} characters`);
    res.json(data);
  } catch (error) {
    console.error('Error in Jikan API:', error);
    res.json({ data: [] });
  }
});

export default router;
